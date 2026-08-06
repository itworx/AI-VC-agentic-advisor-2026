from __future__ import annotations
from langgraph.types import interrupt
from backend.state import State


def human_approval(state: State) -> dict:
    """Pause the graph and wait for the human's decision on the screening result."""
    response = interrupt(
        {
            "company_name": state["company_name"],
            "company_url": state["company_url"],
            "screening_decision": state["screening_decision"],
            "screening_reason": state["screening_reason"],
            "matched_criteria": state["matched_criteria"],
            "prompt": (
                "Review the screening decision. Approve to continue, "
                "override to reverse, or add focus areas for the specialists."
            ),
        }
    )

    # Defensive: if a human/UI sends something malformed, end safely.
    if not isinstance(response, dict):
        return {"human_approved": False, "human_notes": ""}

    updates: dict = {
        "human_approved": bool(response.get("approved", False)),
        "human_notes": response.get("notes", "") or "",
    }

    # Handle override: if the human flipped the decision, apply it and
    # append the override reason to screening_reason so the audit trail
    # shows both the original screen output and the human's justification.
    override = response.get("override_decision")
    if override in ("pass", "reject"):
        override_reason = (response.get("override_reason", "") or "").strip()
        updates["screening_decision"] = override
        original_reason = state.get("screening_reason", "")
        updates["screening_reason"] = (
            f"{original_reason} | Human override ({override}): {override_reason}"
        )

    return updates


def human_approval_stub(state: State) -> dict:
    """Test stub: skips the pause and auto-approves.

    For tests that just want the graph to run to completion. Tests that
    specifically exercise the pause/resume flow should NOT use this stub —
    build the graph with stub_hitl=False instead.
    """
    return {"human_approved": True, "human_notes": ""}
