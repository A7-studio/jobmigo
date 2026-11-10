# Jobmigo - Project Overview

<!-- blueprint:source-hash 5c3904903afd720e006132f3c5dac8302bc075b4b2306d71f77503e11d0d6d30 -->

> AI job-application assistant for professionals: gets applications out of the ghost pipeline and into interviews (no outcome promised; winning the interview is up to the user). AI proposes, the user decides; workflow map in `docs/ai-workflows.md`: Discover -> Verify -> Evaluate -> Prepare -> Contact -> Apply -> Track -> Improve. First product of A7Studio.

## Problem

The main bottleneck is the application itself: filtered out by hiring software, buried in the pile, or sent to a job that is already dead. Job searching is also scattered and repetitive. Existing tools cover one slice and "AI apply" tools favour volume. Jobmigo tells the user which few verified jobs deserve time, why, and prepares truthful tailored applications.

Principles for every feature:
- Never fabricate experience; documents reuse only confirmed profile facts, new claims are flagged.
- No fake precision: fit is a band (Strong, Good, Stretch) with per-requirement evidence, never a percentage.
- Legitimate sources only; no scraping behind logins, no ToS-violating automation, no auto-submitting.

## Users

- **Initial ICP (hypothesis):** experienced, remote-seeking technology professionals running a multi-track search, applying to 5+ roles a week, valuing quality over volume.
- **Also served:** career changers, freelancers, remote seekers.
- **First user:** the founder (Flutter/mobile engineer) with three tracks: Flutter and mobile; AI coding evaluation and AI training; AI application engineering and product engineering, each with its own profile variant and criteria.
- **Validation:** the founder edition must get the founder work first: 4 weeks of daily self-use with outcomes recorded in the tracker, then 10-15 interviews, concierge pilot with 5-10 people, $19 founding-member waitlist; goal 10 paying customers.

## Usage model

- Scale: founder first (the founder edition runs locally for one user), then tens of users; no larger scale assumed.
- Internet-facing, multi-user: per-user isolation is a real requirement; users are ordinary job seekers, not assumed adversarial.
- Sensitive data: CVs and contact details; private storage, owner-scoped access, export and deletion, no personal CV data in logs or public content.
- Recruiter data: public information only.
- Not required now: enterprise SSO, compliance certifications, multi-region, team accounts, HA.

## Features

Direction since 2026-11-11: a **founder edition** first. It runs locally for one user, with no billing or hosting, and must get the founder work (jobs, freelance gigs, AI training roles). Selling starts in slice 2. The **headline feature is #8, AI job evaluation**.

_Done: launch and foundation_
- **27, 28a, 28b, 32** - TypeScript full-stack switch; homepage and consented waitlist with a Resend confirmation email; production deploy files (one VPS behind Cloudflare, backups); animated homepage.
- **1** foundation and app shell (Better Auth, per-user scoping, staff roles skeleton, audit log). **2, 30, 31** AI gateway and usage ledger in the Python engine (FastAPI, own Postgres schema with Alembic, bearer auth with the verified user id).
- **3** CV upload, isolated text extraction, AI parse into an unconfirmed draft, `/onboarding` screen. **4** profile review, edit and confirm, tracks and emphasis. **5** job preferences per track (roles, salary floor, work modes, locations, eligibility, criteria, dealbreakers, do-not-apply).
- **29** add a job by link or paste: safe fetch when robots.txt allows, cleaner for hidden and instruction-shaped text, dedupe, legitimacy flag, saved and dismissed, `/jobs` screen.

_Slice 1, founder edition (in build order)_
33. **Simpler app structure and design sync** (33a design boards first, then 33b app shell) - sidebar of Today, Jobs, Profile, Settings; one job workspace with steps Fit, CV and letter, Outreach, Track (replaces the Documents, Outreach and Applications pages); quests, levels, Ask Migo, credits meter and upgrade prompts hidden; canvas boards updated and approved before new screens.
8. **AI job evaluation** - dealbreaker gates before AI calls (including "hires from my country"), cheap screen, evidence-based fit band (importance read from the posting first, inferred importance capped), gaps, salary/eligibility checks, research budget, cached; the Fit step, verdict first; a golden set of the founder's verdicts (starts at 10, grows to 30 to 50) gates model and prompt changes (`uv run eval`).
35. **AI cost and quality page** - read-only, staff: cost, tokens and calls per workflow, cost per evaluation, cache savings, model and prompt versions, failures, golden-set match rate beside cost, paid-model estimate.
34. **Opportunity types** - job, freelance gig or AI training role; picks track defaults and cover letter vs proposal.
11. **Application kit** - tailored CV, cover letter or proposal, answers from confirmed facts, fact check, versions, PDF/DOCX export; the CV and letter step.
12. **Application tracking** - stage per job with terminal flags, dates, notes, interview stages, follow-up date, outcome; stages are views of the Jobs list; interviews per application by track; board view later.
36. **One-step prepare** - one button runs evaluation, kit and fact check (later contacts and outreach draft) in the background; one review page, one approval; nothing is sent.
6. **Job source ingestion** - adapter contract: company board feeds (Greenhouse, Lever, Ashby, Workable), free remote feeds, JSearch; verify live, expiry, dedupe, per-host limits, monthly call budget, dismissed-job memory, legitimacy flag; no LinkedIn or Indeed scraping.
10. **Scheduled discovery** - daily run per track: fetch, gates without AI, evaluate the best within a budget, results in Today; gated jobs listed as "Filtered out" with the reason.
7. **Jobs list** - search, filters by track, stage, fit, location, source; keep or skip.
9. **Today** - home page as one queue: matches to keep or skip, applications to review, follow-ups due, interviews; one main button each; no widgets.
14. **Company and recruiter research** - public hiring-team info with source links, user-confirmed; no email guessing.
15. **Outreach drafts and log** - messages the user copies and sends; the Outreach step.
13. **Follow-ups and ghost watch** - due items in Today, flag applications silent for 10+ days, draft a nudge.
37. **Interview prep** - likely questions, story bank from confirmed history, company brief.
21. **Reachability check** - checklist of how a tailored CV reads to hiring systems (readability, headings, title match, truthful keyword coverage, file type), apply-early prompt.
38. **Showcase pack** - README, golden-set results, cost per evaluation, safety demo, video script; no personal data.

_Slice 2, validate and sell_
19. **Sign-up and onboarding flow** - four steps ending in a first evaluation. 17. **Data export and account deletion.** 40. **First payments by hand** - payment link and a staff-set paid flag for the first 10 customers. 16. **Subscription billing and entitlements** - regional price book (KES via Paystack with M-Pesa and cards, USD via a merchant of record), credits, checkout, dunning, invoices, pause. 39. **Telegram digest and alerts.** 24. **Email service.**

_Slice 3, grow and operate_
20 progress and quests; 18 application analytics; 22 Ask Migo; 23 localisation (English, Swahili); 25 admin panel; 26 support desk.

Excluded or later: auto-apply, browser automation, LinkedIn scraping, Hunter.io contact emails, BYOK, autonomous agents, Python scraping adapters (only within site terms), native app, team accounts, interview coaching, AI insights, application board view, sending email from the user's mailbox.

## Data model

Every user-owned row has `user_id`; all queries are scoped by it. Canonical jobs are shared public data; anything derived from a CV is private. Types are proposed starting points, to be locked by the feature that first uses each. Tables built on AI output or file parsing (CvFile, Profile and children, Evaluation, Document, Reachability, UsageEvent, AI cache) are owned by the engine in its own `engine` schema (Alembic); the rest live in `public` (Drizzle). No cross-schema foreign keys.

### User
- `id` (uuid), `email` (text, unique), `auth` fields (managed by the auth feature), `plan` (enum, default free), `telegram_chat_id` (text, nullable), `created_at` (timestamp)

### CvFile (built in 3a/3b)
- `id`, `user_id` (plain uuid, no FK across schemas), `storage_key` (private object), `filename`, `mime` (pdf|docx), `size_bytes`, `extracted_text`, `parse_status` (extracted|parsing|parsed|failed), `parse_error` (stable code, only when failed), `created_at`, `updated_at`

### Profile (the user's confirmed facts)
- `id`, `user_id`, `headline`, `summary`, `source_cv_id` (FK CvFile, unique: one draft per CV, cascade delete)
- Children, each with `user_id`, `profile_id`, `position`, `status` (extracted|confirmed|edited): `Experience` (`company`, `role`, `start`, `end` as `YYYY` or `YYYY-MM`, `is_current`, `bullets` json), `Skill` (`name`; `evidence_ref` and `used_in_role` arrive with the feature that first uses them), `Achievement` (`text`, `experience_id`), `Project` (`name`, `description`), `Education` (`institution`, `qualification`, `start`, `end`). Drafts from 3b are all `extracted`; feature 4 confirms or edits.

> Lock: generated documents and evaluations may only cite rows with `status` confirmed or edited.

### Track (profile variant + criteria)
- `id`, `user_id`, `name`, `variant_version` (int), `target_roles` (text[]), `salary_floor` (int), `currency`, `work_mode` (enum), `locations` (text[]), `eligibility` (text), `criteria` (json: items with `label`, `weight` must|important|nice), `dealbreakers` (json: hard rules checked before any AI call), `do_not_apply` (text[] of companies)
- `TrackProfileItem` links a Track to the Profile rows it emphasises.

### Company
- `id`, `name`, `domain`, `careers_url`, `summary` (text, nullable), `researched_at`

### JobSource
- `id`, `kind` (career_page|api), `base_url`, `adapter` (text), `active` (bool), `last_run_at`

### Job (canonical, shared)
- `id`, `company_id` (FK), `title`, `description`, `location`, `remote_policy`, `salary_min`, `salary_max`, `currency`, `category`, `requirements` (json, extracted), `dedupe_key` (text, indexed; normalised URL, company+role fallback), `legitimacy` (enum high|caution|suspicious), `legitimacy_notes` (json, never changes fit), `posted_at`, `first_seen_at`, `last_verified_at`, `status` (live|expired|unverified)
- `JobListing` (`job_id`, `source_id`, `url`, `external_id`): several listings merge into one Job.

### UserJob (per-user state)
- `id`, `user_id`, `job_id`, `track_id`, `kind` (job|gig|ai_training), `state` (new|saved|dismissed|skipped), `recheck_after` (date, nullable), `skip_reason` (text), `screen_result` (json), `created_at`

### Evaluation
- `id`, `user_job_id`, `profile_version`, `prompt_version`, `band` (strong|good|stretch|poor), `summary`, `requirements` (json: `need`, `status` met|partial|gap|unknown, `quote`, `evidence_ref`), `checks` (json: salary, location, eligibility, seniority), `cache_key` (content hash), `usage_event_id`

> Lock: no numeric score; each requirement carries evidence or an explicit `unknown`.

### Document
- `id`, `user_id`, `user_job_id`, `kind` (cv|cover_letter|proposal|answers), `version` (int), `content` (json), `fact_check` (json), `storage_key` (exported file, nullable)

### Contact and Outreach
- `Contact`: `id`, `company_id`, `name`, `role`, `public_source_url`
- `Outreach`: `id`, `user_id`, `contact_id`, `user_job_id` (nullable), `draft`, `status` (draft|sent|replied), `sent_at`

### Application
- `id`, `user_id`, `user_job_id`, `stage` (saved|preparing|applied|interviewing|offer|closed; terminal: offer, closed), `applied_at`, `notes`, `outcome` (nullable)
- `StageEvent` (`application_id`, `stage`, `at`), `Interview` (`application_id`, `kind`, `at`, `notes`), `FollowUp` (`application_id`, `due_at`, `done_at`)

### Notification
- `id`, `user_id`, `kind`, `payload` (json), `channel` (app|telegram), `sent_at`, `read_at`

### UsageEvent (AI ledger)
- `id`, `user_id`, `workflow` (parse|screen|evaluate|tailor|outreach), `provider`, `model`, `prompt_version`, `tokens_in`, `tokens_out`, `cost_usd`, `cache_hit` (bool), `created_at`

### Billing, support and admin
Field-level design in `docs/database-design.md`; architecture in `docs/technical-design.md`. Tables: `plan`, `region`, `price` (plan x region x interval, minor units), `subscription` (provider, status, `renewal_mode` auto or manual_mpesa), `payment`, `invoice`, `entitlement` (derived), `billing_event` (unique provider event id), `credit_adjustment`, `staff_member`, `role`, `audit_log` (append-only), `support_ticket`, `ticket_message`, `feature_flag`, `announcement`, `email_log`.

### Progress
- `ProgressEvent` (`user_id`, `kind` quest|follow_up|application|review, `xp`, `at`; level and streak derived), `Badge` (`user_id`, `key`, `earned_at`)

### Reachability
- `ReachabilityCheck`: `id`, `user_job_id`, `document_id` (FK), `items` (json: `check`, `status` pass|fix|unknown, `detail`), `keyword_coverage` (json: `present`, `missing`, `truthful_addable`), `prompt_version`, `created_at`

### BackgroundJob
- `id`, `kind`, `payload` (json), `status`, `attempts`, `run_at`, `idempotency_key` (unique)

## Tech stack

Two services over one Postgres: the TypeScript web app and a Python AI engine. No further microservices.

- **TanStack Start (Router, Query), React, TypeScript, Tailwind CSS** - UI layer only
- **TypeScript server code in TanStack Start** - accounts, billing, CRM, server functions and routes, Zod validation, Vitest
- **Python AI engine (FastAPI)** - Python 3.13 with uv, Pydantic v2, SQLAlchemy 2 async and Alembic, httpx, pytest, Ruff, strict typing. Owns everything that calls a model or parses a file. No public port: the web server calls it over internal HTTP with a bearer token and the verified user id. Decision (2026-11-08): the project also demonstrates AI engineering and parsing needs process isolation (`docs/python-engine-proposal.md`)
- **PostgreSQL, Drizzle, drizzle-kit** - web app data and migrations
- **Postgres-backed queue (pg-boss) + Node worker + scheduler** - background work; Redis only when volume or retries justify it
- **Private S3-compatible object storage** - CVs and exports via signed URLs
- **AI gateway (in the engine)** - provider-independent; per-task model routing, prompt versioning, schema-validated outputs, content-hash caching, usage ledger. Managed keys by default; BYOK later through the same interface
- **Better Auth** - in the web server, data in our PostgreSQL (`auth_*` tables), email and Google sign-in, sessions read directly by server functions, behind an auth interface; the application `user` stores `auth_subject` only
- **Resend** (free tier) first for transactional email behind an email interface; Postmark or another later for inbound support and broadcast
- **Paystack (Kenya, KES, M-Pesa and cards) and Paddle (international, USD, merchant of record)** - behind one billing interface
- **i18n catalogs** - English first, Swahili next
- **Telegram bot** - first notification channel
- **Docker** - packaging and deployment

AI task routing: conventional code for extraction, dedupe, expiry, filters, credit accounting and scheduling; cheap model for CV parsing, categorisation, requirement extraction and first-pass screening; stronger model for final evaluation, tailored documents and outreach. Cost control: reuse cached results (same job + same profile version), screen before deep evaluation, per-plan credit caps.

## Monetization

Subscription plus AI credits. Prices are hypotheses to test and differ by region: Kenya in KES (M-Pesa, cards via Paystack), international in USD (merchant of record). Prices are set per region, not converted, and edited in the admin panel.

- **Free:** CV upload, profile, application tracking (free on every plan), bring-your-own-job (paste a link or text), a small monthly allowance of evaluations and kits, a limited preview of automatic discovery once built.
- **Starter (~$9):** automatic daily discovery for one track, digest, monthly evaluation allowance.
- **Pro (~$19):** multiple tracks and profiles, Telegram alerts, tailored documents, CRM, larger credits.
- **Power (~$39):** recruiter research and outreach, highest credits, priority processing, exports.

Credits meter evaluation, tailoring and outreach with separate monthly quotas per workflow; cached results are free. Consider early-bird pricing for the first 10. Smallest paid set to test: verified daily discovery, evidence-based evaluation, Telegram digest, tailored CV. Distribution: LinkedIn build-in-public. Open until the founder edition has results: whether the paid line is discovery or evaluation and kit volume, a fixed job-search pass vs a monthly plan, and the first audience.

## UI/UX

Calm, focused workspace that removes steps: one queue of next actions, one page per job, one approval per application, verdict first with evidence one click away. Mascot Migo (briefcase); motion only on state changes, respecting reduced-motion. Light theme, warm ivory ground, white cards, orange accent #D97757 (dark text; primary buttons #B04A27 with white text), Fredoka headings, Nunito body. Not a chatbot or job board. Approved design canvas: https://claude.ai/artifact/2jc4qnjcWgNi6cFLu72k7Q. Locked tokens: `prototypes/theme.css`. Fit and status use text labels, never colour alone; 44px touch targets; sidebar stacks on small screens, lists instead of boards on phones.

Screens (route names proposed; the canvas still shows the older seven-page layout until feature 33 updates it):
- `/` - public homepage with waitlist; `/today` - action queue (replaces `/dashboard`)
- `/jobs` - list with stage views; `/jobs/$jobId` - job workspace: Fit, CV and letter, Outreach, Track
- `/profile` - profile review, tracks, preferences; `/settings` - account, data controls; staff cost page under `/admin`
- `/signup`; `/onboarding`; `/plans` (slice 2); empty/loading/error states

## Deployment

- Containers: `app` (TanStack Start Node server), `engine` (Python FastAPI, internal network only, no published port), `worker` (jobs and scheduler), Postgres, object storage.
- Host: one small VPS with Docker Compose behind Cloudflare, object storage for files and backups; scaling path in `docs/technical-design.md` (sections 15, 16). Provider and region chosen on price, stock and Kenya latency.
- Env vars (see `docs/technical-design.md`): `DATABASE_URL`, `STORAGE_BUCKET`, `STORAGE_ENDPOINT`, `STORAGE_KEY`, `STORAGE_SECRET`, `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, `RESEND_API_KEY`, `MAIL_FROM`, `AI_PROVIDER_KEYS`, `ENGINE_URL`, `ENGINE_TOKEN`, `TELEGRAM_BOT_TOKEN`, `PAYSTACK_SECRET_KEY` and `PADDLE_API_KEY` (later).
- Health check: `GET /healthz` on the app.
- Cron: daily discovery and digest run by the worker scheduler.
- Backups: daily Postgres backups, restore tested. Structured logs with request IDs; error tracking.
- > TODO domain.

## Open questions

> Resolve in the plans, then re-run /overview. Delete when empty.

- Feature 17 (export and deletion) must land before any other person's CV is stored.
- A hard AI spend cap in the engine gateway is undecided; the founder edition relies on the discovery budgets in 6 and 10.
- The first company board list (5 to 10) comes from the founder.
- Undecided: whether source adapters and the daily run live in the engine or the Node worker, and what schedules the run locally.
- Onboarding ends in a first shortlist (project plan) or a first evaluation (feature 19).
- The data model below predates the built per-user `engine.job` table; reconcile in feature 8 or 12.
