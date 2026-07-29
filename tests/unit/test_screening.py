from pathlib import Path
from backend.nodes.screening.screen_company import screen_company


def test_pass_company():

    description = """
    AI-powered contract review platform
    for enterprise legal teams.
    B2B SaaS.
    """

    result = screen_company(description)

    assert result.decision == "pass"


def test_reject_company():

    description = """
    Social fitness app for consumers.
    """

    result = screen_company(description)

    assert result.decision == "reject"

def test_example_a_pass():

    file_path = Path("project3_inputs/example_a_pass.md")

    description = file_path.read_text(encoding="utf-8")

    result = screen_company(description)

    assert result.decision == "pass"
    assert len(result.reason) > 0

def test_example_b_reject():

    file_path = Path("project3_inputs/example_b_reject.md")

    description = file_path.read_text(encoding="utf-8")

    result = screen_company(description)

    assert result.decision == "reject"
    assert len(result.reason) > 0

def test_reject_reason_references_thesis():

    description = """
    Consumer transportation platform.
    """

    result = screen_company(description)

    assert result.decision == "reject"

    assert (
        "consumer" in result.reason.lower()
        or "thesis" in result.reason.lower()
    )