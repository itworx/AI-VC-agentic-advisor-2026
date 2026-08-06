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
from backend.models.evaluation import BLOCKING_KINDS
from backend.models.memo import MemoDraft
from backend.nodes.memo.write_memo import write_memo
from backend.nodes.memo.render_citations import (
    enforce_page_cap,
    render_citations,
    strip_unresolved_markers,
)
from backend.nodes.evaluation.evaluate import (
    EVALUATOR_CAP,
    evaluate_stub,
    make_evaluate_node,
    route_from_evaluate,
)
from backend.nodes.evaluation.support import check_support




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

NO_CLAIMS_PLACEHOLDER = "[no claims collected — nothing to write]"


def write_memo_node(state: State) -> dict:
    """Adapter for D's write_memo. Produces the raw <<N>> draft only.

    Rendering is deliberately NOT done here - it's its own node, downstream of
    the evaluator. See render_citations.py's ordering note: rendering first
    means a hallucinated <<N>> raises UnresolvedCitationError before the
    evaluator can turn it into a clean reject.

    Re-entrant: the evaluator routes back here on a reject, in which case
    evaluator_feedback is non-empty and gets passed through to write_memo as
    a revision brief. Same claims, sharper instructions.
    """
    claims = [Claim(**c) for c in state["claims"]]

    if not claims:
        return {
            "memo_bull": NO_CLAIMS_PLACEHOLDER,
            "memo_base": NO_CLAIMS_PLACEHOLDER,
            "memo_bear": NO_CLAIMS_PLACEHOLDER,
        }

    draft = write_memo(claims, feedback=state.get("evaluator_feedback", ""))

    return {
        "memo_bull": draft.bull_case,
        "memo_base": draft.base_case,
        "memo_bear": draft.bear_case,
    }


def render_citations_node(state: State) -> dict:
    """Adapter for D's render_citations + enforce_page_cap (M-03/M-04/M-05).

    Runs only after the evaluator accepts. Turns the raw <<N>> markers into
    renumbered [k] footnotes with a Sources section, applies the 4-page cap
    last, and - when the run is shipping on accept_capped - prepends the
    warning banner naming how many sentences never traced.
    """
    claims = [Claim(**c) for c in state["claims"]]

    if not claims:
        return {"memo_rendered": NO_CLAIMS_PLACEHOLDER}

    draft = MemoDraft(
        bull_case=state["memo_bull"],
        base_case=state["memo_base"],
        bear_case=state["memo_bear"],
    )

    # Normally a no-op: unresolved markers are a blocking evaluator violation,
    # so a draft only reaches here with one when the E-03 cap ran out.
    draft, dropped = strip_unresolved_markers(draft, claims)
    if dropped:
        print(
            f"[render_citations] dropped {len(dropped)} unresolved citation "
            f"marker(s) {dropped} from a memo shipping on a spent evaluator cap"
        )

    rendered = enforce_page_cap(render_citations(draft, claims))

    if state.get("evaluator_decision") == "accept_capped":
        untraced = sum(
            1
            for v in state.get("evaluator_violations", [])
            if v.get("kind") in BLOCKING_KINDS
        )
        banner = (
            f"> **EVALUATOR WARNING (E-03):** this memo was accepted after the "
            f"evaluator cap of {EVALUATOR_CAP} passes was spent, with "
            f"{untraced} sentence(s) still failing the traceability check"
            + (
                f", and {len(dropped)} citation marker(s) pointing at no claim "
                "were removed"
                if dropped
                else ""
            )
            + ". The flagged sentences are NOT sourced - read "
            "evaluator_feedback in the run state before relying on anything "
            "here.\n\n"
        )
        rendered = banner + rendered

    return {"memo_rendered": rendered}



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
    """Test-only stub. Emits a well-formed draft that cites every claim in
    state, so the REAL evaluator can be exercised against it offline (see
    build_graph's stub_evaluator). A marker-free placeholder would be rejected
    by tier 1 every pass and tell us nothing.

    The three cases cite different subsets on purpose - identical citation sets
    are what M-02's assert_cases_differ exists to catch, and a stub that
    tripped it would be a misleading fixture.
    """
    n = len(state["claims"])
    if n == 0:
        return {
            "memo_bull": NO_CLAIMS_PLACEHOLDER,
            "memo_base": NO_CLAIMS_PLACEHOLDER,
            "memo_bear": NO_CLAIMS_PLACEHOLDER,
        }

    all_markers = " ".join(f"<<{i}>>" for i in range(1, n + 1))
    first = "<<1>>"
    last = f"<<{n}>>"
    return {
        "memo_bull": f"The favourable reading rests on the cited evidence {first}.",
        "memo_base": f"The balanced reading weighs every claim gathered {all_markers}.",
        "memo_bear": f"The cautious reading weights the gaps {last}.",
    }


# conditional edge router


def route_from_supervisor(state: State) -> str:
    """Read next_action off state (set by supervisor). Return node name."""
    return state["next_action"]


# route_from_evaluate is imported from the evaluation package rather than
# defined here - see its docstring.

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
    stub_evaluator: bool | None = None,
    semantic_eval: bool | None = None,
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
      stub_evaluator: When True, replaces evaluate with an always-accept stub.
                 Defaults to matching use_stubs. Set to False with
                 use_stubs=True to run the REAL evaluator against
                 write_memo_stub's draft — an offline, zero-cost end-to-end
                 test of the memo -> evaluate -> render path.
      semantic_eval: When True, the evaluator's tier-2 entailment check runs
                 (one extra cheap model call per pass). Defaults to on for real
                 runs and off whenever the evaluator is stubbed or use_stubs is
                 set, so tests never reach the network.
    """
    if stub_hitl is None:
        stub_hitl = use_stubs
    if stub_evaluator is None:
        stub_evaluator = use_stubs
    if semantic_eval is None:
        semantic_eval = not (use_stubs or stub_evaluator)

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
    builder.add_node(
        "write_memo",
        write_memo_stub if use_stubs else write_memo_node)
    builder.add_node(
        "evaluate",
        evaluate_stub
        if stub_evaluator
        else make_evaluate_node(check_support if semantic_eval else None),
    )
    builder.add_node("render_citations", render_citations_node)

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

    # memo -> evaluator -> either back for one rewrite, or on to rendering.
    # Rendering is downstream of the evaluator so an unresolved <<N>> is a
    # clean reject rather than a crash inside the renderer.
    builder.add_edge("write_memo", "evaluate")
    builder.add_conditional_edges(
        "evaluate",
        route_from_evaluate,
        {"write_memo": "write_memo", "render_citations": "render_citations"},
    )
    builder.add_edge("render_citations", END)

    if checkpointer is None:
        checkpointer = get_checkpointer()

    return builder.compile(checkpointer=checkpointer)


graph = build_graph()


if __name__ == "__main__":
    import sys
    import os
    from langgraph.types import Command

    auto_approve = "--auto" in sys.argv
    # Live run, calls real APIs and costs real money.
    print("WARNING: this runs the graph with real specialists (Gemini + Tavily).")

    # Fresh thread every run so we always start clean
    thread_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    config = {"configurable": {"thread_id": thread_id},
              "recursion_limit": 40
              }


    # config = {"configurable": {"thread_id": "hitl-test-1"}}
    initial = create_initial_state(
        company_name="Instabug",
        company_url="https://www.instabug.com",
    )
    

    # print("Invoking graph...\n")
    # result = graph.invoke(initial, config)

    # print(f"Screening decision: {result['screening_decision']}")
    # print(f"Screening reason: {result['screening_reason']}")
    # print(f"Matched thesis criteria: {result['matched_criteria']}")
    # print()
    # print(f"Final iteration_count: {result['iteration_count']}")
    # print(f"Specialists that ran: {result['specialists_run']}")
    # print(f"Total claims collected: {len(result['claims'])}")
    # print(f"Coverage covered: {result['covered_categories']}")
    # print(f"Coverage missing: {result['missing_categories']}")
    # print(f"Not found: {result['not_found']}")
    # print(f"\nDecision log ({len(result['decision_log'])} entries):")
    # for entry in result["decision_log"]:
    #     print(f"  iter {entry['iteration']}: chose {entry['chosen']} — {entry['reason']}")

    # First invoke: screen runs, graph pauses at human_approval
    print("Invoking graph...\n")
    result = graph.invoke(initial, config)

    print(f"Screening decision: {result['screening_decision']}")
    print(f"Screening reason:   {result['screening_reason']}")
    print(f"Matched criteria:   {result['matched_criteria']}\n")

    state = graph.get_state(config)
    if state.next:
        if auto_approve:
            print("Auto-approving (--auto flag set)\n")
            human_response = {"approved": True, "override_decision": None, "override_reason": None, "notes": None}
        else:
            choice = input("Approve this company? [y/n]: ").strip().lower()
            approved = choice == "y"
            human_response = {"approved": approved, "override_decision": None, "override_reason": None, "notes": None}

        result = graph.invoke(Command(resume=human_response), config)

    print(f"\nSpecialists ran: {result['specialists_run']}")
    print(f"Claims:          {len(result['claims'])}")
    print(f"Covered:         {result['covered_categories']}")
    print(f"Missing:         {result['missing_categories']}")
    print(f"Not found:       {result['not_found']}")
    print(f"\nMemo — Bull case:\n{result.get('memo_bull', '')[:500]}...")
    print(f"\nMemo — Base case:\n{result.get('memo_base', '')[:500]}...")
    print(f"\nMemo — Bear case:\n{result.get('memo_bear', '')[:500]}...")
    print(f"\nDecision log ({len(result['decision_log'])} entries):")
    for entry in result["decision_log"]:
        print(f"  iter {entry['iteration']}: chose {entry['chosen']} — {entry['reason']}")