# automated-dispute-resolution-agent
Automated Dispute Resolution Agent (ADRA)
📌 Project Overview
ADRA is an enterprise-grade Agentic RAG (Retrieval-Augmented Generation) system designed to automate complex financial dispute workflows. Traditionally handled by legacy BPM platforms (like Pega), this project demonstrates how to modernize dispute resolution using Large Language Models (LLMs) grounded in real-world regulatory data.

By integrating Reg E (Federal Regulation E) and Card Network Rules (VCR/MCOM) into a vector database, ADRA provides automated, audit-ready decisions for credit/debit card disputes while significantly reducing manual triage.

🏗 Architecture
The system follows a modular "Chain of Thought" architecture:

Ingestion Layer: Converts unstructured bank policy PDFs/Text into high-dimensional vectors.

Knowledge Retrieval (RAG): Uses ChromaDB to perform semantic searches for relevant clauses (e.g., "Low-value write-off rules").

Reasoning Agent: An LLM-based agent (GPT-4o) that synthesizes transactional data + retrieved policies to output a structured JSON decision.

Governance Layer: Implements specific guardrails to ensure compliance with financial deadlines and data privacy.

🚀 Key Features
Policy-Grounded Decisioning: Eliminates AI hallucinations by forcing the model to cite specific sections of the bank’s internal handbook.

Structured Output for BPM Integration: Outputs decisions in JSON format, making it compatible with legacy systems like Pega, Salesforce, or custom ERPs.

Fintech Domain Logic: Built-in understanding of Regulation E, Provisional Credit timelines, and STP (Straight-Through Processing) thresholds.

Cost-Optimized Architecture: Utilizes semantic chunking and efficient embedding models to minimize API token consumption.

🛠 Tech Stack
Orchestration: Python, LangChain

LLM API: OpenAI (GPT-4o) / AWS Bedrock (Claude 3.5)

Vector Database: ChromaDB

Embeddings: OpenAI text-embedding-3-small

UI/Interface: Streamlit
