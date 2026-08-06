"""
Unit tests for the evaluator's tier-2 support check (E-01, semantic layer).
Offline: the model is replaced by a fake, because what needs pinning down here
is the plumbing and the failure handling, not the judge's taste.

The load-bearing property is that tier 2 can only ever ADD violations. If a
model verdict could clear a tier-1 finding, an agreeable judge would be able to
wave through a sentence with no citation at all.
"""

import pytest

from backend.models.claim import Claim
from backend.models.memo import MemoDraft
from backend.models.support import SupportVerdict, SupportVerdicts
from backend.nodes.evaluation.evaluate import evaluate_memo, trace_memo
from backend.nodes.evaluation.support import SupportCheckError, check_support


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
    ),
]


class FakeLLM:
    def __init__(self, result):
        self.result = result
        self.last_prompt = None

    def invoke(self, prompt: str):
        self.last_prompt = prompt
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _all_supported(pairs):
    return {i: (True, "") for i in range(len(pairs))}


def _none_supported(pairs):
    return {i: (False, "the claim says nothing about this") for i in range(len(pairs))}


# ------------------------------------------------- evaluate_memo tier interaction


def test_tier_2_off_by_default():
    """No support_checker means no model call and no semantic violations."""
    memo = MemoDraft(
        bull_case="Instabug sells observability software <<1>>.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="Instabug sells observability tooling <<1>>.",
    )
    result = evaluate_memo(memo, CLAIMS)

    assert result.passed
    assert result.violations == []


def test_tier_2_flags_a_marker_sprayed_onto_an_unsupported_sentence():
    """The hole tier 1 cannot see: every marker resolves, so tier 1 passes the
    memo, but the claims say nothing about growth rates or profitability."""
    memo = MemoDraft(
        bull_case="Instabug grows 30% year over year and is profitable <<1>>.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="Instabug sells observability tooling <<1>>.",
    )

    assert trace_memo(memo, CLAIMS).passed  # tier 1 alone sees nothing wrong

    def checker(pairs):
        verdicts = _all_supported(pairs)
        for i, (sentence, _claims) in enumerate(pairs):
            if "profitable" in sentence:
                verdicts[i] = (False, "the claim does not mention growth or profit")
        return verdicts

    result = evaluate_memo(memo, CLAIMS, support_checker=checker)

    assert not result.passed
    flagged = [v for v in result.violations if v.kind == "unsupported_by_claim"]
    assert len(flagged) == 1
    assert "profitable" in flagged[0].sentence
    assert flagged[0].cited_ids == [1]
    assert "does not mention growth or profit" in flagged[0].detail


def test_tier_2_cannot_clear_a_tier_1_violation():
    """An agreeable judge must not be able to unblock an uncited sentence."""
    memo = MemoDraft(
        bull_case="It serves 25,000 customers.",  # no marker at all
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="Instabug sells observability tooling <<1>>.",
    )
    result = evaluate_memo(memo, CLAIMS, support_checker=_all_supported)

    assert not result.passed
    assert any(v.kind == "untraced_factual" for v in result.violations)


def test_tier_2_is_not_asked_about_unresolvable_markers():
    """A sentence citing <<9>> has no claim text to judge against, and tier 1
    already blocks it. Sending it to the judge would invite a verdict on
    nothing."""
    memo = MemoDraft(
        bull_case="Instabug has 400 staff <<9>>.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="Instabug sells observability tooling <<1>>.",
    )
    seen = []

    def checker(pairs):
        seen.extend(sentence for sentence, _ in pairs)
        return _all_supported(pairs)

    result = evaluate_memo(memo, CLAIMS, support_checker=checker)

    assert not any("400 staff" in s for s in seen)
    assert any(v.kind == "unresolved_citation" for v in result.violations)


def test_traced_count_reflects_tier_2_findings():
    memo = MemoDraft(
        bull_case="Instabug sells observability software <<1>>.",
        base_case="The market was worth 2 billion <<2>>.",
        bear_case="Instabug sells observability tooling <<1>>.",
    )
    clean = evaluate_memo(memo, CLAIMS, support_checker=_all_supported)
    dirty = evaluate_memo(memo, CLAIMS, support_checker=_none_supported)

    assert clean.sentences_traced == 3
    assert dirty.sentences_traced == 0
    assert dirty.sentences_checked == 3


def test_a_sentence_flagged_by_both_tiers_is_only_counted_once():
    """weak_support (tier 1) and unsupported_by_claim (tier 2) tend to fire on
    the same sentence, since a marker pointing at the wrong claim usually shares
    no vocabulary with it. Subtracting per-violation instead of recounting
    per-sentence undercounted the traced total - it reported 0/3 for a memo with
    one perfectly good sentence."""
    memo = MemoDraft(
        # cites claim 1 (a product claim) for a market assertion: no shared
        # vocabulary AND not supported, so both tiers flag it
        bull_case="Turnover across the sector reached new highs <<1>>.",
        base_case="Instabug sells observability software <<1>>.",
        bear_case="The market was worth 2 billion dollars in 2024 <<2>>.",
    )

    def checker(pairs):
        return {
            i: (False, "unrelated") if "Turnover" in s else (True, "")
            for i, (s, _) in enumerate(pairs)
        }

    result = evaluate_memo(memo, CLAIMS, support_checker=checker)

    kinds = {v.kind for v in result.violations if v.sentence.startswith("Turnover")}
    assert kinds == {"weak_support", "unsupported_by_claim"}, kinds
    # 3 sentences, exactly 1 of them flagged (twice) -> 2 still traced
    assert result.sentences_checked == 3
    assert result.sentences_traced == 2


def test_judge_sees_only_the_sentence_and_its_cited_claims():
    """It must not see the rest of the memo - surrounding argument is exactly
    what would talk a judge into agreeing."""
    memo = MemoDraft(
        bull_case="Instabug sells observability software <<1>>.",
        base_case="A DISTINCTIVE UNCITED SENTENCE ABOUT NOTHING.",
        bear_case="The market was worth 2 billion <<2>>.",
    )
    captured = []

    def checker(pairs):
        captured.extend(pairs)
        return _all_supported(pairs)

    evaluate_memo(memo, CLAIMS, support_checker=checker)

    sentences = [s for s, _ in captured]
    assert not any("DISTINCTIVE UNCITED" in s for s in sentences)
    for sentence, claims in captured:
        assert len(claims) >= 1
        assert all(isinstance(c, Claim) for c in claims)


# ----------------------------------------------------- check_support plumbing


def test_check_support_maps_verdicts_by_index():
    pairs = [("first sentence", [CLAIMS[0]]), ("second sentence", [CLAIMS[1]])]
    fake = FakeLLM(
        SupportVerdicts(
            verdicts=[
                SupportVerdict(index=2, supported=False, reason="nope"),
                SupportVerdict(index=1, supported=True, reason=""),
            ]
        )
    )

    out = check_support(pairs, llm=fake)

    assert out[0] == (True, "")
    assert out[1][0] is False
    assert out[1][1] == "nope"


def test_check_support_prompt_contains_sentences_and_claim_text():
    pairs = [("a very distinctive sentence", [CLAIMS[0]])]
    fake = FakeLLM(
        SupportVerdicts(verdicts=[SupportVerdict(index=1, supported=True, reason="")])
    )

    check_support(pairs, llm=fake)

    assert "a very distinctive sentence" in fake.last_prompt
    assert CLAIMS[0].claim_text in fake.last_prompt


def test_missing_verdict_defaults_to_unsupported():
    """A judge that fails to answer must not thereby wave a sentence through."""
    pairs = [("first", [CLAIMS[0]]), ("second", [CLAIMS[1]])]
    fake = FakeLLM(
        SupportVerdicts(verdicts=[SupportVerdict(index=1, supported=True, reason="")])
    )

    out = check_support(pairs, llm=fake)

    assert out[0] == (True, "")
    assert out[1][0] is False
    assert "no verdict" in out[1][1]


def test_duplicate_verdicts_default_to_unsupported():
    """Two verdicts for one index means neither can be trusted."""
    pairs = [("first", [CLAIMS[0]])]
    fake = FakeLLM(
        SupportVerdicts(
            verdicts=[
                SupportVerdict(index=1, supported=True, reason=""),
                SupportVerdict(index=1, supported=False, reason="actually no"),
            ]
        )
    )

    out = check_support(pairs, llm=fake)

    assert out[0][0] is False
    assert "conflicting" in out[0][1]


def test_out_of_range_verdict_index_is_ignored():
    pairs = [("first", [CLAIMS[0]])]
    fake = FakeLLM(
        SupportVerdicts(
            verdicts=[
                SupportVerdict(index=7, supported=True, reason=""),
                SupportVerdict(index=1, supported=True, reason=""),
            ]
        )
    )

    out = check_support(pairs, llm=fake)

    assert set(out) == {0}
    assert out[0] == (True, "")


def test_empty_pairs_makes_no_call():
    fake = FakeLLM(RuntimeError("should never be invoked"))
    assert check_support([], llm=fake) == {}
    assert fake.last_prompt is None


def test_call_failure_raises_support_check_error():
    pairs = [("first", [CLAIMS[0]])]
    fake = FakeLLM(RuntimeError("connection reset"))

    with pytest.raises(SupportCheckError, match="connection reset"):
        check_support(pairs, llm=fake)


def test_empty_verdict_list_raises_rather_than_passing_everything():
    pairs = [("first", [CLAIMS[0]])]
    fake = FakeLLM(SupportVerdicts(verdicts=[]))

    with pytest.raises(SupportCheckError, match="no verdicts"):
        check_support(pairs, llm=fake)
