"""
The memo -> evaluate -> render_citations path, inside the REAL build_graph().

This closes a gap the other tests couldn't: every existing graph test passes
use_stubs=True, which used to swap in evaluate_stub, so the real evaluator had
never once executed inside build_graph. Its loop was only ever proven against a
hand-built StateGraph with a fake write_memo - which cannot catch a state-key
mismatch between the real nodes, and cannot catch a rendering-order bug.

build_graph(use_stubs=True, stub_evaluator=False) gives the real evaluator and
the real renderer over write_memo_stub's marker-bearing draft: offline, free,
and end to end. semantic_eval defaults off here, so nothing reaches the network.
"""

import pytest
from langgraph.checkpoint.memory import MemorySaver

from backend.graph import build_graph
from backend.models.claim import Claim
from backend.nodes.evaluation.evaluate import EVALUATOR_CAP
from backend.state import create_initial_state


def _claim(**overrides) -> Claim:
    defaults = dict(
        claim_text="Instabug sells mobile app observability software.",
        source_url="https://instabug.com",
        quoted_snippet="Mobile app observability platform.",
        specialist="company_intel",
        confidence="verified",
        category="what_company_does",
    )
    defaults.update(overrides)
    return Claim(**defaults)


CLAIMS = [
    _claim(claim_text="Instabug sells mobile app observability software."),
    _claim(
        claim_text="The mobile observability market was worth 2 billion dollars in 2024.",
        category="market_size",
        confidence="inferred",
    ),
    _claim(
        claim_text="Sentry and Datadog are competitors in observability.",
        category="competitors",
        confidence="reported",
    ),
]


def _run(initial_extra=None, **build_kwargs):
    """Run the real graph with stub specialists to the end, returning state."""
    kwargs = dict(use_stubs=True, stub_hitl=True, stub_evaluator=False)
    kwargs.update(build_kwargs)
    graph = build_graph(checkpointer=MemorySaver(), **kwargs)

    state = create_initial_state("Instabug", "https://instabug.com")
    if initial_extra:
        state.update(initial_extra)

    config = {"configurable": {"thread_id": "memo-pipeline"}, "recursion_limit": 40}
    return graph.invoke(state, config)


def _with_claims(claims=CLAIMS):
    """Claims pre-seeded into state, since the stub specialists return none."""
    return {"claims": [c.model_dump(mode="json") for c in claims]}


def test_real_evaluator_runs_inside_the_real_graph():
    result = _run(_with_claims())

    assert result["evaluator_iterations"] >= 1, "the evaluate node never ran"
    assert result["evaluator_decision"] == "accept"
    assert result["memo_rendered"], "render_citations produced nothing"


def test_render_citations_is_its_own_node_and_runs_after_the_evaluator():
    graph = build_graph(
        checkpointer=MemorySaver(), use_stubs=True, stub_hitl=True, stub_evaluator=False
    )
    drawn = graph.get_graph()
    nodes = {n for n in drawn.nodes if not n.startswith("__")}

    assert "render_citations" in nodes
    assert "evaluate" in nodes

    edges = {(e.source, e.target) for e in drawn.edges}
    assert ("write_memo", "evaluate") in edges
    assert ("evaluate", "render_citations") in edges
    assert ("evaluate", "write_memo") in edges  # the rework loop
    assert ("write_memo", "render_citations") not in edges


def test_rendered_memo_has_resolved_footnotes_and_sources():
    result = _run(_with_claims())
    rendered = result["memo_rendered"]

    assert "<<" not in rendered, "raw markers leaked into the rendered memo"
    assert "[1]" in rendered
    assert "## Sources" in rendered
    # M-04: the inferred claim must be visibly marked
    assert "[inferred]" in rendered


def test_no_claims_run_still_completes():
    """The supervisor shouldn't route here with zero claims, but if it does the
    graph must finish rather than raise out of write_memo."""
    result = _run()

    assert result["evaluator_decision"] == "accept"
    assert "nothing to trace" in result["evaluator_feedback"]
    assert result["memo_rendered"]


def test_unresolved_citation_rejects_instead_of_crashing_the_renderer():
    """The bug this ordering exists to prevent.

    render_citations raises UnresolvedCitationError on an out-of-range <<N>>.
    With rendering downstream of the evaluator, such a draft is a clean reject
    that loops for a rewrite. With rendering upstream (the original ordering),
    the run died inside the renderer and the evaluator's unresolved_citation
    verdict was unreachable in production.
    """
    seen_feedback = []

    def bad_marker_write_memo(state):
        seen_feedback.append(state.get("evaluator_feedback", ""))
        n = len(state["claims"])
        return {
            "memo_bull": f"Instabug has 400 staff <<{n + 5}>>.",  # points at nothing
            "memo_base": "Instabug sells observability software <<1>>.",
            "memo_bear": f"Competitors exist <<{n}>>.",
        }

    graph_builder = build_graph  # named for clarity in the patch below
    import backend.graph as graph_module

    original = graph_module.write_memo_stub
    graph_module.write_memo_stub = bad_marker_write_memo
    try:
        result = _run(_with_claims())
    finally:
        graph_module.write_memo_stub = original

    # It rejected, looped, and stopped at the cap rather than raising.
    assert result["evaluator_iterations"] == EVALUATOR_CAP
    assert result["evaluator_decision"] == "accept_capped"
    assert any(
        v["kind"] == "unresolved_citation" for v in result["evaluator_violations"]
    ), "the unresolved marker was never reported as such"
    # the rewrite actually received the feedback
    assert len(seen_feedback) == EVALUATOR_CAP
    assert "not a claim" in seen_feedback[1]


def test_capped_memo_ships_with_a_warning_banner_and_no_dead_footnotes():
    """A memo that failed its own traceability check must never leave the
    pipeline looking clean - and must not crash on the way out."""

    def bad_marker_write_memo(state):
        n = len(state["claims"])
        return {
            "memo_bull": f"Instabug has 400 staff <<{n + 5}>>.",
            "memo_base": "Instabug sells observability software <<1>>.",
            "memo_bear": f"Competitors exist <<{n}>>.",
        }

    import backend.graph as graph_module

    original = graph_module.write_memo_stub
    graph_module.write_memo_stub = bad_marker_write_memo
    try:
        result = _run(_with_claims())
    finally:
        graph_module.write_memo_stub = original

    rendered = result["memo_rendered"]
    assert "EVALUATOR WARNING" in rendered
    assert "traceability check" in rendered
    assert "pointing at no claim" in rendered
    # the unresolvable marker is gone rather than rendered as a live footnote
    assert "<<" not in rendered
    assert "[4]" not in rendered  # would be the dead marker's footnote number


def test_page_cap_applies_after_the_evaluator_accepts():
    """M-05 runs last, in the renderer, so it can never truncate a sentence out
    from under the traceability check."""
    long_claim = _claim(claim_text="word " * 40, category="market_trends")
    many = CLAIMS + [long_claim] * 60

    def verbose_write_memo(state):
        n = len(state["claims"])
        # long sentences on purpose: the cap counts the combined body, so short
        # filler wouldn't reach MAX_BODY_WORDS and the test would pass vacuously
        body = " ".join(
            f"Filler sentence number {i} padded with a good many additional "
            f"words so that the combined body reliably exceeds the four page "
            f"word budget enforced by the renderer <<{i}>>."
            for i in range(1, n + 1)
        )
        return {
            "memo_bull": body,
            "memo_base": body + " Extra <<1>>.",
            "memo_bear": f"Short bear case <<{n}>>.",
        }

    import backend.graph as graph_module

    original = graph_module.write_memo_stub
    graph_module.write_memo_stub = verbose_write_memo
    try:
        result = _run(_with_claims(many))
    finally:
        graph_module.write_memo_stub = original

    assert result["evaluator_decision"] == "accept"
    assert "truncated to the 4-page cap" in result["memo_rendered"]
    # Sources survive truncation so attribution stays checkable
    assert "## Sources" in result["memo_rendered"]


def test_stub_evaluator_still_available_for_other_tests():
    """The existing graph tests rely on the always-accept stub. Confirm the
    default still gives it, so this change didn't quietly make every other
    graph test pay for a real evaluation."""
    result = _run(_with_claims(), stub_evaluator=None)

    assert result["evaluator_decision"] == "accept"
    assert result["evaluator_iterations"] == 1


def test_semantic_eval_never_switches_on_under_stubs():
    """A test that accidentally reached the network would be slow, costly, and
    flaky. use_stubs must imply no tier-2 call."""
    import backend.nodes.evaluation.support as support_module

    def explode(*a, **k):
        raise AssertionError("tier 2 must not run under use_stubs")

    original = support_module.check_support
    support_module.check_support = explode
    try:
        result = _run(_with_claims())
    finally:
        support_module.check_support = original

    assert result["evaluator_decision"] == "accept"
