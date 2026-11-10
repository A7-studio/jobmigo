# Jobmigo technical design

Status: draft for review, 2026-11-06. Companion documents: `database-design.md`
(data), `ai-workflows.md` (AI), `reference-study.md` (competitors).

Items marked **Verify** rest on facts we could only partly confirm from public
sources and must be checked before we commit.

## 1. Purpose and scope

Jobmigo is an AI job-application assistant. It finds live jobs, evaluates fit,
tailors truthful CVs, checks that a CV is reachable by hiring systems, helps reach
a human, and tracks follow-ups, so applications do not vanish into the ghost
pipeline. This document describes how the system works: architecture, backend,
authentication, billing and localisation, email, support, the admin panel, data,
security and operations.

**Non-goals for the first release:** microservices, auto-applying, scraping sites
that forbid it, native mobile apps, enterprise SSO, multi-region active-active.

## 2. System context

```mermaid
flowchart LR
  U[Job seeker] --> WEB[Web app<br/>TanStack Start]
  S[Staff: support and admin] --> WEB
  WEB --> DB[(PostgreSQL)]
  WEB --> OBJ[(Private object storage)]
  WRK[Worker and scheduler<br/>same codebase] --> DB
  WRK --> OBJ
  WEB -- internal HTTP --> ENG[AI engine<br/>Python FastAPI]
  WRK --> ENG
  ENG --> LLM[Model providers]
  ENG --> DB
  ENG --> OBJ
  WRK --> SRC[Public job sources]
  WEB --> PAY[Payment providers<br/>Paystack and merchant of record]
  PAY -- webhooks --> WEB
  WEB --> MAIL[Email provider]
  MAIL -- inbound support email --> WEB
  WEB --> TG[Telegram bot]
  TG --> U
  MAIL --> U
```

## 3. Architecture overview

Two services over one Postgres. The web app is TypeScript on TanStack Start: the UI
and the server code live together, and background work runs in a second Node process
from the same codebase. The AI engine is a Python FastAPI service that owns everything
that calls a model or parses a file (see "The AI engine" below).

| Container | Technology | Responsibility |
|---|---|---|
| `web` | TanStack Start, React, TypeScript, Tailwind, Better Auth, Drizzle | Public site, app UI, admin UI, and all server code: sign-up, sign-in and sessions (Better Auth), business logic, validation, authorisation, billing logic, webhooks, in `web/src/server/` |
| `worker` | Same code as `web` (separate Node process) | Background jobs, schedules, retries, email sending, AI calls, job-source ingestion |
| `engine` | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic | AI gateway and usage ledger, CV storage and extraction, parsing, evaluation, application kit. Internal network only |
| `db` | PostgreSQL | System of record, job queue, audit trail |
| `storage` | S3-compatible private bucket | CVs, generated documents, invoice PDFs |

### Backend modules

Each module owns its tables, schemas, service functions and server functions. A module calls
another only through that module's service functions, never its tables.

| Module | Owns |
|---|---|
| `identity` | Application users, consent, data requests, staff and roles. Sign-in itself lives in Better Auth (web server) |
| `profiles` | CV upload and parsing, profile, tracks |
| `jobs` | Sources, adapters, ingestion, dedupe, verification, legitimacy |
| `evaluation` | Screening, fit evaluation, evidence |
| `documents` | Tailored CV and letters, fact check, reachability check, export |
| `applications` | Pipeline, follow-ups, ghost watch |
| `outreach` | Public contacts, drafted notes, send log |
| `progress` | Quests, streaks, levels, badges |
| `ai` | The AI gateway, prompts, cache, usage ledger |
| `billing` | Plans, regional prices, subscriptions, payments, entitlements, credits |
| `notifications` | In-app, Telegram, email dispatch, templates |
| `support` | Tickets, messages, canned replies |
| `admin` | Staff-only operations, RBAC, audit log, feature flags, announcements |
| `platform` | Config, logging, errors, jobs, health, i18n helpers |

### The AI engine

Boundary rule: if it calls a model or parses a file, it lives in the engine with its data;
everything else stays in the web app. The modules `ai` and the AI and document parts of
`profiles`, `evaluation`, `documents` and `outreach` belong to the engine.

- **Auth between services:** the web server calls the engine with
  `Authorization: Bearer <ENGINE_TOKEN>` and `X-User-Id`, set from the verified session. The
  engine never sees cookies and has no public port. Every engine query is scoped by that user
  id. A missing or wrong token is 401.
- **Data:** one Postgres, two schemas. Drizzle owns `public`; the engine owns schema `engine`
  through Alembic. No cross-schema foreign keys; account deletion calls an engine endpoint that
  removes a user's rows and stored files. Backups cover both because they are one database.
- **Uploads:** the browser posts to a web route that streams the body to the engine. The engine
  stores the file in private object storage and extracts text in a subprocess with memory and CPU
  limits and a wall-clock timeout, reading archives with byte-counted limits.
- **Background work:** in-process tasks with a status column to start; a Postgres job table and
  worker later.
- **Tooling:** `uv`, Ruff, a strict type checker and pytest, with commands in `AGENTS.md`.
- **As built (feature 30):** `engine/` holds the app factory, internal auth (`/internal/*` needs the
  bearer token and a UUID `X-User-Id`), `/healthz` and `/readyz`, JSON logs with a request id, and
  an empty Alembic baseline in schema `engine`. The web side calls it through
  `web/src/server/engine/client.ts` (`callEngine`), which sends the token, the verified user id and
  the request id with a 30 s timeout. Locally the engine is published on `127.0.0.1:8100`; in the
  production compose file it publishes no port. See `engine/README.md`.

### CV storage and extraction (feature 3a, as built)

- **Routes.** The web server exposes `POST /api/cv` (raw file bytes as the body, name in
  `X-Filename` percent-encoded), `GET /api/cv`, `GET /api/cv/:id/download` (302 to a signed
  link) and `DELETE /api/cv/:id`. Each needs a session and calls the engine's
  `/internal/cv` routes with the session user's id. The body is passed on as a stream through
  a byte counter that stops at 5 MiB.
- **Storage.** `engine/src/engine/storage/` holds an `ObjectStore` protocol, an S3 adapter
  (boto3, Signature V4, path-style) and an in-memory store for tests. Settings are read at
  call time from `STORAGE_ENDPOINT`, `STORAGE_BUCKET`, `STORAGE_KEY`, `STORAGE_SECRET`, optional
  `STORAGE_REGION` (default `us-east-1`) and optional `STORAGE_PUBLIC_ENDPOINT` (the host signed
  links are built for; needed when the engine reaches storage by an internal name, as in the full
  compose stack). A missing bucket is created on first write only when `ENVIRONMENT=local`.
  Keys are `cv/<userId>/<uuid4>`; links last 300 seconds. The local store is RustFS
  (`docker compose up -d storage`, API on port 9100).
- **Extraction.** The type comes from the first bytes. Parsing runs in a child process
  (`python -I -m engine.cv.worker`) that limits itself to 512 MiB of address space (Linux only),
  10 CPU seconds, no core files and 32 open files, while the parent enforces a 15 second wall
  clock, caps the output it reads, passes an empty environment and runs at most two children at
  once. DOCX bytes are counted as they are inflated (10 MiB for `word/document.xml`, never
  trusting declared sizes); PDFs are limited to 50 pages; text to 200,000 characters. The child
  is bounded, not sandboxed: it has no network or syscall filter.
- **Limits** live in `engine/src/engine/cv/limits.py`. Errors are `cv_too_large` 413,
  `cv_unsupported_type` 415, `cv_unreadable` 422, `storage_not_configured` 503,
  `storage_unavailable` 502 and `not_found` 404. The web server reports engine 5xx as
  `engine_unavailable`.
- **Privacy.** Filenames, bytes, text, keys and signed links are never logged; the list never
  returns text. Account deletion must delete each file (not built yet), and `readyz` does not
  check storage yet.

### CV parse (feature 3b, as built)

- **Flow.** `POST /api/cv/:id/parse` (web) calls `POST /internal/cv/:id/parse`. It claims the
  row atomically (`extracted` or `failed` to `parsing`), starts an in-process task and answers
  202; it answers 200 when the CV is already `parsed` and the same 202 if a parse is running.
  `GET /api/cv/:id` returns the status (`parseStatus`, `parseError`) and
  `GET /api/cv/:id/profile` the draft once `parsed`. Parse is explicit: upload does not start it.
- **Task.** `engine/src/engine/cv/parse.py`: gateway task `cv-parse`, cheap tier, workflow
  `parse`, prompt version `cv-parse-v1`, cache off (a parse only re-runs after a failure, and a
  cache would keep a second copy of derived CV data). The CV text goes in a delimited block that
  the prompt marks as data; the reply must match bounded Pydantic models (unknown keys, long
  strings, too many rows and dates other than `YYYY` or `YYYY-MM` are rejected, and the gateway
  retries once). Text over 60,000 characters fails instead of being cut.
- **Draft.** One `engine.profile` per CV with `experience`, `skill`, `achievement`, `project`
  and `education` children, all `status = extracted` (unconfirmed; feature 4 confirms or edits).
  The draft and the `parsed` status are written in one transaction that only commits if the CV
  is still `parsing`, so a CV deleted mid-parse leaves nothing. Deleting a CV cascades to its draft.
- **Failures** are stored as a code in `cv_file.parse_error`: `ai_not_configured`,
  `ai_unavailable`, `ai_output_invalid`, `ai_input_invalid`, `text_too_long`, `no_profile_found`,
  `interrupted`, `internal`. A missing AI setting is refused with 503 before any claim. A retry is
  the same `POST` from `failed`.
- **One engine process.** The task runs in the engine process and a startup sweep turns rows left
  in `parsing` by a restart into `failed` / `interrupted`. Running more than one engine replica
  needs the background worker first.
- **Privacy.** CV text goes to the cheap-tier provider (DeepSeek, named on `/privacy`) only when a
  parse is requested. CV text, names and replies are never logged; `usage_event` holds no text.

### CV upload and parse screen (feature 3c, as built)

- **Route.** `/onboarding` (signed in, inside the app shell) is step 1 of the four-step flow in the
  design canvas: a dropzone (PDF or DOCX, 5 MB), a file card with the real status, and a trust box
  that says only what is true today. Sign-up now lands here; the dashboard links to it.
- **Flow.** Choose a file, checked in the browser (`lib/cv-view.ts`) and again by the engine, then
  `POST /api/cv`; the user presses "Build my profile draft" (`POST /parse`); the page polls the CV
  list every 2 seconds while `parsing` (and stops after 3 minutes with a "Check again" button);
  `parsed` shows counts and the first roles from `GET /api/cv/:id/profile`, labelled unconfirmed.
- **Failures.** Every parse and upload code maps to calm copy in `lib/cv-view.ts` with only the
  actions that can help ("Try again" for transient codes; "Upload another file" for
  `text_too_long`, `no_profile_found` and unreadable files). No raw engine message or code is shown.
- **Delete** is on the page with an inline confirm and also removes the draft.
- **Not built yet** (honest gaps against the board): the tracks card, manual entry, and "Review
  my profile" (feature 4).

### Profile facts: edit and confirm (feature 4a, as built)

- **The profile** is the user's latest parsed draft (`GET /internal/profile`, web `/api/profile`).
  Replacing a CV starts a new unconfirmed draft; merging drafts is a later feature.
- **Statuses.** `extracted` (from the parse), `confirmed` (the user said it is right) and `edited`
  (the user changed it, or added it). Generated work may cite `confirmed` and `edited` only.
- **Routes.** `PATCH /api/profile` (headline, summary), `POST /api/profile/items/:kind` (add),
  `PATCH` and `DELETE /api/profile/items/:kind/:id`, `POST .../:id/confirm`, and
  `POST /api/profile/confirm-all`. Kinds: experience, skill, achievement, project, education.
- **Rules.** A patch must change something to count (a no-op changes nothing); a real change sets
  `edited`. Confirm turns `extracted` into `confirmed` and leaves the others alone. Adds use the
  parse limits and bounds; a skill name already present is `409 already_exists`; an achievement may
  link only to an experience of the same profile. Deleting an experience keeps its achievements,
  unlinked.
- **`profile.version`** goes up by one on every real change, in the same transaction. Evaluations
  and documents key their caches on it.
- **Errors** are stable codes (`not_found`, `validation_failed`, `limit_reached`, `already_exists`)
  and never echo what was sent. An item of an older draft, or another user's, is `not_found`.

### Layering inside a module

routes (thin: validate, call service) -> services (business rules) -> repositories
(queries, always owner-scoped) -> models. External providers are used only through
interfaces defined in the owning module.

### Provider interfaces

Every external service sits behind a small interface so it can be swapped.

| Interface | Methods (sketch) | First implementation |
|---|---|---|
| `AuthProvider` | `getSession(headers) -> { user: { id, email, name } } or null` | Better Auth sessions (see section 6) |
| `BillingProvider` | `create_checkout`, `change_plan`, `cancel`, `pause`, `refund`, `parse_webhook` | Paystack (Kenya), Paddle (international) |
| `EmailProvider` | `send(template, to, locale, data)`, `parseInbound` | Resend first; Postmark or another later |
| `NotificationChannel` | `deliver(user, message)` | In-app, Telegram, email |
| `AIProvider` (engine) | `complete(task, input, schema)` | Chosen per task in config |
| `JobSourceAdapter` | `detect`, `fetch` | Public career pages and job APIs |
| `ObjectStore` (engine) | `put`, `signed_url`, `delete` | S3-compatible |

## 4. Backend behaviour

### Request lifecycle

1. The browser calls a server function or route with its session cookie.
2. Request middleware assigns a request id; `requireUser` reads the session and loads the `user`.
3. The function validates input and calls a service, always scoped by the user id.
4. The service checks permissions and entitlements, does the work, and returns typed data.
5. Errors are typed domain errors mapped to one `{ code, message }` shape; unexpected errors are logged without personal data and returned as a generic error.

### Background work

- Jobs are rows in `background_job` with status, attempts, `run_at` and a unique `idempotency_key`. Workers claim rows with `SELECT ... FOR UPDATE SKIP LOCKED`.
- Handlers are safe to run twice. Retries use exponential backoff with a maximum attempt count, then a dead state visible in the admin panel.
- A scheduler enqueues recurring work: job discovery, digest per user at 07:30 local time, ghost-watch scan, entitlement resets, data purge.
- Slow or external steps (CV parsing, AI calls, source fetches, email) always run in the worker.
- Move to Redis and Celery only when queue volume or latency demands it.

### Idempotency and retries

- Webhooks and API writes that move money or credits carry an idempotency key. Duplicate deliveries are detected by `billing_event.provider_event_id`.
- External calls have timeouts and retries. A failing source or provider degrades one feature, never the whole app.

### Server interface style

Server functions (typed end to end, no generated client) serve the app UI, and
server routes serve webhooks, health checks and any public endpoint. Both return
the stable `{ code, message }` error shape. Staff functions sit behind a separate
permission check.

## 5. Frontend architecture

- TanStack Start: file-based routes, loaders that prefetch through TanStack Query, server rendering for the public site.
- Routes: public (`/`, `/pricing`, `/signup`), onboarding, app (`/dashboard`, `/jobs`, `/applications`, `/documents`, `/outreach`, `/profile`), billing (`/plans`, `/checkout`), admin (`/admin/*`, staff only).
- The web server also hosts Better Auth (`/api/auth/*`). Business logic lives in `web/src/server/` modules, called from thin server functions and routes; client components never import it.
- Styling from the locked tokens in `prototypes/theme.css`. Motion respects reduced-motion settings.

## 6. Authentication and authorisation

**Choice: Better Auth** (open source, TypeScript), running inside the TanStack Start
web server, with its data in our own PostgreSQL database.

- Why: no per-user fee and no external account or vendor lock-in, our users live in our database, email and password plus Google sign-in out of the box, a plugin for two-factor authentication (staff), and first-class TanStack Start support.
- Trade-offs accepted: we own the security configuration (password rules, rate limits, cookie settings), keep it patched, and build the sign-in screens ourselves. Email verification and password reset need the email service (feature 24).
- Alternatives kept in view: Clerk (managed UI and a free tier, but per-user pricing later and vendor lock-in) and WorkOS AuthKit.
- Portability: server code depends only on the `AuthProvider` shape (`getSession`). The application `user` row stores `auth_subject` (the Better Auth user id) and email; everything else about people stays in our tables.

### How identity reaches the app

Better Auth owns four tables (`auth_user`, `auth_session`, `auth_account`,
`auth_verification`) in the same database. Drizzle migrations create them like every
other table. The rest of the server code never reads them directly. It asks for the
session and maps it to the application `user` row.

```mermaid
sequenceDiagram
  participant B as Browser
  participant S as Web server
  participant D as PostgreSQL
  B->>S: Sign up or sign in (email and password, or Google)
  S->>D: Create user, account and session rows
  S-->>B: Session cookie
  B->>S: Server function call (cookie attached)
  S->>S: requireUser: read the session
  S->>D: Find or create the application user from the session
  S-->>B: Data
```

- `requireUser` is the only source of the acting user. It creates the `user` row on first use (concurrent first requests create one row), refuses suspended or deleted users, and refuses an email already owned by another identity.
- Account linking is disabled until email verification exists (feature 24), so a pre-registered unverified email cannot be taken over by a later social sign-in.

### Authorisation

- **Users:** every query is scoped by the authenticated `user_id`, taken from the verified session, never from client input.
- **Entitlements:** plan features and credit balance are checked in services before any paid or AI action.
- **Staff:** roles `support`, `finance`, `admin`, `owner` with explicit permissions (`users.read`, `tickets.reply`, `billing.refund`, `pricing.write`, `flags.write`). Staff accounts will require two-factor authentication (Better Auth plugin) and are provisioned by an owner.
- Staff functions are separate, permission-checked, rate-limited and write an audit row for every read or change of user data.

### Security settings we own

Password minimum length 8 and a breached-password check when available, rate limits
on sign-in and sign-up, secure and `HttpOnly` cookies, CSRF protection, a long random
`BETTER_AUTH_SECRET` per environment, trusted origins limited to our domains, and a
separate database role for migrations once deployed.

## 7. Subscriptions, billing and payments

### Principles

- Two payment rails behind one `BillingProvider` interface, chosen by the user's **billing region**, not just IP.
- Our database holds the truth about what a user is entitled to. Providers hold the money.
- Webhooks are the only way subscription state changes. We never trust the browser redirect.
- No card or mobile-money credentials touch our servers.

### Providers by region

| Region | Currency | Provider | Methods | Notes |
|---|---|---|---|---|
| Kenya (`KE`) | KES | **Paystack** | M-Pesa, cards (Visa, Mastercard, Amex), Apple Pay | Live for Kenyan merchants, settles in KES and USD |
| International (`INT`) | USD | **Paddle** as merchant of record (fallback: Polar) | Cards, wallets, local methods | Merchant of record handles global sales tax and VAT |

Why not Stripe directly: sources indicate Stripe business accounts are not
directly available in Kenya (access is through Paystack's extended network, or an
offshore company). **Verify** on Stripe's own country page before deciding.

Paddle lists Kenya as a supported country, but payout rails to Kenyan sellers were
not confirmed in official documentation. **Verify** payout method, fees, minimum
payout and currency with Paddle before committing. Polar lists Kenya as a payout
country (via Stripe Connect Express). **Verify** the same for Polar.

### M-Pesa and recurring billing

Paystack's support material says M-Pesa cannot be used for automatic recurring
payments, while cards can. **Verify** current behaviour. Design for it:

- **Cards (KES or USD):** automatic renewal through provider subscriptions.
- **M-Pesa in Kenya:** `renewal_mode = manual_mpesa`. Each period is prepaid. Three days before expiry the user gets an email, Telegram message and in-app prompt with a one-tap M-Pesa STK push. If unpaid, the subscription moves to `past_due` with a grace period, then back to Free. Nothing is lost.
- **Later:** Safaricom's Daraja M-Pesa Ratiba (standing orders) can enable true M-Pesa auto-renew. It is a commercial API that needs Safaricom approval and a paybill or till. Revisit when Kenyan volume justifies it.

### Regional pricing

- A **price book**: `plan` x `region` x `interval` -> `price` (amount in minor units, currency, provider price id, effective dates). Kenya has its own prices in KES. Prices are never computed by converting a USD figure at runtime.
- Prices are versioned. A change creates a new row with `active_from`; existing subscribers keep their price until they change plan (grandfathering is a policy flag).
- Admins edit prices in the admin panel (finance permission, audited). Publishing creates or syncs the provider price object.
- Price levels are business decisions still to be made. Suggested approach to test: set Kenya prices from local willingness to pay and the M-Pesa fee structure, not by currency conversion, and compare conversion per region.
- Abuse control: region is set from the billing country and payment method country. A user cannot get Kenyan pricing with an international card.

### Checkout and subscription flow

```mermaid
sequenceDiagram
  participant U as User
  participant W as Web app
  participant A as Server
  participant P as Payment provider
  participant D as Database
  U->>W: Choose plan on /plans
  W->>A: POST /v1/billing/checkout (plan, interval)
  A->>D: Resolve region and price
  A->>P: Create checkout session (price, user ref)
  P-->>A: Checkout URL
  A-->>W: URL
  W->>P: Redirect, user pays (M-Pesa or card)
  P-->>U: Receipt
  P->>A: Webhook payment.succeeded (signed)
  A->>D: Store billing_event (unique id)
  A->>D: Upsert subscription, payment, invoice
  A->>D: Recompute entitlement and credits
  A-->>P: 200 OK
  U->>W: Return to app
  W->>A: GET /v1/me/entitlement
  A-->>W: Pro, credits reset
```

### Entitlements and credits

- `entitlement` is derived state: plan features, credit balance and quotas for the current period.
- Credits are consumed by AI workflows (see `ai-workflows.md`); every call writes a `usage_event`. Cached results cost nothing.
- Credits reset at period start. Unused credits do not roll over (policy, adjustable).
- Free plan has fixed quotas (for example a daily job-match cap). Limits are hypotheses to test.
- If a webhook is missed, an hourly reconciliation job compares provider state with ours and repairs drift.

### Dunning, pauses, refunds, cancellation

- Failed card renewals: retry per provider schedule, email the user, `past_due` with a grace period, then downgrade.
- Pause for up to two months: keeps profile and history, suspends paid features.
- Cancel any time: access continues to period end. Refunds follow the published policy and are issued by finance staff from the admin panel through the provider, with an audit row.
- Invoices: we issue Kenyan invoices for Paystack payments (with VAT when registered); the merchant of record issues international invoices.

### Tax

Kenya VAT on digital services and KRA registration obligations apply to Kenyan
sales. **Verify** thresholds and filing duties with an accountant. The merchant
of record handles international sales tax and VAT.

## 8. Localisation

Localisation covers language, currency, payment methods, tax, time and email.

| Concern | Approach |
|---|---|
| UI language | i18n framework with message catalogs. English first, Swahili next. Keys from day one, no hard-coded copy |
| Region vs language | Independent settings: a user in Kenya can use English or Swahili; language never changes the price |
| Currency | Region sets the currency (KES, USD). All amounts formatted with `Intl.NumberFormat` using the user's locale |
| Prices | Region-specific price book (section 7), not currency conversion |
| Payment methods | Region decides what checkout shows: M-Pesa and cards in Kenya, cards and wallets internationally |
| Tax | Tax rate and inclusive or exclusive display come from the region record |
| Time | Timezone stored per user. Default `Africa/Nairobi` for Kenya. The daily digest and reminders send at local time |
| Email and Telegram | Templates per locale, with an English fallback |
| Job data | Salaries and locations keep their original currency. Display conversion is informational only |
| Legal | Terms, privacy policy and invoice wording per region |

## 9. Email service

**Waitlist mail (feature 28a):** `web/src/server/mail.ts` defines `EmailProvider` with a Resend implementation (one `fetch` call, no SDK) and a console provider for local development. Waitlist emails use double opt-in with `List-Unsubscribe`.

**Choice: Resend first** (free tier, transactional email, behind the `EmailProvider`
interface). Postmark or another provider can take over inbound support mail and
broadcast later, with separate streams for transactional and broadcast mail.

- Why: strong deliverability record, simple inbound parsing (needed for the support inbox), clear bounce and spam handling. Sources agree Postmark leads on deliverability and inbound, Resend on developer experience, and Amazon SES on cost at high volume. Resend may lack inbound parsing (**Verify**).
- Cost note: Postmark is priced higher per message than SES. At our early volume the difference is small. Revisit SES if volume grows past what justifies the premium.
- Behind `EmailProvider`, so a switch to SES or Resend is contained.

| Email | Stream | Examples |
|---|---|---|
| Account | Transactional | Verification and reset (if sent by us), welcome |
| Billing | Transactional | Receipt, renewal reminder, M-Pesa renewal prompt, failed payment |
| Product | Transactional | Daily digest, strong-fit alert, ghost-watch nudge |
| Support | Transactional and inbound | Ticket confirmation, staff replies, inbound to `support@` |
| Marketing | Broadcast | Waitlist and product updates, with one-click unsubscribe and consent check |

Setup: dedicated sending domain with SPF, DKIM and DMARC; webhooks for bounces,
spam complaints and delivery update `email_log` and suppress bad addresses.

## 10. Notifications

- Channels: in-app, Telegram bot, email. Each user chooses channels and quiet hours.
- A notification is created once, then delivered per channel by worker jobs with retries.
- Telegram: users link their account with a one-time code. The digest sends at local 07:30.
- Marketing consent is separate from product notifications.

## 11. AI gateway

Summarised here; full map in `ai-workflows.md`. One interface for all model
calls. Task name selects model and prompt (cheap model for screening, strong
model for evaluation and drafting), prompts are versioned, outputs validated
against schemas, results cached by content hash, and every call writes a
`usage_event` with cost. Dealbreaker gates and caching run before any model call.

Code: the gateway lives in the Python engine (`engine/src/engine/ai/`, feature 31); the
earlier TypeScript version and its two tables were removed. Entry point `run_task(task, input,
user_id=..., database=...)` with two model tiers set by `AI_CHEAP_MODEL` and `AI_STRONG_MODEL`
(`provider/model-id`), the DeepSeek, Moonshot and OpenRouter providers over one
OpenAI-compatible adapter (httpx), task definitions with a prompt `version` and Pydantic input
and output models, a per-user cache (`engine.ai_cache`), and a ledger (`engine.usage_event`)
that never stores prompt or output text. The first task, CV parsing (feature 3b), is reached
through the CV routes below. Credits and spend caps arrive with billing (feature 16).

## 12. Admin panel and support desk

Part of the same web app under `/admin`, backed by the `admin` and `support`
modules. Staff only, MFA required, every action audited.

### Admin areas

| Area | What staff can do | Permission |
|---|---|---|
| Overview | Signups, active users, MRR by currency, AI cost against revenue, queue and webhook health | `overview.read` |
| Users | Search, view profile summary and plan, adjust credits (with reason), suspend or restore, start data export or deletion | `users.read`, `users.write` |
| Subscriptions | See status and payments, retry, pause, extend, refund through the provider | `billing.read`, `billing.refund` |
| Pricing and regions | Edit the price book, regions, currencies, payment methods, tax rates, effective dates | `pricing.write` |
| Support inbox | Read, assign, reply, add internal notes, tag, use canned replies, solve tickets | `tickets.*` |
| Job sources | Adapter health, last run, errors, run now, disable | `jobs.write` |
| AI and costs | Cost per workflow and per user, model routing, kill switches, prompt versions | `ai.write` |
| Feature flags and announcements | Roll out features by plan, region or percentage; banner messages | `flags.write` |
| Operations | Failed background jobs, webhook failures, email bounces, replay events | `ops.write` |
| Audit log | Search who did what, when and why | `audit.read` |

### Support desk

```mermaid
flowchart LR
  A[User emails support@] --> B[Postmark inbound webhook]
  C[User uses in-app help form] --> D[POST support ticket]
  B --> E[Create or update ticket]
  D --> E
  E --> F[Admin inbox]
  F --> G[Staff reply or internal note]
  G --> H[Postmark outbound with thread headers]
  H --> I[User inbox]
  I --> B
```

- Tickets link to the user, plan and recent billing events so staff see context without hunting.
- Replies keep the email thread (Message-Id, In-Reply-To). Internal notes never leave the system.
- Canned replies support localisation. First-response and resolution times are tracked.
- A support provider (Crisp or Help Scout) is the alternative if the in-house inbox outgrows its value. The `support` module keeps that option open.

### Safeguards

- **Least privilege:** support staff cannot refund or change prices.
- **View as user:** read-only, requires a ticket reference, time-limited, and is audited. Staff never see passwords or payment credentials, and CV text is shown only when the ticket needs it.
- **Dual control (optional):** refunds above a threshold need a second approver.
- The audit log is append-only.

## 13. Data, tenancy, security and privacy

- **Tenancy:** row-level `user_id` scoping in the repository layer, plus Postgres Row Level Security as defence in depth. See `database-design.md`.
- **Storage:** private bucket, signed URLs with short expiry, virus scan on upload, file type and size limits.
- **Secrets:** environment variables per environment, never in code or logs. Rotate provider keys on schedule.
- **Transport and web:** HTTPS only, secure cookies, CSRF protection for cookie sessions, strict CORS, security headers, rate limits per user and IP.
- **Webhooks:** verify signatures, reject replays, process idempotently.
- **PII in logs:** none. Logs carry ids and request ids, not CV text or contact details.
- **AI data handling:** prompts contain only the user's own data, no other user's. Provider settings must opt out of training on our data. Record this in the provider contract.
- **Privacy law:** Kenya Data Protection Act applies to Kenyan users (registration with the Office of the Data Protection Commissioner as a data controller or processor may be required) and GDPR to EU users. **Verify** with a lawyer. Required product features: consent records, export, deletion, clear privacy policy.
- **Backups:** automated daily database backups, point-in-time recovery if the host offers it, and a restore drill before launch.
- **Admin hardening:** MFA, role separation, audit, optional IP allow-list.

## 14. Observability and operations

- Structured JSON logs with request id and user id (no personal text).
- Error tracking (Sentry or equivalent) for the app and the worker.
- Metrics: request latency, job queue depth and age, webhook failures, AI cost per workflow, email bounce rate, payment success rate by region and method.
- Alerts: failed webhooks, stuck queue, error spike, AI daily spend over budget.
- Health: `GET /healthz` (process) and `GET /readyz` (database, storage).

## 15. Environments, hosting and deployment

**Target: about 100 users within a couple of months, at the lowest sensible cost, with a clear path to grow.**

### Recommendation for the first 100 users

Run everything on **one small virtual server** with Docker Compose, put Cloudflare in front, and keep files and backups off the box.

| Piece | Choice | Why |
|---|---|---|
| Compute | One VPS, 2 vCPU, 4 GB RAM, 40 GB or more disk, running Caddy (automatic HTTPS), `web`, `worker` and PostgreSQL | One bill, one place to debug, no per-service minimums |
| Edge | Cloudflare free plan for DNS, caching of static files, DDoS protection | Free, and shields the single server |
| Files and backups | S3-compatible object storage (Cloudflare R2 or Backblaze B2) | Pennies at our size. **Verify** current free tier and fees |
| Database backups | Nightly encrypted `pg_dump` to object storage, plus the VPS provider's weekly snapshot, and a restore drill before launch | Cheap and testable |
| Deploys | CI builds images, pushes them to a registry, then `docker compose pull && up -d` over SSH (Kamal or Dokploy are alternatives) | Simple, repeatable, no platform lock-in |
| Monitoring | Sentry free tier, an uptime check, Docker logs with rotation | $0 to start |
| Region | A provider region closest to Kenya that fits the budget. Expect roughly 150 to 200 ms to Europe, which is acceptable for this app. **Verify** with a latency test | Africa regions cost more |

**VPS provider.** Candidates are Hetzner (cheapest per spec, but sources report 2026
price rises and uneven stock, **Verify** on their site), DigitalOcean, Vultr and Akamai
Linode (slightly dearer, steadier availability), and AWS Lightsail in Cape Town (best
latency to Kenya, dearer). Pick on price, stock and latency on the day. The design has
no provider-specific parts, so moving later is a redeploy.

**Why not a managed platform first.** Render, Fly.io and Railway remove server work,
but one comparison puts a small app with Postgres at roughly 35 to 65 US dollars a
month, about two to three times the VPS route. They are a fair choice if your time
is worth more than the difference. Managed Postgres is the usual first thing to buy
later (stage 2).

**What the single server handles.** 100 registered users is perhaps 30 to 60 active in
a week. That is a few requests a second at peak. Job discovery is shared across
users, so it grows with sources, not users. The slow part is AI calls, which wait on
the provider and use little CPU. We expect low CPU use on a 2 vCPU server (**Verify**
with a short load test before launch).

**Production layout (feature 28b).** The app is built with Nitro for plain Node
(`.output/server/index.mjs`) and shipped as a multi-stage Docker image that runs as a
non-root user and applies Drizzle migrations before the server starts. `deploy/` holds
the production Compose file (db, web, Caddy; only Caddy publishes ports), the Caddyfile
(automatic HTTPS, security headers, an optional Cloudflare-only guard), nightly
encrypted backups to object storage with a restore script, and `deploy.sh`, which
builds, waits for health and rolls back on failure. `docs/deploy.md` is the runbook.
`TRUST_PROXY_HEADERS=true` (the waitlist rate limit trusts `cf-connecting-ip`) is only
allowed together with `CLOUDFLARE_ONLY=true`, so a visitor cannot spoof the header.

### Environments

- Local: `docker compose`. Staging: a second small VPS or the same one on another port set, with provider test modes. Production: the VPS above.
- Config only through environment variables. Secrets never enter the repository or logs.
- Config names: `DATABASE_URL`, `STORAGE_*`, `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `PAYSTACK_SECRET_KEY`, `PADDLE_API_KEY`, `RESEND_API_KEY`, `MAIL_FROM`, `TELEGRAM_BOT_TOKEN`, `STORAGE_PUBLIC_ENDPOINT`, `STORAGE_REGION`, `ENGINE_URL`, `ENGINE_TOKEN`, `AI_CHEAP_MODEL`, `AI_STRONG_MODEL`, `AI_CHEAP_PRICE`, `AI_STRONG_PRICE`, `DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY`, `OPENROUTER_API_KEY`, `SENTRY_DSN`.
- CI: lint, type check, tests, build; migrations run before the app starts; deploy on merge to main with a manual production gate.

## 16. Cost and scaling plan

### Monthly cost at about 100 users (estimates, US dollars)

| Item | Estimate | Notes |
|---|---|---|
| VPS | 5 to 20 | Provider and size dependent. **Verify** |
| Object storage and backups | 0 to 2 | R2 or B2 |
| Email (Resend) | 0 to 20 | Free tier covers early volume. **Verify** current limits and paid plans |
| Authentication | 0 | Better Auth is open source |
| Error tracking and uptime | 0 | Free tiers |
| Domain | about 1 | Per month equivalent |
| Telegram | 0 | |
| Payment fees | percentage of revenue | Paystack and the merchant of record charge per transaction. **Verify** rates |
| **Fixed total** | **about 10 to 40** | |
| AI inference | variable, the largest cost | Depends on credits used. Budget per user and per plan |

**AI cost control is the real cost lever.** Credits cap what each user can spend.
Dealbreaker gates and cached results run before any model call, a cheap model
screens, the strong model only handles shortlisted jobs, and research per evaluation
is capped. Plan prices should keep AI cost at a small share of revenue (a target of
25 to 30 percent is a hypothesis to test). The admin overview shows AI cost against
revenue from day one, with a daily spend alert and a kill switch.

### Scaling path

Scale in steps, triggered by measurements, not by user counts alone.

| Stage | Roughly | Setup | Typical added cost |
|---|---|---|---|
| 0 | up to 300 users | One VPS as above | baseline |
| 1 | 300 to 2,000 | Bigger VPS, or move PostgreSQL to its own server or a managed instance with point-in-time recovery, add PgBouncer | modest |
| 2 | 2,000 to 10,000 | Two `web` nodes behind a load balancer, a separate `worker` node, managed Postgres with a standby, Redis only if the queue needs it | noticeable |
| 3 | 10,000 and up | Read replica, a queue service, regional edge, autoscaling or Kubernetes only if the team and load justify it | significant |

| Signal | Threshold (starting point) | Action |
|---|---|---|
| CPU or memory | over 60 percent CPU or 75 percent memory sustained | Move up a server size |
| Database | over half the disk, or connections near the limit | Separate database server, add PgBouncer |
| Latency | Server p95 over 800 ms | Profile first, then add a node |
| Queue | oldest waiting job over 5 minutes | Move the worker to its own node, raise concurrency |
| Availability | deploys or restarts visible to users | Second app node behind a load balancer |
| AI spend | over daily budget | Tighten credits and caching, route more work to the cheap model |

**Why this scales without a rewrite.** `web` is stateless (sessions live in
the database, files in object storage), the worker pulls jobs from a table so more
workers can share it, everything runs in containers configured by environment
variables, and every provider is behind an interface.

## 17. Decisions and open questions

| Decision | Choice | Status |
|---|---|---|
| Architecture | Modular monolith, one worker process | Decided |
| Stack | Hybrid: TanStack Start, Drizzle, Better Auth and Vitest for the web app; Python FastAPI, SQLAlchemy, Alembic and pytest for the AI engine (revised 2026-11-08) | Decided |
| Auth | Better Auth in the web server, sessions read by server functions, behind `AuthProvider` | Decided |
| Email | Resend first behind `EmailProvider`; Postmark or similar later for inbound and broadcast | Proposed |
| Kenya billing | Paystack (cards auto-renew, M-Pesa prepaid with renewal prompt) | Proposed. **Verify** M-Pesa recurring |
| International billing | Paddle as merchant of record, Polar as fallback | Proposed. **Verify** Kenyan payout |
| Support desk | In-house in the admin panel, inbound email provider chosen later | Proposed |
| Languages | English first, Swahili next | Proposed |
| Pricing levels | Kenya and international prices | Open: business decision |
| Hosting | One VPS with Docker Compose and Cloudflare to start (section 15), scale by stages (section 16) | Proposed. Pick provider and region on price, stock and latency |
| Company and tax setup (VAT, KRA, ODPC) | Needs accountant and lawyer | Open |

## 18. Impact on the build plan

New or expanded work (added to `blueprint/build-plan.md`):

- Foundation: Better Auth in the web server, the `AuthProvider` session interface, staff roles and the audit log skeleton.
- Billing and entitlements: regional price book, Paystack and Paddle providers, webhooks, entitlements, M-Pesa renewal prompts, dunning, invoices.
- Localisation: i18n catalogs, locale and timezone settings, regional formatting.
- Email: Resend provider, templates, bounce handling, inbound support.
- Admin panel and support desk.
