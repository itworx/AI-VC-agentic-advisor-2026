
from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator
from backend.models.categories import ALLOWED_CATEGORIES

Specialist = Literal["company_intel", "market_intel", "team_signals"]
Confidence = Literal["verified", "reported", "inferred"]


class Claim(BaseModel):
    """A single factual assertion about the company or its market.

    Every field is required. Absence of any field must cause validation to
    fail, which is the C-03 guarantee (see tests/unit/test_schema.py).
    """

    claim_text: str = Field(
        ...,
        min_length=1,
        description=(
            "A single factual assertion, e.g. 'Acme Corp raised a $2M seed "
            "round in 2023.' Must not include any named individual."
        ),
    )
    source_url: HttpUrl = Field(
        ...,
        description="URL where this claim was found. Hard rule: required.",
    )
    #source_url: HttpUrl | None = None (tested that its failed when source url is None)
    quoted_snippet: str = Field(
        ...,
        min_length=1,
        description=(
            "Direct quote from the source supporting the claim. "
            "Must be under 25 words."
        ),
    )
    specialist: Specialist = Field(
        ...,
        description="Which specialist produced this claim.",
    )
    confidence: Confidence = Field(
        ...,
        description=(
            "verified: quoted directly from a primary source (company site, "
            "filing). reported: quoted from a secondary source (news, blog). "
            "inferred: reasoned from other claims, not stated directly."
        ),
    )
    category: str = Field(
        ...,
        description=(
            "Category the claim covers, e.g. 'market_size', 'competitors'. "
            "Must be in ALLOWED_CATEGORIES."
        ),
    )
    retrieval_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When the source was fetched (UTC).",
    )

    @field_validator("quoted_snippet")
    @classmethod
    def snippet_word_limit(cls, v: str) -> str:
        word_count = len(v.split())
        if word_count > 25:
            raise ValueError(
                f"quoted_snippet must be under 25 words, got {word_count}"
            )
        return v

    @field_validator("category")
    @classmethod
    def category_must_be_allowed(cls, v: str) -> str:
        if v not in ALLOWED_CATEGORIES:
            raise ValueError(
                f"category '{v}' is not in ALLOWED_CATEGORIES. "
                "Add it to backend/models/categories.py if it's a real new category."
            )
        return v


class SpecialistOutput(BaseModel):
    """Wrapper for what a specialist returns via with_structured_output.

    A specialist run produces two things: the claims it found, and the
    categories it looked for but could not find. Both matter. 'not_found' is
    a first-class result, not an empty list.

    In each specialist node:

        model = ChatOpenAI().with_structured_output(SpecialistOutput)
        result = model.invoke(prompt)
        # result.claims -> list[Claim]
        # result.not_found -> list[str]
    """

    claims: list[Claim] = Field(
        default_factory=list,
        description="Claims found during this specialist's research.",
    )
    not_found: list[str] = Field(
        default_factory=list,
        description=(
            "Categories the specialist looked for but could not find. "
            "Values must be strings from ALLOWED_CATEGORIES."
        ),
    )

    @field_validator("not_found")
    @classmethod
    def not_found_must_be_allowed(cls, v: list[str]) -> list[str]:
        for cat in v:
            if cat not in ALLOWED_CATEGORIES:
                raise ValueError(
                    f"not_found contains '{cat}' which is not in "
                    "ALLOWED_CATEGORIES"
                )
        return v