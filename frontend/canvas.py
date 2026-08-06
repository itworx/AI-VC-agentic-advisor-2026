"""Builds the Graphviz DOT for the graph-state canvas (spec section 3.3)."""
from __future__ import annotations

from frontend.theme import STATUS

_EDGES = [
    ("screen", "human_approval"),
    ("human_approval", "check_coverage"),
    ("check_coverage", "supervisor"),
    ("supervisor", "company_intel"),
    ("supervisor", "market_intel"),
    ("supervisor", "team_signals"),
    ("supervisor", "write_memo"),
    ("company_intel", "check_coverage"),
    ("market_intel", "check_coverage"),
    ("team_signals", "check_coverage"),
]


def build_dot(statuses: dict[str, str], sublabels: dict[str, str]) -> str:
    """One rounded box per node, tinted by status; edges in design gray."""
    lines = [
        "digraph G {",
        "rankdir=LR;",
        'bgcolor="#FBFCFD";',
        'node [shape=box style="rounded,filled" fontname="IBM Plex Mono" '
        'fontsize=11 margin="0.18,0.10"];',
        'edge [color="#9AA5B1" arrowsize=0.6];',
    ]
    for name, status in statuses.items():
        c = STATUS[status]
        label = name
        if sublabels.get(name):
            label = f"{name}\\n{sublabels[name]}"
        lines.append(
            f'{name} [label="{label}" fillcolor="{c.bg}" color="{c.dot}" '
            f'fontcolor="{c.text if status != "pending" else "#75808E"}"];'
        )
    for src, dst in _EDGES:
        lines.append(f"{src} -> {dst};")
    lines.append("}")
    return "\n".join(lines)
