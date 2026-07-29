"""
End-to-end pipe test: fetch_service -> extraction prompt -> local granite3.3.

Two cases: one article that should contain a competitor/market fact
(found: true), and one unrelated article for an unrelated company
(found: false). Kept out of tests/ since a local LLM call is too slow
for a normal test run.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.services.fetch_service import fetch_page  # noqa: E402
from langchain_ollama import ChatOllama  # noqa: E402

PROMPT_TEMPLATE = (REPO_ROOT / "backend/prompts/specialists/market_intel_extraction.txt").read_text(
    encoding="utf-8"
)

llm = ChatOllama(model="granite3.3", temperature=0)

CASES = [
    {
        "label": "POSITIVE (expect found: true)",
        "company_name": "Runway",
        "url": "https://techcrunch.com/2026/02/10/ai-video-startup-runway-raises-315m-at-5-3b-valuation-eyes-more-capable-world-models",
    },
    {
        "label": "NEGATIVE (expect found: false)",
        "company_name": "Ramp",
        "url": "https://techcrunch.com/2023/10/20/tam-sam-som-is-only-for-founders-who-think-small",
    },
]

for case in CASES:
    print("=" * 70)
    print(case["label"], "-", case["company_name"])
    fetched = fetch_page(case["url"])
    if fetched.status != "ok":
        print(f"  fetch failed: {fetched.status} ({fetched.reason})")
        continue

    prompt = PROMPT_TEMPLATE.format(
        company_name=case["company_name"],
        article_text=fetched.text[:6000],
    )
    response = llm.invoke(prompt)
    print(response.content)
    try:
        parsed = json.loads(response.content)
        print("\n  parsed OK:", parsed)
    except json.JSONDecodeError:
        print("\n  [!] model did not return valid JSON")
    print()
