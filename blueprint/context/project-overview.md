# Jobmigo - Project Overview

<!-- blueprint:source-hash e4a69478b9e60f905da9f88ef9f3636ddb783e1e8adfd52754de7816393000c9 -->

> AI job-application assistant for professionals: gets applications out of the ghost pipeline and into interviews (no outcome promised; winning the interview is up to the user). AI proposes, the user decides; workflow map in `docs/ai-workflows.md`: Discover -> Verify -> Evaluate -> Prepare -> Contact -> Apply -> Track -> Improve. First product of A7Studio; the founder's own search is the first real use case.

## Problem

The main bottleneck is the application itself: filtered out by hiring software, buried in the pile, or sent to a job that is already dead. Job searching is also scattered and repetitive: finding live roles, judging fit, tailoring documents, finding contacts and remembering what was sent. Existing tools cover one slice, and "AI apply" tools favour volume over quality. Jobmigo tells the user which few verified jobs deserve time today, why, and prepares truthful tailored applications.

Principles for every feature:
- Never fabricate experience; documents reuse only confirmed profile facts, new claims are flagged for user confirmation.
- No fake precision: fit is a band (Strong, Good, Stretch) with per-requirement evidence, never a percentage.
- Legitimate sources only; no scraping behind logins, no ToS-violating automation, no auto-submitting applications.

## Users

- **Initial ICP (hypothesis):** experienced, remote-seeking software and technology professionals running a multi-track search, applying to 5+ roles a week, valuing quality over volume.
- **Also served:** career changers, freelancers/contractors, remote seekers; the product must not be engineer-specific.
- **First user:** the founder (Flutter/mobile engineer) with three tracks: Flutter and mobile; AI coding evaluation and AI training; AI application engineering and product engineering. Each track has its own profile variant and evaluation criteria.
- **Validation:** 4 weeks of daily self-use, 10-15 interviews, concierge pilot with 5-10 people, $19 founding-member waitlist. Milestone: 10 paying customers.

## Usage model

- Scale: founder first, then tens of users; no larger scale assumed.
- Internet-facing, multi-user: per-user data isolation is a real requirement. Users are ordinary job seekers, not assumed adversarial.
- Sensitive data: CVs and contact details; private storage, owner-scoped access, export and deletion, no personal CV data in logs or public content.
- Recruiter data: publicly available information only.
- Not required now: enterprise SSO, compliance certifications, multi-region, team accounts, HA beyond one deployment.

## Features

Build order from `build-plan.md`. Slice 1 is the paste-a-job loop usable by the founder; the **headline feature is #8, AI job evaluation**. Automatic discovery and alerts are the premium slice (3) and reuse the evaluator.

0. **Waitlist launch (features 27, 28a, 28b)** - 27 TypeScript full-stack switch (done); 28a public homepage and consented waitlist with a Resend confirmation email; 28b production deploy on one VPS behind Cloudflare with backups.

_Slice 1, the paste-a-job loop (usable by the founder)_
1. **Foundation and app shell** - sign-up/sign-in via Better Auth (sessions read by server functions) behind an auth interface, per-user scoping, staff roles skeleton and audit log, sidebar shell with theme, health check.
2. **AI gateway and usage ledger** - provider interface, task routing, prompt versions, validated outputs, cost and cache logging.
3. **CV upload and parsing** - PDF/DOCX to private storage, text extraction, AI parse into a profile draft.
4. **Profile review and track variants** - edit and confirm extracted facts, variants per track.
5. **Job preferences and track criteria** - roles, salary floor, location, eligibility, must-have vs nice-to-have per track, dealbreakers, do-not-apply list.
29. **Add a job by link or paste** - paste a link or the posting text; fetch public page text when allowed, paste fallback; normalise, dedupe by URL, light legitimacy flag, saved and dismissed jobs; free on every plan.
8. **AI job evaluation** - dealbreaker gates before AI calls, cheap screen, evidence-based fit band (importance read from the posting first, inferred importance capped), gaps, salary/eligibility checks, research budget, cached; runs on a pasted job first, then on discovered jobs; a golden set of 30 to 50 real jobs with the founder's verdicts gates model and prompt changes.
11. **Application kit** - tailored CV, cover letter, answer drafts from confirmed facts, fact check, versions, PDF/DOCX export.
12. **Application CRM** - canonical stages with terminal flags, dates, notes, interview stages, board view; free on every plan; each application records its outcome and the app shows interviews per application by track.
9. **Dashboard** - evaluated jobs, needs-action list, application progress, empty/loading states; discovery widgets arrive with feature 10.
19. **Sign-up and onboarding flow** - sign-up page, four-step onboarding ending in a first-evaluation moment (paste a job, see an evidence-based evaluation); first-shortlist moment arrives with discovery; demand validation (homepage and waitlist ship in 28).

_Slice 2, apply better and follow through_
13. **Follow-ups and ghost watch** - due items on dashboard and Telegram, flag applications silent for 10+ days and draft a nudge.
21. **Reachability check** - AI checklist of how a tailored CV reads to hiring systems (readability, headings, title match, keyword coverage with truthful additions only, file type), plus a hiring-team route and apply-early prompt.
14. **Company and recruiter research** - public hiring-team info and company summaries.
15. **Outreach drafts and log** - personalised messages and tracking.
20. **Progress and quests** - daily quests, streaks, levels, badges rewarding careful applications and follow-ups, not volume; weekly recap, streak freeze, Migo mascot moments.

_Slice 3, premium automatic discovery_
16. **Subscription billing and entitlements** - plans, regional price book (KES via Paystack with M-Pesa and cards, USD via a merchant of record), credit allowances, checkout, M-Pesa prepaid renewal prompts, dunning, invoices, upgrade prompts, pause instead of cancel; free plan is bring-your-own-job with a small evaluation allowance, paid plans add automatic discovery and alerts.
6. **Job source ingestion (premium)** - adapter contract with per-host limits, URL-normalised dedupe, dismissed-job memory with recheck window, verify live, detect expiry, legitimacy flag.
7. **Jobs list (premium)** - search, filters, saved and dismissed jobs.
10. **Scheduled discovery and Telegram alerts (premium)** - daily run, digest, strong-fit alerts, in-app notifications.

_Slice 4, grow and operate_
17. **Data export and account deletion** - full export, verified delete.
18. **Application analytics** - response rate, time to reply, outcomes by track.
23. **Localisation** - i18n catalogs (English, Swahili), locale and time zone, regional formatting, region-aware payment methods and tax display.
24. **Email service** - full layer beyond the waitlist confirmation (Resend first), per-locale templates, bounce handling, receipts and reminders, consented marketing.
25. **Admin panel** - staff roles with MFA, users, subscriptions and refunds, price book, job sources, AI cost, flags, announcements, ops, audit log.
26. **Support desk** - in-app help form, inbound email to tickets, admin inbox, notes, canned replies.
22. **Ask Migo** - natural-language questions over the user's own jobs, profile and applications, with cited answers.

Excluded or later: browser automation/auto-apply, LinkedIn scraping, BYOK (gateway designed for it, not built), autonomous agents, microservices, native app, team accounts, interview prep and coaching (later), AI insights dashboards (later), sending email from the user's mailbox (a read-only status scan may come later).

## Data model

Every user-owned row has `user_id`; all queries are scoped by it. Canonical jobs are shared public data; anything derived from a CV or preferences is private. Types are proposed starting points, to be locked by the feature that first uses each.

### User
- `id` (uuid), `email` (text, unique), `auth` fields (managed by the auth feature), `plan` (enum, default free), `telegram_chat_id` (text, nullable), `created_at` (timestamp)

### CvFile
- `id`, `user_id` (FK User), `storage_key` (text, private object), `filename`, `mime` (pdf|docx), `extracted_text` (text), `parse_status` (enum), `created_at`

### Profile (the user's confirmed facts)
- `id`, `user_id`, `headline`, `summary`, `source_cv_id` (FK CvFile)
- Children, each with `profile_id`, `status` (extracted|confirmed|edited): `Experience` (`company`, `role`, `start`, `end`, `bullets` json), `Skill` (`name`, `evidence_ref`, `used_in_role` bool), `Achievement` (`text`, `experience_id`), `Project`, `Education`

> Lock: generated documents and evaluations may only cite rows with `status` confirmed or edited.

### Track (profile variant + criteria)
- `id`, `user_id`, `name`, `variant_version` (int), `target_roles` (text[]), `salary_floor` (int), `currency`, `work_mode` (enum), `locations` (text[]), `eligibility` (text), `criteria` (json: items with `label`, `weight` must|important|nice), `dealbreakers` (json: hard rules checked before any AI call), `do_not_apply` (text[] of companies)
- `TrackProfileItem` links a Track to the Profile rows it emphasises.

### Company
- `id`, `name`, `domain`, `careers_url`, `summary` (text, nullable), `researched_at`

### JobSource
- `id`, `kind` (career_page|api), `base_url`, `adapter` (text), `active` (bool), `last_run_at`

### Job (canonical, shared)
- `id`, `company_id` (FK), `title`, `description`, `location`, `remote_policy`, `salary_min`, `salary_max`, `currency`, `category`, `requirements` (json, extracted), `dedupe_key` (text, indexed; normalised URL, company+role fallback), `legitimacy` (enum high|caution|suspicious), `legitimacy_notes` (json observations, never changes fit), `posted_at`, `first_seen_at`, `last_verified_at`, `status` (live|expired|unverified)
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
- `Entitlement` (`user_id`, `plan`, `credits_total`, `credits_used`, `period_end`)

### Billing, support and admin
Full field-level design in `docs/database-design.md`; architecture, auth, billing, email, localisation and admin in `docs/technical-design.md`. Tables: `plan`, `region`, `price` (plan x region x interval, amount in minor units), `subscription` (provider, status, `renewal_mode` auto or manual_mpesa), `payment`, `invoice`, `entitlement` (derived), `billing_event` (unique provider event id), `credit_adjustment`, `usage_event`, `staff_member`, `role`, `audit_log` (append-only), `support_ticket`, `ticket_message`, `feature_flag`, `announcement`, `email_log`.

### Progress
- `ProgressEvent`: `id`, `user_id`, `kind` (quest|follow_up|application|review), `xp` (int), `at`; level and streak are derived
- `Badge`: `user_id`, `key`, `earned_at`

### Reachability
- `ReachabilityCheck`: `id`, `user_job_id`, `document_id` (FK Document), `items` (json: `check`, `status` pass|fix|unknown, `detail`), `keyword_coverage` (json: `present`, `missing`, `truthful_addable`), `prompt_version`, `created_at`

### BackgroundJob
- `id`, `kind`, `payload` (json), `status`, `attempts`, `run_at`, `idempotency_key` (unique)

## Tech stack

Modular monolith, no microservices.

- **TanStack Start (Router, Query), React, TypeScript, Tailwind CSS** - UI layer only
- **TypeScript server code in TanStack Start** - domain modules, server functions and routes, Zod validation, Vitest; one language end to end (decision: the founder maintains the code; a Python service may be added later only if needed)
- **PostgreSQL, Drizzle, drizzle-kit** - data and migrations
- **Postgres-backed queue (pg-boss) + Node worker + scheduler** - background work; Redis only when volume or retries justify it
- **Private S3-compatible object storage** - CVs and exports via signed URLs
- **AI gateway** - provider-independent; per-task model routing, prompt versioning, schema-validated outputs, content-hash caching, usage ledger. Managed keys by default; BYOK later through the same interface
- **Better Auth** - in the web server, data in our PostgreSQL (`auth_*` tables), email and Google sign-in, sessions read directly by server functions, behind an auth interface; the application `user` stores `auth_subject` only
- **Resend** (free tier) first for transactional email behind an email interface; Postmark or another provider later for inbound support and broadcast
- **Paystack (Kenya, KES, M-Pesa and cards) and Paddle (international, USD, merchant of record)** - behind one billing interface
- **i18n catalogs** - English first, Swahili next
- **Telegram bot** - first notification channel
- **Docker** - packaging and deployment

AI task routing:
- Conventional code: text extraction, dedupe, expiry checks, filters, credit accounting, scheduling.
- Cheap model: CV parsing, categorisation, requirement extraction, first-pass screening.
- Stronger model: final evaluation, tailored documents, outreach.
- Cost control: reuse cached results (same job + same profile version), screen before deep evaluation, per-plan credit caps.

## Monetization

Subscription plus AI credits. Prices are hypotheses to test and differ by region: Kenya in KES (M-Pesa, cards via Paystack), international in USD (merchant of record). Prices are set per region, not converted, and edited in the admin panel.

- **Free:** CV upload, profile, application tracking (free on every plan), bring-your-own-job (paste a link or text), a small monthly allowance of evaluations and kits, a limited preview of automatic discovery once built.
- **Starter (~$9):** automatic daily discovery for one track, digest, monthly evaluation allowance.
- **Pro (~$19):** multiple tracks and profiles, Telegram alerts, tailored documents, CRM, larger credits.
- **Power (~$39):** recruiter research and outreach, highest credits, priority processing, exports.

Credits meter evaluation, tailoring and outreach, with separate monthly quotas per workflow; cached results are free. Consider early-bird pricing for the first 10 customers. Smallest paid set to test: verified daily discovery, evidence-based evaluation, Telegram digest, tailored CV. Daily hook: morning digest and "needs action" list. Reference study: `docs/reference-study.md`. Distribution: LinkedIn build-in-public, with personal CV and recruiter data protected.

## UI/UX

Calm, focused SaaS workspace; data-rich but uncluttered. Product name Jobmigo; mascot Migo (briefcase character in logo, onboarding, empty states, homepage); light motion that respects reduced-motion; light gamification (streaks, quests, levels, badges) for quality actions only. Light theme, warm ivory ground, white cards, Claude orange (#D97757) accent (dark text on #D97757; primary buttons are deeper #B04A27 with white text), Fredoka headings with Nunito body text (playful, calming). Not a chatbot or job board. Approved design canvas: https://claude.ai/artifact/2jc4qnjcWgNi6cFLu72k7Q. Locked tokens: `prototypes/theme.css` (port to the app's theme in the first UI feature). Fit and status always use text labels, never colour alone; 44px minimum touch targets; sidebar stacks on small screens, boards scroll horizontally.

Screens (route names proposed):
- `/` - public homepage with waitlist (designed); signed-in `/dashboard` (designed, includes progress and quests)
- `/jobs`, `/jobs/$jobId` - list and job evaluation (both designed)
- `/applications` - kanban board with ghost watch (designed)
- `/profile` - profile review (also onboarding step 2), variants, preferences, alerts, data controls (designed)
- `/documents` - application kit with fact check and reachability check (designed)
- `/outreach` - contacts, drafts, activity log (designed)
- `/signup` - sign-up (designed); `/onboarding` - four steps: upload CV, review profile, make it yours, first shortlist (all designed); `/plans` - plans and upgrade (designed); empty/loading/error states (designed)
- `/settings` - to design

## Deployment

- Containers: `app` (TanStack Start Node server), `worker` (jobs and scheduler), Postgres, object storage.
- Host: one small VPS with Docker Compose behind Cloudflare, object storage for files and backups; staged scaling path in `docs/technical-design.md` (sections 15 and 16). Provider and region chosen on price, stock and Kenya latency.
- Env vars (see `docs/technical-design.md`): `DATABASE_URL`, `STORAGE_BUCKET`, `STORAGE_ENDPOINT`, `STORAGE_KEY`, `STORAGE_SECRET`, `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, `RESEND_API_KEY`, `MAIL_FROM`, `AI_PROVIDER_KEYS`, `TELEGRAM_BOT_TOKEN`, `PAYSTACK_SECRET_KEY` and `PADDLE_API_KEY` (later).
- Health check: `GET /healthz` on the app.
- Cron: daily discovery and digest run by the worker scheduler.
- Backups: daily Postgres backups with a tested restore. Structured logs with request IDs and error tracking.
- > TODO build and start commands, domain.

## Open questions

> Resolve in the plans, then re-run /overview. Delete when empty.

- Feature 19 (sign-up and onboarding) is last; the waitlist ships earlier in feature 28 for demand validation.
- Feature 17 (export and deletion) is scheduled after CVs are stored (feature 3); the plan states export and deletion are a requirement. Consider moving it earlier.
- "Credit limits from day one" (plan section 3) vs enforcement only arriving with billing (feature 16): decide whether feature 2 enforces a hard cap.
- Job source list (which ATS/career-page adapters first) and the identity/auth provider are not chosen.
- Project plan §3 lists Telegram and in-app alerts together with scheduled discovery; feature 10 matches, but in-app notifications are also needed by feature 9 (dashboard).
