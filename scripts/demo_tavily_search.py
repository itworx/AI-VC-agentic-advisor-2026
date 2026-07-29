"""
Minimal one-shot Tavily API smoke test.

Confirms the API key works and shows the shape of a Tavily search
response. Runs exactly one search call (~1 credit). Kept out of tests/
on purpose since it spends a paid credit every run.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv(Path(__file__).parent.parent / ".env")

api_key = os.environ.get("TAVILY_API_KEY")
if not api_key:
    raise SystemExit("TAVILY_API_KEY not set — check .env")

client = TavilyClient(api_key=api_key)

response = client.search(
    query="site:techcrunch.com market size",
    max_results=3,
    search_depth="basic",
)

print(f"query: {response['query']}")
print(f"results: {len(response['results'])}\n")

for r in response["results"]:
    print(f"- {r['title']}")
    print(f"  {r['url']}")
    print(f"  score: {r['score']}")
    print()
