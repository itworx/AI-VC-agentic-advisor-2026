from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from langchain_tavily import TavilySearch
from langchain_google_genai import ChatGoogleGenerativeAI

from backend.models.claim import SpecialistOutput
from backend.services.claim_verifier import verify_claims
from backend.utils.cost_logger import log_cost
from backend.utils.token_cost import estimate_cost
from backend.nodes.company_intel_constants import (
    COMPANY_INTEL_CATEGORIES,
    NON_NAME_CAPITALIZED_WORDS,
    PERSON_CONTEXT_WORDS,
)

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "specialists" / "company_intel_extraction.txt"
PROMPT_TEMPLATE = PROMPT_PATH.read_text(encoding="utf-8")

model = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
structured_model = model.with_structured_output(SpecialistOutput, include_raw=True)
search_tool = TavilySearch(max_results=5)


def looks_like_named_individual(claim_text: str) -> bool:
    words = [w.strip(".,()\"'") for w in claim_text.split()]

    if not any(w.lower() in {c.lower() for c in PERSON_CONTEXT_WORDS} for w in words):
        return False

    streak = 0
    for w in words:
        is_name_like = w[:1].isupper() and w not in NON_NAME_CAPITALIZED_WORDS and w.isalpha()
        streak = streak + 1 if is_name_like else 0
        if streak >= 2:
            return True
    return False


def filter_named_individuals(claims: list) -> tuple[list, list]:
    safe = [c for c in claims if not looks_like_named_individual(c.claim_text)]
    dropped = [c for c in claims if looks_like_named_individual(c.claim_text)]
    if dropped:
        print(f"[company_intel] dropped {len(dropped)} claim(s) that named an individual")
    return safe, dropped


def fetch_company_pages(company_name: str, company_website: str) -> list[dict]:
    query = f"{company_name} site:{company_website}"
    try:
        results = search_tool.invoke({"query": query})
    except Exception as e:
        print(f"[company_intel] source unreachable: {e}")
        return []

    pages = results.get("results", [])
    usable_pages = []
    for p in pages:
        if not p.get("content", "").strip():
            print(f"[company_intel] no text content found: {p.get('url')}")
            continue
        usable_pages.append(p)

    return usable_pages


def build_extraction_prompt(company_name: str, pages: list[dict]) -> str:
    page_blocks = "\n\n".join(f"URL: {p['url']}\nCONTENT:\n{p['content']}" for p in pages)
    return PROMPT_TEMPLATE.format(company_name=company_name, page_blocks=page_blocks)


def run_extraction(prompt: str) -> dict | None:
    for attempt in range(2):
        try:
            return structured_model.invoke(prompt)
        except Exception as e:
            print(f"[company_intel] extraction attempt {attempt + 1} failed: {e}")
    return None


def company_intel(company_name: str, company_website: str) -> SpecialistOutput:
    pages = fetch_company_pages(company_name, company_website)
    if not pages:
        return SpecialistOutput(claims=[], not_found=COMPANY_INTEL_CATEGORIES)

    prompt = build_extraction_prompt(company_name, pages)
    response = run_extraction(prompt)
    if response is None:
        return SpecialistOutput(claims=[], not_found=COMPANY_INTEL_CATEGORIES)

    result: SpecialistOutput = response["parsed"]

    usage = getattr(response["raw"], "usage_metadata", None) or {}
    cost = estimate_cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0))
    log_cost(
        node_name="company_intel",
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        estimated_cost=cost,
    )

    fetched_at = datetime.now(timezone.utc)
    for claim in result.claims:
        claim.specialist = "company_intel"
        claim.retrieval_timestamp = fetched_at

    result.claims, _ = verify_claims(result.claims, pages, node_name="company_intel")
    result.claims, _ = filter_named_individuals(result.claims)

    return result


if __name__ == "__main__":
    output = company_intel("Vezeeta", "vezeeta.com")
    print(f"\nClaims found: {len(output.claims)}")
    for c in output.claims:
        print(f"  [{c.category}] ({c.confidence}) {c.claim_text}")
        print(f"    source: {c.source_url}")
        print(f"    quote: \"{c.quoted_snippet}\"")
    print(f"\nNot found: {output.not_found}")
