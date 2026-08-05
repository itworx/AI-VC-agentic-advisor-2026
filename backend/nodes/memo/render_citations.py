"""
M-03 / M-04 / M-05

Pure Python. No model calls. Takes write_memo's raw <<N>> markers and turns
them into a readable memo document:
  - M-03: renumber citations to first-appearance order across the whole
    memo (not per-section), append one shared Sources list at the end.
  - M-04: visually mark inferred-confidence claims in the Sources list
    (italics + an explicit [inferred] tag), so a reader can't mistake an
    inferred figure for a verified one just by skimming.
  - M-05: hard word-budget truncation of the body to a 4-page cap, enforced
    here rather than as a prompt instruction - a length limit in the prompt
    is something a model can talk itself past ("just a bit more detail is
    warranted here"); a word-count cutoff in code can't be argued with.

Ordering in the real pipeline: write_memo -> render_citations (this module,
producing the FULL untruncated doc) -> evaluate (E-01, checks traceability
on the full doc, needs every marker already resolved) -> only once evaluate
passes, enforce_page_cap() runs as the final step. Truncating before
evaluate would risk cutting a sentence the evaluator was about to check.
"""

import re

from backend.models.claim import Claim
from backend.models.memo import MemoDraft

CITATION_PATTERN = re.compile(r"<<(\d+)>>")

WORDS_PER_PAGE = 500  # rough single-spaced VC-memo heuristic
MAX_PAGES = 4
MAX_BODY_WORDS = WORDS_PER_PAGE * MAX_PAGES

SOURCES_HEADING = "\n\n## Sources\n"


class UnresolvedCitationError(ValueError):
    """A <<N>> marker referenced a claim index that doesn't exist in the
    claims list. This must fail loudly - silently dropping it or rendering
    a dead link would hide a hallucinated citation."""


def _build_id_map(memo: MemoDraft, claims: list[Claim]) -> dict[int, int]:
    """First-appearance-order map from original claim index -> display
    footnote number, reading bull -> base -> bear in that fixed order."""
    id_map: dict[int, int] = {}
    for section_text in (memo.bull_case, memo.base_case, memo.bear_case):
        for m in CITATION_PATTERN.finditer(section_text):
            original_id = int(m.group(1))
            if original_id not in id_map:
                if original_id < 1 or original_id > len(claims):
                    raise UnresolvedCitationError(
                        f"<<{original_id}>> does not correspond to any claim "
                        f"(claims list has {len(claims)} entries)"
                    )
                id_map[original_id] = len(id_map) + 1
    return id_map


def _renumber_section(text: str, id_map: dict[int, int]) -> str:
    def _sub(match: re.Match) -> str:
        original_id = int(match.group(1))
        return f"[{id_map[original_id]}]"

    return CITATION_PATTERN.sub(_sub, text)


def render_citations(memo: MemoDraft, claims: list[Claim]) -> str:
    """M-03 + M-04. Combines bull/base/bear into one document string with
    shared, renumbered [k] footnotes and one Sources section at the end.
    Inferred-confidence claims are italicized and tagged [inferred] (M-04).
    """
    id_map = _build_id_map(memo, claims)

    bull = _renumber_section(memo.bull_case, id_map)
    base = _renumber_section(memo.base_case, id_map)
    bear = _renumber_section(memo.bear_case, id_map)

    sources_lines = []
    for original_id, display_id in sorted(id_map.items(), key=lambda kv: kv[1]):
        claim = claims[original_id - 1]
        entry = f"[{display_id}] {claim.claim_text} — {claim.source_url}"
        if claim.confidence == "inferred":
            entry = f"*{entry}* [inferred]"
        sources_lines.append(entry)

    sources_section = SOURCES_HEADING + "\n".join(sources_lines)

    body = (
        "## Bull case\n" + bull + "\n\n"
        "## Base case\n" + base + "\n\n"
        "## Bear case\n" + bear
    )
    return body + sources_section


def enforce_page_cap(rendered_memo: str, max_words: int = MAX_BODY_WORDS) -> str:
    """M-05. Truncates the BODY only, by word count - never the Sources
    list, so attribution stays intact and checkable even in a truncated
    memo. No-op if the memo is already under the cap."""
    if SOURCES_HEADING in rendered_memo:
        body, sources = rendered_memo.split(SOURCES_HEADING, 1)
        sources = SOURCES_HEADING + sources
    else:
        body, sources = rendered_memo, ""

    words = body.split()
    if len(words) <= max_words:
        return rendered_memo

    truncated_body = " ".join(words[:max_words])
    omitted = len(words) - max_words
    notice = (
        f"\n\n*[Memo truncated to the {MAX_PAGES}-page cap — {omitted} "
        "words omitted. All cited sources remain listed below.]*"
    )
    return truncated_body + notice + sources


def build_final_memo(memo: MemoDraft, claims: list[Claim]) -> str:
    """Convenience wrapper matching the real pipeline order: render then cap.
    Call render_citations() directly first if you need the untruncated
    version for the evaluator."""
    rendered = render_citations(memo, claims)
    return enforce_page_cap(rendered)
