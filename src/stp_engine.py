def evaluate_stp_eligibility(transaction, dispute_type, monthly_writeoff_count=0):
    amount = float(transaction["amount"])

    if (
        amount <= 25
        and dispute_type in ["services_not_rendered", "incorrect_amount"]
        and monthly_writeoff_count < 3
    ):
        return {
            "stp_eligible": True,
            "resolution_code": "LOW_VALUE_WRITEOFF",
            "recommended_action": "Auto approve low-value write-off",
            "human_review_required": False,
            "accounting_action": "Credit customer and debit write-off GL account",
            "policy_reference": "Section 1.1 Low-Value Write-Off Rule"
        }

    if dispute_type == "duplicate_charge":
        return {
            "stp_eligible": False,
            "resolution_code": "DUPLICATE_REVIEW_REQUIRED",
            "recommended_action": "Route to duplicate review. Duplicate transaction validation is required before any customer credit decision.",
            "human_review_required": True,
            "accounting_action": "No accounting action until duplicate transaction is confirmed.",
            "policy_reference": "Duplicate Transaction Validation Deferred"
        }

    return {
        "stp_eligible": False,
        "resolution_code": "OPEN_INVESTIGATION",
        "recommended_action": "Open dispute investigation",
        "human_review_required": True,
        "accounting_action": "Place amount in suspense if provisional credit is issued",
        "policy_reference": "Reg E / Reg Z / Network Rules Review Required"
    }