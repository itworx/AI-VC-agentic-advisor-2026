# Streamlit backend API

The UI calls three functions in `backend/api.py`. Never touches LangGraph directly.

## Contract

```python
from backend.api import start_run, submit_approval, get_status, get_history

# 1. User clicks "Run"
handle, status = start_run(company_name, company_url)
# status["status"] == "awaiting_approval" if screen ran; render the approval form

# 2. User clicks approve/reject/override on the form
status = submit_approval(handle, {
    "approved": True,
    "override_decision": None,       # or "pass" / "reject"
    "override_reason": None,          # or str
    "notes": None,                    # or str
})
# status["status"] == "complete" | "rejected" | "error"

# 3. UI can re-read state at any point
status = get_status(handle)

# 4. Optional: render a run trace
history = get_history(handle)  # oldest first, each entry has next_nodes + values
```

## Storing state between renders

Streamlit re-runs the script on every interaction. Store `handle` in `st.session_state`:

```python
if "handle" not in st.session_state:
    st.session_state.handle = None

if st.button("Run"):
    handle, status = start_run(name, url)
    st.session_state.handle = handle
    st.session_state.status = status

if st.session_state.handle:
    # render status, offer approve/reject buttons, etc.
    ...
```

## Status values

- `awaiting_approval` — graph paused at HITL, render the approval form
- `running` — mid-run (shouldn't normally see this since invoke blocks; useful if streaming is added later)
- `complete` — full pipeline finished, memo populated
- `rejected` — either screen or HITL rejected; specialists never ran
- `error` — check `status["error"]` for the message

## Fields the UI can display

Every status contains these fields (empty string / empty list if not yet populated):
- `screening_decision`, `screening_reason`, `matched_criteria`
- `specialists_run`, `claims`, `covered_categories`, `missing_categories`, `not_found`
- `decision_log` (one entry per supervisor turn — great for a "why did the agent do this" panel)
- `iteration_count`
- `memo_bull`, `memo_base`, `memo_bear`, `memo_rendered`