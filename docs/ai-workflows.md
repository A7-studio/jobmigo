# How AI works in Jobmigo

Goal: get the user's application out of the ghost pipeline and into an
interview. The bottleneck is the application itself: filtered out by hiring
software, buried in the pile, or sent to a job that is already dead. Jobmigo
improves the odds by targeting live jobs, making the CV reachable, and routing
it to a person. Winning the interview is the user's job. Jobmigo does not
promise or guarantee interviews.

Principle: **AI proposes, the user decides.** AI output is labelled as AI, is
based only on the user's confirmed profile and the public posting, cites its
evidence, and is never sent anywhere without the user.

Each Career-Ops capability below is a pattern we study (see
`reference-study.md`). We re-implement the idea as a multi-user, schema-validated
service, not by reusing its CLI or prompts.

## Workflow map

| Step | What the user gets | Code (no AI cost) | AI task and model tier | Career-Ops idea | Human gate |
|---|---|---|---|---|---|
| Discover | Fresh jobs from public sources | Source adapters, dedupe key, filters, schedule | Categorise and extract requirements: cheap model | `scan`, provider modules | None |
| Verify | Only live, real jobs | Liveness check, expiry, repost detection | Legitimacy observations (ghost-job signals): cheap model | liveness, legitimacy tiers | None |
| Screen | A ranked inbox | Dealbreaker and do-not-apply gates, salary and location rules | First-pass fit screen: cheap model | gates before evaluation | User sets the rules |
| Evaluate | Fit band with evidence and gaps | Cache lookup, credit check, budget cap | Requirement-to-evidence match, level and pay reading: strong model | `oferta` blocks A-G | User reads the verdict |
| Prepare | Tailored CV, cover letter, answers | Fact-check gate, ATS-readability check, PDF/DOCX render | Rewrite from confirmed facts: strong model | `pdf`, `cover`, fact check | User approves every claim |
| Reachability | A checklist of how the CV reads to hiring systems, and a route to a person | Text extraction, format and file checks, keyword diff against the posting, contact lookup | Judge title match, keyword gaps and which additions are truthful: strong model | `ATS check`, `cv-title-check` | User decides which keywords are true |
| Contact | Public contacts and drafted messages | Contact source links, send log | Personalised draft: strong model | `contacto` | User sends it themselves |
| Track | Pipeline and follow-ups | Canonical stages, reminders | None | tracker, `states.yml` | User moves stages |
| Follow up | Silent applications caught and nudged | Silence timer (10+ days), reminders | Draft the follow-up note: strong model | tracker, patterns | User sends it |

## Rules for every AI task

- **Inputs:** only confirmed profile facts and public posting text. No other user's data.
- **Outputs:** validated against a schema. One retry, then fail visibly.
- **Evidence:** every claim carries a source (profile line or posting quote) or is marked unknown. Inferred importance cannot be "critical" or "high".
- **No fake precision:** fit is a band, never a percentage.
- **Cost control:** dealbreakers and cached results run before any model call; cheap model screens, strong model only for shortlisted jobs; research capped per evaluation (for example 5 searches).
- **Ledger:** every call records workflow, model, prompt version, tokens, cost, cache hit and user.
- **Labelling:** AI-generated text is marked in the UI, with a one-click way to see what it was based on.
- **Privacy:** CV text is never logged; prompts and outputs are stored only as the user's own data.

## Where AI appears in the product

- **Homepage:** "AI job-application assistant" ("Skip the ghost pipeline. Get the interview."), with a section showing what the AI does and what the user decides at each step.
- **Dashboard:** "Ask Migo" bar (natural-language questions over the user's own jobs and applications) and ghost-watch alerts.
- **Job page:** "AI evaluation" with evidence per requirement, plus the application kit and a reachability check.
- **Application kit:** tailored CV with fact check and a reachability checklist (a checklist, not a score).
- **Applications board:** ghost watch for applications silent 10+ days.

## Out of scope for the MVP

Autonomous multi-step agents, auto-applying, interview prep and coaching (later),
AI insights dashboards (later), and any promise of outcomes.
