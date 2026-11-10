# Jobmigo - Project Overview

<!-- blueprint:source-hash 32748038b999683c1a49c9bace97dd8b8e52ff620f3285d22abcc483414489f5 -->

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
- **Validation:** 4 weeks of daily self-use, 10-15 interviews, concierge pilot with 5-10 people, $19 founding-member waitlist; goal 10 paying customers.

## Usage model

- Scale: founder first, then tens of users; no larger scale assumed.
- Internet-facing, multi-user: per-user isolation is a real requirement; users are ordinary job seekers, not assumed adversarial.
- Sensitive data: CVs and contact details; private storage, owner-scoped access, export and deletion, no personal CV data in logs or public content.
- Recruiter data: public information only.
- Not required now: enterprise SSO, compliance certifications, multi-region, team accounts, HA.

## Features

Slice 1 is the founder's paste-a-job loop; the **headline feature is #8, AI job evaluation**. Automatic discovery and alerts are the premium slice (3) and reuse the evaluator.

0. **Waitlist launch (27, 28a, 28b, 32; done)** - TypeScript full-stack switch; public homepage and consented waitlist with a Resend confirmation email; production deploy on one VPS behind Cloudflare with backups; animated homepage and design sync (canvas update published only with approval).

_Slice 1, the paste-a-job loop (usable by the founder)_
1. **Foundation and app shell** - sign-up/sign-in via Better Auth (sessions read by server functions) behind an auth interface, per-user scoping, staff roles skeleton and audit log, sidebar shell with theme, health check.
2. **AI gateway and usage ledger** (done; in the engine since 31) - provider interface, task routing, prompt versions, validated outputs, cost and cache logging.
30. **Python AI engine foundation** - FastAPI service in `engine/` (uv, Pydantic, Ruff, strict typing, pytest), Docker entry, health, internal bearer auth with the user id from the verified web session, own Postgres schema with Alembic, TypeScript client in the web server.
31. **Port the AI gateway and ledger to the engine** (done) - Python version with parity tests; the TypeScript gateway and its two tables are removed.
3. **CV upload and parsing** (in the engine) - private storage, text extraction in a resource-limited subprocess, AI parse into a profile draft. 3a storage, upload and extraction (done); 3b AI parse into an unconfirmed draft, engine and web API routes (done); 3c `/onboarding` upload and parse status screen.
4. **Profile review and track variants** - edit and confirm extracted facts, variants per track; 4a engine edit and confirm routes, 4b `/profile` screen, 4c tracks and variants.
5. **Job preferences and track criteria** - roles, salary floor, location, eligibility, must-haves per track, dealbreakers, do-not-apply list.
29. **Add a job by link or paste** - paste a link or posting text; fetch public page text when allowed, paste fallback; normalise, dedupe by URL, light legitimacy flag, saved and dismissed jobs; free on every plan.
8. **AI job evaluation** - dealbreaker gates before AI calls, cheap screen, evidence-based fit band (importance read from the posting first, inferred importance capped), gaps, salary/eligibility checks, research budget, cached; runs on a pasted job first, then on discovered jobs; a golden set of 30 to 50 real jobs with the founder's verdicts gates model and prompt changes (`uv run eval`).
11. **Application kit** - tailored CV, cover letter, answers from confirmed facts, fact check, versions, PDF/DOCX export.
12. **Application CRM** - canonical stages with terminal flags, dates, notes, interview stages, board view; free on every plan; records each outcome, shows interviews per application by track.
9. **Dashboard** - evaluated jobs, needs-action list, application progress, empty/loading states; discovery widgets arrive with 10.
19. **Sign-up and onboarding flow** - sign-up page, four-step onboarding ending in a first-evaluation moment (paste a job, see an evidence-based evaluation); the first-shortlist moment arrives with discovery.

_Slice 2, apply better and follow through_
13. **Follow-ups and ghost watch** - due items on dashboard and Telegram, flag applications silent for 10+ days and draft a nudge.
21. **Reachability check** - AI checklist of how a tailored CV reads to hiring systems (readability, headings, title match, truthful keyword coverage, file type), plus a hiring-team route and apply-early prompt.
14. **Company and recruiter research** - public hiring-team info and company summaries.
15. **Outreach drafts and log** - personalised messages and tracking.
20. **Progress and quests** - quests, streaks, levels, badges rewarding careful applications and follow-ups, not volume; weekly recap, Migo moments.

_Slice 3, premium automatic discovery_
16. **Subscription billing and entitlements** - plans, regional price book (KES via Paystack with M-Pesa and cards, USD via a merchant of record), credit allowances, checkout, M-Pesa prepaid renewal prompts, dunning, invoices, pause instead of cancel; free plan is bring-your-own-job with a small evaluation allowance.
6. **Job source ingestion (premium)** - adapter contract with per-host limits, URL-normalised dedupe, dismissed-job memory, verify live, expiry, legitimacy flag.
7. **Jobs list (premium)** - search, filters, saved and dismissed jobs.
10. **Scheduled discovery and Telegram alerts (premium)** - daily run, digest, strong-fit alerts, in-app notifications.

_Slice 4, grow and operate_
17. **Data export and account deletion** - full export, verified delete.
18. **Application analytics** - response rate, time to reply, outcomes by track.
23. **Localisation** - i18n catalogs (English, Swahili), locale and time zone, regional formatting, region-aware payments and tax display.
24. **Email service** - full layer beyond the waitlist confirmation (Resend first), per-locale templates, bounces, receipts, reminders, consented marketing.
25. **Admin panel** - staff roles with MFA, users, subscriptions, refunds, price book, job sources, AI cost, flags, ops, audit log.
26. **Support desk** - help form, inbound email to tickets, admin inbox, notes, canned replies.
22. **Ask Migo** - natural-language questions over the user's own data, with cited answers.

Excluded or later: auto-apply, browser automation, LinkedIn scraping, BYOK (gateway designed for it), autonomous agents, extra services, Python job-source adapters (only if scraping is approved within site terms), native app, team accounts, interview prep and coaching, AI insights dashboards, sending email from the user's mailbox (a read-only status scan may come later).

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
- `id`, `user_id`, `job_id`, `track_id`, `state` (new|saved|dismissed|skipped), `recheck_after` (date, nullable), `skip_reason` (text), `screen_result` (json), `created_at`

### Evaluation
- `id`, `user_job_id`, `profile_version`, `prompt_version`, `band` (strong|good|stretch|poor), `summary`, `requirements` (json: `need`, `status` met|partial|gap|unknown, `quote`, `evidence_ref`), `checks` (json: salary, location, eligibility, seniority), `cache_key` (content hash), `usage_event_id`

> Lock: no numeric score; each requirement carries evidence or an explicit `unknown`.

### Document
- `id`, `user_id`, `user_job_id`, `kind` (cv|cover_letter|answers), `version` (int), `content` (json), `fact_check` (json), `storage_key` (exported file, nullable)

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

Credits meter evaluation, tailoring and outreach with separate monthly quotas per workflow; cached results are free. Consider early-bird pricing for the first 10. Smallest paid set to test: verified daily discovery, evidence-based evaluation, Telegram digest, tailored CV. Daily hook: morning digest and "needs action" list. Distribution: LinkedIn build-in-public.

## UI/UX

Calm, focused SaaS workspace; data-rich but uncluttered. Mascot Migo (briefcase); light motion that respects reduced-motion; light gamification for quality actions only. Light theme, warm ivory ground, white cards, orange accent #D97757 (dark text; primary buttons #B04A27 with white text), Fredoka headings, Nunito body. Not a chatbot or job board. Approved design canvas: https://claude.ai/artifact/2jc4qnjcWgNi6cFLu72k7Q. Locked tokens: `prototypes/theme.css`. Fit and status use text labels, never colour alone; 44px touch targets; sidebar stacks on small screens, boards scroll horizontally.

Screens (route names proposed, all designed except `/settings`):
- `/` - public homepage with waitlist; signed-in `/dashboard` (includes progress and quests)
- `/jobs`, `/jobs/$jobId` - list and job evaluation; `/applications` - kanban board with ghost watch
- `/profile` - profile review (also onboarding step 2), variants, preferences, alerts, data controls
- `/documents` - application kit with fact and reachability checks; `/outreach` - contacts, drafts, log
- `/signup`; `/onboarding` (four steps: upload CV, review profile, make it yours, first shortlist); `/plans`; empty/loading/error states
- `/settings` - to design

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

- Feature 17 (export and deletion) comes after CVs are stored (feature 3); consider moving it earlier.
- "Credit limits from day one" (plan section 3) vs enforcement only arriving with billing (feature 16): decide whether the engine gateway (31) enforces a hard cap.
- Job source list (which ATS/career-page adapters first) is not chosen.
- In-app notifications are needed by feature 9 (dashboard) but built in feature 10.
