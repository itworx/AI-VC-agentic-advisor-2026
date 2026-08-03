"""Models package: Pydantic schemas and category vocabulary."""

from backend.models.categories import ALLOWED_CATEGORIES, REQUIRED_CATEGORIES
from backend.models.claim import (
    Claim,
    ClaimContent,
    Confidence,
    Specialist,
    SpecialistOutput,
)

__all__ = [
    "Claim",
    "ClaimContent",
    "SpecialistOutput",
    "Specialist",
    "Confidence",
    "ALLOWED_CATEGORIES",
    "REQUIRED_CATEGORIES",
]
