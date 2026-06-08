import json
import os
from datetime import datetime

CASE_DB_PATH = "data/cases.json"

TERMINAL_STATUSES = ["RESOLVED", "CLOSED", "CANCELLED"]


def _ensure_case_db():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(CASE_DB_PATH):
        with open(CASE_DB_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)


def load_cases():
    _ensure_case_db()

    try:
        with open(CASE_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def save_cases(cases):
    _ensure_case_db()

    with open(CASE_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2)


def find_open_case_by_transaction(transaction_id):
    cases = load_cases()

    for case in cases:
        if (
            case.get("transaction_id") == transaction_id
            and case.get("status") not in TERMINAL_STATUSES
        ):
            return case

    return None


def insert_case(case):
    cases = load_cases()
    cases.append(case)
    save_cases(cases)
    return case


def update_case(case_id, updates):
    cases = load_cases()

    for case in cases:
        if case.get("case_id") == case_id:
            case.update(updates)
            case["updated_at"] = datetime.now().isoformat()
            save_cases(cases)
            return case

    return None