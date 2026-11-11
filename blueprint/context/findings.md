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

### F-71 [P3] open - A parse stuck in `parsing` has no recovery until the engine restarts

**File:** engine/src/engine/cv/parse_service.py:279
**Found:** 2026-11-09 by /audit (scope: current; lens: quality)
**Why it matters:** `run_parse` swallows a failed `mark_failed` (logged only), and shutdown cancellation deliberately leaves the row `parsing`. The only recovery is `sweep_interrupted` at the next start. If the status write fails once (a database blip) or the engine is stopped and not restarted promptly, the row stays `parsing`, `POST /parse` is idempotent for `parsing` so a retry changes nothing, and the user sees a spinner indefinitely. A provider hang is bounded by the adapter timeout, so this needs a database error or a stop. Not reproduced.
**Suggested fix:** Treat `parsing` rows whose `updated_at` is older than a few minutes (well past the provider timeout) as claimable in `claim`, or fail them in the status read. Cheap and keeps one process.
**Resolution:**

### F-72 [P3] open - `achievement.experience_id` has no index, so deleting a CV scans `achievement` once per experience row

**File:** engine/migrations/versions/0004_profile_draft.py:127
**Found:** 2026-11-09 by /audit (scope: current; lens: performance)
**Why it matters:** The `ON DELETE SET NULL` foreign key on `achievement.experience_id` is checked by Postgres for each deleted `experience` row (CV delete cascades to profile, then experience). With no index on the referencing column each check is a sequential scan of `achievement`. Harmless at launch volumes, but it grows with users times experiences and runs inside the delete request. Not measured.
**Suggested fix:** Add an index on `achievement(experience_id)` in a later migration (or change 0004 before it ships), with the matching `Index` in the model.
**Resolution:**

### F-73 [P3] unverified - One out-of-bounds field fails the whole parse

**File:** engine/src/engine/cv/parse.py:56
**Found:** 2026-11-09 by /audit (scope: current; lens: quality)
**Why it matters:** Bounds and the date pattern are rejections, not clamps. A model reply with one 600-character bullet, a date such as "Present" or "2020-1", a 31st experience, or an empty required name after cleaning fails validation; after the gateway's single retry the whole parse ends as `ai_output_invalid`, and a user retry reruns the same input. Real CVs with long bullets or "Present" end dates may hit this. The design choice is documented, but no live run with a real model has measured how often it happens (the live test was not run).
**Suggested fix:** After the live run, decide whether to drop or truncate individual bad items (skip an experience with an invalid date, normalise "Present" to `is_current`) instead of failing everything.
**Resolution:**

### F-74 [P3] open - No test races two claims or proves the claim, draft write and failure write are owner-scoped on their own

**File:** engine/tests/test_cv_parse_service.py:127
**Found:** 2026-11-09 by /audit (scope: current; lens: tests)
**Why it matters:** The idempotency test starts two parses one after the other, so it does not exercise the atomic claim under a real race, and owner scoping is tested only through `start_parse` and the routes (the pre-read `get_cv` already refuses another user). A regression that dropped `user_id` from the `claim` or `_write_draft` UPDATE, or from `mark_failed`, would still pass. These statements carry the trust boundary the spec names.
**Suggested fix:** Add tests that call `claim`, `mark_failed` and `_write_draft` directly with a different user id and assert no row changes, and one that runs two `claim` calls with `asyncio.gather` and asserts exactly one returns True.
**Resolution:**

### F-76 [P3] open - Focus is dropped on every state change and the upload has no announcement

**File:** web/src/routes/_app/onboarding.tsx:408
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The spec requires focus and announcements. Pressing "Delete this CV" unmounts that button and renders the confirm group, but focus is not moved into it, so a keyboard or screen-reader user lands on the body; the same happens when the dropzone or "Upload another file" button unmounts after an upload, a delete confirm, or a parse starting. While uploading, the dropzone only swaps its text ("Uploading your CV...") with no `role="status"` or live region, so nothing is announced until the ready view appears (the `Problem` alert does fire).
**Suggested fix:** Move focus to the confirm group's first button (and back to the trigger on cancel), move focus to the new state's heading or status region after upload and delete, and wrap the busy text in a `role="status"`.
**Resolution:** Fixed: focus moves to "Keep it" when the delete confirm opens and back to "Delete this CV" when kept, and to the page heading after an upload or delete; the dropzone status text is a polite live region; seen in the browser.
Reopened 2026-11-10 by /audit independent at P3: the delete confirm and upload focus repairs work, but the "a parse starting" case is not repaired. `build()` (Build my profile draft and Try again) never moves focus, so the pressed button unmounts into the parsing view and focus falls to the body. Also `confirmDelete` is not reset by `build()` and is shared by every `DeleteControl` instance, so opening the confirm and then pressing Build (or a parse finishing) remounts the control with the confirm already open and steals focus into "Keep it". Suggested fix: call `settleFocus()` after `build()`, and `setConfirmDelete(false)` there.

### F-77 [P3] open - A failed "Build my profile draft" call shows the same alert twice

**File:** web/src/routes/_app/onboarding.tsx:146
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** When `startParse` fails with an HTTP error (the engine's 502 for an AI failure), `build()` calls `setProblem(copyFor(code))` and then refreshes the list, which now returns the CV as `failed` with the same code. The page then renders the `problem` card and the failed card, both `role="alert"` with identical title and body, so a screen reader announces it twice and sighted users see two cards.
**Suggested fix:** Clear `problem` after the refresh when the refreshed CV is `failed`, or skip `setProblem` for parse codes and let the failed card speak.
**Resolution:** Fixed: the failed view shows one alert (the latest message), not two; seen in the browser (1 alert after a failed retry).
Reopened 2026-11-10 by /audit independent: the repair (`problem ?? screen.copy` in the failed view) lets a client-side file problem replace the failure message while the failed CV's buttons stay. Choose a 6 MB file from "Upload another file" on an `ai_unavailable` failure and the one card reads "That file is too large" with "Try again" (which re-runs the parse, not the upload) beside it. Suggested fix: show a file-validation problem as its own card above the failed card, or keep the failed copy and add the file message; the duplicate-alert fix only needs to drop the stale parse problem.

### F-78 [P3] open - "Try again" is offered for `ai_not_configured`, where retrying cannot help

**File:** web/src/lib/cv-view.ts:114
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** `ai_not_configured` shares the "could not reach the AI service ... Try again in a moment" copy and the retry button with transient errors. It is a server configuration state that never clears by retrying, so a user loops on it. The spec lists it as retryable and the test encodes that, so this is a spec choice worth revisiting, not a build deviation.
**Suggested fix:** Give it its own copy ("This feature is not switched on yet") with no retry, or keep it and note the decision.
**Resolution:** Fixed: `ai_not_configured` no longer offers Try again (copy: the AI service is not set up yet); the unit test lists it with the codes that offer no retry.
Reopened 2026-11-10 by /audit independent: `ai_not_configured` now has no "Try again", but the engine stores it as the CV's `failed` state. The only action is "Upload another file", which deletes the CV first, and the copy says "check back later". When the AI is configured the user returns to a CV that still shows this failure, with no way to build the draft except delete and re-upload. Suggested fix: keep a retry for this code (the engine re-checks configuration on each POST) with the "not set up yet" copy, or do not persist it as `failed`.

### F-81 [P3] open - A 401 during replace is never redirected, and tests cover only the pure helpers

**File:** web/src/routes/_app/onboarding.tsx:126
**Found:** 2026-11-10 by /audit independent (scope: current; lens: tests)
**Why it matters:** In `chooseFile`, a delete that fails with `unauthorized` sets the "Please sign in again" card and returns before `refresh()`, so the sign-in redirect (driven only by the list query's error) never fires and the card has no sign-in link. The page logic that carries the spec's risks (the `refetchInterval` and `startedRef` stop conditions, the delete-then-upload order, one interval, redirect on 401) has no automated test; `shouldKeepPolling` and `copyFor` tests prove only the pure helpers, and the evidence is a scripted browser pass that is not in the repo.
**Suggested fix:** Call `refresh()` (or navigate to sign-in) on `unauthorized` in every handler, and extract the replace flow and poll decision into testable functions with a Vitest case each.
**Resolution:** Part fixed: a 401 anywhere in the page now goes back to sign-in. Still open: the page logic (polling stop conditions, delete-then-upload order) has no automated test, because no DOM test library is installed.
Re-examined 2026-11-10 by /audit independent, left open: the 401 redirect is now in `fail()` and the list query, but the draft query is not covered (F-82). In `cv-api.test.ts` the "each route" test records four calls and runs DELETE through a separate fetch, so the DELETE method and path are not asserted.

### F-82 [P3] open - A session that ends while a draft is shown is not sent to sign-in

**File:** web/src/routes/_app/onboarding.tsx:82
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The sign-in redirect reads only the list query's error. The draft query throws `CvError('unauthorized')` on a 401 but nothing inspects it, so the parsed view shows "We could not load your draft ... Your CV is safe. Try again in a moment" and Try again gets the same 401. The list is not polled in `parsed`, so the page may not notice for a long time. Not reproduced.
**Suggested fix:** Treat `draft.error` with code `unauthorized` like the list error.
**Resolution:**

### F-83 [P3] open - The trust box names DeepSeek as the provider, but the engine's provider is configuration

**File:** web/src/components/cv/parts.tsx:222
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The copy says the CV text is sent to "our AI provider, DeepSeek". `AI_CHEAP_MODEL` accepts `deepseek/`, `moonshot/` or `openrouter/` models (`.env.example`), so a deployment on another provider would make a privacy statement false. Correct today only because DeepSeek is the planned model, which is unset.
**Suggested fix:** Say "our AI provider" without a name, or have the engine expose the provider name and render it.
**Resolution:**

### F-84 [P3] open - The parsing and parsed views are one `role="status"` region around buttons and the whole draft

**File:** web/src/routes/_app/onboarding.tsx:281, web/src/routes/_app/onboarding.tsx:508
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** A live region should hold the message. Here it wraps the file card, the delete control (so opening the confirm is announced as a change), and in the parsed view the full draft (headline, role list, user-derived text) plus a nested `role="alert"` for a draft load error, read out on mount. It works but is noisy and nests live regions.
**Suggested fix:** Put `role="status"` on a short sentence ("Reading your CV", "Draft ready") and leave the rest as ordinary content.
**Resolution:**

### F-90 [P3] open - The lost-update and confirm-versus-edit concurrency tests pass without the row lock

**File:** engine/tests/test_profile_edit.py:359, engine/tests/test_profile_edit.py:386
**Found:** 2026-11-10 by /audit independent (scope: current; lens: tests)
**Why it matters:** In a scratch copy with the `FOR UPDATE` removed from `latest_profile`, `test_concurrent_edits_to_different_fields_are_both_kept` and `test_a_confirm_racing_an_edit_never_hides_the_edit` still passed on three runs; only the duplicate-add, limit and patch-versus-delete tests failed. `asyncio.gather` over two short calls does not force the two reads to overlap, and the confirm test ends in `edited` for either order. A regression that drops the lock for confirm, or writes stale columns, would go unnoticed.
**Suggested fix:** Make the overlap deterministic: hold the profile lock in a separate session (or add a barrier/sleep after the read through a test hook), start the call, release, and assert the outcome; or drop the two tests' claim of covering the lock.
**Resolution:**

### F-91 [P3] open - Reads after commit run outside the lock, so a concurrent delete can turn a committed change into a 500 or 404

**File:** engine/src/engine/profile/service.py:196, :228, :248, :150, :295
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** `add_item`, `patch_item` and `confirm_item` call `session.refresh(row)` after `commit()` (which expires the row and frees the lock). If another request deletes that row in between, `refresh` raises `InvalidRequestError`, an unhandled 500 for a write that succeeded. `patch_profile` and `confirm_all` re-run `_current` after commit; if the profile was deleted meanwhile they answer 404 for a change that was saved. Narrow window, not reproduced.
**Suggested fix:** Build the response before commit (flush, then validate the row into the output model, or use `expire_on_commit=False`), and read the new version in the same transaction with `RETURNING`.
**Resolution:**

### F-92 [P3] unverified - Latest-profile lock query can lock an older draft when the newest one is deleted while waiting; `GET` is not one snapshot

**File:** engine/src/engine/profile/service.py:34
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** With `ORDER BY ... LIMIT 1 FOR UPDATE OF profile`, Postgres re-checks a row that was changed while it waited and, if the row is gone, takes the next one: a mutation that was queued behind a delete of the newest CV could add an item to the previous parsed draft. Also `get_profile` reads the profile and each fact table in separate READ COMMITTED statements, so `version` can be older than the rows returned if a commit lands between them. Neither reproduced; only reachable with more than one parsed CV or a read racing an edit.
**Suggested fix:** If it matters, re-check after locking that the locked profile is still the user's newest parsed one (or reject when its CV is not `parsed`), and read in a REPEATABLE READ transaction.
**Resolution:**

### F-93 [P2] fixed - The skill panel reuses one fact row across skills, so an open editor or delete question follows you to the next skill

**File:** web/src/routes/_app/profile.tsx:491
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** `SkillChips` renders `<FactRow kind="skill" fact={selected} />` with no `key`. Chips stay clickable while a panel is open, so clicking skill B while skill A's editor is open keeps the same component instance: `FactEditor` keeps A's typed values in its `useState` and `fact` is now B, so Save sends the diff against B and renames B to A's text (or hits `already_exists`). An open "Delete this?" question likewise carries over, now under B's name. Found by reading; not run in a browser.
**Suggested fix:** `key={selected.id}` on the panel's `FactRow` (and consider disabling the other chips while an editor is open).
**Resolution:** `key={selected.id}` on the panel `FactRow`, so each skill gets its own editor and delete state; browser-checked.

### F-94 [P2] fixed - The load-failed card uses the save-failure copy ("We could not save that ... Your profile is unchanged")

**File:** web/src/routes/_app/profile.tsx:218, web/src/lib/profile-view.ts:272
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** Any load error other than `not_found` and `unauthorized` (`engine_unavailable`, `network`, `unexpected`) is shown with `copyFor`, whose default says "We could not save that. Your profile is unchanged." On a load that is the wrong action, and after a successful save whose re-read fails the same card says the profile is unchanged when it was changed, while the stale profile is still on screen. The unit test only checks length and that no code leaks, so it passes. The load-failed state was not captured in the build evidence.
**Suggested fix:** A separate load copy ("We could not load your profile ... Try again") and, after a mutation, a message that the change was saved but the page could not refresh.
**Resolution:** Load failure now has its own copy ("We could not load your profile") and shows no stale facts; `copyFor` covers it; browser-checked.

### F-95 [P2] fixed - Focus is lost after Confirm, Confirm all, opening the headline editor and closing a skill panel

**File:** web/src/components/profile/facts.tsx:355, web/src/routes/_app/profile.tsx:175, web/src/routes/_app/profile.tsx:353, web/src/routes/_app/profile.tsx:493
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The spec requires focus to land somewhere sensible after every transition, and the earlier /onboarding reviews found this class. (1) Confirm: the button is removed once the status changes, so focus drops to the page body (a user confirming rows with the keyboard must tab from the top each time). (2) Confirm all: the button becomes disabled, so keyboard focus is stranded on it. (3) "Edit headline" is replaced by the form and nothing moves focus into the Headline field (the row editor does this; this one does not). (4) The skill panel's Close button unmounts itself with no focus target. The docs say focus returns "after a delete or add" and the evidence lists focus only for those, so these were not seen.
**Suggested fix:** After Confirm, move focus to that row's Edit button (or the next unconfirmed Confirm); after Confirm all, to the progress text or the first section heading; focus the Headline input when the editor opens; focus the chip that opened the panel on Close.
**Resolution:** Focus returns to the row's Edit button after Confirm, to the page title after Confirm all, to the headline input when it opens, and to the chip when a skill panel closes; browser-checked.

### F-96 [P2] fixed - Save errors raise two alerts; Confirm and Delete errors appear only in a banner at the top of the page

**File:** web/src/routes/_app/profile.tsx:95, web/src/routes/_app/profile.tsx:230, web/src/components/profile/facts.tsx:219
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** `ctx.run` always sets the page-level `Problem` (`role="alert"`, above the progress cards) and, for save, add and headline edits, the caller also sets an inline `role="alert"` with the same words: two announcements per failure, the exact duplicate-alert class found on /onboarding. For Confirm and Delete there is only the top banner, which a user working on a row far down the page does not see, and focus does not move to it. The banner is cleared only by the next action, so after Cancel it still says "That was not accepted" for an edit that no longer exists.
**Suggested fix:** Show one error, next to the control that failed (inline for edit, add, headline, and a short inline line for Confirm and Delete); keep the top banner only for page-level errors, and clear it on Cancel.
**Resolution:** Save errors show once, in the row; Confirm and Delete errors also show in the row (`rowError`); the page banner is only for `not_found` and Confirm all failures; browser-checked.

### F-97 [P3] fixed - The same live-region message twice in a row is not announced

**File:** web/src/routes/_app/profile.tsx:100
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** `run` sets `notice` to "Confirmed." for each Confirm. When the text is unchanged React does not touch the DOM, so confirming a second fact right after the first, or saving twice, announces nothing. Together with F-95 a screen reader user confirming several rows gets feedback only for the first.
**Suggested fix:** Clear the notice at the start of `run` (or add a counter into the text, or key the region node on a sequence number).
**Resolution:** `announce()` alternates a zero-width suffix so a repeated message changes the live region text.

### F-98 [P3] open - Stale data is kept after a failed or empty re-read, and a headline edit can overwrite a concurrent change

**File:** web/src/routes/_app/profile.tsx:80, web/src/routes/_app/profile.tsx:397
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The page shows `query.data` and the error card together. If the re-read after a change returns `not_found` (the draft was deleted in another tab) the "Upload your CV to begin" card shows above the old facts, which can still be edited (each action then answers not_found). If the re-read fails, the new values are not shown (see F-94). In the headline form the diff is taken against the live `profile.headline`, not the value the form was opened from, so an untouched field is sent if another tab changed it meanwhile; row editors have the same property (`fromForm` diffs against the current `fact`). Narrow races, not reproduced.
**Suggested fix:** Hide the review view when `loadCode` is `not_found`; diff against the values the editor opened with.
**Resolution:** The page shows `undefined` data while the query is in error; the headline editor still diffs against the live value (the stale-data part is fixed; the diff-against-live-value race is not, and stays open).

### F-99 [P3] open - The page has no automated test, and the API test does not assert the DELETE call

**File:** web/tests/profile-api.test.ts:19, web/tests/profile-view.test.ts
**Found:** 2026-11-10 by /audit independent (scope: current; lens: tests)
**Why it matters:** "Calls each route" runs the DELETE through a separate fetch and the expected list has six entries, so the DELETE method and path are unasserted. The behaviours that carry this feature's risks (one mutation at a time, the refetch after each change, `not_found` and 401 handling, the focus and live-region rules, panel state per skill) are not tested; the build evidence is a scripted browser pass not kept in the repo, and F-93 to F-97 were all missed by it. `copyFor`'s test cannot catch the wrong load copy (F-94). No case covers toggling `isCurrent` alone, an achievement with a related role set, or the add-form body for the other kinds.
**Suggested fix:** Record the DELETE in the same fetch mock; extract the run/refresh logic into a tested function; add a component or browser test when a harness is added (`/tests browser`).
**Resolution:** Partly: the API test now asserts the DELETE method and path and the whitespace rules are tested; the page behaviours still lack automated tests because the repo has no DOM test library. Left open.

### F-100 [P3] fixed - The client length check counts raw characters, the engine counts them after cleaning

**File:** web/src/lib/profile-view.ts:216, web/src/routes/_app/profile.tsx:392
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The engine collapses runs of whitespace and drops control characters before checking the maximum (`cv/parse.py` `_clean`); the form checks after only a trim. A pasted value that fits after cleaning but is over the limit with its spaces is refused client-side, and the headline and summary check the untrimmed length. The error is conservative and calm, so it is not harmful, but the mirror is not exact, and the headline and summary inputs have no `aria-invalid` or `aria-describedby` tie to their (page-level) alert.
**Suggested fix:** Collapse whitespace the same way before counting, and tie the headline error to its field.
**Resolution:** `profile-view.ts` collapses whitespace like the engine before the length check and before sending; test `counts the collapsed length and sends the collapsed text`.

### F-101 [P3] fixed - Skill chips: "Open" in the accessible name, no panel relationship, and focus does not move to the panel

**File:** web/src/routes/_app/profile.tsx:472
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** Each chip's `aria-label` is "Name, unconfirmed. Open" while `aria-expanded` already says it is open or closed, so the name reads wrongly when expanded. The detail panel renders after all chips with no `aria-controls` and focus stays on the chip, so a keyboard user must tab through the remaining chips to reach the panel. State is in the text (good), and targets are 44px.
**Suggested fix:** Label "Name, unconfirmed" and keep `aria-expanded`; add `aria-controls` and move focus into the panel (or render it right after the chip row with a heading).
**Resolution:** Chips are named by the skill, carry `aria-controls`, focus moves to `#skill-panel` on open and back to the chip on close.

### F-102 [P3] open - A failed background or post-change re-read removes the whole review view, and with it any open editor and its typed text

**File:** web/src/routes/_app/profile.tsx:94, web/src/router.tsx:7
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The F-98 repair sets `profile = query.isError ? undefined : query.data`. The query client keeps the default `refetchOnWindowFocus` with `staleTime` 30 s, so returning to the tab after 30 s refetches `/api/profile`; one transient failure (the query has `retry: false`) unmounts every section, row editor, the headline form, an open add form and the skill panel, discarding what the user typed, and shows "We could not load your profile". After a successful save whose re-read fails, the change is saved but the page hides it and the user sees the load card; "Try again" restores the view but not the lost input. Found by reading; not run in a browser.
**Suggested fix:** Keep showing the last good data when a refetch fails (with the load card above it, controls still guarded), and hide the facts only for `not_found`; or set `refetchOnWindowFocus: false` for this query.
**Resolution:**

### F-103 [P3] open - Inline row errors are not cleared by later actions, and a server error stays beside a client validation error

**File:** web/src/components/profile/facts.tsx:303, web/src/components/profile/facts.tsx:349, web/src/components/profile/facts.tsx:389
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** `rowError` (a failed Confirm or Delete) is cleared only by the next Confirm or Delete on that row; opening Edit, saving or cancelling leaves "We could not save that. Your profile is unchanged." showing, now wrong after a successful edit. In `FactEditor`, `serverError` is passed in and remains while the user fixes a field and a client error appears, so two alerts can show for one form. Also the `autoOpen` prop on `FactRow` is unused. Narrow, calm, not reproduced.
**Suggested fix:** Clear `rowError` when editing opens or a save succeeds; clear the server error on the next submit attempt (or on input); remove `autoOpen`.
**Resolution:**

### F-104 [P2] fixed - A delete or rename that answers `not_found` leaves the track controls stuck in the delete or rename mode

**File:** web/src/components/profile/tracks.tsx:38, web/src/components/profile/tracks.tsx:180, web/src/routes/_app/profile.tsx:153
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** `mode` is local to `TracksSection` and is only reset by `close()`. If the track was already deleted elsewhere (another tab or device), the engine answers `not_found`, `track()` refreshes the list, and `selected` becomes null while `mode` is still `deleting`. The confirm block is hidden (`selected &&`), every chip is disabled (`mode === 'deleting'`) and "+ Add a track" is disabled (`mode !== 'idle'`), and nothing on screen can set the mode back, so the section is unusable until a reload. For `renaming` the form stays titled "Rename track" but `submit()` falls through to `onCreate` because `selected` is null, so Save silently creates a new track. Found by reading; not run in a browser.
**Suggested fix:** Reset `mode` to `idle` when `selected` disappears (an effect on `selected?.id`), and in `submit()` never fall back to create while `mode === 'renaming'`.
**Resolution:** The panel modes reset when the chosen track disappears (effect in `tracks.tsx`), and a stale save refreshes the list; browser-checked (panel gone, Add enabled).

### F-105 [P3] fixed - `str.isalnum()` accepts non-ASCII letters in `CLOUDFLARE_ACCOUNT_ID`

**File:** engine/src/engine/ai/config.py:149
**Found:** 2026-11-10 by /audit independent (scope: current; lens: security)
**Why it matters:** The check is meant to keep the account id from changing the URL's shape, but Python's `isalnum()` is Unicode-aware, so an id such as `abcé` passes and is formatted into the URL. It cannot add a path, host or query (httpx percent-encodes it), and the value comes from operator config, so the impact is a confusing 4xx rather than an exploit. Cloudflare account ids are 32 hex characters.
**Suggested fix:** Match `[0-9A-Za-z]+` (or `[0-9a-f]{32}`) with `re.fullmatch`, and add a case with a non-ASCII value to `test_cloudflare_needs_an_account_id_that_goes_into_the_url`.
**Resolution:** Account id is checked with an ASCII regex; test covers a non-ASCII id.

### F-106 [P3] open - Emphasis rows can be orphaned by a race with a fact delete, and the list route returns orphans

**File:** engine/src/engine/tracks/service.py:155, engine/src/engine/profile/service.py:295
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** `emphasise` checks the fact and inserts under the track lock, but `delete_item` removes the emphasis rows without locking any track. A delete that commits between the fact check and the insert leaves an emphasis row for a fact that no longer exists. Rows for facts of older drafts or a deleted CV are likewise never cleaned (no foreign key, by design), and `GET /internal/tracks` returns every row, so the response and `variantVersion`-based consumers (features 8 and 11) must filter against the live profile. The screen already filters, and the spec accepts orphans, so this is a note for the generation features rather than a defect today.
**Suggested fix:** When a consumer is added, join emphasis to the live fact tables (or filter in `_emphasis`), and consider locking the track rows or using `FOR SHARE` on the fact row in `emphasise`.
**Resolution:**

### F-107 [P3] open - The tracks UI states that carry the risk have no automated test

**File:** web/tests/tracks-view.test.ts, web/tests/tracks-api.test.ts
**Found:** 2026-11-10 by /audit independent (scope: current; lens: tests)
**Why it matters:** The view model, client, proxy and engine routes are well covered (cap race, ownership, older drafts, concurrency, cleanup), but the component behaviour is only in the unrecorded browser pass: one mutation at a time, focus after add, rename, delete and toggle, the live-region announcements and the `not_found` path that F-104 breaks. There is no engine test for the `delete_item` and `emphasise` race either. Same gap as F-99 (no DOM test harness).
**Suggested fix:** Add a component or browser test when `/tests browser` is set up, starting with delete-then-`not_found`.
**Resolution:**

### F-108 [P3] open - The preferences panel remounts, and loses typed text, when the track's variant version changes

**File:** web/src/components/profile/tracks.tsx:248
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The panel is keyed by `${selected.id}-${selected.variantVersion}`. Preferences do not bump `variant_version`, but toggling "Emphasise" on a fact does (`tracks/service.py` lines 114 and 207), and the fact buttons stay enabled while the panel is open (only the chips are disabled by `mode`). Emphasising a fact, or a refetch after another tab emphasised one, changes the key, so the form remounts from stored values, discards unsaved typing and moves focus to the first field. Found by reading; not run in a browser.
**Suggested fix:** Key the panel by `selected.id` only (the diff-only body already tolerates stale originals), or disable the emphasis toggles while the panel is open.
**Resolution:**

### F-109 [P3] open - The form's duplicate and length checks are not an exact mirror of the engine's cleaning

**File:** web/src/lib/tracks-view.ts:117, web/src/lib/tracks-view.ts:128
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The engine drops control, format and surrogate characters (for example U+200B) and compares with `casefold()`; the form only collapses `\s+` and compares with `toLowerCase()`. So "Straße" and "STRASSE" pass the form and get a generic 422; a line holding only a zero-width character passes the form and is refused as empty; a pasted line whose length fits only after the format characters are dropped is refused client-side. All outcomes are calm and nothing is saved wrongly, but the per-field message is lost for these inputs.
**Suggested fix:** Strip `\p{Cc}\p{Cf}\p{Cs}` (keeping tab and newline) in `tidyName` before collapsing, and compare with a case-fold approximation (`toLowerCase()` plus `toUpperCase().toLowerCase()`).
**Resolution:**

### F-110 [P3] open - Preferences fields put the hint and error inside the label, so the accessible name is long and read twice

**File:** web/src/components/profile/preferences.tsx:47, web/src/components/profile/preferences.tsx:111
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** Each field is a `<label>` that wraps the control, the hint span and the error span, so the accessible name becomes "label + hint + error", and `aria-describedby` then repeats the same hint and error. Screen readers announce the text twice. The salary and currency inputs also leave their hint out of `aria-describedby`. Errors are reached by focus, which is good, and are not live, so nothing is lost; it is noise.
**Suggested fix:** Use a plain `<label htmlFor>` for the label text only and keep the hint and error as siblings referenced by `aria-describedby` (include the hint on salary and currency).
**Resolution:**

### F-111 [P2] fixed - A crafted 200,000-character paste can block the engine for over 20 seconds (quadratic cleaner paths, run on the event loop)

**File:** engine/src/engine/jobs/posting_guard.py:350, engine/src/engine/jobs/posting_guard.py:421, engine/src/engine/jobs/service.py:67
**Found:** 2026-11-10 by /audit independent (scope: current; lens: performance)
**Why it matters:** `last_index` scans the whole open-element stack for every closer, so many unclosed openers followed by many unmatched closers is quadratic. Measured here: `<p>` + `<b>` x 33,000 + `</x>` x 25,000 (199,003 characters, well inside the 256 KB body cap and the 200,000-character limit) took 23 s; `<div>` x 20,000 + `</x>` x 20,000 took 9 s. Also quadratic but milder: the `word not in homoglyphs` and `url not in hidden_urls` list lookups in `scan` (about 1.7 s for 25,000 distinct mixed-script words). `create_job` calls `clean_posting` synchronously inside the async handler, so the whole engine (every user, CV parsing, health checks) is stalled for that time by one signed-in user. The regexes themselves held up (no ReDoS found across 24 hostile shapes: unterminated tags, quotes, comments, script, doctype, deep nesting, entities). Not network-reachable without a session, hence P2.
**Suggested fix:** Keep a name-to-count dict (or a dict of name to list of indexes) beside the stack so a closer with no open match is O(1), and use a set next to the lists in `scan`. Optionally run `clean_posting` in `asyncio.to_thread` or cap the number of tags processed.
**Resolution:** The element lookup uses an index kept per name and `scan` uses sets, so the cleaner is linear (the 199k-character shapes take well under a second); `create_job` also runs it in `asyncio.to_thread`. A differential run of 4,000 random tag soups against the original walker gave identical output; a timing test is in `test_posting_guard.py`.

### F-112 [P3] open - Stored `source_url` is only checked in code, and `url_key` drops IPv6 brackets

**File:** engine/src/engine/jobs/models.py:121, engine/migrations/versions/0008_job.py:25
**Found:** 2026-11-10 by /audit independent (scope: current; lens: security)
**Why it matters:** `create_job` rejects non-http(s) schemes and credentials before storing, so no `javascript:` URL can be saved through the routes today. The table has no check constraint on `source_url`, though, and `sourceUrl` is returned verbatim, so a later screen (29c) must still render it as a link only after an http(s) check, and any other writer (a seed, a later import) is unguarded. Separately, `url_key` uses `parts.hostname`, which has no brackets, so `http://[::1]:80/a` and a host key built from `::1:80` look alike; the collision is contrived and only affects the duplicate check.
**Suggested fix:** Add `CHECK (source_url is null or source_url ~* '^https?://')` in a later migration, and re-add brackets for IPv6 hosts in `url_key`. Note the rule for 29c.
**Resolution:**

### F-113 [P3] open - No test guards the cleaner against slow input, and the body-cap tests do not show the profile route stays at 32 KB in the engine

**File:** engine/tests/test_posting_guard.py, engine/tests/test_jobs_routes.py
**Found:** 2026-11-10 by /audit independent (scope: current; lens: tests)
**Why it matters:** The suite covers hidden HTML, invisible characters, flags, counts-only findings, duplicates, the race, ownership and the job cap well, but nothing bounds the cleaner's time on hostile 200,000-character shapes (see F-111), so a future edit to the walker could regress silently. The web side proves the default 32 KB cap is kept; the engine's `_body` default is only covered by older profile tests, not by one that sends 40 KB to a profile or track route next to the 256 KB job route.
**Suggested fix:** Add a generous-bound timing test for the deep-stack and many-distinct-word shapes, and one engine test that a 40 KB profile body is refused while a 40 KB job body is accepted.
**Resolution:** Partly: a timing test for hostile input now exists; the profile-route 32 KB check next to the job route is still untested. Left open.

### F-115 [P2] fixed - `asyncio.to_thread` does not keep the event loop free while the cleaner runs

**File:** engine/src/engine/jobs/service.py:67
**Found:** 2026-11-10 by /audit independent (scope: current; lens: performance)
**Why it matters:** The cleaner is regex work, and a single `re` call holds the GIL for its whole duration, so the loop thread cannot run while one is matching. Measured: a ticker task on the loop with `await asyncio.to_thread(clean_posting, "<p>" + "<script " * 1500)` saw a maximum loop lag of 2.37 s for a 2.38 s job, so health checks, CV parsing and other users stall exactly as before. The comment "Off the event loop ... must not stall others" is therefore false for the slow shapes of F-114, and the thread also stays busy (the default pool) after the client disconnects.
**Suggested fix:** Fix the scans (F-114) so no single match is long. If a hard bound is still wanted, run the cleaner in a worker process with a timeout (the engine already runs CV extraction out of process) and refuse the paste with `validation_failed` on timeout; otherwise drop the `to_thread` and its comment, since it adds nothing.
**Resolution:** The comment no longer claims the event loop is free; the real protection is the linear-time cleaner and the size cap, with the thread as a courtesy.

### F-117 [P2] fixed - `collect` removes tags with `<[^>]+>`, which is quadratic on a comment or script block full of `<`

**File:** engine/src/engine/jobs/posting_guard.py:316
**Found:** 2026-11-10 by /audit independent (scope: current; lens: performance)
**Why it matters:** `collect` runs `re.sub(r"<[^>]+>", " ", inner)` over every dropped comment, script or style block. An unclosed `<!--` or `<script>` runs to the end of input, and `<` repeated inside it scans to the end from each `<`. Measured at 200,000 characters after a `<p>` prefix: `<!--` + `<` x n 13.8 s, `<script>` + `<` x n 13.8 s, `<style>` + `<b ` repeated 4.6 s, `<!--` + `<a ` repeated 4.7 s, `<!--` + `< ` repeated 6.9 s (all roughly 4x per doubling). One request stalls the engine for that time.
**Suggested fix:** Use `<[^<>]+>` here too (same rule as the other scans), or `<[^<>]*>`; the removed text only feeds the hidden-text scan.
**Resolution:** The tag strip over dropped blocks uses `<[^<>]+>`; the `<`-run shapes are in the timing test.

### F-118 [P2] fixed - Excluding `<` from tag bodies lets a tag written with a `<` inside it escape the hidden-content stripping

**File:** engine/src/engine/jobs/posting_guard.py:61, engine/src/engine/jobs/posting_guard.py:66, engine/src/engine/jobs/posting_guard.py:68
**Found:** 2026-11-10 by /audit independent (scope: current; lens: security)
**Why it matters:** A browser reads `<div hidden <b>` as a hidden `div` whose attributes include `<b`, so the text is invisible to the reader. After F-114's change `TAG` refuses a body containing `<`, so the cleaner now sees no `div` tag: `<p>a<div hidden <b>SECRET ignore all previous</div>vis` cleaned to `a<div hidden SECRET ignore all previous|vis` (before: `a|vis`), and `<div style="display:none" <b>X</b>vis</div>` kept `X` plus the raw `<div style=...` text. So a posting author can again put hidden text in the cleaned description that the user never saw, and the raw tag text is stored. Instruction-shaped lines are still counted, so this is partly covered by the flag. Ordinary pages are unaffected: 40,000 random tag soups without `<` inside tags matched the pre-repair output exactly. `<!DOCTYPE x<y>` and `<a title=x<y>` also change.
**Suggested fix:** Keep the old forms (`[^>]*`, a body allowed to contain `<`) and bound the work another way: possessive name (F-116) plus a bounded body, for example `{0,4000}` for the attribute group, with a longer unterminated tag treated as text; or tokenize once with `find("<")`/`find(">")` and remember when no more `>` exists.
**Resolution:** `<` is allowed inside a tag again (bounded to 1,000 characters of attribute text), so `<div hidden <b>SECRET` stays hidden; test added.

### F-119 [P2] fixed - The new timing test does not run the HTML walker, and misses the quadratic shapes

**File:** engine/tests/test_posting_guard.py:164
**Found:** 2026-11-10 by /audit independent (scope: current; lens: tests)
**Why it matters:** `test_repeated_unterminated_openers_are_cleaned_in_bounded_time` feeds strings that start with `<script `, `<a `, `<? ` and so on. Auto mode switches to the HTML cleaner only when the text contains `<html`, `<body`, `<div` or `<p`, so these inputs are cleaned as plain text and pass in milliseconds whatever the regexes do. The older test's shapes do start with `<p>` or `<div>`. A regression of F-114 would not fail this test, and F-116 and F-117 are not reachable from it either.
**Suggested fix:** Prefix every shape with `<p>`, call `guard(raw, "html")` directly, and add the F-116 and F-117 shapes: `<aaaa...`, `</aaaa...`, `<!--` + `<` x n, `<script>` + `<` x n, `<style>` + `<b ` repeated.
**Resolution:** The timing test starts every shape with `<p>` so it reaches the HTML path, and includes the F-114, F-116 and F-117 shapes, 62 in all.

### F-120 [P3] open - `addedLabel` says "Added today" for a job added yesterday on the day after a clock change

**File:** web/src/lib/jobs-view.ts:115
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The day count is `Math.floor((startOfDay(now) - startOfDay(then)) / 86_400_000)`. Across a spring-forward day the two midnights are 23 hours apart, so the floor gives 0. Measured with `TZ=America/New_York`: 8 March 2026 20:00 versus 9 March 2026 10:00 gives 0 (should be 1), so "Added yesterday" shows as "Added today", and a two-day gap shows as one day. The test uses one fixed date and no clock-change case, so it cannot catch this.
**Suggested fix:** Use `Math.round(...)` (or compare `Date.UTC(y, m, d)` of each local date), and add a test case across a clock change.

### F-121 [P3] open - A failed "Read the text we saved" has no retry and a sign-out is shown as a generic error

**File:** web/src/components/jobs/job-row.tsx:57, web/src/components/jobs/job-row.tsx:203
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** The text query has `retry: false` and `staleTime: Infinity`, and the error block is only a `Problem` with no button. Hiding and showing the disclosure again does not refetch an errored query whose observer stays mounted, so the user must reload the page to see the text after one network blip. A 401 from `getJob` is shown as "Something went wrong" instead of sending the user to sign in as the list and the actions do.
**Suggested fix:** Add a "Try again" button calling `text.refetch()` and treat `unauthorized` like the other calls.

### F-122 [P3] open - Failed Dismiss, Restore or Delete with `not_found` loses its message because the row is removed

**File:** web/src/routes/_app/jobs.tsx:81, web/src/components/jobs/job-row.tsx:134
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** For `not_found` the page invalidates the list and returns the copy "It may have been removed in another tab. We refreshed the list." The row unmounts on refresh and `setError` runs on it, so the message is never seen or announced; the row just disappears, silently for a screen reader. Failures of other kinds keep the row and show the message correctly.
**Suggested fix:** Announce the not-found copy through the page's live region (`announce`) instead of, or as well as, the row error.

### F-123 [P3] open - Small accessibility gaps in the add form and the disclosure

**File:** web/src/components/jobs/add-job.tsx:158, web/src/components/jobs/add-job.tsx:241, web/src/components/jobs/job-row.tsx:179
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** (1) Each `<label>` wraps its input, hint and error text, so the accessible name includes the hint and the error, which the input then also gets through `aria-describedby` (read twice). (2) `aria-controls="text-<id>"` points at an element that exists only while the disclosure is open. (3) When the carried link is invalid (credentials or over 2,000 characters from a fetched final address), `errors.url` is a `role="alert"` paragraph with no field and no focus target, and the form cannot be saved except by going Back; the message does not say that. (4) After a refused read, "Paste the text instead" appears twice (inside the notice and as the normal button).
**Suggested fix:** Put the visible label text in its own element tied with `htmlFor` or `aria-labelledby`, render the controlled region always (hidden when closed) or drop `aria-controls`, tell the user to go Back or clear the link for a url error, and keep one paste button.

### F-124 [P3] open - A link the engine refused as blocked or private is carried into the saved source link

**File:** web/src/components/jobs/add-job.tsx:93
**Found:** 2026-11-10 by /audit independent (scope: current; lens: security)
**Why it matters:** After `fetch_blocked` (for example a private address), "Paste the text instead" sets `finalUrl` to the typed link, which is sent as `url` on save, stored, and shown as "Open the original posting" with a clickable link (http and https only, `rel="noopener noreferrer"`, server revalidated). This matches the spec ("a link kept when switching to paste") and only the signed-in user sees it, so it is not exploitable; but a private or localhost address stored as a job source is of no use and the spec does not record the choice for blocked links.
**Suggested fix:** Keep the link only when the failure was not `fetch_blocked`, or record the decision in the spec.

### F-125 [P3] open - Tests cover only the pure view model; the add state machine and row behavior have no test

**File:** web/tests/jobs-view.test.ts:1
**Found:** 2026-11-10 by /audit independent (scope: current; lens: tests)
**Why it matters:** `jobs-view.test.ts` covers form checks, link safety, labels and copy well, but the repository has no DOM test library, so nothing exercises the add flow (link, refusal, paste, confirm, duplicate), the single-mutation rule, the delete question focus, the cache invalidation or the failed-load handling; these rest on the manual browser pass recorded in the spec. Two assertions are weak: the paste-instead test accepts "try again" as proof of a paste hint, and the date test has no clock-change case (F-120).
**Suggested fix:** Accept as a documented gap for this repo, or extract the add flow into a small reducer in `jobs-view.ts` with tests; tighten the assertion to require "paste" for every `PASTE_INSTEAD` code except `fetch_failed`.

### F-126 [P3] open - A stray `<` followed by a letter in an HTML paste drops the words up to the next `>`

**File:** engine/src/engine/jobs/posting_guard.py:417
**Found:** 2026-11-11 by /audit (scope: current; lens: performance, with the repair re-read for correctness)
**Why it matters:** The scanner reads `<y then pay more.</p>` as a tag, as a browser does, so text such as "if x<y then pay more." loses "y then pay more." from the saved posting when the paste is treated as HTML. With no later `>`, everything after it is dropped. Reproduced with `clean_posting("<p>Salary if x<y then pay more.</p><p>Second line stays</p>")`, which returns "Salary if x" then "Second line stays". Rare in real postings; the browser-faithful rule is what keeps hidden text from being revealed.
**Suggested fix:** Accept as a documented trade-off, or keep the dropped span in the counts so a user can see that text was removed. Decide with feature 8 when postings are read next to the profile.
**Resolution:**

### F-132 [P3] open - Log-leak test covers only the success path

**File:** engine/tests/test_job_screen.py:180, engine/tests/test_job_screening.py:276
**Found:** 2026-11-11 by /audit independent (scope: current; lens: tests)
**Why it matters:** Both "no posting text is logged" tests use a reply that parses. The gateway logs a `reason` when a reply is rejected, and the failure branches in `screening.py` (unavailable, invalid) are never run under `caplog`, so a leak on those paths would pass. The module also imports the private `_clean` from `engine.cv.parse`.
**Suggested fix:** Run the invalid-reply and unavailable paths under `caplog` and assert no posting or dealbreaker text; expose `_clean` under a public name.
**Resolution:** Partly (2026-11-11): failure-path log tests added for the screen task and the service. The private `_clean` import from `engine.cv.parse` stays: `tracks/preferences.py` does the same, so moving it is a separate cleanup. Left open.

### F-168 [P2] open - Project docs and the build plan still say evaluation "reads importance from the posting first"

**File:** blueprint/context/project-overview.md:43
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality)
**Why it matters:** The fix's decision is that the app never claims the posting states importance, yet blueprint/context/project-overview.md:43 (feature 8 summary, the Data and workflow source for later audits), blueprint/build-plan.md:49 and :51, docs/ai-workflows.md:39 and docs/reference-study.md:103 and :122 still describe the evaluation as reading importance from the posting first with inferred importance capped. The code at the target no longer does either: importance is the model's guess, capped at `important`. Future specs (8d golden set, the Fit step) will be written against a false contract.
**Suggested fix:** Reword those lines to "importance is the model's guess, never above important; the posting is not read for must-haves". Delete nothing else.
**Resolution:**

### F-169 [P3] open - The band, summary and web comments still describe must-haves the posting states, and the must branches are now unreachable

**File:** engine/src/engine/jobs/eval_band.py:30
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality)
**Why it matters:** `core()` docstring says "The must-haves; when the posting states none, the important ones" and `summary()` gives "Evidence for 6 of 7 must-haves" as its example (eval_band.py:30 and :72), `Judged.importance` comment lists `must` (:22), and web/src/lib/jobs-api.ts:171 repeats the "6 of 7 must-haves" example for a sentence the engine can no longer produce (it now reads "Evidence for N of M important requirements"). In `band_for` the `musts_decide` / `important_gap` path (:52-54) and the `musts` branch in `core` can never run, because no `must` is produced; no test of production input reaches them. The spec chose to keep this code, so this is a stale-comment and unreachable-path note, not a defect in the band. The marketing copy "6 of 7 must-haves evidenced" (web/src/components/home/Sections.tsx:106, HeroDemo.tsx:122) now promises wording the product never shows. Also quotes.py:13-19 (`fold` keeps line breaks "for readers of the folded text") describes the deleted readers; no reader remains.
**Suggested fix:** Update the docstrings and comments to the important-requirements wording; leave the code as the spec says. Reword the homepage example to match the real sentence or leave it as a decision for the founder. None lost.
**Resolution:**

### F-170 [P3] open - An evaluation saved before this change is still served as `must` / posting-stated and as current

**File:** engine/src/engine/jobs/evaluating.py:83
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality, security)
**Why it matters:** Probed `RequirementOut.model_validate` with an old row (`importance: "must"`, `importance_source: "posting"`): it validates, drops the extra key and returns `importance: "must"`. `_out` computes `stale` only from profile id/version and the rules key, not from the prompt version, so such a row (band and "of N must-haves" summary decided by posting-read musts) is listed as current and not re-evaluated until the profile or rules change, although the cache key now includes `eval-extract-3`. The web `Importance` type no longer allows `must`, so the type is wrong for that data. No UI renders importance yet, so nothing user-visible breaks today; development data only.
**Suggested fix:** None needed if no real rows exist; otherwise treat a row whose cache key no longer matches as stale, or reset the Evaluation table. Requirement lost: none.
**Resolution:**

### F-172 [P3] open - Report totals are rounded to whole cents, so a small total shows "$0.00" while its own rows show a price

**File:** engine/src/engine/ai/usage_report.py:229
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness)
**Why it matters:** `total_cost_usd`, `cache_savings_usd` and `compare.estimate_usd` are quantized to $0.01, but the per-workflow and per-row figures keep six places, and the page formats anything under a cent with four ("never a bare zero"). Reproduced with two priced `screen` calls at $0.001 and one cache hit: the workflow shows cost $0.002000, the row shows savings $0.001000, and the report totals are `0.00`, so the "Cost" and "Saved by the cache" tiles read "$0.00" and "Every call has a price" next to a table that shows $0.0020. The same happens to the paid-model estimate with small usage. A roll-up that disagrees with the rows it sums is the kind of mistake F-171 was; the spec says "to cents" for money, but not at the cost of a nonzero amount reading as zero.
**Suggested fix:** Keep the totals at six places (the page's `usd()` already formats for people), or round only when the value is at least one cent.
**Resolution:**

### F-173 [P3] open - A workflow or row whose calls were all rejected shows "Unknown" for the average although every price is known

**File:** engine/src/engine/ai/usage_report.py:131
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness)
**Why it matters:** The average counts only `ok` calls with a price, so a row with only rejected (priced) calls has `avg_cost_usd = None`, and the page prints "Unknown" in "Per call" with `unknownCostCalls` 0 and a real cost beside it. Reproduced with two priced rejected `evaluate` calls: cost $0.040000, average `None`. This is the state a broken prompt version produces, the one staff most need to read correctly; "Unknown" contradicts the "cost unknown, never zero" rule's meaning. Cache savings for that row are also 0 for the same reason.
**Suggested fix:** Show "No usable answers" (or a dash) when `calls > 0`, nothing is unpriced and the average is null, or add a field the page can use to say so.
**Resolution:**

### F-174 [P3] open - The hiding of evaluations on a type change, and the Fit step's type filter and empty state, have no test

**File:** engine/tests/test_opportunity_kind.py:219
**Found:** 2026-11-11 by /audit independent (scope: current; lens: tests)
**Why it matters:** `test_results_for_another_type_are_hidden_not_deleted` covers screens only. The evaluation twin (`Track.kind == job.kind` in `list_evaluations`, evaluating.py:310) is exercised only with an empty list in the wrong-type test, so deleting that filter would pass every test; a saved evaluation hidden after a type change and returned after changing back is the spec's stated rule and has no assertion. On the web, the filter and the two empty-state texts live inline in `FitStep` (fit-step.tsx:127-141) and no test renders the component, so the filter by `job.kind` is untested.
**Suggested fix:** Add an engine test that inserts an evaluation (see `save_evaluation` in test_evaluation_routes.py), changes the job type, expects `[]`, changes back and expects the same row; move the track filter and the empty-state choice into a pure function in `fit-view.ts` and test it.
**Resolution:**

### F-175 [P3] closed - After adding a track in Profile, the Fit step can still show "Add a ... track" for up to 30 seconds

**File:** web/src/components/jobs/fit-step.tsx:60
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness)
**Why it matters:** The Fit step reads tracks under the key `['fit-tracks']` while the Profile page creates and invalidates `['tracks']` (profile.tsx:165, :173). The query client has `staleTime: 30_000` (router.tsx:7), so returning to the job within 30 seconds of adding the matching-type track serves the cached list and repeats the empty state that sent the person to Profile. The new empty state makes this the main path for gig and AI training jobs. Evidenced by reading the keys and config; not run in a browser.
**Suggested fix:** Use the same `['tracks']` key in the Fit step, or invalidate `['fit-tracks']` where tracks change.
**Resolution:** Not reproduced in a browser on 2026-11-11: after adding a matching track in Profile and returning to the job through the app's links, the Fit step listed the new track. The cache window may have passed; the code reading still stands.
Closed 2026-11-11 by feature 11b: the Fit step and the CV and letter step now read tracks under `['tracks']`, the key Profile invalidates; the independent review of 11b (9e21309) confirmed both use the same query and data.

### F-176 [P3] open - The Fit step's empty state reads "This is a ai training role"

**File:** web/src/components/jobs/fit-step.tsx
**Found:** 2026-11-11 in a browser check of feature 34 (job set to AI training role, no matching track)
**Why it matters:** The sentence is built as "This is a ${label in lower case}", so the AI training role gives "a ai training role" and "Add a ai training role track". It is wrong English and shows an acronym in lower case.
**Suggested fix:** Word it without an article, for example "This job is marked as AI training role, and a track only checks its own kind of work. Add a track of that kind in your profile." Keep the label's own case.
**Resolution:**

### F-185 [P2] open - The number check still passes a figure whose percent, magnitude or currency is written in a form it does not read: "35 %", "35 pc", "10 lakhs", "10 millions", "10 mln", "10万", "KES 130,000"

**File:** engine/src/engine/jobs/kit_check.py:19
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security, correctness)
**Why it matters:** The docstring says a percent sign after the digits, attached letters, and "a currency sign" are part of the number, so `35%`, `10bn` and `$10` differ from a plain figure. Reproduced with `numbers_in` and `check_block`: `35 %` (space before the sign), `35 pc`, `35‰`, `10×` all read as plain `35` / `10`; `10 lakhs`, `10 crores`, `10 lacs`, `10 millions`, `10 mln`, `10 bln`, `10 Millionen` (plurals and neighbours of listed words, so the list is finite as documented but the gap is the plural of words it does list) read as `10`; attached non-ASCII letters are dropped although the comment says attached letters are always kept (`10万`, `10млн` read as `10`); a currency written as a code or a name (`KES 130,000`, `Ksh 10`, `USD 10`, `R10`) reads as the bare digits, because only `$ € £ ¥ ₹` are signs. A cited fact "Led 35 engineers; served 10 users" passes the blocks "Grew revenue 35 % in a year", "Managed 10 lakhs of users" and "Paid KES 35 for 10 users" with no flag. The finite list is a stated limit; these are cases the docstring's own wording (percent sign, attached letters, currency) promises, or plurals of a word the list names. Weight is P2 because the person sees `sources` and reads the text, the model writes English from English facts, and the digits still must appear in a cited fact.
**Suggested fix:** Read `\s?%`, `\s?pc` and `‰` as a percent; match unit words with an optional plural `s` (and `mln`, `bln`, `lakhs`, `crores`); keep any attached `\w` letters, not only `[a-z]`; read an ISO or common currency code or `KSh` before or after the digits as part of the number (or say in the docstring that only the listed signs are read); add the cases as tests.
**Resolution:**

### F-186 [P3] open - Digits split by an invisible mark, a fraction or a date-like hyphen are read as separate numbers, so a block can show a figure no fact states

**File:** engine/src/engine/jobs/kit_check.py:68
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security)
**Why it matters:** `_clean` removes control and format characters (so a zero-width space is gone) but not combining or variation marks. Reproduced: with a cited fact "Cut costs by 2 teams, 5% faster", the block "Cut cost 2͏5% faster" (a combining grapheme joiner, or U+FE0F, between the digits, which display as `25%`) passes with no flag, while the plain "25%" is flagged. A hostile posting can ask the model for such text. Also `numbers_in("1000-12")` is `["1000"]`: any four digits followed by `-01` to `-12` is taken as a date and the second figure is dropped, so "Handled 1000-12 sites" passes against a fact that says only "1000". Fractions: NFKC turns `½` into `1⁄2`, read as `1` and `2`, so it passes against facts that state a 1 and a 2. None of these is in the docstring's list of limits.
**Suggested fix:** Drop combining and variation marks (categories Mn, Me, and U+FE0F) in `numbers_in` and in the block text, or flag any block whose digits are separated by a non-space, non-punctuation character; read a `YYYY-MM` as a date only when it is a plausible year; name fractions in the docstring.
**Resolution:**

### F-187 [P3] open - The kit never uses the track, and the spec's "track rules" are not in the cache key, so every track of a job gets an identical, separately paid kit

**File:** engine/src/engine/jobs/kitting.py:104
**Found:** 2026-11-11 by /audit independent (scope: current; lens: quality, performance)
**Why it matters:** The spec says a kit is for one job and one track and that a change of track rules makes a new version. `_cache_key` holds the posting, profile id and version, facts hash, questions and prompt version only, and no prompt (`kit_write.py`) carries the track's name or rules; the track only filters stored rows and the type check. Two tracks of one type therefore each trigger their own strong-tier calls with identical input (the gateway cache only helps within its own window), and a change to a track's rules neither re-runs nor changes the kit. Not a security issue; either the track is meant to shape the writing (then it is missing) or the spec wording is wrong. Also `parent` (the achievement's experience) is not in `_facts_hash`, so moving an achievement to another job reuses a kit whose bullets were checked against the old anchors.
**Suggested fix:** Decide whether the track's rules reach the prompt. If so, send them and put them in the key; if not, reword the spec and note that tracks share a kit. Add `parent` to `_facts_hash`.
**Resolution:**

### F-188 [P2] open - An open edit box survives a Remove of another statement; the paths shift and Save overwrites a different statement

**File:** web/src/components/jobs/kit-step.tsx:333
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness)
**Why it matters:** `Document` keeps `editing = {path, text}` in its own state and never clears it when the version changes (`change.onSuccess` only resets `picked`; `Document` has no `key`). While one statement is open for editing, the Edit and Remove buttons of every other statement stay visible. Edit `entries.1.bullets.3`, then Remove `entries.1.bullets.1` on the same page: the engine saves a new version in which the old bullet 4 is now `entries.1.bullets.3`, the open textarea still holds the old bullet 3's text, and Save sends `edit` for `entries.1.bullets.3`, so the person's text silently replaces a different statement (the former bullet 4). The same stale path applies after any version change (a write again, a reload after 409). Evidenced by reading the component state flow; not run in a browser.
**Suggested fix:** Clear `editing` whenever `version.id` changes (give `Document` `key={shown.id}`), or hide Edit and Remove on all other statements while one is being edited; send the version's own statement text check (or the old text) with the path if a stronger guard is wanted.
**Resolution:**

### F-189 [P2] open - The typed edit is thrown away before the save succeeds, so a refused or failed save loses the person's text

**File:** web/src/components/jobs/kit-step.tsx:324
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness)
**Why it matters:** `onSave` calls `onChange(...)` (which starts the mutation) and immediately `setEditing(null)`. If the engine answers `invalid_edit` (for example text over the block's cap: the textarea has no `maxLength` or counter, and the summary, bullet, paragraph and answer caps differ), `not_latest`, or the network fails, the page shows "Check the text and try again" while the text the person wrote is gone and the statement shows the old wording. Long cover letter paragraphs make an over-cap save plausible.
**Suggested fix:** Close the editor in the mutation's `onSuccess` and keep the text on error; show the cap in the textarea (`maxLength` or a counter) using the engine limits.
**Resolution:**

### F-190 [P3] open - Once an answers document exists, the question box cannot be emptied, so "write again" always re-sends the old questions

**File:** web/src/components/jobs/kit-step.tsx:158
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness)
**Why it matters:** `questionsValue` falls back to the saved answers' questions whenever the local `questions` state is `''`. A person who deletes all text to write the kit again without questions sees the old questions reappear, and `startWriting` sends them, so an answers document is written (and paid for) again. Evidenced by reading; not run in a browser.
**Suggested fix:** Track "touched" separately from the value (null until the person types), so an empty string is a real choice.
**Resolution:**

### F-191 [P3] open - Edit and Remove buttons share one name for every statement, and focus is lost after Save, Cancel and Remove

**File:** web/src/components/jobs/kit-step.tsx:392
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness, accessibility)
**Why it matters:** A screen reader lists many buttons named only "Edit" and "Remove" with no statement named; Remove has no confirmation and no live announcement of the result. Pressing Edit does not move focus into the textarea, and when Save, Cancel or Remove unmounts the focused button, focus drops to the page body. Saving also has no `role="status"` message.
**Suggested fix:** Give each button an `aria-label` that names the statement (for example "Edit statement in Summary"), focus the textarea on Edit and the statement or its Edit button after Save or Cancel, and announce a save or removal in a status region.
**Resolution:**

### F-192 [P3] open - The recheck never looks at a CV's skills (or entry headings), so a skill whose fact is gone or edited stays listed unflagged

**File:** engine/src/engine/jobs/kit_edit.py:123
**Found:** 2026-11-11 by /audit independent (scope: current; lens: correctness)
**Why it matters:** The spec says the whole document is checked again from the facts of the version's own profile that are still confirmed or edited. `recheck` copies `skills` through untouched: with the skill fact removed from the facts, the saved version still lists `{"name": "Flutter"}` and reports `flagged: 0` (reproduced with `recheck` on the test CV). The skills line shows the old fact wording, and `omitted` is not raised. The skills are not editable or removable either, so a person cannot fix the line. Entries whose own fact is gone keep their heading but their bullets are flagged `off_entry`, which hides the cause.
**Suggested fix:** Drop skills (and count them in `omitted`) whose fact id is no longer among the facts, or flag them; refresh the name from the fact's current text.
**Resolution:**

### F-193 [P3] open - The path pattern ends in `$`, which accepts a trailing newline: `entries.1.bullets.1\n` is applied

**File:** engine/src/engine/jobs/kit_edit.py:28
**Found:** 2026-11-11 by /audit independent (scope: current; lens: security)
**Why it matters:** `re.match` with `$` matches before a final newline, and `int("1\n")` succeeds, so a path with a trailing newline is accepted as the statement `entries.1.bullets.1` (reproduced with `apply_edit`; `paragraphs.1\n` and `summary\n` fail later only by luck of the checks). The raw path also goes into the cache-key material, so equal edits with different paths get different keys. No data exposure; it is a validation looseness in a function whose job is a strict path grammar.
**Suggested fix:** Use `re.fullmatch` with `[0-9]` instead of `\d` (which also reads other Unicode digits), and add a test for a trailing newline.
**Resolution:**
