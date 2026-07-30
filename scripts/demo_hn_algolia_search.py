"""
Hacker News Algolia API smoke test.

Free, unauthenticated discovery/search source (same role as Tavily
search, not a URL fetcher). Useful for community sentiment and early
signal on a company, not for official numbers.
"""
import requests

response = requests.get(
    "https://hn.algolia.com/api/v1/search",
    params={"query": "Ramp funding", "tags": "story"},
    timeout=10,
)
response.raise_for_status()
data = response.json()

print(f"total hits: {data['nbHits']}\n")

for hit in data["hits"][:5]:
    print(f"- {hit['title']}")
    print(f"  points: {hit['points']}  comments: {hit['num_comments']}")
    print(f"  hn thread: https://news.ycombinator.com/item?id={hit['objectID']}")
    if hit.get("url"):
        print(f"  linked url: {hit['url']}")
    print()
