"""
Unit tests for the evaluator (E-01 / E-02 / E-03). Fast and fully offline -
the evaluator makes no model calls at all, which is the point of building it
in pure Python, so there is no fake LLM to inject here.

Coverage:
  E-01  sentence splitting, marker resolution, the four violation kinds
  E-02  feedback names the offending sentences verbatim
  E-03  the cap stops the rewrite loop, including end-to-end through a graph
"""

import pytest
from langgraph.graph import END, START, StateGraph

from backend.models.claim import Claim
from backend.models.memo import MemoDraft
from backend.nodes.evaluation.evaluate import (
    EVALUATOR_CAP,
    evaluate,
    format_feedback,
    route_from_evaluate,
    split_sentences,
    trace_memo,
)
from backend.state import State, create_initial_state


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
        confidence="reported",
    ),
    _claim(
        claim_text="Sentry and Datadog are competitors in observability.",
        category="competitors",
        confidence="reported",
    ),
]


def _state(memo: MemoDraft, claims=CLAIMS, iterations=0, rendered="rendered memo body") -> State:
    state = create_initial_state("Instabug", "https://instabug.com")
    state["claims"] = [c.model_dump(mode="json") for c in claims]
    state["memo_bull"] = memo.bull_case
    state["memo_base"] = memo.base_case
    state["memo_bear"] = memo.bear_case
    state["memo_rendered"] = rendered
    state["evaluator_iterations"] = iterations
    return state


# ---------------------------------------------------------------- E-01: splitting


def test_split_sentences_basic():
    assert split_sentences("First one <<1>>. Second one <<2>>.") == [
        "First one <<1>>.",
        "Second one <<2>>.",
    ]


def test_split_does_not_break_on_decimals_or_currency():
    """A split inside "$1.2 billion" would produce two half-sentences and
    report the second half as untraced. Classic false positive."""
    text = "The market reached $1.2 billion in 2024 <<2>>."
    assert split_sentences(text) == ["The market reached $1.2 billion in 2024 <<2>>."]


def test_split_does_not_break_on_abbreviations_or_initials():
    text = "It sells in the U.S. and the U.K. <<1>>. Growth is steady <<2>>."
    assert split_sentences(text) == [
        "It sells in the U.S. and the U.K. <<1>>.",
        "Growth is steady <<2>>.",
    ]


def test_split_drops_headings_and_keeps_bullets():
    """An unsourced figure hiding in a bullet with no terminal punctuation is
    exactly what this evaluator is for - it must not be skipped."""
    text = "## Bull case\n- 40% YoY growth\n- Strong retention <<1>>."
    assert split_sentences(text) == ["40% YoY growth", "Strong retention <<1>>."]


def test_split_ignores_blank_lines():
    assert split_sentences("\n\nOne <<1>>.\n\n\nTwo <<2>>.\n") == [
        "One <<1>>.",
        "Two <<2>>.",
    ]


# --------------------------------------------------------------- E-01: tracing


def test_fully_cited_memo_passes():
    memo = MemoDraft(
        bull_case="Instabug sells observability software <<1>>.",
        base_case="The market was worth 2 billion in 2024 <<2>>.",
        bear_case="Sentry and Datadog compete in observability <<3>>.",
    )
    result = trace_memo(memo, CLAIMS)

    assert result.passed
    assert result.violations == []
    assert result.sentences_checked == 3
    assert result.sentences_traced == 3


def test_untraced_figure_is_blocking():
    """The core requirement: an invented number with no citation is rejected."""
    memo = MemoDraft(
        bull_case="Instabug sells observability software <<1>>. It serves 25,000 customers.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="Sentry competes <<3>>.",
    )
    result = trace_memo(memo, CLAIMS)

    assert not result.passed
    kinds = [v.kind for v in result.violations]
    assert kinds == ["untraced_factual"]
    assert result.violations[0].sentence == "It serves 25,000 customers."
    assert result.violations[0].section == "bull_case"


def test_citation_outside_claims_range_is_blocking():
    """A marker pointing at nothing reads as sourced to a human. Worse than
    no marker, so it can never be advisory."""
    memo = MemoDraft(
        bull_case="Instabug has 400 employees <<9>>.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="Sentry competes <<3>>.",
    )
    result = trace_memo(memo, CLAIMS)

    assert not result.passed
    violation = result.violations[0]
    assert violation.kind == "unresolved_citation"
    assert violation.cited_ids == [9]
    assert "<<9>>" in violation.detail
    assert "<<1>> to <<3>>" in violation.detail


def test_uncited_company_fact_with_no_numbers_is_blocking():
    """Regression from the second live run. This sentence has no digits, no
    currency and no finance vocabulary, but it is squarely a claim about what
    the company does. The earlier factual-keyword allowlist scored it as merely
    advisory - see _META_PATTERNS for why the default was inverted."""
    memo = MemoDraft(
        bull_case=(
            "Instabug provides mobile app monitoring and bug reporting tools "
            "for developers, giving it a clear and verified product identity."
        ),
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="Sentry competes <<3>>.",
    )
    result = trace_memo(memo, CLAIMS)

    assert not result.passed
    assert result.violations[0].kind == "untraced_factual"


def test_meta_sentence_about_the_memo_is_advisory_not_blocking():
    """write_memo.txt permits unmarked sentences about the memo's own
    reasoning. Rejecting them would make the evaluator fight our own prompt."""
    memo = MemoDraft(
        bull_case="Instabug sells observability software <<1>>. Consider the following.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="The bear case rests on what the claims do not tell us.",
    )
    result = trace_memo(memo, CLAIMS)

    assert result.passed  # not blocking
    assert [v.kind for v in result.violations] == ["untraced", "untraced"]
    assert result.violations[0].sentence == "Consider the following."


def test_meta_exemption_does_not_cover_a_figure():
    """The quantitative check runs first, so meta phrasing can't launder a
    number: "the bear case rests on 40% churn" still needs a source."""
    memo = MemoDraft(
        bull_case="Instabug sells observability software <<1>>.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="The bear case rests on 40% annual churn.",
    )
    result = trace_memo(memo, CLAIMS)

    assert not result.passed
    assert result.violations[0].kind == "untraced_factual"


def test_absence_statement_needs_no_citation():
    """"Team size was not found" is what the memo SHOULD say when no claim
    covers it. There is no claim to cite for a gap."""
    memo = MemoDraft(
        bull_case="Instabug sells observability software <<1>>.",
        base_case="Team size is not publicly disclosed among the claims gathered.",
        bear_case="Sentry competes <<3>>.",
    )
    result = trace_memo(memo, CLAIMS)

    assert result.passed
    assert result.violations == []


def test_bear_case_gap_statement_naming_data_categories_is_allowed():
    """Regression from the first live run: this exact sentence shape was
    false-positived as untraced_factual because "revenue" is a factual keyword,
    even though the sentence is asserting the ABSENCE of revenue data - which
    is precisely what a bear case is supposed to do."""
    memo = MemoDraft(
        bull_case="Instabug sells observability software <<1>>.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case=(
            "Absent verified data on customer count, revenue, or team scale, "
            "the bear case rests on the compounding uncertainty created by "
            "these gaps."
        ),
    )
    result = trace_memo(memo, CLAIMS)

    assert result.passed
    assert result.violations == []


@pytest.mark.parametrize(
    "sentence",
    [
        "There is no basis to assess operational maturity.",
        "Headcount is undisclosed.",
        "No verified figure for revenue exists.",
        "Team scale could not be established.",
        "Market share is not covered in the claims gathered.",
        # each of the next three came from a live run that the previous
        # literal-phrase version of this rule false-positived on
        "The absence of any traction or financial claims is itself a risk signal.",
        "Absent verified data on customer count, revenue, or team scale, conviction is hard.",
        "Funding history and revenue remain unreported.",
        "There is a lack of transparency around operational metrics.",
        "Without disclosed figures, the growth trajectory is unknown.",
    ],
)
def test_gap_statement_phrasings_are_allowed(sentence):
    memo = MemoDraft(
        bull_case="Instabug sells observability software <<1>>.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case=sentence,
    )
    assert trace_memo(memo, CLAIMS).passed, f"false positive on: {sentence}"


@pytest.mark.parametrize(
    "sentence",
    [
        # negation word present, but paired with a subject rather than with
        # information language - these are assertions about the company
        "Absent serious competitors, Instabug dominates the market.",
        "No rival product matches its integration depth.",
        "Without competition, margins expand steadily.",
        "Nothing constrains its expansion into adjacent segments.",
    ],
)
def test_absence_wording_does_not_exempt_a_real_assertion(sentence):
    """The gap rule pairs a negation word with INFORMATION language for exactly
    this reason. A bare "absent"/"no"/"without" would wave through unsourced
    assertions that merely happen to start with one."""
    memo = MemoDraft(
        bull_case=sentence,
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="Sentry competes <<3>>.",
    )
    result = trace_memo(memo, CLAIMS)

    assert not result.passed, f"loophole: {sentence}"
    assert result.violations[0].kind == "untraced_factual"


def test_absence_window_does_not_reach_across_a_sentence_boundary():
    """The negation and the information word have to be in the SAME sentence.
    Splitting happens first, so this is really a guard on the 60-char window
    never containing . ! or ?."""
    memo = MemoDraft(
        bull_case="Nothing is certain. Instabug dominates the enterprise segment.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="Sentry competes <<3>>.",
    )
    result = trace_memo(memo, CLAIMS)

    blocking = [v for v in result.violations if v.blocking]
    assert any("dominates" in v.sentence for v in blocking)


def test_figure_dressed_up_as_an_absence_statement_is_still_blocking():
    """The absence exemption must not become a loophole: digits beat the
    "not disclosed" phrasing."""
    memo = MemoDraft(
        bull_case="Revenue is around 40 million, though not publicly disclosed.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="Sentry competes <<3>>.",
    )
    result = trace_memo(memo, CLAIMS)

    assert not result.passed
    assert result.violations[0].kind == "untraced_factual"


def test_citation_unrelated_to_its_claim_is_flagged_as_weak_support():
    memo = MemoDraft(
        bull_case="Regulatory tailwinds favour European deployment options <<1>>.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="Sentry competes <<3>>.",
    )
    result = trace_memo(memo, CLAIMS)

    assert result.passed  # advisory only - overlap is a hint, not proof
    assert [v.kind for v in result.violations] == ["weak_support"]
    assert result.violations[0].cited_ids == [1]


# ------------------------------------------------------------- E-02: feedback


def test_feedback_names_the_offending_sentences_verbatim():
    memo = MemoDraft(
        bull_case="It serves 25,000 customers.",
        base_case="Instabug sells observability software <<1>>.",
        bear_case="Headcount is roughly 400 people.",
    )
    result = trace_memo(memo, CLAIMS)
    feedback = format_feedback(result, CLAIMS)

    assert "REJECTED" in feedback
    assert "It serves 25,000 customers." in feedback
    assert "Headcount is roughly 400 people." in feedback
    assert "bull_case" in feedback and "bear_case" in feedback
    # tells the model the valid marker range so it can't "fix" it with <<9>>
    assert "<<1>> to <<3>>" in feedback


def test_feedback_separates_advisory_from_blocking():
    memo = MemoDraft(
        bull_case="It serves 25,000 customers. Consider the following.",
        base_case="Instabug sells observability software <<1>>.",
        bear_case="Sentry competes <<3>>.",
    )
    result = trace_memo(memo, CLAIMS)
    feedback = format_feedback(result, CLAIMS)

    assert "1 sentence(s) do not trace" in feedback
    assert "not blocking on their own" in feedback


# ------------------------------------------------- the node: routing + E-03 cap


def test_node_accepts_clean_memo():
    memo = MemoDraft(
        bull_case="Instabug sells observability software <<1>>.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="Sentry competes <<3>>.",
    )
    update = evaluate(_state(memo))

    assert update["evaluator_decision"] == "accept"
    assert update["evaluator_feedback"] == ""
    assert update["evaluator_iterations"] == 1


def test_node_never_writes_memo_text():
    """This node judges; render_citations presents. If evaluate started
    producing memo text, the rendering order that keeps an unresolved <<N>>
    from crashing the renderer would be back in play."""
    memo = MemoDraft(
        bull_case="Instabug sells observability software <<1>>.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="Sentry competes <<3>>.",
    )
    for iterations in (0, EVALUATOR_CAP - 1):
        update = evaluate(_state(memo, iterations=iterations))
        assert "memo_rendered" not in update
        assert "memo_bull" not in update


def test_node_rejects_and_asks_for_a_rewrite_on_the_first_pass():
    memo = MemoDraft(
        bull_case="It serves 25,000 customers.",
        base_case="Instabug sells observability software <<1>>.",
        bear_case="Sentry competes <<3>>.",
    )
    update = evaluate(_state(memo, iterations=0))

    assert update["evaluator_decision"] == "rewrite"
    assert "It serves 25,000 customers." in update["evaluator_feedback"]
    assert update["evaluator_iterations"] == 1
    # the un-truncated memo is left alone: it's about to be rewritten anyway
    assert "memo_rendered" not in update


def test_node_stops_at_the_cap():
    """E-03. At the cap we accept rather than loop. The warning banner that
    stops such a memo leaving here looking clean is render_citations_node's job
    - see test_memo_pipeline_graph.py."""
    memo = MemoDraft(
        bull_case="It serves 25,000 customers.",
        base_case="Instabug sells observability software <<1>>.",
        bear_case="Sentry competes <<3>>.",
    )
    update = evaluate(_state(memo, iterations=EVALUATOR_CAP - 1))

    assert update["evaluator_decision"] == "accept_capped"
    assert update["evaluator_iterations"] == EVALUATOR_CAP
    # feedback is retained on state so the banner and a human can both use it
    assert "It serves 25,000 customers." in update["evaluator_feedback"]


def test_node_records_violations_on_state_for_later_inspection():
    memo = MemoDraft(
        bull_case="It serves 25,000 customers.",
        base_case="Instabug sells observability software <<1>>.",
        bear_case="Sentry competes <<3>>.",
    )
    update = evaluate(_state(memo))

    assert len(update["evaluator_violations"]) == 1
    assert update["evaluator_violations"][0]["kind"] == "untraced_factual"


def test_node_accepts_immediately_when_there_are_no_claims():
    """write_memo_node short-circuits to a placeholder when claims is empty.
    Routing that to "rewrite" would call write_memo with zero claims, which
    raises by design."""
    memo = MemoDraft(
        bull_case="[no claims collected - nothing to write]",
        base_case="[no claims collected - nothing to write]",
        bear_case="[no claims collected - nothing to write]",
    )
    update = evaluate(_state(memo, claims=[]))

    assert update["evaluator_decision"] == "accept"
    assert "nothing to trace" in update["evaluator_feedback"]


# ------------------------------------------- E-03 end to end: the loop terminates


def test_rewrite_loop_terminates_at_the_cap():
    """A model that never fixes its untraced sentences must not spin forever.
    Wires the real evaluate node to a write_memo that stubbornly re-emits the
    same bad draft, and asserts the graph still ends.
    """
    drafts_written = []

    def stubborn_write_memo(state: State) -> dict:
        drafts_written.append(state.get("evaluator_feedback", ""))
        return {
            "memo_bull": "It serves 25,000 customers.",  # never gets a marker
            "memo_base": "Instabug sells observability software <<1>>.",
            "memo_bear": "Sentry competes <<3>>.",
            "memo_rendered": "rendered body",
        }

    builder = StateGraph(State)
    builder.add_node("write_memo", stubborn_write_memo)
    builder.add_node("evaluate", evaluate)
    builder.add_edge(START, "write_memo")
    builder.add_edge("write_memo", "evaluate")
    builder.add_conditional_edges(
        "evaluate",
        route_from_evaluate,
        {"write_memo": "write_memo", "render_citations": END},
    )
    graph = builder.compile()

    result = graph.invoke(_state(MemoDraft(bull_case="x", base_case="x", bear_case="x")))

    assert result["evaluator_iterations"] == EVALUATOR_CAP
    assert result["evaluator_decision"] == "accept_capped"
    assert len(drafts_written) == EVALUATOR_CAP  # first draft + one rewrite
    assert drafts_written[0] == ""  # first pass gets no feedback
    assert "It serves 25,000 customers." in drafts_written[1]  # rewrite does


def test_router_only_loops_on_an_explicit_rewrite():
    state = create_initial_state("x", "https://x.com")
    for decision, expected in [
        ("rewrite", "write_memo"),
        ("accept", "render_citations"),
        ("accept_capped", "render_citations"),
        ("", "render_citations"),
    ]:
        state["evaluator_decision"] = decision
        assert route_from_evaluate(state) == expected


def test_evaluator_cap_matches_the_brief():
    assert EVALUATOR_CAP == 2
