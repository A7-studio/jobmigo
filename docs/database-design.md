# Jobmigo database design

PostgreSQL, SQLAlchemy 2.x models, Alembic migrations. This document is the
design of record for how data is stored. Field lists are the starting point; the
feature that first uses a table locks its final shape in its spec.

## Conventions

- Primary keys are UUIDs (`id`). Every table has `created_at`; mutable tables also have `updated_at`.
- **Tenant data** (anything derived from a user's CV, preferences, applications or payments) carries `user_id` and is always queried through the owner-scoping helper. **Shared data** (`company`, `job`, `job_listing`, `job_source`, `plan`, `price`) has no `user_id`.
- Defence in depth: Row Level Security is enabled on tenant tables. The API sets `app.user_id` per request; the admin role bypasses it only through the audited admin module.
- Money is stored as integer minor units (`amount_minor`) with an ISO `currency` code. Never floats.
- Enums are Postgres enums or text with check constraints, defined once in the owning module.
- Soft delete only where history matters (`user.status`, `application`). User deletion is a real purge job that removes tenant rows and storage objects.
- No card or mobile-money credentials are stored. Only provider references (customer id, subscription id, payment reference).
- Personal text (CV text, drafts) is never written to logs or analytics.
- Indexes: every foreign key; `(user_id, created_at)` on tenant lists; `job.dedupe_key` unique-ish; `billing_event.provider_event_id` unique for idempotency.

## 1. Identity and access

Sign-in is handled by Better Auth in the web server. It owns five tables, created by Alembic like the rest: `auth_user`, `auth_session`, `auth_account`, `auth_verification` and `auth_jwks` (signing keys). The API never reads them. It trusts a signed token, and `user.auth_subject` holds the Better Auth user id.

```mermaid
erDiagram
  USER ||--o{ CONSENT : gives
  USER ||--o{ DATA_REQUEST : files
  USER ||--o| STAFF_MEMBER : "may be"
  STAFF_MEMBER }o--|| ROLE : has
  ROLE ||--o{ ROLE_PERMISSION : grants
  USER {
    uuid id PK
    text auth_subject UK "Better Auth user id"
    text email UK
    text display_name
    text country "ISO 3166, from billing or choice"
    text locale "en, sw"
    text timezone "Africa/Nairobi"
    text currency "KES, USD"
    text status "active, suspended, deleted"
    text telegram_chat_id
    timestamptz created_at
  }
  CONSENT {
    uuid id PK
    uuid user_id FK
    text kind "terms, privacy, marketing"
    text version
    timestamptz at
  }
  DATA_REQUEST {
    uuid id PK
    uuid user_id FK
    text kind "export, delete"
    text status "pending, running, done"
    timestamptz requested_at
  }
  STAFF_MEMBER {
    uuid user_id PK
    uuid role_id FK
    bool mfa_enforced
  }
  ROLE {
    uuid id PK
    text name "support, finance, admin, owner"
  }
  ROLE_PERMISSION {
    uuid role_id FK
    text permission "users.read, billing.refund"
  }
```

## 2. Profile and tracks

```mermaid
erDiagram
  USER ||--o{ CV_FILE : uploads
  USER ||--|| PROFILE : owns
  CV_FILE ||--o| PROFILE : "source of"
  PROFILE ||--o{ EXPERIENCE : has
  PROFILE ||--o{ SKILL : has
  PROFILE ||--o{ PROJECT : has
  PROFILE ||--o{ EDUCATION : has
  EXPERIENCE ||--o{ ACHIEVEMENT : has
  USER ||--o{ TRACK : defines
  TRACK ||--o{ TRACK_PROFILE_ITEM : emphasises
  CV_FILE {
    uuid id PK
    uuid user_id FK
    text storage_key "private object"
    text mime "pdf, docx"
    text parse_status
    text extracted_text
  }
  PROFILE {
    uuid id PK
    uuid user_id FK
    text headline
    text summary
    uuid source_cv_id FK
  }
  EXPERIENCE {
    uuid id PK
    uuid profile_id FK
    text company
    text role
    date start_date
    date end_date
    jsonb bullets
    text status "extracted, confirmed, edited"
  }
  SKILL {
    uuid id PK
    uuid profile_id FK
    text name
    bool used_in_role
    text status
  }
  TRACK {
    uuid id PK
    uuid user_id FK
    text name
    int variant_version
    text_array target_roles
    int salary_floor
    text currency
    text work_mode
    text_array locations
    text eligibility
    jsonb criteria "must, important, nice"
    jsonb dealbreakers
    text_array do_not_apply
  }
```

Rule: generated documents and evaluations may only cite rows whose `status` is `confirmed` or `edited`.

## 3. Jobs, evaluation and documents

```mermaid
erDiagram
  JOB_SOURCE ||--o{ JOB_LISTING : yields
  COMPANY ||--o{ JOB : posts
  JOB ||--o{ JOB_LISTING : "merged from"
  JOB ||--o{ USER_JOB : "seen by"
  USER ||--o{ USER_JOB : has
  TRACK ||--o{ USER_JOB : "matched to"
  USER_JOB ||--o{ EVALUATION : "evaluated as"
  USER_JOB ||--o{ DOCUMENT : "prepared for"
  DOCUMENT ||--o{ REACHABILITY_CHECK : "checked by"
  JOB_SOURCE {
    uuid id PK
    text kind "career_page, api"
    text adapter
    text base_url
    bool active
    timestamptz last_run_at
    text last_status
  }
  COMPANY {
    uuid id PK
    text name
    text domain
    text careers_url
  }
  JOB {
    uuid id PK
    uuid company_id FK
    text title
    text description
    text location
    text remote_policy
    int salary_min
    int salary_max
    text currency
    text dedupe_key "normalised URL, company+role fallback"
    text legitimacy "high, caution, suspicious"
    jsonb legitimacy_notes
    jsonb requirements
    text status "live, expired, unverified"
    timestamptz posted_at
    timestamptz last_verified_at
  }
  JOB_LISTING {
    uuid id PK
    uuid job_id FK
    uuid source_id FK
    text url
    text external_id
  }
  USER_JOB {
    uuid id PK
    uuid user_id FK
    uuid job_id FK
    uuid track_id FK
    text state "new, saved, dismissed, skipped"
    date recheck_after
    text skip_reason
    jsonb screen_result
  }
  EVALUATION {
    uuid id PK
    uuid user_job_id FK
    text band "strong, good, stretch, poor"
    jsonb requirements "need, status, quote, evidence_ref"
    jsonb checks
    text cache_key "content hash"
    text prompt_version
    uuid usage_event_id FK
  }
  DOCUMENT {
    uuid id PK
    uuid user_id FK
    uuid user_job_id FK
    text kind "cv, cover_letter, answers"
    int version
    jsonb content
    jsonb fact_check
    text storage_key
  }
  REACHABILITY_CHECK {
    uuid id PK
    uuid document_id FK
    jsonb items "check, status pass or fix, detail"
    jsonb keyword_coverage
    text prompt_version
  }
```

## 4. Applications, outreach and progress

```mermaid
erDiagram
  USER_JOB ||--o| APPLICATION : "becomes"
  APPLICATION ||--o{ STAGE_EVENT : logs
  APPLICATION ||--o{ INTERVIEW : has
  APPLICATION ||--o{ FOLLOW_UP : schedules
  COMPANY ||--o{ CONTACT : "has public"
  USER ||--o{ OUTREACH : drafts
  CONTACT ||--o{ OUTREACH : "addressed in"
  USER ||--o{ PROGRESS_EVENT : earns
  USER ||--o{ BADGE : earns
  APPLICATION {
    uuid id PK
    uuid user_id FK
    uuid user_job_id FK
    text stage "saved, preparing, applied, interviewing, offer, closed"
    timestamptz applied_at
    timestamptz last_activity_at "drives ghost watch"
    text notes
    text outcome
  }
  STAGE_EVENT {
    uuid id PK
    uuid application_id FK
    text stage
    timestamptz at
  }
  FOLLOW_UP {
    uuid id PK
    uuid application_id FK
    timestamptz due_at
    timestamptz done_at
  }
  CONTACT {
    uuid id PK
    uuid company_id FK
    text name
    text role
    text public_source_url
  }
  OUTREACH {
    uuid id PK
    uuid user_id FK
    uuid contact_id FK
    uuid user_job_id FK
    text draft
    text status "draft, sent, replied"
    timestamptz sent_at
  }
  PROGRESS_EVENT {
    uuid id PK
    uuid user_id FK
    text kind "quest, follow_up, application, review"
    int xp
    timestamptz at
  }
  BADGE {
    uuid user_id FK
    text key
    timestamptz earned_at
  }
```

## 5. Billing, pricing and usage

Provider-neutral. Two rails behind one interface: Paystack (Kenya, KES) and a
merchant of record such as Paddle (international, USD). See the technical design.

```mermaid
erDiagram
  PLAN ||--o{ PRICE : "priced by"
  REGION ||--o{ PRICE : "applies in"
  USER ||--o{ SUBSCRIPTION : holds
  PLAN ||--o{ SUBSCRIPTION : "subscribed to"
  PRICE ||--o{ SUBSCRIPTION : "billed at"
  SUBSCRIPTION ||--o{ PAYMENT : "paid by"
  PAYMENT ||--o| INVOICE : "documented by"
  USER ||--|| ENTITLEMENT : receives
  USER ||--o{ USAGE_EVENT : incurs
  USER ||--o{ CREDIT_ADJUSTMENT : "adjusted by staff"
  BILLING_EVENT }o--o| SUBSCRIPTION : "updates"
  PLAN {
    uuid id PK
    text key "free, pro, power"
    jsonb features
    int credits_per_period
    jsonb quotas "evaluations, tailoring, outreach"
  }
  REGION {
    text code PK "KE, INT"
    text currency "KES, USD"
    text provider "paystack, paddle"
    jsonb payment_methods "mpesa, card"
    numeric tax_rate
    bool tax_inclusive
  }
  PRICE {
    uuid id PK
    uuid plan_id FK
    text region_code FK
    text interval "month, quarter, year"
    int amount_minor
    text currency
    text provider_price_id
    timestamptz active_from
    timestamptz active_to
  }
  SUBSCRIPTION {
    uuid id PK
    uuid user_id FK
    uuid plan_id FK
    uuid price_id FK
    text provider "paystack, paddle"
    text provider_customer_id
    text provider_subscription_id
    text status "trialing, active, past_due, paused, cancelled"
    timestamptz current_period_end
    timestamptz cancel_at
    timestamptz pause_until
    text renewal_mode "auto, manual_mpesa"
  }
  PAYMENT {
    uuid id PK
    uuid subscription_id FK
    text provider_reference UK
    int amount_minor
    text currency
    text method "card, mpesa, apple_pay"
    text status
    timestamptz paid_at
  }
  INVOICE {
    uuid id PK
    uuid payment_id FK
    text number
    int tax_minor
    numeric tax_rate
    text pdf_storage_key
  }
  ENTITLEMENT {
    uuid user_id PK
    text plan_key
    int credits_total
    int credits_used
    jsonb quotas_used
    timestamptz period_end
  }
  USAGE_EVENT {
    uuid id PK
    uuid user_id FK
    text workflow "parse, screen, evaluate, tailor, reach_check, outreach"
    text provider
    text model
    text prompt_version
    int tokens_in
    int tokens_out
    numeric cost_usd
    bool cache_hit
    timestamptz created_at
  }
  CREDIT_ADJUSTMENT {
    uuid id PK
    uuid user_id FK
    uuid staff_id FK
    int delta
    text reason
  }
  BILLING_EVENT {
    uuid id PK
    text provider
    text provider_event_id UK "idempotency"
    jsonb payload
    text status "received, processed, failed"
    timestamptz received_at
  }
```

`entitlement` is derived state: it is recomputed from `subscription` and
`credit_adjustment` whenever a billing event is processed, so a missed webhook
can always be repaired by replaying `billing_event`.

## 6. Support, notifications and operations

```mermaid
erDiagram
  USER ||--o{ SUPPORT_TICKET : opens
  SUPPORT_TICKET ||--o{ TICKET_MESSAGE : contains
  SUPPORT_TICKET }o--o| STAFF_MEMBER : "assigned to"
  SUPPORT_TICKET }o--o{ TICKET_TAG : tagged
  STAFF_MEMBER ||--o{ AUDIT_LOG : performs
  USER ||--o{ NOTIFICATION : receives
  USER ||--o{ EMAIL_LOG : "emailed"
  SUPPORT_TICKET {
    uuid id PK
    uuid user_id FK "nullable for unknown senders"
    text requester_email
    text subject
    text status "new, open, waiting, solved"
    text priority
    uuid assignee_id FK
    text channel "email, in_app"
    timestamptz first_response_at
    timestamptz created_at
  }
  TICKET_MESSAGE {
    uuid id PK
    uuid ticket_id FK
    text direction "inbound, outbound, internal_note"
    text body
    text email_message_id "threading"
    uuid author_staff_id FK
    timestamptz at
  }
  AUDIT_LOG {
    uuid id PK
    uuid staff_id FK
    text action "user.suspend, billing.refund"
    text target_type
    uuid target_id
    jsonb before
    jsonb after
    text reason
    text ip
    timestamptz at
  }
  NOTIFICATION {
    uuid id PK
    uuid user_id FK
    text kind
    text channel "app, telegram, email"
    jsonb payload
    timestamptz sent_at
    timestamptz read_at
  }
  EMAIL_LOG {
    uuid id PK
    uuid user_id FK
    text template
    text locale
    text provider_message_id
    text status "sent, delivered, bounced, complained"
    timestamptz at
  }
  FEATURE_FLAG {
    text key PK
    bool enabled
    jsonb rules "percent, plans, regions"
  }
  ANNOUNCEMENT {
    uuid id PK
    text body
    text audience
    timestamptz starts_at
    timestamptz ends_at
  }
  BACKGROUND_JOB {
    uuid id PK
    text kind
    jsonb payload
    text status
    int attempts
    timestamptz run_at
    text idempotency_key UK
  }
```

`audit_log` is append-only (no updates or deletes, enforced by permissions and a
trigger). Every staff action that reads or changes a user's data writes a row.

## Storage map

| Data | Where | Notes |
|---|---|---|
| Structured data | PostgreSQL | One database, schema per module is optional |
| CV files, exported documents, invoice PDFs | Private S3-compatible bucket | Signed URLs, short expiry |
| Cache of AI results | PostgreSQL (`evaluation.cache_key`, document versions) | Keyed by content hash |
| Job queue | PostgreSQL `background_job` | Redis only if volume demands it |
| Sessions, credentials and signing keys | `auth_*` tables (Better Auth, in our PostgreSQL) | Application `user` stores `auth_subject` and email only |
| Card and M-Pesa credentials | Payment providers | Never stored by Jobmigo |
| Raw inbound support emails | Provider and `ticket_message` | Attachments in the private bucket |

## Retention and deletion

- Account deletion purges all tenant rows and storage objects within a defined window and keeps only what law requires (for example invoices and tax records, de-identified where possible).
- Data export produces a downloadable archive of the user's own rows and files.
- `billing_event` payloads and `email_log` are pruned after a retention period. `audit_log` is kept longer.
- Support tickets are retained for a set period after resolution, then anonymised.
