from frontend.run_state import (
    NODE_ORDER, claims_to_rows, derive_node_statuses, parse_spend, run_pill,
)


def _values(**overrides):
    base = {
        "screening_decision": "", "screening_reason": "", "human_approved": False,
        "human_notes": "", "claims": [], "covered_categories": [],
        "missing_categories": [], "specialists_run": [], "not_found": [],
        "decision_log": [], "iteration_count": 0, "next_action": "",
        "memo_base": "",
    }
    base.update(overrides)
    return base


def test_node_order_matches_graph():
    assert NODE_ORDER == [
        "screen", "human_approval", "check_coverage", "supervisor",
        "company_intel", "market_intel", "team_signals", "write_memo",
    ]


def test_hitl_pause_state_frame_1a():
    v = _values(screening_decision="pass")
    s = derive_node_statuses(v, ("human_approval",))
    assert s["screen"] == "done"
    assert s["human_approval"] == "waiting"
    assert s["check_coverage"] == "pending"
    assert run_pill(v, ("human_approval",)) == ("interrupted", "waiting")


def test_specialist_running_frame_1b():
    v = _values(
        screening_decision="pass", human_approved=True,
        specialists_run=["company_intel"], next_action="market_intel",
        iteration_count=2,
        decision_log=[{"iteration": 1, "chosen": "company_intel", "reason": "r",
                       "missing_categories": []}],
    )
    s = derive_node_statuses(v, ("market_intel",))
    assert s["company_intel"] == "done"
    assert s["market_intel"] == "running"
    assert s["supervisor"] == "done"
    assert run_pill(v, ("market_intel",)) == ("running", "running")


def test_reject_end_frame_1c():
    v = _values(screening_decision="reject", human_approved=True)
    s = derive_node_statuses(v, ())
    assert s["screen"] == "halted"
    assert s["write_memo"] == "pending"
    assert run_pill(v, ()) == ("ended · rejected", "halted")


def test_complete_frame_1d():
    v = _values(screening_decision="pass", human_approved=True,
                memo_base="memo text", specialists_run=["company_intel"])
    s = derive_node_statuses(v, ())
    assert s["write_memo"] == "done"
    assert run_pill(v, ()) == ("complete", "done")


def test_claims_to_rows():
    rows = claims_to_rows([{
        "category": "market_size", "claim_text": "APM market is USD 7.7B.",
        "specialist": "market_intel", "confidence": "reported",
        "source_url": "https://grandviewresearch.com/apm",
        "quoted_snippet": "…", "retrieval_timestamp": "2026-08-05T09:00:00Z",
    }])
    assert rows == [{
        "Category": "market_size", "Claim": "APM market is USD 7.7B.",
        "Specialist": "market_intel", "Conf.": "reported",
        "Source": "https://grandviewresearch.com/apm",
    }]


def test_parse_spend_sums_only_lines_after_start():
    log = (
        "2026-08-05T08:00:00 | screen | input=10 | output=5 | cost=$0.002000\n"
        "2026-08-05T10:00:00 | screen | input=10 | output=5 | cost=$0.004000\n"
        "2026-08-05T10:05:00 | market_intel | input=99 | output=9 | cost=$0.057000\n"
        "garbage line without cost\n"
    )
    assert parse_spend(log, "2026-08-05T09:00:00") == 0.061
    assert parse_spend("", "2026-08-05T09:00:00") == 0.0
