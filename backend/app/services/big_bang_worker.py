import asyncio
import time
from datetime import datetime, timedelta

def run_worker():
    """Background worker that checks and executes scheduled BIG BANG jobs."""
    print("[NEXUS WORKER] Starting worker...")
    
    while True:
        try:
            check_and_execute_scheduled_jobs()
            check_waiting_recurring_jobs()
            check_and_execute_harvest_jobs()
        except Exception as e:
            print(f"[NEXUS WORKER] Error: {e}")

        time.sleep(60)


def check_and_execute_harvest_jobs():
    """Prende ed esegue i job di search-term harvesting in coda (harvest_jobs.status='QUEUED').

    - Prima recupera i job appesi (RUNNING senza heartbeat) marcandoli FAILED.
    - Poi drena la coda: ogni job viene preso atomicamente (claim -> RUNNING) ed
      eseguito in un thread, cosi' report lunghi non bloccano il loop del worker.
    """
    import threading
    from db.harvest_db import claim_next_harvest_job, fail_stale_harvest_jobs
    from backend.app.services.harvest_service import run_harvest_job

    try:
        stale = fail_stale_harvest_jobs(stale_minutes=10)
        if stale:
            print(f"[HARVEST WORKER] {stale} job stale marcati FAILED")
    except Exception as e:
        print(f"[HARVEST WORKER] Errore recupero stale: {e}")

    launched = 0
    while launched < 10:  # cap per ciclo, evita starvation di altri task
        job = claim_next_harvest_job()
        if not job:
            break

        def run_in_thread(j):
            try:
                run_harvest_job(
                    job_id=j["id"], account_id=j["account_id"], profile_id=j["profile_id"],
                    days=j["days"], min_purchases=j["min_purchases"], dry_run=j["dry_run"],
                )
            except Exception as ex:
                print(f"[HARVEST WORKER] Job {j['id']} fallito: {ex}")

        t = threading.Thread(target=run_in_thread, args=(job,), daemon=True)
        t.start()
        launched += 1
        print(f"[HARVEST WORKER] Avviato harvest job {job['id']} "
              f"(account={job['account_id']}, profile={job['profile_id']}, dry_run={job['dry_run']})")

    if launched:
        print(f"[HARVEST WORKER] {launched} harvest job avviati in questo ciclo")


def check_waiting_recurring_jobs():
    """Check for WAITING recurring jobs that are ready to start their next run.
    
    Instead of creating a new job, directly transitions the WAITING job to RUNNING
    and launches the execution in a background thread.
    """
    from db.accounts_db import get_connection, update_big_bang_job, get_big_bang_job
    from psycopg2.extras import RealDictCursor
    import threading
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM big_bang_jobs 
        WHERE status = 'WAITING' AND next_run_at <= NOW()
        ORDER BY next_run_at ASC
    """)
    waiting_jobs = cur.fetchall()
    cur.close()
    conn.close()
    
    if not waiting_jobs:
        return
    
    print(f"[NEXUS WORKER] Found {len(waiting_jobs)} waiting jobs ready to start")
    
    for job in waiting_jobs:
        job_id = job['id']
        account_id = job['account_id']
        ad_product = job.get('ad_product', 'ALL')
        recurring_interval_days = job.get('recurring_interval_days')
        
        try:
            conn2 = get_connection()
            try:
                conn2.autocommit = False
                cur2 = conn2.cursor()
                cur2.execute("SELECT pg_advisory_xact_lock(%s)", (account_id + 1000000,))
                cur2.execute("""
                    SELECT id FROM big_bang_jobs 
                    WHERE account_id = %s AND status IN ('RUNNING', 'SCHEDULED', 'EXECUTING')
                    LIMIT 1
                """, (account_id,))
                if cur2.fetchone():
                    conn2.rollback()
                    print(f"[NEXUS WORKER] Account {account_id} already has an active job, skipping WAITING job {job_id}")
                    continue
                cur2.execute("""
                    UPDATE big_bang_jobs SET status = 'RUNNING', current_phase = 1,
                    phase_status = 'running', phase_message = 'Avvio ciclo ricorrente...', progress_pct = 0
                    WHERE id = %s AND status = 'WAITING' RETURNING id
                """, (job_id,))
                updated = cur2.fetchone()
                conn2.commit()
            finally:
                conn2.close()
            
            if not updated:
                print(f"[NEXUS WORKER] Job {job_id} already picked up by another process, skipping")
                continue
            
            print(f"[NEXUS WORKER] Starting recurring job {job_id} for account {account_id} ({ad_product})")
            
            def run_in_thread(jid, aid, rid, ap):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    from backend.app.api.routes.autopilot_v2 import run_big_bang_async
                    loop.run_until_complete(run_big_bang_async(jid, aid, rid, ap))
                except Exception as ex:
                    print(f"[NEXUS WORKER] Recurring job {jid} failed: {ex}")
                    update_big_bang_job(jid, status='FAILED', phase_status='failed', error_message=str(ex))
                finally:
                    loop.close()
            
            t = threading.Thread(target=run_in_thread, args=(job_id, account_id, recurring_interval_days, ad_product), daemon=True)
            t.start()
            
        except Exception as e:
            print(f"[NEXUS WORKER] Error starting waiting job {job_id}: {e}")


def _has_executing_job_for_account(account_id: int, current_job_id: int) -> bool:
    """Check if there's already an EXECUTING job for this account (concurrency guard).
    
    Also handles stale EXECUTING jobs (stuck for more than 30 minutes) by marking them FAILED.
    """
    from db.accounts_db import get_connection, update_big_bang_job
    from psycopg2.extras import RealDictCursor
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, created_at, execute_at FROM big_bang_jobs 
        WHERE account_id = %s AND status = 'EXECUTING' AND id != %s
        LIMIT 1
    """, (account_id, current_job_id))
    existing = cur.fetchone()
    cur.close()
    conn.close()
    
    if not existing:
        return False
    
    stale_threshold = datetime.now() - timedelta(minutes=30)
    job_time = existing.get('execute_at') or existing.get('created_at')
    if job_time and job_time < stale_threshold:
        print(f"[NEXUS WORKER] Stale EXECUTING job {existing['id']} detected (>30 min), marking as FAILED")
        update_big_bang_job(
            existing['id'],
            status='FAILED',
            phase_status='failed',
            error_message='Job bloccato per oltre 30 minuti - marcato come fallito'
        )
        return False
    
    return True


def check_and_execute_scheduled_jobs():
    """Check for SCHEDULED jobs where execute_at has passed and run step 6 (bid execution).
    
    The API (run_big_bang_async) handles phases 1-5 and sets status to SCHEDULED.
    This worker only handles:
    - Executing step 6 (bid updates) when the scheduled time arrives
    - Marking the job as COMPLETED
    - Scheduling the next recurring job if applicable
    """
    from db.accounts_db import get_pending_scheduled_jobs, update_big_bang_job
    
    pending_jobs = get_pending_scheduled_jobs()
    
    if not pending_jobs:
        return
    
    print(f"[NEXUS WORKER] Found {len(pending_jobs)} scheduled jobs ready for step 6 execution")
    
    for job in pending_jobs:
        job_id = job['id']
        account_id = job['account_id']
        recurring_mode = job.get('recurring_mode', 'single')
        recurring_interval_days = job.get('recurring_interval_days')
        delay_hours = job.get('delay_hours', 15)
        ad_product = job.get('ad_product', 'SP')
        current_phase = job.get('current_phase', 6)
        
        label = "SP" if ad_product == "SP" else "SB" if ad_product == "SB" else "SP+SB"
        
        try:
            from db.accounts_db import get_big_bang_job
            fresh_job = get_big_bang_job(job_id)
            if not fresh_job or fresh_job['status'] == 'CANCELLED':
                print(f"[NEXUS WORKER] Job {job_id} was cancelled, skipping")
                continue
            
            if _has_executing_job_for_account(account_id, job_id):
                print(f"[NEXUS WORKER] Job {job_id}: another job already EXECUTING for account {account_id}, will retry next cycle (60s)")
                continue
            
            print(f"[NEXUS WORKER] Executing step 6 (bid updates) for job {job_id}, account {account_id} ({label})")
            
            update_big_bang_job(job_id, status='EXECUTING', current_phase=current_phase, phase_status='running',
                               phase_message=f'Fase {current_phase} - Esecuzione in corso...', progress_pct=95)
            
            result = execute_step_6(account_id)
            
            executed = result.get('executed', 0)
            failed = result.get('failed', 0)
            paused = result.get('paused', 0)
            
            update_big_bang_job(
                job_id,
                status='COMPLETED',
                current_phase=current_phase,
                phase_status='completed',
                phase_message=f"Completato - {executed} eseguite, {failed} fallite, {paused} pausate",
                executed_at=datetime.now(),
                last_completed_at=datetime.now(),
                progress_pct=100
            )
            
            print(f"[NEXUS WORKER] Job {job_id} completed step 6: {executed} executed, {failed} failed, {paused} paused")
            
            if recurring_mode is not None and recurring_interval_days is not None:
                schedule_next_recurring_job(
                    account_id, 
                    delay_hours, 
                    ad_product, 
                    recurring_mode, 
                    recurring_interval_days,
                    job.get('next_run_at') or job['created_at']
                )
            
        except Exception as e:
            print(f"[NEXUS WORKER] Job {job_id} step 6 failed: {e}")
            update_big_bang_job(
                job_id,
                status='FAILED',
                phase_status='failed',
                error_message=str(e)
            )


def schedule_next_recurring_job(account_id: int, delay_minutes: int, ad_product: str, recurring_mode: str, recurring_interval_days: int, prev_created_at=None):
    """Schedule the next recurring job after completion.
    
    next_run_at is calculated from prev_created_at + interval, so the cadence
    stays fixed regardless of how long the job takes to execute.
    If prev_created_at is None, falls back to datetime.now().
    """
    from db.accounts_db import get_connection

    base_time = prev_created_at or datetime.now()

    if recurring_interval_days == 0:
        interval = timedelta(hours=1)
        wait_label = "1 ora"
    elif recurring_interval_days == -3:
        interval = timedelta(hours=3)
        wait_label = "3 ore"
    elif recurring_interval_days == 1:
        interval = timedelta(days=1)
        wait_label = "1 giorno"
    elif recurring_interval_days == 3:
        interval = timedelta(days=3)
        wait_label = "3 giorni"
    elif recurring_interval_days == 5:
        interval = timedelta(days=5)
        wait_label = "5 giorni"
    else:
        print(f"[NEXUS WORKER] Unknown recurring_interval_days: {recurring_interval_days}")
        return

    next_run = base_time + interval
    if next_run <= datetime.now():
        next_run = datetime.now() + timedelta(minutes=1)

    conn = get_connection()
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (account_id,))
        cur.execute("""
            SELECT id FROM big_bang_jobs 
            WHERE account_id = %s AND status IN ('WAITING', 'RUNNING', 'SCHEDULED', 'EXECUTING')
            LIMIT 1
        """, (account_id,))
        existing = cur.fetchone()

        if existing:
            conn.rollback()
            print(f"[NEXUS WORKER] Skipping schedule: account {account_id} already has active job {existing[0]}")
            return

        phase_msg = f"Prossima esecuzione: {next_run.strftime('%d/%m/%Y %H:%M')}"
        cur.execute("""
            INSERT INTO big_bang_jobs (account_id, delay_hours, ad_product, recurring_mode, recurring_interval_days,
                                      status, current_phase, phase_status, phase_message, next_run_at, created_at)
            VALUES (%s, %s, %s, %s, %s, 'WAITING', 0, 'waiting', %s, %s, NOW())
            RETURNING id
        """, (account_id, delay_minutes, ad_product, recurring_mode, recurring_interval_days, phase_msg, next_run))
        new_id = cur.fetchone()[0]
        conn.commit()
        print(f"[NEXUS WORKER] Scheduling next job in {wait_label} for account {account_id}")
        print(f"[NEXUS WORKER] Created waiting job {new_id} for {next_run}")
    except Exception as e:
        conn.rollback()
        print(f"[NEXUS WORKER] Error scheduling recurring job for account {account_id}: {e}")
    finally:
        conn.close()


def execute_step_6(account_id: int, max_retries: int = 3) -> dict:
    """Execute step 6 (bid updates) in-process with retry logic.
    
    Calls execute_all_bids directly without HTTP, eliminating timeout issues.
    Retries on transient errors (SSL, connection reset).
    """
    from backend.app.services.bid_executor import execute_all_bids
    
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[NEXUS WORKER] Step 6 attempt {attempt}/{max_retries} for account {account_id} (in-process)")
            result = execute_all_bids(account_id)
            
            if result.get('status') == 'error':
                raise Exception(result.get('message', 'Errore sconosciuto'))
            
            return result
            
        except Exception as e:
            last_error = str(e)
            is_transient = any(kw in last_error.lower() for kw in ['ssl', 'connection', 'timeout', 'reset', 'refused', 'unexpectedly'])
            
            if is_transient and attempt < max_retries:
                wait_time = 30 * attempt
                print(f"[NEXUS WORKER] Step 6 transient error, retrying in {wait_time}s: {last_error[:200]}")
                time.sleep(wait_time)
            elif attempt < max_retries and 'token' not in last_error.lower():
                wait_time = 30 * attempt
                print(f"[NEXUS WORKER] Step 6 error, retrying in {wait_time}s: {last_error[:200]}")
                time.sleep(wait_time)
            else:
                raise Exception(f"Step 6 fallito dopo {max_retries} tentativi: {last_error[:300]}")
    
    raise Exception(f"Step 6 fallito dopo {max_retries} tentativi: {last_error}")


if __name__ == "__main__":
    run_worker()
