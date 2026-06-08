import os
from datetime import datetime
from operator import add
from typing import Annotated, Literal, Optional, TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

from questionnaire import classify_dispute_type, get_questionnaire
from case_service import create_dispute_case, update_case_status
from stp_engine import evaluate_stp_eligibility
from email_service import generate_resolution_email

from audit_repository import (
    upsert_case_record,
    insert_case_audit_event,
    insert_communication,
    build_event,
)

# Reuse existing RAG / fraud capabilities from the current agent layer.
from agent import detect_fraud_risk, analyze_dispute


load_dotenv()

POSTGRES_URI = os.getenv("POSTGRES_URI")

if not POSTGRES_URI:
    raise ValueError("POSTGRES_URI not found in .env")


# ============================================================
# Status Naming Convention
# ============================================================

PENDING_CLASSIFICATION = "PENDING_CLASSIFICATION"
PENDING_DUPLICATE_CHECK = "PENDING_DUPLICATE_CHECK"
PENDING_STP_EVALUATION = "PENDING_STP_EVALUATION"
PENDING_INVESTIGATION = "PENDING_INVESTIGATION"
PENDING_CUSTOMER_COMMUNICATION = "PENDING_CUSTOMER_COMMUNICATION"

RESOLVED_DUPLICATE_CASE = "RESOLVED_DUPLICATE_CASE"
RESOLVED_SMALL_DOLLAR_WRITEOFF = "RESOLVED_SMALL_DOLLAR_WRITEOFF"
RESOLVED_CUSTOMER_LIABILITY = "RESOLVED_CUSTOMER_LIABILITY"


# ============================================================
# State Model
# ============================================================

class DisputeState(TypedDict, total=False):
    # Input
    transaction: dict
    customer_input: str
    checkbox_data: dict
    region: str

    # Case / workflow identity
    thread_id: str
    case_id: str

    # Current workflow status
    current_status: str
    current_node: str
    path: str
    resolution_type: str

    # Case-state snapshot
    # This is the LangGraph equivalent of a case clipboard/state snapshot.
    case_state_snapshot: dict

    # Timeline / audit
    node_trace: Annotated[list[str], add]
    case_timeline: Annotated[list[dict], add]
    audit_trail: Annotated[list[dict], add]

    # Classification
    dispute_type: str
    questionnaire: list

    # Case creation / duplicate check
    case: dict
    duplicate_case_found: bool
    duplicate_check: dict

    # STP
    stp_result: Optional[dict]

    # Investigation
    fraud_report: Optional[str]
    policy_decision: Optional[str]
    human_review_required: bool

    # Communication / final output
    email_payload: Optional[dict]
    final_decision: str
    accounting_action: str


# ============================================================
# Utility Helpers
# ============================================================

def _now():
    return datetime.now().isoformat()


def _transaction_to_dict(transaction):
    if hasattr(transaction, "to_dict"):
        raw = transaction.to_dict()
    else:
        raw = dict(transaction)

    # Make values JSON-friendly.
    clean = {}
    for key, value in raw.items():
        if hasattr(value, "item"):
            value = value.item()
        clean[key] = value

    return clean


def _transaction_to_text(transaction_dict):
    return "\n".join([f"{key}: {value}" for key, value in transaction_dict.items()])


def _customer_name(transaction):
    return transaction.get("customer_name") or transaction.get("customer_id") or "Customer"


def _base_snapshot(state: DisputeState, **updates):
    snapshot = dict(state.get("case_state_snapshot", {}))
    snapshot.update(updates)
    snapshot["updated_at"] = _now()
    return snapshot


def _record_event(
    *,
    state: DisputeState,
    node_name: str,
    status: str,
    event_type: str,
    result: Optional[str] = None,
    note: Optional[str] = None,
    assigned_queue: Optional[str] = None,
    assigned_to: Optional[str] = None,
    completed_by: Optional[str] = None,
    score: Optional[float] = None,
    sla_due_at: Optional[str] = None,
    case_state_snapshot: Optional[dict] = None,
):
    event = build_event(
        case_id=state.get("case_id"),
        thread_id=state.get("thread_id"),
        node_name=node_name,
        status=status,
        event_type=event_type,
        result=result,
        note=note,
        assigned_queue=assigned_queue,
        assigned_to=assigned_to,
        completed_by=completed_by,
        score=score,
        sla_due_at=sla_due_at,
        case_state_snapshot=case_state_snapshot or state.get("case_state_snapshot", {}),
    )

    # Persist business-visible audit event.
    insert_case_audit_event(event)

    return event


def _upsert_business_case(state: DisputeState):
    case = state.get("case")
    transaction = state.get("transaction")
    dispute_type = state.get("dispute_type")
    current_status = state.get("current_status")
    snapshot = state.get("case_state_snapshot", {})

    if not case or not transaction:
        return

    upsert_case_record(
        case_id=case.get("case_id"),
        transaction=transaction,
        dispute_type=dispute_type,
        current_status=current_status,
        case_state_snapshot=snapshot,
    )


# ============================================================
# Nodes
# ============================================================

def classify_dispute_node(state: DisputeState) -> DisputeState:
    transaction = _transaction_to_dict(state["transaction"])
    customer_input = state["customer_input"]
    checkbox_data = state["checkbox_data"]
    region = state.get("region", "TX")

    dispute_type = classify_dispute_type(customer_input, checkbox_data)
    questionnaire = get_questionnaire(dispute_type)

    snapshot = _base_snapshot(
        state,
        transaction=transaction,
        customer_input=customer_input,
        checkbox_data=checkbox_data,
        region=region,
        dispute_type=dispute_type,
        questionnaire=questionnaire,
    )

    event = _record_event(
        state={
            **state,
            "case_state_snapshot": snapshot,
            "current_status": PENDING_DUPLICATE_CHECK,
        },
        node_name="classify_dispute",
        status=PENDING_DUPLICATE_CHECK,
        event_type="CLASSIFICATION",
        result=dispute_type,
        note="Dispute classified and dynamic questionnaire selected.",
        case_state_snapshot=snapshot,
    )

    return {
        "transaction": transaction,
        "region": region,
        "dispute_type": dispute_type,
        "questionnaire": questionnaire,
        "current_node": "classify_dispute",
        "current_status": PENDING_DUPLICATE_CHECK,
        "case_state_snapshot": snapshot,
        "node_trace": ["classify_dispute"],
        "case_timeline": [event],
        "audit_trail": [event],
    }


def duplicate_case_check_node(state: DisputeState) -> DisputeState:
    transaction = state["transaction"]
    dispute_type = state["dispute_type"]

    customer_summary = {
        "customer_input": state.get("customer_input"),
        "checkbox_data": state.get("checkbox_data"),
        "region": state.get("region"),
        "recommended_questionnaire": state.get("questionnaire"),
    }

    result = create_dispute_case(
        transaction=transaction,
        dispute_type=dispute_type,
        customer_summary=customer_summary,
    )

    case = result["case"]
    duplicate_case_found = result["duplicate_case_found"]
    duplicate_check = result["duplicate_check"]

    case_id = case["case_id"]

    if duplicate_case_found:
        current_status = PENDING_CUSTOMER_COMMUNICATION
        event_result = "DUPLICATE_CASE_FOUND"
        note = "Existing open case found. New intake merged into existing case."
    else:
        current_status = PENDING_STP_EVALUATION
        event_result = "DUPLICATE_CHECK_PASSED"
        note = "No existing open case found. Case is ready for STP evaluation."

    snapshot = _base_snapshot(
        state,
        case=case,
        case_id=case_id,
        duplicate_case_found=duplicate_case_found,
        duplicate_check=duplicate_check,
    )

    event = _record_event(
        state={
            **state,
            "case_id": case_id,
            "case_state_snapshot": snapshot,
            "current_status": current_status,
        },
        node_name="duplicate_case_check",
        status=current_status,
        event_type="DUPLICATE_CASE_CHECK",
        result=event_result,
        note=note,
        case_state_snapshot=snapshot,
    )

    next_state = {
        **state,
        "case": case,
        "case_id": case_id,
        "duplicate_case_found": duplicate_case_found,
        "duplicate_check": duplicate_check,
        "current_node": "duplicate_case_check",
        "current_status": current_status,
        "case_state_snapshot": snapshot,
    }

    _upsert_business_case(next_state)

    return {
        "case": case,
        "case_id": case_id,
        "duplicate_case_found": duplicate_case_found,
        "duplicate_check": duplicate_check,
        "current_node": "duplicate_case_check",
        "current_status": current_status,
        "case_state_snapshot": snapshot,
        "node_trace": ["duplicate_case_check"],
        "case_timeline": [event],
        "audit_trail": [event],
    }


def resolve_duplicate_case_node(state: DisputeState) -> DisputeState:
    duplicate_check = state.get("duplicate_check", {})

    snapshot = _base_snapshot(
        state,
        resolution_type="duplicate_case",
        final_decision="Merged to existing case",
        duplicate_check=duplicate_check,
    )

    event = _record_event(
        state={
            **state,
            "case_state_snapshot": snapshot,
            "current_status": PENDING_CUSTOMER_COMMUNICATION,
        },
        node_name="resolve_duplicate_case",
        status=PENDING_CUSTOMER_COMMUNICATION,
        event_type="RESOLUTION_PREP",
        result="MERGED_TO_EXISTING_CASE",
        note="Duplicate intake resolved by merging into the existing open case.",
        case_state_snapshot=snapshot,
    )

    return {
        "resolution_type": "duplicate_case",
        "path": "MERGED_TO_EXISTING_CASE",
        "stp_result": None,
        "fraud_report": None,
        "policy_decision": "Existing open case found. Intake merged into existing case.",
        "human_review_required": False,
        "final_decision": "Merged to existing case",
        "accounting_action": "No new accounting action. Existing case remains active.",
        "current_node": "resolve_duplicate_case",
        "current_status": PENDING_CUSTOMER_COMMUNICATION,
        "case_state_snapshot": snapshot,
        "node_trace": ["resolve_duplicate_case"],
        "case_timeline": [event],
        "audit_trail": [event],
    }


def stp_evaluation_node(state: DisputeState) -> DisputeState:
    transaction = state["transaction"]
    dispute_type = state["dispute_type"]

    stp_result = evaluate_stp_eligibility(
        transaction=transaction,
        dispute_type=dispute_type,
    )

    if stp_result.get("stp_eligible"):
        current_status = PENDING_CUSTOMER_COMMUNICATION
        result = "STP_ELIGIBLE"
        note = "Case is eligible for straight-through processing."
    else:
        current_status = PENDING_INVESTIGATION
        result = "STP_NOT_ELIGIBLE"
        note = "Case is not eligible for STP and requires investigation."

    snapshot = _base_snapshot(
        state,
        stp_result=stp_result,
    )

    event = _record_event(
        state={
            **state,
            "case_state_snapshot": snapshot,
            "current_status": current_status,
        },
        node_name="stp_evaluation",
        status=current_status,
        event_type="STP_EVALUATION",
        result=result,
        note=note,
        case_state_snapshot=snapshot,
    )

    next_state = {
        **state,
        "stp_result": stp_result,
        "current_node": "stp_evaluation",
        "current_status": current_status,
        "case_state_snapshot": snapshot,
    }

    _upsert_business_case(next_state)

    return {
        "stp_result": stp_result,
        "current_node": "stp_evaluation",
        "current_status": current_status,
        "case_state_snapshot": snapshot,
        "node_trace": ["stp_evaluation"],
        "case_timeline": [event],
        "audit_trail": [event],
    }


def resolve_small_dollar_node(state: DisputeState) -> DisputeState:
    case = update_case_status(
        state["case"],
        PENDING_CUSTOMER_COMMUNICATION,
        "Small-dollar write-off approved. Customer communication pending.",
    )

    stp_result = state.get("stp_result", {})

    snapshot = _base_snapshot(
        state,
        case=case,
        resolution_type="small_dollar_writeoff",
        final_decision=stp_result.get("recommended_action", "Auto approve low-value write-off"),
    )

    event = _record_event(
        state={
            **state,
            "case": case,
            "case_state_snapshot": snapshot,
            "current_status": PENDING_CUSTOMER_COMMUNICATION,
        },
        node_name="resolve_small_dollar",
        status=PENDING_CUSTOMER_COMMUNICATION,
        event_type="RESOLUTION_PREP",
        result="SMALL_DOLLAR_WRITEOFF_APPROVED",
        note="Small-dollar write-off approved. Pending customer communication.",
        case_state_snapshot=snapshot,
    )

    next_state = {
        **state,
        "case": case,
        "resolution_type": "small_dollar_writeoff",
        "path": "AUTO_RESOLUTION",
        "human_review_required": False,
        "final_decision": stp_result.get("recommended_action", "Auto approve low-value write-off"),
        "policy_decision": stp_result.get("recommended_action"),
        "accounting_action": stp_result.get("accounting_action"),
        "current_node": "resolve_small_dollar",
        "current_status": PENDING_CUSTOMER_COMMUNICATION,
        "case_state_snapshot": snapshot,
    }

    _upsert_business_case(next_state)

    return {
        "case": case,
        "resolution_type": "small_dollar_writeoff",
        "path": "AUTO_RESOLUTION",
        "human_review_required": False,
        "final_decision": stp_result.get("recommended_action", "Auto approve low-value write-off"),
        "policy_decision": stp_result.get("recommended_action"),
        "accounting_action": stp_result.get("accounting_action"),
        "current_node": "resolve_small_dollar",
        "current_status": PENDING_CUSTOMER_COMMUNICATION,
        "case_state_snapshot": snapshot,
        "node_trace": ["resolve_small_dollar"],
        "case_timeline": [event],
        "audit_trail": [event],
    }


def pending_investigation_node(state: DisputeState) -> DisputeState:
    case = update_case_status(
        state["case"],
        PENDING_INVESTIGATION,
        "Case requires investigation / human review.",
    )

    transaction = state["transaction"]
    stp_result = state.get("stp_result", {})

    fraud_report = detect_fraud_risk(
        transaction_data=_transaction_to_text(transaction),
        customer_input=state.get("customer_input", ""),
    )

    policy_decision = analyze_dispute(
        customer_query=state.get("customer_input", ""),
        transaction_amount=transaction["amount"],
    )

    assignment = {
        "assigned_queue": "investigation_queue",
        "assigned_to": None,
        "assigned_at": _now(),
        "completed_by": None,
        "completed_at": None,
        "sla_due_at": None,
        "lock_owner": None,
        "lock_acquired_at": None,
        "lock_expires_at": None,
    }

    snapshot = _base_snapshot(
        state,
        case=case,
        fraud_report=fraud_report,
        policy_decision=policy_decision,
        assignment=assignment,
    )

    event = _record_event(
        state={
            **state,
            "case": case,
            "case_state_snapshot": snapshot,
            "current_status": PENDING_INVESTIGATION,
        },
        node_name="pending_investigation",
        status=PENDING_INVESTIGATION,
        event_type="ASSIGNMENT",
        result="ASSIGNED_TO_INVESTIGATION_QUEUE",
        note="Case routed to investigation queue.",
        assigned_queue="investigation_queue",
        case_state_snapshot=snapshot,
    )

    next_state = {
        **state,
        "case": case,
        "path": "INVESTIGATION",
        "fraud_report": fraud_report,
        "policy_decision": policy_decision,
        "human_review_required": True,
        "final_decision": "Pending Human Review",
        "accounting_action": stp_result.get("accounting_action"),
        "current_node": "pending_investigation",
        "current_status": PENDING_INVESTIGATION,
        "case_state_snapshot": snapshot,
    }

    _upsert_business_case(next_state)

    return {
        "case": case,
        "path": "INVESTIGATION",
        "fraud_report": fraud_report,
        "policy_decision": policy_decision,
        "human_review_required": True,
        "final_decision": "Pending Human Review",
        "accounting_action": stp_result.get("accounting_action"),
        "current_node": "pending_investigation",
        "current_status": PENDING_INVESTIGATION,
        "case_state_snapshot": snapshot,
        "node_trace": ["pending_investigation"],
        "case_timeline": [event],
        "audit_trail": [event],
    }


def customer_communication_node(state: DisputeState) -> DisputeState:
    transaction = state["transaction"]
    case = state["case"]
    resolution_type = state.get("resolution_type")

    if state.get("path") == "INVESTIGATION":
        email_payload = {
            "to": f"{_customer_name(transaction).replace(' ', '.').lower()}@demo-customer.com",
            "subject": f"Dispute Received for {transaction['transaction_id']}",
            "body": f"""
Dear {_customer_name(transaction)},

We have received your dispute and it is currently under investigation.

Transaction ID: {transaction['transaction_id']}
Merchant: {transaction['merchant']}
Amount: ${float(transaction['amount']):,.2f}
Date: {transaction['date']}

Current Status:
Pending Investigation

We will notify you once the review is completed.

Thank you,
Dispute Resolution Team
""",
            "status": "DRAFT",
            "generated_at": _now(),
        }

    elif resolution_type == "duplicate_case":
        email_payload = {
            "to": f"{_customer_name(transaction).replace(' ', '.').lower()}@demo-customer.com",
            "subject": f"Duplicate Dispute Intake for {transaction['transaction_id']}",
            "body": f"""
Dear {_customer_name(transaction)},

We found an existing open dispute related to this transaction.

Transaction ID: {transaction['transaction_id']}
Merchant: {transaction['merchant']}
Amount: ${float(transaction['amount']):,.2f}
Date: {transaction['date']}

Your new intake has been linked to the existing dispute case.

No new case was created.

Thank you,
Dispute Resolution Team
""",
            "status": "DRAFT",
            "generated_at": _now(),
        }

    else:
        email_payload = generate_resolution_email(
            customer_name=_customer_name(transaction),
            transaction=transaction,
            final_decision=state.get("final_decision", "Resolved"),
            reason=state.get("policy_decision") or state.get("final_decision") or "Resolution completed.",
        )

    insert_communication(case.get("case_id"), email_payload)

    snapshot = _base_snapshot(
        state,
        email_payload=email_payload,
    )

    event = _record_event(
        state={
            **state,
            "case_state_snapshot": snapshot,
            "current_status": PENDING_CUSTOMER_COMMUNICATION,
        },
        node_name="customer_communication",
        status=PENDING_CUSTOMER_COMMUNICATION,
        event_type="COMMUNICATION",
        result="CUSTOMER_EMAIL_GENERATED",
        note="Customer communication generated.",
        case_state_snapshot=snapshot,
    )

    next_state = {
        **state,
        "email_payload": email_payload,
        "current_node": "customer_communication",
        "current_status": PENDING_CUSTOMER_COMMUNICATION,
        "case_state_snapshot": snapshot,
    }

    _upsert_business_case(next_state)

    return {
        "email_payload": email_payload,
        "current_node": "customer_communication",
        "current_status": PENDING_CUSTOMER_COMMUNICATION,
        "case_state_snapshot": snapshot,
        "node_trace": ["customer_communication"],
        "case_timeline": [event],
        "audit_trail": [event],
    }


def close_case_node(state: DisputeState) -> DisputeState:
    resolution_type = state.get("resolution_type")

    if resolution_type == "duplicate_case":
        final_status = RESOLVED_DUPLICATE_CASE
        note = "Duplicate intake resolved by linking to existing case."
    elif resolution_type == "small_dollar_writeoff":
        final_status = RESOLVED_SMALL_DOLLAR_WRITEOFF
        note = "Case resolved through small-dollar write-off."
    else:
        final_status = RESOLVED_CUSTOMER_LIABILITY
        note = "Case resolved."

    # For duplicate intake, do not close the existing open case in cases.json.
    # The intake is resolved, but the existing case remains active.
    if resolution_type == "duplicate_case":
        case = state["case"]
    else:
        case = update_case_status(
            state["case"],
            final_status,
            note,
        )

    snapshot = _base_snapshot(
        state,
        case=case,
        final_status=final_status,
    )

    event = _record_event(
        state={
            **state,
            "case": case,
            "case_state_snapshot": snapshot,
            "current_status": final_status,
        },
        node_name="close_case",
        status=final_status,
        event_type="CLOSURE",
        result=final_status,
        note=note,
        case_state_snapshot=snapshot,
    )

    next_state = {
        **state,
        "case": case,
        "current_node": "close_case",
        "current_status": final_status,
        "case_state_snapshot": snapshot,
    }

    _upsert_business_case(next_state)

    return {
        "case": case,
        "current_node": "close_case",
        "current_status": final_status,
        "case_state_snapshot": snapshot,
        "node_trace": ["close_case"],
        "case_timeline": [event],
        "audit_trail": [event],
    }


# ============================================================
# Routing
# ============================================================

def route_after_duplicate_check(state: DisputeState) -> Literal["resolve_duplicate_case", "stp_evaluation"]:
    if state.get("duplicate_case_found"):
        return "resolve_duplicate_case"
    return "stp_evaluation"


def route_after_stp(state: DisputeState) -> Literal["resolve_small_dollar", "pending_investigation"]:
    stp_result = state.get("stp_result") or {}
    if stp_result.get("stp_eligible"):
        return "resolve_small_dollar"
    return "pending_investigation"


def route_after_communication(state: DisputeState) -> Literal["close_case", "__end__"]:
    # Pending investigation remains open.
    if state.get("path") == "INVESTIGATION":
        return "__end__"
    return "close_case"


# ============================================================
# Graph Assembly
# ============================================================

def build_graph():
    graph = StateGraph(DisputeState)

    graph.add_node("classify_dispute", classify_dispute_node)
    graph.add_node("duplicate_case_check", duplicate_case_check_node)
    graph.add_node("resolve_duplicate_case", resolve_duplicate_case_node)
    graph.add_node("stp_evaluation", stp_evaluation_node)
    graph.add_node("resolve_small_dollar", resolve_small_dollar_node)
    graph.add_node("pending_investigation", pending_investigation_node)
    graph.add_node("customer_communication", customer_communication_node)
    graph.add_node("close_case", close_case_node)

    graph.add_edge(START, "classify_dispute")
    graph.add_edge("classify_dispute", "duplicate_case_check")

    graph.add_conditional_edges(
        "duplicate_case_check",
        route_after_duplicate_check,
        {
            "resolve_duplicate_case": "resolve_duplicate_case",
            "stp_evaluation": "stp_evaluation",
        },
    )

    graph.add_edge("resolve_duplicate_case", "customer_communication")

    graph.add_conditional_edges(
        "stp_evaluation",
        route_after_stp,
        {
            "resolve_small_dollar": "resolve_small_dollar",
            "pending_investigation": "pending_investigation",
        },
    )

    graph.add_edge("resolve_small_dollar", "customer_communication")
    graph.add_edge("pending_investigation", "customer_communication")

    graph.add_conditional_edges(
        "customer_communication",
        route_after_communication,
        {
            "close_case": "close_case",
            "__end__": END,
        },
    )

    graph.add_edge("close_case", END)

    return graph


def compile_graph():
    with PostgresSaver.from_conn_string(POSTGRES_URI) as checkpointer:
        return build_graph().compile(checkpointer=checkpointer)


# ============================================================
# Public Runner
# ============================================================

def run_langgraph_dispute_agent(transaction, customer_input, checkbox_data, region="TX"):
    transaction_dict = _transaction_to_dict(transaction)

    thread_id = f"dispute-{transaction_dict['transaction_id']}"

    initial_state: DisputeState = {
        "transaction": transaction_dict,
        "customer_input": customer_input,
        "checkbox_data": checkbox_data,
        "region": region,
        "thread_id": thread_id,
        "current_status": PENDING_CLASSIFICATION,
        "current_node": "START",
        "case_state_snapshot": {
            "transaction": transaction_dict,
            "customer_input": customer_input,
            "checkbox_data": checkbox_data,
            "region": region,
            "created_at": _now(),
        },
        "node_trace": [],
        "case_timeline": [],
        "audit_trail": [],
    }

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    with PostgresSaver.from_conn_string(POSTGRES_URI) as checkpointer:
        app = build_graph().compile(checkpointer=checkpointer)
        final_state = app.invoke(initial_state, config=config)

    return {
        "case": final_state.get("case"),
        "case_id": final_state.get("case_id"),
        "duplicate_case_found": final_state.get("duplicate_case_found", False),
        "duplicate_check": final_state.get("duplicate_check"),
        "region": final_state.get("region", region),
        "dispute_type": final_state.get("dispute_type"),
        "questionnaire": final_state.get("questionnaire"),
        "path": final_state.get("path"),
        "stp_result": final_state.get("stp_result"),
        "fraud_report": final_state.get("fraud_report"),
        "policy_decision": final_state.get("policy_decision"),
        "human_review_required": final_state.get("human_review_required", False),
        "final_decision": final_state.get("final_decision"),
        "accounting_action": final_state.get("accounting_action"),
        "email_payload": final_state.get("email_payload"),
        "current_status": final_state.get("current_status"),
        "current_node": final_state.get("current_node"),
        "case_state_snapshot": final_state.get("case_state_snapshot"),
        "node_trace": final_state.get("node_trace", []),
        "case_timeline": final_state.get("case_timeline", []),
        "audit_trail": final_state.get("audit_trail", []),
        "thread_id": thread_id,
    }


# ============================================================
# Checkpoint / State History Helper
# ============================================================

def get_langgraph_state_history(thread_id: str):
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    with PostgresSaver.from_conn_string(POSTGRES_URI) as checkpointer:
        app = build_graph().compile(checkpointer=checkpointer)
        history = list(app.get_state_history(config))

    return history