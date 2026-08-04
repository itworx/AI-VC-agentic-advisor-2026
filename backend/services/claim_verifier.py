"""
S-01: verifies a claim's citation actually holds up against the pages it
was extracted from. Asking the model nicely to only cite real URLs and
real quotes is necessary but not sufficient -- this is the code-level
check that actually enforces it.
"""
from __future__ import annotations


def _normalize_url(url) -> str:
    return str(url).strip().rstrip("/")


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def verify_claims(claims: list, pages: list[dict], node_name: str = "claim_verifier") -> tuple[list, list]:
    """Returns (verified_claims, rejected_claims).

    A claim is rejected outright if its source_url doesn't match any page
    we actually fetched -- there's nothing to fall back to, the citation
    is fabricated. A claim whose source_url is real but whose
    quoted_snippet isn't actually present in that page's text gets
    downgraded to "inferred" rather than dropped -- the underlying fact
    may still be real, just misquoted.
    """
    pages_by_url = {_normalize_url(p["url"]): p["content"] for p in pages}

    verified, rejected = [], []
    downgraded = 0

    for claim in claims:
        page_content = pages_by_url.get(_normalize_url(claim.source_url))

        if page_content is None:
            rejected.append(claim)
            continue

        snippet = _normalize_whitespace(claim.quoted_snippet)
        content = _normalize_whitespace(page_content)
        if snippet not in content:
            claim.confidence = "inferred"
            downgraded += 1

        verified.append(claim)

    if rejected:
        print(f"[{node_name}] rejected {len(rejected)} claim(s) citing a URL not in the fetched pages:")
        for c in rejected:
            print(f"    rejected: \"{c.claim_text}\" -> {c.source_url}")

    if downgraded:
        print(f"[{node_name}] downgraded {downgraded} claim(s) to 'inferred': quoted_snippet not found verbatim in its source page")

    return verified, rejected
