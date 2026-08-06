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

model = ChatGoogleGenerativeAI(model="gemini-3.6-flash")
structured_model = model.with_structured_output(SpecialistOutput, include_raw=True)
search_tool = TavilySearch(max_results=5)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "specialists" / "company_intel_extraction.txt"
PROMPT_TEMPLATE = PROMPT_PATH.read_text()


def looks_like_named_individual(claim_text: str) -> bool:
    words = claim_text.split()
    cleaned_words = [w.strip(".,()\"'") for w in words]

    has_person_context = any(
        w.lower().strip(".,()\"'") in {c.lower() for c in PERSON_CONTEXT_WORDS}
        for w in cleaned_words
    )
    if not has_person_context:
        return False

    consecutive_capitalized = 0
    for cleaned in cleaned_words:
        is_capitalized_word = (
            cleaned[:1].isupper()
            and cleaned not in NON_NAME_CAPITALIZED_WORDS
            and cleaned.isalpha()
        )
        if is_capitalized_word:
            consecutive_capitalized += 1
            if consecutive_capitalized >= 2:
                return True
        else:
            consecutive_capitalized = 0
    return False


def filter_named_individuals(claims: list) -> tuple[list, list]:
    safe, dropped = [], []
    for claim in claims:
        if looks_like_named_individual(claim.claim_text):
            dropped.append(claim)
        else:
            safe.append(claim)

    if dropped:
        print(f"[company_intel] dropped {len(dropped)} claim(s) that looked like a named individual:")
        for c in dropped:
            print(f"    dropped: \"{c.claim_text}\"")

    return safe, dropped


def fetch_company_pages(company_name: str, company_website: str) -> list[dict]:
    query = f"{company_name} site:{company_website}"
    try:
        results = search_tool.invoke({"query": query})
    except Exception as e:
        print(f"[company_intel] search failed: {e}")
        return []

    pages = results.get("results", [])
    if not pages:
        print(f"[company_intel] no pages found for {company_name} on {company_website}")
    return pages


def build_extraction_prompt(company_name: str, pages: list[dict]) -> str:
    page_blocks = "\n\n".join(
        f"URL: {p['url']}\nCONTENT:\n{p['content']}"
        for p in pages
    )
    return PROMPT_TEMPLATE.format(company_name=company_name, page_blocks=page_blocks)


def company_intel(company_name: str, company_website: str) -> SpecialistOutput:
    pages = fetch_company_pages(company_name, company_website)

    if not pages:
        return SpecialistOutput(claims=[], not_found=COMPANY_INTEL_CATEGORIES)

    prompt = build_extraction_prompt(company_name, pages)

    try:
        response = structured_model.invoke(prompt)
    except Exception as e:
        print(f"[company_intel] extraction failed: {e}")
        try:
            response = structured_model.invoke(prompt)
        except Exception as e2:
            print(f"[company_intel] retry failed: {e2}")
            return SpecialistOutput(claims=[], not_found=COMPANY_INTEL_CATEGORIES)

    result: SpecialistOutput = response["parsed"]

    usage = getattr(response["raw"], "usage_metadata", None) or {}
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cost = estimate_cost(input_tokens, output_tokens)
    log_cost(
        node_name="company_intel",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=cost,
    )

    fetched_at = datetime.now(timezone.utc)

    for claim in result.claims:
        claim.specialist = "company_intel"
        claim.retrieval_timestamp = fetched_at

    verified_claims, _rejected = verify_claims(result.claims, pages, node_name="company_intel")
    safe_claims, _dropped = filter_named_individuals(verified_claims)
    result.claims = safe_claims

    return result


if __name__ == "__main__":
    output = company_intel("Vezeeta", "vezeeta.com")

    print(f"\nClaims found: {len(output.claims)}")
    for c in output.claims:
        print(f"  [{c.category}] ({c.confidence}) {c.claim_text}")
        print(f"    source: {c.source_url}")
        print(f"    quote: \"{c.quoted_snippet}\"")

    print(f"\nNot found: {output.not_found}")
