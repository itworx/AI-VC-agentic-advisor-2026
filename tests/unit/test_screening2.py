"""
SC-02: test screen_company against the reject example (Swvl, from
example_b_reject.md), and confirm the reason names a specific thesis
criterion rather than a vague non-answer.

Uses an injected fake LLM so this runs offline, fast, no API key. The real
model's actual reasoning quality against the real thesis is checked in
tests/manual/test_screen_company_live.py, which hits OpenRouter for real.
"""

from backend.models.screening import ScreeningResult
from backend.nodes.screening.screen_company2 import screen_company

VAGUE_REASONS = {"not a good fit", "doesn't fit", "doesn't seem right", "not right for us"}


class FakeLLM:
    """Stands in for the real structured-output client. Records the prompt it
    was called with so tests can check the thesis/company text actually made
    it in, without a real network call."""

    def __init__(self, result: ScreeningResult):
        self.result = result
        self.last_prompt = None

    def invoke(self, prompt: str) -> ScreeningResult:
        self.last_prompt = prompt
        return self.result


def test_reject_swvl_names_a_specific_criterion():
    """example_b_reject.md's exact case. 'Not a good fit' must not pass -
    the reason has to reference an actual thesis line."""
    fake = FakeLLM(
        ScreeningResult(
            decision="reject",
            reason="Swvl is a consumer transport marketplace, not B2B "
            "software, and is past the thesis's Series A stage ceiling.",
            matched_criteria=["Consumer social, gaming, or entertainment"],
        )
    )

    result = screen_company(
        "Company name: Swvl\nWebsite: https://www.swvl.com", llm=fake
    )

    assert result.decision == "reject"
    assert result.reason.strip().lower() not in VAGUE_REASONS
    assert len(result.matched_criteria) > 0, (
        "reason must name a specific thesis criterion, not just say reject"
    )


def test_pass_instabug():
    fake = FakeLLM(
        ScreeningResult(
            decision="pass",
            reason="B2B developer tools, MENA origin, paying customers per "
            "public pricing page.",
            matched_criteria=["Sector: business-to-business software"],
        )
    )

    result = screen_company(
        "Company name: Instabug\nWebsite: https://instabug.com", llm=fake
    )

    assert result.decision == "pass"
    assert len(result.matched_criteria) > 0


def test_thesis_file_reaches_the_prompt():
    """Plumbing check: the real thesis.md content, not a stale copy, must be
    what gets sent to the model."""
    fake = FakeLLM(
        ScreeningResult(decision="reject", reason="x", matched_criteria=["x"])
    )
    screen_company("Some company.", llm=fake)

    assert "Nile Ventures" in fake.last_prompt
    assert "seed to Series A" in fake.last_prompt


def test_prompt_survives_json_braces_in_template():
    """screen_company.txt's example output block has literal { } in it - this
    guards against a regression to str.format(), which would raise on that
    block instead of rendering cleanly."""
    fake = FakeLLM(
        ScreeningResult(decision="pass", reason="x", matched_criteria=["x"])
    )
    screen_company("Any description.", llm=fake)  # should not raise