from __future__ import annotations

import re


def normalise_url(url: str) -> str:
    # HttpUrl adds a trailing slash to bare domains; strip it before comparing
    return str(url).rstrip("/")


def normalise_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def verify_claims(claims: list, pages: list[dict]) -> tuple[list, list]:
    # drops any claim whose source_url or quoted_snippet doesn't match a fetched page
    page_by_url = {
        normalise_url(p["url"]): normalise_whitespace(p.get("content", ""))
        for p in pages
    }

    safe, dropped = [], []
    for claim in claims:
        page_content = page_by_url.get(normalise_url(claim.source_url))
        if page_content is None:
            dropped.append(claim)
            continue
        if normalise_whitespace(claim.quoted_snippet) not in page_content:
            dropped.append(claim)
            continue
        safe.append(claim)

    if dropped:
        print(f"[claim_verifier] dropped {len(dropped)} unverified claim(s)")

    return safe, dropped
