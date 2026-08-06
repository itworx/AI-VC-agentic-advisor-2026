"""Run console — the screen from 'VC Advisor Frontend.dc.html' (frames 1a-1d).

Run from the repo root:  streamlit run frontend/app.py
Free dev mode:           VC_UI_STUBS=1 streamlit run frontend/app.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# allow `streamlit run frontend/app.py` from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from dotenv import load_dotenv

from frontend import graph_client, ui
from frontend.run_state import derive_node_statuses, parse_spend, run_pill
from frontend.theme import GLOBAL_CSS

load_dotenv()

COSTS_LOG = Path("logs/costs.log")


@st.cache_resource
def get_graph():
    return graph_client.make_graph(db_path=os.getenv("VC_UI_DB", "checkpoints/ui.db"))


def _spend() -> float:
    since = st.session_state.get("run_start_iso", "9999")
    if not COSTS_LOG.exists():
        return 0.0
    return parse_spend(COSTS_LOG.read_text(encoding="utf-8"), since)


def _submit_hitl(approved, override_decision, override_reason, notes):
    """Called by the dialog. Resumes the graph and drains the stream."""
    for _ in graph_client.resume_run(
        st.session_state.graph, st.session_state.config,
        approved=approved, override_decision=override_decision,
        override_reason=override_reason, notes=notes,
    ):
        pass  # values land in the checkpointer; we re-read via snapshot()


def run_console() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.session_state.graph = get_graph()

    # --- run form (no active run yet) ---
    if not st.session_state.get("run_started"):
        st.title("Run console")
        name = st.text_input("Company name", placeholder="Instabug")
        url = st.text_input("Company website", placeholder="https://www.instabug.com")
        if st.button("Start run", type="primary", disabled=not (name and url)):
            st.session_state.config = graph_client.new_thread_config()
            st.session_state.company_label = f"{name} · {url.removeprefix('https://').removeprefix('www.')}"
            st.session_state.run_start_iso = datetime.now(timezone.utc).isoformat()
            st.session_state.run_started = True
            with st.spinner("Screening…"):
                for _ in graph_client.start_run(
                    st.session_state.graph, st.session_state.config, name, url
                ):
                    pass
            st.rerun()
        return

    # --- active run: read the latest snapshot and render everything ---
    values, next_nodes, payload = graph_client.snapshot(
        st.session_state.graph, st.session_state.config
    )
    statuses = derive_node_statuses(values, next_nodes)
    pill = run_pill(values, next_nodes)
    thread_id = st.session_state.config["configurable"]["thread_id"]

    ui.render_top_bar(st.session_state.get("company_label", ""), thread_id, pill)

    if pill[0] == "ended · rejected":
        st.error(f"Run ended before any specialist spend — {values.get('screening_reason', '')}")

    rail_col, canvas_col = st.columns([27, 100])
    with rail_col:
        ui.render_rail(
            statuses,
            meta={
                "screen": values.get("screening_decision", ""),
                "human_approval": "waiting" if statuses["human_approval"] == "waiting"
                                  else ("approved" if values.get("human_approved") else ""),
                "supervisor": f"iter {values.get('iteration_count', 0)}"
                              if values.get("iteration_count") else "",
                "company_intel": _claims_meta(values, "company_intel"),
                "market_intel": _claims_meta(values, "market_intel"),
                "team_signals": _claims_meta(values, "team_signals"),
            },
            metrics={
                "iteration": values.get("iteration_count", 0),
                "claims": len(values.get("claims", [])),
                "spend": _spend(),
            },
        )
    with canvas_col:
        caption = _canvas_caption(values, next_nodes)
        ui.render_canvas(statuses, _sublabels(values, statuses), caption)

    st.divider()
    ui.render_evidence(values)

    if payload is not None:
        ui.hitl_dialog(payload, _submit_hitl)

    if st.button("New run"):
        for key in ("run_started", "config", "company_label", "run_start_iso"):
            st.session_state.pop(key, None)
        st.rerun()


def _claims_meta(values: dict, specialist: str) -> str:
    n = sum(1 for c in values.get("claims", []) if c.get("specialist") == specialist)
    return f"{n} claims" if n else ""


def _sublabels(values: dict, statuses: dict) -> dict:
    subs = {}
    if values.get("screening_decision"):
        subs["screen"] = values["screening_decision"]
    if statuses["human_approval"] == "waiting":
        subs["human_approval"] = "awaiting input"
    covered = len(values.get("covered_categories", []))
    missing = len(values.get("missing_categories", []))
    if covered or missing:
        subs["check_coverage"] = f"{covered} / {covered + missing} covered"
    if values.get("iteration_count"):
        subs["supervisor"] = f"iter {values['iteration_count']}"
    return subs


def _canvas_caption(values: dict, next_nodes: tuple) -> str:
    if "human_approval" in next_nodes:
        return "paused at human_approval · interrupt()"
    log = values.get("decision_log", [])
    if next_nodes and log:
        last = log[-1]
        return f"supervisor → {last['chosen']} · {last['reason']}"
    if values.get("memo_base"):
        return "run complete · memo written"
    return ""


pages = st.navigation([
    st.Page(run_console, title="Run console", default=True),
    st.Page("memo_page.py", title="IC Memo"),
])
st.set_page_config(page_title="AI VC Advisor", layout="wide")
pages.run()
