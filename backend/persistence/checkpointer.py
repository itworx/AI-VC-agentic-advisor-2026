"""SQLite checkpointer for LangGraph state persistence."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from langgraph.checkpoint.sqlite import SqliteSaver

DEFAULT_DB_PATH = "checkpoints/hitl.db"

def get_checkpointer(db_path: str = DEFAULT_DB_PATH) -> SqliteSaver:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn)