# AI VC Agentic Advisor

## Overview

AI VC Agentic Advisor is a multi-agent venture capital research system designed to automate the early stages of startup evaluation and investment memo generation.

The system uses a supervisor-based agent architecture built with LangGraph, where a central supervisor coordinates multiple specialist agents responsible for gathering and validating information about a company, its market, and organizational signals.

The final output is a structured, citation-backed Investment Committee (IC) Memo that provides a Base Case, Bull Case, and Bear Case for human review.

This project is being developed as part of the ITWorx AI Engineering Internship Program and serves as a practical implementation of multi-agent orchestration, structured outputs, human-in-the-loop workflows, and research automation.

---

## Project Objectives

The project aims to:

- Build a supervisor-driven multi-agent workflow
- Demonstrate intelligent task routing between specialist agents
- Generate evidence-based investment research
- Enforce citation-backed claims
- Implement human-in-the-loop approval checkpoints
- Prevent hallucinations through structured outputs and validation
- Produce transparent and auditable research reports

---

## Scope

### In Scope

The system accepts:

- Company Name
- Company Website

And performs:

### 1. Screening

- Early thesis-fit evaluation
- Cheap rejection path before expensive research

### 2. Supervisor Orchestration

- Determines which specialist runs next
- Tracks coverage gaps
- Controls stopping conditions
- Logs workflow decisions

### 3. Specialist Research Agents

#### Company Intelligence

Researches:

- Products and services
- Business model
- Company positioning
- Public company information

#### Market Intelligence

Researches:

- Market size
- Industry trends
- Competitive landscape
- Market positioning

#### Team Signals

Researches company-level information only:

- Company age
- Public organizational signals
- Growth indicators
- Workforce-related public information

### 4. Memo Generation

Generates:

- Base Case
- Bull Case
- Bear Case

using validated claims collected by specialist agents.

### 5. Citation Tracking

- Every claim linked to a source
- Traceable evidence for all research findings

### 6. Human-in-the-Loop (HITL)

- Input verification
- Approval checkpoints
- Workflow interruption and resume support

### 7. Evaluation and Validation

- Memo traceability checks
- Coverage verification
- Quality assessment

---

## Out of Scope

The following capabilities are intentionally excluded:

- Claims about named individuals
- Legal due diligence
- Cap table analysis
- Sanctions screening
- Portfolio monitoring
- Deal sourcing across the internet
- Investment recommendations
- Pitch deck analysis

> The system supports human decision-making and does not make investment decisions.

---

## System Architecture

### Supervisor Agent

Responsible for:

- Workflow orchestration
- Specialist selection
- Coverage monitoring
- Iteration control
- Decision logging

### Specialist Agents

#### Company Intelligence

Researches:

- Products
- Services
- Business model
- Public company claims

#### Market Intelligence

Researches:

- Market size
- Industry trends
- Competitors
- Market positioning

#### Team Signals

Researches:

- Company age
- Growth indicators
- Public organizational information

No claims about named individuals are allowed.

### Memo Writer

Generates:

- Base Case
- Bull Case
- Bear Case

using validated claims only.

### Evaluator

Verifies:

- Claim traceability — every memo sentence traces to a claim in the claims list
- Citation integrity — no marker may point at a claim that doesn't exist
- Rejects with feedback naming the specific offending sentences, capped at 2 passes

Implementation detail in [Evaluator (E-01 / E-02 / E-03)](#evaluator-e-01--e-02--e-03) below.

---

## Graph Architecture (Role A)

### Overview

The system is a single LangGraph state graph. All nodes read from and write to a shared `State` object. Routing between nodes is deterministic and controlled by two pure-Python router functions: one after human approval, one after the supervisor.

### Node flow

```
START
  │
  ▼
[screen] ── one cheap LLM call, judges thesis fit from homepage content
  │
  ▼
[human_approval] ── interrupt() pauses the graph until a human responds
  │
  ├─ approved=False or decision=reject ──► END
  │
  └─ approved=True and decision=pass
       │
       ▼
    [check_coverage] ── pure Python, computes covered vs missing categories
       │
       ▼
    [supervisor] ── ~30 lines of Python, picks next specialist or memo
       │
       ├─► [company_intel] ──┐
       ├─► [market_intel]  ──┼──► back to [check_coverage]
       ├─► [team_signals]  ──┘
       │
       └─► [write_memo] ── model sees the claims list only, never raw web text.
             │              Emits the raw <<N>> draft; no rendering here.
             ▼
          [evaluate] ── every memo sentence must trace to a claim
             │
             ├─ rewrite (blocking violations, under the 2-pass cap)
             │     └──► back to [write_memo] with the feedback attached
             │
             └─ accept / accept_capped
                   │
                   ▼
             [render_citations] ── [k] footnotes, Sources, 4-page cap, and on
                   │               accept_capped a warning banner
                   ▼
                  END
```

Rendering sits **downstream** of the evaluator, not upstream. `render_citations`
raises `UnresolvedCitationError` on an out-of-range `<<N>>`, so with the original
ordering a hallucinated citation killed the run inside the renderer before the
evaluator could turn it into a clean reject — making the evaluator's
`unresolved_citation` verdict unreachable in production. The evaluator doesn't
need rendered text anyway: it reads the raw `<<N>>` draft, where markers are
claim indices directly rather than renumbered footnotes.
### Screening

`backend/nodes/screening/screen_company.py`. One LLM call against a small model (Claude Haiku 4.5 via OpenRouter). Fetches the company homepage (up to 4,000 chars) so it judges from real content rather than the model's training data. Returns `{decision: pass|reject, reason, matched_criteria}`.

### Human-in-the-loop

`backend/nodes/hitl/human_approval.py`. Calls LangGraph's `interrupt()` after screening and before any specialist runs. State is persisted via `SqliteSaver` to `checkpoints/hitl.db`, so the pause survives full process termination. The human resumes with a `Command(resume=...)` payload containing `{approved, override_decision, override_reason, notes}`. This gate is what stops the system spending on specialist research when the screening result should not proceed.

### Supervisor

`backend/nodes/supervisor/supervisor.py`. Hand-written (no pre-built library, per the brief). Each turn, the supervisor:

1. Reads `missing_categories` from state
2. Picks the specialist that covers the most missing categories, in deterministic order
3. Appends a decision-log entry (`iteration`, `chosen`, `reason`, `missing_categories`)

**Three stop conditions:**

- Coverage complete: all required categories filled → route to `write_memo`
- Iteration cap hit (6 turns): route to `write_memo` with whatever's collected
- Specialists exhausted: every specialist that could cover a remaining gap has already run → route to `write_memo`

The iteration cap is the guard against infinite loops.

### Evaluator (E-01 / E-02 / E-03)

`backend/nodes/evaluation/`. Two tiers, and the split is the design:

| | Tier 1 — `evaluate.py` | Tier 2 — `support.py` |
|---|---|---|
| Question | Is there a marker, and does it resolve? | Does the cited claim actually *say* this? |
| Method | Pure Python | One model call per pass |
| Cost | Free | ~1 cheap call (Haiku) |
| Authority | Final — nothing can clear its findings | Can only **add** violations |

Tier 1 is the floor precisely because it can't be argued with. But marker
presence is not entailment, and that leaves the obvious hole: a model satisfies
tier 1 completely by spraying plausible markers onto sentences the claims don't
support. Closing that needs a judge, so tier 2 is quarantined in its own module,
sees **only** the sentence and its cited claim text — never the memo, the other
claims, or any web content — and uses a *different* model from the memo writer,
since a judge sharing the writer's blind spots is worth much less.

Tier 2's structural guarantee is that it can only add violations. No amount of
agreeable judging can unblock a sentence carrying no citation at all. Its
verdicts default to **unsupported** when the judge omits, duplicates, or
out-of-ranges an index — a judge that fails to answer must not thereby wave a
sentence through. If the support model is unreachable the run continues on tier 1
and records that it degraded, rather than silently losing coverage.

It reads the raw draft sections (`memo_bull`/`memo_base`/`memo_bear`), which
still carry write_memo's `<<N>>` markers pointing straight at claim indices —
not `memo_rendered`, whose `[k]` footnotes have been renumbered to
first-appearance order and would need mapping back through
`render_citations`' id_map to mean anything.

**E-01 — traceability.** Splits each section into sentences (conservatively:
no splitting inside `$1.2 billion`, `U.S.`, or initials; bullet items count as
sentences even without terminal punctuation, since an unsourced figure hiding
in a bullet is exactly the failure mode being hunted). Each sentence is then
classified:

| Kind | Blocking? | Meaning |
|---|---|---|
| `untraced_factual` | **yes** | no `<<N>>` marker but asserts something about the company — the invented market size / customer count / team size case, and equally an uncited product or positioning claim carrying no numbers at all |
| `unresolved_citation` | **yes** | cites `<<N>>` where N is not a real claim index. A marker pointing at nothing looks *sourced* to a reader, so it can never be advisory |
| `unsupported_by_claim` | **yes** | tier 2: cites a real claim that doesn't say this. Misattribution is the failure a citation is supposed to make impossible |
| `untraced` | no | no marker, but the sentence is about the memo's own reasoning rather than the company ("the bear case rests on what the claims do not tell us"). It asserts nothing that could be true or false |
| `weak_support` | no | cites a claim it shares no content words with. A cheap lexical hint, superseded by `unsupported_by_claim` whenever tier 2 runs |

**An unmarked sentence is blocking by default.** Exactly two things excuse one:

1. A statement that information could not be found — there is no claim to cite
   for a gap.
2. A statement about the memo's own reasoning rather than the company.

Digits and currency are checked first and override both exemptions, so neither
"revenue is around 40 million, though not publicly disclosed" nor "the bear case
rests on 40% annual churn" can launder a figure past the check.

**Gap statements are detected structurally, not by phrase list.** A negation word
(`no`, `not`, `absent`, `absence`, `lack`, `without`) followed within 60
characters — never across a sentence boundary — by an *information* word (`data`,
`claims`, `evidence`, `traction`, `figures`, `disclosed`, `basis`, `transparency`,
…), plus standalone forms like `undisclosed` / `unreported` that mean absence on
their own. Two successive live runs each added one phrase a literal list didn't
have, which is the signature of a rule enumerated at the wrong level: memos have
many ways to say "we don't know this" and only so many words for the knowing.

The pairing is what keeps it honest. A bare negation word would exempt far too
much — *"Absent serious competitors, Instabug dominates the market"* is an
unsourced assertion, not a gap statement, and `competitors` is not an information
word, so it stays blocking. That loophole and three variants of it are pinned by
tests.

**Why the default runs this way round.** The first version inverted it: an
allowlist of factual-sounding words (revenue, market, headcount…) with anything
else assumed connective. A live run walked straight through it — *"Instabug
provides mobile app monitoring and bug reporting tools for developers"* contains
no finance vocabulary, so an uncited product claim scored as merely advisory.
Any allowlist of factual words has that hole, because the set of things a
company can factually do is unbounded; the set of ways to refer to this memo's
own reasoning is not. When the current heuristic is wrong it costs a rework
cycle. When the old one was wrong, an uncited assertion shipped.

**What tier 2 does and does not police.** Its mandate is deliberately narrow:
*does the sentence introduce a specific, checkable fact that no cited claim
states?* Invented numbers, invented business properties (profitability, growth,
retention, headcount), and citations pointing at a claim about a different
subject are all caught. Interpretation is not — however far it reaches — because
a memo exists to interpret, and a judge that treats analysis as fabrication makes
memo-writing impossible.

That last point is measured, not assumed. A first version of the judge asked for
strict entailment and **all four** test claim sets failed to converge: it rejected
sentences like *"Rasa provides an open-source framework `<<1>>`, giving
engineering teams a flexible foundation"*, whose factual core is verbatim the
claim. Narrowing the mandate to fabricated specifics took convergence from 0/4 to
4/4, while still catching *"Instabug is profitable and retains 95% of its
customers `<<1>>`"* and a market-size sentence citing a product claim.

**Still not covered:** whether a memo's *overall* argument is fair, whether
interpretation is sound, and whether the claims themselves were correctly
extracted from their sources. Those stay with the human read-through in I-05.

**E-02 — feedback.** On reject, `format_feedback()` quotes every blocking
sentence verbatim with its section and the specific reason, tells the model the
valid marker range so it can't "fix" the problem by inventing `<<9>>`, and
states explicitly that deleting a sentence — or replacing it with a "not found"
statement — is always the correct fix when no claim covers it. The feedback is
appended to the *end* of the write_memo prompt, where it outranks the general
guidance above it. Claims never change between passes; only the instructions do.

**E-03 — the cap.** `EVALUATOR_CAP = 2`. Evaluate runs at most twice, which
allows at most one rewrite. If the second pass still finds blocking violations,
the decision is `accept_capped`: the memo ships, but with a warning banner
prepended naming the count of still-untraced sentences, and the full feedback
retained in `evaluator_feedback`. Silently emitting a memo that failed its own
traceability check would be the worst thing this pipeline could do.

The M-05 four-page cap (`enforce_page_cap`) runs inside this node, and only on
an accept — truncating earlier would risk cutting a sentence the evaluator was
about to check.

**Verification.**

Offline, no model calls, no keys needed:

- `tests/unit/test_evaluate.py` — tier 1 logic, the node's three decisions, cap
- `tests/unit/test_evaluate_support.py` — tier 2 plumbing and its failure
  handling, with the judge faked
- `tests/unit/test_memo_pipeline_graph.py` — the real evaluator and real renderer
  running inside `build_graph()`, via
  `build_graph(use_stubs=True, stub_evaluator=False)`. Before this existed every
  graph test stubbed the evaluator, so the real node had never once executed
  inside the real graph and a rendering-order bug could not have been caught.

Live (`pytest tests/manual/test_evaluate_live.py -v -s -o addopts=""` —
pyproject's `addopts` ignores `tests/manual`, so the override is required):

- a genuine draft converges inside the 2-pass budget
- E-02 feedback actually makes the model fix a named sentence
- tier 2 catches a marker sprayed onto an unsupported sentence, and leaves a
  legitimate paraphrase alone
- **tier 2 detection rate**, measured against 17 labelled probes that all pass
  tier 1 by construction (so the measurement isolates tier 2's own judgement):
  10 fabrications ranging from a blatant customer count to an invented funding
  round, against 7 legitimate sentences from plain paraphrase up to
  far-reaching interpretation. Last measured **10/10 fabrications caught, 0/7
  false alarms, stable across three consecutive runs**. Thresholds in the test
  are ≥8 caught and ≤1 false alarm — a layer catching half of these would not
  be worth a model call, and one crying wolf more than about once in seven
  would burn rework cycles every run
- **four unrelated claim sets** — observability, fintech, devtool, and a
  deliberately thin-information one — all converge. This is the guard against
  heuristics tuned to a single company, which is exactly what the gap-statement
  and meta-sentence rules were at first. Last measured: 8/8 clean on draft 1
  across two consecutive runs.

Five of this evaluator's rules exist because a live test caught the first version
getting them wrong. The offline tests are where each of those regressions is
pinned.

### Coverage checker

`backend/nodes/supervisor/coverage_checker.py`. Pure Python, no LLM. Takes the claims list and required categories, returns sorted `covered_categories` and `missing_categories`. Runs after every specialist to update state.

### State object

Defined in `backend/state.py`. Key fields:

- `company_name`, `company_url` — inputs
- `screening_decision`, `screening_reason`, `matched_criteria` — screen output
- `human_approved`, `human_notes` — HITL response
- `claims` — list of `Claim` dicts (dumped for SQLite serialization)
- `specialists_run`, `specialist_outputs` — what has run and what they returned
- `not_found` — categories a specialist looked for and could not find
- `covered_categories`, `missing_categories` — coverage checker output
- `iteration_count`, `decision_log` — supervisor bookkeeping
- `memo_bull`, `memo_base`, `memo_bear` — raw draft sections, `<<N>>` markers intact
- `memo_rendered` — the memo with `[k]` footnotes and a Sources section
- `evaluator_iterations`, `evaluator_decision` — evaluator bookkeeping. The
  decision is deliberately *not* `next_action`: that field belongs to the
  supervisor, and sharing it would corrupt the decision log
- `evaluator_feedback`, `evaluator_violations` — why a draft was rejected, kept
  on state so a rejected memo stays inspectable in the checkpoint afterwards

---

## Cost profile (I-06)

The screening gate is the whole point of the architecture: cheaply reject the ~90% of companies that don't fit the thesis, so the expensive specialist research only runs on the ~10% that do.

Measured from `logs/costs.log` on Aug 5:

| Path | Nodes that run | Cost per company |
|---|---|---|
| Reject | screening only | **~$0.00035** |
| Full pass | screening + 3 specialists | **~$0.01005** |

**A full pass costs ~28x a reject.** Equivalently, a reject saves ~97% of a full run's cost.

At the thesis's target 90% reject rate, screening 100 companies costs:

- **Without the gate:** 100 × $0.01005 = **$1.00**
- **With the gate:** (90 × $0.00035) + (10 × $0.01005) = **$0.13**
- **~87% saved** across a realistic funnel.

Detailed per-node breakdown in `docs/I06_cost_analysis.md`.

---

## Technology Stack

### Frontend

- Streamlit (planned)

### Backend

- Python
- LangGraph state graph

FastAPI was considered but not implemented — the graph is invoked directly by the CLI and (planned) by Streamlit in-process, so an HTTP layer would sit between them without a job. If the system is later deployed as a service for other teams to call, FastAPI is the natural fit in front of `build_graph()`.

### Agent Framework

- LangGraph

### LLM Layer

- LangChain
- OpenAI
- OpenRouter (screening)
- Google Gemini (specialists)

### Research & Data Collection

- Tavily
- Firecrawl

### Data Validation

- Pydantic

### Persistence

- SQLite

### Testing

- Pytest
- LangSmith Evaluation Testing

### Observability & Monitoring

- LangSmith

### Configuration

- python-dotenv

---

## Key Features

- Multi-agent architecture
- Supervisor-driven orchestration
- Structured outputs
- Citation-backed claims
- Human-in-the-loop approval
- Coverage tracking
- Iteration limits
- Prompt injection resilience
- Checkpointing and resume support
- Decision logging
- Cost tracking
- Evaluation and validation layer

---

## Repository Structure

```text
AI-VC-agentic-advisor-2026/
│
├── backend/
│   ├── models/          # Claim schema, categories, screening result
│   ├── nodes/           # Graph nodes (screening, HITL, supervisor, specialists)
│   ├── persistence/     # SqliteSaver checkpointer
│   ├── services/        # Shared utilities (fetch_service)
│   ├── utils/           # Cost logging, token estimation
│   ├── graph.py         # Graph builder + entry point
│   └── state.py         # Shared State TypedDict
│
├── frontend/            # Streamlit UI (planned)
├── project3_inputs/     # Thesis, company list, worked examples (do not modify)
├── tests/               # Unit, integration, manual
├── docs/                # HITL design, schema decisions, cost analysis
├── logs/                # Cost log
├── checkpoints/         # SQLite HITL checkpoint database
└── scripts/             # Batch runners
```

---

## Contributors

- Sara Ahmed
- Abdullah
- Nour
- Seif

---

## Development Timeline

Project Duration:

**13 Working Days**

### Milestones

| Day | Milestone |
|-----|------------|
| 5 | Thin Slice |
| 9 | Walking Skeleton |
| 13 | Final Review & Demo |

---

## Future Enhancements

Potential future improvements include:

- Parallel specialist execution (LangGraph `Send`)
- Expanded evaluation datasets
- Advanced memo scoring
- Additional specialist agents
- Portfolio monitoring workflows
- Enhanced analytics dashboards

---

## Getting Started

### Clone the Repository

```bash
git clone https://github.com/itworx/AI-VC-agentic-advisor-2026.git
cd AI-VC-agentic-advisor-2026
```

### Create a Virtual Environment

```bash
python -m venv .venv
```

### Activate the Virtual Environment

Windows:

```bash
.venv\Scripts\activate
```

Linux / macOS:

```bash
source .venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment Variables

Copy `.env.example` to `.env` and add your API keys:

- `OPENROUTER_API_KEY` — screening, memo writer, evaluator support check
- `GOOGLE_API_KEY` — only needed to *run* the specialists, but currently
  required to **import `backend.graph` at all**: `market_intel` and
  `team_signals` construct their Gemini client at module level, so the import
  fails without some value present. `tests/conftest.py` installs placeholders so
  the offline test suite needs no real keys. Note this is the only part of the
  pipeline not on OpenRouter — screening, the memo writer and the evaluator's
  support check all go through it. Porting those two specialists would drop this
  key from the project (open question for roles B/C).
- `TAVILY_API_KEY` — used by specialists for web search

### Run the Graph

Interactive mode (prompts for human approval at the HITL pause):

​```bash
python -m backend.graph
​```

Batch mode over all 8 companies from `project3_inputs/companies.json`
(auto-approves at HITL, writes a report to `docs/eight_company_run.md`):

​```bash
python -m scripts.run_all_companies
​```

### Inspect the Graph in LangGraph Studio

For an interactive visual demo of the graph, HITL pause, and per-node state:

​```bash
langgraph dev
​```

### Run the Frontend (planned)

A Streamlit UI 

​```bash
streamlit run frontend/app.py
​```

---

## License

This project is developed for educational and internship purposes as part of the ITWorx AI Engineering Internship Program.