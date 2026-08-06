import os

from streamlit.testing.v1 import AppTest


def test_app_boots_and_shows_run_form(tmp_path, monkeypatch):
    monkeypatch.setenv("VC_UI_STUBS", "1")
    monkeypatch.setenv("VC_UI_DB", str(tmp_path / "smoke.db"))
    at = AppTest.from_file("frontend/app.py", default_timeout=30)
    at.run()
    assert not at.exception
    assert len(at.text_input) >= 2      # company name + website
    assert any("Start run" in b.label for b in at.button)


def test_start_run_pauses_and_shows_interrupted(tmp_path, monkeypatch):
    monkeypatch.setenv("VC_UI_STUBS", "1")
    monkeypatch.setenv("VC_UI_DB", str(tmp_path / "smoke2.db"))
    at = AppTest.from_file("frontend/app.py", default_timeout=60)
    at.run()
    at.text_input[0].set_value("Acme").run()
    at.text_input[1].set_value("https://acme.test").run()
    next(b for b in at.button if "Start run" in b.label).click().run()
    assert not at.exception
    body = " ".join(md.value for md in at.markdown)
    assert "interrupted" in body        # pill shows the HITL pause
