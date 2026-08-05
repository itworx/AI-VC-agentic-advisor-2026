# Eight-Company Batch Run

Generated: 2026-08-05T08:16:56+00:00
Total companies: 8

## Summary

| Company | Expected | Actual | Match | Claims |
|---|---|---|---|---|
| Paymob | pass | pass | yes | 12 |
| Instabug | pass | pass | yes | 13 |
| Supabase | pass | reject | NO | - |
| dbt Labs | reject | reject | yes | - |
| Hugging Face | reject | reject | yes | - |
| Vezeeta | ambiguous | reject | NO | - |
| Swvl | reject | reject | yes | - |
| Figma | reject | reject | yes | - |

---

## Paymob

- Expected: `pass` (pass - B2B fintech infrastructure, MENA) | Actual: `pass` [yes]
- Reason: Paymob is a B2B fintech infrastructure company operating in MENA (Egypt-based) with multiple payment solutions (online payments, POS, payouts, APIs) that serve businesses. The homepage indicates paying customers across various merchant segments, meeting the traction requirement.
- Matched criteria: ['business-to-business software', 'Fintech infrastructure', 'MENA', 'must have paying customers']
- Runtime: 116.8s
- Specialists ran: ['company_intel', 'market_intel', 'team_signals']
- Claims collected: 12
- Covered categories: ['competitors', 'funding_stage', 'market_size', 'target_customer', 'what_company_does']
- Missing categories: ['team_size']
- Not found: ['business_model']

**Decision log (4 entries):**
- iter 1: chose `company_intel` -- company_intel covers 2 missing categories: ['target_customer', 'what_company_does']
- iter 2: chose `market_intel` -- market_intel covers 2 missing categories: ['competitors', 'market_size']
- iter 3: chose `team_signals` -- team_signals covers 2 missing categories: ['funding_stage', 'team_size']
- iter 4: chose `write_memo` -- all useful specialists exhausted, 1 still missing

## Instabug

- Expected: `pass` (pass - developer tools, B2B, MENA) | Actual: `pass` [yes]
- Reason: Instabug (Luciq) is a B2B software platform for mobile engineering teams that provides observability and AI-assisted debugging tools. The company clearly operates in the developer tools sector with enterprise customers, matching the thesis focus on business-to-business software and developer tools.
- Matched criteria: ['business-to-business software', 'developer tools']
- Runtime: 94.9s
- Specialists ran: ['company_intel', 'market_intel', 'team_signals']
- Claims collected: 13
- Covered categories: ['competitors', 'funding_stage', 'market_size', 'target_customer', 'team_size', 'what_company_does']
- Missing categories: []
- Not found: ['business_model']

**Decision log (4 entries):**
- iter 1: chose `company_intel` -- company_intel covers 2 missing categories: ['target_customer', 'what_company_does']
- iter 2: chose `market_intel` -- market_intel covers 2 missing categories: ['competitors', 'market_size']
- iter 3: chose `team_signals` -- team_signals covers 2 missing categories: ['funding_stage', 'team_size']
- iter 4: chose `write_memo` -- coverage complete

## Supabase

- Expected: `pass` (pass on sector, likely reject on stage - verify) | Actual: `reject` [NO]
- Reason: Supabase is a developer tools platform for building applications, but the company information does not indicate paying customers or revenue traction, which is a hard requirement in the thesis. Without evidence of customer acquisition and revenue, this fails the traction floor criterion.
- Matched criteria: ['must have paying customers. Revenue may be small, but not zero']
- Runtime: 4.5s

## dbt Labs

- Expected: `reject` (reject - past Series B) | Actual: `reject` [yes]
- Reason: dbt Labs is a data infrastructure and analytics tool, which aligns with the sector focus. However, the company information provided does not indicate paying customer traction, revenue, or current stage. The homepage content describes product features and ecosystem integrations but contains no evidence of revenue or paying customers, which is a hard requirement in the thesis.
- Matched criteria: ['must have paying customers. Revenue may be small, but not zero', 'business-to-business software. Fintech infrastructure, developer tools, vertical SaaS, logistics software, data infrastructure']
- Runtime: 4.6s

## Hugging Face

- Expected: `reject` (reject - stage) | Actual: `reject` [yes]
- Reason: Hugging Face is a developer platform and open-source community hub for machine learning models and datasets, not a B2B software company in Nile Ventures' target sectors (fintech infrastructure, vertical SaaS, logistics software, data infrastructure). The company operates primarily as a free/freemium open-source platform rather than a traditional SaaS business with paying enterprise customers as the core revenue model.
- Matched criteria: ['business-to-business software. Fintech infrastructure, developer tools, vertical SaaS, logistics software, data infrastructure']
- Runtime: 3.4s

## Vezeeta

- Expected: `ambiguous` (ambiguous - the interesting case. Either answer is acceptable if the reason is sound) | Actual: `reject` [ambiguous]
- Reason: Vezeeta is a consumer-facing healthcare marketplace for booking doctor appointments and purchasing medicines. This falls under consumer services, which is explicitly excluded by the thesis that states 'We do not invest in Consumer social, gaming, or entertainment.' While it operates in the MENA region, the business model is B2C rather than B2B software.
- Matched criteria: ['Consumer social, gaming, or entertainment']
- Runtime: 3.6s

## Swvl

- Expected: `reject` (reject - consumer, and past stage) | Actual: `reject` [yes]
- Reason: Swvl is a consumer-facing mobility and transportation platform focused on ride-booking and fleet operations for individual commuters and passengers. This falls under consumer transportation services, which is outside Nile Ventures' B2B software focus. The company does not fit the thesis sectors of fintech infrastructure, developer tools, vertical SaaS, logistics software, or data infrastructure.
- Matched criteria: ['business-to-business software', 'Consumer social, gaming, or entertainment']
- Runtime: 6.3s

## Figma

- Expected: `reject` (reject - stage. Must not pass just because the company is good) | Actual: `reject` [yes]
- Reason: Figma is a design and collaboration tool primarily serving creative and design teams, not a business-to-business software company in the sectors we target (fintech infrastructure, developer tools, vertical SaaS, logistics software, data infrastructure). While it has B2B elements, it does not fit our core sector focus.
- Matched criteria: ['business-to-business software. Fintech infrastructure, developer tools, vertical SaaS, logistics software, data infrastructure']
- Runtime: 3.4s


---

## I-04 — Mismatch analysis

Two mismatches: Supabase (agent substantively wrong — missed paying-customer evidence in the fetched content) and Vezeeta (agent defensible — the case is deliberately ambiguous and the reasoning is sound).

### Supabase — expected `pass`, actual `reject`

**Expected reason (from companies.json):** "pass on sector, likely reject on stage - verify"

**Agent's reject reason:** cited the traction floor — no evidence of paying customers or revenue on the homepage.

**Ground-truth check:** fetched the first 4000 chars of https://supabase.com directly. The content **does** contain paying-customer evidence: a named customer testimonial ("Caleb Peffer, CEO, Firecrawl") for a real B2B company that switched from Pinecone to Supabase, a "How industry leaders are building with Supabase" section, "Trusted by fast-growing companies worldwide", and a Stripe Subscriptions Starter template.

**Verdict:** the agent's reject reason is **substantively incorrect**. Sector (data infrastructure, developer tools) is a clear pass and the fetched content contains explicit paying-customer evidence. The screening prompt appears to weight overt pricing pages more than customer testimonials as traction evidence, missing the signal that was present. **Agent wrong, not expectation stale.** Worth flagging to the screening node owner: the prompt should treat named enterprise customer testimonials as traction evidence.

### Vezeeta — expected `ambiguous`, actual `reject`

**Expected reason (from companies.json):** "ambiguous - the interesting case. Either answer is acceptable if the reason is sound"

**Agent's reject reason:** cited the consumer-services exclusion, noted Vezeeta's B2C patient-facing model, acknowledged MENA fit, concluded exclusion outweighs geographic fit.

**Ground-truth check:** fetched both `vezeeta.com` (served Arabic) and `vezeeta.com/en` (served English). Both versions lead with patient-facing services: doctor search, appointment booking, medicine delivery, home visits, telehealth calls. No B2B/PMS software surface on the landing page in either language. The agent's characterisation of Vezeeta as B2C-first is directly supported by the fetched content.

**Verdict:** the agent's reasoning meets the acceptance bar for this case — cites the thesis directly, identifies the right business-model tension, defensible on the fetched evidence. **Neither side is wrong, mismatch is expected by design.**

**Side note on cross-language robustness:** the agent judged Vezeeta from the Arabic homepage (the default served) and reached a substantively correct conclusion. This is one data point in favour of cross-language screening but not proof — worth flagging as future work if the fund thesis expands to Arabic-first markets.

### Six matches — no action needed

Paymob, Instabug, dbt Labs, Hugging Face, Swvl, and Figma all matched their expected screening decisions. Reject reasons for the strong-companies-outside-thesis cases (Figma, Hugging Face) correctly cited sector fit rather than company quality, which was the whole point of including them.

### Note on reject reasoning quality

Two reject reasons (Supabase, dbt Labs) blamed the "paying customers" traction floor when sector fit or stage would have been the stronger available ground. The final decisions matched expectations for dbt Labs but not Supabase. In both cases the emphasis in the reasoning is weak. Worth flagging to the screening node owner for prompt tuning.