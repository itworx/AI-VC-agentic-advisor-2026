"""
Unit tests for team_signals's pure-Python helper logic. No network, no
LLM calls -- fast and safe for automatic pytest runs.
"""
from backend.nodes.team_signals import (
    build_search_queries,
    dedupe_by_url,
    interleave,
    looks_like_named_individual,
)


def test_named_individual_without_role_context_is_still_flagged():
    # No "CEO"/"founder"/"said" nearby -- market_intel's loosened filter
    # would miss this, which is exactly why team_signals uses the strict
    # version instead: this hard rule can't tolerate a false negative.
    text = "Sarah Ahmed has worked at the company since 2018."
    assert looks_like_named_individual(text) is True


def test_named_individual_with_role_context_is_flagged():
    text = "According to CEO Jane Doe, the company grew revenue 40% last year."
    assert looks_like_named_individual(text) is True


def test_plain_headcount_sentence_is_not_flagged():
    text = "The company has approximately 150 employees as of 2025."
    assert looks_like_named_individual(text) is False


def test_plain_funding_sentence_is_not_flagged():
    text = "The company raised a Series B round in 2023."
    assert looks_like_named_individual(text) is False


def test_build_search_queries_covers_all_targeted_sources():
    queries = build_search_queries("Instabug", "https://instabug.com")
    assert queries["general"] == "Instabug company employees founded funding stage"
    assert queries["techcrunch"] == "Instabug site:techcrunch.com"
    assert queries["about_careers"] == "Instabug about team careers site:instabug.com"


def test_dedupe_by_url_removes_duplicates():
    hits = [{"url": "https://a.com"}, {"url": "https://a.com"}, {"url": "https://b.com"}]
    assert len(dedupe_by_url(hits)) == 2


def test_interleave_round_robins_across_sources():
    general = [{"url": "g1"}, {"url": "g2"}]
    about = [{"url": "a1"}]
    result = interleave([general, about])
    assert [h["url"] for h in result] == ["g1", "a1", "g2"]
