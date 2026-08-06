"""
Unit tests for company_intel's pure-Python helper logic. No network, no
LLM calls -- fast and safe for automatic pytest runs. Follows the same
pattern as tests/unit/test_market_intel.py and test_team_signals.py.
"""
from backend.models.claim import Claim
from backend.nodes.company_intel import (
    COMPANY_INTEL_CATEGORIES,
    build_extraction_prompt,
    filter_named_individuals,
    looks_like_named_individual,
)


# --- looks_like_named_individual ---------------------------------------


def test_plain_company_name_is_not_flagged():
    text = "Vezeeta is a digital healthcare booking platform in MENA."
    assert looks_like_named_individual(text) is False


def test_two_capitalized_words_with_no_context_is_not_flagged():
    # "Firebase Crashlytics"-style false positive: two capitalized words
    # alone is not enough, there must be a person-context word nearby.
    text = "Vezeeta Pharmacy is a feature within the main app."
    assert looks_like_named_individual(text) is False


def test_named_individual_with_role_context_is_flagged():
    text = "According to CEO Amira Hassan, the company expanded regionally."
    assert looks_like_named_individual(text) is True


def test_named_individual_with_said_is_flagged():
    text = "Founder Ahmed Helal said the platform now serves five countries."
    assert looks_like_named_individual(text) is True


def test_plain_sentence_with_no_names_is_not_flagged():
    text = "The company offers a mobile app for booking doctors and pharmacies."
    assert looks_like_named_individual(text) is False


# S-03 regression tests: the original filter used loose substring
# matching and wrongly flagged ordinary words like "sector" or
# "hundreds" as person-indicators. These confirm that bug stays fixed.
def test_poc_sentence_sector_is_not_flagged():
    text = "Vezeeta operates in the digital healthcare sector across MENA."
    assert looks_like_named_individual(text) is False


def test_poc_sentence_hundreds_is_not_flagged():
    text = "Vezeeta serves hundreds of clinics and hospitals in the region."
    assert looks_like_named_individual(text) is False


def test_country_names_are_not_flagged_as_people():
    text = "Vezeeta operates in Egypt Saudi Arabia and the United Arab Emirates."
    assert looks_like_named_individual(text) is False


# --- filter_named_individuals --------------------------------------------


def _make_claim(claim_text: str) -> Claim:
    return Claim(
        claim_text=claim_text,
        source_url="https://vezeeta.com/en/generic/aboutus",
        quoted_snippet="a real quote from the page",
        specialist="company_intel",
        confidence="verified",
        category="what_company_does",
    )


def test_filter_keeps_safe_claims():
    claim = _make_claim("Vezeeta is a healthcare booking platform in MENA.")
    safe, dropped = filter_named_individuals([claim])
    assert safe == [claim]
    assert dropped == []


def test_filter_drops_named_individual_claims():
    claim = _make_claim("CEO Amira Hassan said the company is expanding.")
    safe, dropped = filter_named_individuals([claim])
    assert safe == []
    assert dropped == [claim]


def test_filter_handles_mixed_list():
    safe_claim = _make_claim("Vezeeta offers clinic management software.")
    unsafe_claim = _make_claim("Founder Ahmed Helal said revenue doubled.")
    safe, dropped = filter_named_individuals([safe_claim, unsafe_claim])
    assert safe == [safe_claim]
    assert dropped == [unsafe_claim]


def test_filter_handles_empty_list():
    safe, dropped = filter_named_individuals([])
    assert safe == []
    assert dropped == []


# --- build_extraction_prompt ---------------------------------------------


def test_prompt_includes_company_name_and_page_content():
    pages = [{"url": "https://vezeeta.com/about", "content": "Vezeeta is a platform."}]
    prompt = build_extraction_prompt("Vezeeta", pages)
    assert "Vezeeta" in prompt
    assert "https://vezeeta.com/about" in prompt
    assert "Vezeeta is a platform." in prompt


def test_prompt_labels_pages_as_untrusted_data():
    # Safety requirement: untrusted text must be clearly labeled as data
    # to analyze, not instructions to follow.
    pages = [{"url": "https://vezeeta.com/about", "content": "some content"}]
    prompt = build_extraction_prompt("Vezeeta", pages)
    assert "not instructions" in prompt or "DATA TO ANALYZE" in prompt


def test_prompt_forbids_named_individual_claims():
    pages = [{"url": "https://vezeeta.com/about", "content": "some content"}]
    prompt = build_extraction_prompt("Vezeeta", pages)
    assert "named individual" in prompt


# --- COMPANY_INTEL_CATEGORIES sanity check --------------------------------


def test_company_intel_categories_are_exactly_the_expected_three():
    assert set(COMPANY_INTEL_CATEGORIES) == {
        "what_company_does",
        "target_customer",
        "business_model",
    }
