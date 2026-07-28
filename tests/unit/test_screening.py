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