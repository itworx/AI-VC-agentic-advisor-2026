"""
Unit tests for write_memo - fast, offline, injected fake LLM. Tests plumbing
(claims reach the prompt, empty-claims guard, the assert_cases_differ
backstop) - not whether the real model's writing is any good. That's
tests/manual/test_write_memo_live.py.
"""

import pytest

from backend.models.claim import Claim
from backend.models.memo import MemoDraft
from backend.nodes.memo.write_memo import (
    assert_cases_differ,
    citation_ids_used,
    write_memo,
)


class FakeLLM:
    def __init__(self, result: MemoDraft):
        self.result = result
        self.last_prompt = None

    def invoke(self, prompt: str) -> MemoDraft:
        self.last_prompt = prompt
        return self.result


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


def test_empty_claims_raises():
    with pytest.raises(ValueError, match="zero claims"):
        write_memo([], llm=FakeLLM(MemoDraft(bull_case="x", base_case="x", bear_case="x")))


def test_claims_reach_the_prompt():
    claims = [_claim(claim_text="A very distinctive marker sentence about the company.")]
    fake = FakeLLM(MemoDraft(bull_case="<<1>>", base_case="<<1>>", bear_case="<<1>>"))

    write_memo(claims, llm=fake)

    assert "A very distinctive marker sentence about the company." in fake.last_prompt
    assert "<<1>>" in fake.last_prompt


def test_multiple_claims_numbered_in_order():
    claims = [
        _claim(claim_text="First claim text."),
        _claim(claim_text="Second claim text.", category="market_size"),
    ]
    fake = FakeLLM(MemoDraft(bull_case="x", base_case="x", bear_case="x"))

    write_memo(claims, llm=fake)

    first_pos = fake.last_prompt.index("First claim text.")
    second_pos = fake.last_prompt.index("Second claim text.")
    assert "<<1>>" in fake.last_prompt
    assert "<<2>>" in fake.last_prompt
    assert first_pos < second_pos


def test_citation_ids_used():
    text = "Some claim <<1>>. Another point <<3>>. Repeated <<1>> again."
    assert citation_ids_used(text) == {1, 3}


def test_assert_cases_differ_raises_on_identical_citations():
    memo = MemoDraft(
        bull_case="Great company <<1>> <<2>>.",
        base_case="Decent company <<3>>.",
        bear_case="Risky company <<1>> <<2>>.",  # same set as bull_case
    )
    with pytest.raises(ValueError, match="cite the exact same claims"):
        assert_cases_differ(memo)


def test_assert_cases_differ_passes_on_distinct_citations():
    memo = MemoDraft(
        bull_case="Great company <<1>> <<2>>.",
        base_case="Decent company <<1>> <<3>>.",
        bear_case="Risky company <<4>>.",
    )
    assert_cases_differ(memo) is None  # should not raise


def test_assert_cases_differ_ignores_cases_with_no_citations():
    """Two empty citation sets shouldn't false-positive against each other -
    'and' in the check requires ids_a to be non-empty."""
    memo = MemoDraft(bull_case="No claims here.", base_case="Also none.", bear_case="<<1>>")
    assert_cases_differ(memo) is None
