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

from backend.models.screening import ScreeningResult

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


def screen_company(description: str, llm=None) -> ScreeningResult:
    """
    description: short text about the company - name, sector, product, any
        stage/traction signal available (e.g. "Company name: Swvl\\nWebsite:
        https://www.swvl.com"). No live website fetch happens here.
    llm: injectable structured-output client, defaults to the real
        OpenRouter-backed model. Tests pass a fake here to stay offline -
        see tests/unit/test_screening.py. Real-model checks against the
        actual thesis live in tests/manual/test_screen_company_live.py.
    """
    if llm is None:
        llm = _default_llm()

    thesis = THESIS_PATH.read_text(encoding="utf-8")
    prompt = _render_prompt(thesis=thesis, company_information=description)

    return llm.invoke(prompt)