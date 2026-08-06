"""
E-01 / E-02 result types.

The evaluator's output has to be two things at once: a machine-readable
verdict the graph can route on, and a human-readable list of exactly which
sentences failed and why (E-02 requires naming them, not just counting them).
Violation carries the sentence verbatim so the feedback string can quote it
back to the memo writer without re-deriving anything.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Which memo section a sentence came from.
Section = Literal["bull_case", "base_case", "bear_case"]

# Why a sentence failed to trace.
#   unresolved_citation - cites <<N>> where N isn't a real claim index. Always
#       hard: a citation pointing at nothing is worse than no citation, it
#       looks sourced to a reader.
#   untraced_factual    - no citation marker, and the sentence states figures
#       or company facts. This is the failure the whole project exists to
#       catch (an invented market size / customer count / team size).
#   untraced            - no citation marker, no detectable factual content.
#       Reported but not blocking: write_memo.txt explicitly allows unmarked
#       connective sentences, so rejecting on these would fight our own prompt.
#   unsupported_by_claim - cites a real claim that does not actually say what
#       the sentence says. Tier 2 (see check_support): the only check here that
#       uses a model, because entailment is not a string operation. Blocking -
#       a sentence citing a claim that doesn't support it is a misattribution,
#       which is the failure a citation is supposed to make impossible.
#   weak_support        - cites a claim it shares no content words with.
#       Reported but not blocking: lexical overlap is a cheap hint, not proof;
#       a correctly-cited sentence can legitimately paraphrase. Superseded by
#       unsupported_by_claim whenever tier 2 is enabled.
ViolationKind = Literal[
    "unresolved_citation",
    "untraced_factual",
    "unsupported_by_claim",
    "untraced",
    "weak_support",
]

# Kinds that cause a reject. The other kinds are surfaced in feedback so a
# human (I-05) can look at them, but don't on their own trigger a rewrite.
BLOCKING_KINDS: frozenset[str] = frozenset(
    {"unresolved_citation", "untraced_factual", "unsupported_by_claim"}
)


class Violation(BaseModel):
    """One memo sentence that failed to trace to a claim."""

    section: Section
    sentence: str = Field(..., description="The offending sentence, verbatim.")
    kind: ViolationKind
    detail: str = Field(
        ...,
        description="Why it failed, and what the writer should do about it.",
    )
    cited_ids: list[int] = Field(
        default_factory=list,
        description="Claim indices the sentence cited, if any.",
    )

    @property
    def blocking(self) -> bool:
        return self.kind in BLOCKING_KINDS


class EvaluationResult(BaseModel):
    """Verdict for one memo draft.

    `passed` is derived from blocking violations only - see BLOCKING_KINDS.
    """

    passed: bool
    violations: list[Violation] = Field(default_factory=list)
    sentences_checked: int = 0
    sentences_traced: int = 0

    @property
    def blocking_violations(self) -> list[Violation]:
        return [v for v in self.violations if v.blocking]

    @property
    def advisory_violations(self) -> list[Violation]:
        return [v for v in self.violations if not v.blocking]
