# market_intel — source list

External sources only (never the target company's own site — that's
company_intel/B's job). Grouped by implementation status.

## In use

| Source | What it's for | Cost | Confidence tier |
|---|---|---|---|
| **Tavily search** | General web discovery — find candidate article URLs for a company/market | Credits (~1/call) | n/a (finds URLs; the article itself gets a tier) |
| **TechCrunch (via fetch_service)** | Funding, competitor, market-size news coverage | Free | `reported` |
| **Hacker News Algolia API** (`hn.algolia.com/api/v1/search`) | Community discussion/early signal on a company or competitor — no key, no cost | Free | `reported` if a linked article states something directly; `inferred` if it's just comment opinion |
| **Tavily `site:g2.com` / `site:capterra.com` search operators** | Indirect competitor-list snippets from G2/Capterra without hitting their Cloudflare wall directly | Credits | `inferred` (it's search-snippet text, not the full page) |
| **Tavily `site:sec.gov/Archives/edgar/data "competes directly with"`** | Phrase-mining real 10-K competitor disclosures | Credits | `reported`/`verified` depending on what's quoted |

## Planned, not yet built

| Source | What it's for | Cost | Confidence tier |
|---|---|---|---|
| **SEC EDGAR** (`data.sec.gov`) — CIK lookup → submissions → XBRL `companyfacts` | Maps a private target to a public peer for real financial baselines; legally-binding competitor/risk language from 10-K/S-1 filings | Free (needs a `User-Agent` header + ≤10 req/sec) | `verified` |
| **US Census Bureau CBP API** (`api.census.gov/data/2021/cbp`) | Bottom-up market sizing by NAICS code (establishment counts, payroll, employees) | Free | `verified` (raw counts) — any TAM multiplier applied to these is code-level math, never an LLM-generated number |

## Out of scope

- **AlternativeTo.net API** — no confirmed public endpoint; excluded until one is verified.
- **USPTO PatentsView** — endpoint has moved and now requires registration; shared patent classification is also a weak competitor proxy.
- **Wikidata SPARQL competitor queries** — no reliable "competitor" relation in Wikidata's schema; excluded.
- **Payroll-multiplier TAM formulas** — not sourced from any dataset; any market-size math stays in code, not in a prompt.
- **MENA/Gulf registries** (ADGM, DIFC, Wamda, Saudi Open Data) — out of scope for the current US-focused build; candidates for a future regional expansion.
