import streamlit as st
import pandas as pd
from agent import analyze_dispute, detect_fraud_risk 

# --- Page Configuration ---
st.set_page_config(page_title="GRB Smart Dispute AI", layout="wide")

st.title("🏦 Global Retail Bank: Smart Dispute AI")
st.markdown("### AI-Powered Agentic Dispute Resolution Dashboard")
st.info("Multi-stage pipeline: Fraud Screening followed by RAG-based Policy Compliance.")

# --- Sidebar & Data Loading ---
st.sidebar.header("Bank Portal: My Activity")

try:
    df = pd.read_csv("data/transactions.csv")
    
    # Create the detailed label for the dropdown
    df['display_label'] = (
        df['transaction_id'] + " | " + 
        df['merchant'] + " | $" + 
        df['amount'].astype(str) + " | " + 
        df['date'] + " | [" + 
        df['status'] + "]"
    )
    
    label_to_id = dict(zip(df['display_label'], df['transaction_id']))
    selected_label = st.sidebar.selectbox("Choose a transaction to dispute:", df['display_label'])
    
    # Get details
    transaction_id = label_to_id[selected_label]
    selected_txn = df[df['transaction_id'] == transaction_id].iloc[0]
    
    # Sidebar Display
    st.sidebar.write("---")
    st.sidebar.success(f"👋 **Welcome, {selected_txn['customer_name']}**")
    
    st.sidebar.write("### Transaction Details")
    st.sidebar.write(f"**ID:** {selected_txn['transaction_id']}")
    st.sidebar.write(f"**Merchant:** {selected_txn['merchant']}")
    st.sidebar.write(f"**Amount:** ${selected_txn['amount']}")
    st.sidebar.write(f"**Date:** {selected_txn['date']}")
    
    if selected_txn['status'] == "Disputed":
        st.sidebar.error(f"**Status:** {selected_txn['status']}")
    elif selected_txn['status'] == "Pending":
        st.sidebar.warning(f"**Status:** {selected_txn['status']}")
    else:
        st.sidebar.info(f"**Status:** {selected_txn['status']}")

    # --- Main Layout (Inside Try to ensure selected_txn exists) ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Customer Claim")
        customer_input = st.text_area(
            "Enter customer's dispute reason:", 
            value=f"I am disputing this charge from {selected_txn['merchant']} because I was billed twice for the same item."
        )
        analyze_button = st.button("🚀 Analyze Dispute with AI")

    with col2:
        st.subheader("AI Decision Engine")
        if analyze_button:
            # STEP 1: Fraud Risk Assessment
            with st.spinner("Step 1: Running Fraud Risk Assessment..."):
                # Pass transaction as string + customer claim
                fraud_report = detect_fraud_risk(selected_txn.to_string(), customer_input)
                
                st.markdown("#### 🛡️ Fraud Screening Result")
                if "High" in fraud_report:
                    st.error(fraud_report)
                elif "Medium" in fraud_report:
                    st.warning(fraud_report)
                else:
                    st.success(fraud_report)
            
            st.divider()

            # STEP 2: Regulatory Policy Analysis (RAG)
            with st.spinner("Step 2: Retrieving Policy & Analyzing Compliance..."):
                decision = analyze_dispute(customer_input, selected_txn['amount'])
                
                st.success("Step 2: Analysis Complete")
                st.markdown("#### ⚖️ Final Recommendation:")
                st.write(decision)
                
                with st.expander("View Audit Trail (Policy Reference)"):
                    st.write("Source: `data/bank_policy.txt`")
                    st.info("The AI retrieved the most relevant policy section to ensure compliance.")

except FileNotFoundError:
    st.error("⚠️ Error: `data/transactions.csv` not found. Please run your data generation script first.")
except Exception as e:
    st.error(f"⚠️ An unexpected error occurred: {e}")

# --- Footer ---
st.markdown("---")
st.caption("Enterprise Solutions Architect Demo | Integration: OpenAI + ChromaDB + Python")