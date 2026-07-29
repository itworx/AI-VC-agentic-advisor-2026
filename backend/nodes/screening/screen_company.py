"""
SC-01 Prototype

Current implementation:
- Rule-based screening
- Thesis-aware reasons

Future implementation:
- Read thesis.md
- Read company website via Firecrawl
- Single inexpensive LLM call
- Structured output
- Return thesis-referenced reason
"""

from backend.models.screening import ScreeningResult


PASS_KEYWORDS = [
    "developer tools",
    "saas",
    "b2b",
    "enterprise",
    "fintech",
    "data infrastructure",
    "logistics software",
]

FAIL_KEYWORDS = {
    "consumer": "Consumer social, gaming, or entertainment",
    "gaming": "Consumer social, gaming, or entertainment",
    "entertainment": "Consumer social, gaming, or entertainment",
    "robotics": "Hardware, robotics, or anything requiring a factory",
    "hardware": "Hardware, robotics, or anything requiring a factory",
    "biotech": "Biotech, pharmaceuticals, or medical devices",
    "pharmaceutical": "Biotech, pharmaceuticals, or medical devices",
    "medical device": "Biotech, pharmaceuticals, or medical devices",
    "crypto": "Cryptocurrency trading or token issuance",
    "token": "Cryptocurrency trading or token issuance",
}


def screen_company(description: str) -> ScreeningResult:

    text = description.lower()

    for keyword, criterion in FAIL_KEYWORDS.items():

        if keyword in text:
            return ScreeningResult(
                decision="reject",
                reason=f"Rejected because the company matches the excluded thesis criterion: {criterion}.",
                matched_criteria=[criterion],
            )

    matches = []

    for keyword in PASS_KEYWORDS:

        if keyword in text:
            matches.append(keyword)

    if len(matches) >= 2:

        return ScreeningResult(
            decision="pass",
            reason="Passes screening because it appears to be a B2B software company aligned with the investment thesis.",
            matched_criteria=matches,
        )

    return ScreeningResult(
        decision="reject",
        reason="Rejected because there is insufficient evidence that the company fits the B2B software investment thesis.",
        matched_criteria=[],
    )