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
