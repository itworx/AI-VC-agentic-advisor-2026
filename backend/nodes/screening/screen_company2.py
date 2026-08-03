"""
SC-01

Screens one company against the Nile Ventures thesis using a single, cheap
LLM call with structured output. Replaces the earlier keyword-matching
prototype (see git history / the "Future implementation" note that was in
this file's original docstring).

Self-contained on purpose: config/settings.py and services/llm_service.py
aren't built out yet, so this reads its own env var and hardcodes the
OpenRouter base URL directly, the same way tests/manual/test_openrouter.py
already does. If/when llm_service.py exists, swap _default_llm() to call it
instead - nothing else here needs to change.

Deliberately does NOT call Firecrawl or any search tool. Screening is meant
to be the cheap gate that runs on every company before expensive research
does - see thesis.md ("roughly 9 out of 10 companies should be rejected
here, before any expensive research runs").
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from backend.models.screening2 import ScreeningResult
from backend.services.fetch_service import fetch_page

load_dotenv()

# backend/nodes/screening/screen_company.py -> backend/nodes -> backend -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
THESIS_PATH = _REPO_ROOT / "project3_inputs" / "thesis.md"
PROMPT_PATH = _REPO_ROOT / "backend" / "prompts" / "screening" / "screen_company.txt"

# Small, cheap model on purpose - this call happens on every company that
# comes in, including the ~90% that get rejected. Do not upgrade this to the
# same model tier used for the memo writer or specialists.
SCREEN_MODEL = "anthropic/claude-haiku-4.5"

# NOTE: .env.example currently defines OPENAI_API_KEY, but this (and
# test_openrouter.py / test_structured_output.py) read OPENROUTER_API_KEY.
# Add OPENROUTER_API_KEY=... to your local .env or this silently gets api_key=None.
MAX_PAGE_TEXT_CHARS = 4000

def _default_llm():
    return ChatOpenAI(
        model=SCREEN_MODEL,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        temperature=0,
    ).with_structured_output(ScreeningResult)


def _render_prompt(thesis: str, company_information: str) -> str:
    # Not using str.format(): screen_company.txt's example JSON block has
    # literal { } characters that .format() would try to parse as extra
    # placeholders and raise on. Plain .replace() sidesteps that without
    # touching the prompt file.
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{thesis}", thesis).replace(
        "{company_information}", company_information
    )


# 
def _build_company_information(
    company_name: str,
    company_url: str,
    fetch=None,
) -> str:
    """Fetch the company homepage and format company_information for the prompt.

    On fetch failure we still return usable text: the model sees the name and
    URL plus a clear note that the site could not be read. It can then either
    reject on that ground or pass based on the URL/name alone.
    """
    fetch = fetch or fetch_page
    result = fetch(company_url)

    if result.status == "ok" and result.text:
        page_text = result.text[:MAX_PAGE_TEXT_CHARS]
        return (
            f"Company name: {company_name}\n"
            f"Website: {company_url}\n"
            f"Homepage content (fetched):\n{page_text}"
        )

    return (
        f"Company name: {company_name}\n"
        f"Website: {company_url}\n"
        f"Homepage content: NOT AVAILABLE ({result.status}: {result.reason})"
    )


def screen_company(
    company_name: str,
    company_url: str,
    llm=None,
    fetch=None,
) -> ScreeningResult:
    """
    Screen one company against the Nile Ventures thesis.

    company_name / company_url: identify the company. The homepage is fetched
        and its extracted text is included in the prompt so the model can
        judge sector/product/traction from real content, not from its
        training-data knowledge of the company.
    llm: injectable structured-output client. Defaults to the real
        OpenRouter-backed model. Tests pass a fake to stay offline.
    fetch: injectable page fetcher. Same idea, tests pass a fake so no real
        network call happens.
    """
    if llm is None:
        llm = _default_llm()

    thesis = THESIS_PATH.read_text(encoding="utf-8")
    company_information = _build_company_information(
        company_name=company_name,
        company_url=company_url,
        fetch=fetch,
    )
    prompt = _render_prompt(thesis=thesis, company_information=company_information)

    return llm.invoke(prompt)