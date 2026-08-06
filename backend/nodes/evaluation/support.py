"""
E-01 tier 2: does the cited claim actually SAY what the sentence says?

trace_memo() (tier 1, pure Python) can only check that a marker is present and
resolvable. That leaves one hole, and it's the obvious one to walk through: a
model can satisfy tier 1 completely by spraying plausible markers onto sentences
the claims don't support. Marker presence is not entailment, and entailment is
not a string operation - so this layer is the one place in the evaluator that
uses a model.

Design constraints that keep it honest:
  - The judge sees ONLY the sentence and the text of the claims it cites. Not
    the memo, not the other claims, not any web content. It cannot be talked
    into agreeing by surrounding argument, and it cannot "verify" a sentence
    against knowledge the pipeline never gathered.
  - One call for the whole memo, not one per sentence: ~12-16 sentences batched
    into a single request keeps this affordable enough to run every pass.
  - Verdicts are matched back by index and default to UNSUPPORTED when the
    model omits, duplicates, or garbles an index. A judge that fails to answer
    must not thereby wave a sentence through.
  - Tier 1 stays authoritative on its own findings. This layer can only ADD
    violations, never clear one, so no model verdict can unblock a sentence
    that has no citation at all.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from backend.models.claim import Claim
from backend.models.support import SupportVerdicts

load_dotenv()

_REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = _REPO_ROOT / "backend" / "prompts" / "evaluation" / "check_support.txt"

# A cheaper model than write_memo's on purpose: this is a narrow entailment
# judgement on two short texts, not open-ended writing. Deliberately a
# DIFFERENT model from the memo writer - a judge sharing the writer's blind
# spots is worth much less than an independent one.
SUPPORT_MODEL = "anthropic/claude-haiku-4.5"


class SupportCheckError(RuntimeError):
    """The support model could not be reached or returned nothing usable."""


def _default_llm():
    return ChatOpenAI(
        model=SUPPORT_MODEL,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        temperature=0,  # a judgement, not a draft
    ).with_structured_output(SupportVerdicts)


def _render_items(pairs: list[tuple[str, list[Claim]]]) -> str:
    blocks = []
    for i, (sentence, claims) in enumerate(pairs, start=1):
        lines = [f"ITEM {i}", f"  SENTENCE: {sentence}"]
        for c in claims:
            lines.append(f"  CITED CLAIM: {c.claim_text}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _render_prompt(pairs: list[tuple[str, list[Claim]]]) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{items}", _render_items(pairs))


def check_support(
    pairs: list[tuple[str, list[Claim]]],
    llm=None,
) -> dict[int, tuple[bool, str]]:
    """Judge each (sentence, cited claims) pair.

    Returns {0-based pair index: (supported, reason)}. Every input pair is
    present in the result: anything the model didn't return a usable verdict for
    is recorded as unsupported, with a reason saying so.

    Raises SupportCheckError if the call itself fails. Callers decide whether a
    dead judge should block the memo - see evaluate()'s fail_open handling.
    """
    if not pairs:
        return {}

    if llm is None:
        llm = _default_llm()

    try:
        result = llm.invoke(_render_prompt(pairs))
    except Exception as exc:  # noqa: BLE001 - re-raised as our own type
        raise SupportCheckError(f"support check call failed: {exc}") from exc

    if result is None or not getattr(result, "verdicts", None):
        raise SupportCheckError("support check returned no verdicts")

    # Index by the model's 1-based index, dropping anything out of range or
    # duplicated - a repeated index means we can't trust either copy.
    seen: dict[int, tuple[bool, str]] = {}
    duplicated: set[int] = set()
    for v in result.verdicts:
        if v.index < 1 or v.index > len(pairs):
            continue
        if v.index in seen:
            duplicated.add(v.index)
            continue
        seen[v.index] = (v.supported, v.reason)

    out: dict[int, tuple[bool, str]] = {}
    for i in range(len(pairs)):
        one_based = i + 1
        if one_based in duplicated:
            out[i] = (
                False,
                "the support check returned conflicting verdicts for this "
                "sentence, so it is treated as unsupported",
            )
        elif one_based in seen:
            out[i] = seen[one_based]
        else:
            out[i] = (
                False,
                "the support check returned no verdict for this sentence, so "
                "it is treated as unsupported",
            )
    return out
