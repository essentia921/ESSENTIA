import os
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("Database non configurato. Imposta DATABASE_URL.")


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_accounts_db():
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS client_accounts (
            id SERIAL PRIMARY KEY,
            client_name VARCHAR(255) NOT NULL,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        ALTER TABLE client_accounts ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS client_tokens (
            id SERIAL PRIMARY KEY,
            client_account_id INTEGER REFERENCES client_accounts(id) ON DELETE CASCADE,
            access_token TEXT,
            refresh_token TEXT,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(client_account_id)
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS client_profiles (
            id SERIAL PRIMARY KEY,
            client_account_id INTEGER REFERENCES client_accounts(id) ON DELETE CASCADE,
            profile_id VARCHAR(100) NOT NULL,
            country_code VARCHAR(10),
            currency_code VARCHAR(10),
            marketplace_string VARCHAR(50),
            region VARCHAR(10),
            api_url VARCHAR(255),
            profile_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(client_account_id, profile_id)
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS launched_campaigns (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            account_id INTEGER,
            profile_id VARCHAR(255),
            marketplace VARCHAR(50),
            campaign_type VARCHAR(50),
            campaign_id VARCHAR(255),
            ad_group_id VARCHAR(255),
            asin VARCHAR(50),
            campaign_name VARCHAR(500),
            daily_budget DECIMAL(10,2),
            default_bid DECIMAL(10,2),
            status VARCHAR(50) DEFAULT 'pending',
            request_payload JSONB,
            response_payload JSONB,
            error_message TEXT,
            launched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS amazon_reports (
            id SERIAL PRIMARY KEY,
            account_id INTEGER REFERENCES client_accounts(id) ON DELETE CASCADE,
            profile_id VARCHAR(255) NOT NULL,
            report_id VARCHAR(255) UNIQUE NOT NULL,
            report_type VARCHAR(50) NOT NULL,
            ad_product VARCHAR(20) DEFAULT 'SP',
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            status VARCHAR(50) DEFAULT 'PENDING',
            download_url TEXT,
            file_path TEXT,
            failure_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            autopilot_run_id INTEGER,
            report_data JSONB
        )
    """)
    
    cur.execute("""
        ALTER TABLE amazon_reports 
        ADD COLUMN IF NOT EXISTS ad_product VARCHAR(20) DEFAULT 'SP'
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS autopilot_runs (
            id SERIAL PRIMARY KEY,
            profile_id VARCHAR(255) NOT NULL,
            account_id INTEGER,
            status VARCHAR(50) DEFAULT 'PENDING',
            mode VARCHAR(20) DEFAULT 'normal',
            report_14d_id VARCHAR(255),
            report_30d_id VARCHAR(255),
            discovery_report_id VARCHAR(255),
            actions_count INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reports_requested_at TIMESTAMP,
            reports_completed_at TIMESTAMP,
            analysis_completed_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_tokens (
            id SERIAL PRIMARY KEY,
            token VARCHAR(255) UNIQUE NOT NULL,
            user_id INTEGER,
            client_name VARCHAR(255),
            client_account_id INTEGER REFERENCES client_accounts(id) ON DELETE SET NULL,
            expires_at TIMESTAMP,
            used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS planned_bid_actions (
            id SERIAL PRIMARY KEY,
            profile_id VARCHAR(255) NOT NULL,
            account_id INTEGER,
            campaign_id VARCHAR(255),
            campaign_name VARCHAR(500),
            ad_group_id VARCHAR(255),
            keyword_id VARCHAR(255),
            asin VARCHAR(50),
            target_keyword TEXT,
            current_bid DECIMAL(10,4),
            delta_bid DECIMAL(10,4),
            tipo_azione VARCHAR(50),
            report_14d_id VARCHAR(255),
            report_30d_id VARCHAR(255),
            target_type VARCHAR(20) DEFAULT 'keyword',
            acos_14d DECIMAL(10,4),
            acos_30d DECIMAL(10,4),
            acos_be DECIMAL(10,4),
            status VARCHAR(20) DEFAULT 'PLANNED',
            autopilot_run_id INTEGER,
            executed BOOLEAN DEFAULT FALSE,
            executed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255),
            google_id VARCHAR(255) UNIQUE,
            picture TEXT,
            role VARCHAR(50) DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            stripe_customer_id VARCHAR(255),
            stripe_subscription_id VARCHAR(255),
            plan VARCHAR(50) DEFAULT 'free',
            status VARCHAR(50) DEFAULT 'inactive',
            current_period_end TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id)
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            asin VARCHAR(50) NOT NULL,
            marketplace VARCHAR(10) NOT NULL,
            title VARCHAR(500),
            author VARCHAR(255),
            price DECIMAL(10,2),
            print_cost DECIMAL(10,2),
            royalty_rate DECIMAL(5,2),
            pages INTEGER,
            format VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, asin, marketplace)
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS autopilot_settings (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            profile_id VARCHAR(255),
            enabled BOOLEAN DEFAULT FALSE,
            target_acos DECIMAL(5,2),
            min_bid DECIMAL(10,2),
            max_bid DECIMAL(10,2),
            bid_step DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, profile_id)
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS big_bang_jobs (
            id SERIAL PRIMARY KEY,
            account_id INTEGER REFERENCES client_accounts(id) ON DELETE CASCADE,
            delay_hours INTEGER NOT NULL DEFAULT 1,
            status VARCHAR(50) DEFAULT 'RUNNING',
            current_phase INTEGER DEFAULT 1,
            phase_status VARCHAR(50) DEFAULT 'pending',
            phase_message TEXT,
            execute_at TIMESTAMP,
            executed_at TIMESTAMP,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS amazon_oauth_states (
            state VARCHAR(255) PRIMARY KEY,
            account_id INTEGER,
            region VARCHAR(10) DEFAULT 'eu',
            flow_type VARCHAR(50) DEFAULT 'direct',
            onboarding_token VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS amazon_pending_oauth (
            redirect_token VARCHAR(255) PRIMARY KEY,
            account_id INTEGER,
            region VARCHAR(10) DEFAULT 'eu',
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


def create_oauth_pending(token, account_id, region, user_id):
    """Store a one-time redirect token for Amazon OAuth init in the DB."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM amazon_oauth_pending
        WHERE created_at < NOW() - INTERVAL '15 minutes'
    """)
    cur.execute("""
        INSERT INTO amazon_oauth_pending (token, account_id, region, user_id)
        VALUES (%s, %s, %s, %s)
    """, (token, account_id, region, user_id))
    conn.commit()
    cur.close()
    conn.close()


def get_and_delete_oauth_pending(token):
    """Retrieve and atomically delete a pending OAuth token. Returns None if not found or expired."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        DELETE FROM amazon_oauth_pending
        WHERE token = %s AND created_at > NOW() - INTERVAL '10 minutes'
        RETURNING *
    """, (token,))
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return dict(result) if result else None


def create_oauth_state(state, account_id, region, flow_type='direct', onboarding_token=None):
    """Store an OAuth state parameter in the DB."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM amazon_oauth_states
        WHERE created_at < NOW() - INTERVAL '15 minutes'
    """)
    cur.execute("""
        INSERT INTO amazon_oauth_states (state, account_id, region, flow_type, onboarding_token)
        VALUES (%s, %s, %s, %s, %s)
    """, (state, account_id, region, flow_type, onboarding_token))
    conn.commit()
    cur.close()
    conn.close()


def get_and_delete_oauth_state(state):
    """Retrieve and atomically delete an OAuth state. Returns None if not found or expired."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        DELETE FROM amazon_oauth_states
        WHERE state = %s AND created_at > NOW() - INTERVAL '10 minutes'
        RETURNING *
    """, (state,))
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return dict(result) if result else None


def create_default_admin(username="admin", password="admin123"):
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT id FROM admin_users WHERE username = %s", (username,))
    if cur.fetchone() is None:
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur.execute(
            "INSERT INTO admin_users (username, password_hash) VALUES (%s, %s)",
            (username, password_hash)
        )
        conn.commit()
    
    cur.close()
    conn.close()


def verify_admin(username, password):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM admin_users WHERE username = %s", (username,))
    user = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        return user
    return None


def change_admin_password(username, new_password):
    conn = get_connection()
    cur = conn.cursor()
    
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cur.execute(
        "UPDATE admin_users SET password_hash = %s WHERE username = %s",
        (password_hash, username)
    )
    
    conn.commit()
    cur.close()
    conn.close()


def create_client_account(client_name, user_id=None):
    """Create a client account associated with a user."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute(
        "INSERT INTO client_accounts (client_name, user_id) VALUES (%s, %s) RETURNING *",
        (client_name, user_id)
    )
    account = cur.fetchone()
    
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(account)


def get_all_client_accounts(user_id=None):
    """Get all client accounts, optionally filtered by user_id."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if user_id:
        cur.execute("""
            SELECT ca.*, 
                   ct.access_token IS NOT NULL as has_tokens,
                   (SELECT COUNT(*) FROM client_profiles cp WHERE cp.client_account_id = ca.id) as profile_count
            FROM client_accounts ca
            LEFT JOIN client_tokens ct ON ca.id = ct.client_account_id
            WHERE ca.user_id = %s
            ORDER BY ca.client_name
        """, (user_id,))
    else:
        cur.execute("""
            SELECT ca.*, 
                   ct.access_token IS NOT NULL as has_tokens,
                   (SELECT COUNT(*) FROM client_profiles cp WHERE cp.client_account_id = ca.id) as profile_count
            FROM client_accounts ca
            LEFT JOIN client_tokens ct ON ca.id = ct.client_account_id
            ORDER BY ca.client_name
        """)
    accounts = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return [dict(a) for a in accounts]


def get_client_account(account_id, user_id=None):
    """Get a client account by ID, optionally filtered by user_id for ownership."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if user_id:
        cur.execute("SELECT * FROM client_accounts WHERE id = %s AND user_id = %s", (account_id, user_id))
    else:
        cur.execute("SELECT * FROM client_accounts WHERE id = %s", (account_id,))
    account = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return dict(account) if account else None


def delete_client_account(account_id, user_id=None):
    """Delete a client account. If user_id provided, only delete if owned by user."""
    conn = get_connection()
    cur = conn.cursor()
    
    if user_id:
        cur.execute("DELETE FROM client_accounts WHERE id = %s AND user_id = %s RETURNING id", (account_id, user_id))
    else:
        cur.execute("DELETE FROM client_accounts WHERE id = %s RETURNING id", (account_id,))
    
    deleted = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return deleted is not None


def rename_client_account(account_id, new_name, user_id=None):
    """Rename a client account. If user_id provided, only rename if owned by user."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if user_id:
        cur.execute(
            "UPDATE client_accounts SET client_name = %s, updated_at = %s WHERE id = %s AND user_id = %s RETURNING *",
            (new_name, datetime.now(), account_id, user_id)
        )
    else:
        cur.execute(
            "UPDATE client_accounts SET client_name = %s, updated_at = %s WHERE id = %s RETURNING *",
            (new_name, datetime.now(), account_id)
        )
    account = cur.fetchone()
    
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(account) if account else None


def save_client_tokens(client_account_id, access_token, refresh_token, expires_at=None):
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO client_tokens (client_account_id, access_token, refresh_token, expires_at, updated_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (client_account_id) 
        DO UPDATE SET 
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at,
            updated_at = EXCLUDED.updated_at
    """, (client_account_id, access_token, refresh_token, expires_at, datetime.now()))
    
    conn.commit()
    cur.close()
    conn.close()


def get_client_tokens(client_account_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM client_tokens WHERE client_account_id = %s", (client_account_id,))
    tokens = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return dict(tokens) if tokens else None


def save_client_profiles(client_account_id, profiles):
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("DELETE FROM client_profiles WHERE client_account_id = %s", (client_account_id,))
    
    for p in profiles:
        cur.execute("""
            INSERT INTO client_profiles 
            (client_account_id, profile_id, country_code, currency_code, marketplace_string, region, api_url, profile_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            client_account_id,
            str(p.get("profileId")),
            p.get("countryCode"),
            p.get("currencyCode"),
            p.get("marketplaceString"),
            p.get("_region"),
            p.get("_api_url"),
            psycopg2.extras.Json(p)
        ))
    
    conn.commit()
    cur.close()
    conn.close()


def get_client_profiles(client_account_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM client_profiles 
        WHERE client_account_id = %s 
        ORDER BY country_code
    """, (client_account_id,))
    profiles = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return [dict(p) for p in profiles]


def get_profile_info(client_account_id, profile_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT api_url, region, country_code FROM client_profiles 
        WHERE client_account_id = %s AND profile_id = %s
    """, (client_account_id, str(profile_id)))
    profile = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if profile:
        return dict(profile)
    return None


def get_account_for_profile(profile_id):
    """Get account_id and profile info from just profile_id."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT client_account_id, api_url, region, country_code 
        FROM client_profiles 
        WHERE profile_id = %s
    """, (str(profile_id),))
    result = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if result:
        return dict(result)
    return None


def create_onboarding_token(token, user_id, client_name, expires_at):
    """Create a new onboarding token for client self-service linking."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO onboarding_tokens (token, user_id, client_name, expires_at)
        VALUES (%s, %s, %s, %s)
    """, (token, user_id, client_name, expires_at))
    
    conn.commit()
    cur.close()
    conn.close()


def get_onboarding_token(token):
    """Get onboarding token details."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM onboarding_tokens WHERE token = %s
    """, (token,))
    result = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def mark_onboarding_used(token, client_account_id):
    """Mark an onboarding token as used."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE onboarding_tokens 
        SET used_at = %s, client_account_id = %s 
        WHERE token = %s
    """, (datetime.now(), client_account_id, token))
    
    conn.commit()
    cur.close()
    conn.close()


def get_user_onboarding_tokens(user_id):
    """Get all onboarding tokens created by a user."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM onboarding_tokens 
        WHERE user_id = %s 
        ORDER BY created_at DESC
    """, (user_id,))
    results = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def save_launched_campaign(
    user_id,
    account_id,
    profile_id,
    marketplace,
    campaign_type,
    campaign_id,
    ad_group_id,
    asin,
    campaign_name,
    daily_budget,
    default_bid,
    status,
    request_payload,
    response_payload,
    error_message=None
):
    """Save a launched campaign record."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        INSERT INTO launched_campaigns 
        (user_id, account_id, profile_id, marketplace, campaign_type, campaign_id, 
         ad_group_id, asin, campaign_name, daily_budget, default_bid, status,
         request_payload, response_payload, error_message, launched_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """, (
        user_id, account_id, profile_id, marketplace, campaign_type, campaign_id,
        ad_group_id, asin, campaign_name, daily_budget, default_bid, status,
        psycopg2.extras.Json(request_payload), psycopg2.extras.Json(response_payload),
        error_message, datetime.now()
    ))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_user_launched_campaigns(user_id, limit=50):
    """Get launched campaigns for a user."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT lc.*, ca.client_name as account_name
        FROM launched_campaigns lc
        LEFT JOIN client_accounts ca ON lc.account_id = ca.id
        WHERE lc.user_id = %s
        ORDER BY lc.launched_at DESC
        LIMIT %s
    """, (user_id, limit))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


ALLOWED_COUNTRY_CODES = ('US', 'CA', 'MX', 'BR', 'UK', 'GB', 'DE', 'FR', 'IT', 'ES', 'NL', 'SE', 'PL', 'BE', 'AE', 'SA', 'EG', 'TR', 'IN', 'JP', 'AU', 'SG')

def get_profiles_for_account(account_id):
    """Get all profiles for a specific account with account info. Filtered to supported marketplaces."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT cp.*, ca.client_name as account_name
        FROM client_profiles cp
        JOIN client_accounts ca ON cp.client_account_id = ca.id
        WHERE cp.client_account_id = %s
          AND cp.country_code IN ('US', 'CA', 'MX', 'BR', 'UK', 'GB', 'DE', 'FR', 'IT', 'ES', 'NL', 'SE', 'PL', 'BE', 'AE', 'SA', 'EG', 'TR', 'IN', 'JP', 'AU', 'SG')
        ORDER BY cp.country_code
    """, (account_id,))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def get_all_user_profiles(user_id=None):
    """Get all profiles across all accounts, optionally filtered by user_id."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if user_id:
        cur.execute("""
            SELECT cp.*, ca.client_name as account_name, ca.id as account_id
            FROM client_profiles cp
            JOIN client_accounts ca ON cp.client_account_id = ca.id
            WHERE ca.user_id = %s
            ORDER BY ca.client_name, cp.country_code
        """, (user_id,))
    else:
        cur.execute("""
            SELECT cp.*, ca.client_name as account_name, ca.id as account_id
            FROM client_profiles cp
            JOIN client_accounts ca ON cp.client_account_id = ca.id
            ORDER BY ca.client_name, cp.country_code
        """)
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def verify_account_ownership(user_id, account_id):
    """Verify that account exists and belongs to the specified user."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT id FROM client_accounts 
        WHERE id = %s AND user_id = %s
    """, (account_id, user_id))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    return result is not None


def create_report(account_id, profile_id, report_id, report_type, start_date, end_date, ad_product='SP'):
    """Create a new report record."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        INSERT INTO amazon_reports 
        (account_id, profile_id, report_id, report_type, ad_product, start_date, end_date, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDING')
        RETURNING *
    """, (account_id, profile_id, report_id, report_type, ad_product, start_date, end_date))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_reports_for_profile(profile_id):
    """Get all reports for a specific profile."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM amazon_reports 
        WHERE profile_id = %s
        ORDER BY created_at DESC
    """, (profile_id,))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def get_all_reports():
    """Get all reports."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM amazon_reports 
        ORDER BY created_at DESC
    """)
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def delete_all_reports():
    """Delete all reports from database."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("DELETE FROM amazon_reports")
    deleted_count = cur.rowcount
    
    conn.commit()
    cur.close()
    conn.close()
    
    return deleted_count


def delete_reports_by_ids(report_ids):
    """Delete specific reports by their IDs."""
    if not report_ids:
        return 0
    
    conn = get_connection()
    cur = conn.cursor()
    
    placeholders = ','.join(['%s'] * len(report_ids))
    cur.execute(f"DELETE FROM amazon_reports WHERE id IN ({placeholders})", tuple(report_ids))
    deleted_count = cur.rowcount
    
    conn.commit()
    cur.close()
    conn.close()
    
    return deleted_count


def delete_reports_for_account(account_id):
    """Delete all reports for a specific account."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("DELETE FROM amazon_reports WHERE account_id = %s", (account_id,))
    deleted_count = cur.rowcount
    
    conn.commit()
    cur.close()
    conn.close()
    
    return deleted_count


def get_pending_reports():
    """Get all reports with PENDING status."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT ar.*, ca.client_name as account_name
        FROM amazon_reports ar
        JOIN client_accounts ca ON ar.account_id = ca.id
        WHERE ar.status = 'PENDING'
        ORDER BY ar.created_at ASC
    """)
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def get_recent_reports_status(account_id: int, minutes: int = 30) -> dict:
    """Get status summary of reports created in last N minutes for an account.
    
    Returns:
        {
            'total': int,
            'pending': int,
            'parsed': int,
            'failed': int,
            'all_parsed': bool
        }
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT status, COUNT(*) as count
        FROM amazon_reports 
        WHERE account_id = %s 
          AND created_at >= NOW() - (%s || ' minutes')::interval
        GROUP BY status
    """, (account_id, str(minutes)))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    status_counts = {r['status']: r['count'] for r in results}
    total = sum(status_counts.values())
    pending = status_counts.get('PENDING', 0) + status_counts.get('PROCESSING', 0)
    # Consider COMPLETED and PARSED as both valid "parsed/ready" states
    parsed = status_counts.get('PARSED', 0) + status_counts.get('COMPLETED', 0)
    failed = status_counts.get('FAILED', 0)
    
    return {
        'total': total,
        'pending': pending,
        'parsed': parsed,
        'failed': failed,
        'all_parsed': total > 0 and pending == 0 and total == parsed + failed
    }


def update_report_status(report_id, status, download_url=None, file_path=None, failure_reason=None, report_data=None):
    """Update report status."""
    import json
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if status == 'COMPLETED':
        report_data_json = json.dumps(report_data) if report_data else None
        cur.execute("""
            UPDATE amazon_reports 
            SET status = %s, download_url = %s, file_path = %s, report_data = %s, completed_at = CURRENT_TIMESTAMP
            WHERE report_id = %s
            RETURNING *
        """, (status, download_url, file_path, report_data_json, report_id))
    elif status == 'FAILED':
        cur.execute("""
            UPDATE amazon_reports 
            SET status = %s, failure_reason = %s
            WHERE report_id = %s
            RETURNING *
        """, (status, failure_reason, report_id))
    else:
        cur.execute("""
            UPDATE amazon_reports 
            SET status = %s
            WHERE report_id = %s
            RETURNING *
        """, (status, report_id))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def update_client_tokens(account_id, access_token, refresh_token, expires_at):
    """Update client tokens after refresh."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        UPDATE client_tokens 
        SET access_token = %s, refresh_token = %s, expires_at = %s, updated_at = CURRENT_TIMESTAMP
        WHERE client_account_id = %s
        RETURNING *
    """, (access_token, refresh_token, expires_at, account_id))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_report_by_id(report_id):
    """Get a report by its Amazon report_id."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM amazon_reports WHERE report_id = %s
    """, (report_id,))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def ensure_target_type_column():
    """Add target_type, ACOS, status and autopilot columns to planned_bid_actions if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            ALTER TABLE planned_bid_actions 
            ADD COLUMN IF NOT EXISTS target_type VARCHAR(20) DEFAULT 'keyword'
        """)
        cur.execute("""
            ALTER TABLE planned_bid_actions 
            ADD COLUMN IF NOT EXISTS acos_14d DECIMAL(10,4)
        """)
        cur.execute("""
            ALTER TABLE planned_bid_actions 
            ADD COLUMN IF NOT EXISTS acos_30d DECIMAL(10,4)
        """)
        cur.execute("""
            ALTER TABLE planned_bid_actions 
            ADD COLUMN IF NOT EXISTS acos_be DECIMAL(10,4)
        """)
        cur.execute("""
            ALTER TABLE planned_bid_actions 
            ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'PLANNED'
        """)
        cur.execute("""
            ALTER TABLE planned_bid_actions 
            ADD COLUMN IF NOT EXISTS autopilot_run_id INTEGER
        """)
        cur.execute("""
            ALTER TABLE planned_bid_actions 
            ADD COLUMN IF NOT EXISTS executed_at TIMESTAMP
        """)
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def save_planned_bid_action(
    profile_id: str,
    account_id: int,
    campaign_id: str,
    campaign_name: str,
    ad_group_id: str,
    keyword_id: str,
    asin: str,
    target_keyword: str,
    current_bid,
    delta_bid: float,
    tipo_azione: str,
    report_14d_id: str = None,
    report_30d_id: str = None,
    target_type: str = "keyword",
    acos_14d: float = None,
    acos_30d: float = None
):
    """Save a planned bid action."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        INSERT INTO planned_bid_actions 
        (profile_id, account_id, campaign_id, campaign_name, ad_group_id, keyword_id, asin, target_keyword, current_bid, delta_bid, tipo_azione, report_14d_id, report_30d_id, target_type, acos_14d, acos_30d)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """, (profile_id, account_id, campaign_id, campaign_name, ad_group_id, keyword_id, asin, target_keyword, current_bid, delta_bid, tipo_azione, report_14d_id, report_30d_id, target_type, acos_14d, acos_30d))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_planned_actions(profile_id: str = None, executed: bool = None):
    """Get planned bid actions, optionally filtered by profile_id and executed status."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    query = "SELECT * FROM planned_bid_actions WHERE 1=1"
    params = []
    
    if profile_id:
        query += " AND profile_id = %s"
        params.append(profile_id)
    
    if executed is not None:
        query += " AND executed = %s"
        params.append(executed)
    
    query += " ORDER BY created_at DESC"
    
    cur.execute(query, params)
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def clear_planned_actions(profile_id: str = None):
    """Clear planned actions (optionally for a specific profile)."""
    conn = get_connection()
    cur = conn.cursor()
    
    if profile_id:
        cur.execute("DELETE FROM planned_bid_actions WHERE profile_id = %s AND executed = FALSE", (profile_id,))
    else:
        cur.execute("DELETE FROM planned_bid_actions WHERE executed = FALSE")
    
    conn.commit()
    cur.close()
    conn.close()


def mark_actions_executed(action_ids: list):
    """Mark planned bid actions as executed."""
    if not action_ids:
        return 0
    
    conn = get_connection()
    cur = conn.cursor()
    
    placeholders = ','.join(['%s'] * len(action_ids))
    cur.execute(f"UPDATE planned_bid_actions SET executed = TRUE WHERE id IN ({placeholders})", action_ids)
    
    updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    
    return updated


def get_planned_actions_by_ids(action_ids: list):
    """Get planned actions by their IDs."""
    if not action_ids:
        return []
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    placeholders = ','.join(['%s'] * len(action_ids))
    cur.execute(f"SELECT * FROM planned_bid_actions WHERE id IN ({placeholders})", action_ids)
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def delete_planned_actions_by_ids(action_ids: list):
    """Delete planned actions by their IDs."""
    if not action_ids:
        return 0
    
    conn = get_connection()
    cur = conn.cursor()
    
    placeholders = ','.join(['%s'] * len(action_ids))
    cur.execute(f"DELETE FROM planned_bid_actions WHERE id IN ({placeholders}) AND executed = FALSE", action_ids)
    
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    
    return deleted


def get_completed_reports_for_analysis(profile_id: str):
    """Get completed 14D and 30D reports for a profile."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM amazon_reports 
        WHERE profile_id = %s AND status = 'COMPLETED' AND report_data IS NOT NULL
        ORDER BY created_at DESC
    """, (profile_id,))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    report_14d = None
    report_30d = None
    
    for r in results:
        report_type = r.get("report_type", "")
        if "14D" in report_type and not report_14d:
            report_14d = dict(r)
        elif "30D" in report_type and not report_30d:
            report_30d = dict(r)
        
        if report_14d and report_30d:
            break
    
    return report_14d, report_30d


def get_latest_discovery_report(profile_id: str):
    """Get latest completed discovery report for a profile."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM amazon_reports 
        WHERE profile_id = %s 
        AND status = 'COMPLETED' 
        AND report_data IS NOT NULL
        AND (report_type LIKE '%DISCOVERY%' OR report_type LIKE '%discovery%' OR report_type LIKE '%SP_ASINS%')
        ORDER BY created_at DESC
        LIMIT 1
    """, (profile_id,))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_all_profiles_with_report_status():
    """Get all profiles with their report status (has 14D, 30D reports or not)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT 
            cp.profile_id,
            cp.country_code,
            cp.client_account_id as account_id,
            ca.client_name as account_name,
            (SELECT COUNT(*) FROM amazon_reports ar 
             WHERE ar.profile_id = cp.profile_id 
             AND ar.status = 'COMPLETED' 
             AND ar.report_type LIKE '%14D%'
             AND ar.report_data IS NOT NULL) as has_14d,
            (SELECT COUNT(*) FROM amazon_reports ar 
             WHERE ar.profile_id = cp.profile_id 
             AND ar.status = 'COMPLETED' 
             AND ar.report_type LIKE '%30D%'
             AND ar.report_data IS NOT NULL) as has_30d
        FROM client_profiles cp
        JOIN client_accounts ca ON cp.client_account_id = ca.id
        ORDER BY ca.client_name, cp.country_code
    """)
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def get_profiles_with_completed_reports():
    """Get profiles that have at least one completed report (14D or 30D)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT DISTINCT
            cp.profile_id,
            cp.country_code,
            cp.api_url,
            cp.client_account_id as account_id,
            ca.client_name as account_name
        FROM client_profiles cp
        JOIN client_accounts ca ON cp.client_account_id = ca.id
        JOIN amazon_reports ar ON ar.profile_id = cp.profile_id
        WHERE ar.status = 'COMPLETED' 
        AND ar.report_data IS NOT NULL
        ORDER BY ca.client_name, cp.country_code
    """)
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def get_profiles_without_reports():
    """Get profiles that have NO completed reports."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT 
            cp.profile_id,
            cp.country_code,
            cp.client_account_id as account_id,
            ca.client_name as account_name
        FROM client_profiles cp
        JOIN client_accounts ca ON cp.client_account_id = ca.id
        WHERE NOT EXISTS (
            SELECT 1 FROM amazon_reports ar 
            WHERE ar.profile_id = cp.profile_id 
            AND ar.status = 'COMPLETED'
            AND ar.report_data IS NOT NULL
        )
        ORDER BY ca.client_name, cp.country_code
    """)
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def create_autopilot_run(profile_id: str, account_id: int, mode: str = "normal"):
    """Create a new autopilot run record."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        INSERT INTO autopilot_runs (profile_id, account_id, status, mode, created_at)
        VALUES (%s, %s, 'PENDING', %s, NOW())
        RETURNING *
    """, (profile_id, account_id, mode))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def update_autopilot_run(run_id: int, **kwargs):
    """Update autopilot run with provided fields."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    set_clauses = []
    values = []
    for key, value in kwargs.items():
        if value == "NOW()":
            set_clauses.append(f"{key} = NOW()")
        else:
            set_clauses.append(f"{key} = %s")
            values.append(value)
    
    if not set_clauses:
        cur.close()
        conn.close()
        return None
    
    values.append(run_id)
    cur.execute(f"""
        UPDATE autopilot_runs 
        SET {', '.join(set_clauses)}
        WHERE id = %s
        RETURNING *
    """, values)
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_autopilot_run(run_id: int):
    """Get autopilot run by ID."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM autopilot_runs WHERE id = %s", (run_id,))
    result = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_pending_autopilot_runs():
    """Get all autopilot runs that are waiting for reports."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT ar.*, cp.api_url, cp.country_code
        FROM autopilot_runs ar
        LEFT JOIN client_profiles cp ON ar.profile_id = cp.profile_id
        WHERE ar.status IN ('PENDING', 'GENERATING_REPORTS', 'WAITING_REPORTS')
        ORDER BY ar.created_at ASC
    """)
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def get_autopilot_runs_for_profile(profile_id: str, limit: int = 10):
    """Get recent autopilot runs for a profile."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM autopilot_runs 
        WHERE profile_id = %s 
        ORDER BY created_at DESC 
        LIMIT %s
    """, (profile_id, limit))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def save_report_to_db(profile_id: str, account_id: int, report_id: str, report_type: str, 
                      start_date: str, end_date: str, autopilot_run_id: int = None, ad_product: str = 'SP'):
    """Save a new report record to the database."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        INSERT INTO amazon_reports (profile_id, account_id, report_id, report_type, ad_product,
                                    start_date, end_date, status, autopilot_run_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDING', %s, NOW())
        ON CONFLICT (report_id) DO UPDATE SET
            status = 'PENDING',
            autopilot_run_id = EXCLUDED.autopilot_run_id
        RETURNING *
    """, (profile_id, account_id, report_id, report_type, ad_product, start_date, end_date, autopilot_run_id))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_report_by_amazon_id(report_id: str):
    """Get report by Amazon report ID."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM amazon_reports WHERE report_id = %s", (report_id,))
    result = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return dict(result) if result else None


# ============================================================
# AUTOPILOT REFACTORED CRUD FUNCTIONS
# ============================================================

# --- RUNS ---

def get_runs_by_status(status_list: list):
    """Get all autopilot runs with status in the given list."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    placeholders = ','.join(['%s'] * len(status_list))
    cur.execute(f"""
        SELECT ar.*, cp.api_url, cp.country_code
        FROM autopilot_runs ar
        LEFT JOIN client_profiles cp ON ar.profile_id = cp.profile_id
        WHERE ar.status IN ({placeholders})
        ORDER BY ar.created_at ASC
    """, tuple(status_list))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def set_run_status(run_id: int, status: str):
    """Set status of an autopilot run."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        UPDATE autopilot_runs 
        SET status = %s
        WHERE id = %s
        RETURNING *
    """, (status, run_id))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def attach_run_reports(run_id: int, report_14_id: str, report_30_id: str):
    """Attach report IDs to an autopilot run."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        UPDATE autopilot_runs 
        SET report_14d_id = %s, report_30d_id = %s, reports_requested_at = NOW()
        WHERE id = %s
        RETURNING *
    """, (report_14_id, report_30_id, run_id))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


# --- REPORTS ---

def create_report_record(report_id: str, run_id: int, profile_id: str, account_id: int, 
                         report_type: str, start_date: str, end_date: str, status: str = "PENDING", ad_product: str = 'SP'):
    """Create a new report record linked to a run."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        INSERT INTO amazon_reports (report_id, autopilot_run_id, profile_id, account_id, 
                                    report_type, ad_product, start_date, end_date, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (report_id) DO UPDATE SET
            autopilot_run_id = EXCLUDED.autopilot_run_id,
            status = EXCLUDED.status
        RETURNING *
    """, (report_id, run_id, profile_id, account_id, report_type, ad_product, start_date, end_date, status))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def set_report_status(report_id: str, status: str, download_url: str = None):
    """Set status of a report and optionally the download URL."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if status == "COMPLETED" or status == "PARSED":
        cur.execute("""
            UPDATE amazon_reports 
            SET status = %s, download_url = %s, completed_at = NOW()
            WHERE report_id = %s
            RETURNING *
        """, (status, download_url, report_id))
    else:
        cur.execute("""
            UPDATE amazon_reports 
            SET status = %s
            WHERE report_id = %s
            RETURNING *
        """, (status, report_id))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def save_report_data(report_id: str, report_data: dict):
    """Save parsed report data to the database."""
    import json
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    report_data_json = json.dumps(report_data) if report_data else None
    
    cur.execute("""
        UPDATE amazon_reports 
        SET report_data = %s, status = 'PARSED', completed_at = NOW()
        WHERE report_id = %s
        RETURNING *
    """, (report_data_json, report_id))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_reports_for_run(run_id: int) -> dict:
    """Get 14D and 30D reports for a specific run, grouped by ad_product."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM amazon_reports 
        WHERE autopilot_run_id = %s
    """, (run_id,))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    reports = {"SP_14": None, "SP_30": None, "SB_14": None, "SB_30": None, "14": None, "30": None}
    for r in results:
        report_type = r.get("report_type", "")
        ad_product = r.get("ad_product", "SP")
        report_dict = dict(r)
        
        if "14D" in report_type:
            reports[f"{ad_product}_14"] = report_dict
            if ad_product == "SP":
                reports["14"] = report_dict
        elif "30D" in report_type:
            reports[f"{ad_product}_30"] = report_dict
            if ad_product == "SP":
                reports["30"] = report_dict
    
    return reports


def get_reports_by_status(status: str):
    """Get all reports with a given status."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT ar.*, ca.client_name as account_name
        FROM amazon_reports ar
        LEFT JOIN client_accounts ca ON ar.account_id = ca.id
        WHERE ar.status = %s
        ORDER BY ar.created_at ASC
    """, (status,))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


# --- ACTIONS ---

def insert_planned_actions(run_id: int, profile_id: str, actions_list: list):
    """Insert multiple planned actions for a run. Status defaults to PLANNED."""
    if not actions_list:
        return 0
    
    conn = get_connection()
    cur = conn.cursor()
    
    inserted = 0
    for action in actions_list:
        current_bid = action.get("current_bid")
        delta_bid = action.get("delta_bid", 0)
        new_bid = action.get("new_bid")
        if new_bid is None and current_bid is not None:
            new_bid = max(0.02, float(current_bid) + float(delta_bid))
        
        try:
            cur.execute("""
                INSERT INTO planned_actions 
                (profile_id, autopilot_run_id, campaign_id, campaign_name, ad_group_id,
                 keyword_id, keyword, asin, current_bid, delta_bid, new_bid,
                 reason, target_type, acos_14d, acos_30d, acos_be, ad_product, 
                 impressions_14d, impressions_30d, purchases_14d, purchases_30d, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PLANNED', NOW())
            """, (
                profile_id,
                run_id,
                action.get("campaign_id"),
                action.get("campaign_name"),
                action.get("ad_group_id"),
                action.get("keyword_id"),
                action.get("keyword"),
                action.get("asin"),
                current_bid,
                delta_bid,
                new_bid,
                action.get("reason") or action.get("tipo_azione"),
                action.get("target_type", "keyword"),
                action.get("acos_14d"),
                action.get("acos_30d"),
                action.get("acos_be"),
                action.get("ad_product", "SP"),
                action.get("impressions_14d"),
                action.get("impressions_30d"),
                action.get("purchases_14d", 0),
                action.get("purchases_30d", 0)
            ))
            inserted += 1
        except Exception as e:
            print(f"Error inserting action: {e}")
    
    conn.commit()
    cur.close()
    conn.close()
    
    return inserted


def get_actions_by_status(status: str, limit: int = 100):
    """Get planned actions with a given status."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM planned_actions 
        WHERE status = %s
        ORDER BY created_at ASC
        LIMIT %s
    """, (status, limit))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def mark_actions_status(action_ids: list, status: str):
    """Update status for a list of action IDs."""
    if not action_ids:
        return 0
    
    conn = get_connection()
    cur = conn.cursor()
    
    placeholders = ','.join(['%s'] * len(action_ids))
    cur.execute(f"""
        UPDATE planned_actions 
        SET status = %s, executed_at = CASE WHEN %s IN ('EXECUTED', 'FAILED') THEN NOW() ELSE executed_at END
        WHERE id IN ({placeholders})
    """, (status, status, *action_ids))
    
    updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    
    return updated


def count_actions_by_run_and_status(run_id: int, statuses: list) -> int:
    """Count actions for a run with given statuses."""
    conn = get_connection()
    cur = conn.cursor()
    
    placeholders = ','.join(['%s'] * len(statuses))
    cur.execute(f"""
        SELECT COUNT(*) FROM planned_actions 
        WHERE autopilot_run_id = %s AND status IN ({placeholders})
    """, (run_id, *statuses))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    return result[0] if result else 0


def get_asin_to_acos_be_map(profile_id: str = None) -> dict:
    """Get a mapping of ASIN to ACOS BE for books."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    if profile_id:
        cur.execute("""
            SELECT pb.asin, bec.acos_be 
            FROM profile_books pb 
            JOIN book_economics_cache bec ON pb.asin = bec.asin AND pb.marketplace = bec.marketplace
            WHERE pb.profile_id = %s AND bec.acos_be IS NOT NULL
        """, (profile_id,))
    else:
        cur.execute("""
            SELECT pb.asin, bec.acos_be 
            FROM profile_books pb 
            JOIN book_economics_cache bec ON pb.asin = bec.asin AND pb.marketplace = bec.marketplace
            WHERE bec.acos_be IS NOT NULL
        """)
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return {r["asin"]: float(r["acos_be"]) / 100 for r in results if r.get("asin")}


# ============================================
# AUTOPILOT V2 - Simplified Flow
# ============================================

def init_autopilot_v2_tables():
    """Initialize tables for the simplified Autopilot V2 flow."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Autopilot profiles - enable/disable per profile with scheduling
    cur.execute("""
        CREATE TABLE IF NOT EXISTS autopilot_profiles (
            id SERIAL PRIMARY KEY,
            account_id INTEGER REFERENCES client_accounts(id) ON DELETE CASCADE,
            profile_id VARCHAR(255) NOT NULL,
            enabled BOOLEAN DEFAULT FALSE,
            cadence VARCHAR(50) DEFAULT 'daily',
            next_run_at TIMESTAMP,
            last_run_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, profile_id)
        )
    """)
    
    # Profile to books mapping (many-to-many)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profile_books (
            id SERIAL PRIMARY KEY,
            profile_id VARCHAR(255) NOT NULL,
            asin VARCHAR(50) NOT NULL,
            title VARCHAR(500),
            marketplace VARCHAR(10),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(profile_id, asin)
        )
    """)
    
    # Book economics cache from Oxylab
    cur.execute("""
        CREATE TABLE IF NOT EXISTS book_economics_cache (
            id SERIAL PRIMARY KEY,
            asin VARCHAR(50) NOT NULL,
            marketplace VARCHAR(10) NOT NULL,
            price DECIMAL(10,2),
            print_cost DECIMAL(10,2),
            royalty_net DECIMAL(10,2),
            format VARCHAR(50),
            pages INTEGER,
            trim VARCHAR(50),
            ink VARCHAR(20),
            acos_be DECIMAL(5,2),
            acos_opt DECIMAL(5,2),
            title TEXT,
            author TEXT,
            image_url TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source VARCHAR(50) DEFAULT 'oxylabs',
            UNIQUE(asin, marketplace)
        )
    """)
    
    # Add columns if they don't exist (for existing databases)
    for col, col_type in [('title', 'TEXT'), ('author', 'TEXT'), ('image_url', 'TEXT')]:
        try:
            cur.execute(f"ALTER TABLE book_economics_cache ADD COLUMN IF NOT EXISTS {col} {col_type}")
        except Exception:
            pass
    
    # Aggregated ads metrics per book (ASIN)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ads_agg_book_metrics (
            id SERIAL PRIMARY KEY,
            run_id INTEGER,
            profile_id VARCHAR(255) NOT NULL,
            asin VARCHAR(50) NOT NULL,
            period_days INTEGER DEFAULT 14,
            spend DECIMAL(10,2) DEFAULT 0,
            sales DECIMAL(10,2) DEFAULT 0,
            orders INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            acos DECIMAL(5,2),
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(run_id, profile_id, asin, period_days)
        )
    """)
    
    # Ads report runs for tracking sync status
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ads_report_runs (
            id SERIAL PRIMARY KEY,
            account_id INTEGER REFERENCES client_accounts(id) ON DELETE CASCADE,
            profile_id VARCHAR(255) NOT NULL,
            marketplace VARCHAR(10),
            period_days INTEGER DEFAULT 14,
            status VARCHAR(50) DEFAULT 'PENDING',
            report_id VARCHAR(255),
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            error TEXT
        )
    """)
    
    # Autopilot sync jobs for tracking complete refresh flow
    cur.execute("""
        CREATE TABLE IF NOT EXISTS autopilot_sync_jobs (
            id SERIAL PRIMARY KEY,
            account_id INTEGER REFERENCES client_accounts(id) ON DELETE CASCADE,
            status VARCHAR(50) DEFAULT 'STARTING',
            phase VARCHAR(50) DEFAULT 'INIT',
            progress_pct INTEGER DEFAULT 0,
            message TEXT,
            total_profiles INTEGER DEFAULT 0,
            completed_profiles INTEGER DEFAULT 0,
            total_asins INTEGER DEFAULT 0,
            completed_asins INTEGER DEFAULT 0,
            total_reports INTEGER DEFAULT 0,
            completed_reports INTEGER DEFAULT 0,
            error TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    
    # Planned actions for bid changes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS planned_actions (
            id SERIAL PRIMARY KEY,
            autopilot_run_id INTEGER REFERENCES autopilot_runs(id) ON DELETE SET NULL,
            account_id INTEGER REFERENCES client_accounts(id) ON DELETE CASCADE,
            profile_id VARCHAR(64) NOT NULL,
            ad_product VARCHAR(20) DEFAULT 'SP',
            marketplace VARCHAR(10),
            asin VARCHAR(20),
            entity_type VARCHAR(32),
            target_type VARCHAR(32),
            target_id VARCHAR(128),
            keyword TEXT,
            action_type VARCHAR(32),
            current_bid NUMERIC(12,4),
            proposed_bid NUMERIC(12,4),
            bid_change_pct NUMERIC(6,2),
            acos_target NUMERIC(6,2),
            acos_actual NUMERIC(6,2),
            spend NUMERIC(12,2),
            sales NUMERIC(12,2),
            clicks INTEGER,
            orders INTEGER,
            rationale TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'PLANNED',
            planned_for DATE,
            executed_at TIMESTAMPTZ,
            execution_error TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Indexes for planned_actions
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_planned_actions_profile_status 
        ON planned_actions(profile_id, status)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_planned_actions_run 
        ON planned_actions(autopilot_run_id)
    """)
    
    cur.execute("""
        ALTER TABLE planned_actions 
        ADD COLUMN IF NOT EXISTS ad_product VARCHAR(20) DEFAULT 'SP'
    """)
    
    cur.execute("""
        ALTER TABLE planned_actions 
        ADD COLUMN IF NOT EXISTS entity_id VARCHAR(128)
    """)
    
    try:
        cur.execute("ALTER TABLE autopilot_settings_profiles ALTER COLUMN account_id DROP NOT NULL")
    except Exception:
        conn.rollback()

    for col, col_type in [('user_id', 'INTEGER'), ('is_system', 'BOOLEAN DEFAULT FALSE')]:
        try:
            cur.execute(f"ALTER TABLE autopilot_settings_profiles ADD COLUMN IF NOT EXISTS {col} {col_type}")
        except Exception:
            conn.rollback()

    try:
        cur.execute("""
            UPDATE autopilot_settings_profiles asp SET user_id = ca.user_id
            FROM client_accounts ca 
            WHERE asp.account_id = ca.id AND ca.user_id IS NOT NULL AND asp.user_id IS NULL
        """)
    except Exception:
        conn.rollback()

    conn.commit()
    cur.close()
    conn.close()


# ============================================
# AUTOPILOT V2 - CRUD Operations
# ============================================

def get_autopilot_profile(account_id: int, profile_id: str) -> dict:
    """Get autopilot settings for a profile."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM autopilot_profiles 
        WHERE account_id = %s AND profile_id = %s
    """, (account_id, profile_id))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_autopilot_profiles_for_account(account_id: int) -> list:
    """Get all autopilot profile settings for an account."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT ap.*, cp.country_code, cp.marketplace_string
        FROM autopilot_profiles ap
        JOIN client_profiles cp ON ap.profile_id = cp.profile_id AND ap.account_id = cp.client_account_id
        WHERE ap.account_id = %s
        ORDER BY ap.profile_id
    """, (account_id,))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def upsert_autopilot_profile(account_id: int, profile_id: str, enabled: bool, cadence: str = 'daily') -> dict:
    """Create or update autopilot settings for a profile."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    from datetime import timedelta
    next_run = datetime.now() + timedelta(days=1) if enabled else None
    
    cur.execute("""
        INSERT INTO autopilot_profiles (account_id, profile_id, enabled, cadence, next_run_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (account_id, profile_id) 
        DO UPDATE SET enabled = %s, cadence = %s, next_run_at = %s, updated_at = CURRENT_TIMESTAMP
        RETURNING *
    """, (account_id, profile_id, enabled, cadence, next_run, enabled, cadence, next_run))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_enabled_autopilot_profiles_due() -> list:
    """Get all enabled profiles where next_run_at <= now."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT ap.*, ca.client_name
        FROM autopilot_profiles ap
        JOIN client_accounts ca ON ap.account_id = ca.id
        WHERE ap.enabled = TRUE AND (ap.next_run_at IS NULL OR ap.next_run_at <= CURRENT_TIMESTAMP)
    """)
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def get_enabled_autopilot_profile_ids(account_id: int) -> list:
    """Get list of profile_ids with autopilot enabled for an account."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT profile_id FROM autopilot_profiles 
        WHERE account_id = %s AND enabled = TRUE
    """, (account_id,))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [str(r['profile_id']) for r in results]


def upsert_profile_book(profile_id: str, asin: str, title: str = None, marketplace: str = None) -> dict:
    """Add or update a book for a profile."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        INSERT INTO profile_books (profile_id, asin, title, marketplace)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (profile_id, asin) 
        DO UPDATE SET title = COALESCE(%s, profile_books.title), marketplace = COALESCE(%s, profile_books.marketplace)
        RETURNING *
    """, (profile_id, asin, title, marketplace, title, marketplace))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_books_for_profile(profile_id: str) -> list:
    """Get all books for a profile with economics data."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT pb.*, bec.price, bec.print_cost, bec.royalty_net, bec.format, 
               bec.pages, bec.trim, bec.ink, bec.acos_be, bec.acos_opt, bec.fetched_at,
               bec.title, bec.author, bec.image_url
        FROM profile_books pb
        LEFT JOIN book_economics_cache bec ON pb.asin = bec.asin AND pb.marketplace = bec.marketplace
        WHERE pb.profile_id = %s
        ORDER BY pb.asin
    """, (profile_id,))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def upsert_book_economics(asin: str, marketplace: str, data: dict) -> dict:
    """Update book economics cache."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        INSERT INTO book_economics_cache (asin, marketplace, price, print_cost, royalty_net, format, pages, trim, ink, acos_be, acos_opt, fetched_at, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
        ON CONFLICT (asin, marketplace) 
        DO UPDATE SET price = %s, print_cost = %s, royalty_net = %s, format = %s, pages = %s, 
                      trim = %s, ink = %s, acos_be = %s, acos_opt = %s, fetched_at = CURRENT_TIMESTAMP, source = %s
        RETURNING *
    """, (
        asin, marketplace, 
        data.get('price'), data.get('print_cost'), data.get('royalty_net'),
        data.get('format'), data.get('pages'), data.get('trim'), data.get('ink'),
        data.get('acos_be'), data.get('acos_opt'), data.get('source', 'oxylabs'),
        data.get('price'), data.get('print_cost'), data.get('royalty_net'),
        data.get('format'), data.get('pages'), data.get('trim'), data.get('ink'),
        data.get('acos_be'), data.get('acos_opt'), data.get('source', 'oxylabs')
    ))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def upsert_ads_book_metrics(run_id: int, profile_id: str, asin: str, period_days: int, metrics: dict) -> dict:
    """Update aggregated ads metrics for a book."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    spend = metrics.get('spend', 0)
    sales = metrics.get('sales', 0)
    acos = (spend / sales * 100) if sales > 0 else None
    
    cur.execute("""
        INSERT INTO ads_agg_book_metrics (run_id, profile_id, asin, period_days, spend, sales, orders, clicks, impressions, acos, calculated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (run_id, profile_id, asin, period_days) 
        DO UPDATE SET spend = %s, sales = %s, orders = %s, clicks = %s, impressions = %s, acos = %s, calculated_at = CURRENT_TIMESTAMP
        RETURNING *
    """, (
        run_id, profile_id, asin, period_days,
        spend, sales, metrics.get('orders', 0), metrics.get('clicks', 0), metrics.get('impressions', 0), acos,
        spend, sales, metrics.get('orders', 0), metrics.get('clicks', 0), metrics.get('impressions', 0), acos
    ))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_book_metrics_for_profile(profile_id: str, period_days: int = 14) -> list:
    """Get latest aggregated metrics for all books in a profile."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT DISTINCT ON (asin) *
        FROM ads_agg_book_metrics 
        WHERE profile_id = %s AND period_days = %s
        ORDER BY asin, calculated_at DESC
    """, (profile_id, period_days))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def create_big_bang_job(account_id: int, delay_minutes: int = 60, ad_product: str = "ALL", recurring_mode: str = "single", recurring_interval_days: int = None) -> dict:
    """Create a new BIG BANG job.
    
    Args:
        account_id: Account ID
        delay_minutes: Minutes to delay execution
        ad_product: SP, SB, or ALL
        recurring_mode: 'single' (one-time), 'recurring' (continuous), 'recurring_3d', 'recurring_5d'
        recurring_interval_days: Days between recurring executions (None for single, 0 for continuous recurring)
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        INSERT INTO big_bang_jobs (account_id, delay_hours, ad_product, status, current_phase, phase_status, phase_message, recurring_mode, recurring_interval_days, created_at)
        VALUES (%s, %s, %s, 'RUNNING', 1, 'pending', 'Inizializzazione...', %s, %s, NOW())
        RETURNING *
    """, (account_id, delay_minutes, ad_product, recurring_mode, recurring_interval_days))
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_big_bang_job(job_id: int) -> dict:
    """Get a BIG BANG job by ID."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM big_bang_jobs WHERE id = %s", (job_id,))
    result = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_active_big_bang_job(account_id: int) -> dict:
    """Get active BIG BANG job for an account (RUNNING, SCHEDULED, WAITING, or EXECUTING)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM big_bang_jobs 
        WHERE account_id = %s AND status IN ('RUNNING', 'SCHEDULED', 'WAITING', 'EXECUTING')
        ORDER BY created_at DESC LIMIT 1
    """, (account_id,))
    result = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def update_big_bang_job(job_id: int, **kwargs) -> dict:
    """Update a BIG BANG job."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    set_parts = []
    values = []
    for key, value in kwargs.items():
        set_parts.append(f"{key} = %s")
        values.append(value)
    
    set_parts.append("updated_at = NOW()")
    values.append(job_id)
    
    cur.execute(f"""
        UPDATE big_bang_jobs SET {', '.join(set_parts)}
        WHERE id = %s RETURNING *
    """, values)
    
    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def get_pending_scheduled_jobs() -> list:
    """Get all jobs that are SCHEDULED and ready to execute (execute_at <= NOW)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM big_bang_jobs 
        WHERE status = 'SCHEDULED' AND execute_at <= NOW()
        ORDER BY execute_at ASC
    """)
    results = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]


def get_big_bang_jobs_for_account(account_id: int, limit: int = 10) -> list:
    """Get recent BIG BANG jobs for an account."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM big_bang_jobs 
        WHERE account_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    """, (account_id, limit))
    results = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return [dict(r) for r in results]
