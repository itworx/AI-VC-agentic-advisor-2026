"""All LangGraph access for the UI lives here.

Set VC_UI_STUBS=1 to develop with the backend's free stubs (no API calls).
The HITL pause is always real (stub_hitl=False) — the UI exists to show it.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Iterator

from langgraph.types import Command

from backend.graph import build_graph
from backend.persistence import get_checkpointer
from backend.state import create_initial_state


def make_graph(db_path: str = "checkpoints/ui.db", force_stubs: bool | None = None):
    use_stubs = (
        force_stubs
        if force_stubs is not None
        else os.getenv("VC_UI_STUBS") == "1"
    )
    return build_graph(
        checkpointer=get_checkpointer(db_path),
        use_stubs=use_stubs,
        stub_hitl=False,
    )


def new_thread_config() -> dict:
    thread_id = f"ui-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    return {"configurable": {"thread_id": thread_id}}


def start_run(graph, config: dict, company_name: str, company_url: str) -> Iterator[dict]:
    """Start a run. Yields state snapshots until the graph pauses or ends."""
    initial = create_initial_state(company_name, company_url)
    yield from graph.stream(initial, config, stream_mode="values")


def resume_run(
    graph,
    config: dict,
    approved: bool,
    override_decision: str | None = None,
    override_reason: str | None = None,
    notes: str | None = None,
) -> Iterator[dict]:
    """Answer the human_approval interrupt and stream the rest of the run.

    Payload shape must match backend/nodes/hitl/human_approval.py.
    """
    response = {
        "approved": approved,
        "override_decision": override_decision,
        "override_reason": override_reason,
        "notes": notes,
    }
    yield from graph.stream(Command(resume=response), config, stream_mode="values")


def snapshot(graph, config: dict) -> tuple[dict, tuple, dict | None]:
    """Latest (values, next_nodes, interrupt_payload-or-None) for a thread."""
    snap = graph.get_state(config)
    payload = None
    for task in snap.tasks:
        if task.interrupts:
            payload = task.interrupts[0].value
            break
    return dict(snap.values), tuple(snap.next), payload
