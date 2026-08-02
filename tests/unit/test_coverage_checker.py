from __future__ import annotations
from datetime import datetime, timezone

from backend.models.categories import REQUIRED_CATEGORIES
from backend.models.claim import Claim
from backend.nodes.supervisor.coverage_checker import check_coverage
from backend.state import State, create_initial_state

# Helpers


def _claim(category: str) -> Claim:
    """Build a valid claim with the given category. Other fields are stubbed."""
    return Claim(
        claim_text=f"Test claim for {category}.",
        source_url="https://example.com/source",
        quoted_snippet=f"Snippet about {category}.",
        specialist="company_intel",
        confidence="reported",
        category=category,
        retrieval_timestamp=datetime.now(tz=timezone.utc),
    )


def _state_with_claims(claims: list[Claim]) -> State:
    """Build a state with the given claims, everything else default."""
    state = create_initial_state("Test Co", "https://example.com")
    state["claims"] = claims
    return state


# three required cases from acceptance criteria

def test_full_coverage():
    """Every required category has a claim: all covered, nothing missing."""
    state = _state_with_claims([_claim(cat) for cat in REQUIRED_CATEGORIES])

    result = check_coverage(state)

    assert set(result["covered_categories"]) == REQUIRED_CATEGORIES
    assert result["missing_categories"] == []


def test_partial_coverage():
    """Some required categories present, some missing."""
    present = list(REQUIRED_CATEGORIES)[:3]
    state = _state_with_claims([_claim(cat) for cat in present])

    result = check_coverage(state)

    assert set(result["covered_categories"]) == set(present)
    assert set(result["missing_categories"]) == REQUIRED_CATEGORIES - set(present)


def test_empty_claims_list():
    """No claims: nothing covered, everything missing."""
    state = _state_with_claims([])

    result = check_coverage(state)

    assert result["covered_categories"] == []
    assert set(result["missing_categories"]) == REQUIRED_CATEGORIES


# Invariants that should always hold

def test_covered_and_missing_are_disjoint():
    """A category can't be both covered and missing."""
    state = _state_with_claims([_claim(cat) for cat in list(REQUIRED_CATEGORIES)[:2]])

    result = check_coverage(state)

    assert set(result["covered_categories"]) & set(result["missing_categories"]) == set()


def test_covered_plus_missing_equals_required():
    """Every required category must appear in exactly one of the two lists."""
    state = _state_with_claims([_claim(cat) for cat in list(REQUIRED_CATEGORIES)[:2]])

    result = check_coverage(state)

    assert set(result["covered_categories"]) | set(result["missing_categories"]) == REQUIRED_CATEGORIES


def test_output_lists_are_sorted():
    """Output should be deterministic; sorted lists make the decision log stable."""
    state = _state_with_claims([_claim(cat) for cat in list(REQUIRED_CATEGORIES)[:3]])

    result = check_coverage(state)

    assert result["covered_categories"] == sorted(result["covered_categories"])
    assert result["missing_categories"] == sorted(result["missing_categories"])


# edge cases


def test_duplicate_claims_in_same_category_still_count_as_covered():
    """Two claims sharing a category still count as one covered category."""
    cat = list(REQUIRED_CATEGORIES)[0]
    state = _state_with_claims([_claim(cat), _claim(cat), _claim(cat)])

    result = check_coverage(state)

    assert cat in result["covered_categories"]
    assert set(result["missing_categories"]) == REQUIRED_CATEGORIES - {cat}


def test_claims_outside_required_categories_are_ignored():
    """A claim in an allowed-but-not-required category doesn't affect coverage."""
    bonus_claim = _claim("market_trends")  # allowed, not required
    required_claim = _claim(list(REQUIRED_CATEGORIES)[0])
    state = _state_with_claims([bonus_claim, required_claim])

    result = check_coverage(state)

    assert "market_trends" not in result["covered_categories"]
    assert list(REQUIRED_CATEGORIES)[0] in result["covered_categories"]


# shape of the return value


def test_returns_only_expected_keys():
    """Node should return only covered_categories and missing_categories."""
    state = _state_with_claims([])

    result = check_coverage(state)

    assert set(result.keys()) == {"covered_categories", "missing_categories"}


def test_returned_values_are_lists_not_sets():
    """State fields are declared as list[str]; make sure we don't return sets."""
    state = _state_with_claims([_claim(list(REQUIRED_CATEGORIES)[0])])

    result = check_coverage(state)

    assert isinstance(result["covered_categories"], list)
    assert isinstance(result["missing_categories"], list)
