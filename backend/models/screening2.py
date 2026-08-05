from typing import Literal

from pydantic import BaseModel, Field


class ScreeningResult(BaseModel):
    """Output of screen_company(). Field names match prompts/screening/screen_company.txt's
    JSON contract exactly - don't rename one without the other."""

    decision: Literal["pass", "reject"]
    reason: str
    # Thesis criteria the decision turned on - e.g. "Sector: business-to-business
    # software" or "Consumer social, gaming, or entertainment" (an exclusion).
    # Empty list is only valid for a reject on insufficient evidence, not for a pass.
    matched_criteria: list[str] = Field(default_factory=list)