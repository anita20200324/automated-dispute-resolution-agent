import os
from dotenv import load_dotenv
from openai import OpenAI
import chromadb
from chromadb.utils import embedding_functions

# --- Initialize environment and keys ---
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Set up OpenAI Client
client_ai = OpenAI(api_key=api_key)

# --- Connect to the existing Vector Database (ChromaDB) ---
client_db = chromadb.PersistentClient(path="./chroma_db")
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=api_key,
    model_name="text-embedding-3-small"
)
collection = client_db.get_or_create_collection(
    name="bank_policies", 
    embedding_function=openai_ef
)

# --- FIXED: Fraud Detection Function (Step 1) ---
def detect_fraud_risk(transaction_data, customer_input):
    """
    Analyzes transaction patterns for risk before checking policy.
    Now checks for Serial Disputers and Velocity Attacks.
    """
    # We put the prompt INSIDE the function so it can use the variables
    fraud_prompt = f"""
    You are a Fraud Detection Expert. Identify if this is a 'Serial Disputer' or 'Velocity Attack'.
    
    【Transaction Data】: {transaction_data}
    【Customer Claim】: {customer_input}

    Check for these Red Flags:
    1. Is the amount unusually high (e.g., a $5,000 spike)?
    2. Is the user mentioning 'multiple', 'all', or 'other' charges?
    3. Does the transaction status suggest an ongoing attack?

    Output Format:
    Risk Level: [Low/Medium/High]
    Reason: [Short explanation in English]
    """

    response = client_ai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": fraud_prompt}]
    )
    return response.choices[0].message.content

# --- EXISTING: Dispute Analysis Function (Step 2) ---
def analyze_dispute(customer_query, transaction_amount):
    """
    Processes a dispute claim by retrieving relevant policy and reasoning with an LLM.
    """
    # 1. RETRIEVAL: Find relevant bank policy sections
    results = collection.query(
        query_texts=[customer_query],
        n_results=1 
    )
    relevant_policy = results['documents'][0]

    # 2. PROMPT ENGINEERING
    system_prompt = f"""
    You are an expert Bank Dispute Resolution Officer.
    Decide if a claim is 'Approved' or 'Denied' based on the policy below.
    
    【BANK POLICY】:
    {relevant_policy}
    
    【TRANSACTION DATA】:
    Amount: ${transaction_amount}
    """

    # 3. GENERATION
    response = client_ai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Customer Claim: {customer_query}"}
        ]
    )

    return response.choices[0].message.content