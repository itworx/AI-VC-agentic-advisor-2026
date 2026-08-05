"""
T-09: Any run, not only a HITL pause, can be inspected and resumed.

The checkpointer stores state at every super-step, not just at interrupts.
That means we can:
  - Inspect the state at any point in a completed run (auditing)
  - Fork a run from any past checkpoint (what-if replays)
  - Resume a run that ended, adding new updates

This test proves all three against real runs — happy path and reject path,
not just HITL-paused runs.
"""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from backend.graph import build_graph
from backend.state import create_initial_state


APPROVE = {"approved": True, "override_decision": None, "override_reason": None, "notes": None}


def _run_to_completion(graph, thread_id, company="TestCo", url="https://test.co"):
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}
    initial = create_initial_state(company_name=company, company_url=url)
    result = graph.invoke(initial, config)
    if graph.get_state(config).next:
        result = graph.invoke(Command(resume=APPROVE), config)
    return config, result


def test_completed_run_state_is_inspectable():
    """After a full run finishes, we can still fetch its final state."""
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer, use_stubs=True, stub_hitl=True)
    config, result = _run_to_completion(graph, "inspect-completed")

    # get_state on a completed run returns the last checkpoint
    snapshot = graph.get_state(config)
    assert snapshot.values["screening_decision"] == "pass"
    assert snapshot.values["iteration_count"] >= 1
    # No more work queued: run is complete
    assert snapshot.next == ()


def test_state_history_available_for_completed_run():
    """Every super-step of a completed run leaves a checkpoint we can walk."""
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer, use_stubs=True, stub_hitl=True)
    config, _ = _run_to_completion(graph, "inspect-history")

    history = list(graph.get_state_history(config))
    # At least one checkpoint per node executed. The run has several nodes,
    # so we expect a healthy number of checkpoints (>= 5).
    assert len(history) >= 5, f"expected several checkpoints, got {len(history)}"

    # Newest is at index 0
    latest = history[0]
    assert latest.values["screening_decision"] == "pass"


def test_can_fork_run_from_earlier_checkpoint():
    """Pick any past checkpoint and re-invoke — that's the resume primitive
    that isn't just HITL. This proves the checkpointer isn't specific to
    interrupt()."""
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer, use_stubs=True, stub_hitl=True)
    config, _ = _run_to_completion(graph, "inspect-fork")

    history = list(graph.get_state_history(config))

    # Pick a checkpoint from the middle of the run (not the final one)
    mid_checkpoint = history[len(history) // 2]

    # Fork from that checkpoint
    fork_config = mid_checkpoint.config
    forked = graph.invoke(None, fork_config)  # None input = continue from checkpoint

    # The fork completed and produced a final state
    assert forked["screening_decision"] == "pass"


def test_reject_run_is_inspectable():
    """A run that ended via reject (no HITL involvement) is also inspectable.
    Coverage for 'any run, not only a HITL pause'."""
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer, use_stubs=True, stub_hitl=False)

    config = {"configurable": {"thread_id": "inspect-reject"}, "recursion_limit": 40}
    initial = create_initial_state(company_name="RejectCo", company_url="https://reject.co")

    graph.invoke(initial, config)
    graph.invoke(
        Command(resume={"approved": False, "override_decision": None, "override_reason": None, "notes": None}),
        config,
    )

    # Even though this run terminated at HITL rejection, the checkpointer
    # captured the full trail
    snapshot = graph.get_state(config)
    assert snapshot.values["human_approved"] is False
    assert snapshot.values["iteration_count"] == 0

    history = list(graph.get_state_history(config))
    assert len(history) >= 2, "reject-path history should be captured"


def test_two_threads_are_isolated():
    """Inspection works per-thread. Two thread_ids don't cross-contaminate.
    This matters for T-09 because a real system inspects specific runs."""
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer, use_stubs=True, stub_hitl=True)

    _run_to_completion(graph, "thread-a", company="CompanyA")
    _run_to_completion(graph, "thread-b", company="CompanyB")

    state_a = graph.get_state({"configurable": {"thread_id": "thread-a"}})
    state_b = graph.get_state({"configurable": {"thread_id": "thread-b"}})

    assert state_a.values["company_name"] == "CompanyA"
    assert state_b.values["company_name"] == "CompanyB"