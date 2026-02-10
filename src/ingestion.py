import os
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

# Load environment variables (API Keys)
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

def ingest_policies():
    """
    Reads bank policy documents, chunks them, and stores them in ChromaDB.
    This enables the AI to 'remember' specific banking regulations.
    """
    if not api_key:
        print("❌ Error: OPENAI_API_KEY not found in .env file.")
        return

    # Initialize persistent storage for the vector database
    client = chromadb.PersistentClient(path="./chroma_db")

    # Define the embedding model (converts text to numerical vectors)
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name="text-embedding-3-small"
    )

    # Create or connect to the collection
    collection = client.get_or_create_collection(
        name="bank_policies", 
        embedding_function=openai_ef
    )

    try:
        # Load the raw policy text file
        with open("data/bank_policy.txt", "r", encoding="utf-8") as f:
            policy_text = f.read()

        # Split policy into chunks based on double newlines (logical sections)
        chunks = [c.strip() for c in policy_text.split("\n\n") if c.strip()]

        # Upsert (Update or Insert) chunks into the database
        collection.upsert(
            documents=chunks,
            ids=[f"id_{i}" for i in range(len(chunks))]
        )

        print(f"✅ Success: Ingested {len(chunks)} policy sections.")
        
    except FileNotFoundError:
        print("❌ Error: File 'data/bank_policy.txt' not found.")

if __name__ == "__main__":
    ingest_policies()