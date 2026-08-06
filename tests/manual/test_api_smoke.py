"""End-to-end smoke test of the Streamlit-facing API.

Runs Instabug through the whole pipeline the way the UI would:
  1. start_run(name, url) → graph runs screen, pauses at human_approval
  2. submit_approval(handle, {approved: True}) → runs specialists + memo
  3. get_status(handle) → final state
  4. get_history(handle) → full checkpoint trail

Costs real API money. Only run when Gemini free tier has quota available.
"""
from backend.api.streamlit_api import start_run, submit_approval, get_status, get_history


print("=== 1. start_run ===")
handle, status = start_run("Instabug", "https://instabug.com")
print(f"status: {status['status']}")
print(f"screening_decision: {status['screening_decision']}")
print(f"screening_reason: {status['screening_reason'][:200]}...")
print(f"matched_criteria: {status['matched_criteria']}")

assert status["status"] == "awaiting_approval", (
    f"expected paused at approval, got {status['status']}"
)
assert status["screening_decision"] in ("pass", "reject")
assert status["screening_reason"], "screening_reason should not be empty"


print("\n=== 2. submit_approval (approve) ===")
status = submit_approval(handle, {"approved": True})
print(f"status: {status['status']}")
print(f"specialists_run: {status['specialists_run']}")
print(f"claims: {len(status['claims'])}")
print(f"covered: {status['covered_categories']}")
print(f"missing: {status['missing_categories']}")
print(f"not_found: {status['not_found']}")
print(f"iteration_count: {status['iteration_count']}")

assert status["status"] == "complete", (
    f"expected complete after approval, got {status['status']}"
)
assert status["iteration_count"] > 0, "supervisor should have run at least once"


print("\n=== 3. Decision log ===")
for entry in status["decision_log"]:
    print(f"  iter {entry['iteration']}: chose {entry['chosen']} — {entry['reason']}")


print("\n=== 4. Memo output ===")
print(f"memo_bull length: {len(status['memo_bull'])} chars")
print(f"memo_base length: {len(status['memo_base'])} chars")
print(f"memo_bear length: {len(status['memo_bear'])} chars")
print(f"memo_rendered length: {len(status['memo_rendered'])} chars")

if status["memo_rendered"]:
    print(f"\nMemo preview (first 600 chars):\n{status['memo_rendered'][:600]}...")


print("\n=== 5. get_status is idempotent (call it again) ===")
status2 = get_status(handle)
assert status2["status"] == status["status"]
assert len(status2["claims"]) == len(status["claims"])
print("get_status returns consistent state on repeated calls ✓")


print("\n=== 6. get_history ===")
history = get_history(handle)
print(f"history entries: {len(history)}")
print("first 3 checkpoints (oldest first):")
for i, entry in enumerate(history[:3]):
    print(f"  [{i}] next_nodes: {entry['next_nodes']}")

assert len(history) >= 5, f"expected several checkpoints, got {len(history)}"


print("\n=== ALL CHECKS PASSED ===")