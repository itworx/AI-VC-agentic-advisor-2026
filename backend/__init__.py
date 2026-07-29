"""Models package: Pydantic schemas and category vocabulary."""

from backend.models.categories import ALLOWED_CATEGORIES, REQUIRED_CATEGORIES
from backend.models.claim import Claim, Confidence, Specialist, SpecialistOutput

__all__ = [
    "Claim",
    "SpecialistOutput",
    "Specialist",
    "Confidence",
    "ALLOWED_CATEGORIES",
    "REQUIRED_CATEGORIES",
]