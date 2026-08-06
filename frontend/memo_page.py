"""Memo page (frame 1d). write_memo is a backend stub until M-01,
so this shows whatever memo_base contains, plus a CSV export of claims."""
from __future__ import annotations

import csv
import io

import streamlit as st

from frontend import graph_client
from frontend.run_state import claims_to_rows


def memo_page() -> None:
    st.title("IC Memo")
    if "config" not in st.session_state:
        st.info("No run yet. Start one on the Run console page.")
        return

    values, next_nodes, _ = graph_client.snapshot(
        st.session_state.graph, st.session_state.config
    )
    if not values.get("memo_base"):
        st.info("Memo not written yet — the run has not reached write_memo.")
        return

    st.subheader("Base case")
    st.markdown(values["memo_base"])
    if values.get("memo_bull"):
        st.subheader("Bull case")
        st.markdown(values["memo_bull"])
    if values.get("memo_bear"):
        st.subheader("Bear case")
        st.markdown(values["memo_bear"])

    rows = claims_to_rows(values.get("claims", []))
    if rows:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        st.download_button(
            "Download claims CSV",
            buf.getvalue(),
            file_name=f"{values['company_name']}-claims.csv",
            mime="text/csv",
        )


memo_page()
