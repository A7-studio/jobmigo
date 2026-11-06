# Project Plan

Jobmigo is an AI-powered job-search operating system, the first commercial
product of A7Studio. The founder's own job search is the first real use case.
This plan is a draft for review. Items marked **Hypothesis** are to be tested,
not assumed.

## 1. Problem - What problem are we solving?

Job searching is a scattered, repetitive workflow: finding live roles, judging
fit, tailoring documents, finding people to contact, and remembering what was
sent to whom. Existing tools each cover one slice (boards, resume writers,
trackers) and most "AI apply" tools optimise volume over quality, which erodes
trust.

Jobmigo manages the whole journey in one workspace:
**Discover -> Verify -> Evaluate -> Prepare -> Contact -> Apply -> Track -> Improve.**

**The problem worth paying for (Hypothesis):** "Tell me which few verified jobs
deserve my time today, why, and give me a truthful tailored application in
minutes." Time saved on triage and tailoring, with evidence rather than a magic
score, is the wedge. Everything else (CRM, outreach) supports the daily habit.

Principles that shape every feature:
- Never fabricate experience. Generated documents may only reuse facts from the
  user's confirmed profile; anything new is flagged for confirmation.
- No fake precision. Fit is shown as bands (Strong, Good, Stretch) with
  per-requirement evidence, not a percentage.
- Only legitimate sources. No scraping behind logins, no ToS-violating
  automation, no auto-submitting applications.

## 2. Users - Who is this for?

**Initial ideal customer profile (Hypothesis):** experienced remote-seeking
software and technology professionals (engineers, product, AI/ML-adjacent
roles) running a multi-track search, who apply to 5+ roles a week and value
quality over volume.

Also served: experienced professionals changing jobs, freelancers and
contractors, remote-job seekers. The product must not be engineer-specific
(profile, tracks and criteria are generic), but the first sources and
messaging target tech roles.

**First user and test case:** the founder, a Flutter/mobile engineer searching
three tracks: (1) Flutter and mobile engineering, (2) AI coding evaluation and
AI training, (3) AI application engineering and related product engineering.
Each track has its own CV/profile variant and its own evaluation criteria.

**Validation before large investment:**
- Use it daily for 4 weeks on the founder's own search and record real outcomes.
- Run 10-15 problem interviews and a concierge pilot (manually run the
  pipeline for 5-10 people from LinkedIn, then replace manual steps with product).
- Landing page plus waitlist with a $19 "founding member" offer; the milestone
  is **10 paying customers**.

## 3. Features - What does the MVP need?

**MVP vertical slice (must be usable by the founder first):**
- Account registration and sign-in
- CV upload (PDF/DOCX) with AI parsing into a structured profile
- Profile review and editing, with multiple track variants
- Job preferences per track (roles, salary floor, location, eligibility, priorities, dealbreakers, do-not-apply list)
- Job discovery from legitimate public sources, with verification, dedupe and a posting-legitimacy flag
- Job list with search, filters and saved jobs
- AI job evaluation with fit band, per-requirement evidence and gaps
- Dashboard (relevant jobs, top opportunities, actions, progress)
- Scheduled discovery, daily digest and strong-fit alerts via Telegram and in-app
- AI usage ledger and credit limits from day one

**Next (after the slice):**
- Tailored CV, cover letter and application-question drafts with fact checking, PDF/DOCX export
- Application CRM: stages, notes, follow-ups, interview stages
- Progress and quests: daily quests, streaks, levels and badges that reward quality actions, not volume
- Reachability check: how a tailored CV reads to hiring systems, keyword coverage with truthful additions only, and a route to the hiring team
- Ghost watch: flags applications silent for 10+ days and drafts a follow-up
- Ask Migo: cited answers to questions about the user's own jobs, profile and applications
- Recruiter and company research from public information, drafted outreach
- Subscription billing and entitlements with regional prices (Kenya in KES, international in USD) and M-Pesa
- Localisation: language, currency, payment methods, time zone
- Admin panel and support desk: manage users, subscriptions, pricing, jobs sources, AI cost, flags; answer support requests
- Email service: transactional, billing, support and consented marketing email
- Data export and account deletion
- Application analytics

**Later or deliberately excluded:**
- Browser automation and auto-applying (risky, ToS and trust issues)
- Scraping LinkedIn or other sources that forbid it
- Bring-your-own-key (design the gateway for it, do not build it yet)
- Autonomous multi-step agents, microservices, native mobile app
- Team or agency accounts, interview prep and coaching (for now), AI insights dashboards (for now), salary negotiation tools
- Sending email from the user's mailbox (a read-only scan to detect status changes may come later)

## 4. Data - What are we storing?

Every user-owned row carries `user_id`; all queries are scoped by it.

- Users, sessions, plan and entitlements
- Uploaded CV files (private object storage) and parse results
- Career profile: experience, skills, achievements, projects, education
- Profile variants (per track) and job preferences / evaluation criteria
- Job sources and raw postings, canonical jobs (shared, deduplicated), source
  links, verification status and last-checked time
- Per-user job state: saved, dismissed, evaluation results with evidence
- Generated documents with versions (CV, cover letter, answers)
- Companies and public recruiter/hiring-team contacts, outreach drafts and log
- Applications, stage history, interviews, notes, follow-ups
- Notifications and Telegram link
- AI usage ledger: workflow, model, tokens, cost, cache hit, per user
- Prompt versions and cached AI results keyed by content hash

Canonical jobs are shared across users (public data); everything derived from
a user's CV or preferences is private to that user.

## 5. Tech - What stack are we using?

Modular monolith, no microservices.

- **Frontend:** TanStack Start (TanStack Router and Query), React, TypeScript, Tailwind CSS
- **Backend:** Python, FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL
- **Background work:** start with a Postgres-backed job table and a simple
  worker process plus a scheduler; introduce Redis/Celery only when volume or
  retry needs justify it
- **Storage:** private S3-compatible object storage with signed URLs
- **AI:** provider-independent AI gateway (single interface, per-task model
  routing, prompt versioning, schema-validated structured outputs, caching,
  usage and cost ledger). Managed keys by default; BYOK later via the same
  interface
- **Auth:** Better Auth (open source, in the web server, data in our PostgreSQL; email and Google sign-in, two-factor for staff later) issuing short-lived JWTs that the API verifies, behind a provider interface
- **Email:** Postmark (transactional, broadcast and inbound support email) behind a provider interface
- **Billing:** Paystack for Kenya (KES; M-Pesa and cards) and Paddle as merchant of record for international (USD), behind one billing interface
- **Admin and support:** staff-only `/admin` area with roles, audit log and an in-house support inbox
- **Localisation:** i18n catalogs (English, then Swahili), per-region price book and payment methods
- **Notifications:** Telegram bot first, plus in-app
- **Deployment:** Docker, one small cloud host

Challenges to the proposed split: a two-language stack doubles tooling and
deployment work for a solo builder. It is acceptable because the AI/ingestion
logic is Python-native, but keep the boundary thin (typed API contract
generated from OpenAPI) and keep TanStack Start as a UI layer only.

**AI task routing:**
- Conventional code: file text extraction, dedupe, expiry checks, filters,
  credit accounting, scheduling
- Cheap model: CV parsing, job categorisation, requirement extraction,
  first-pass screening of many jobs
- Stronger model: final evaluation of shortlisted jobs, tailored CV and cover
  letter, outreach drafts
- Cost control: cache by content hash (same job + same profile version = reuse),
  screen cheaply before evaluating deeply, evaluate on demand for low-ranked
  jobs, per-plan credit caps

## 6. Monetize - How will this make money?

Subscription with AI credits. All prices are **hypotheses to test**. Prices differ by region: Kenya is priced in KES and paid by M-Pesa or card through Paystack; international customers pay in USD through a merchant of record that handles global tax. Regional prices are set from local willingness to pay, not currency conversion, and are edited by finance staff in the admin panel. Pricing levels are an open business decision.

- **Free:** CV upload, profile, application tracking (free on every plan), saved
  jobs, limited discovery view, a few evaluations to show the value
- **Starter (~$9):** daily discovery for one track, daily digest, a monthly
  evaluation allowance
- **Pro (~$19):** multiple tracks and profiles, Telegram alerts, tailored
  documents, application CRM, larger credit allowance
- **Power (~$39):** recruiter research and outreach, highest credits, priority
  processing, exports

Credits meter the expensive workflows (evaluation, tailoring, outreach), with
separate monthly quotas per workflow so each is easy to explain and cap. Cached
results are free. Consider an early-bird price for the first 10 customers. Discovery itself is mostly conventional code, so it can be
generous. Track cost per user and per workflow from day one so pricing follows
real margin data.

Smallest paid feature set to test: verified daily discovery + evidence-based
evaluation + Telegram digest + tailored CV. Return-daily hook: the morning
digest and "needs action" list.

## 7. UI/UX - How should this look and feel?

Approved design canvas: https://claude.ai/artifact/2jc4qnjcWgNi6cFLu72k7Q
Locked theme: `prototypes/theme.css`.

Positioning: **an AI job-application assistant that gets applications out of the ghost pipeline and into interviews.** The main bottleneck is the application: filtered out by software, buried in the pile, or sent to a dead job. Jobmigo makes the CV reachable by hiring systems and recruiters, targets live jobs, and helps reach a human. Winning the interview is up to the user; no outcome is promised. The AI proposes and the user decides; AI output is labelled, evidence-backed and never sent without the user. The AI workflow map, model tiers and rules are in `docs/ai-workflows.md`.

Product name: **Jobmigo** (job + amigo). Mascot: Migo, a friendly briefcase character used in the logo, onboarding, empty states and homepage. Light motion (Migo blinks and bobs, bars and rings fill in, strong-fit badges glow gently) respects reduced-motion settings. Gamification is light: streaks, quests, levels and badges tied to careful applications and follow-ups.

Calm, focused SaaS workspace; data-rich but uncluttered. Light theme, warm ivory
ground, white cards, Claude orange (#D97757) accent, Fredoka (rounded, friendly)
headings with Nunito body text, chosen so a stressful search feels lighter. Not a chatbot and not an
ordinary job board. Inspired by the Joobin job-seeker dashboard direction
(original design, no copied assets); the reference image should be shared if
closer alignment is wanted.

Principle: a job search is already stressful, so the product should feel welcoming, trustworthy and a little playful. Copy is warm and plain, every trust promise is stated where the user needs it (privacy near the CV upload, "nothing is sent without you" near actions), and rewards are gentle.

Sign-up and onboarding flow (Jobmate's public pages show a single sign-up entry point, a free plan with no trial, and pre-selected plans from pricing; its actual sign-up form and wizard are not public, so this flow is our own design): Homepage -> Sign up (Google or email, free, no card, plan pre-selected if chosen) -> 1 Upload CV (privacy promises, skip option) -> 2 Review profile -> 3 Make it yours (tracks, weekly pace, must-haves, dealbreakers, optional Telegram) -> 4 First shortlist (the value moment: verified jobs, strong fits, welcome badge, Day 1 streak) -> Dashboard. The first shortlist appears before any payment ask.

Retention and conversion: daily Telegram digest, streaks with one freeze, daily quests, weekly goal ring, weekly recap with shareable numbers-only progress post, and honest contextual upgrade prompts (for example "9 matches are waiting" with free-plan limits). Free-plan limits (for example 4 job matches a day) and plan quotas are hypotheses to test. Pause (up to two months) is offered instead of cancel-only.

Screens designed: Homepage (hero, journey, features, quests, honest-by-design, waitlist), Sign up, the four-step onboarding flow, Plans and upgrade, Dashboard with Ask Migo, progress, quests, weekly recap and upgrade nudge, Jobs list, Job evaluation, Applications board with ghost watch,
Profile review, Onboarding, Application kit with reachability check, Outreach, and empty, loading and
error states, Settings, Help, regional Checkout (Kenya and international), the M-Pesa prompt, a prototype flow map, and four staff admin screens (overview, support inbox, users and subscriptions, pricing and regions). Technical and database design: `docs/technical-design.md` and `docs/database-design.md`.

Navigation: Dashboard, Jobs, Applications, Outreach, Documents, Career profile. Track switcher on list views. Responsive: sidebar stacks on small
screens, boards scroll horizontally, 44px minimum touch targets. Fit and
status are always conveyed by text labels, never colour alone.

## 8. Deployment - Where and how will this ship?

- Containers: `web` (TanStack Start), `api` (FastAPI), `worker` (jobs and scheduler),
  Postgres, object storage
- Early host: one small VPS running Docker Compose behind Cloudflare, with object
  storage for files and backups (about 10 to 40 USD a month fixed, plus AI cost);
  scale in stages (see `docs/technical-design.md` sections 15 and 16). Target: about
  100 users within a couple of months.
- Env vars by name: `DATABASE_URL`, `STORAGE_BUCKET`, `STORAGE_ENDPOINT`,
  `STORAGE_KEY`, `STORAGE_SECRET`, `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`,
  `BETTER_AUTH_JWKS_URL`, `BETTER_AUTH_ISSUER`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `AI_PROVIDER_KEYS`,
  `TELEGRAM_BOT_TOKEN`, `POSTMARK_SERVER_TOKEN`, `POSTMARK_INBOUND_SECRET`,
  `PAYSTACK_SECRET_KEY`, `PADDLE_API_KEY`, `SENTRY_DSN`
- Health check: `GET /healthz` on the API
- Scheduled work: daily discovery and digest run by the worker scheduler
- Backups: automated daily Postgres backups with a tested restore
- Logging: structured logs with request IDs and error tracking

## 9. Usage model and constraints (optional)

- Markets: Kenya first (KES, M-Pesa, English and Swahili), plus international customers (USD). Kenya Data Protection Act and GDPR may apply; confirm with a lawyer.
- Scale: single founder user first, then tens of users; the 10-paying-customer
  milestone drives early sizing. No scale beyond that is assumed.
- Internet-facing, multi-user from the start because the product is a SaaS and
  holds personal CVs; per-user data isolation is a real requirement. Users are
  assumed to be ordinary job seekers, not adversarial.
- Sensitive data: CVs and contact details. Needs private storage, access
  scoped by owner, export and deletion, and no personal CV data in logs or
  public build-in-public content.
- Recruiter data: only publicly available information, no private data
  harvesting.
- Not required now: enterprise SSO, compliance certifications, multi-region,
  team accounts, high availability beyond a single deployment.

## Commercial plan notes

- **Distribution:** LinkedIn build-in-public. Content shows real jobs
  discovered, verification and evaluation examples (with personal data
  removed), engineering and AI-cost decisions, and real application outcomes.
- **Competitive stance:** adopt end-to-end workflow and credit-based plans
  (Jobmate, Aarivi); adopt verification, dedupe and structured evaluation ideas
  (Career-Ops); deliberately exclude auto-apply and volume spam. The edge is
  trustworthy, evidence-backed evaluation and truthful documents.
- **Reference study:** see `docs/reference-study.md` for evidence-tagged findings
  on Jobmate, Career-Ops and Aarivi.
- **Biggest risks:** source coverage and legality, evaluation quality, AI cost
  per active user, churn after a job is found (consider a pause plan), and
  recruiter-data privacy.
