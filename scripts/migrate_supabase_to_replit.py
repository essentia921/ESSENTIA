#!/usr/bin/env python3
"""
Migration script: Copy all data from Supabase to Replit PostgreSQL
"""
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor, Json

SUPABASE_URL = os.environ.get("SUPABASE_DATABASE_URL")
REPLIT_URL = os.environ.get("DATABASE_URL")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_DATABASE_URL not set")
if not REPLIT_URL:
    raise RuntimeError("DATABASE_URL not set")

TABLES_TO_MIGRATE = [
    "users",
    "subscriptions", 
    "admin_users",
    "client_accounts",
    "client_tokens",
    "client_profiles",
    "launched_campaigns",
    "amazon_reports",
    "autopilot_runs",
    "onboarding_tokens",
    "planned_bid_actions",
    "books",
    "autopilot_settings",
    "autopilot_profiles",
    "profile_books",
    "book_economics_cache",
    "ads_agg_book_metrics",
    "ads_report_runs",
    "autopilot_sync_jobs",
    "planned_actions",
]


def get_table_columns(conn, table_name):
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s AND table_schema = 'public'
        ORDER BY ordinal_position
    """, (table_name,))
    columns = [row[0] for row in cur.fetchall()]
    cur.close()
    return columns


def migrate_table(src_url, dst_url, table_name):
    try:
        src_conn = psycopg2.connect(src_url)
        src_cur = src_conn.cursor(cursor_factory=RealDictCursor)
        src_cur.execute(f"SELECT * FROM {table_name}")
        rows = src_cur.fetchall()
        src_cur.close()
        src_conn.close()
        
        if not rows:
            print(f"  {table_name}: 0 rows (empty in source)")
            return 0
        
        dst_conn = psycopg2.connect(dst_url)
        dst_columns = get_table_columns(dst_conn, table_name)
        if not dst_columns:
            print(f"  {table_name}: SKIPPED (table doesn't exist in destination)")
            dst_conn.close()
            return 0
        
        common_columns = [col for col in rows[0].keys() if col in dst_columns]
        
        if not common_columns:
            print(f"  {table_name}: SKIPPED (no common columns)")
            dst_conn.close()
            return 0
        
        dst_cur = dst_conn.cursor()
        
        dst_cur.execute(f"DELETE FROM {table_name}")
        
        placeholders = ', '.join(['%s'] * len(common_columns))
        columns_str = ', '.join(common_columns)
        insert_sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
        
        inserted = 0
        for row in rows:
            values = []
            for col in common_columns:
                val = row.get(col)
                if isinstance(val, (dict, list)):
                    val = Json(val)
                values.append(val)
            try:
                dst_cur.execute(insert_sql, values)
                inserted += 1
            except Exception as e:
                print(f"    Error inserting row in {table_name}: {e}")
                dst_conn.rollback()
        
        dst_conn.commit()
        dst_cur.close()
        dst_conn.close()
        
        print(f"  {table_name}: {inserted} rows migrated")
        return inserted
        
    except Exception as e:
        print(f"  {table_name}: SKIPPED - {e}")
        return 0


def reset_sequences(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name, column_name 
        FROM information_schema.columns 
        WHERE column_default LIKE 'nextval%' AND table_schema = 'public'
    """)
    sequences = cur.fetchall()
    
    for table_name, column_name in sequences:
        try:
            cur.execute(f"""
                SELECT setval(
                    pg_get_serial_sequence('{table_name}', '{column_name}'),
                    COALESCE((SELECT MAX({column_name}) FROM {table_name}), 1)
                )
            """)
        except Exception as e:
            print(f"  Warning: Could not reset sequence for {table_name}.{column_name}: {e}")
    
    conn.commit()
    cur.close()


def main():
    print("=" * 60)
    print("MIGRAZIONE SUPABASE → REPLIT")
    print("=" * 60)
    
    print("\nTesting connections...")
    try:
        src_conn = psycopg2.connect(SUPABASE_URL)
        src_conn.close()
        print("  Supabase: OK")
    except Exception as e:
        print(f"  Supabase: FAILED - {e}")
        return
    
    try:
        dst_conn = psycopg2.connect(REPLIT_URL)
        dst_conn.close()
        print("  Replit: OK")
    except Exception as e:
        print(f"  Replit: FAILED - {e}")
        return
    
    print("\nMigrating tables:")
    total_rows = 0
    for table in TABLES_TO_MIGRATE:
        rows = migrate_table(SUPABASE_URL, REPLIT_URL, table)
        total_rows += rows
    
    print("\nResetting sequences...")
    dst_conn = psycopg2.connect(REPLIT_URL)
    reset_sequences(dst_conn)
    dst_conn.close()
    
    print("\n" + "=" * 60)
    print(f"MIGRAZIONE COMPLETATA: {total_rows} righe totali migrate")
    print("=" * 60)


if __name__ == "__main__":
    main()
