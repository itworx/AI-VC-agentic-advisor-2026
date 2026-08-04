from __future__ import annotations
from datetime import datetime, timezone
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from backend.nodes.market_intel import market_intel
from backend.nodes.company_intel import company_intel
from backend.nodes.screening.screen_company2 import screen_company
from backend.nodes.supervisor.coverage_checker import check_coverage
from backend.nodes.supervisor.supervisor import supervisor
from backend.nodes.team_signals import team_signals
from backend.persistence import get_checkpointer
from backend.state import State, create_initial_state
from backend.models.claim import Claim
from backend.nodes.hitl.human_approval import human_approval, human_approval_stub



# real specialist adapters
# Teammates' specialist functions take (company_name, company_website) and
# return a SpecialistOutput. LangGraph nodes need to take State and return
# a state-update dict. These adapters translate between the two.

def screen_node(state: State) -> dict:
    result = screen_company(
        company_name=state["company_name"],
        company_url=state["company_url"],
    )
    return {
        "screening_decision": result.decision,
        "screening_reason": result.reason,
        "matched_criteria": result.matched_criteria,
    }

def market_intel_node(state: State) -> dict:
    """Adapter for market_intel.

    Converts ClaimContent → Claim by adding a real retrieval_timestamp we
    control (not one the LLM guessed). Serializes to dicts so the SQLite
    checkpointer can persist state.
    """
    output = market_intel(state["company_name"], state["company_url"])
    fetched_at = datetime.now(tz=timezone.utc)
    claims = []
    for c in output.claims:
        data = c.model_dump()
        data["retrieval_timestamp"] = fetched_at  # our timestamp wins
        claims.append(Claim(**data))
    
    dumped_claims = [c.model_dump(mode="json") for c in claims]
    return {
        "claims": dumped_claims,
        "not_found": output.not_found,
        "specialists_run": ["market_intel"],
        "specialist_outputs": [{
            "specialist": "market_intel",
            "claims": dumped_claims,
            "not_found": output.not_found,
        }],
    }


def team_signals_node(state: State) -> dict:
    """Adapter for team_signals. Same pattern as market_intel_node."""
    output = team_signals(state["company_name"], state["company_url"])
    fetched_at = datetime.now(tz=timezone.utc)
    claims = []
    for c in output.claims:
        data = c.model_dump()
        data["retrieval_timestamp"] = fetched_at  # our timestamp wins
        claims.append(Claim(**data))

    dumped_claims = [c.model_dump(mode="json") for c in claims]
    return {
        "claims": dumped_claims,
        "not_found": output.not_found,
        "specialists_run": ["team_signals"],
        "specialist_outputs": [{
            "specialist": "team_signals",
            "claims": dumped_claims,
            "not_found": output.not_found,
        }],
    }
def company_intel_node(state: State) -> dict:
    """Adapter for company_intel. Same pattern as market_intel_node."""
    output = company_intel(state["company_name"], state["company_url"])
    fetched_at = datetime.now(tz=timezone.utc)
    claims = []
    for c in output.claims:
        data = c.model_dump()
        data["retrieval_timestamp"] = fetched_at  # our timestamp wins
        claims.append(Claim(**data))
        
    dumped_claims = [c.model_dump(mode="json") for c in claims]
    return {
        "claims": dumped_claims,
        "not_found": output.not_found,
        "specialists_run": ["company_intel"],
        "specialist_outputs": [{
            "specialist": "company_intel",
            "claims": dumped_claims,
            "not_found": output.not_found,
        }],
    }



# stubs (fast, no API cost; used in tests and for company_intel until merge)

def screen_stub(state: State) -> dict:
    """Test stub: always passes so tests can exercise the rest of the graph."""
    return {
        "screening_decision": "pass",
        "screening_reason": "test stub always passes",
        "matched_criteria": ["test_criterion"],
    }

def company_intel_stub(state: State) -> dict:
    """Test-only stub that skips the real API call."""
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

# def route_after_screen(state: State) -> str:
#     """After screen: if reject, end the run without running specialists.
#     If pass, proceed to research. This is the whole cost-savings point of
#     putting screen first."""
#     return "check_coverage" if state["screening_decision"] == "pass" else "end"
def route_after_human_approval(state: State) -> str:
    """After human_approval: end if human said no, or if screening
    (possibly overridden by the human) is reject. Otherwise proceed to
    research. This is the gate that stops us spending on specialists."""
    if not state["human_approved"]:
        return "end"
    if state["screening_decision"] == "reject":
        return "end"
    return "check_coverage"


# graph builder


def build_graph(
    checkpointer: SqliteSaver | None = None,
    use_stubs: bool = False,
    stub_hitl: bool | None = None,
):
    """Build and compile the graph.

    Args:
      checkpointer: SqliteSaver to use. Defaults to the shared production one.
      use_stubs: When True, replaces market_intel and team_signals with
                 fast stubs that don't call any API. Use in tests. Default
                 False = real specialists, real API calls, real costs.
      stub_hitl: When True, replaces human_approval with an auto-approve
                 stub that skips the interrupt() pause. Defaults to matching
                 use_stubs — tests that just want the graph to run through
                 don't want to handle a pause. Set to False explicitly in
                 tests that exercise the pause/resume flow.


    """
    if stub_hitl is None:
            stub_hitl = use_stubs

    builder = StateGraph(State)

    builder.add_node("screen", screen_stub if use_stubs else screen_node)
    builder.add_node(
            "human_approval",
            human_approval_stub if stub_hitl else human_approval,
        )
    builder.add_node("check_coverage", check_coverage)
    builder.add_node("supervisor", supervisor)
    builder.add_node(
        "company_intel", 
        company_intel_stub if use_stubs else company_intel_node,
    )
    builder.add_node(
        "market_intel",
        market_intel_stub if use_stubs else market_intel_node,
    )
    builder.add_node(
        "team_signals",
        team_signals_stub if use_stubs else team_signals_node,
    )
    builder.add_node("write_memo", write_memo_stub)

    # flow: screen runs first (cheap), then human_approval pauses so the
    # user can approve/override before we spend money on specialists.
    builder.add_edge(START, "screen")
    builder.add_edge("screen", "human_approval")
    builder.add_conditional_edges(
            "human_approval",
            route_after_human_approval,
            {"check_coverage": "check_coverage", "end": END},
        )
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
        company_url="https://www.instabug.com",
    )

    print("Invoking graph...\n")
    result = graph.invoke(initial, config)

    print(f"Screening decision: {result['screening_decision']}")
    print(f"Screening reason: {result['screening_reason']}")
    print(f"Matched thesis criteria: {result['matched_criteria']}")
    print()
    print(f"Final iteration_count: {result['iteration_count']}")
    print(f"Specialists that ran: {result['specialists_run']}")
    print(f"Total claims collected: {len(result['claims'])}")
    print(f"Coverage covered: {result['covered_categories']}")
    print(f"Coverage missing: {result['missing_categories']}")
    print(f"Not found: {result['not_found']}")
    print(f"\nDecision log ({len(result['decision_log'])} entries):")
    for entry in result["decision_log"]:
        print(f"  iter {entry['iteration']}: chose {entry['chosen']} — {entry['reason']}")
