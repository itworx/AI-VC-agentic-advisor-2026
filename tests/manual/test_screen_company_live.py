"""
SC-02, live version: screen_company against the real thesis and the real
OpenRouter model. Requires OPENROUTER_API_KEY in .env. Not part of the fast
suite - run explicitly:

    pytest tests/manual/test_screen_company_live.py -v
"""

from backend.nodes.screening.screen_company import screen_company

VAGUE_REASONS = {"not a good fit", "doesn't fit", "doesn't seem right"}


def _describe(name: str, website: str) -> str:
    return f"Company name: {name}\nWebsite: {website}"


def test_reject_swvl_example_b():
    result = screen_company(_describe("Swvl", "https://www.swvl.com"))

    assert result.decision == "reject"
    assert result.reason.strip().lower() not in VAGUE_REASONS
    combined = (" ".join(result.matched_criteria) + " " + result.reason).lower()
    assert any(kw in combined for kw in ["consumer", "b2b", "series", "stage"]), result


def test_reject_figma_rejects_on_thesis_not_quality():
    """companies.json: Figma tests that the agent rejects on thesis fit even
    though it's a very strong company - not because it's impressive."""
    result = screen_company(_describe("Figma", "https://www.figma.com"))

    assert result.decision == "reject"
    combined = (" ".join(result.matched_criteria) + " " + result.reason).lower()
    assert "stage" in combined or "series" in combined, result


def test_vezeeta_flags_its_own_uncertainty():
    """companies.json's designed ambiguous case - no fixed expected decision.
    What's graded is whether the reason shows the model flagging its own
    uncertainty rather than deciding confidently either way."""
    result = screen_company(_describe("Vezeeta", "https://www.vezeeta.com"))

    combined = (" ".join(result.matched_criteria) + " " + result.reason).lower()
    hedge_words = ["ambig", "border", "could", "either", "uncertain", "unclear", "arguab"]
    assert any(w in combined for w in hedge_words), result
