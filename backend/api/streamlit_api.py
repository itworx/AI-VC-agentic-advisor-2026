"""
Backend API for the Streamlit UI.

Wraps the graph so the UI layer doesn't need to know anything about
LangGraph internals (interrupt, Command, config, checkpointer). The UI
calls these functions, gets back plain dicts, and displays them.

Design principle: UI code stays declarative. It reads state fields off
the dicts these functions return and never has to reach into the graph.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional, TypedDict

from langgraph.types import Command

from backend.graph import graph
from backend.state import create_initial_state


# --- Types the UI reads from ---

class RunHandle(TypedDict):
    """Opaque handle the UI stores in st.session_state and passes back to
    every subsequent call. Contains just what the backend needs to resume."""
    thread_id: str
    config: dict


class RunStatus(TypedDict):
    """What the UI needs to render at any point in a run."""
    status: Literal["awaiting_approval", "running", "complete", "rejected", "error"]
    screening_decision: str  # "pass" | "reject" | ""
    screening_reason: str
    matched_criteria: list[str]
    specialists_run: list[str]
    claims: list[dict]
    covered_categories: list[str]
    missing_categories: list[str]
    not_found: list[str]
    decision_log: list[dict]
    iteration_count: int
    memo_bull: str
    memo_base: str
    memo_bear: str
    memo_rendered: str
    error: Optional[str]


class HumanResponse(TypedDict, total=False):
    """The payload from the UI's approve / reject / override form."""
    approved: bool
    override_decision: Optional[Literal["pass", "reject"]]
    override_reason: Optional[str]
    notes: Optional[str]


# --- Public functions the UI calls ---

def start_run(company_name: str, company_url: str) -> tuple[RunHandle, RunStatus]:
    """Kick off a new run. Returns a handle the UI stores, plus the current
    status. The graph will screen the company, then pause at human_approval
    waiting for the UI to call submit_approval().
    """
    thread_id = f"ui-{company_name.replace(' ', '-').lower()}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}
    handle: RunHandle = {"thread_id": thread_id, "config": config}

    try:
        initial = create_initial_state(company_name=company_name, company_url=company_url)
        graph.invoke(initial, config)
    except Exception as e:
        return handle, _status_from_state({}, error=str(e))

    return handle, get_status(handle)


def submit_approval(handle: RunHandle, response: HumanResponse) -> RunStatus:
    """Resume a paused run with the human's approval decision. The graph
    will then run specialists (if approved and pass) and terminate with the
    memo.

    The UI passes response as a plain dict with keys:
      - approved: bool (required)
      - override_decision: "pass" | "reject" | None
      - override_reason: str | None
      - notes: str | None
    """
    # Fill in optional fields to match the human_approval node's expectations
    payload = {
        "approved": response["approved"],
        "override_decision": response.get("override_decision"),
        "override_reason": response.get("override_reason"),
        "notes": response.get("notes"),
    }

    try:
        graph.invoke(Command(resume=payload), handle["config"])
    except Exception as e:
        return _status_from_state({}, error=str(e))

    return get_status(handle)


def get_status(handle: RunHandle) -> RunStatus:
    """Read the current state of a run at any point. Safe to call before,
    during, or after execution — including after the pause and after the
    graph has ended.
    """
    try:
        snapshot = graph.get_state(handle["config"])
        return _status_from_state(snapshot.values, next_nodes=snapshot.next)
    except Exception as e:
        return _status_from_state({}, error=str(e))


def get_history(handle: RunHandle) -> list[dict]:
    """Return the full checkpoint history of a run, oldest first. Each
    entry is a plain dict with what the UI needs to render the timeline:
    the checkpoint's state values, and the node about to run next.

    Useful for a "run trace" or "step through the run" view in the UI.
    """
    try:
        history = list(graph.get_state_history(handle["config"]))
    except Exception:
        return []

    # Oldest first, so the UI can render top-to-bottom
    history.reverse()

    return [
        {
            "checkpoint_id": entry.config.get("configurable", {}).get("checkpoint_id"),
            "next_nodes": list(entry.next),
            "values": dict(entry.values),
        }
        for entry in history
    ]


# --- Internal helpers ---

def _status_from_state(
    values: dict,
    next_nodes: tuple[str, ...] = (),
    error: Optional[str] = None,
) -> RunStatus:
    """Turn LangGraph's raw state dict into the flat RunStatus shape the
    UI expects. Also derives 'status' from what's queued next and what's
    populated in state."""
    if error:
        status: Literal["awaiting_approval", "running", "complete", "rejected", "error"] = "error"
    elif "human_approval" in next_nodes:
        status = "awaiting_approval"
    elif next_nodes:
        status = "running"
    elif values.get("human_approved") is False:
        status = "rejected"
    elif values.get("screening_decision") == "reject":
        status = "rejected"
    else:
        status = "complete"

    return {
        "status": status,
        "screening_decision": values.get("screening_decision", ""),
        "screening_reason": values.get("screening_reason", ""),
        "matched_criteria": values.get("matched_criteria", []),
        "specialists_run": values.get("specialists_run", []),
        "claims": values.get("claims", []),
        "covered_categories": values.get("covered_categories", []),
        "missing_categories": values.get("missing_categories", []),
        "not_found": values.get("not_found", []),
        "decision_log": values.get("decision_log", []),
        "iteration_count": values.get("iteration_count", 0),
        "memo_bull": values.get("memo_bull", ""),
        "memo_base": values.get("memo_base", ""),
        "memo_bear": values.get("memo_bear", ""),
        "memo_rendered": values.get("memo_rendered", ""),
        "error": error,
    }