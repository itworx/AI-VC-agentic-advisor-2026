from __future__ import annotations
from pathlib import Path
from langgraph.types import Command
from backend.graph import build_graph
from backend.persistence.checkpointer import get_checkpointer
from backend.state import create_initial_state


def _graph_with_real_hitl(tmp_path: Path):
    """Build a graph where everything is stubbed EXCEPT human_approval.

    We want to exercise the real pause/resume mechanic without paying for
    real screen or specialist API calls.
    """
    db_path = str(tmp_path / "hitl-test.db")
    checkpointer = get_checkpointer(db_path)
    return build_graph(
        checkpointer=checkpointer,
        use_stubs=True,      # screen + specialists stubbed
        stub_hitl=False,     # but human_approval is REAL
    )


# H-03: pause behavior

def test_graph_pauses_at_human_approval(tmp_path):
    """After the initial invoke, screen has run but nothing after it has —
    the graph is waiting for the human's response."""
    graph = _graph_with_real_hitl(tmp_path)
    config = {"configurable": {"thread_id": "pause-test"}}
    initial = create_initial_state("Test Co", "https://example.com")

    graph.invoke(initial, config)

    state = graph.get_state(config)
    # Screen already ran (stub, sets pass)
    assert state.values["screening_decision"] == "pass"
    # But nothing after human_approval: no specialists, no supervisor turns
    assert state.values["specialists_run"] == []
    assert state.values["iteration_count"] == 0


# H-03/H-04: resume with each of the three response types

def test_resume_with_approval_populates_state_and_continues(tmp_path):
    """approved=True with notes: state carries the response and specialists run."""
    graph = _graph_with_real_hitl(tmp_path)
    config = {"configurable": {"thread_id": "approve-test"}}
    initial = create_initial_state("Test Co", "https://example.com")

    graph.invoke(initial, config)
    graph.invoke(
        Command(resume={"approved": True, "notes": "focus on revenue"}),
        config,
    )

    state = graph.get_state(config)
    assert state.values["human_approved"] is True
    assert state.values["human_notes"] == "focus on revenue"
    # Approved + screening=pass means research proceeds
    assert len(state.values["specialists_run"]) > 0


def test_resume_with_rejection_ends_run(tmp_path):
    """approved=False: state records the refusal, no specialists run."""
    graph = _graph_with_real_hitl(tmp_path)
    config = {"configurable": {"thread_id": "reject-test"}}
    initial = create_initial_state("Test Co", "https://example.com")

    graph.invoke(initial, config)
    graph.invoke(Command(resume={"approved": False}), config)

    state = graph.get_state(config)
    assert state.values["human_approved"] is False
    assert state.values["specialists_run"] == []


def test_override_flips_decision_and_appends_reason(tmp_path):
    """Override flips screening_decision and appends the human's reason."""
    graph = _graph_with_real_hitl(tmp_path)
    config = {"configurable": {"thread_id": "override-test"}}
    initial = create_initial_state("Test Co", "https://example.com")

    graph.invoke(initial, config)
    graph.invoke(
        Command(resume={
            "approved": True,
            "override_decision": "reject",
            "override_reason": "borderline stage",
        }),
        config,
    )

    state = graph.get_state(config)
    # The override took effect
    assert state.values["screening_decision"] == "reject"
    # And the audit trail shows what happened
    assert "Human override" in state.values["screening_reason"]
    assert "borderline stage" in state.values["screening_reason"]
    # Approved but now reject -> route to END, no specialists
    assert state.values["specialists_run"] == []


# defensive behavior


def test_notes_default_to_empty_string_not_none(tmp_path):
    """If human doesn't send notes, human_notes is '' (per State schema)."""
    graph = _graph_with_real_hitl(tmp_path)
    config = {"configurable": {"thread_id": "no-notes-test"}}
    initial = create_initial_state("Test Co", "https://example.com")

    graph.invoke(initial, config)
    graph.invoke(Command(resume={"approved": True}), config)

    state = graph.get_state(config)
    assert state.values["human_notes"] == ""


def test_state_survives_across_pause(tmp_path):
    """H-02 acceptance meets H-03: state written before pause is still there after resume."""
    graph = _graph_with_real_hitl(tmp_path)
    config = {"configurable": {"thread_id": "survives-test"}}
    initial = create_initial_state("Test Co", "https://example.com")

    graph.invoke(initial, config)
    graph.invoke(Command(resume={"approved": True}), config)

    state = graph.get_state(config)
    # Company info from initial state is still there after the pause/resume roundtrip
    assert state.values["company_name"] == "Test Co"
    assert state.values["company_url"] == "https://example.com"
    # Screening result from before the pause is still there
    assert state.values["screening_decision"] == "pass"

def test_pause_survives_new_graph_instance(tmp_path):
    """H-04: pause on one graph instance, resume from a fresh instance
    against the same DB. Simulates a process restart. This is what CI
    catches if the checkpointer ever stops persisting pause state."""
    db_path = str(tmp_path / "restart-test.db")
    config = {"configurable": {"thread_id": "restart-thread"}}
    initial = create_initial_state("Test Co", "https://example.com")

    # Graph instance A: run to the pause and stop
    checkpointer_a = get_checkpointer(db_path)
    graph_a = build_graph(
        checkpointer=checkpointer_a,
        use_stubs=True,
        stub_hitl=False,
    )
    graph_a.invoke(initial, config)

    # Graph instance B: brand new objects (different checkpointer, different
    # compiled graph), same DB on disk. Resume the same thread.
    checkpointer_b = get_checkpointer(db_path)
    graph_b = build_graph(
        checkpointer=checkpointer_b,
        use_stubs=True,
        stub_hitl=False,
    )
    graph_b.invoke(
        Command(resume={"approved": True, "notes": "cross-instance"}),
        config,
    )

    state = graph_b.get_state(config)
    assert state.values["human_approved"] is True
    assert state.values["human_notes"] == "cross-instance"
    assert len(state.values["specialists_run"]) > 0
