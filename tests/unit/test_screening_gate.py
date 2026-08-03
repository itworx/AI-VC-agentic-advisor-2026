"""
SC-03: verify that zero specialist calls fire on a rejected company.

The brief's instruction is to check this manually in LangSmith - still do
that once for the demo, a reviewer wants to see the trace live. This test
proves the same property in code so it runs in CI on every commit instead of
only when someone remembers to check a trace.

Self-contained: backend/graph.py doesn't have a real graph yet (still a
commented-out template), so this builds a minimal local
"screen -> conditional -> specialist" graph rather than importing one that
doesn't exist. Once the real supervisor graph exists, this is a candidate to
run against it directly instead - worth revisiting with whoever owns SV-01.
"""

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from backend.models.screening import ScreeningResult
from backend.nodes.screening.screen_company import screen_company


class _GateState(TypedDict):
    company_name: str
    company_url: str
    screening_decision: str
    screening_reason: str


class FakeLLM:
    def __init__(self, result: ScreeningResult):
        self.result = result

    def invoke(self, prompt: str) -> ScreeningResult:
        return self.result


def _make_screen_node(fake_llm: FakeLLM):
    def screen_node(state: _GateState) -> dict:
        description = f"Company name: {state['company_name']}\nWebsite: {state['company_url']}"
        result = screen_company(description, llm=fake_llm)
        return {
            "screening_decision": result.decision,
            "screening_reason": result.reason,
        }

    return screen_node


def _route_after_screen(state: _GateState) -> str:
    return "specialist" if state["screening_decision"] == "pass" else "reject_end"


def _counting_stub():
    calls = {"count": 0}

    def stub(state: _GateState) -> dict:
        calls["count"] += 1
        return {}

    return stub, calls


def _build_gate_graph(specialist_node, fake_llm: FakeLLM):
    g = StateGraph(_GateState)
    g.add_node("screen", _make_screen_node(fake_llm))
    g.add_node("specialist", specialist_node)

    g.set_entry_point("screen")
    g.add_conditional_edges(
        "screen",
        _route_after_screen,
        {"specialist": "specialist", "reject_end": END},
    )
    g.add_edge("specialist", END)

    return g.compile()


def test_zero_specialist_calls_on_reject():
    reject_result = ScreeningResult(
        decision="reject",
        reason="Consumer transport marketplace, not B2B software.",
        matched_criteria=["Consumer social, gaming, or entertainment"],
    )
    stub, calls = _counting_stub()
    graph = _build_gate_graph(stub, FakeLLM(reject_result))

    graph.invoke({"company_name": "Swvl", "company_url": "https://www.swvl.com"})

    assert calls["count"] == 0, (
        f"specialist fired {calls['count']} time(s) on a rejected company - "
        "the screening gate is decorative. See example_b_reject.md: 'If "
        "company_intel ran on a rejected company, your screening gate is "
        "decorative.'"
    )


def test_specialist_fires_on_pass():
    """Sanity check the other direction - without this, the reject test above
    would pass trivially even if the stub itself were broken."""
    pass_result = ScreeningResult(
        decision="pass",
        reason="B2B developer tools, MENA, paying customers.",
        matched_criteria=["Sector: business-to-business software"],
    )
    stub, calls = _counting_stub()
    graph = _build_gate_graph(stub, FakeLLM(pass_result))

    graph.invoke({"company_name": "Instabug", "company_url": "https://instabug.com"})

    assert calls["count"] == 1