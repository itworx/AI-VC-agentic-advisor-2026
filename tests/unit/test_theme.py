from frontend import theme


def test_status_triples_match_design_spec():
    assert theme.STATUS["done"].dot == "#0F8A6D"
    assert theme.STATUS["done"].bg == "#EAF6F2"
    assert theme.STATUS["running"].dot == "#B26A00"
    assert theme.STATUS["running"].text == "#8A5200"
    assert theme.STATUS["waiting"].dot == "#5348B8"
    assert theme.STATUS["waiting"].border == "#C6C0EC"
    assert theme.STATUS["pending"].dot == "#C2C9D2"
    assert theme.STATUS["halted"].dot == "#B3261E"
    assert theme.STATUS["halted"].bg == "#FDEDEC"


def test_all_statuses_present_and_complete():
    assert set(theme.STATUS) == {"done", "running", "waiting", "pending", "halted"}
    for s in theme.STATUS.values():
        for value in s:
            assert value.startswith("#") and len(value) == 7


def test_css_embeds_fonts_and_pulse():
    assert "IBM Plex Mono" in theme.GLOBAL_CSS
    assert "pulseDot" in theme.GLOBAL_CSS
