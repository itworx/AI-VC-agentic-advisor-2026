from frontend.canvas import build_dot


def test_dot_contains_all_nodes_and_edges():
    statuses = {n: "pending" for n in (
        "screen", "human_approval", "check_coverage", "supervisor",
        "company_intel", "market_intel", "team_signals", "write_memo")}
    dot = build_dot(statuses, {})
    for node in statuses:
        assert node in dot
    assert "screen -> human_approval" in dot
    assert "supervisor -> market_intel" in dot
    assert "market_intel -> check_coverage" in dot   # the loop back
    assert "write_memo" in dot
    assert "rankdir=LR" in dot


def test_dot_colors_follow_status():
    statuses = {n: "pending" for n in (
        "screen", "human_approval", "check_coverage", "supervisor",
        "company_intel", "market_intel", "team_signals", "write_memo")}
    statuses["screen"] = "done"
    statuses["human_approval"] = "waiting"
    dot = build_dot(statuses, {"screen": "pass · 1.8s"})
    assert 'fillcolor="#EAF6F2"' in dot   # done tint
    assert 'fillcolor="#EFEDFB"' in dot   # waiting tint
    assert "pass · 1.8s" in dot
