import os
import json
from datetime import datetime
from dotenv import load_dotenv
import psycopg

load_dotenv()

POSTGRES_URI = os.getenv("POSTGRES_URI")

if not POSTGRES_URI:
    raise ValueError("POSTGRES_URI not found in .env")


def upsert_case_record(case_id, transaction, dispute_type, current_status, case_state_snapshot):
    with psycopg.connect(POSTGRES_URI) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cases (
                    case_id,
                    transaction_id,
                    customer_id,
                    merchant,
                    amount,
                    dispute_type,
                    current_status,
                    case_state_snapshot,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
                ON CONFLICT (case_id)
                DO UPDATE SET
                    transaction_id = EXCLUDED.transaction_id,
                    customer_id = EXCLUDED.customer_id,
                    merchant = EXCLUDED.merchant,
                    amount = EXCLUDED.amount,
                    dispute_type = EXCLUDED.dispute_type,
                    current_status = EXCLUDED.current_status,
                    case_state_snapshot = EXCLUDED.case_state_snapshot,
                    updated_at = NOW()
                """,
                (
                    case_id,
                    transaction.get("transaction_id"),
                    transaction.get("customer_id"),
                    transaction.get("merchant"),
                    float(transaction.get("amount", 0)),
                    dispute_type,
                    current_status,
                    json.dumps(case_state_snapshot),
                )
            )
        conn.commit()


def insert_case_audit_event(event):
    with psycopg.connect(POSTGRES_URI) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO case_audit_history (
                    case_id,
                    thread_id,
                    node_name,
                    status,
                    event_type,
                    assigned_queue,
                    assigned_to,
                    completed_by,
                    result,
                    score,
                    note,
                    sla_due_at,
                    case_state_snapshot
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s::jsonb
                )
                """,
                (
                    event.get("case_id"),
                    event.get("thread_id"),
                    event.get("node_name"),
                    event.get("status"),
                    event.get("event_type"),
                    event.get("assigned_queue"),
                    event.get("assigned_to"),
                    event.get("completed_by"),
                    event.get("result"),
                    event.get("score"),
                    event.get("note"),
                    event.get("sla_due_at"),
                    json.dumps(event.get("case_state_snapshot", {})),
                )
            )
        conn.commit()


def insert_communication(case_id, email_payload):
    with psycopg.connect(POSTGRES_URI) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO communications (
                    case_id,
                    communication_type,
                    to_address,
                    subject,
                    body,
                    status,
                    generated_at,
                    sent_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    case_id,
                    "CUSTOMER_EMAIL",
                    email_payload.get("to"),
                    email_payload.get("subject"),
                    email_payload.get("body"),
                    email_payload.get("status"),
                    email_payload.get("generated_at"),
                    email_payload.get("sent_at"),
                )
            )
        conn.commit()


def build_event(
    *,
    case_id,
    thread_id,
    node_name,
    status,
    event_type,
    result=None,
    note=None,
    assigned_queue=None,
    assigned_to=None,
    completed_by=None,
    score=None,
    sla_due_at=None,
    case_state_snapshot=None
):
    return {
        "case_id": case_id,
        "thread_id": thread_id,
        "node_name": node_name,
        "status": status,
        "event_type": event_type,
        "assigned_queue": assigned_queue,
        "assigned_to": assigned_to,
        "completed_by": completed_by,
        "result": result,
        "score": score,
        "note": note,
        "sla_due_at": sla_due_at,
        "case_state_snapshot": case_state_snapshot or {},
        "created_at": datetime.now().isoformat()
    }