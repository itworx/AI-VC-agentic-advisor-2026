"""
Unit tests for market_intel's pure-Python helper logic. No network, no
LLM calls -- fast and safe for automatic pytest runs.
"""
from backend.nodes.market_intel import build_search_query, looks_like_named_individual


def test_plain_competitor_name_is_not_flagged():
    text = (
        "Firebase Crashlytics is considered a main direct competitor to "
        "Instabug in mobile observability."
    )
    assert looks_like_named_individual(text) is False


def test_multiple_competitor_names_are_not_flagged():
    text = (
        "New Relic, Datadog, and Dynatrace compete indirectly with "
        "Instabug in high-end mobile APM."
    )
    assert looks_like_named_individual(text) is False


def test_named_individual_with_role_context_is_flagged():
    text = "According to CEO Jane Doe, the company grew revenue 40% last year."
    assert looks_like_named_individual(text) is True


def test_named_individual_with_said_is_flagged():
    text = "Founder John Smith said the market is growing quickly."
    assert looks_like_named_individual(text) is True


def test_plain_sentence_with_no_names_is_not_flagged():
    text = "The market size for mobile observability tools is growing rapidly."
    assert looks_like_named_individual(text) is False


def test_build_search_query_strips_protocol_and_path():
    query = build_search_query("Instabug", "https://instabug.com")
    assert query == "Instabug market size competitors -site:instabug.com"
