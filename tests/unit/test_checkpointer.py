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

def test_checkpointed_state_survives_new_graph_instance(tmp_path: Path):
    """H-02 acceptance: run stops, restarts, resumes from same thread_id.

    Simulates a process restart by building two independent graph instances
    against the same DB. State written by the first must be readable by
    the second. This is the guarantee interrupt() (H-03) relies on.
    """
    db_path = str(tmp_path / "test.db")

    # First graph instance: run and let it write to the DB
    checkpointer_a = get_checkpointer(db_path)
    graph_a = build_graph(checkpointer=checkpointer_a, use_stubs=True)
    config = {"configurable": {"thread_id": "restart-test"}}
    result = graph_a.invoke(
        create_initial_state("Test Co", "https://example.com"),
        config,
    )
    expected_iterations = result["iteration_count"]
    expected_specialists = result["specialists_run"]

    # Second graph instance: fresh objects, same DB, read state back
    checkpointer_b = get_checkpointer(db_path)
    graph_b = build_graph(checkpointer=checkpointer_b, use_stubs=True)
    state = graph_b.get_state(config)

    # State written by graph_a must be readable by graph_b
    assert state.values["iteration_count"] == expected_iterations
    assert state.values["specialists_run"] == expected_specialists
    assert state.values["company_name"] == "Test Co"