# Build Plan

Features in rough build order, one line each. Details come later in `/feature`.
The goal changed on 2026-11-11: build a **founder edition** first. It runs on the founder's
own machine for one user, with no billing and no hosting, and must get the founder work:
automatic search for valid jobs, evidence-based evaluation, a CV personalised to each job,
recruiter outreach drafts and application tracking. It covers jobs, freelance gigs and AI
training roles. Selling starts only after it has worked for the founder (slice 2).

The stack is a hybrid: TanStack Start (web, sign-in and server code) with Drizzle on Postgres,
plus a Python FastAPI AI engine in `engine/` that owns everything that calls a model or parses a
file (gateway and ledger, CV storage and extraction, parsing, evaluation, kit, discovery).

Scaffolding the app and applying `prototypes/theme.css` are pre-build steps, not features.

## Slice 0: launch (waitlist live)

- [x] 27. TypeScript full-stack switch - replace the separate Python API with TanStack Start server code: Drizzle schema and migrations carrying over the user, staff, audit log and Better Auth tables, Better Auth sessions used directly by server functions, per-user data scoping helper, staff permissions, audit log recorder, health check, Vitest tests, remove `api/`, update compose, docs and design docs
- [x] 28. Waitlist and launch
  - [x] 28a. Homepage and waitlist - public homepage from the design (waitlist-honest copy), working waitlist (consented email capture, validation, duplicate handling, rate limit, confirmation page), confirmation email through Resend behind a mail interface with unsubscribe, privacy notice, owner-scoping and auth-wiring test fixes carried from review (F-05, F-06)
  - [x] 28b. Production deploy - production build and image, one VPS with Docker Compose and Caddy behind Cloudflare, HTTPS, migrations at start, health check, nightly Postgres backups to object storage with a tested restore
- [x] 32. Animated homepage and design sync - scripted "paste a job" hero demo (sample job, fit score counting up, flags, tailored CV lines, labelled Preview), floating cards and Migo reactions, scroll reveals on the journey and honesty sections, sticky pill nav, reduced-motion support, no new animation library, no outcome claims; then sync the design canvas with what is built (pill buttons, new homepage, honest-copy fixes on Home, Signup, Onboarding and Dashboard boards, onboarding step 4 as first evaluation), published only with explicit approval

## Foundation: account, CV, profile and add a job (done)

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
- [x] 5. Job preferences and track criteria - roles, salary floor, location, eligibility, must-have vs nice-to-have per track, dealbreakers and a do-not-apply list
- [x] 29. Add a job by link or paste - paste a job link or the posting text; fetch the public page text when the site allows it and fall back to paste, normalise, dedupe by URL, light legitimacy flag, saved and dismissed jobs; free on every plan
  - [x] 29a. Job table and paste (engine) - `Job` table, paste posting text, clean it (hidden text and instruction-shaped lines removed, counts stored not excerpts), normalise, dedupe by URL and by company and title, light legitimacy flag, saved and dismissed state, routes in the engine and web
  - [x] 29b. Safe link fetch (engine) - fetch a public posting page only when robots.txt allows it, with an SSRF guard, size and time limits and a paste fallback; port the robots and posting-guard rules from ai-job-search with the MIT notice
  - [x] 29c. Add a job screen - the add-by-link-or-paste screen and the saved jobs list from the Jobs and Job boards, with loading, empty, blocked-by-site and error states

## Slice 1: founder edition (local, one user, no billing)

- [x] 33. Simpler app structure and design sync
  - [x] 33a. Design boards for the simpler structure - canvas boards for Today, the Jobs list with stage views, the job workspace (steps Fit, CV and letter, Outreach and Track), Settings and the four-place sidebar (Today, Jobs, Profile, Settings); the old Documents, Outreach and Applications pages and the Dashboard widgets (quests, levels, Ask Migo, credits meter, upgrade prompts) are marked as hidden in the founder edition; honest copy; saved under `blueprint/reference/`; published to the canvas only with explicit approval, merged onto the newest canvas version; no app code
  - [x] 33b. App shell and navigation - sidebar of Today, Jobs, Profile and Settings with the greyed-out items removed; `/dashboard` becomes `/today` with the old address redirecting and the sign-in redirects updated; a basic `/settings` page (account details, sign-out); an empty `/jobs/$jobId` workspace shell with the four steps for features 8, 11, 12 and 15 to fill; route and redirect tests; built to match the approved 33a boards
- [ ] 8. AI job evaluation - dealbreaker gates before any AI call (including "hires from my country"), cheap screening, then an evidence-based fit band where importance is the model's own guess, capped at important (the posting's wording is not read as importance; the golden set tunes the band), per-requirement evidence, gaps, salary and eligibility checks, research budget per evaluation, cached results; shown as the Fit step of the job workspace with the verdict first and the evidence one click away; a golden set of real jobs with the founder's own verdicts is run before any model or prompt change ships. Bands shown: Strong, Good, Stretch and Weak fit (stored as `poor`)
  - [x] 8a. Dealbreaker gates and cheap screen (engine) - code-only gates from the track's preferences before any model call (do-not-apply list, work mode, and region-only phrases checked against the track's eligibility and locations, including "hires from my country"); free-text dealbreakers are read by the cheap screen, which must quote the posting, each removal kept with its reason; a cheap-tier screen of what passes, stored as the screen result; the table that ties a saved job to a track and its state; routes in the engine and web; no screen
  - [x] 8b. Evidence-based evaluation (engine) - requirement extraction where importance is the model's guess, capped at important, per-requirement evidence cited only from confirmed or edited profile facts or an explicit unknown, the main gap, a salary check once the founder says whether the floor is monthly or annual, eligibility checks, band Strong, Good, Stretch or Weak fit, a research budget per evaluation, results cached by content hash, the Evaluation table, routes in the engine and web
  - [x] 8c. Fit step in the job workspace - the Fit tab of `/jobs/$jobId` from the approved board: the band and the main gap first, requirement-by-requirement evidence one click away, practical checks, and the not started, working, ready, failed with retry and empty states
  - [ ] 8d. Golden set and `uv run eval` - about 10 real jobs with the founder's own verdicts (the founder supplies them), a Python command that prints a per-job report against those verdicts and cost, and the rule that a model or prompt change ships only after it runs; the set grows to 30 to 50 as the founder applies
- [x] 35. AI cost and quality page - one read-only page for staff: cost, tokens and calls per workflow, cost per evaluation split by screening and full call, cache savings, model and prompt version per result, failed and invalid outputs, the golden-set match rate beside the cost of that run, and an estimate of the same usage on a paid model
- [x] 34. Opportunity types - a saved job is a job, a freelance gig or an AI training role; the type picks the track defaults and whether the kit writes a cover letter or a proposal
- [ ] 11. Application kit - tailored CV, cover letter or proposal, and application-question drafts from confirmed facts only, fact check, versions, PDF/DOCX export; shown as the CV and letter step of the job workspace
  - [ ] 11a. Kit writing and fact check (engine) - for one saved job and a track of its type, the strong model selects and rewords the person's confirmed or edited profile facts into a tailored CV and a cover letter (job) or a proposal (gig or AI training role), plus drafts for the application questions the person pastes in; code then checks that every statement and every number traces to a confirmed fact and flags anything that does not, never silently keeping it; each result is a saved version (the earlier ones stay), cached by content hash, with routes in the engine and web and no model text in logs
  - [ ] 11b. CV and letter step in the job workspace - the CV and letter tab of `/jobs/$jobId` from the approved board: the documents, the fact-check result with each flagged statement one click from fixing or removing it, versions, and the not started, working, ready, failed with retry and empty states
  - [ ] 11c. PDF and DOCX export - plain, ATS-friendly PDF and DOCX files built in the engine with Python libraries from a saved version, refused while a statement is still flagged until the person removes it or confirms the fact; stored in private file storage; a download from the CV and letter step
- [ ] 12. Application tracking - a stage on each job (saved, preparing, applied, interviewing, offer, closed) with terminal flags, dates, notes, interview stages, a follow-up date and an outcome (no response, rejected, interview, offer); the Jobs list shows stages as views, the app shows interviews per application by track; "Open the posting and apply" then "Did you apply?" marks it applied; the board view comes later
- [ ] 36. One-step prepare - "Prepare application" runs the evaluation, the kit and the fact check in the background (and the contacts and outreach draft once 14 and 15 exist) and returns one review page with one approval; nothing is ever sent or submitted for the user
- [ ] 6. Job source ingestion - adapters behind one contract: public company board feeds (Greenhouse, Lever, Ashby, Workable), one or two free remote-job feeds and JSearch on RapidAPI; normalise, deduplicate, verify live and detect expiry, per-host limits and a monthly call budget, URL-normalised dedupe key, dismissed-job memory with recheck window, posting-legitimacy flag; no LinkedIn or Indeed scraping
- [ ] 10. Scheduled discovery - a daily run per track that fetches new jobs, applies the dealbreaker gates without AI, evaluates the best matches within a daily budget and puts them in Today; jobs dropped by a gate stay visible in a "Filtered out" list with the reason
- [ ] 7. Jobs list - search and filters by track, stage, fit, location and source, saved and dismissed jobs, keep or skip on each new match
- [ ] 9. Today - the home page as one queue of next actions in order: new matches to keep or skip, applications ready to review, follow-ups due and interviews coming up, each with one main button; empty and loading states; no widgets or charts
- [ ] 14. Company and recruiter research - public hiring-team information and company summaries with a source link on every entry, confirmed by the user before drafting; no email guessing
- [ ] 15. Outreach drafts and log - personalised referral and follow-up messages the user copies and sends, outreach tracking; shown as the Outreach step of the job workspace
- [ ] 13. Follow-ups and ghost watch - due follow-ups in Today, flag applications silent for 10+ days and draft a nudge
- [ ] 37. Interview prep - likely questions, a story bank from confirmed history and a company brief, opened from an application in the interviewing stage (the user owns the interview; our job is to get them one)
- [ ] 21. Reachability check - AI checklist of how a tailored CV reads to hiring systems (plain-text readability, headings, title match, posting keyword coverage with truthful additions only, file type), plus a hiring-team route and apply-early prompt
- [ ] 38. Showcase pack - README with the architecture and key decisions, the golden-set results table, cost per evaluation, a safety demo (hidden instructions removed from a posting) and a script for a short demo video; no personal data

## Slice 2: validate and sell (after four weeks of the founder's own use)

- [ ] 19. Sign-up and onboarding flow - sign-up page, four-step onboarding ending in a first-evaluation moment (paste a job and see an evidence-based evaluation), demand validation (the public homepage and waitlist ship in feature 28)
- [ ] 17. Data export and account deletion - full export and verified delete
- [ ] 40. First payments by hand - one paid plan sold through a payment link, with a paid flag set by staff, for the first 10 customers; packaging and price decided from the founder's results
- [ ] 16. Subscription billing and entitlements - plans, regional price book (KES via Paystack with M-Pesa and cards, USD via a merchant of record), credit allowances, checkout and upgrade flow, M-Pesa prepaid renewal prompts, dunning, invoices, contextual upgrade prompts, pause instead of cancel
- [ ] 39. Telegram digest and alerts - daily digest, strong-fit alerts and follow-up reminders in Telegram, plus in-app notifications
- [ ] 24. Email service - full email layer beyond the waitlist confirmation (Resend first, Postmark later if needed), templates per locale, bounce and complaint handling, receipts and reminders, consented marketing email

## Slice 3: grow and operate

- [ ] 20. Progress and quests - daily quests, streaks, levels and badges that reward careful applications and follow-ups, never volume; weekly recap, streak freeze, Migo mascot moments
- [ ] 18. Application analytics - response rate, time to reply, outcomes by track
- [ ] 22. Ask Migo - natural-language questions over the user's own jobs, profile and applications, with cited answers
- [ ] 23. Localisation - i18n catalogs (English, then Swahili), locale and time zone settings, regional currency and number formatting, region-aware payment methods and tax display
- [ ] 25. Admin panel - staff roles with MFA, user search and detail, credit adjustments, subscriptions and refunds, price book and regions, job source health, AI cost and kill switches, feature flags, announcements, ops views, audit log
- [ ] 26. Support desk - in-app help form, inbound support email to tickets, admin inbox with replies, internal notes, canned replies, response-time tracking

## Later (not scheduled)

- AI insights: observations on which CV versions and tracks get replies, with sample-size caveats
- Board view for applications
- Hunter.io for contact emails in outreach, with consent and data-protection rules checked first
- Bring-your-own-key option on the existing AI gateway
- Additional job sources and regional boards
- Browser-assisted application filling, only if it can be done within site terms
- Read-only email scan to detect application status changes (no sending from the user's mailbox)
- Upwork MCP source and proposal drafting for freelancers, only if beta access opens and its terms allow it (the user reviews and submits every proposal)
- Python job-source adapters (including Scrapling) in the engine, only if scraping is ever approved within site terms
