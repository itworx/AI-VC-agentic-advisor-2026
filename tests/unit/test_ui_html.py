from frontend.ui import (
    coverage_chip_html, decision_entry_html, pill_html, rail_row_html,
)


def test_pill_uses_status_triple():
    html = pill_html("interrupted", "waiting")
    assert "#EFEDFB" in html and "#C6C0EC" in html and "#4438A8" in html
    assert "interrupted" in html
    assert "pulseDot" in html          # waiting pills pulse


def test_done_pill_does_not_pulse():
    assert "pulseDot" not in pill_html("complete", "done")


def test_rail_row_active_gets_tint():
    html = rail_row_html("market_intel", "running", "14s", active=True)
    assert "market_intel" in html and "14s" in html
    assert "#FDF3E3" in html           # running tint background


def test_coverage_chip_states():
    covered = coverage_chip_html("market_size", covered=True)
    missing = coverage_chip_html("competitors", covered=False)
    assert "#EAF6F2" in covered and "#0B7259" in covered
    assert "#EAF6F2" not in missing


def test_decision_entry_shows_iteration_and_reason():
    html = decision_entry_html(
        {"iteration": 2, "chosen": "market_intel", "reason": "covers 2"},
        latest=True,
    )
    assert "iter 2 → market_intel" in html and "covers 2" in html
