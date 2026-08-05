"""
M-01/M-02 live check: write_memo against the real model. Requires
OPENROUTER_API_KEY. Not part of the fast suite - run explicitly:

    pytest tests/manual/test_write_memo_live.py -v -s

Uses a small, realistic claims list (Instabug-like) so a human can actually
read the output and judge whether bull/base/bear differ in substance, not
just check assertions - see M-02's own instruction (I-05: "read every
passing memo as if you were a partner").
"""

from backend.models.claim import Claim
from backend.nodes.memo.render_citations import build_final_memo, render_citations
from backend.nodes.memo.write_memo import assert_cases_differ, write_memo

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


def test_write_memo_live_produces_readable_output():
    memo = write_memo(SAMPLE_CLAIMS)

    assert_cases_differ(memo)  # will raise if bull/base/bear cite identically

    final = build_final_memo(memo, SAMPLE_CLAIMS)

    print("\n\n===== FINAL MEMO =====\n")
    print(final)
    print("\n=======================\n")

    assert "[1]" in final or "[2]" in final  # at least some citation resolved
    assert "## Sources" in final
