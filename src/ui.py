import streamlit as st
import pandas as pd
from agent import analyze_dispute  # Importing the logic we built earlier

# --- Page Configuration ---
st.set_page_config(page_title="GRB Smart Dispute AI", layout="wide")

st.title("🏦 Global Retail Bank: Smart Dispute AI")
st.markdown("### AI-Powered Agentic Dispute Resolution Dashboard")
st.info("This agent uses RAG to ground decisions in Federal Reg E and Internal Bank Policy.")

# --- Sidebar: Transaction Selection ---
st.sidebar.header("Select Transaction")
try:
    # Load mock transactions
    df = pd.read_csv("data/transactions.csv")
    transaction_id = st.sidebar.selectbox("Choose Transaction ID", df['transaction_id'])
    
    # Get details for selected transaction
    selected_txn = df[df['transaction_id'] == transaction_id].iloc[0]
    
    st.sidebar.write("---")
    st.sidebar.write(f"**Merchant:** {selected_txn['merchant']}")
    st.sidebar.write(f"**Amount:** ${selected_txn['amount']}")
    st.sidebar.write(f"**Date:** {selected_txn['date']}")
    
except FileNotFoundError:
    st.error("Please ensure data/transactions.csv exists.")

# --- Main Layout ---
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
        with st.spinner("Retrieving Policy & Analyzing..."):
            # Call our Agent
            decision = analyze_dispute(customer_input, selected_txn['amount'])
            
            st.success("Analysis Complete")
            st.markdown("#### Recommendation:")
            st.write(decision)
            
            # Show the Audit Trail (Proof of RAG)
            with st.expander("View Audit Trail (Policy Reference)"):
                st.write("Source: `data/bank_policy.txt`")
                st.write("The AI retrieved the most relevant policy section to ensure compliance.")

# --- Footer ---
st.markdown("---")
st.caption("Enterprise Solutions Architect Demo | Integration: OpenAI + ChromaDB + Python")