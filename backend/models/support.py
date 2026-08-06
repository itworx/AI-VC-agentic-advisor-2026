"""
Structured output for the evaluator's tier-2 support check (see
backend/nodes/evaluation/support.py).

One verdict per cited sentence: does the claim it points at actually say what
the sentence says?
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SupportVerdict(BaseModel):
    """Whether one memo sentence is supported by the claims it cites."""

    index: int = Field(
        ...,
        description="The 1-based number of the sentence being judged, as given in the prompt.",
    )
    supported: bool = Field(
        ...,
        description=(
            "True only if the cited claim(s) state or directly entail the "
            "sentence. False if the sentence goes beyond them, or cites an "
            "unrelated claim."
        ),
    )
    reason: str = Field(
        ...,
        description=(
            "One short sentence: what the sentence asserts that the claim does "
            "not support. Empty string when supported is true."
        ),
    )


class SupportVerdicts(BaseModel):
    """All verdicts for one memo, returned in a single model call."""

    verdicts: list[SupportVerdict] = Field(default_factory=list)
