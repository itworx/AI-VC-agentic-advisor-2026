"""Streamlit rendering for the run console (spec sections 3.1-3.5)."""
from __future__ import annotations

import streamlit as st

from frontend.canvas import build_dot
from frontend.run_state import NODE_ORDER, claims_to_rows
from frontend.theme import INK, STATUS, SURFACE

_MONO = "font-family:'IBM Plex Mono',monospace;"


# ---------- pure HTML builders (unit-tested) ----------

def pill_html(label: str, status_key: str) -> str:
    c = STATUS[status_key]
    pulse = "animation:pulseDot 1.2s infinite;" if status_key in ("waiting", "running") else ""
    return (
        f'<span style="display:inline-flex;align-items:center;gap:7px;'
        f'background:{c.bg};border:1px solid {c.border};color:{c.text};'
        f'border-radius:99px;padding:5px 12px;{_MONO}font-size:11px;'
        f'font-weight:600;letter-spacing:.06em;text-transform:uppercase">'
        f'<span style="width:7px;height:7px;border-radius:50%;'
        f'background:{c.dot};{pulse}"></span>{label}</span>'
    )


def rail_row_html(name: str, status_key: str, meta: str, active: bool) -> str:
    c = STATUS[status_key]
    box = f"background:{c.bg};border:1px solid {c.border};" if active else ""
    name_color = c.text if active else (INK["main"] if status_key == "done" else INK["muted"])
    indent = "padding-left:26px;" if name in ("company_intel", "market_intel", "team_signals") else ""
    pulse = "animation:pulseDot 1.2s infinite;" if status_key in ("waiting", "running") else ""
    return (
        f'<div style="display:flex;align-items:center;gap:10px;'
        f'padding:9px 10px;border-radius:6px;{box}{indent}">'
        f'<span style="width:8px;height:8px;border-radius:50%;background:{c.dot};'
        f'flex:none;{pulse}"></span>'
        f'<span style="{_MONO}font-size:13px;font-weight:{600 if active else 500};'
        f'color:{name_color};flex:1">{name}</span>'
        f'<span style="{_MONO}font-size:11px;color:{c.dot if active else INK["muted"]}">'
        f'{meta}</span></div>'
    )


def coverage_chip_html(category: str, covered: bool) -> str:
    if covered:
        c = STATUS["done"]
        style = f"color:{c.text};background:{c.bg};border:1px solid {c.border};"
    else:
        style = f'color:{INK["muted"]};border:1px solid {SURFACE["border"]};'
    return (
        f'<span style="{_MONO}font-size:11px;font-weight:500;border-radius:4px;'
        f'padding:4px 8px;display:inline-block;margin:0 4px 6px 0;{style}">'
        f"{category}</span>"
    )


def decision_entry_html(entry: dict, latest: bool) -> str:
    bar = STATUS["running"].dot if latest else SURFACE["border_input"]
    return (
        f'<div style="border-left:2px solid {bar};padding-left:11px;margin-bottom:9px">'
        f'<div style="{_MONO}font-size:11px;font-weight:600;color:{INK["body"]}">'
        f'iter {entry["iteration"]} → {entry["chosen"]}</div>'
        f'<div style="font-size:11px;line-height:1.5;color:{INK["muted"]}">'
        f'{entry["reason"]}</div></div>'
    )


# ---------- Streamlit renderers (exercised by AppTest in Task 7) ----------

def render_top_bar(company_label: str, thread_id: str, pill: tuple[str, str]) -> None:
    label, key = pill
    left, right = st.columns([3, 2])
    with left:
        st.markdown(
            f'<div style="font-weight:700;font-size:14px">Nile Ventures '
            f'<span style="color:#94A0AD">/</span> '
            f'<span style="color:#5A6472;font-weight:500">AI VC Advisor</span> '
            f'<span style="{_MONO}font-size:12px;color:{INK["muted"]};'
            f'margin-left:14px">thread_id {thread_id}</span></div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            f'<div style="text-align:right"><span style="{_MONO}font-size:12px;'
            f'color:{INK["sub"]};margin-right:10px">{company_label}</span>'
            f"{pill_html(label, key)}</div>",
            unsafe_allow_html=True,
        )
    st.divider()


def render_rail(statuses: dict, meta: dict, metrics: dict) -> None:
    st.markdown('<div class="vc-label">Pipeline</div>', unsafe_allow_html=True)
    rows = []
    for name in NODE_ORDER:
        key = statuses[name]
        rows.append(rail_row_html(name, key, meta.get(name, ""),
                                  active=key in ("running", "waiting")))
    st.markdown("".join(rows), unsafe_allow_html=True)
    st.divider()
    a, b, c = st.columns(3)
    a.metric("Iteration", f'{metrics["iteration"]} / 6')
    b.metric("Claims", metrics["claims"])
    c.metric("Spend", f'${metrics["spend"]:.3f}')


def render_canvas(statuses: dict, sublabels: dict, caption: str) -> None:
    top_l, top_r = st.columns([1, 2])
    top_l.markdown('<div class="vc-label">Graph state</div>', unsafe_allow_html=True)
    top_r.markdown(
        f'<div style="text-align:right;{_MONO}font-size:12px;'
        f'color:{INK["sub"]}">{caption}</div>',
        unsafe_allow_html=True,
    )
    st.graphviz_chart(build_dot(statuses, sublabels), use_container_width=True)


def render_evidence(values: dict) -> None:
    cov_col, claims_col, log_col = st.columns([27, 60, 34])

    with cov_col:
        covered = set(values.get("covered_categories", []))
        missing = values.get("missing_categories", [])
        total = len(covered) + len(missing) if (covered or missing) else 6
        st.markdown(f'<div class="vc-label">Coverage {len(covered)} / {total}</div>',
                    unsafe_allow_html=True)
        st.progress(len(covered) / total if total else 0.0)
        # keep chip order stable: required categories, covered first look same order
        all_cats = sorted(covered) + list(missing)
        chips = "".join(coverage_chip_html(c, c in covered) for c in all_cats)
        st.markdown(chips, unsafe_allow_html=True)
        nf = ", ".join(values.get("not_found", [])) or "none yet"
        st.markdown(
            f'<div style="{_MONO}font-size:11px;color:{INK["faint"]}">'
            f"not_found: {nf}</div>", unsafe_allow_html=True)

    with claims_col:
        claims = values.get("claims", [])
        st.markdown(f'<div class="vc-label">Claims &amp; evidence · {len(claims)}</div>',
                    unsafe_allow_html=True)
        if not claims:
            st.markdown(
                f'<div style="border:1px dashed {SURFACE["border"]};border-radius:8px;'
                f'padding:28px;text-align:center;color:{INK["sub"]}">No claims yet<br>'
                f'<span style="font-size:12px;color:{INK["faint"]}">Specialists run '
                f"only after approval — that is the cost gate.</span></div>",
                unsafe_allow_html=True,
            )
        else:
            st.dataframe(
                claims_to_rows(claims),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Source": st.column_config.LinkColumn("Source"),
                },
            )

    with log_col:
        st.markdown('<div class="vc-label">Decision log</div>', unsafe_allow_html=True)
        log = values.get("decision_log", [])
        if not log:
            st.markdown(
                f'<div style="{_MONO}font-size:12px;color:{INK["faint"]}">'
                "empty — supervisor has not run</div>", unsafe_allow_html=True)
        else:
            html = "".join(
                decision_entry_html(e, latest=(i == len(log) - 1))
                for i, e in enumerate(log)
            )
            st.markdown(html, unsafe_allow_html=True)
        if values.get("human_notes"):
            st.markdown(
                f'<div style="{_MONO}font-size:11px;color:{INK["faint"]}">'
                f'human_notes: "{values["human_notes"]}"</div>',
                unsafe_allow_html=True)


@st.dialog("Review screening decision", width="large")
def hitl_dialog(payload: dict, on_submit) -> None:
    """Frame 1a modal. on_submit(approved, override_decision, override_reason, notes)."""
    verdict = payload.get("screening_decision", "")
    v_key = "done" if verdict == "pass" else "halted"
    c = STATUS[v_key]
    st.markdown(
        f'<span style="background:{c.bg};border:1px solid {c.dot};color:{c.text};'
        f'border-radius:6px;padding:8px 14px;{_MONO}font-weight:700;'
        f'font-size:13px">{verdict.upper()}</span> '
        f'<span style="color:{INK["body"]};font-size:14px">'
        f'{payload.get("screening_reason", "")}</span>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="vc-label">Matched criteria</div>', unsafe_allow_html=True)
    chips = "".join(
        f'<span style="{_MONO}font-size:11px;color:{INK["body"]};'
        f'background:{SURFACE["chip_bg"]};border:1px solid {SURFACE["border_input"]};'
        f'border-radius:4px;padding:5px 9px;margin:0 4px 6px 0;display:inline-block">'
        f"{m}</span>"
        for m in payload.get("matched_criteria", [])
    )
    st.markdown(chips or "—", unsafe_allow_html=True)
    st.divider()

    flipped = "reject" if verdict == "pass" else "pass"
    choice = st.radio(
        "Your call",
        ["Approve — run specialists" if verdict == "pass" else "Agree — end run",
         f"Override to {flipped} — reason required",
         "End run"],
        index=0,
    )
    override_reason = ""
    if choice.startswith("Override"):
        override_reason = st.text_input("Override reason (required)")
    notes = st.text_area("Focus notes for specialists (optional)",
                         placeholder="Focus on retention and enterprise logos, not headcount.")

    st.caption("resumes via Command(resume=…)")
    if st.button("Submit decision", type="primary"):
        if choice.startswith("Override") and not override_reason.strip():
            st.error("An override needs a reason.")
            return
        if choice.startswith("Override"):
            on_submit(True, flipped, override_reason.strip(), notes or None)
        elif choice.startswith(("Approve", "Agree")):
            # Approving a reject verdict still ends the run (router checks decision)
            on_submit(True, None, None, notes or None)
        else:
            on_submit(False, None, None, notes or None)
        st.rerun()
