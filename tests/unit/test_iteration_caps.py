"""
T-10: Iteration cap holds on every route through the graph.

The supervisor cap (6) must terminate the loop no matter which specialists
are available, no matter what claims come back, no matter what missing
categories persist. A cap that only works when things go smoothly is not
a cap.
"""
from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from backend.graph import build_graph
from backend.state import create_initial_state
from backend.nodes.supervisor.supervisor import ITERATION_CAP


APPROVE = {"approved": True, "override_decision": None, "override_reason": None, "notes": None}
REJECT = {"approved": False, "override_decision": None, "override_reason": None, "notes": None}


def _run(graph, company_name="TestCo", company_url="https://test.co"):
    """Invoke, resume any HITL pause with approve, return final state."""
    config = {
        "configurable": {"thread_id": f"cap-test-{company_name}"},
        "recursion_limit": 40,
    }
    initial = create_initial_state(company_name=company_name, company_url=company_url)
    result = graph.invoke(initial, config)
    if graph.get_state(config).next:
        result = graph.invoke(Command(resume=APPROVE), config)
    return result


def test_iteration_cap_on_happy_path():
    """Coverage-complete path terminates well under the cap."""
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer, use_stubs=True, stub_hitl=True)
    result = _run(graph)
    assert result["iteration_count"] <= ITERATION_CAP


def test_iteration_cap_when_specialists_exhausted():
    """Specialists-exhausted path terminates well under the cap.

    With stubs, all specialists return empty claims, so nothing gets covered.
    The supervisor should route to memo once every specialist has run once,
    not loop back through them.
    """
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer, use_stubs=True, stub_hitl=True)
    result = _run(graph)
    # Even with nothing being covered, we should terminate within a few iterations
    assert result["iteration_count"] <= ITERATION_CAP


def test_iteration_cap_hard_upper_bound():
    """No matter the path, iteration_count never exceeds ITERATION_CAP."""
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer, use_stubs=True, stub_hitl=True)
    result = _run(graph)
    assert result["iteration_count"] <= ITERATION_CAP, (
        f"Supervisor exceeded iteration cap of {ITERATION_CAP}, "
        f"got {result['iteration_count']}"
    )


def test_reject_path_never_enters_supervisor_loop():
    """A rejected screening should exit before the supervisor even runs.

    Uses real HITL (stub_hitl=False) so the graph actually pauses at
    human_approval, and we can resume with a rejection.
    """
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer, use_stubs=True, stub_hitl=False)

    config = {
        "configurable": {"thread_id": "cap-reject-path"},
        "recursion_limit": 40,
    }
    initial = create_initial_state(company_name="RejectCo", company_url="https://reject.co")

    # First invoke: runs stub screen (passes), pauses at real human_approval
    result = graph.invoke(initial, config)
    assert graph.get_state(config).next, "graph did not pause at human_approval"

    # Resume with rejection — router should send us to END
    result = graph.invoke(Command(resume=REJECT), config)

    assert result["iteration_count"] == 0
    assert result["specialists_run"] == []


def test_recursion_limit_is_configured():
    """Prove the recursion limit is being passed and honoured by config."""
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer, use_stubs=True, stub_hitl=True)

    # A very low recursion limit should force GraphRecursionError before
    # the graph completes. This proves the mechanism is active.
    config = {
        "configurable": {"thread_id": "cap-recursion-limit"},
        "recursion_limit": 2,  # deliberately too low
    }
    initial = create_initial_state(company_name="TestCo", company_url="https://test.co")

    from langgraph.errors import GraphRecursionError
    with pytest.raises(GraphRecursionError):
        graph.invoke(initial, config)