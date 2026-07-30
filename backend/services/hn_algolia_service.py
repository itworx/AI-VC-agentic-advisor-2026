"""
Hacker News Algolia API. Free, unauthenticated discovery source -- returns
HN stories mentioning a query, with the linked external URL when present
(falls back to the HN discussion thread itself for self-posts).
"""
import requests

HN_ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search"


def search_hn(query: str, max_results: int = 5) -> list[dict]:
    try:
        response = requests.get(
            HN_ALGOLIA_SEARCH_URL,
            params={"query": query, "tags": "story"},
            timeout=10,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[hn_algolia_service] search failed: {e}")
        return []

    hits = response.json().get("hits", [])[:max_results]
    results = []
    for hit in hits:
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        results.append({"url": url, "title": hit.get("title") or ""})
    return results
