"""
Unit tests for claim_verifier (S-01). No network, no LLM calls.
"""
from backend.models.claim import Claim
from backend.services.claim_verifier import verify_claims

PAGES = [
    {"url": "https://example.com/article", "content": "Acme Corp raised a $2M seed round in 2023."},
]


def make_claim(source_url: str, quoted_snippet: str, confidence: str = "reported") -> Claim:
    return Claim(
        claim_text="Acme Corp raised a $2M seed round.",
        source_url=source_url,
        quoted_snippet=quoted_snippet,
        specialist="market_intel",
        confidence=confidence,
        category="market_size",
    )


def test_claim_with_real_url_and_real_quote_is_verified_unchanged():
    claim = make_claim("https://example.com/article", "Acme Corp raised a $2M seed round in 2023.")
    verified, rejected = verify_claims([claim], PAGES)
    assert len(verified) == 1
    assert len(rejected) == 0
    assert verified[0].confidence == "reported"


def test_claim_with_fabricated_url_is_rejected():
    claim = make_claim("https://not-a-real-fetched-page.com", "Acme Corp raised a $2M seed round in 2023.")
    verified, rejected = verify_claims([claim], PAGES)
    assert len(verified) == 0
    assert len(rejected) == 1


def test_claim_with_real_url_but_wrong_quote_is_downgraded_to_inferred():
    claim = make_claim("https://example.com/article", "This exact sentence does not appear on the page.")
    verified, rejected = verify_claims([claim], PAGES)
    assert len(verified) == 1
    assert len(rejected) == 0
    assert verified[0].confidence == "inferred"


def test_trailing_slash_mismatch_does_not_cause_a_false_rejection():
    # Pydantic's HttpUrl appends a trailing slash to bare-domain URLs;
    # Tavily often returns the bare form. Both must be treated as equal.
    pages = [{"url": "https://instabug.com/", "content": "Instabug was founded in 2014."}]
    claim = make_claim("https://instabug.com", "Instabug was founded in 2014.")
    verified, rejected = verify_claims([claim], pages)
    assert len(verified) == 1
    assert len(rejected) == 0
