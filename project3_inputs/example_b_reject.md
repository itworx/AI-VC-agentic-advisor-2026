# Worked input example B - a company that should be rejected at screening

## Input given to the agent

```
company_name: Swvl
website: https://www.swvl.com
thesis_file: thesis.md
run_date: <today>
```

## What should happen

**Screening rejects it.** One model call. Reason: consumer transport, not B2B software,
and past the thesis stage ceiling.

Then the graph **stops**. That is the whole run.

## What to check in the output

This is the cheapest and most important test in the project.

- **Zero specialist calls.** Check LangSmith: the trace should show screening and
  nothing else. If `company_intel` ran, your gate is decorative
- The reject reason **names a specific thesis criterion**. "Not a good fit" is not
  an acceptable output
- Total cost of the run is a fraction of example A. Note both numbers in your README

## Why this matters

A VC firm looks at roughly 2,000 companies to invest in 10. If your agent spends full
research effort on every one, it is unusable at any real volume. **The ability to reject
cheaply is the product.** Build and test this path before you build the memo writer.

## A third case worth adding yourself

Run a company that is a **borderline** fit - Vezeeta in the companies list is the
designed example. There is no single correct answer. What is graded is whether the
reason given is sound and references the thesis, and whether the agent flags its own
uncertainty rather than picking confidently.
