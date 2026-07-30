"""
Integration test for fetch_service.fetch_page against real URLs. Not
mocked on purpose -- the point of SP-01 is verified behavior under real
network conditions for each FetchStatus outcome.
"""
import pytest

from backend.services.fetch_service import fetch_page

MIN_TEXT_LENGTH_FOR_TEST = 200

CASES = {
    "ok": "https://techcrunch.com/2023/10/20/tam-sam-som-is-only-for-founders-who-think-small",
    "unreachable": "https://this-domain-absolutely-does-not-exist-xyz123.com",
    "http_error": "https://techcrunch.com/this-page-definitely-does-not-exist-404",
    "no_text_content": "https://www.python.org/static/img/python-logo.png",
}


@pytest.mark.parametrize("expected_status,url", list(CASES.items()))
def test_fetch_page_status(expected_status, url):
    result = fetch_page(url)
    assert result.status == expected_status


def test_fetch_page_ok_returns_text():
    result = fetch_page(CASES["ok"])
    assert result.text is not None
    assert len(result.text) > MIN_TEXT_LENGTH_FOR_TEST
