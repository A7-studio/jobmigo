# Build Plan

Features in rough build order, one line each. Details come later in `/feature`.
The first ten features form the first vertical slice: account -> CV -> profile
-> preferences -> jobs -> evaluation -> shortlist -> Telegram alert. Everything
after it is post-slice and ordered by commercial value.

Scaffolding the app (TanStack Start web, FastAPI api, Postgres, Docker) and applying
`prototypes/theme.css` are pre-build steps, not features.

## Slice 1: usable by the founder

- [ ] 1. Foundation and app shell - sign-up and sign-in through Clerk behind an auth interface, per-user data scoping, staff roles skeleton and audit log, app shell with sidebar and theme, health check
- [ ] 2. AI gateway and usage ledger - one provider interface, task-based model routing, prompt versions, schema-validated outputs, cost and cache logging
- [ ] 3. CV upload and parsing - PDF/DOCX to private storage, text extraction, AI parse into a structured profile draft
- [ ] 4. Profile review and track variants - edit extracted experience, skills and achievements, confirm facts, create variants for the three tracks
- [ ] 5. Job preferences and track criteria - roles, salary floor, location, eligibility, must-have vs nice-to-have per track, dealbreakers and a do-not-apply list
- [ ] 6. Job source ingestion - adapters for public company career pages and supported job APIs, normalise, deduplicate, verify live and detect expiry, adapter contract with per-host limits, URL-normalised dedupe key, dismissed-job memory with recheck window, posting-legitimacy flag
- [ ] 7. Jobs list - search, filters by track, location and source, saved and dismissed jobs
- [ ] 8. AI job evaluation - dealbreaker gates before any AI call, cheap screening, then evidence-based fit band that reads importance from the posting first (inferred importance capped), per-requirement evidence, gaps, salary and eligibility checks, research budget per evaluation, cached results
- [ ] 9. Dashboard - relevant job count, top opportunities, needs-action list, search progress, empty and loading states
- [ ] 10. Scheduled discovery and Telegram alerts - daily discovery run, daily digest, strong-fit alerts, in-app notifications

## Slice 2: apply and track

- [ ] 11. Application kit - tailored CV, cover letter and application-question drafts from confirmed facts only, fact check, versions, PDF/DOCX export
- [ ] 12. Application CRM - canonical stage list with terminal flags, dates, notes, interview stages, board view, free on every plan
- [ ] 13. Follow-ups and ghost watch - due follow-ups on the dashboard and in Telegram, flag applications silent for 10+ days and draft a nudge
- [ ] 21. Reachability check - AI checklist of how a tailored CV reads to hiring systems (plain-text readability, headings, title match, posting keyword coverage with truthful additions only, file type), plus a hiring-team route and apply-early prompt
- [ ] 20. Progress and quests - daily quests, streaks, levels and badges that reward careful applications and follow-ups, never volume; weekly recap, streak freeze, Migo mascot moments

## Slice 3: contact and grow

- [ ] 14. Company and recruiter research - public hiring-team information and company summaries
- [ ] 15. Outreach drafts and log - personalised messages, outreach tracking
- [ ] 16. Subscription billing and entitlements - plans, regional price book (KES via Paystack with M-Pesa and cards, USD via a merchant of record), credit allowances, checkout and upgrade flow, M-Pesa prepaid renewal prompts, dunning, invoices, contextual upgrade prompts, pause instead of cancel
- [ ] 17. Data export and account deletion - full export and verified delete
- [ ] 18. Application analytics - response rate, time to reply, outcomes by track
- [ ] 23. Localisation - i18n catalogs (English, then Swahili), locale and time zone settings, regional currency and number formatting, region-aware payment methods and tax display
- [ ] 24. Email service - Postmark provider, templates per locale, bounce and complaint handling, receipts and reminders, consented marketing email
- [ ] 25. Admin panel - staff roles with MFA, user search and detail, credit adjustments, subscriptions and refunds, price book and regions, job source health, AI cost and kill switches, feature flags, announcements, ops views, audit log
- [ ] 26. Support desk - in-app help form, inbound support email to tickets, admin inbox with replies, internal notes, canned replies, response-time tracking
- [ ] 22. Ask Migo - natural-language questions over the user's own jobs, profile and applications, with cited answers
- [ ] 19. Homepage, sign-up and onboarding flow - public homepage with waitlist, sign-up page, four-step onboarding ending in a first-shortlist moment, demand validation

## Later (not scheduled)

- Interview prep: likely questions, STAR+R story bank from confirmed history, company brief (the user owns the interview; our job is to get them one)
- AI insights: observations on which CV versions and tracks get replies, with sample-size caveats

- Bring-your-own-key option on the existing AI gateway
- Additional job sources and regional boards
- Browser-assisted application filling, only if it can be done within site terms
- Read-only email scan to detect application status changes (no sending from the user's mailbox)
