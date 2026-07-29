"""
Required and allowed claim categories.

ALLOWED_CATEGORIES: every category a claim may have. The Claim schema
validates category against this set, so a specialist cannot invent a new
category without updating this file.

REQUIRED_CATEGORIES: subset of ALLOWED_CATEGORIES that the supervisor treats
as necessary for the memo. check_coverage compares the categories of
accumulated claims against this set to decide whether more research is needed.
"""

from __future__ import annotations

# Every valid category. Specialists may return claims in any of these.
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

# Categories the supervisor requires before triggering memo writing.
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

# Sanity check: REQUIRED must be a subset of ALLOWED. Fails at import time
# if the two sets ever drift out of sync.
assert REQUIRED_CATEGORIES.issubset(ALLOWED_CATEGORIES), (
    "REQUIRED_CATEGORIES contains categories not in ALLOWED_CATEGORIES"
)