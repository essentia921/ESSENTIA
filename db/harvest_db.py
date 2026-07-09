"""
Harvest DB - persistenza per il search-term harvesting (SP + SB).

Tabelle:
  - harvest_jobs    : un record per run (account + profile), stato/fasi/conteggi/routing
  - harvest_actions : una riga per micro-azione pianificata, con esito post-esecuzione

Segue lo stesso pattern di autopilot_sync_jobs (raw SQL + psycopg2 + RealDictCursor).
"""

import json
from db.accounts_db import get_connection
from psycopg2.extras import RealDictCursor


def init_harvest_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS harvest_jobs (
            id SERIAL PRIMARY KEY,
            account_id INTEGER NOT NULL,
            profile_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'STARTING',
            phase TEXT,
            message TEXT,
            days INTEGER NOT NULL DEFAULT 60,
            min_purchases INTEGER NOT NULL DEFAULT 1,
            dry_run BOOLEAN NOT NULL DEFAULT FALSE,
            qualifying_terms INTEGER DEFAULT 0,
            planned_actions INTEGER DEFAULT 0,
            executed_ok INTEGER DEFAULT 0,
            executed_err INTEGER DEFAULT 0,
            sp_dest JSONB,
            sb_dest JSONB,
            error TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS harvest_actions (
            id SERIAL PRIMARY KEY,
            job_id INTEGER NOT NULL REFERENCES harvest_jobs(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            product TEXT NOT NULL,
            campaign_id TEXT,
            ad_group_id TEXT,
            term TEXT,
            value TEXT,
            match_type TEXT,
            bid NUMERIC,
            note TEXT,
            status TEXT NOT NULL DEFAULT 'PLANNED',
            response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # heartbeat per il recupero dei job appesi dopo un riavvio del worker
    cur.execute("ALTER TABLE harvest_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_harvest_jobs_account ON harvest_jobs(account_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_harvest_jobs_status ON harvest_jobs(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_harvest_actions_job ON harvest_actions(job_id)")

    conn.commit()
    cur.close()
    conn.close()


def create_harvest_job(account_id: int, profile_id: str, days: int,
                       min_purchases: int, dry_run: bool) -> int:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        INSERT INTO harvest_jobs (account_id, profile_id, days, min_purchases, dry_run,
                                  status, phase, message, started_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, 'QUEUED', 'QUEUED', 'In coda, in attesa del worker...',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        RETURNING id
    """, (account_id, profile_id, days, min_purchases, dry_run))
    job = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return job['id']


def update_harvest_job(job_id: int, **kwargs):
    if not kwargs:
        return
    conn = get_connection()
    cur = conn.cursor()
    sets, values = [], []
    for key, value in kwargs.items():
        if key in ("sp_dest", "sb_dest") and value is not None:
            value = json.dumps(value)
        sets.append(f"{key} = %s")
        values.append(value)
    sets.append("updated_at = CURRENT_TIMESTAMP")  # heartbeat automatico
    values.append(job_id)
    cur.execute(f"UPDATE harvest_jobs SET {', '.join(sets)} WHERE id = %s", values)
    conn.commit()
    cur.close()
    conn.close()


def claim_next_harvest_job() -> dict:
    """Preso atomicamente il prossimo job QUEUED la cui coppia (account, profile)
    non ha gia' un job RUNNING. Lo transita a RUNNING. Ritorna il job o None.

    FOR UPDATE SKIP LOCKED rende sicura la presa in carico anche con piu' worker.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        UPDATE harvest_jobs
        SET status = 'RUNNING', phase = 'CLAIMED',
            message = 'Preso in carico dal worker...', updated_at = CURRENT_TIMESTAMP
        WHERE id = (
            SELECT q.id FROM harvest_jobs q
            WHERE q.status = 'QUEUED'
              AND NOT EXISTS (
                  SELECT 1 FROM harvest_jobs r
                  WHERE r.status = 'RUNNING'
                    AND r.account_id = q.account_id
                    AND r.profile_id = q.profile_id
              )
            ORDER BY q.started_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING *
    """)
    job = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return dict(job) if job else None


def fail_stale_harvest_jobs(stale_minutes: int = 10) -> int:
    """Job RUNNING senza heartbeat da troppo tempo = worker morto/riavviato.
    Vengono marcati FAILED (rilanciabili: il nuovo run deduplica cio' gia' creato)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE harvest_jobs
        SET status = 'FAILED', phase = 'STALE',
            message = 'Job interrotto (worker riavviato o bloccato) - rilancia',
            error = 'stale: nessun heartbeat', finished_at = CURRENT_TIMESTAMP
        WHERE status = 'RUNNING'
          AND updated_at < NOW() - (%s || ' minutes')::interval
    """, (str(stale_minutes),))
    n = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return n


def insert_harvest_actions(job_id: int, actions: list) -> None:
    """Inserisce le azioni pianificate e scrive l'id DB dentro ogni dict (action['db_id'])."""
    if not actions:
        return
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    for a in actions:
        cur.execute("""
            INSERT INTO harvest_actions
                (job_id, kind, product, campaign_id, ad_group_id, term, value,
                 match_type, bid, note, status, response)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (job_id, a["kind"], a["product"], a["campaignId"], a["adGroupId"],
              a["term"], a["value"], a["matchType"], a["bid"], a["note"],
              a["status"], a["response"]))
        a["db_id"] = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()


def update_action_result(action_db_id: int, status: str, response: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE harvest_actions SET status = %s, response = %s WHERE id = %s",
                (status, response[:1000] if response else response, action_db_id))
    conn.commit()
    cur.close()
    conn.close()


def get_harvest_job(job_id: int) -> dict:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM harvest_jobs WHERE id = %s", (job_id,))
    job = cur.fetchone()
    cur.close()
    conn.close()
    return dict(job) if job else None


def get_harvest_actions(job_id: int) -> list:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM harvest_actions WHERE job_id = %s ORDER BY id", (job_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def list_harvest_jobs(account_id: int, limit: int = 50) -> list:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT * FROM harvest_jobs WHERE account_id = %s
        ORDER BY started_at DESC LIMIT %s
    """, (account_id, limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]
