import os
from dotenv import load_dotenv
from openai import OpenAI
import chromadb
from chromadb.utils import embedding_functions

# Initialize environment and keys
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Set up OpenAI Client
client_ai = OpenAI(api_key=api_key)

# Connect to the existing Vector Database (ChromaDB)
client_db = chromadb.PersistentClient(path="./chroma_db")
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=api_key,
    model_name="text-embedding-3-small"
)
collection = client_db.get_or_create_collection(
    name="bank_policies", 
    embedding_function=openai_ef
)

def analyze_dispute(customer_query, transaction_amount):
    """
    Processes a dispute claim by retrieving relevant policy and reasoning with an LLM.
    
    Args:
        customer_query (str): The reason provided by the customer for the dispute.
        transaction_amount (float): The dollar value of the transaction.
        
    Returns:
        str: The AI-generated decision recommendation.
    """
    
    # 1. RETRIEVAL: Find relevant bank policy sections using semantic search
    results = collection.query(
        query_texts=[customer_query],
        n_results=1  # Get the single most relevant policy section
    )
    relevant_policy = results['documents'][0]

    # 2. PROMPT ENGINEERING: Ground the AI in specific facts and policies
    system_prompt = f"""
    You are an expert Bank Dispute Resolution Officer.
    Your task is to decide if a claim should be 'Approved' or 'Denied' based on the policy below.
    
    【BANK POLICY】:
    {relevant_policy}
    
    【TRANSACTION DATA】:
    Amount: ${transaction_amount}
    """

    # 3. GENERATION: Call GPT-4o to make a reasoned decision
    response = client_ai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Customer Claim: {customer_query}"}
        ]
    )

    return response.choices[0].message.content