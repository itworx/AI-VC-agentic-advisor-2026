"""
E-01/E-02/E-03 live check: the evaluator against a REAL memo from the real
model. Requires OPENROUTER_API_KEY. Not part of the fast suite - and note
pyproject's addopts ignores tests/manual, so override it to run:

    pytest tests/manual/test_evaluate_live.py -v -s -o addopts=""

The unit tests (tests/unit/test_evaluate.py) prove the evaluator's logic
against hand-written memos. They cannot prove the two things that only show up
against a live model:

  1. Does a real draft actually PASS? An evaluator that rejects every genuine
     memo is worse than none - it would burn the E-03 cap every run and ship
     everything with a warning banner. This is the false-positive check.
  2. Does the E-02 feedback actually WORK? Naming the offending sentences is
     only useful if the model then fixes them. This is the loop check.

Claims are duplicated from test_write_memo_live.py rather than imported -
tests/manual has no __init__.py, and each manual test staying self-contained
matches how that one is written.
"""

import re

from backend.models.claim import Claim
from backend.models.memo import MemoDraft
from backend.nodes.evaluation.evaluate import (
    EVALUATOR_CAP,
    evaluate_memo,
    format_feedback,
    split_sentences,
    trace_memo,
)
from backend.nodes.evaluation.support import check_support
from backend.nodes.memo.render_citations import render_citations
from backend.nodes.memo.write_memo import write_memo

SAMPLE_CLAIMS = [
    Claim(
        claim_text="Instabug provides mobile app monitoring and bug reporting tools for developers.",
        source_url="https://instabug.com",
        quoted_snippet="Mobile app monitoring and bug reporting platform.",
        specialist="company_intel",
        confidence="verified",
        category="what_company_does",
    ),
    Claim(
        claim_text="Instabug's customers are mobile app development teams at enterprises.",
        source_url="https://instabug.com/customers",
        quoted_snippet="Trusted by leading mobile teams.",
        specialist="company_intel",
        confidence="verified",
        category="target_customer",
    ),
    Claim(
        claim_text="Instabug has not publicly disclosed headcount.",
        source_url="https://instabug.com/about",
        quoted_snippet="not found",
        specialist="team_signals",
        confidence="reported",
        category="team_size",
    ),
    Claim(
        claim_text="The mobile DevOps/observability tooling market is estimated in the low billions of dollars.",
        source_url="https://example.com/market-report",
        quoted_snippet="market estimated at several billion dollars",
        specialist="market_intel",
        confidence="inferred",
        category="market_size",
    ),
]


def _report(label: str, result) -> None:
    print(f"\n----- {label} -----")
    print(
        f"{result.sentences_traced}/{result.sentences_checked} sentences traced | "
        f"passed={result.passed} | "
        f"{len(result.blocking_violations)} blocking, "
        f"{len(result.advisory_violations)} advisory"
    )
    for v in result.violations:
        flag = "BLOCKING" if v.blocking else "advisory"
        print(f"  [{flag}] {v.section} / {v.kind}")
        print(f"      {v.sentence!r}")
        print(f"      -> {v.detail}")


def test_real_memo_converges_within_the_evaluator_cap():
    """False-positive check, framed as convergence rather than first-pass
    perfection.

    An earlier version of this test asserted the first draft must trace
    cleanly. It doesn't, reliably - the real model tends to write one bare
    evaluative summary per run ("The opportunity is real, but the evidence base
    is incomplete."), and the evaluator is right to block it: "the opportunity
    is real" is a conclusion about the company and should rest on cited claims.

    Needing one rewrite is the system working, not failing - that is what the
    E-03 budget is for. What would be a real problem is not converging inside
    it, or the first draft failing so widely that the evaluator is obviously
    over-strict. Both are what this asserts.
    """
    memo = write_memo(SAMPLE_CLAIMS)
    first = trace_memo(memo, SAMPLE_CLAIMS)

    print("\n\n===== REAL MEMO (draft 1) =====\n")
    print(render_citations(memo, SAMPLE_CLAIMS))
    _report("PASS 1", first)

    assert first.sentences_checked > 5, "suspiciously few sentences - check the split"
    assert len(first.blocking_violations) <= 2, (
        f"{len(first.blocking_violations)} blocking violations on a genuine "
        f"first draft. A rewrite or two is expected; this many suggests the "
        f"evaluator is over-strict or the prompt is out of sync with it"
    )

    if first.passed:
        print("\nfirst draft traced cleanly - no rewrite needed")
        return

    # One rewrite, which is all EVALUATOR_CAP=2 allows.
    revised = write_memo(SAMPLE_CLAIMS, feedback=format_feedback(first, SAMPLE_CLAIMS))
    second = trace_memo(revised, SAMPLE_CLAIMS)
    _report("PASS 2 (after the one permitted rewrite)", second)

    print("\n\n===== REAL MEMO (draft 2) =====\n")
    print(render_citations(revised, SAMPLE_CLAIMS))

    assert second.passed, (
        f"did not converge within EVALUATOR_CAP={EVALUATOR_CAP}: still "
        f"{len(second.blocking_violations)} blocking after the rewrite, so a "
        f"live run would ship as accept_capped with a warning banner"
    )


def test_evaluator_feedback_makes_the_real_model_fix_a_real_draft():
    """Loop check (E-02 -> write_memo -> E-01 again).

    Takes a real draft and strips one citation marker off a factual sentence,
    which is precisely the failure this evaluator exists to catch. Then feeds
    the real E-02 feedback back to the real model and re-evaluates.
    """
    memo = write_memo(SAMPLE_CLAIMS)

    # Manufacture an untraced sentence by stripping EVERY marker off one
    # sentence. Stripping just the first marker in the section isn't enough:
    # the prompt asks summary sentences to cite every claim they draw on, so a
    # sentence routinely carries several and would still trace after losing one.
    target = next(
        (s for s in split_sentences(memo.base_case) if "<<" in s),
        None,
    )
    assert target is not None, "no citation marker found in base_case to strip"
    stripped = re.sub(r"\s*<<\d+>>", "", target)
    assert target in memo.base_case, "sentence splitter altered the text"

    damaged = MemoDraft(
        bull_case=memo.bull_case,
        base_case=memo.base_case.replace(target, stripped, 1),
        bear_case=memo.bear_case,
    )
    print(f"\n----- SENTENCE DAMAGED -----\n{stripped}")

    first = trace_memo(damaged, SAMPLE_CLAIMS)
    _report("PASS 1 (marker stripped)", first)
    assert not first.passed, (
        "stripping a citation off a factual sentence did not trigger a "
        "blocking violation - the factual-signal heuristic missed it"
    )

    feedback = format_feedback(first, SAMPLE_CLAIMS)
    print("\n----- E-02 FEEDBACK SENT TO THE MODEL -----")
    print(feedback)

    revised = write_memo(SAMPLE_CLAIMS, feedback=feedback)
    second = trace_memo(revised, SAMPLE_CLAIMS)
    _report("PASS 2 (after rewrite)", second)

    print("\n\n===== REVISED MEMO =====\n")
    print(render_citations(revised, SAMPLE_CLAIMS))

    assert second.passed, (
        f"the model still had {len(second.blocking_violations)} untraced "
        f"sentence(s) after being given the feedback. With EVALUATOR_CAP="
        f"{EVALUATOR_CAP} this run would ship as accept_capped with a warning"
    )


# ------------------------------------------------ tier 2: the semantic layer


def test_tier_2_catches_a_marker_sprayed_onto_an_unsupported_sentence():
    """The hole tier 1 structurally cannot see, against the real judge.

    Every marker below resolves, so tier 1 passes all three sentences. Only a
    semantic check can tell that two of them say things their claims don't.
    """
    memo = MemoDraft(
        # legitimate paraphrase - must NOT be flagged, or the layer is useless
        bull_case="Instabug provides observability tooling for mobile developers <<1>>.",
        # asserts profitability and retention, which claim 1 says nothing about
        base_case="Instabug is profitable and retains 95% of its customers <<1>>.",
        # cites the product claim for a market-size assertion: wrong claim
        bear_case="The observability market was worth two billion dollars <<1>>.",
    )

    assert trace_memo(memo, SAMPLE_CLAIMS).passed, "tier 1 should see nothing wrong"

    result = evaluate_memo(memo, SAMPLE_CLAIMS, support_checker=check_support)
    _report("TIER 1 + TIER 2", result)

    flagged = {
        v.section for v in result.violations if v.kind == "unsupported_by_claim"
    }
    assert "base_case" in flagged, "missed an unsupported profitability/retention claim"
    assert "bear_case" in flagged, "missed a citation pointing at the wrong claim"
    assert "bull_case" not in flagged, (
        "flagged a legitimate paraphrase - the judge is too strict and every "
        "real memo would burn rework cycles"
    )
    assert not result.passed


# ------------------------------- generalisation: more than one claim set


FINTECH_CLAIMS = [
    Claim(
        claim_text="Paymob processes online and in-store payments for merchants in Egypt.",
        source_url="https://paymob.com",
        quoted_snippet="Payment infrastructure for merchants.",
        specialist="company_intel",
        confidence="verified",
        category="what_company_does",
    ),
    Claim(
        claim_text="Paymob's customers are small and medium merchants accepting digital payments.",
        source_url="https://paymob.com/merchants",
        quoted_snippet="Built for growing businesses.",
        specialist="company_intel",
        confidence="verified",
        category="target_customer",
    ),
    Claim(
        claim_text="Fawry and Opay are competitors in Egyptian digital payments.",
        source_url="https://example.com/egypt-fintech",
        quoted_snippet="competitors include Fawry and Opay",
        specialist="market_intel",
        confidence="reported",
        category="competitors",
    ),
    Claim(
        claim_text="Paymob has not publicly disclosed its funding stage.",
        source_url="https://paymob.com/about",
        quoted_snippet="not found",
        specialist="team_signals",
        confidence="reported",
        category="funding_stage",
    ),
]

DEVTOOL_CLAIMS = [
    Claim(
        claim_text="Rasa provides an open-source framework for building conversational assistants.",
        source_url="https://rasa.com",
        quoted_snippet="Open source conversational AI framework.",
        specialist="company_intel",
        confidence="verified",
        category="what_company_does",
    ),
    Claim(
        claim_text="Rasa targets enterprise engineering teams building customer service automation.",
        source_url="https://rasa.com/enterprise",
        quoted_snippet="Built for enterprise teams.",
        specialist="company_intel",
        confidence="verified",
        category="target_customer",
    ),
    Claim(
        claim_text="The conversational AI tooling market is contested by large cloud vendors.",
        source_url="https://example.com/conversational-ai",
        quoted_snippet="dominated by large cloud providers",
        specialist="market_intel",
        confidence="inferred",
        category="competitors",
    ),
]

# Deliberately thin, in the spirit of the brief's thin-information edge case:
# almost nothing is known, so a correct memo is mostly explicit gaps.
THIN_CLAIMS = [
    Claim(
        claim_text="Northwind Analytics describes itself as a data analytics company.",
        source_url="https://northwind-analytics.test",
        quoted_snippet="A data analytics company.",
        specialist="company_intel",
        confidence="verified",
        category="what_company_does",
    ),
    Claim(
        claim_text="Northwind Analytics has not publicly disclosed its team size.",
        source_url="https://northwind-analytics.test",
        quoted_snippet="not found",
        specialist="team_signals",
        confidence="reported",
        category="team_size",
    ),
]

CLAIM_SETS = [
    ("instabug (observability)", SAMPLE_CLAIMS),
    ("paymob (fintech)", FINTECH_CLAIMS),
    ("rasa (devtool)", DEVTOOL_CLAIMS),
    ("northwind (thin info)", THIN_CLAIMS),
]


def test_converges_across_several_different_claim_sets():
    """Generalisation check.

    Both exemption lists in the evaluator (gap statements, meta sentences) are
    phrase allowlists, and both were extended in response to a single live run
    on a single company. That is exactly the shape of a heuristic tuned to one
    sample. This runs four unrelated claim sets - including a deliberately thin
    one, where a correct memo is mostly explicit gaps - through the FULL check
    (both tiers) and requires every one of them to converge inside the E-03
    budget.

    A failure here names the claim set and the sentences that blocked, which is
    the information needed to decide whether the evaluator or the prompt is
    wrong. It is not a flake to be re-run.
    """
    failures = []
    summary = []

    for label, claims in CLAIM_SETS:
        print(f"\n\n########## {label} ##########")
        memo = write_memo(claims)
        first = evaluate_memo(memo, claims, support_checker=check_support)
        _report(f"{label} - PASS 1", first)

        if first.passed:
            summary.append(f"{label}: clean on draft 1")
            continue

        revised = write_memo(claims, feedback=format_feedback(first, claims))
        second = evaluate_memo(revised, claims, support_checker=check_support)
        _report(f"{label} - PASS 2", second)

        if second.passed:
            summary.append(f"{label}: clean after 1 rewrite")
        else:
            summary.append(
                f"{label}: STILL BLOCKED after {EVALUATOR_CAP} passes "
                f"({len(second.blocking_violations)})"
            )
            failures.append(
                (label, [v.sentence for v in second.blocking_violations])
            )

    print("\n\n===== CONVERGENCE SUMMARY =====")
    for line in summary:
        print(f"  {line}")

    assert not failures, (
        "these claim sets did not converge within the evaluator cap, so a live "
        f"run would ship them with a warning banner: {failures}"
    )


# ----------------------------- tier 2 detection rate (the measured unknown)

# Labelled probes against SAMPLE_CLAIMS, which state only: (1) what Instabug
# does, (2) who its customers are, (3) that headcount is NOT disclosed, (4) that
# the market is in the low billions.
#
# Every sentence below carries a RESOLVABLE marker, so tier 1 passes all of them.
# Tier 2 is the only thing that can tell these two groups apart, which makes this
# the measurement of whether tier 2 earns its place. Ordered roughly from blatant
# to subtle.
FABRICATIONS = [
    ("blatant count", "Instabug serves over 25,000 companies <<1>>."),
    ("profitability", "Instabug is profitable <<1>>."),
    ("wrong claim subject", "The observability market is worth two billion dollars <<1>>."),
    ("growth rate", "The observability market is growing 30% annually <<4>>."),
    ("retention", "Instabug's enterprise customers renew at above-average rates <<2>>."),
    ("founding date", "Instabug has served enterprise teams since 2014 <<2>>."),
    ("named integrations", "Instabug integrates with Jira and Slack <<1>>."),
    # Directly contradicts claim 3, which says headcount is undisclosed
    ("contradicts its claim", "Instabug's headcount is under 100 employees <<3>>."),
    ("invented pricing", "Instabug is priced per seat with volume discounts <<1>>."),
    ("invented funding", "Instabug raised a Series B to fund enterprise expansion <<2>>."),
]

LEGITIMATE = [
    ("paraphrase", "Instabug provides observability tooling for mobile developers <<1>>."),
    ("interpretation", "Instabug's product addresses a recurring pain point for mobile teams <<1>>."),
    (
        "far-reaching interpretation",
        "The enterprise focus positions Instabug for durable, high-value relationships <<2>>.",
    ),
    (
        "gap statement plus cited fact",
        "Headcount is undisclosed <<3>>, so operational scale cannot be assessed.",
    ),
    ("hedged reasoning", "The market size suggests meaningful room for growth <<4>>."),
    (
        "multi-claim synthesis",
        "A verified product aimed at enterprise mobile teams in a low-billions market is a coherent pairing <<1>> <<2>> <<4>>.",
    ),
    (
        "absence commentary",
        "The absence of traction data <<3>> makes the investment case hard to underwrite.",
    ),
]


def test_tier_2_detection_and_false_positive_rate():
    """Measures the number I could not previously report: how often tier 2
    actually catches a fabrication, and how often it cries wolf.

    Both groups pass tier 1 by construction - every marker resolves - so this
    isolates tier 2's own judgement. A catch rate near zero would mean the layer
    is decorative; a false-positive rate above roughly one in seven would mean
    every real memo burns rework cycles on sentences that were fine.
    """
    probes = [(label, s, True) for label, s in FABRICATIONS] + [
        (label, s, False) for label, s in LEGITIMATE
    ]

    # One sentence per section per probe would be 17 memos; instead judge them
    # all in one batch, which is also how the node does it.
    pairs = []
    for _label, sentence, _is_fab in probes:
        ids = [int(n) for n in re.findall(r"<<(\d+)>>", sentence)]
        pairs.append((sentence, [SAMPLE_CLAIMS[i - 1] for i in ids]))

    verdicts = check_support(pairs)

    caught, missed, false_alarms, correct_passes = [], [], [], []
    for i, (label, sentence, is_fabrication) in enumerate(probes):
        supported, reason = verdicts[i]
        flagged = not supported
        if is_fabrication and flagged:
            caught.append((label, reason))
        elif is_fabrication and not flagged:
            missed.append((label, sentence))
        elif not is_fabrication and flagged:
            false_alarms.append((label, sentence, reason))
        else:
            correct_passes.append(label)

    print("\n\n===== TIER 2 DETECTION RATE =====")
    print(f"fabrications caught:  {len(caught)}/{len(FABRICATIONS)}")
    for label, reason in caught:
        print(f"    caught   {label}: {reason}")
    for label, sentence in missed:
        print(f"    MISSED   {label}: {sentence}")
    print(f"\nlegitimate passed:    {len(correct_passes)}/{len(LEGITIMATE)}")
    for label, sentence, reason in false_alarms:
        print(f"    FALSE ALARM {label}: {sentence}\n        -> {reason}")

    # Thresholds chosen to be meaningful rather than merely passable: a layer
    # that caught half of these would not be worth a model call.
    assert len(caught) >= 8, (
        f"tier 2 only caught {len(caught)}/{len(FABRICATIONS)} fabrications. "
        f"Missed: {[m[0] for m in missed]}"
    )
    assert len(false_alarms) <= 1, (
        f"tier 2 raised {len(false_alarms)} false alarms on legitimate memo "
        f"sentences, which would burn rework cycles every run: "
        f"{[f[0] for f in false_alarms]}"
    )
