# Findings

> **Generated file.** The findings ledger: review findings raised by `/audit`
> against the work in progress, each with a durable ID, severity (P0-P3), and
> status. `/implement` marks repaired findings `fixed`, a later `/audit` pass
> moves them to `closed`, and `/complete` refuses to land while any P0 or P1
> finding is `open` or `fixed`, then archives resolved findings with the work
> and resets this file.

### F-04 [P2] unverified - Pre-registered unverified email plus Google sign-in could allow account pre-hijack

**File:** web/src/lib/auth.ts:26
**Found:** 2026-11-06 by /audit (scope: current; lens: security)
**Why it matters:** Email and password sign-up needs no verification (an accepted out-of-scope item until feature 24). If Google is enabled later and Better Auth links a verified Google identity to an existing unverified email-password user, whoever pre-registered that address keeps the password. Not exercised: Google is not configured and the linking behavior of the installed Better Auth version was not tested.
**Suggested fix:** Before enabling Google, or with feature 24, require email verification before sign-in, or disable implicit account linking for unverified users; confirm with a test.
**Resolution:** Feature 27 disables `account.accountLinking` in `src/lib/auth.ts:26`. Re-examined 2026-11-07 by independent review: the setting is present, but no test or live check exercises Google linking and the config is untested (see F-07). Stays unverified until Google is configured.

### F-06 [P3] open - Better Auth config (model names, `accountLinking: false`, no JWT) still has no test

**File:** web/src/server/identity.ts:57, web/src/server/permissions.ts:63, web/src/lib/auth.functions.ts:21
**Found:** 2026-11-07 by /audit (scope: current; lens: tests)
**Why it matters:** Every test injects a session object into `resolveUser`, `buildMe` or `assertPermission`. Nothing exercises `requireUser(headers)`, `requirePermission(headers, ...)`, the `getMe` server function, the Better Auth Drizzle adapter config (model names, `accountLinking: false`, no JWT), the request-id middleware (`start.ts`) or `/healthz` and `/readyz` (503 path). These carry the session-to-user trust boundary and were verified only by a one-off live check. A broken model-name mapping or a changed Better Auth default would pass the suite.
**Suggested fix:** Add one Vitest file that imports `auth` against the test database, signs up and signs in through `auth.api`, and asserts `requireUser(headers)` returns that user, a request with no cookie raises `UnauthorizedError`, and account linking is off. Add a small test for the `/readyz` handler failure shape and the middleware header.
**Resolution:** Feature 28a: `tests/wiring.test.ts` mocks Better Auth and covers `requireUser(headers)`, `requirePermission(headers, ...)`, the `getMe` path (`meFromHeaders`), the request-id function and the health and readiness handlers; the request-id test fails when its behaviour is changed.
Re-examined 2026-11-07 by independent review (a3dfe45): `requireUser`, `requirePermission`, the `getMe` path, request-id and health/readiness are now covered (the session-to-user boundary part is closed in substance). But `tests/wiring.test.ts:25` replaces `#/lib/auth` with a mock, so the Drizzle adapter model-name mapping, `accountLinking: false` and the no-JWT setting in `src/lib/auth.ts` are still exercised by nothing, which was the other half of the original finding. Reopened as P3 with that narrower scope; a test that imports the real `auth` against the test database and signs up through `auth.api` would close it.

### F-07 [P3] open - Unexpected errors and readiness failures are logged without a cause

**File:** web/src/server/errors.ts:48, web/src/routes/readyz.ts:14
**Found:** 2026-11-07 by /audit (scope: current; lens: quality)
**Why it matters:** `toResult` logs only the error class name, and `/readyz` swallows the exception with no log at all. A 500 `internal_error` or a failing readiness probe cannot be diagnosed from logs. The no-leak behaviour is correct for the client; the server log is too thin.
**Suggested fix:** Log `error.message` code-side-safe fields (for example the Postgres `code`) and a short stack, never request bodies, and log the readyz failure once at `warn`. Keep the client messages unchanged.
**Resolution:**

### F-08 [P3] open - `X-Request-Id` is trusted without length or character limits

**File:** web/src/start.ts:6
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** Any client value is echoed in the response header and written to every log line for that request. JSON encoding prevents log forging, but a very long or misleading id inflates logs and can be used to confuse tracing.
**Suggested fix:** Accept the header only when it matches a short pattern (for example `^[A-Za-z0-9._-]{1,64}$`), otherwise generate a UUID.
**Resolution:**

### F-09 [P3] open - Audit immutability trigger does not cover TRUNCATE

**File:** web/drizzle/0000_baseline.sql:132
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** `BEFORE UPDATE OR DELETE ... FOR EACH ROW` blocks row changes but `TRUNCATE audit_log` succeeds. Only a role with table privileges can run it, and the app uses one owner role, so the exposure is limited to app bugs or raw SQL.
**Suggested fix:** Add a statement-level `BEFORE TRUNCATE` trigger using the same function in a new migration, with a test.
**Resolution:**

### F-10 [P3] unverified - Per-request write and unbounded list helper may cost more than needed

**File:** web/src/server/identity.ts:30, web/src/server/ownership.ts:44
**Found:** 2026-11-07 by /audit (scope: current; lens: performance)
**Why it matters:** `resolveUser` runs an `INSERT ... ON CONFLICT DO NOTHING` on every authenticated request before selecting, and `getMe` then runs two more staff queries. `listOwned` has no limit, so a future caller on a large table returns every row. No profiling was done and there are no callers of `listOwned` yet, so this is a lead, not a defect.
**Suggested fix:** Select first and insert only on a miss (keep the conflict handling), and require a limit argument in `listOwned` when the first list feature lands.
**Resolution:**

### F-14 [P3] open - Waitlist state changes are not atomic

**File:** web/src/server/waitlist.ts:114, web/src/server/waitlist.ts:204
**Found:** 2026-11-07 by /audit (scope: current; lens: quality)
**Why it matters:** `confirmWaitlist` reads the row and then updates by `id` with no status guard, so a confirm that races an unsubscribe can overwrite `unsubscribed` with `confirmed` and the person keeps getting email after opting out. Two concurrent joins at the resend boundary both read the stale row, both send, and the first token is invalidated by the second. A send failure sets `tokenSentAt` to epoch even for a resend of a row whose previous token is already replaced, which also makes any live token read as expired. All narrow windows, none likely at waitlist volume.
**Suggested fix:** Add the expected status (and `tokenHash`) to the `WHERE` of each `UPDATE` and treat zero rows as invalid. Nothing is lost.
**Resolution:**

### F-15 [P3] open - A pending address that used its five emails or expired link has no way back

**File:** web/src/server/waitlist.ts:136
**Found:** 2026-11-07 by /audit (scope: current; lens: quality)
**Why it matters:** Re-joining sends nothing once `emailsSent` reaches 5, and the confirm page tells an expired user to "join again". Someone who never saw the earlier mails (spam folder) is told success and silently never gets a working link. Only unsubscribing (and re-joining) resets the counter.
**Suggested fix:** Reset the counter after a longer window (for example 24 hours) or when the last token has expired.
**Resolution:**

### F-16 [P3] fixed - Privacy notice does not match what is kept or loaded

**File:** web/src/routes/privacy.tsx:60, web/src/routes/__root.tsx:28
**Found:** 2026-11-07 by /audit (scope: current; lens: quality)
**Why it matters:** The notice says that after unsubscribing "we keep only your email address", but the row keeps source, consent timestamps and the token hash. Pages also load fonts from Google (`fonts.googleapis.com`), sending visitors' IP addresses to a third party that the notice does not name while it says it does not store IPs. A legal read is already an open decision; these are concrete items for it. Re-joining by anyone who knows the address also reopens an opted-out address (it only becomes pending and needs confirmation, so this is accepted by design).
**Suggested fix:** Either null the extra columns on unsubscribe, or reword the notice; self-host the fonts or mention Google Fonts.
**Resolution:** Privacy notice now names Google Fonts and the retained record (email, consent and unsubscribe dates, source tag). Pending re-review.

### F-17 [P3] open - Waitlist form accessibility gaps after submit

**File:** web/src/components/WaitlistForm.tsx:56, web/src/components/WaitlistForm.tsx:76
**Found:** 2026-11-07 by /audit (scope: current; lens: quality)
**Why it matters:** On success the form is unmounted, so keyboard focus (on the submit button) drops to the document body, and the success message is a `role="status"` node inserted already filled, which many screen readers do not announce. The form-level error container has `role="alert"` with `aria-live="polite"`, which conflict. Field errors, labels, `aria-invalid`, focus on first error and 44px targets are correct.
**Suggested fix:** Render the status container always and fill it, or move focus to the success heading (`tabIndex={-1}`); drop `aria-live` from the alert.
**Resolution:**

### F-18 [P3] fixed - Some homepage claims are in present tense for unbuilt features

**File:** web/src/components/home/Honest.tsx:12, web/src/components/home/Hero.tsx:50
**Found:** 2026-11-07 by /audit (scope: current; lens: quality)
**Why it matters:** The spec says to write claims in future wording. Most sections do ("will", "is being built", Preview labels). But "Your CV is private. Export it or delete it whenever you like." and "We never invent experience" / "Your CV stays private" describe an upload, export and delete flow and an AI that do not exist yet, with no tense or "will".
**Suggested fix:** "Your CV will be private, and you will be able to export or delete it." or similar for those lines.
**Resolution:** Homepage principles reworded in future tense; hero, section and footer copy no longer promise interviews. Pending re-review.

### F-19 [P3] open - Waitlist tests miss the server-function layer and some stated guarantees

**File:** web/tests/waitlist-api.test.ts:41, web/tests/waitlist.test.ts:207
**Found:** 2026-11-07 by /audit (scope: current; lens: tests)
**Why it matters:** The honeypot test asserts only that no mail was sent, not that no row was stored (the spec says "without storing"). Nothing exercises `joinWaitlistFn`'s validator or its use of the real request headers and the module-level limiter, the confirm and unsubscribe server functions, the HTML email (token placement, no unescaped user text), the absent-header `unknown` bucket, or concurrent joins. The no-address-in-logs test only covers the failure log line. Service-level tests are otherwise solid: real database, injected clock, raw token not stored, resend limits, expiry, idempotency.
**Suggested fix:** Assert the table is empty in the honeypot test; add a test of the server-function handler path and one concurrent-join test once F-14 is repaired.
**Resolution:**

### F-20 [P3] open - Confirm and unsubscribe pages drop keyboard focus and wrap a button in a live region

**File:** web/src/routes/waitlist/confirm.tsx:57, web/src/components/MessagePage.tsx:15
**Found:** 2026-11-07 by /audit (scope: current; lens: quality)
**Why it matters:** `MessagePage` puts the whole card, title and button included, in `role="status" aria-live="polite"`. Pressing "Confirm my email" disables the button (focus is lost in several browsers), then the result branch removes it, so focus falls to the document body and a keyboard or screen-reader user must navigate again to find the outcome. Announcing the heading plus every paragraph on each state change is also noisy. The same holds for the unsubscribe page.
**Suggested fix:** Keep the button out of the live region, announce only a short status line, and move focus to the result heading (`tabIndex={-1}`) when the state changes; use `aria-disabled` instead of `disabled` while working.
**Resolution:**

### F-21 [P3] open - Background confirmation sends can be lost silently

**File:** web/src/server/waitlist.ts:200, web/src/server/waitlist.ts:213
**Found:** 2026-11-07 by /audit (scope: current; lens: quality)
**Why it matters:** Since the send is detached, the visitor is always told "Check your inbox". Failures are only logged at error level, so with `UnconfiguredProvider` outside local, a wrong Resend key or an outage every new signup is stored and never mailed, with no signal to the visitor or alert. `flushPendingSends` is documented as for graceful shutdown but nothing calls it, so a restart or deploy drops queued sends: the row then has a fresh `tokenSentAt` and a 10-minute resend gate with no email ever sent. The failure handler also resets `tokenSentAt` to epoch without checking that the row still holds the same token (see F-14), which can expire a newer live token. `track` uses `void task.finally(...)`, which would surface an unhandled rejection if `logger.error` ever threw.
**Suggested fix:** Register a `SIGTERM` handler (in the 28b server entry) that awaits `flushPendingSends`; add a startup/readiness warning when the provider is unconfigured outside local; guard the failure update with `tokenHash`; end `track` with `.catch(() => undefined)`.
**Resolution:**

### F-22 [P3] open - Some repair tests no longer prove what they claim

**File:** web/tests/waitlist-api.test.ts:164, web/tests/waitlist-api.test.ts:123
**Found:** 2026-11-07 by /audit (scope: current; lens: tests)
**Why it matters:** The "does not confirm on load" test greps the route source for `loader:` and counts `confirmWaitlistFn(` occurrences, so a `useEffect` or `beforeLoad` that confirms on load would still pass; it proves wording, not behaviour. The global-cap test uses `trustProxy: false` only, so nothing covers the order of the global and per-IP limiters (F-11), the global cap with a trusted address, or `TRUST_PROXY_HEADERS` being read from the environment by default. The unconfigured-provider path (every send rejected) has no test.
**Suggested fix:** Test the page with a rendered component (no server function call on mount, one call after click) or a browser test; add the limiter-order test with F-11; add a default-argument test for `clientIp`.
**Resolution:**

### F-30 [P3] open - Backup failure paths can leave a bad object and the server holds delete rights to the bucket

**File:** deploy/backup.sh:53, deploy/backup.sh:57
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** The partial-upload cleanup is an `ERR` trap, so the later `die` branches (listing mismatch, size under 100 bytes) exit without deleting the bad object, and a failed `deletefile` is ignored, which leaves a truncated object with a valid name. The `>100 bytes` check cannot tell a truncated dump from a complete one. Separately, the rclone remote on the server holds a read and write token, so anyone who gets the server can delete every backup (retention uses the same credentials). Only the encryption keeps contents safe.
**Suggested fix:** Verify with `gzip -t` after decrypting in a periodic drill, or write to a temp name and rename on success; document a write-only or versioned bucket token for the server.
**Resolution:**

### F-31 [P3] unverified - Cloudflare-only guard admits any Cloudflare customer; Docker source address not tested on Linux

**File:** deploy/cloudflare-ips.caddy:6, deploy/Caddyfile:9
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** Allowing the Cloudflare ranges means anyone with their own Cloudflare zone can proxy requests to the origin IP with `Host: jobmigo.com`. `cf-connecting-ip` then carries that sender's real address, so the limiter stays per-client, but the guard is weaker than the runbook claims and no authenticated origin pulls or secret header are used. The guard also depends on Caddy seeing Cloudflare's real peer address through Docker's published port (true for IPv4 with default iptables NAT; a userland-proxy or IPv6 path shows the bridge gateway and returns 403). Only a local macOS 403 was verified, so the pass-through for real Cloudflare traffic is covered only by the runbook checklist.
**Suggested fix:** State the limitation in the runbook; add authenticated origin pulls later; run the checklist after step 9.4 including a proxied request.
**Resolution:**

### F-33 [P2] open - deploy.sh can roll back a healthy deploy because `caddy reload` runs the instant Caddy starts

**File:** deploy/deploy.sh:68-71
**Found:** 2026-11-07 by /audit (scope: current; lens: quality, independent review of e84d143..b1de666)
**Why it matters:** `start_stack` runs `up -d --build` and then immediately `exec caddy caddy reload`. When Caddy was just created or restarted (first deploy, an image bump, a changed compose file, an env change), its admin API is not yet listening. I reproduced it: `docker run -d caddy:2` followed at once by `docker exec ... caddy reload` failed with `dial tcp [::1]:2019: connection refused` on the first try. A failed reload makes `start_stack` return 1, which `deploy.sh` reads as an unhealthy release: it logs "did not become healthy", hard-resets the checkout to the previous commit and rebuilds, even though the web container was healthy (compose already waits for web before starting Caddy). On a first deploy it exits 1 with a working stack and a misleading message.
**Suggested fix:** Retry the reload for a few seconds, or skip it when the Caddy container was just recreated (a start already reads the files), and treat a reload failure separately from a health failure so it never triggers the git rollback. Nothing is lost.
**Resolution:**

### F-34 [P3] unverified - Runbook SSH hardening may not take effect on Ubuntu cloud images

**File:** docs/deploy.md:52
**Found:** 2026-11-07 by /audit (scope: current; lens: security, independent review of e84d143..b1de666)
**Why it matters:** The step edits only `/etc/ssh/sshd_config`. Ubuntu 24.04 cloud images read `/etc/ssh/sshd_config.d/*.conf` first (the first value wins), and some providers ship a drop-in such as `50-cloud-init.conf` with `PasswordAuthentication yes`. The founder would believe password login is off when it is not. Not reproduced here (no server touched); it depends on the provider image.
**Suggested fix:** After restarting ssh, add `sshd -T | grep -E 'passwordauthentication|permitrootlogin'` to the runbook with the expected values, and write the settings to a `sshd_config.d/00-jobmigo.conf` drop-in instead.
**Resolution:**

### F-35 [P3] open - Privacy notice does not name Cloudflare, which will proxy all traffic

**File:** web/src/routes/privacy.tsx:48-55
**Found:** 2026-11-07 by /audit (scope: current; lens: quality, independent review of e84d143..b1de666)
**Why it matters:** The "Who handles it" section was corrected to mention Resend and Google Fonts, but the deployment this feature ships puts Cloudflare in front of every request (it sees visitors' IP addresses and the join request body) and stores the encrypted backups in Cloudflare R2 in the runbook's default setup. The notice also says "We do not store your IP address ourselves" and stays silent about who does. The earlier honesty review of this page was the reason for those edits, so the same standard applies here.
**Suggested fix:** Add one sentence naming Cloudflare (DNS, proxy, email forwarding for the contact address) and the hosting provider as processors, and keep it in step with the provider actually chosen.
**Resolution:**

### F-36 [P3] open - After a rollback the next routine deploy silently re-applies the rolled-back commit; a second rollback is a no-op

**File:** deploy/deploy.sh:76-97, docs/deploy.md:264-277
**Found:** 2026-11-07 by /audit (scope: current; lens: quality, independent review of e84d143..b1de666)
**Why it matters:** `--rollback` does `git reset --hard <previous>` on the branch, so `origin` is still ahead. The next `./deploy/deploy.sh` runs `git pull --ff-only` and redeploys the commit that was just rolled back, with no warning, unless the founder first reverts or fixes it upstream. After a rollback `.previous-good-commit` is left equal to the commit now running, so running `--rollback` again changes nothing and reports success. The runbook does not say either.
**Suggested fix:** State in the runbook that a rollback must be followed by a revert or fix pushed to the branch before the next deploy; print that reminder at the end of `--rollback`. Nothing is lost.
**Resolution:**

### F-37 [P3] open - A failed nightly backup is silent

**File:** deploy/jobmigo-backup.service:6-11, docs/deploy.md:187-198
**Found:** 2026-11-07 by /audit (scope: current; lens: security, independent review of e84d143..b1de666)
**Why it matters:** `backup.sh` exits non-zero on failure, but nothing tells the founder: no `OnFailure=` unit, no ping to a monitor, no check of the newest object's age. The uptime monitor watches `/healthz` only. A rotated rclone token, a full bucket or a changed remote would leave the project without backups for weeks while every check in the runbook stays green, and the restore drill is a few-months affair.
**Suggested fix:** Ping a dead-man's-switch URL (for example a Healthchecks.io check) at the end of a successful run and have it email when the ping stops, or add a weekly "newest backup is younger than 36 hours" check to the runbook. Nothing is lost.
**Resolution:**

### F-38 [P3] unverified - No container log size cap and a growing image cache on a 40 GB server

**File:** deploy/docker-compose.prod.yml:5-61, deploy/deploy.sh:68
**Found:** 2026-11-07 by /audit (scope: current; lens: performance, independent review of e84d143..b1de666)
**Why it matters:** Services use Docker's default `json-file` logging with no `max-size`, and every deploy builds a new image on the server without pruning the old ones. The web container logs per request errors (including failed sends), so a noisy period or a flood can fill the disk, which would also stop Postgres. The runbook has a "disk is full" row but nothing prevents it. Unverified: no long run was measured.
**Suggested fix:** Add `logging: {driver: json-file, options: {max-size: 10m, max-file: "3"}}` to each service (or the Docker daemon default) and run `docker image prune -f` after a successful deploy.
**Resolution:**

### F-39 [P3] open - Backup, restore and deploy logic has no repeatable test, only one-off drills

**File:** deploy/backup.sh, deploy/restore.sh, deploy/deploy.sh, web/docker-entrypoint.sh
**Found:** 2026-11-07 by /audit (scope: current; lens: tests, independent review of e84d143..b1de666)
**Why it matters:** The two P1 findings in this feature were in `restore.sh` and the password handling, and their repairs are verified by manual drills recorded only in prose. The scripts contain the only code path that can replace the live database, and no committed script reproduces the drills (the rclone stand-in, the wrong-name, corrupt-file and web-running cases, the `/` password refusal, the trust-flag refusal). A later edit can reintroduce the same defect with a green `npm test`. `shellcheck` was also not available to this reviewer, so no static check ran on any script.
**Suggested fix:** Add one `deploy/test-drill.sh` (or a Vitest file that spawns the scripts) that runs the restore failure cases against a throwaway Postgres container with a directory-backed `RCLONE` stand-in, and add `shellcheck` to the documented Verify steps once installed. Keep it small; no CI is needed.
**Resolution:**

### F-42 [P3] open - Canonical JSON collapses Date, Map, Set and non-finite numbers, so different inputs can share a cache key

**File:** web/src/server/ai/gateway.ts:34
**Found:** 2026-11-07 by /audit independent (scope: current; lens: security, quality)
**Why it matters:** `canonicalJson` treats any non-array object by its own enumerable entries. Verified: `{d: new Date(1)}` and `{d: new Date(99999)}` both serialise to `{"d":{}}`, and `NaN` serialises to `null`. A task whose input schema contains `z.date()`, a Set, a Map or a non-finite number would be served another input's cached answer for the same user and be billed as a cache hit. No current task does this, but the key contract is generic and the first real tasks are written later. Cross-user isolation is unaffected (the user id is a separate key column).
**Suggested fix:** Make the canonical form throw (or convert via `toJSON`) for anything that is not a plain object, array, string, finite number, boolean or null, so an unsupported input fails visibly; add a test for a Date and for NaN.
**Resolution:**

### F-45 [P3] unverified - `ai_cache` has no expiry and non-2xx response bodies are left unread

**File:** web/drizzle/0002_late_harpoon.sql:1, web/src/server/ai/openai-compatible.ts:96
**Found:** 2026-11-07 by /audit independent (scope: current; lens: performance)
**Why it matters:** One row holding the full validated output is stored per distinct input and never removed except with the user; a prompt-version or model change orphans every older row. At early volume this is small, so it is a lead. Separately, a non-OK response returns without consuming or cancelling `response.body`, which can keep the connection open until garbage collection when 429 or 5xx replies are frequent. Neither was profiled.
**Suggested fix:** Plan a periodic delete of `ai_cache` rows older than a set age (the `created_at` column exists) when the job table arrives, and call `await response.body?.cancel()` on the failure paths.
**Resolution:**

### F-46 [P3] unverified - Cached output is stored after schema transforms and revalidated against the same schema

**File:** web/src/server/ai/gateway.ts:107
**Found:** 2026-11-07 by /audit independent (scope: current; lens: quality, tests)
**Why it matters:** The cache stores `parsed.value` (the schema's output type) and reads it back through `task.output.safeParse`. For a schema with a `transform`, `coerce.date` or a defaulted field, the stored value may not parse again, so every call would be a cache miss that pays the provider and overwrites the row, silently defeating caching and cost control. No test task uses a transform, so this is unverified for real tasks.
**Suggested fix:** Document that task output schemas must be idempotent under re-parse (or store the raw validated JSON and parse on read), and add one gateway test with a transforming schema.
**Resolution:**

### F-47 [P2] open - A failed cache write throws away a good, paid answer and a raw Drizzle error can carry the model output

**File:** web/src/server/ai/gateway.ts:155
**Found:** 2026-11-07 by /audit independent (scope: current; lens: security, quality)
**Why it matters:** The `ai_cache` upsert runs after the usage row is written and its failure propagates out of `runTask`. The caller then gets no result for a reply it already paid for (the ledger shows the spend, the user sees an error), although the cache is only an optimisation. The thrown value is a `DrizzleQueryError` whose message is "Failed query: ... params: ..." (drizzle-orm 0.45.4, `errors.js:11`); for this insert the params include the validated `output` JSON, i.e. CV-derived text. Today `toResult` logs only the error name, but F-07 proposes logging a cause, and any future Sentry or caller log of `error.message` would put model output in logs, against "prompts, inputs, outputs ... never logged".
**Suggested fix:** Make the cache write best effort: wrap it in try/catch, log only `{ task, provider, model, code: 'ai_cache_write_failed' }`, and return the validated output. Add a gateway test with a failing cache write (for example a stub `db` or dropping the table) asserting the result is still returned, the usage row exists and nothing from the output is logged.
**Resolution:**

### F-48 [P3] open - A 200 reply that carries an error body or array content is treated as invalid output, not unavailable

**File:** web/src/server/ai/openai-compatible.ts:101
**Found:** 2026-11-07 by /audit independent (scope: current; lens: quality)
**Why it matters:** Some OpenAI-compatible gateways (OpenRouter among them) can answer HTTP 200 with a top-level `error` object, or return `message.content` as an array of parts. Both collapse to `text: ''` with zero tokens, so the gateway writes a zero-token usage row, spends a second provider call, and throws `ai_output_invalid` instead of `ai_unavailable`. This misleads callers and later credit logic about whether the model answered. Not exercised by any test.
**Suggested fix:** If the payload has a truthy `error` field and no `choices[0].message`, return a non-transient failure (status only logged); join array content parts of type text. Add provider tests for both shapes.
**Resolution:**

### F-49 [P3] open - Gateway tests miss mixed retry paths and weak spots in the cache key contract

**File:** web/tests/ai-gateway.test.ts:96, web/tests/ai-gateway.test.ts:236
**Found:** 2026-11-07 by /audit independent (scope: current; lens: tests)
**Why it matters:** (1) No test covers a billed invalid first reply followed by a provider failure on the retry; it is the path that decides whether attempt one stays in the ledger while `ai_unavailable` is thrown. (2) The canonicalisation test checks only key order and one differing value: it would still pass if arrays were sorted, `undefined` handling changed, or nested values were dropped. (3) The "never logs" gateway test passes a reply with no schema-mismatch shape, so the retry-prompt reason is only guarded by the json unit tests. The tested behaviours would otherwise fail if broken (per-user scope, version and model misses, empty billed reply, stale shape).
**Suggested fix:** Add a gateway test (invalid reply then `AiUnavailableError`) asserting one usage row and `ai_unavailable`; extend the canonical test with array order, nested objects and equal-after-`undefined` cases; make the logging test use a schema-mismatch reply with a secret value.
**Resolution:**

### F-52 [P3] open - `callEngine` path guard is bypassed by encoded dot segments, and redirects are followed with the identity headers

**File:** web/src/server/engine/client.ts:84, web/src/server/engine/client.ts:102
**Found:** 2026-11-07 by /audit independent (scope: current; lens: security)
**Why it matters:** The guard `path.startsWith('/internal/') && !path.includes('..')` does not stop `/internal/%2e%2e/healthz`: `new URL(path, base)` normalises it to `http://engine:8000/healthz` (verified in Node). The reachable targets are the engine's unauthenticated routes, so impact is low today, but the guard is documented as "only /internal/ paths" and a later caller that interpolates an id into the path would inherit the hole (also `?` and `#` in a path are accepted). Separately, `fetch` follows redirects by default; the engine returns a 307 for `/internal/whoami/` (verified), and a redirect to another origin would forward `x-user-id` (undici strips only `authorization`).
**Suggested fix:** Build the URL, then require `url.origin === base.origin` and `url.pathname.startsWith('/internal/')` on the parsed result (and reject `?`/`#` in `path`), and pass `redirect: 'error'` in the fetch init. Add tests for `%2e%2e`, `?` and the redirect option.
**Resolution:** `callEngine` checks the path as the URL parser reads it (an encoded `..` is refused) and sets `redirect: error`. Tests added for `%2e%2e` in both cases and the redirect option.

Reopened 2026-11-08 by /audit independent (scope: current; lens: quality, security, performance, tests). The code is repaired (verified in Node: `/internal/%2e%2e/healthz`, `%2E%2E` and `.%2e` all parse to `/healthz` and are refused by the parsed-pathname check). The claimed tests are not there: `web/tests/engine-client.test.ts:164` covers only `/healthz`, `/internal/../x` and an absolute URL, which the raw `includes('..')` guard and the prefix check already reject. Removing the `target.origin`/`target.pathname` check would fail no test. Still to do: add `/internal/%2e%2e/healthz` (and `%2E%2E`) to that list. `?` and `#` are still accepted in `path`; that is acceptable for query strings but undocumented.

### F-55 [P3] open - Small engine hygiene gaps: unused setting, unreadable bad `LOG_LEVEL`, undeclared direct dependencies, no stack trace for 500s, dropped HTTP error headers

**File:** engine/src/engine/config.py:27, engine/src/engine/jsonlog.py:39, engine/pyproject.toml:6, engine/src/engine/middleware.py:29, engine/src/engine/errors.py:44
**Found:** 2026-11-07 by /audit independent (scope: current; lens: quality)
**Why it matters:** (1) `Settings.environment` is read and passed by both compose files but used nowhere (dead configuration surface). (2) A bad `LOG_LEVEL` fails `setLevel` with a bare `ValueError: Unknown level: 'BOGUS'` traceback rather than the variable-naming message the spec requires for startup configuration failures. (3) The code imports `pydantic` and `starlette` directly but only `fastapi` is declared; they come in transitively, so a FastAPI release that changes its dependencies could break the import. (4) Unexpected errors log only the exception type, with no traceback or location, which makes a real 500 undebuggable; a stack trace can be logged safely if frames, not messages, are emitted (for example the file and line of the innermost frame) . (5) The Starlette `HTTPException` handler drops `error.headers`, so a 405 has no `Allow` header (verified live). (6) The `postgres://` URL with `?sslmode=` would be passed to asyncpg unchanged and fail; not a problem on the internal network.
**Suggested fix:** Drop `environment` until something uses it (or use it, for example to refuse an empty `ENVIRONMENT=production` token mismatch); validate `LOG_LEVEL` in `load_settings` and raise `ConfigError` naming it; add `pydantic` and `starlette` to `dependencies`; log `error.__traceback__` location fields; pass `headers=error.headers` in the 405 response.
**Resolution:** The unused `ENVIRONMENT` setting is removed, an invalid `LOG_LEVEL` names the variable, `pydantic` and `starlette` are declared dependencies and the 405 keeps its `Allow` header. Logging only the exception type on a 500 is kept on purpose (messages can carry request data).

Reopened 2026-11-08 by /audit independent (scope: current; lens: quality, security, performance, tests). Verified fixed: items 2, 3 and 5 (a bad `LOG_LEVEL` names only the variable; `pydantic` and `starlette` are declared and `uv lock --check` passes; a 405 keeps `Allow`, seen live). Still open: (1) the setting was removed but both compose files still pass `ENVIRONMENT` to the engine (`docker-compose.yml:26`, `deploy/docker-compose.prod.yml:30`), which is now dead configuration; and (4) a real 500 logs only the exception class (`engine/src/engine/middleware.py:29`), so it cannot be located. Logging the innermost frame (file, function, line from `error.__traceback__`, no message, no locals) keeps the no-request-data rule. Declining (4) is the user's call, not the builder's; it needs an explicit decision to become `accepted`.

### F-56 [P3] open - The 30 s default client timeout is not asserted by any test

**File:** web/tests/engine-client.test.ts:54, web/src/server/engine/client.ts:21
**Found:** 2026-11-08 by /audit independent (scope: current; lens: quality, security, performance, tests)
**Why it matters:** The spec's step 5 requires the 30 s timeout to be wired through the abort signal. The test passes `timeoutMs: 20`, so changing `DEFAULT_TIMEOUT_MS` to any value, or dropping the default, breaks no test. The abort wiring is proven, the contract value is not.
**Suggested fix:** Spy on `AbortSignal.timeout` (or use fake timers) in a call without `timeoutMs` and assert it was called with 30000.
**Resolution:**

### F-57 [P3] open - `deploy.sh` measures the raw `ENGINE_TOKEN` line, not the value Compose reads

**File:** deploy/deploy.sh:30, deploy/deploy.sh:40
**Found:** 2026-11-08 by /audit independent (scope: current; lens: quality, security, performance, tests)
**Why it matters:** `get_var` takes the text after `=`. With scratch env files and `--dry-run`: `ENGINE_TOKEN="<31 chars>"` (quotes) and `ENGINE_TOKEN=<10 chars> # <30 chars>` (inline comment) both pass the 32-character check, but Compose strips the quotes and the comment, so the engine receives 31 and 10 characters and refuses to start. A CRLF file line also counts the carriage return. Because `wait_healthy` now requires the engine, such a deploy is caught after the build and rolled back, so the harm is a slow, confusing failure rather than a silent one.
**Suggested fix:** Ask Compose for the value (`docker compose --env-file ... config` and read `ENGINE_TOKEN`, or `docker compose run`-free `config --format json`), or reject values containing quotes, spaces or `#` in the pre-flight check, as the `POSTGRES_PASSWORD` check does with its character class.
**Resolution:**

### F-58 [P3] open - First deploy of this release and a rollback past it are not covered by the new checks

**File:** deploy/deploy.sh:88, deploy/deploy.sh:111, docs/deploy.md:136
**Found:** 2026-11-08 by /audit independent (scope: current; lens: quality, security, performance, tests)
**Why it matters:** (1) The token check and the engine wait live in the script file, but on the first deploy that brings them the running script is the old one: it pulls, starts the new compose with no `ENGINE_TOKEN` (now tolerated by `:-`), waits only for web and records the commit as good while the engine crash-loops. Bash also reads a script incrementally, so replacing it mid-run by `git pull`/`reset --hard` is fragile (this predates the change). (2) `--rollback`, or the failure rollback, to a commit without the engine service runs `up -d` without `--remove-orphans`, so the engine container (holding the token and database access) keeps running unmanaged. The docs say deploy.sh "refuses to run without" the token, which is only true from the second deploy.
**Suggested fix:** In `docs/deploy.md`, tell the operator to add `ENGINE_TOKEN` to `.env.production` before pulling this release (or run `git pull` then `deploy.sh`), and add `--remove-orphans` to `up -d` in `start_stack` or note the manual `docker compose rm` after a rollback past this feature. No code change is needed for (1) if the doc is explicit.
**Resolution:**

### F-59 [P3] open - `X-User-Id` accepts non-canonical UUID forms and echoes a rewritten id

**File:** engine/src/engine/auth.py:35, web/src/server/engine/client.ts:97
**Found:** 2026-11-08 by /audit independent (scope: current; lens: quality, security, performance, tests)
**Why it matters:** `UUID(raw)` also accepts `{uuid}`, `urn:uuid:uuid` and the 32-digit form without hyphens. Verified live: all three return the canonical `userId` with 200. The spec says the header holds a UUID, and later features will key every query on this value, so two spellings of one id reaching logs, caches or keys is an avoidable ambiguity (the web client only sends canonical ids, so today only a hand-made call is affected). Related: `callEngine` forwards `currentRequestId()` unchecked; the web `withRequestId` keeps any client-supplied `X-Request-Id`, and a value Node's `Headers` rejects (for example non-ASCII) makes `fetch` throw a `TypeError`, which maps to `engine_unavailable` 502 for that request only.
**Suggested fix:** Require the canonical form in `require_user` (a hyphenated, case-insensitive regex, then `UUID`), with a test for the braces, `urn:` and bare-hex forms; in the client send `x-request-id` only when it matches a safe pattern (the engine already uses `[A-Za-z0-9._-]{1,64}`).
**Resolution:**

### F-60 [P3] open - Cached output is stored by field name, so an output model with aliases never hits the cache

**File:** engine/src/engine/ai/gateway.py:125, engine/src/engine/ai/gateway.py:198
**Found:** 2026-11-08 by /audit independent (scope: current; lens: quality, performance)
**Why it matters:** `_store` saves `output.model_dump(mode="json")`, which writes field names, and the cache read runs `task.output_model.model_validate(cached)`, which expects aliases by default. Verified: a model with `full_name: str = Field(alias="fullName")` dumps `{"full_name": ...}` and that dict fails `model_validate`. Any task whose output model uses aliases (likely for camelCase model JSON) would treat every cached row as a stale miss, pay the provider on every call and overwrite the row, with no error. A related, smaller effect: a `set` field in an input model dumps in hash order, so the same input can get a different cache key in another process (a miss, not a collision). No current task is affected; the first real tasks arrive in 3b. This is the Python form of F-46.
**Suggested fix:** Store `output.model_dump(mode="json", by_alias=True)` and add one gateway test with an aliased output model that asserts the second call is a cache hit. Nothing is lost.
**Resolution:**

### F-61 [P3] open - Ported gateway tests keep the gaps of F-49: mixed retry path, weak canonical test, logging test without a schema mismatch

**File:** engine/tests/test_ai_gateway.py:94, engine/tests/test_ai_gateway.py:446
**Found:** 2026-11-08 by /audit independent (scope: current; lens: tests)
**Why it matters:** (1) No test covers an invalid first reply followed by `AiUnavailableError` on the retry, the path that keeps attempt one in the ledger while raising `ai_unavailable` (the code in `gateway.py:227-243` does this correctly today, but nothing pins it). (2) `test_canonical_hashing_ignores_key_order_and_differs_on_content` checks key order and one value only; it would still pass if list order were ignored or nested values dropped. (3) The never-logs test sends a non-JSON reply, so the schema-mismatch reason that goes into the `ai output rejected` log line and the retry prompt is guarded only by the JSON unit tests. All other ported cases fail when their behaviour is broken.
**Suggested fix:** Add a gateway test with `Fake(reply("not json"), AiUnavailableError())` asserting one usage row and `ai_unavailable`; extend the canonical test with list order and a nested difference; make the logging test use a reply such as `{"name": 42, "secret-key": "reply-secret"}` against an output model with `extra="forbid"`.
**Resolution:**

### F-62 [P3] open - The production web container still receives the AI provider keys

**File:** deploy/docker-compose.prod.yml:51, deploy/.env.production.example:28
**Found:** 2026-11-08 by /audit independent (scope: current; lens: security)
**Why it matters:** The web service loads the whole `.env.production` with `env_file`, and this change adds `DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY` and `OPENROUTER_API_KEY` to that file. The web app no longer calls a model, but its container environment still holds every provider key, so a web-side compromise (the internet-facing service) exposes keys that only the internal engine needs. The local `docker-compose.yml` lists web variables explicitly and does not have this problem.
**Suggested fix:** Put the AI keys in a separate file read only by the engine service (for example `env_file: .env.engine` on `engine`), or replace the web `env_file` with an explicit variable list as in the local compose file; update `.env.production.example` and `docs/deploy.md` to match.
**Resolution:**

### F-63 [P3] unverified - A new HTTP client per provider attempt and a long worst-case task duration

**File:** engine/src/engine/ai/openai_compatible.py:90, engine/src/engine/ai/gateway.py:227
**Found:** 2026-11-08 by /audit independent (scope: current; lens: performance)
**Why it matters:** `create_provider` passes no client, so each attempt opens and closes its own `httpx.AsyncClient` (a new TCP and TLS connection to the provider every call and every retry). The total limit is per attempt, so one `run_task` can take up to two gateway attempts times two provider attempts at 60 s each, plus retry delays, about four minutes, before failing. Same semantics as the TypeScript version; no route calls it yet and nothing was profiled.
**Suggested fix:** When the first route lands (3b), create one `httpx.AsyncClient` in the app lifespan and pass it to `create_provider`, and decide whether the task time limit should bound the whole `run_task` rather than each attempt.
**Resolution:**

### F-68 [P3] open - A deeply nested DOCX costs about 800 MB of memory for a 10 KB upload; nothing bounds element depth

**File:** engine/src/engine/cv/extract.py:105
**Found:** 2026-11-09 by /audit (scope: current; lens: performance)
**Why it matters:** `_docx_text` keeps every open element in the tree and in `open_elements`, and has no depth limit. A 10 MiB `word/document.xml` of nested `<a>` tags compresses to about 10 KB; measured in-process it peaked at about 808 MB RSS and 2.9 s before returning `unreadable`. On Linux the child's `RLIMIT_AS` (512 MiB) kills it, so production is bounded and the user sees `cv_unreadable`. On macOS (no `RLIMIT_AS`) and for any in-process use, the limit does not hold, and the module docstring says each bound holds without the child.
**Suggested fix:** Raise `too_large` (or `unreadable`) when `len(open_elements)` passes a small depth cap (real documents stay well under 100), and add a test with a nested-element DOCX.

### F-69 [P3] open - The upload cleanup misses a cancelled `store.put` and deletes the object of a row that already committed

**File:** engine/src/engine/cv/service.py:111
**Found:** 2026-11-09 by /audit (scope: current; lens: quality)
**Why it matters:** (1) `await store.put` runs before the `try`, and it runs in a thread, so cancelling the task during the put lets the write finish later with no row and no cleanup. (2) The `try` also covers `session.refresh` and `model_validate` after `commit`. A failure or cancellation there deletes the object while the committed row stays, so the row points at a missing object and the download link returns a 404 from storage. Starlette does not cancel a request task on client disconnect, so both need shutdown or an unusual error; the impact is a stray or a dangling object, not exposure.
**Suggested fix:** Build the response from the values already in hand (or read them before commit) and put only `session.add` and `commit` under the delete-on-failure guard; leave a sweeper for the put window as a later item.

### F-70 [P3] open - A lone surrogate in extracted PDF text reaches the database insert and returns a 500

**File:** engine/src/engine/cv/extract.py:62
**Found:** 2026-11-09 by /audit (scope: current; lens: quality)
**Why it matters:** pypdf decodes `/ToUnicode` maps with `errors="surrogatepass"` (`_cmap.py`), and `normalise` strips control characters but not U+D800 to U+DFFF. Verified: such text survives the worker's JSON round trip and then fails `.encode()` with `UnicodeEncodeError`, which is what the Postgres driver does on insert. The upload returns a generic 500 (the object is cleaned up) instead of a 422 for a crafted or odd PDF. A full PDF reproduction was not built.
**Suggested fix:** Remove surrogate code points in `normalise` (extend `_CONTROL` with `\ud800-\udfff`) and add a unit test.
