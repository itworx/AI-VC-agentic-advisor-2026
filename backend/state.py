
from __future__ import annotations
from operator import add
from typing import Annotated, Literal, TypedDict
from backend.models.claim import Claim


class State(TypedDict):
    """The state object passed through every node in the graph."""

    # input
    company_name: str
    company_url: str

    # human-in-the-loop
    human_approved: bool
    human_notes: str  # optional focus areas from the human; "" if none

    # screening (populated by screen node) 
    screening_decision: Literal["pass", "reject", ""]
    screening_reason: str
     # thesis criteria the screen decision turned on. Populated by screen,
     # read later by the memo writer for the audit trail.
    matched_criteria: list[str]

    # claims accumulated across specialists 
    # 'add' means new claims append to the existing list, not overwrite it.
    # without this, the second specialist's claims would replace the first's.
    claims: Annotated[list[Claim], add]

    # coverage tracking
    covered_categories: list[str]
    missing_categories: list[str]
    specialists_run: Annotated[list[str], add]
    specialist_outputs: Annotated[list[dict], add]
    not_found: Annotated[list[str], add]

    # supervisor state 
    # each entry: {"chosen": str, "reason": str, "missing_categories": list[str]}
    decision_log: Annotated[list[dict], add]
    iteration_count: int  # incremented by supervisor each turn; capped at 6
    next_action: str  # set by supervisor each turn, read by conditional edge router

    # Memo
    memo_bull: str
    memo_base: str
    memo_bear: str
    memo_rendered: str  # after render_citations attaches source markers

    # evaluator
    evaluator_feedback: str
    evaluator_iterations: int  # incremented by evaluate each turn; capped at 2


def create_initial_state(company_name: str, company_url: str) -> State:
    """Build a fresh State with sensible defaults.

    Use this at graph invocation so every field is present before any node
    reads it. LangGraph reducers handle appends to lists, but scalar fields
    need to exist upfront or nodes will KeyError.
    """
    return State(
        company_name=company_name,
        company_url=company_url,
        human_approved=False,
        human_notes="",
        screening_decision="",
        screening_reason="",
        matched_criteria=[],
        claims=[],
        covered_categories=[],
        missing_categories=[],
        specialists_run=[],
        specialist_outputs=[],
        not_found=[],
        decision_log=[],
        iteration_count=0,
        next_action="",
        memo_bull="",
        memo_base="",
        memo_bear="",
        memo_rendered="",
        evaluator_feedback="",
        evaluator_iterations=0,
    )