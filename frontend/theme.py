"""Design tokens lifted verbatim from 'VC Advisor Frontend.dc.html'.

Single source of truth for colors in the UI. See
vc-advisor-frontend-spec.md section 2 for the full palette tables.
"""
from __future__ import annotations

from typing import NamedTuple


class StatusColors(NamedTuple):
    dot: str      # dot / strong border
    bg: str       # tint background
    border: str   # soft border
    text: str     # dark text on the tint


STATUS: dict[str, StatusColors] = {
    "done":    StatusColors("#0F8A6D", "#EAF6F2", "#A9D8C9", "#0B7259"),
    "running": StatusColors("#B26A00", "#FDF3E3", "#E8CFA0", "#8A5200"),
    "waiting": StatusColors("#5348B8", "#EFEDFB", "#C6C0EC", "#4438A8"),
    "pending": StatusColors("#C2C9D2", "#FAFBFC", "#DDE2E8", "#75808E"),
    "halted":  StatusColors("#B3261E", "#FDEDEC", "#EFC5C1", "#9B2018"),
}

INK = {
    "main": "#1A2129",
    "body": "#333D49",
    "sub": "#64707E",
    "muted": "#75808E",
    "faint": "#7C8694",
}

SURFACE = {
    "card": "#FFFFFF",
    "panel": "#F7F8FA",
    "canvas": "#FBFCFD",
    "table_head": "#EFF2F5",
    "chip_bg": "#EDF0F3",
    "border": "#DDE2E8",
    "border_card": "#D8DDE4",
    "border_soft": "#E3E7EC",
    "border_input": "#D5DBE3",
    "edge": "#B8C1CB",
    "link": "#1662C4",
}

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; color: #1A2129; }
@keyframes pulseDot { 0%,100% { opacity:1 } 50% { opacity:.25 } }
.vc-mono { font-family: 'IBM Plex Mono', monospace; }
.vc-label { font: 600 10px 'IBM Plex Mono', monospace; letter-spacing:.16em;
            text-transform: uppercase; color:#75808E; }
a { color:#1662C4; text-decoration:none; }
a:hover { color:#0F4E9E; }
</style>
"""
