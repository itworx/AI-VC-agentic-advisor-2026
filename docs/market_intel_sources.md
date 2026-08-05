# market_intel and team_signals — source list

Both specialists' actual, implemented source lists. Grouped by node.

## market_intel

External sources only (never the target company's own site — that's
company_intel/B's job).

| Source | What it's for | Cost | Confidence tier |
|---|---|---|---|
| **Tavily search (general)** | General web discovery — find candidate article URLs for a company/market | Credits (~1/call) | n/a (finds URLs; the article itself gets a tier) |
| **Tavily `site:techcrunch.com`** | Funding, competitor, market-size news coverage | Credits | `reported` |
| **Hacker News Algolia API** (`hn.algolia.com/api/v1/search`) | Community discussion/early signal on a company or competitor — no key, no cost | Free | `reported` if a linked article states something directly; `inferred` if it's just comment opinion |
| **Tavily `site:g2.com`** | Competitor/alternative lists. Direct fetch 403s (bot wall) — falls back to Tavily's own search snippet instead of losing the source | Credits | `inferred` (it's search-snippet text, not the full page) |
| **Tavily `site:sec.gov/Archives/edgar/data`** | Finds real SEC filing documents mentioning the company (its own filings if public, or peer filings that name it as a competitor) | Credits | `reported`/`verified` depending on what's quoted |

## team_signals

Company-level facts only (headcount, founding year, funding stage, public
statements) — no named individuals, ever.

| Source | What it's for | Cost | Confidence tier |
|---|---|---|---|
| **Tavily search (general)** | General web discovery for company facts | Credits | n/a |
| **Tavily `site:techcrunch.com`** | Funding announcements, headcount mentions | Credits | `reported` |
| **Tavily `site:{company domain}`** (about/team/careers) | The company's own stated facts | Credits | `verified` |
| **`data.sec.gov`** (real API: CIK lookup → submissions) | Live-tested against Swvl (publicly listed) — returned a real `verified` claim straight from its SEC 20-F filing. Returns nothing for private companies, which is correct, not a failure | Free (needs a `User-Agent` header + ≤10 req/sec) | `verified` |
| ~~**web.archive.org** (Wayback Machine availability API)~~ | Dropped — persistent `429 Too Many Requests` across multiple retries, different schemes, different headers. Not a code bug; looks like an IP-reputation rate limit on this environment specifically | — | — |

## Out of scope (considered and rejected for both nodes)

- **AlternativeTo.net API** — no confirmed public endpoint; excluded until one is verified.
- **USPTO PatentsView** — endpoint has moved and now requires registration; shared patent classification is also a weak competitor proxy.
- **Wikidata SPARQL competitor queries** — no reliable "competitor" relation in Wikidata's schema; excluded.
- **Payroll-multiplier TAM formulas** — not sourced from any dataset; any market-size math stays in code, not in a prompt.
- **MENA/Gulf registries** (ADGM, DIFC, Wamda, Saudi Open Data) — out of scope for the current US-focused build; candidates for a future regional expansion.
- **US Census Bureau CBP API** — bottom-up NAICS sizing, still a good idea for market_intel specifically, just not built yet.
