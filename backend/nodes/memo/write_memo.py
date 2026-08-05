"""
M-01 / M-02

Writes the bull/base/bear memo from the accumulated claims list ONLY - the
model is given claim_text strings, numbered, and NOTHING else. It never sees
raw web text, search results, or website content directly.

ASSUMPTION FLAGGED FOR REVIEW: there's no existing citation-marker convention
anywhere in this repo yet (checked prompts/, no memo/ folder existed before
this). I invented one: the model must tag every claim-backed sentence with
<<N>> where N is that claim's 1-based position in the numbered list it was
given. render_citations.py (M-03) turns these into renumbered [k] footnotes.
If market_intel/company_intel prompts already assume a different citation
format elsewhere, reconcile before merging - this was built with nothing to
match against.

M-02 (the 3 cases must differ in assumptions, not tone) is enforced two ways:
1. The prompt instructs each case to weight different claims (bull =
   favorable interpretation, bear = risk/gaps/"not found", base = balanced)
   rather than restating the same argument in different adjectives.
2. assert_cases_differ() below is a cheap, mechanical backstop: if two cases
   end up citing the *exact same set* of claims, that's a strong "same
   claims, different tone" signal, and this raises rather than shipping it
   silently. It cannot verify the cases differ in the *right* way - that's
   still a human judgement call per M-02's own wording (see I-05: "read
   every passing memo as if you were a partner").
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from backend.models.claim import Claim
from backend.models.memo import MemoDraft

load_dotenv()

_REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = _REPO_ROOT / "backend" / "prompts" / "memo" / "write_memo.txt"

# Full-strength model on purpose - unlike screen's cheap gate call, this is
# the highest-stakes text in the whole pipeline; it's what a human reads.
MEMO_MODEL = "anthropic/claude-sonnet-4.6"

CITATION_PATTERN = re.compile(r"<<(\d+)>>")


def _default_llm():
    return ChatOpenAI(
        model=MEMO_MODEL,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        temperature=0.2,
    ).with_structured_output(MemoDraft)


def _numbered_claims_block(claims: list[Claim]) -> str:
    lines = []
    for i, c in enumerate(claims, start=1):
        lines.append(f"<<{i}>> [{c.category} | {c.confidence}] {c.claim_text}")
    return "\n".join(lines)


def _render_prompt(claims: list[Claim]) -> str:
    # Not str.format(): keep this consistent with screen_company.py's
    # approach in case the prompt ever grows a literal-brace JSON example.
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{claims}", _numbered_claims_block(claims))


def write_memo(claims: list[Claim], llm=None) -> MemoDraft:
    """
    claims: the FULL accumulated claims list from state (not raw web text).
    llm: injectable structured-output client, defaults to the real
        OpenRouter-backed model. Tests inject a fake to stay offline - see
        tests/unit/test_write_memo.py. Real-model checks live in
        tests/manual/test_write_memo_live.py.
    """
    if not claims:
        raise ValueError(
            "write_memo called with zero claims - the supervisor should "
            "never route here with an empty claims list; check_coverage "
            "should have caught this first."
        )
    if llm is None:
        llm = _default_llm()

    prompt = _render_prompt(claims)
    return llm.invoke(prompt)


def citation_ids_used(section_text: str) -> set[int]:
    """All claim indices (<<N>>) referenced in one section of memo text."""
    return {int(n) for n in CITATION_PATTERN.findall(section_text)}


def assert_cases_differ(memo: MemoDraft) -> None:
    """M-02 backstop. Raises ValueError if any two of the three cases cite
    the exact same set of claims - see module docstring for what this can
    and can't actually verify."""
    sections = {
        "bull_case": citation_ids_used(memo.bull_case),
        "base_case": citation_ids_used(memo.base_case),
        "bear_case": citation_ids_used(memo.bear_case),
    }
    names = list(sections.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            name_a, name_b = names[i], names[j]
            ids_a, ids_b = sections[name_a], sections[name_b]
            if ids_a and ids_a == ids_b:
                raise ValueError(
                    f"{name_a} and {name_b} cite the exact same claims "
                    f"({sorted(ids_a)}) - likely differ only in tone, not "
                    "assumptions. See M-02."
                )
