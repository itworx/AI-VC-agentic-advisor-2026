from __future__ import annotations
from backend.models.categories import REQUIRED_CATEGORIES, SPECIALIST_BY_CATEGORY
from backend.nodes.supervisor.supervisor import (
    ITERATION_CAP,
    SPECIALIST_ORDER,
    supervisor,
)
from backend.state import State, create_initial_state


# helper

def _state(
    missing: list[str] | None = None,
    specialists_run: list[str] | None = None,
    iteration: int = 0,
) -> State:
    """Build a state configured for supervisor testing."""
    s = create_initial_state("Test Co", "https://example.com")
    s["missing_categories"] = missing or []
    s["specialists_run"] = specialists_run or []
    s["iteration_count"] = iteration
    return s


# stop conditions

def test_coverage_complete_routes_to_memo():
    """No missing categories: go write the memo."""
    state = _state(missing=[])

    result = supervisor(state)

    assert result["next_action"] == "write_memo"
    assert "coverage complete" in result["decision_log"][0]["reason"]


def test_iteration_cap_routes_to_memo_even_if_missing():
    """At the iteration cap: cut losses and write memo with what we have."""
    state = _state(
        missing=["market_size", "team_size"],
        iteration=ITERATION_CAP - 1,  # so incrementing hits the cap
    )

    result = supervisor(state)

    assert result["next_action"] == "write_memo"
    assert "iteration cap" in result["decision_log"][0]["reason"]


def test_all_specialists_exhausted_routes_to_memo():
    """If every useful specialist has already run, go to memo."""
    state = _state(
        missing=["market_size"],  # market_intel covers this
        specialists_run=["market_intel"],  # but market_intel already ran
    )

    result = supervisor(state)

    assert result["next_action"] == "write_memo"
    assert "exhausted" in result["decision_log"][0]["reason"]


# specialist selection

def test_picks_company_intel_when_only_its_categories_missing():
    """Missing only company_intel categories: picks company_intel."""
    state = _state(missing=["what_company_does", "target_customer"])

    result = supervisor(state)

    assert result["next_action"] == "company_intel"


def test_picks_market_intel_when_only_its_categories_missing():
    """Missing only market_intel categories: picks market_intel."""
    state = _state(missing=["market_size", "competitors"])

    result = supervisor(state)

    assert result["next_action"] == "market_intel"


def test_picks_team_signals_when_only_its_categories_missing():
    """Missing only team_signals categories: picks team_signals."""
    state = _state(missing=["team_size", "funding_stage"])

    result = supervisor(state)

    assert result["next_action"] == "team_signals"


def test_deterministic_order_when_multiple_specialists_could_help():
    """When multiple specialists could help, pick in SPECIALIST_ORDER."""
    # missing categories span all three specialists
    state = _state(missing=["what_company_does", "market_size", "team_size"])

    result = supervisor(state)

    # SPECIALIST_ORDER puts company_intel first
    assert result["next_action"] == SPECIALIST_ORDER[0]
    assert result["next_action"] == "company_intel"


def test_skips_specialist_that_already_ran():
    """If the first-in-order specialist ran, pick the next available one."""
    state = _state(
        missing=["what_company_does", "market_size"],
        specialists_run=["company_intel"],  # already tried company_intel
    )

    result = supervisor(state)

    assert result["next_action"] == "market_intel"


# decision log and iteration tracking

def test_decision_log_gets_one_entry_per_call():
    """Each supervisor call appends exactly one entry to decision_log."""
    state = _state(missing=["what_company_does"])

    result = supervisor(state)

    assert len(result["decision_log"]) == 1


def test_decision_log_entry_has_expected_fields():
    """Each decision log entry has iteration, chosen, reason, missing_categories."""
    state = _state(missing=["market_size"], iteration=2)

    result = supervisor(state)
    entry = result["decision_log"][0]

    assert set(entry.keys()) == {"iteration", "chosen", "reason", "missing_categories"}
    assert entry["iteration"] == 3  # incremented from 2
    assert entry["chosen"] == "market_intel"
    assert entry["missing_categories"] == ["market_size"]
    assert isinstance(entry["reason"], str) and len(entry["reason"]) > 0


def test_iteration_count_increments_by_one():
    """Supervisor advances iteration by 1 each turn."""
    state = _state(missing=["market_size"], iteration=2)

    result = supervisor(state)

    assert result["iteration_count"] == 3


def test_reason_names_covered_categories_when_picking_specialist():
    """The reason string should mention which missing categories the pick covers."""
    state = _state(missing=["market_size", "competitors"])

    result = supervisor(state)

    assert "market_intel" in result["decision_log"][0]["reason"]
    assert "market_size" in result["decision_log"][0]["reason"]
    assert "competitors" in result["decision_log"][0]["reason"]

# sanity check on the specialist mapping


def test_every_required_category_has_a_specialist():
    """Every required category must map to one of the known specialists."""
    for cat in REQUIRED_CATEGORIES:
        assert cat in SPECIALIST_BY_CATEGORY
        assert SPECIALIST_BY_CATEGORY[cat] in SPECIALIST_ORDER
