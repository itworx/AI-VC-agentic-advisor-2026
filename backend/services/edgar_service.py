"""
SEC EDGAR lookup (data.sec.gov). Free, unauthenticated, but SEC requires a
descriptive User-Agent header and a rate limit of <=10 req/sec.

Only returns data for companies that are SEC filers -- most private VC
targets will not be found there, which is expected and not an error; it
just means this source contributes nothing for that company.
"""
from typing import Optional

import requests

EDGAR_USER_AGENT = "AI-VC-agentic-advisor-2026 intern-project@itworx.com"
_HEADERS = {"User-Agent": EDGAR_USER_AGENT}

_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

_ticker_cache: Optional[dict] = None


def _load_ticker_map() -> dict:
    global _ticker_cache
    if _ticker_cache is not None:
        return _ticker_cache
    try:
        response = requests.get(_TICKERS_URL, headers=_HEADERS, timeout=10)
        response.raise_for_status()
        _ticker_cache = response.json()
    except requests.exceptions.RequestException as e:
        print(f"[edgar_service] failed to load ticker list: {e}")
        _ticker_cache = {}
    return _ticker_cache


def lookup_cik_by_name(company_name: str) -> Optional[str]:
    tickers = _load_ticker_map()
    name_lower = company_name.lower()
    for entry in tickers.values():
        if name_lower in entry.get("title", "").lower():
            return str(entry["cik_str"]).zfill(10)
    return None


def get_company_submissions(cik: str) -> Optional[dict]:
    try:
        response = requests.get(
            _SUBMISSIONS_URL.format(cik=cik), headers=_HEADERS, timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[edgar_service] submissions fetch failed: {e}")
        return None


def format_submissions_as_text(company_name: str, submissions: dict) -> str:
    lines = [
        f"Company: {submissions.get('name', company_name)}",
        f"SIC description: {submissions.get('sicDescription', 'unknown')}",
    ]
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    if forms:
        lines.append("Recent SEC filings:")
        for form, date in list(zip(forms, dates))[:10]:
            lines.append(f"  {form} filed {date}")
    return "\n".join(lines)


def find_company_facts(company_name: str) -> Optional[str]:
    """Best-effort: look up a company by name and return its public filing
    metadata as text, if it's an SEC filer at all. Returns None if not
    found -- expected for most private companies, not an error."""
    cik = lookup_cik_by_name(company_name)
    if not cik:
        return None
    submissions = get_company_submissions(cik)
    if not submissions:
        return None
    return format_submissions_as_text(company_name, submissions)
