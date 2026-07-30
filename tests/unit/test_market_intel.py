"""
Unit tests for market_intel's pure-Python helper logic. No network, no
LLM calls -- fast and safe for automatic pytest runs.
"""
from backend.nodes.market_intel import (
    build_search_queries,
    dedupe_by_url,
    interleave,
    looks_like_named_individual,
)


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


def test_build_search_queries_covers_all_five_sources():
    queries = build_search_queries("Instabug", "https://instabug.com")
    assert queries["general"] == "Instabug market size competitors -site:instabug.com"
    assert queries["techcrunch"] == "Instabug site:techcrunch.com"
    assert queries["g2"] == "Instabug alternatives competitors site:g2.com"
    assert queries["sec_edgar"] == "Instabug site:sec.gov/Archives/edgar/data"


def test_dedupe_by_url_removes_duplicates_and_keeps_first():
    hits = [
        {"url": "https://a.com", "content": "first"},
        {"url": "https://b.com", "content": "second"},
        {"url": "https://a.com", "content": "duplicate, should be dropped"},
    ]
    deduped = dedupe_by_url(hits)
    assert len(deduped) == 2
    assert deduped[0]["content"] == "first"


def test_dedupe_by_url_skips_missing_urls():
    hits = [{"content": "no url here"}, {"url": "https://a.com", "content": "kept"}]
    deduped = dedupe_by_url(hits)
    assert len(deduped) == 1
    assert deduped[0]["url"] == "https://a.com"


def test_interleave_round_robins_across_sources():
    general = [{"url": "g1"}, {"url": "g2"}, {"url": "g3"}]
    g2_source = [{"url": "s1"}]
    result = interleave([general, g2_source])
    # g2_source's one item must appear early, not pushed to the end where
    # a downstream cap on total results could cut it off entirely.
    urls = [h["url"] for h in result]
    assert urls == ["g1", "s1", "g2", "g3"]


def test_interleave_handles_empty_source():
    result = interleave([[{"url": "a"}], []])
    assert [h["url"] for h in result] == ["a"]
