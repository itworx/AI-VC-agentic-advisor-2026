"""
Unit tests for render_citations / enforce_page_cap - pure Python, no model
calls, no network. These are the fastest, cheapest tests in the memo
pipeline since there's nothing to mock.
"""

import pytest

from backend.models.claim import Claim
from backend.models.memo import MemoDraft
from backend.nodes.memo.render_citations import (
    MAX_BODY_WORDS,
    SOURCES_HEADING,
    UnresolvedCitationError,
    build_final_memo,
    enforce_page_cap,
    render_citations,
)


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


def test_markers_renumbered_first_appearance_order():
    claims = [_claim(claim_text=f"Claim {i}.") for i in range(1, 4)]
    # bear_case cites claim 3 first, before bull/base ever mention it -
    # but reading order is fixed bull->base->bear, so claim 3 should still
    # get whatever number it earns from THAT order, not from appearing
    # "first" in bear_case alone.
    memo = MemoDraft(
        bull_case="Uses claim one <<1>>.",
        base_case="Uses claim two <<2>>.",
        bear_case="Uses claim three <<3>> and claim one again <<1>>.",
    )

    rendered = render_citations(memo, claims)

    assert "[1]" in rendered  # claim 1, first seen in bull_case
    assert "[2]" in rendered  # claim 2, first seen in base_case
    assert "[3]" in rendered  # claim 3, first seen in bear_case
    assert "<<" not in rendered  # no raw markers should survive


def test_sources_section_lists_claim_text_and_url():
    claims = [_claim(claim_text="Instabug sells observability tools.", source_url="https://instabug.com/product")]
    memo = MemoDraft(bull_case="<<1>>", base_case="no citation here", bear_case="none here either")

    rendered = render_citations(memo, claims)

    assert SOURCES_HEADING.strip() in rendered
    assert "Instabug sells observability tools." in rendered
    assert "https://instabug.com/product" in rendered


def test_inferred_claim_marked_in_sources():
    claims = [_claim(claim_text="Market size is roughly $2B.", confidence="inferred", category="market_size")]
    memo = MemoDraft(bull_case="<<1>>", base_case="x", bear_case="x")

    rendered = render_citations(memo, claims)

    sources_section = rendered.split(SOURCES_HEADING)[1]
    assert "[inferred]" in sources_section
    assert "*[1] Market size is roughly $2B." in sources_section  # italicized


def test_verified_claim_not_marked_inferred():
    claims = [_claim(confidence="verified")]
    memo = MemoDraft(bull_case="<<1>>", base_case="x", bear_case="x")

    rendered = render_citations(memo, claims)
    sources_section = rendered.split(SOURCES_HEADING)[1]

    assert "[inferred]" not in sources_section


def test_unresolved_citation_raises():
    claims = [_claim()]  # only claim 1 exists
    memo = MemoDraft(bull_case="<<1>> and <<5>>.", base_case="x", bear_case="x")

    with pytest.raises(UnresolvedCitationError):
        render_citations(memo, claims)


def test_no_citations_at_all_still_renders_sources_heading():
    claims = [_claim()]
    memo = MemoDraft(bull_case="no markers", base_case="no markers", bear_case="no markers")

    rendered = render_citations(memo, claims)
    assert SOURCES_HEADING.strip() in rendered


def test_page_cap_no_op_under_budget():
    short_memo = "## Bull case\nShort text." + SOURCES_HEADING + "[1] source"
    assert enforce_page_cap(short_memo) == short_memo


def test_page_cap_truncates_body_only():
    long_body = "## Bull case\n" + ("word " * (MAX_BODY_WORDS + 100))
    memo_text = long_body + SOURCES_HEADING + "[1] Instabug — https://instabug.com"

    result = enforce_page_cap(memo_text)

    assert "truncated to the" in result
    assert "[1] Instabug — https://instabug.com" in result  # sources intact
    body_part = result.split(SOURCES_HEADING)[0]
    assert len(body_part.split()) < MAX_BODY_WORDS + 50  # truncated, allowing for the notice text


def test_page_cap_handles_memo_with_no_sources_section():
    long_body = "word " * (MAX_BODY_WORDS + 50)
    result = enforce_page_cap(long_body)
    assert "truncated to the" in result


def test_build_final_memo_end_to_end():
    claims = [_claim(claim_text="Instabug is B2B developer tooling.")]
    memo = MemoDraft(
        bull_case="Strong fit <<1>>.",
        base_case="Reasonable fit <<1>>.",
        bear_case="Some risk, unrelated to claim.",
    )

    result = build_final_memo(memo, claims)

    assert "[1]" in result
    assert "Instabug is B2B developer tooling." in result
    assert "truncated" not in result  # short memo, shouldn't hit the cap
