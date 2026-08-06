"""Pure helpers that turn LangGraph state into UI-ready values.

No Streamlit imports here — everything is unit-testable.
"""
from __future__ import annotations

NODE_ORDER = [
    "screen", "human_approval", "check_coverage", "supervisor",
    "company_intel", "market_intel", "team_signals", "write_memo",
]

SPECIALISTS = ("company_intel", "market_intel", "team_signals")


def derive_node_statuses(values: dict, next_nodes: tuple) -> dict[str, str]:
    """Map every node to done/running/waiting/pending/halted.

    'values' is the latest state snapshot (dict), 'next_nodes' is
    graph.get_state(config).next — the nodes the graph will run next.
    """
    nxt = set(next_nodes or ())
    status = {n: "pending" for n in NODE_ORDER}

    decision = values.get("screening_decision", "")
    if decision == "pass":
        status["screen"] = "done"
    elif decision == "reject":
        status["screen"] = "halted"

    if "human_approval" in nxt:
        status["human_approval"] = "waiting"
    elif decision:  # the pause already resolved (approved, agreed, or overridden)
        status["human_approval"] = "done"

    if values.get("decision_log"):
        status["check_coverage"] = "done"
        status["supervisor"] = "done"
    for node in ("check_coverage", "supervisor"):
        if node in nxt:
            status[node] = "running"

    for sp in SPECIALISTS:
        if sp in values.get("specialists_run", []):
            status[sp] = "done"
        if sp in nxt or (values.get("next_action") == sp
                         and sp not in values.get("specialists_run", [])):
            status[sp] = "running"

    if values.get("memo_base"):
        status["write_memo"] = "done"
    elif "write_memo" in nxt or values.get("next_action") == "write_memo":
        status["write_memo"] = "running"

    return status


def run_pill(values: dict, next_nodes: tuple) -> tuple[str, str]:
    """Top-bar pill: (label, status color key)."""
    if next_nodes and "human_approval" in next_nodes:
        return ("interrupted", "waiting")
    if next_nodes:
        return ("running", "running")
    if values.get("memo_base"):
        return ("complete", "done")
    if values.get("screening_decision") == "reject" or (
        values.get("screening_decision") and not values.get("human_approved")
    ):
        return ("ended · rejected", "halted")
    return ("idle", "pending")


def claims_to_rows(claims: list[dict]) -> list[dict]:
    """Shape claim dicts for st.dataframe (spec section 3.4 columns)."""
    return [
        {
            "Category": c["category"],
            "Claim": c["claim_text"],
            "Specialist": c["specialist"],
            "Conf.": c["confidence"],
            "Source": str(c["source_url"]),
        }
        for c in claims
    ]


def parse_spend(log_text: str, since_iso: str) -> float:
    """Sum cost=$… from logs/costs.log lines at/after 'since_iso'.

    Log line format (backend/utils/cost_logger.py):
    '<iso timestamp> | <node> | input=n | output=n | cost=$0.000000'
    """
    total = 0.0
    for line in log_text.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 5 or not parts[-1].startswith("cost=$"):
            continue
        if parts[0] < since_iso:  # ISO strings compare chronologically
            continue
        try:
            total += float(parts[-1].removeprefix("cost=$"))
        except ValueError:
            continue
    return round(total, 6)
