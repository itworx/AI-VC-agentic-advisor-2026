# Worked input example A - a company that should pass screening

## Input given to the agent

```
company_name: Instabug
website: https://instabug.com
thesis_file: thesis.md
run_date: <today>
```

## What should happen

1. **Screening** runs one cheap model call. Reads the website, checks against the thesis.
   Expected result: **pass**, reason "B2B developer tools, MENA origin, has paying
   customers per public pricing page."

2. **Supervisor** sees an empty claims list. `check_coverage` reports every required
   category missing. It picks `company_intel` first, because identity and product must
   be established before market or team questions make sense.

3. **company_intel** returns claims such as: what the product does, who it is sold to,
   what the public pricing tiers are. Each with a source URL and a snippet.

4. **Supervisor** re-checks coverage. Market and competition still empty. Picks
   `market_intel`.

5. **market_intel** returns market and competitor claims. Some will be `reported`
   rather than `verified`, and any market size figure taken from a vendor report
   should be labelled `inferred` if the agent had to estimate.

6. **team_signals** returns company-level facts only. If it cannot find headcount,
   it returns "not found" - it does **not** estimate from LinkedIn or guess.

7. **Supervisor** sees coverage satisfied, routes to `write_memo`.

8. **write_memo** builds three cases from the claims list. **evaluate** checks every
   sentence traces to a claim, and rejects once if not.

## What to check in the output

- Every sentence in the memo has a source marker
- At least one `not found` appears somewhere - a complete memo with zero gaps on a
  private company is a warning sign, not a success
- No claim about any named individual
- The bull and bear cases differ in their assumptions, not only in tone
- The decision log explains each routing choice
