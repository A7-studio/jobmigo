# Build Plan

Features in rough build order, one line each. Details come later in `/feature`.
Slice 1 is the paste-a-job loop: account -> CV -> profile -> preferences -> add a job by link
or paste -> evidence-based evaluation -> application kit -> tracking with outcomes. It is
the core of the product and needs no job scraping. Automatic discovery and alerts are the
premium slice (3) and reuse the same evaluator. Everything after is ordered by commercial value.

The stack is a hybrid: TanStack Start (web, sign-in and server code) with Drizzle on Postgres,
plus a Python FastAPI AI engine in `engine/` that owns everything that calls a model or parses a
file (gateway and ledger, CV storage and extraction, parsing, evaluation, kit). Features 27 and 28
(28a, 28b) shipped first so the public waitlist can go live; slice 1 resumes with the engine
(features 30 and 31) before CV upload.

Scaffolding the app and applying `prototypes/theme.css` are pre-build steps, not features.

## Slice 0: launch (waitlist live)

- [x] 27. TypeScript full-stack switch - replace the separate Python API with TanStack Start server code: Drizzle schema and migrations carrying over the user, staff, audit log and Better Auth tables, Better Auth sessions used directly by server functions, per-user data scoping helper, staff permissions, audit log recorder, health check, Vitest tests, remove `api/`, update compose, docs and design docs
- [x] 28. Waitlist and launch
  - [x] 28a. Homepage and waitlist - public homepage from the design (waitlist-honest copy), working waitlist (consented email capture, validation, duplicate handling, rate limit, confirmation page), confirmation email through Resend behind a mail interface with unsubscribe, privacy notice, owner-scoping and auth-wiring test fixes carried from review (F-05, F-06)
  - [x] 28b. Production deploy - production build and image, one VPS with Docker Compose and Caddy behind Cloudflare, HTTPS, migrations at start, health check, nightly Postgres backups to object storage with a tested restore
- [x] 32. Animated homepage and design sync - scripted "paste a job" hero demo (sample job, fit score counting up, flags, tailored CV lines, labelled Preview), floating cards and Migo reactions, scroll reveals on the journey and honesty sections, sticky pill nav, reduced-motion support, no new animation library, no outcome claims; then sync the design canvas with what is built (pill buttons, new homepage, honest-copy fixes on Home, Signup, Onboarding and Dashboard boards, onboarding step 4 as first evaluation), published only with explicit approval

## Slice 1: paste-a-job loop, usable by the founder

- [x] 1. Foundation and app shell - sign-up and sign-in through Better Auth (web server, JWT to the API) behind an auth interface, per-user data scoping, staff roles skeleton and audit log, app shell with sidebar and theme, health check
- [x] 2. AI gateway and usage ledger - one provider interface, task-based model routing, prompt versions, schema-validated outputs, cost and cache logging
- [x] 30. Python AI engine foundation - FastAPI service in `engine/` (uv, Pydantic, Ruff, strict typing, pytest), Dockerfile and compose entry, health and readiness, internal-only bearer auth with the user id from the verified web session, engine-owned Postgres schema with Alembic, TypeScript client in the web server, commands in AGENTS.md
- [x] 31. Port the AI gateway and usage ledger to the engine - providers, tier routing, prompt versions, validated outputs, per-user cache and ledger in Python with parity tests against the TypeScript cases, then remove the TypeScript gateway and its two tables
- [x] 3. CV upload and parsing - in the engine: private storage, text extraction in a resource-limited subprocess, AI parse into a structured profile draft
  - [x] 3a. CV storage, upload and text extraction - S3-compatible storage (RustFS locally), web upload route streaming to the engine, isolated extraction with memory, CPU and time limits and byte-counted decompression, CV record, owner-scoped signed download and delete
  - [x] 3b. AI parse into a profile draft (engine) - background parse through the engine gateway into a structured draft (unconfirmed facts), draft tables, status and retry routes, web API routes
  - [x] 3c. CV upload and parse status screen - the `/onboarding` upload step and parse status from the design canvas: progress, success, failure with retry, plain AI disclosure on the upload step
- [x] 4. Profile review and track variants - edit extracted experience, skills and achievements, confirm facts, create variants for the three tracks
  - [x] 4a. Profile fact edit and confirm routes (engine) - the profile is the latest parsed draft; per-row edit, confirm, add and delete, confirm all, a profile version that changes on every edit, web API routes
  - [x] 4b. Profile review screen - `/profile` from the Profile board: review each fact, edit, confirm, add, delete, confirm all, with the unconfirmed state always visible
  - [x] 4c. Track variants - Track and TrackProfileItem tables, create, rename and delete a track, choose which confirmed facts a track emphasises, and the screen for it
- [ ] 5. Job preferences and track criteria - roles, salary floor, location, eligibility, must-have vs nice-to-have per track, dealbreakers and a do-not-apply list
- [ ] 29. Add a job by link or paste - paste a job link or the posting text; fetch the public page text when the site allows it and fall back to paste, normalise, dedupe by URL, light legitimacy flag, saved and dismissed jobs; free on every plan
- [ ] 8. AI job evaluation - dealbreaker gates before any AI call, cheap screening, then evidence-based fit band that reads importance from the posting first (inferred importance capped), per-requirement evidence, gaps, salary and eligibility checks, research budget per evaluation, cached results; runs on a pasted job first (the same evaluator later runs on discovered jobs); a golden set of 30 to 50 real jobs with the founder's own verdicts is run before any model or prompt change ships; the golden-set runner is a Python command (`uv run eval`) that prints a per-job report against the founder's verdicts
- [ ] 11. Application kit - tailored CV, cover letter and application-question drafts from confirmed facts only, fact check, versions, PDF/DOCX export
- [ ] 12. Application CRM - canonical stage list with terminal flags, dates, notes, interview stages, board view, free on every plan; each application records its outcome (no response, rejected, interview, offer) and the app shows interviews per application by track
- [ ] 9. Dashboard - evaluated jobs, needs-action list, application progress, empty and loading states; discovery widgets arrive with feature 10
- [ ] 19. Sign-up and onboarding flow - sign-up page, four-step onboarding ending in a first-evaluation moment (paste a job and see an evidence-based evaluation; the first shortlist moment arrives with discovery), demand validation (the public homepage and waitlist ship in feature 28)

## Slice 2: apply better and follow through

- [ ] 13. Follow-ups and ghost watch - due follow-ups on the dashboard and in Telegram, flag applications silent for 10+ days and draft a nudge
- [ ] 21. Reachability check - AI checklist of how a tailored CV reads to hiring systems (plain-text readability, headings, title match, posting keyword coverage with truthful additions only, file type), plus a hiring-team route and apply-early prompt
- [ ] 14. Company and recruiter research - public hiring-team information and company summaries
- [ ] 15. Outreach drafts and log - personalised messages, outreach tracking
- [ ] 20. Progress and quests - daily quests, streaks, levels and badges that reward careful applications and follow-ups, never volume; weekly recap, streak freeze, Migo mascot moments

## Slice 3: premium automatic discovery

- [ ] 16. Subscription billing and entitlements - plans, regional price book (KES via Paystack with M-Pesa and cards, USD via a merchant of record), credit allowances, checkout and upgrade flow, M-Pesa prepaid renewal prompts, dunning, invoices, contextual upgrade prompts, pause instead of cancel; free plan is bring-your-own-job with a small evaluation allowance, paid plans add automatic discovery and alerts
- [ ] 6. Job source ingestion (premium) - adapters for public company career pages and supported job APIs, normalise, deduplicate, verify live and detect expiry, adapter contract with per-host limits, URL-normalised dedupe key, dismissed-job memory with recheck window, posting-legitimacy flag
- [ ] 7. Jobs list (premium) - search, filters by track, location and source, saved and dismissed jobs
- [ ] 10. Scheduled discovery and Telegram alerts (premium) - daily discovery run, daily digest, strong-fit alerts, in-app notifications

## Slice 4: grow and operate

- [ ] 17. Data export and account deletion - full export and verified delete
- [ ] 18. Application analytics - response rate, time to reply, outcomes by track
- [ ] 23. Localisation - i18n catalogs (English, then Swahili), locale and time zone settings, regional currency and number formatting, region-aware payment methods and tax display
- [ ] 24. Email service - full email layer beyond the waitlist confirmation (Resend first, Postmark later if needed), templates per locale, bounce and complaint handling, receipts and reminders, consented marketing email
- [ ] 25. Admin panel - staff roles with MFA, user search and detail, credit adjustments, subscriptions and refunds, price book and regions, job source health, AI cost and kill switches, feature flags, announcements, ops views, audit log
- [ ] 26. Support desk - in-app help form, inbound support email to tickets, admin inbox with replies, internal notes, canned replies, response-time tracking
- [ ] 22. Ask Migo - natural-language questions over the user's own jobs, profile and applications, with cited answers

## Later (not scheduled)

- Interview prep: likely questions, STAR+R story bank from confirmed history, company brief (the user owns the interview; our job is to get them one)
- AI insights: observations on which CV versions and tracks get replies, with sample-size caveats

- Bring-your-own-key option on the existing AI gateway
- Additional job sources and regional boards
- Browser-assisted application filling, only if it can be done within site terms
- Read-only email scan to detect application status changes (no sending from the user's mailbox)
- Upwork MCP source and proposal drafting for freelancers, only if beta access opens and its terms allow it (the user reviews and submits every proposal)
- Python job-source adapters (including Scrapling) in the engine, only if scraping is ever approved within site terms
