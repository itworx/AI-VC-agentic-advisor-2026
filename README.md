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

## Technology Stack

### Frontend

- Streamlit

### Backend

- FastAPI

### Agent Framework

- LangGraph

### LLM Layer

- LangChain
- OpenAI

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
├── frontend/
├── data/
├── tests/
├── docs/
└── checkpoints/
```

Detailed module documentation will be added as implementation progresses.

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

- Parallel specialist execution
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

Copy `.env.example` to `.env` and add your API keys.

### Run the Backend

```bash
uvicorn backend.app:app --reload
```

### Run the Frontend

```bash
streamlit run frontend/app.py
```

---

## License

This project is developed for educational and internship purposes as part of the ITWorx AI Engineering Internship Program.