import os
from dotenv import load_dotenv
from openai import OpenAI
import chromadb
from chromadb.utils import embedding_functions

from questionnaire import classify_dispute_type, get_questionnaire
from stp_engine import evaluate_stp_eligibility
from case_service import create_dispute_case, update_case_status


# -----------------------------
# Environment / OpenAI / ChromaDB
# -----------------------------
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY is missing. Please set it in your .env file.")

client_ai = OpenAI(api_key=api_key)

client_db = chromadb.PersistentClient(path="./chroma_db")

openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=api_key,
    model_name="text-embedding-3-small"
)

collection = client_db.get_or_create_collection(
    name="bank_policies",
    embedding_function=openai_ef
)


# -----------------------------
# Utility Helpers
# -----------------------------
def _transaction_to_dict(transaction):
    if hasattr(transaction, "to_dict"):
        return transaction.to_dict()
    return dict(transaction)


def _transaction_to_text(transaction_dict):
    return "\n".join([f"{key}: {value}" for key, value in transaction_dict.items()])


def _add_audit(audit_trail, step, status, result, details=None):
    audit_trail.append({
        "step": step,
        "status": status,
        "result": result,
        "details": details or {}
    })


# -----------------------------
# Fraud Screening
# -----------------------------
def detect_fraud_risk(transaction_data, customer_input):
    """
    AI-assisted fraud risk screening.
    This does not make the final fraud decision; it provides a risk assessment.
    """

    fraud_prompt = f"""
You are a Fraud Detection Expert for a retail bank.

Analyze the transaction and customer claim for fraud risk.

Transaction Data:
{transaction_data}

Customer Claim:
{customer_input}

Check for these red flags:
1. Serial disputer behavior
2. Velocity attack
3. Unusually high transaction amount
4. Multiple disputed transactions
5. Unauthorized transaction indicators

Output Format:
Risk Level: [Low/Medium/High]
Reason: [Short explanation in English]
Recommended Action: [Continue standard review / Escalate to SIU / Request more evidence]
"""

    response = client_ai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": fraud_prompt}],
        temperature=0
    )

    return response.choices[0].message.content


# -----------------------------
# RAG Policy Analysis
# -----------------------------
def analyze_dispute(customer_query, transaction_amount):
    """
    RAG-based policy analysis.
    Retrieves the most relevant bank policy from ChromaDB and asks the LLM
    to generate a policy-grounded recommendation.
    """

    results = collection.query(
        query_texts=[customer_query],
        n_results=1
    )

    if results and results.get("documents") and results["documents"][0]:
        relevant_policy = results["documents"][0][0]
    else:
        relevant_policy = "No matching policy section found."

    system_prompt = f"""
You are an expert Bank Dispute Resolution Officer.

Decide whether the dispute should be Approved, Denied, or routed for Manual Review
based on the bank policy below.

BANK POLICY:
{relevant_policy}

TRANSACTION DATA:
Amount: ${transaction_amount}

Output Format:
Decision:
Policy Reference:
Reason:
Recommended Next Step:
"""

    response = client_ai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Customer Claim: {customer_query}"}
        ],
        temperature=0
    )

    return response.choices[0].message.content


# -----------------------------
# Main Orchestrator
# -----------------------------
def run_dispute_agent(transaction, customer_input, checkbox_data, region="TX"):
    """
    Main orchestration function for the dispute workflow.

    Flow:
    1. Classify dispute type
    2. Load dynamic questionnaire
    3. Duplicate case check + case creation
    4. STP eligibility
    5. Auto-resolution OR investigation path
    6. Investigation includes fraud screening + RAG policy analysis
    7. Case status is persisted through case_service / case_repository
    """

    audit_trail = []
    transaction_dict = _transaction_to_dict(transaction)

    # -----------------------------
    # Step 1: Dispute Classification
    # -----------------------------
    dispute_type = classify_dispute_type(customer_input, checkbox_data)
    questionnaire = get_questionnaire(dispute_type)

    _add_audit(
        audit_trail,
        step="Dispute Classification",
        status="COMPLETED",
        result=dispute_type,
        details={
            "customer_input": customer_input,
            "checkbox_data": checkbox_data,
            "region": region,
            "questionnaire": questionnaire
        }
    )

    # -----------------------------
    # Step 2: Case Creation + Duplicate Case Check
    # -----------------------------
    customer_summary = {
        "customer_input": customer_input,
        "checkbox_data": checkbox_data,
        "region": region,
        "recommended_questionnaire": questionnaire
    }

    case_creation_result = create_dispute_case(
        transaction=transaction_dict,
        dispute_type=dispute_type,
        customer_summary=customer_summary
    )

    case = case_creation_result["case"]
    duplicate_case_found = case_creation_result["duplicate_case_found"]
    duplicate_check = case_creation_result["duplicate_check"]

    _add_audit(
        audit_trail,
        step="Duplicate Case Check",
        status="COMPLETED",
        result=duplicate_check["result"],
        details=duplicate_check
    )

    _add_audit(
        audit_trail,
        step="Case Creation",
        status="SKIPPED" if duplicate_case_found else "COMPLETED",
        result=case["case_id"],
        details={
            "duplicate_case_found": duplicate_case_found,
            "case": case
        }
    )

    # -----------------------------
    # Duplicate case branch:
    # Existing open case found.
    # Do NOT create new case.
    # Do NOT run STP.
    # Do NOT generate auto-resolution.
    # -----------------------------
    if duplicate_case_found:
        _add_audit(
            audit_trail,
            step="Duplicate Case Handling",
            status="COMPLETED",
            result="MERGED_TO_EXISTING_CASE",
            details={
                "message": "New intake was merged into an existing open case.",
                "existing_case_id": duplicate_check.get("existing_case_id"),
                "existing_case_status": duplicate_check.get("existing_case_status"),
                "action": duplicate_check.get("action")
            }
        )

        return {
            "case": case,
            "duplicate_case_found": True,
            "duplicate_check": duplicate_check,
            "region": region,
            "dispute_type": case.get("dispute_type", dispute_type),
            "questionnaire": questionnaire,
            "path": "MERGED_TO_EXISTING_CASE",
            "stp_result": None,
            "fraud_report": None,
            "policy_decision": "Existing open case found. Intake merged into existing case.",
            "human_review_required": False,
            "final_decision": "Merged to existing case",
            "accounting_action": "No new accounting action. Existing case remains active.",
            "audit_trail": audit_trail
        }

    # -----------------------------
    # Step 3: Duplicate check passed
    # -----------------------------
    case = update_case_status(
        case,
        "DUPLICATE_CHECK_PASSED",
        "Duplicate case check passed. No existing open case found for this transaction."
    )

    _add_audit(
        audit_trail,
        step="Case Status Update",
        status="COMPLETED",
        result="DUPLICATE_CHECK_PASSED",
        details={"case_id": case["case_id"]}
    )

    # -----------------------------
    # Step 4: STP Eligibility
    # -----------------------------
    stp_result = evaluate_stp_eligibility(
        transaction=transaction_dict,
        dispute_type=dispute_type
    )

    _add_audit(
        audit_trail,
        step="STP Eligibility",
        status="COMPLETED",
        result=stp_result["resolution_code"],
        details=stp_result
    )

    # -----------------------------
    # Step 5A: Auto-resolution path
    # -----------------------------
    if stp_result["stp_eligible"]:
        case = update_case_status(
            case,
            "AUTO_RESOLVED",
            "Case qualified for straight-through processing."
        )

        _add_audit(
            audit_trail,
            step="Path Selection",
            status="COMPLETED",
            result="AUTO_RESOLUTION",
            details={
                "reason": "STP rules allowed auto-resolution.",
                "resolution_code": stp_result["resolution_code"]
            }
        )

        _add_audit(
            audit_trail,
            step="Case Status Update",
            status="COMPLETED",
            result="AUTO_RESOLVED",
            details={"case_id": case["case_id"]}
        )

        return {
            "case": case,
            "duplicate_case_found": False,
            "duplicate_check": duplicate_check,
            "region": region,
            "dispute_type": dispute_type,
            "questionnaire": questionnaire,
            "path": "AUTO_RESOLUTION",
            "stp_result": stp_result,
            "fraud_report": None,
            "policy_decision": stp_result["recommended_action"],
            "human_review_required": False,
            "final_decision": stp_result["recommended_action"],
            "accounting_action": stp_result["accounting_action"],
            "audit_trail": audit_trail
        }

    # -----------------------------
    # Step 5B: Investigation path
    # -----------------------------
    case = update_case_status(
        case,
        "HUMAN_REVIEW_PENDING",
        "Case does not qualify for STP and requires investigation / human review."
    )

    _add_audit(
        audit_trail,
        step="Path Selection",
        status="COMPLETED",
        result="INVESTIGATION",
        details={
            "reason": "STP rules did not allow auto-resolution.",
            "resolution_code": stp_result["resolution_code"]
        }
    )

    _add_audit(
        audit_trail,
        step="Case Status Update",
        status="COMPLETED",
        result="HUMAN_REVIEW_PENDING",
        details={"case_id": case["case_id"]}
    )

    # Fraud screening
    fraud_report = detect_fraud_risk(
        transaction_data=_transaction_to_text(transaction_dict),
        customer_input=customer_input
    )

    _add_audit(
        audit_trail,
        step="Fraud Screening",
        status="COMPLETED",
        result=fraud_report
    )

    # Policy analysis
    policy_decision = analyze_dispute(
        customer_query=customer_input,
        transaction_amount=transaction_dict["amount"]
    )

    _add_audit(
        audit_trail,
        step="Policy Analysis",
        status="COMPLETED",
        result=policy_decision
    )

    return {
        "case": case,
        "duplicate_case_found": False,
        "duplicate_check": duplicate_check,
        "region": region,
        "dispute_type": dispute_type,
        "questionnaire": questionnaire,
        "path": "INVESTIGATION",
        "stp_result": stp_result,
        "fraud_report": fraud_report,
        "policy_decision": policy_decision,
        "human_review_required": True,
        "final_decision": "Pending Human Review",
        "accounting_action": stp_result["accounting_action"],
        "audit_trail": audit_trail
    }