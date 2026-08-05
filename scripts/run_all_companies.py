"""Run all companies from project3_inputs/companies.json through the graph.
Writes a markdown report to docs/eight_company_run.md.
"""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from langgraph.types import Command
from backend.graph import graph
from backend.state import create_initial_state

INPUT_PATH = Path("project3_inputs/companies.json")
OUTPUT_PATH = Path("docs/eight_company_run.md")

AUTO_APPROVE = {
    "approved": True,
    "override_decision": None,
    "override_reason": None,
    "notes": None,
}

def expected_verdict(company: dict) -> str:
    """Extract 'pass' / 'reject' / 'ambiguous' from the prose expected_screening string."""
    raw = company.get("expected_screening", "").lower()
    if raw.startswith("pass"):
        return "pass"
    if raw.startswith("reject"):
        return "reject"
    if raw.startswith("ambiguous"):
        return "ambiguous"
    return "?"

def run_one(company: dict) -> dict:
    slug = company["name"].lower().replace(" ", "-")
    thread_id = f"batch-{slug}-{datetime.now().strftime('%H%M%S')}"
    config = {"configurable": {"thread_id": thread_id}}

    # Adjust field names here if your companies.json uses different keys
    url = company["website"]

    initial = create_initial_state(company_name=company["name"], company_url=url)

    started = time.time()
    result = graph.invoke(initial, config)

    if graph.get_state(config).next:
        result = graph.invoke(Command(resume=AUTO_APPROVE), config)

    return {"result": result, "elapsed_s": round(time.time() - started, 1)}


def format_section(company: dict, run: dict) -> str:
    r = run["result"]
    expected = expected_verdict(company)
    expected_full = company.get("expected_screening", "?")
    actual = r["screening_decision"]
    match = "yes" if expected == actual else ("ambiguous" if expected == "ambiguous" else "NO")

    lines = [
        f"## {company['name']}",
        "",
        f"- Expected: `{expected}` ({expected_full}) | Actual: `{actual}` [{match}]",
        f"- Reason: {r['screening_reason']}",
        f"- Matched criteria: {r.get('matched_criteria', [])}",
        f"- Runtime: {run['elapsed_s']}s",
    ]

    if actual == "pass":
        lines.extend([
            f"- Specialists ran: {r['specialists_run']}",
            f"- Claims collected: {len(r['claims'])}",
            f"- Covered categories: {r['covered_categories']}",
            f"- Missing categories: {r['missing_categories']}",
            f"- Not found: {r['not_found']}",
            "",
            f"**Decision log ({len(r['decision_log'])} entries):**",
        ])
        for entry in r["decision_log"]:
            lines.append(f"- iter {entry['iteration']}: chose `{entry['chosen']}` -- {entry['reason']}")

    return "\n".join(lines) + "\n"


def main():
    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    companies = data["companies"]
    print(f"Running {len(companies)} companies...\n")

    results = []
    for i, company in enumerate(companies, 1):
        name = company["name"]
        print(f"[{i}/{len(companies)}] {name}...", end=" ", flush=True)
        try:
            run = run_one(company)
            print(f"{run['result']['screening_decision']} ({run['elapsed_s']}s)")
            results.append((company, run, None))
        except Exception as e:
            print(f"ERROR: {e}")
            results.append((company, None, str(e)))

    # Write report
    now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    out = [
        "# Eight-Company Batch Run",
        "",
        f"Generated: {now}",
        f"Total companies: {len(companies)}",
        "",
        "## Summary",
        "",
        "| Company | Expected | Actual | Match | Claims |",
        "|---|---|---|---|---|",
    ]
    for company, run, err in results:
        expected = expected_verdict(company)
        if err:
            out.append(f"| {company['name']} | {expected} | ERROR | - | - |")
        else:
            r = run["result"]
            actual = r["screening_decision"]
            match = "yes" if expected == actual else "NO"
            claims = len(r["claims"]) if actual == "pass" else "-"
            out.append(f"| {company['name']} | {expected} | {actual} | {match} | {claims} |")

    out.append("\n---\n")

    for company, run, err in results:
        if err:
            out.append(f"## {company['name']}\n\nERROR: {err}\n")
        else:
            out.append(format_section(company, run))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(out), encoding="utf-8")
    print(f"\nReport written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()