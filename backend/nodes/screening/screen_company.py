from backend.models.screening import ScreeningResult


PASS_KEYWORDS = [
    "ai",
    "artificial intelligence",
    "machine learning",
    "enterprise",
    "b2b",
    "saas",
]

FAIL_KEYWORDS = [
    "consumer",
    "social network",
    "fitness app",
    "dating",
    "gaming",
    "marketplace",
]


def screen_company(description: str) -> ScreeningResult:
    text = description.lower()

    for keyword in FAIL_KEYWORDS:
        if keyword in text:
            return ScreeningResult(
                decision="reject",
                reason=f"Detected consumer-focused signal: {keyword}"
            )

    score = 0

    for keyword in PASS_KEYWORDS:
        if keyword in text:
            score += 1

    if score >= 2:
        return ScreeningResult(
            decision="pass",
            reason="Matches AI-first B2B SaaS thesis"
        )

    return ScreeningResult(
        decision="reject",
        reason="Insufficient evidence of AI-first B2B SaaS fit"
    )