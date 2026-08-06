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

- Claim traceability
- Citation integrity
- Memo quality
- Coverage completeness

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
       └─► [write_memo] ──► END
```
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

- `OPENROUTER_API_KEY` — used by the screening node
- `GOOGLE_API_KEY` — used by specialists (Gemini)
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