from __future__ import annotations
from pathlib import Path
import pytest
from backend.graph import build_graph
from backend.persistence.checkpointer import get_checkpointer
from backend.state import create_initial_state


def test_checkpointer_creates_db_file(tmp_path: Path):
    """get_checkpointer must produce a SqliteSaver that writes to the given path."""
    db_path = str(tmp_path / "test_checkpointer.db")
    checkpointer = get_checkpointer(db_path)
    assert checkpointer is not None
    assert Path(db_path).exists()


def test_checkpointer_creates_parent_dirs(tmp_path: Path):
    """get_checkpointer should mkdir parents if they don't exist."""
    nested_path = tmp_path / "sub1" / "sub2" / "test.db"
    get_checkpointer(str(nested_path))
    assert nested_path.parent.exists()


def test_graph_persists_state_after_invoke(tmp_path: Path):
    """Invoking the graph writes state to the checkpointer under the thread_id."""
    db_path = str(tmp_path / "test.db")
    checkpointer = get_checkpointer(db_path)
    graph = build_graph(checkpointer=checkpointer, use_stubs=True)  # no real API calls in tests

    config = {"configurable": {"thread_id": "test-thread-1"}}
    initial = create_initial_state("Test Co", "https://example.com")
    graph.invoke(initial, config)

    # retrieve state back from the checkpointer
    state = graph.get_state(config)
    assert state is not None
    assert state.values["company_name"] == "Test Co"
    assert state.values["company_url"] == "https://example.com"


def test_graph_persists_separate_threads_independently(tmp_path: Path):
    """Two thread_ids should not overwrite each other's state."""
    db_path = str(tmp_path / "test.db")
    checkpointer = get_checkpointer(db_path)
    graph = build_graph(checkpointer=checkpointer, use_stubs=True)  # no real API calls in tests

    graph.invoke(
        create_initial_state("Company A", "https://a.example.com"),
        {"configurable": {"thread_id": "thread-a"}},
    )
    graph.invoke(
        create_initial_state("Company B", "https://b.example.com"),
        {"configurable": {"thread_id": "thread-b"}},
    )

    state_a = graph.get_state({"configurable": {"thread_id": "thread-a"}})
    state_b = graph.get_state({"configurable": {"thread_id": "thread-b"}})

    assert state_a.values["company_name"] == "Company A"
    assert state_b.values["company_name"] == "Company B"
