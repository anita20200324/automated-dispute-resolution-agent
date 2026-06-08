import os
from dotenv import load_dotenv
import psycopg

load_dotenv()

POSTGRES_URI = os.getenv("POSTGRES_URI")

if not POSTGRES_URI:
    raise ValueError("POSTGRES_URI not found in .env")


DDL = """
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    transaction_id TEXT,
    customer_id TEXT,
    merchant TEXT,
    amount NUMERIC(12, 2),
    dispute_type TEXT,
    current_status TEXT,
    assigned_queue TEXT,
    assigned_to TEXT,
    lock_owner TEXT,
    lock_acquired_at TIMESTAMPTZ,
    lock_expires_at TIMESTAMPTZ,
    sla_due_at TIMESTAMPTZ,
    case_state_snapshot JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS case_audit_history (
    id BIGSERIAL PRIMARY KEY,
    case_id TEXT,
    thread_id TEXT,
    node_name TEXT,
    status TEXT,
    event_type TEXT,
    assigned_queue TEXT,
    assigned_to TEXT,
    completed_by TEXT,
    result TEXT,
    score NUMERIC,
    note TEXT,
    sla_due_at TIMESTAMPTZ,
    case_state_snapshot JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS communications (
    id BIGSERIAL PRIMARY KEY,
    case_id TEXT,
    communication_type TEXT,
    to_address TEXT,
    subject TEXT,
    body TEXT,
    status TEXT,
    generated_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_case_audit_case_id
ON case_audit_history(case_id);

CREATE INDEX IF NOT EXISTS idx_case_audit_thread_id
ON case_audit_history(thread_id);

CREATE INDEX IF NOT EXISTS idx_cases_current_status
ON cases(current_status);
"""


def setup_business_db():
    with psycopg.connect(POSTGRES_URI) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()

    print("SUCCESS")
    print("Business tables created successfully.")


if __name__ == "__main__":
    setup_business_db()