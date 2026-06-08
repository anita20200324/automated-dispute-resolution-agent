# Automated Dispute Resolution Agent (ADRA)

## Project Overview

ADRA is an AI-assisted dispute resolution platform designed to automate complex case-management workflows through a combination of Retrieval-Augmented Generation (RAG), workflow orchestration, structured decisioning, and human-in-the-loop review.

The platform demonstrates how modern AI systems can support dispute intake, policy retrieval, duplicate detection, resolution recommendations, investigation routing, customer communication, and future workflow recovery capabilities.

ADRA combines deterministic business rules with AI reasoning to create transparent, auditable, and explainable decisions.

---

## Current Capabilities

### Customer Intake

* Interactive dispute intake experience
* Transaction selection
* Customer explanation capture
* Dynamic follow-up questionnaire generation

### Knowledge Retrieval

* Policy document ingestion
* Semantic search
* ChromaDB vector storage
* Context-aware policy retrieval

### Decision Support

* Duplicate case detection
* Straight-through processing (STP) evaluation
* Resolution recommendation generation
* Structured JSON decision output

### Customer Communication

* Automated customer correspondence generation
* Resolution messaging
* Investigation notifications

### User Experience

* Streamlit-based user interface
* Audit trail visibility
* Decision transparency
* Workflow visualization

---

## Architecture

### Layer 1 – User Interaction

* Streamlit UI
* Customer Intake
* Dynamic Questionnaire

### Layer 2 – Agent Layer

* Intent Analysis
* Question Generation
* Decision Recommendation

### Layer 3 – Knowledge Layer

* Policy Ingestion
* Embeddings
* ChromaDB
* Retrieval-Augmented Generation (RAG)

### Layer 4 – Decision Layer

* Duplicate Detection
* STP Evaluation
* Resolution Recommendation
* Investigation Routing

### Layer 5 – Communication Layer

* Customer Notifications
* Resolution Correspondence
* Investigation Updates

---

## Current Development Focus

### MVP 1 – LangGraph Workflow Refactor

The current sprint focuses on converting the workflow into a stateful LangGraph architecture.

Goals include:

* Workflow state management
* Node trace visualization
* Human-in-the-loop routing
* Unified customer communication
* Duplicate case handling
* Small-dollar resolution workflow

---

## Planned Roadmap

### MVP 2 – Workflow Checkpoint & Replay

* Checkpoint persistence
* State history
* Replay
* Time-travel debugging
* Workflow recovery

### MVP 3 – Duplicate Transaction Validation

* Merchant matching
* Amount matching
* Time-window validation
* Duplicate transaction analysis

### MVP 4 – Investigation Lifecycle

* Investigation queue
* Review workflow
* Escalation routing
* Resolution lifecycle

### MVP 5 – Persistence Layer

* Durable case storage
* Communication history
* Repository-backed lookups
* Workflow state persistence

### MVP 6 – Advanced Agent Reasoning

* Multi-agent workflows
* Enhanced decision support
* Expanded policy retrieval
* Advanced recommendation logic

---

## Technology Stack

### Application

* Python
* Streamlit

### AI

* OpenAI Models
* Retrieval-Augmented Generation (RAG)

### Vector Database

* ChromaDB

### Data Processing

* Embeddings
* Semantic Search
* Policy Chunking

### Workflow Orchestration

* LangGraph (in progress)

### Future Components

* PostgreSQL
* FastAPI
* Durable Checkpoint Storage

---

## Getting Started

### Install Dependencies

```bash
pip install openai chromadb python-dotenv streamlit pandas
```

### Configure Environment

Create a `.env` file:

```text
OPENAI_API_KEY=your_api_key
```

### Build Vector Database

```bash
python src/ingestion.py
```

Expected output:

```text
Success: policy documents ingested.
```

### Launch Application

```bash
streamlit run src/ui.py
```

---

## Example Workflow

1. Select a transaction
2. Enter customer dispute explanation
3. Generate dynamic follow-up questions
4. Retrieve relevant policy guidance
5. Evaluate duplicate conditions
6. Run STP decision engine
7. Generate recommendation
8. Produce customer communication
9. Record audit trail

---

## Current Sprint Goal

Complete MVP 1 by demonstrating:

* LangGraph workflow execution
* Node trace visibility
* Duplicate case resolution
* Small-dollar resolution
* Pending investigation routing
* Customer communication generation

before introducing checkpoint replay and persistence.

---

## Author

Anita Li 
anita20200324@gmail.com

Solutions Architect

AI Workflow & Agentic Systems
