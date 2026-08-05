"""Manual test: verify write_memo_node adapter works with real Claim dicts.
Bypasses the graph so we don't need Gemini quota to test the memo path.
"""
from datetime import datetime, timezone
from backend.graph import write_memo_node
from backend.state import create_initial_state


# Fabricate some claims in the same shape state stores them
fake_claims = [
    {
        "claim_text": "Instabug is a mobile observability platform for engineering teams.",
        "source_url": "https://instabug.com",
        "quoted_snippet": "Mobile observability for engineering teams",
        "specialist": "company_intel",
        "confidence": "verified",
        "category": "what_company_does",
        "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
    },
    {
        "claim_text": "Instabug serves enterprise customers including major mobile brands.",
        "source_url": "https://instabug.com",
        "quoted_snippet": "Trusted by the world's most beloved brands",
        "specialist": "company_intel",
        "confidence": "verified",
        "category": "target_customer",
        "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
    },
    {
        "claim_text": "The mobile observability market is competitive with Firebase Crashlytics as a key rival.",
        "source_url": "https://example.com/market",
        "quoted_snippet": "Firebase Crashlytics is Instabug's main direct rival",
        "specialist": "market_intel",
        "confidence": "reported",
        "category": "competitors",
        "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
    },
]

state = create_initial_state("Instabug", "https://instabug.com")
state["claims"] = fake_claims

result = write_memo_node(state)

print("=== Bull case ===")
print(result["memo_bull"])
print("\n=== Base case ===")
print(result["memo_base"])
print("\n=== Bear case ===")
print(result["memo_bear"])
print("=== Rendered memo (with citations resolved) ===")
print(result["memo_rendered"])