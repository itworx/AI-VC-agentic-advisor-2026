from __future__ import annotations

# every valid category, specialists may return claims in any of these.
ALLOWED_CATEGORIES: frozenset[str] = frozenset(
    {
        # company_intel scope
        "what_company_does",
        "target_customer",
        "business_model",
        # market_intel scope
        "market_size",
        "competitors",
        "market_trends",
        # team_signals scope (company-level only, no named individuals)
        "team_size",
        "founding_year",
        "funding_stage",
        "public_statements",
    }
)

# categories the supervisor requires before triggering memo writing.
# check_coverage compares claims' categories against this set.
REQUIRED_CATEGORIES: frozenset[str] = frozenset(
    {
        "what_company_does",
        "target_customer",
        "market_size",
        "competitors",
        "team_size",
        "funding_stage",
    }
)

# sanity check: REQUIRED must be a subset of ALLOWED, will fail at import time
# if the two sets ever drift out of sync.
assert REQUIRED_CATEGORIES.issubset(ALLOWED_CATEGORIES), (
    "REQUIRED_CATEGORIES contains categories not in ALLOWED_CATEGORIES"
)

# which specialist owns which category, used by the supervisor to pick the
# next specialist based on what's missing from coverage.
SPECIALIST_BY_CATEGORY: dict[str, str] = {
    # company_intel scope
    "what_company_does": "company_intel",
    "target_customer": "company_intel",
    "business_model": "company_intel",
    # market_intel scope
    "market_size": "market_intel",
    "competitors": "market_intel",
    "market_trends": "market_intel",
    # team_signals scope
    "team_size": "team_signals",
    "founding_year": "team_signals",
    "funding_stage": "team_signals",
    "public_statements": "team_signals",
}

# sanity check: every allowed category must have a specialist mapping.
assert set(SPECIALIST_BY_CATEGORY.keys()) == ALLOWED_CATEGORIES, (
    "SPECIALIST_BY_CATEGORY and ALLOWED_CATEGORIES are out of sync"
)
