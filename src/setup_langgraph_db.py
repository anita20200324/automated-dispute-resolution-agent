import os
from dotenv import load_dotenv

from langgraph.checkpoint.postgres import PostgresSaver

load_dotenv()

POSTGRES_URI = os.getenv("POSTGRES_URI")

if not POSTGRES_URI:
    raise ValueError("POSTGRES_URI not found")


def setup_langgraph_db():

    with PostgresSaver.from_conn_string(
        POSTGRES_URI
    ) as checkpointer:

        checkpointer.setup()

    print("SUCCESS")
    print("LangGraph checkpoint tables created.")


if __name__ == "__main__":
    setup_langgraph_db()