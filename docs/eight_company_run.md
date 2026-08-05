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
