import streamlit as st
import pandas as pd

from langgraph_agent import run_langgraph_dispute_agent, get_langgraph_state_history
from questionnaire import classify_dispute_type, get_questionnaire
from email_service import send_email_mock
from case_service import update_case_status


# =====================================================
# Lifecycle Definition
# =====================================================

LIFECYCLE_STAGES = [
    {
        "key": "intake",
        "label": "Intake",
        "nodes": ["classify_dispute"],
        "statuses": ["PENDING_CLASSIFICATION", "PENDING_DUPLICATE_CHECK"],
    },
    {
        "key": "duplicate",
        "label": "Duplicate Check",
        "nodes": ["duplicate_case_check", "resolve_duplicate_case"],
        "statuses": ["PENDING_DUPLICATE_CHECK", "RESOLVED_DUPLICATE_CASE"],
    },
    {
        "key": "stp",
        "label": "STP Evaluation",
        "nodes": ["stp_evaluation", "resolve_small_dollar"],
        "statuses": ["PENDING_STP_EVALUATION", "RESOLVED_SMALL_DOLLAR_WRITEOFF"],
    },
    {
        "key": "investigation",
        "label": "Investigation",
        "nodes": ["pending_investigation"],
        "statuses": ["PENDING_INVESTIGATION"],
    },
    {
        "key": "communication",
        "label": "Communication",
        "nodes": ["customer_communication"],
        "statuses": ["PENDING_CUSTOMER_COMMUNICATION"],
    },
    {
        "key": "resolution",
        "label": "Resolution",
        "nodes": ["close_case"],
        "statuses": [
            "RESOLVED_DUPLICATE_CASE",
            "RESOLVED_SMALL_DOLLAR_WRITEOFF",
            "RESOLVED_CUSTOMER_LIABILITY",
        ],
    },
]


def get_stage_status(stage, current_status, node_trace):
    if current_status in stage["statuses"]:
        return "current"

    if any(node in node_trace for node in stage["nodes"]):
        return "done"

    if current_status and current_status.startswith("RESOLVED") and stage["key"] == "resolution":
        return "current"

    return "pending"


def render_lifecycle_tracker(result):
    current_status = result.get("current_status")
    node_trace = result.get("node_trace", [])

    st.markdown("### Case Lifecycle")

    cols = st.columns(len(LIFECYCLE_STAGES))

    for i, stage in enumerate(LIFECYCLE_STAGES):
        stage_state = get_stage_status(stage, current_status, node_trace)

        with cols[i]:
            if stage_state == "current":
                st.success(f"▶ {stage['label']}")
            elif stage_state == "done":
                st.info(f"✓ {stage['label']}")
            else:
                st.caption(f"○ {stage['label']}")

    st.caption(f"Current Status: `{current_status}`")


def render_stage_details(result):
    st.markdown("### Stage Details")

    timeline = result.get("case_timeline", [])
    snapshot = result.get("case_state_snapshot", {})

    for stage in LIFECYCLE_STAGES:
        matching_events = [
            event for event in timeline
            if event.get("node_name") in stage["nodes"]
        ]

        with st.expander(stage["label"], expanded=bool(matching_events)):
            if not matching_events:
                st.caption("No activity recorded for this stage yet.")
                continue

            for event in matching_events:
                st.markdown(f"**Status:** `{event.get('status')}`")
                st.write(f"**Node:** `{event.get('node_name')}`")
                st.write(f"**Result:** `{event.get('result')}`")
                if event.get("note"):
                    st.write(event.get("note"))
                if event.get("assigned_queue"):
                    st.write(f"**Assigned Queue:** `{event.get('assigned_queue')}`")
                if event.get("created_at"):
                    st.caption(event.get("created_at"))
                st.divider()

            if stage["key"] == "duplicate":
                st.markdown("**Duplicate Check Snapshot**")
                st.json(snapshot.get("duplicate_check", {}))

            if stage["key"] == "stp":
                st.markdown("**STP Snapshot**")
                st.json(snapshot.get("stp_result", {}))

            if stage["key"] == "investigation":
                st.markdown("**Investigation Snapshot**")
                st.json({
                    "fraud_report": snapshot.get("fraud_report"),
                    "policy_decision": snapshot.get("policy_decision"),
                    "assignment": snapshot.get("assignment"),
                })

            if stage["key"] == "communication":
                st.markdown("**Communication Snapshot**")
                st.json(snapshot.get("email_payload", {}))


def render_audit_timeline(case_timeline):
    if not case_timeline:
        st.info("No audit history available.")
        return

    for event in case_timeline:
        with st.container(border=True):
            st.markdown(f"**{event.get('status')}**")
            st.caption(
                f"Node: `{event.get('node_name')}` | "
                f"Type: `{event.get('event_type')}` | "
                f"Result: `{event.get('result')}`"
            )
            if event.get("note"):
                st.write(event.get("note"))
            if event.get("assigned_queue"):
                st.write(f"Assigned Queue: `{event.get('assigned_queue')}`")
            if event.get("created_at"):
                st.caption(event.get("created_at"))


def render_checkpoint_history(thread_id):
    if not thread_id:
        st.info("No thread id available.")
        return

    try:
        history = get_langgraph_state_history(thread_id)
        st.write(f"Checkpoint count: **{len(history)}**")

        for i, checkpoint in enumerate(history, start=1):
            with st.expander(f"Checkpoint {i}", expanded=False):
                st.write(checkpoint)
    except Exception as e:
        st.error(f"Unable to load checkpoint history: {e}")


# =====================================================
# Page Setup
# =====================================================

st.set_page_config(
    page_title="ADRA - Automated Dispute Resolution Agent",
    layout="wide"
)

st.title("🏦 ADRA: Automated Dispute Resolution Agent")
st.caption(
    "Dynamic Intake → LangGraph Case Lifecycle → Audit History → Case State Snapshot → Checkpoint Recovery"
)


try:
    df = pd.read_csv("data/transactions.csv")
except FileNotFoundError:
    st.error("data/transactions.csv not found. Please run `python src/gen_data.py` first.")
    st.stop()


# =====================================================
# Sidebar
# =====================================================

st.sidebar.header("Customer Portal")

df["display_label"] = (
    df["transaction_id"] + " | "
    + df["merchant"] + " | $"
    + df["amount"].round(2).astype(str) + " | "
    + df["date"] + " | ["
    + df["status"] + "]"
)

selected_label = st.sidebar.selectbox(
    "Choose a transaction to dispute:",
    df["display_label"]
)

selected_txn = df[df["display_label"] == selected_label].iloc[0]
customer_name = selected_txn.get("customer_name", selected_txn["customer_id"])

st.sidebar.write("---")
st.sidebar.success(f"Welcome, {customer_name}")
st.sidebar.write(f"**Transaction:** {selected_txn['transaction_id']}")
st.sidebar.write(f"**Merchant:** {selected_txn['merchant']}")
st.sidebar.write(f"**Amount:** ${float(selected_txn['amount']):,.2f}")
st.sidebar.write(f"**Date:** {selected_txn['date']}")
st.sidebar.info(f"**Status:** {selected_txn['status']}")


# =====================================================
# Session State
# =====================================================

if "agent_result" not in st.session_state:
    st.session_state.agent_result = None

if "email_payload" not in st.session_state:
    st.session_state.email_payload = None

if "case_closed" not in st.session_state:
    st.session_state.case_closed = False


# =====================================================
# Main Layout
# =====================================================

col1, col2, col3 = st.columns([1.0, 1.4, 1.1])


# =====================================================
# Column 1: Intake
# =====================================================

with col1:
    st.subheader("1. Intake")

    region = st.selectbox(
        "Region / State",
        ["TX", "CA", "NY", "FL", "IL", "GA"],
        key="region"
    )

    region_badge = {
        "TX": "Standard Review",
        "CA": "Enhanced Consumer Protection",
        "NY": "Regulatory Sensitive",
        "FL": "Standard Review",
        "IL": "Standard Review",
        "GA": "Standard Review"
    }

    st.caption(f"Routing: **{region_badge[region]}**")

    selected_issue = st.radio(
        "Primary dispute type",
        [
            "Duplicate charge",
            "Unauthorized / fraud",
            "Service not provided",
            "Incorrect amount",
            "Goods not received",
            "Other"
        ],
        key="selected_issue"
    )

    fact_col1, fact_col2 = st.columns(2)

    with fact_col1:
        contacted_merchant = st.checkbox("Contacted merchant")
        has_evidence = st.checkbox("Has evidence")

    with fact_col2:
        has_receipt = st.checkbox("Has receipt")
        wants_callback = st.checkbox("Needs callback")

    checkbox_data = {
        "charged_twice": selected_issue == "Duplicate charge",
        "not_authorized": selected_issue == "Unauthorized / fraud",
        "service_not_received": selected_issue == "Service not provided",
        "wrong_amount": selected_issue == "Incorrect amount",
        "goods_not_received": selected_issue == "Goods not received",
        "contacted_merchant": contacted_merchant,
        "has_evidence": has_evidence,
        "has_receipt": has_receipt,
        "wants_callback": wants_callback
    }

    default_reason_map = {
        "Duplicate charge": f"I am disputing this charge from {selected_txn['merchant']} because I was billed twice for the same item.",
        "Unauthorized / fraud": f"I did not authorize this transaction from {selected_txn['merchant']}.",
        "Service not provided": f"The service from {selected_txn['merchant']} was not provided.",
        "Incorrect amount": f"I was charged the wrong amount by {selected_txn['merchant']}.",
        "Goods not received": f"I did not receive the goods I purchased from {selected_txn['merchant']}.",
        "Other": f"I have a concern about this transaction from {selected_txn['merchant']}."
    }

    customer_input = st.text_area(
        "Customer explanation",
        value=default_reason_map[selected_issue],
        height=90,
        key=f"customer_input_{selected_issue}"
    )

    detected_dispute_type = classify_dispute_type(
        customer_input=customer_input,
        checkbox_data=checkbox_data
    )

    dynamic_questions = get_questionnaire(detected_dispute_type)

    st.info(f"Detected: `{detected_dispute_type}`")

    questionnaire_answers = {}

    with st.expander("Dynamic follow-up questions", expanded=False):
        for i, question in enumerate(dynamic_questions, start=1):
            questionnaire_answers[question] = st.text_input(
                f"Q{i}: {question}",
                key=f"{detected_dispute_type}_q_{i}"
            )

    checkbox_data["questionnaire_answers"] = questionnaire_answers

    if st.button("Run LangGraph Workflow", use_container_width=True):
        with st.spinner("Running LangGraph workflow..."):
            st.session_state.agent_result = run_langgraph_dispute_agent(
                transaction=selected_txn,
                customer_input=customer_input,
                checkbox_data=checkbox_data,
                region=region
            )
            st.session_state.email_payload = st.session_state.agent_result.get("email_payload")
            st.session_state.case_closed = False


# =====================================================
# Column 2: Case Lifecycle
# =====================================================

with col2:
    st.subheader("2. Case Lifecycle")

    result = st.session_state.agent_result

    if not result:
        st.info("Complete intake and run the workflow.")
    else:
        case = result.get("case") or {}

        render_lifecycle_tracker(result)
        render_stage_details(result)

        st.markdown("### Case Summary")

        current_status = result.get("current_status")

        if current_status and current_status.startswith("RESOLVED"):
            st.success(f"Current Status: `{current_status}`")
        elif current_status:
            st.warning(f"Current Status: `{current_status}`")
        else:
            st.info("Current status unavailable.")

        st.write(f"**Case ID:** {case.get('case_id', result.get('case_id'))}")
        st.write(f"**Transaction ID:** {case.get('transaction_id', selected_txn['transaction_id'])}")
        st.write(f"**Dispute Type:** `{result.get('dispute_type')}`")
        st.write(f"**Workflow Path:** `{result.get('path')}`")
        st.write(f"**Thread ID:** `{result.get('thread_id')}`")


# =====================================================
# Column 3: Review / Communication
# =====================================================

with col3:
    st.subheader("3. Communication & Work Status")

    result = st.session_state.agent_result

    if not result:
        st.info("No active case yet.")
    else:
        current_status = result.get("current_status")
        email_payload = st.session_state.email_payload or result.get("email_payload")

        st.markdown("### Work Object Summary")
        st.write(f"**Current Node:** `{result.get('current_node')}`")
        st.write(f"**Current Status:** `{current_status}`")
        st.write(f"**Human Review Required:** `{result.get('human_review_required')}`")
        st.write(f"**Final Decision:** {result.get('final_decision')}")
        st.write(f"**Accounting Action:** {result.get('accounting_action')}")

        if result.get("path") == "INVESTIGATION":
            st.markdown("### Human Review Simulation")

            reviewer_decision = st.radio(
                "Final decision",
                [
                    "Approve - Customer Not Liable",
                    "Deny - Customer Liable",
                    "Request More Evidence",
                    "Escalate to Special Review"
                ],
                key="reviewer_decision"
            )

            reviewer_notes = st.text_area(
                "Reviewer notes",
                value="Reviewed AI recommendation, risk indicators, policy guidance, and submitted evidence.",
                height=80
            )

            if st.button("Submit Review", use_container_width=True):
                result["final_decision"] = reviewer_decision
                result["reviewer_notes"] = reviewer_notes
                result["case"] = update_case_status(
                    result["case"],
                    "PENDING_CUSTOMER_COMMUNICATION",
                    "Human reviewer submitted final review decision."
                )
                st.session_state.agent_result = result
                st.success("Human review submitted.")

        st.markdown("### Customer Communication")

        if email_payload:
            with st.expander("Email Preview", expanded=True):
                st.write(f"**To:** {email_payload.get('to')}")
                st.write(f"**Subject:** {email_payload.get('subject')}")
                st.text_area(
                    "Body",
                    email_payload.get("body", ""),
                    height=170
                )

            if email_payload.get("status") != "SENT":
                if st.button("Mock Send Email", use_container_width=True):
                    st.session_state.email_payload = send_email_mock(email_payload)
                    st.success("Mock email sent.")
            else:
                st.success("Email sent.")
        else:
            st.info("No communication generated yet.")

        if current_status and current_status.startswith("RESOLVED"):
            st.success("Case is resolved.")
        elif result.get("path") == "INVESTIGATION":
            st.warning("Case remains open in investigation.")
        else:
            st.info("Case is active.")


# =====================================================
# Bottom Tabs
# =====================================================

if st.session_state.agent_result:
    st.divider()

    result = st.session_state.agent_result

    tab1, tab2, tab3, tab4 = st.tabs([
        "Case Audit History",
        "Case State Snapshot",
        "Technical Audit Trail",
        "LangGraph Checkpoints"
    ])

    with tab1:
        st.subheader("Case Audit History")
        render_audit_timeline(result.get("case_timeline", []))

    with tab2:
        st.subheader("Case State Snapshot")
        st.caption("Workflow state snapshot, similar to a case clipboard/page snapshot.")
        st.json(result.get("case_state_snapshot", {}))

    with tab3:
        st.subheader("Technical Audit Trail")
        st.json(result.get("audit_trail", []))

    with tab4:
        st.subheader("LangGraph Checkpoint History")
        st.caption("Technical checkpoint snapshots stored in PostgreSQL.")
        if st.button("Load Checkpoint History", use_container_width=True):
            render_checkpoint_history(result.get("thread_id"))


st.markdown("---")
st.caption(
    "ADRA Demo | OpenAI + ChromaDB + Streamlit + LangGraph + Neon Postgres + Case Audit History"
)