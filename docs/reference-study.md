# Reference study: Jobmate, Career-Ops, Aarivi

Studied 2026-11-06 for Jobmigo planning. Every claim carries an evidence tag
(the tagging habit comes from the REA casebook approach).

- **[Open source]** read directly from public source code
- **[Public page]** stated on the product's own public website
- **[Unverified]** a marketing claim we could not check
- **[Not seen]** the source did not show it, so we do not assume it

## Method and limits

The REA list (awesome-reverse-engineer-anything) describes agents that inspect
binaries, apps and sites with tools like Ghidra and JADX, and write conclusions
tied to recorded evidence. For this study we use only its evidence discipline.

- **Career-Ops** is MIT-licensed open source, so reading its code is fair game.
- **Jobmate and Aarivi** are closed commercial products. We studied their public
  pages only. We did not decompile or intercept their apps, extension or
  traffic: that would likely breach their terms, and the plan does not need it.
- The REA tool itself was not installed. If you want to run it on anything, it
  should be software you own or have rights to inspect.
- Career-Ops: code under MIT (keep the copyright notice if code is copied), but
  its name is reserved for community use only. Borrow ideas, do not reuse the
  brand.

## Career-Ops (engineering leverage)

Local, CLI-driven tool: Markdown "mode" prompts plus Node scripts. Not a hosted
service.

| Area | What it does | Evidence |
|---|---|---|
| Ingestion | `scan.mjs` reads a user `portals.yml`; 55+ provider modules (ATS APIs, feeds, local parsers). Provider contract: `id`, optional `detect(entry)`, `fetch(entry, ctx)` returning title, url, company, location, optional postedAt/description/salary | [Open source] |
| Rate control | 32 concurrent globally, 10 per host, cached HTTP with TTL, jittered throttle for browser checks | [Open source] |
| Dedupe | URL key from `normalizeUrlForDedup` (strip tracking params, hash, trailing slash, lowercase path); history table with permanent vs observational skip statuses and a recheck-after-days release; company+role key with optional location/language | [Open source] |
| Filters | Title include/exclude keywords, location allow/block, age, visa, country, experience, salary | [Open source] |
| Verification | API liveness pass, Playwright fallback only when inconclusive, only on new offers | [Open source] |
| Legitimacy | Posting-legitimacy block reports observations, not verdicts: tiers High Confidence / Proceed with Caution / Suspicious; repost detector for ghost jobs; does not change the numeric score | [Open source] |
| Evaluation | Gates first (liveness, user blacklist, user dealbreakers, agency check, 5-search research budget), then blocks A-H. CV match is a requirement-to-evidence table; JD is read before the CV so importance is set before fit; inferred importance can never be "critical" or "high"; capped at 12 rows | [Open source] |
| Score | 1-5 from five dimensions; advises against applying below 4.0 but user can override. Weights and band thresholds live in `_shared.md` | [Not seen] |
| Tailoring | CV rendered from the user's own `cv.md`; PDF generation blocks if numbers or facts are not in the sources; title-drift check | [Open source] |
| Tracker | Canonical status list with aliases and terminal flags; atomic file writes with locks | [Open source] |
| Orchestration | One router skill; batch mode runs headless worker processes | [Open source] |

**Limits for a SaaS:** single user, local files, no tenancy, no billing or cost
ledger, prompts are Markdown run by an agent CLI (not schema-validated service
calls). Its ideas transfer; its architecture does not.

## Jobmate (commercial blueprint)

Pricing page only. Early-bird prices shown with post-launch prices in brackets.

| Plan | Monthly | AI credits | Resume profiles | Auto-apply runs | Lead searches | Outreach msgs |
|---|---|---|---|---|---|---|
| Free | $0 | 20 | 2 | 2 | none | none |
| Pro | $15 ($20) | 300 | 5 | 50 | 300 | 60 |
| Max | $25 ($30) | 700 | 10 | 100 | 500 | 150 |
| Ultra | $45 ($50) | 1,500 | 20 | 300 | unlimited | 300 |

- [Public page] Application tracking, interviews, tasks and saved jobs are
  unlimited on every tier, including free.
- [Public page] Gating is by several separate quotas, not one credit pool.
  Quarterly saves 11%, annual is "2 months free".
- [Not seen] Credits consumed per action are not published.
- [Not seen] How auto-apply or autofill work internally.

## Aarivi (journey and UX)

- [Public page] Startup-focused discovery (claims 10,000+ startups), roles scored
  against resume and GitHub.
- [Public page] Daily Gmail scan moves applications across Applied, Interview,
  Offer, Rejected automatically.
- [Public page] Drafts founder cold emails and sends from the user's Gmail after
  approval. Resume tailoring costs one credit.
- [Public page] Basic $5/mo (500 credits), Pro $8/mo (1,500 credits, HR outreach).
- [Unverified] "739 interviews landed in nine days" is unsubstantiated.
- [Not seen] Onboarding steps beyond plan selection then a chat interface.

## Jobmate sign-up and onboarding (limits of what is public)

- [Public page] Nearly every call to action leads to one sign-up page; pricing buttons pre-select a plan and billing period.
- [Public page] Free plan, no free trial mentioned; steps described in the FAQ: create a free account, add the browser extension, sign in so the profile syncs.
- [Public page] Trust cues: "200,000+ jobs" count, company and source logos, user posts, and "review or stop anything" control language. No privacy or security certifications shown.
- [Not seen] The sign-up form and any onboarding wizard are not public. We did not create an account to look.
- [Public page] No retention mechanics (streaks, goals, weekly reports) are visible.

Takeaway: a single sign-up entry, a free plan and plan pre-selection are worth copying. Jobmigo adds explicit privacy promises at the CV step, a first-value moment before any payment ask, and gentle retention mechanics.

## Adopt, improve, exclude

| Idea | Source | Decision | Why |
|---|---|---|---|
| Free, unlimited tracking on every plan | Jobmate | Adopt | Builds the daily habit; costs almost nothing to serve |
| Several metered quotas (tailoring, outreach, evaluations) beside credits | Jobmate | Adopt | Easier to explain and cap cost per workflow |
| Early-bird vs list price | Jobmate | Test | Useful for the 10-customer milestone |
| Provider adapter contract (`id`, `detect`, `fetch`) | Career-Ops | Adopt | Matches feature 6; add per-host concurrency limits |
| URL normalisation as dedupe key, plus company+role fallback | Career-Ops | Adopt | Cheap, deterministic, no AI needed |
| Skip-status memory with recheck-after-days | Career-Ops | Adopt | Stops re-surfacing dismissed jobs |
| Liveness check: API first, browser only when unclear | Career-Ops | Adopt | Saves cost; fits the verification promise |
| Posting-legitimacy tiers (ghost jobs, reposts) | Career-Ops | Adopt, improve | A visible trust feature; show observations, not verdicts |
| User dealbreakers and do-not-apply list as hard gates | Career-Ops | Adopt | Add to feature 5; stops wasted credits early |
| Importance read from the posting before judging fit; inferred importance capped | Career-Ops | Adopt | Core of "no misleading scores" |
| Research budget cap per evaluation | Career-Ops | Adopt | Direct AI cost control |
| PDF blocked unless facts exist in source | Career-Ops | Adopt | Our fact-check rule, as a hard gate |
| 1-5 numeric score | Career-Ops | Exclude | We use bands with evidence |
| Canonical status list with terminal flags | Career-Ops | Adopt | Our stages need the same rule |
| Gmail scan to auto-update status | Aarivi | Later, read-only | High value, high trust and privacy cost |
| Send emails from user's Gmail | Aarivi | Exclude | Draft, copy, mark as sent instead |
| Auto-apply / autofill | Jobmate | Exclude from MVP | Terms and trust risk; revisit only if within site terms |
| Local files and agent-CLI prompts | Career-Ops | Exclude | Not a multi-user architecture |
| Unsubstantiated outcome claims | Aarivi | Exclude | Publish only real, measured outcomes |

## Implications for the plans (applied 2026-11-06)

1. **Pricing:** the $9/$19/$39 hypotheses sit between Aarivi ($5/$8) and Jobmate
   ($15-$45). Make application tracking free and quota-limit evaluations,
   tailoring and outreach separately.
2. **Feature 5:** add dealbreakers and a do-not-apply list to job preferences.
3. **Feature 6:** specify the adapter contract, per-host limits, URL-normalised
   dedupe key, skip-status recheck, and a posting-legitimacy flag.
4. **Feature 8:** read importance from the posting first, cap inferred
   importance, cap research per evaluation, run dealbreaker gates before any
   AI call.
5. **Feature 12:** adopt a canonical status list with terminal flags.
6. **Later list:** read-only Gmail status detection.

## Not yet studied

- Career-Ops `_shared.md` scoring weights and the rest of `scan.mjs` and
  `providers/` (only the first 100k characters of `scan.mjs` were read).
- Jobmate's and Aarivi's in-app flows beyond the public pages.
