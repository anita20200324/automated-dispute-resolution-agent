from datetime import datetime
import random

from case_repository import (
    find_open_case_by_transaction,
    insert_case,
    update_case
)


def _status_event(status, note):
    return {
        "status": status,
        "note": note,
        "timestamp": datetime.now().isoformat()
    }


def create_dispute_case(transaction, dispute_type, customer_summary):
    existing_case = find_open_case_by_transaction(transaction["transaction_id"])

    if existing_case:
        existing_history = existing_case.get("status_history", [])
        existing_history.append(
            _status_event(
                "INTAKE_MERGED",
                "New intake attempt matched this existing open case."
            )
        )

        updated_existing_case = update_case(
            case_id=existing_case["case_id"],
            updates={
                "status": existing_case.get("status", "CREATED"),
                "status_history": existing_history,
                "latest_duplicate_intake": customer_summary
            }
        ) or existing_case

        return {
            "duplicate_case_found": True,
            "case": updated_existing_case,
            "duplicate_check": {
                "result": "EXISTING_CASE_FOUND",
                "message": "Existing open case found for this transaction. New intake merged into existing case.",
                "existing_case_id": updated_existing_case["case_id"],
                "existing_case_status": updated_existing_case.get("status"),
                "existing_case_created_at": updated_existing_case.get("created_at"),
                "action": "MERGE_TO_EXISTING_CASE"
            }
        }

    case_id = f"D-{random.randint(10000, 99999)}"

    case = {
        "case_id": case_id,
        "transaction_id": transaction["transaction_id"],
        "customer_id": transaction["customer_id"],
        "customer_name": transaction.get("customer_name"),
        "merchant": transaction["merchant"],
        "amount": float(transaction["amount"]),
        "date": transaction["date"],
        "dispute_type": dispute_type,
        "summary": customer_summary,
        "status": "CREATED",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "status_history": [
            _status_event("CREATED", "Dispute case created.")
        ]
    }

    insert_case(case)

    return {
        "duplicate_case_found": False,
        "case": case,
        "duplicate_check": {
            "result": "PASSED",
            "message": "No existing open case found for this transaction.",
            "existing_case_id": None,
            "action": "CREATE_NEW_CASE"
        }
    }


def update_case_status(case, status, note=None):
    history = case.get("status_history", [])
    history.append(
        _status_event(
            status,
            note or f"Case status updated to {status}."
        )
    )

    updated_case = update_case(
        case_id=case["case_id"],
        updates={
            "status": status,
            "status_history": history
        }
    )

    return updated_case or case