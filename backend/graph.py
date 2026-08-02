from __future__ import annotations
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from backend.nodes.market_intel import market_intel
from backend.nodes.supervisor.coverage_checker import check_coverage
from backend.nodes.supervisor.supervisor import supervisor
from backend.nodes.team_signals import team_signals
from backend.persistence import get_checkpointer
from backend.state import State, create_initial_state


# real specialist adapters
# Teammates' specialist functions take (company_name, company_website) and
# return a SpecialistOutput. LangGraph nodes need to take State and return
# a state-update dict. These adapters translate between the two.


def market_intel_node(state: State) -> dict:
    """Adapter for market_intel. Calls the real specialist, returns state update."""
    output = market_intel(state["company_name"], state["company_url"])
    return {
        "claims": [c.model_dump(mode="json") for c in output.claims],
        "not_found": output.not_found,
        "specialists_run": ["market_intel"],
    }


def team_signals_node(state: State) -> dict:
    """Adapter for team_signals. Calls the real specialist, returns state update."""
    output = team_signals(state["company_name"], state["company_url"])
    return {
        "claims": [c.model_dump(mode="json") for c in output.claims],
        "not_found": output.not_found,
        "specialists_run": ["team_signals"],
    }



# stubs (fast, no API cost; used in tests and for company_intel until merge)


def company_intel_stub(state: State) -> dict:
    """Placeholder for SP-02. Real company_intel is on a branch."""
    return {"specialists_run": ["company_intel"]}


def market_intel_stub(state: State) -> dict:
    """Test-only stub that skips the real API call."""
    return {"specialists_run": ["market_intel"]}


def team_signals_stub(state: State) -> dict:
    """Test-only stub that skips the real API call."""
    return {"specialists_run": ["team_signals"]}


def write_memo_stub(state: State) -> dict:
    """Placeholder for M-01. Returns a fixed memo body so runs can end."""
    return {"memo_base": "[stub memo — real one comes in M-01]"}


# conditional edge router


def route_from_supervisor(state: State) -> str:
    """Read next_action off state (set by supervisor). Return node name."""
    return state["next_action"]


# graph builder


def build_graph(
    checkpointer: SqliteSaver | None = None,
    use_stubs: bool = False,
):
    """Build and compile the graph.

    Args:
      checkpointer: SqliteSaver to use. Defaults to the shared production one.
      use_stubs: When True, replaces market_intel and team_signals with
                 fast stubs that don't call any API. Use in tests. Default
                 False = real specialists, real API calls, real costs.

    Note: company_intel is stubbed regardless of the flag because the real
    version is still on a branch. Update this file when it merges.
    """
    builder = StateGraph(State)

    builder.add_node("check_coverage", check_coverage)
    builder.add_node("supervisor", supervisor)

    # company_intel is always stubbed for now (real version on a branch)
    builder.add_node("company_intel", company_intel_stub)
    builder.add_node(
        "market_intel",
        market_intel_stub if use_stubs else market_intel_node,
    )
    builder.add_node(
        "team_signals",
        team_signals_stub if use_stubs else team_signals_node,
    )
    builder.add_node("write_memo", write_memo_stub)

    # flow: coverage first (initial has no claims → all missing), then supervisor.
    builder.add_edge(START, "check_coverage")
    builder.add_edge("check_coverage", "supervisor")

    # supervisor's conditional edge: reads next_action from state.
    builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "company_intel": "company_intel",
            "market_intel": "market_intel",
            "team_signals": "team_signals",
            "write_memo": "write_memo",
        },
    )

    # after each specialist, recompute coverage
    builder.add_edge("company_intel", "check_coverage")
    builder.add_edge("market_intel", "check_coverage")
    builder.add_edge("team_signals", "check_coverage")

    # memo is the exit
    builder.add_edge("write_memo", END)

    if checkpointer is None:
        checkpointer = get_checkpointer()

    return builder.compile(checkpointer=checkpointer)


graph = build_graph()


if __name__ == "__main__":
    # Live run, calls real APIs and costs real money.
    print("WARNING: this runs the graph with real specialists (Gemini + Tavily).")
    print("Set use_stubs=True in build_graph() if you just want to verify wiring.\n")

    config = {"configurable": {"thread_id": "sv01-live-run-1"}}
    initial = create_initial_state(
        company_name="Instabug",
        company_url="https://instabug.com",
    )

    print("Invoking graph...\n")
    result = graph.invoke(initial, config)

    print(f"Final iteration_count: {result['iteration_count']}")
    print(f"Specialists that ran: {result['specialists_run']}")
    print(f"Total claims collected: {len(result['claims'])}")
    print(f"Coverage covered: {result['covered_categories']}")
    print(f"Coverage missing: {result['missing_categories']}")
    print(f"Not found: {result['not_found']}")
    print(f"\nDecision log ({len(result['decision_log'])} entries):")
    for entry in result["decision_log"]:
        print(f"  iter {entry['iteration']}: chose {entry['chosen']} — {entry['reason']}")
