from __future__ import annotations
from backend.models.categories import SPECIALIST_BY_CATEGORY
from backend.state import State

# stop after this many supervisor turns even if coverage incomplete
ITERATION_CAP = 6

# order specialists are tried in when multiple could help. Deterministic order
# makes the decision log reproducible.
SPECIALIST_ORDER = ["company_intel", "market_intel", "team_signals"]


def supervisor(state: State) -> dict:
    """Decide next action based on coverage and iteration state.

    Returns a state update including:
      next_action: node the graph routes to next (specialist or "write_memo")
      iteration_count: incremented
      decision_log: appended with this turn's decision entry

    Does NOT modify claims, specialists_run, or coverage lists. Those are
    updated by check_coverage after the chosen specialist runs.
    """
    missing = set(state["missing_categories"])
    specialists_already_run = set(state["specialists_run"])
    iteration = state["iteration_count"] + 1

    # stop condition 1: coverage complete, go straight to memo
    if not missing:
        return _decision("write_memo", "coverage complete", missing, iteration)

    # stop condition 2: iteration cap. Cut losses and write memo with what we have
    if iteration >= ITERATION_CAP:
        reason = f"iteration cap {ITERATION_CAP} reached, {len(missing)} categories still missing"
        return _decision("write_memo", reason, missing, iteration)

    # find specialists that could help AND haven't been called yet
    candidates = set()
    for cat in missing:
        specialist = SPECIALIST_BY_CATEGORY.get(cat)
        if specialist and specialist not in specialists_already_run:
            candidates.add(specialist)

    # stop condition 3: all useful specialists have already been called
    if not candidates:
        reason = f"all useful specialists exhausted, {len(missing)} still missing"
        return _decision("write_memo", reason, missing, iteration)

    # pick a specialist in deterministic order
    chosen = next(s for s in SPECIALIST_ORDER if s in candidates)

    # explain why this one: what missing categories does it cover?
    covers = sorted(cat for cat in missing if SPECIALIST_BY_CATEGORY.get(cat) == chosen)
    plural = "category" if len(covers) == 1 else "categories"
    reason = f"{chosen} covers {len(covers)} missing {plural}: {covers}"

    return _decision(chosen, reason, missing, iteration)


def _decision(next_action: str, reason: str, missing: set[str], iteration: int) -> dict:
    """Build a state update dict for the supervisor's decision this turn."""
    return {
        "next_action": next_action,
        "iteration_count": iteration,
        "decision_log": [
            {
                "iteration": iteration,
                "chosen": next_action,
                "reason": reason,
                "missing_categories": sorted(missing),
            }
        ],
    }
