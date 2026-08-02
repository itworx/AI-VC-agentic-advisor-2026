from __future__ import annotations

from backend.models.categories import REQUIRED_CATEGORIES
from backend.state import State


def check_coverage(state: State) -> dict:
    """
    Compute which required categories are covered by accumulated claims.
    Writes two sorted lists back into state:
      covered_categories: required categories with at least one claim
      missing_categories: required categories with zero claims
    """

    claim_categories = {c.category for c in state["claims"]}

    covered = REQUIRED_CATEGORIES & claim_categories
    missing = REQUIRED_CATEGORIES - claim_categories

    return {
        "covered_categories": sorted(covered),
        "missing_categories": sorted(missing),
    }