# Feature: Production deploy

**From build-plan:** feature 28b
**Build attempt:** 1
**Branch:** feature/production-deploy
**Status:** verified

## Goal

Everything needed to put Jobmigo on one small VPS behind Cloudflare is in the
repository, built and tested locally: a production build that runs on plain Node,
a production Docker image that applies database migrations before it starts, a
Compose stack with Caddy for HTTPS, nightly encrypted Postgres backups to object
storage with a tested restore, a one-command deploy and rollback, and a runbook
for the steps only the founder can do (domain, server, DNS, accounts). After this
feature, going live is following `docs/deploy.md`, not engineering.

## In scope

- **Production server:** the TanStack Start app built for Node with the documented
  Nitro path (`.output/server/index.mjs`, started with `npm start`).
- **Image:** a multi-stage production `web/Dockerfile` (dev image moves to
  `web/Dockerfile.dev`), a migration runner that works without dev dependencies, a
  non-root user and a health check.
- **Stack:** `deploy/docker-compose.prod.yml` (db, web, Caddy), `deploy/Caddyfile`
  (automatic HTTPS, security headers, optional Cloudflare-only guard),
  `deploy/.env.production.example`.
- **Backups:** `deploy/backup.sh`, `deploy/restore.sh`, a systemd timer or cron
  entry, 30-day retention, encryption with `age`, upload with `rclone`.
- **Deploy:** `deploy/deploy.sh` (update, build, migrate, restart, wait for healthy,
  roll back on failure) and `docs/deploy.md`, the step-by-step runbook.
- **Review finding F-11:** the waitlist limiter checks the per-IP limit before the
  global one, so rejected requests cannot spend the global budget.

## Out of scope

- Doing the founder's steps: buying the domain, creating the server, Cloudflare,
  Resend and object-storage accounts, DNS records. The runbook lists them with exact
  values; nothing here can be run without those accounts.
- Verifying TLS, Cloudflare behaviour and real email delivery. Those are checked on
  the real server using the runbook's verification checklist.
- CI/CD, a container registry, multiple nodes, a managed database, error tracking,
  metrics, a worker process, a CDN configuration beyond the runbook.
- The other open P3 findings (F-16 to F-22) except where they touch files changed
  here.

## Build loop

`workflow.stepReview` is `feature`: build all steps in order, run the narrow check
for each, run the full gate once at the end, then present one review packet.
`workflow.checkpointCommits` is disabled; `/complete` makes the commit.

## Build steps

- [x] **1. Production server build and F-11.**
  Add the `nitro` Vite plugin per the TanStack Start hosting guide (check the
  installed package names and exports first) and a `start` script
  (`node .output/server/index.mjs`). Keep `npm run dev` working. Add `.output` to
  `.gitignore`. Fix F-11 in `src/server/waitlist-api.ts`: take the per-IP limit
  first, then the global one, so a request the per-IP limit rejects does not spend
  the global budget; add tests for the order.
  *Done when:* `npm run build` produces `.output/server/index.mjs`; with the
  database running and `ENVIRONMENT=production`, `npm start` serves `/healthz`,
  `/readyz`, `/` (with the share tags), `/favicon.svg`, `/og.png`, the confirm page,
  and a waitlist join returns the success message (the send fails loudly in the
  log because no mail key is set, and no address appears in the log); the global
  budget is not spent by per-IP rejections (test); `npm run lint`, `typecheck` and
  `npm test` pass and the dev server still starts.

- [x] **2. Migration runner and production image.**
  Rename the current `web/Dockerfile` to `web/Dockerfile.dev` and point the dev
  compose service at it. Add `web/scripts/migrate.mjs` (plain ESM, uses
  `drizzle-orm/node-postgres/migrator` and the `drizzle/` folder, reads
  `DATABASE_URL`, exits non-zero on failure) and a new multi-stage `web/Dockerfile`:
  build stage with all dependencies runs `npm run build`; the final stage is
  `node:22-slim`, copies only `.output`, `drizzle/`, `scripts/migrate.mjs` and the
  production dependencies that script needs, runs as a non-root user, sets
  `NODE_ENV=production`, defines `HEALTHCHECK` against `/readyz`, and starts with an
  entrypoint that runs the migration and then the server. Tighten
  `web/.dockerignore` (no `.env`, tests, `node_modules`, `dist`).
  *Done when:* `docker build` succeeds; the container against an empty database
  applies all migrations and `/readyz` returns ok; starting it again applies
  nothing and still starts; a bad `DATABASE_URL` makes the container exit non-zero
  with a clear message; `docker run ... id` shows a non-root user; the image
  contains no `.env`, tests or dev dependencies (checked with `docker run ... ls`);
  the dev compose stack still builds and starts.

- [x] **3. Production stack: Compose, Caddy, headers.**
  Add `deploy/docker-compose.prod.yml` with `db` (Postgres 17, named volume, no
  published port, healthcheck), `web` (the production image, `restart:
  unless-stopped`, env from `.env.production`, depends on a healthy db, no published
  port) and `caddy` (official image, the only service publishing 80 and 443, a
  volume for certificates). Add `deploy/Caddyfile` with the site address from
  `SITE_ADDRESS`, reverse proxy to `web:3000`, gzip and zstd, and headers
  (`Strict-Transport-Security`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`,
  `Permissions-Policy` denying camera, microphone and geolocation). Add an optional
  guard: when `CLOUDFLARE_ONLY=true`, requests whose remote address is not in
  Cloudflare's published ranges get 403; the ranges live in
  `deploy/cloudflare-ips.caddy` fetched from `https://www.cloudflare.com/ips-v4`
  and `ips-v6` with the fetch date in a comment, and
  `deploy/update-cloudflare-ips.sh` regenerates it. Add
  `deploy/.env.production.example` (every variable with a comment, none with a real
  value, `ENVIRONMENT=production`, `TRUST_PROXY_HEADERS=true` only together with
  `CLOUDFLARE_ONLY=true`).
  *Done when:* `docker compose -f deploy/docker-compose.prod.yml config` is valid;
  locally with `SITE_ADDRESS=:80` and `CLOUDFLARE_ONLY=false`, the stack starts, the
  web container becomes healthy, `curl` through Caddy returns the homepage and
  `/healthz`, the response carries the security headers, ports 3000 and 5432 are
  not reachable from the host, and `CLOUDFLARE_ONLY=true` returns 403 to a local
  request; the Cloudflare ranges file is generated by the script and parses with
  `caddy validate`.

- [x] **4. Backups and restore.**
  Add `deploy/backup.sh`: `pg_dump` of the production database inside the db
  container, gzip, encrypt with `age` to `AGE_RECIPIENT`, upload with `rclone` to
  `BACKUP_REMOTE`, delete remote backups older than 30 days, exit non-zero on any
  failure, never print secrets. With no `AGE_RECIPIENT` the script refuses to run
  unless `ALLOW_UNENCRYPTED_BACKUP=true` (local testing only). Add
  `deploy/restore.sh` (download or read a file, decrypt with `AGE_IDENTITY_FILE`,
  restore into a named scratch database by default and into the live database only
  with an explicit `--into-live` flag after a typed confirmation) and a systemd
  timer and service pair (`deploy/jobmigo-backup.timer`, `.service`) running daily
  at 02:30 server time, plus a cron line as an alternative in the runbook.
  *Done when:* a local drill creates waitlist rows, runs `backup.sh` to a local
  `rclone` remote, restores into a scratch database with `restore.sh`, and the row
  counts and a sample row match; an `age`-encrypted run is exercised when `age` is
  installed (otherwise reported as not run); `backup.sh` exits non-zero when the
  database is unreachable, when `rclone` fails, and when no recipient is set
  without the override; `restore.sh` refuses `--into-live` without the typed
  confirmation; `bash -n` passes on every script and `shellcheck` passes when
  installed.

- [x] **5. Deploy script and runbook.**
  Add `deploy/deploy.sh`, run on the server from the repository checkout: records
  the current commit, `git pull --ff-only`, builds the image, brings the stack up,
  waits for the web healthcheck (timeout 120 seconds), prints the deployed commit
  and `/readyz` result, and on a failed health check checks out the previous commit
  and restarts it, exiting non-zero. A `--dry-run` flag prints each command without
  running it. Write `docs/deploy.md`: the founder's checklist in order, with the
  exact values to use: buy the domain; Cloudflare DNS (A record proxied, SSL mode
  Full (strict)); create the server (size, firewall allowing only 22, 80 and 443,
  SSH keys only, a non-root user, unattended upgrades); install Docker; clone the
  repository; create `.env.production` from the example with generated secrets;
  Resend domain verification records (SPF, DKIM) and `MAIL_FROM`; Cloudflare Email
  Routing for the contact address; object-storage bucket and `rclone` remote; `age`
  key pair (keep the private key off the server); first deploy; the verification
  checklist (HTTPS and certificate, headers, homepage and share card in the LinkedIn
  Post Inspector, a real waitlist join with confirmation email delivered, unsubscribe,
  `/readyz`, one backup and one restore drill); an uptime monitor on `/healthz`;
  routine deploys; rollback; and what to do when something fails. Update
  `AGENTS.md` with the deploy commands.
  *Done when:* `deploy.sh --dry-run` prints the expected sequence; a local run of
  `deploy.sh` against the local production stack (using a test checkout) deploys,
  waits for healthy and reports the commit, and a forced unhealthy build rolls back
  to the previous commit and exits non-zero; every command and file path in
  `docs/deploy.md` exists or is a documented external step (checked by reading it
  against the scripts); `bash -n` and, if installed, `shellcheck` pass.

- [x] **6. Docs, env and final gate.**
  Update `docs/technical-design.md` section 15 (production layout, backups, deploy,
  the `TRUST_PROXY_HEADERS` and `CLOUDFLARE_ONLY` rule), `.env.example` and the
  findings ledger (F-11 `fixed` only after its tests pass).
  *Done when:* the `Verify` command from `AGENTS.md` passes in `web/`, `docker
  compose config` is valid for both the dev and production files, and no file
  outside `blueprint/history/` mentions a removed path (`web/Dockerfile` as the dev
  image).

- [x] **7. Review repairs: F-23 to F-29 and F-32.**
  Repair the two P1 and the P2 findings from the independent review, plus the
  cheap P3s, as a user-visible change to the earlier contracts:
  (F-23) `restore.sh` always restores into a scratch database first with a single
  transaction and `ON_ERROR_STOP`; `--into-live` additionally checks the age
  identity file up front, requires the web container to be stopped, takes the typed
  confirmation, and only after the scratch restore succeeded swaps it in by renaming
  databases, keeping the old live database as `jobmigo_before_restore_<time>`. A
  failed fetch, decrypt or restore leaves the live database untouched.
  (F-24) The runbook and example generate secrets with `openssl rand -hex 24`;
  `deploy.sh` refuses a `POSTGRES_PASSWORD` that is not URL-safe
  (`[A-Za-z0-9._~-]+`).
  (F-25) `deploy.sh` keeps the last two good commits (`deploy/.last-good-commit` and
  `deploy/.previous-good-commit`); `--rollback` redeploys the previous one.
  (F-26) The ufw Cloudflare-range loop is removed from the runbook (Docker bypasses
  ufw); `CLOUDFLARE_ONLY` is the control, with an optional provider-level firewall
  noted.
  (F-27) The Caddy files move to `deploy/caddy/` and the directory is mounted;
  `deploy.sh` reloads Caddy after starting the stack; `update-cloudflare-ips.sh`
  validates CIDRs and refuses an empty or malformed list; the runbook says to run it
  on a laptop, commit, push and deploy.
  (F-28) The web container exits when `TRUST_PROXY_HEADERS=true` and
  `CLOUDFLARE_ONLY` is not `true` (compose passes both), and `deploy.sh` checks the
  same before starting.
  (F-29) The runbook gives the real restore drill commands on the server.
  (F-32) The migration dependencies are installed at the exact versions the lockfile
  resolved, and the web service gets `no-new-privileges` and `cap_drop: [ALL]`.
  *Done when:* local drills show: a restore with a wrong object name, an unset
  identity file for an `.age` object, or a corrupt file leaves the live database
  untouched; `--into-live` refuses while web is running and without the typed
  confirmation; a good `--into-live` swaps databases and keeps the old one; a
  `POSTGRES_PASSWORD` containing `/` is refused by `deploy.sh`; a deploy of A, then a
  healthy deploy of B, then `--rollback` returns to A; the web container exits with a
  clear message for `TRUST_PROXY_HEADERS=true` without `CLOUDFLARE_ONLY=true` and
  `deploy.sh` refuses it earlier; the Cloudflare guard still returns 403 and Caddy
  reloads after the ranges file changes without recreating the container;
  `update-cloudflare-ips.sh` rejects a malformed list; the web service shows
  `no-new-privileges` and dropped capabilities and still becomes healthy; shellcheck
  and `bash -n` pass; both compose files are valid; `Verify` passes.

## Files / areas

- `web/vite.config.ts`, `web/package.json`, `web/Dockerfile` (production),
  `web/Dockerfile.dev` (renamed), `web/.dockerignore`, `web/scripts/migrate.mjs`,
  `web/src/server/waitlist-api.ts` and its tests, `.gitignore`.
- `deploy/` (new): `docker-compose.prod.yml`, `caddy/Caddyfile`, `caddy/cloudflare-ips.caddy`,
  `update-cloudflare-ips.sh`, `.env.production.example`, `backup.sh`, `restore.sh`,
  `jobmigo-backup.service`, `jobmigo-backup.timer`, `deploy.sh`.
- `docker-compose.yml` (dev compose points at `Dockerfile.dev`), `docs/deploy.md`
  (new), `docs/technical-design.md`, `AGENTS.md`, `.env.example`.

## Data / contracts

- **Production env (on the server only, file mode 600, never in git):**
  `ENVIRONMENT=production`, `DATABASE_URL`, `POSTGRES_PASSWORD`,
  `BETTER_AUTH_SECRET` (at least 32 random bytes), `BETTER_AUTH_URL` and
  `PUBLIC_URL` (the https site URL), `SITE_ADDRESS` (the domain), `RESEND_API_KEY`,
  `MAIL_FROM`, `CONTACT_EMAIL`, `TRUST_PROXY_HEADERS`, `CLOUDFLARE_ONLY`, backup
  variables (`BACKUP_REMOTE`, `AGE_RECIPIENT`). The restore identity file path is
  an argument or variable on the machine doing the restore, never on the server by
  default.
- **Trust boundary:** the database and the app are not published on the host; only
  Caddy listens. `TRUST_PROXY_HEADERS=true` is allowed only with
  `CLOUDFLARE_ONLY=true`, which makes direct-to-origin requests 403; Docker bypasses host firewalls, so a
  provider-level firewall restricted to Cloudflare's ranges is an optional extra
  (step 7). Secrets are never printed by any script. Backups contain personal data
  (waitlist emails) and are always encrypted before they leave the server.
- **Image contract:** listens on port 3000 as a non-root user; `/readyz` is the
  readiness check; the entrypoint applies migrations first and does not start the
  server if they fail.
- **Backup contract:** one `jobmigo-<UTC timestamp>.sql.gz.age` object per run in
  `BACKUP_REMOTE`; retention 30 days; restore defaults to a scratch database.
- **Rollback contract:** the previous commit hash is recorded before any change;
  database migrations are forward-only, so a rollback restores the previous code
  and a destructive migration must ship with a restore note in its feature.

## Testing

Script and image behaviour is verified locally with Docker, `curl` and the drills
named in each step; application logic changes (the F-11 order) have Vitest tests.
Commands in `web/`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run
build`. No live TLS, Cloudflare, Resend or object-storage check is claimed; the
runbook's verification checklist covers those on the real server. No browser test
harness is configured.

## Notes for the AI

- Check the installed TanStack Start and Nitro packages and the hosting guide
  (`https://tanstack.com/start/latest/docs/framework/react/guide/hosting`) before
  writing the build config; the documented path is `nitro()` in the Vite plugins
  with `.output/server/index.mjs`.
- Fetch the Cloudflare IP lists at implementation time; do not guess ranges.
- Keep scripts portable bash with `set -euo pipefail`, quote variables, and print
  what they are doing without secrets.
- Do not publish anything or contact any external service from the build: no
  Cloudflare, Resend or storage calls. `rclone` is exercised only against a local
  directory remote.
- Resolve the first-deploy details in `docs/deploy.md` honestly: where a price, a
  limit or a provider UI step may have changed, mark it "verify".

## Open questions

- Database location: this spec keeps Postgres on the same server with encrypted
  nightly backups (the plan's choice). A managed database would only change
  `DATABASE_URL` and remove the `db` service; confirm you are happy with
  self-hosting at launch size.
- Server provider and region, and the exact domain, are the founder's decisions
  made while following the runbook; nothing in the build depends on them.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":17361,"specSha256":"1290545f37ef371a603302b85d43827af655b2f607a205d52466464583321d94","branch":"refs/heads/feature/production-deploy","head":"b1de666dda67cfbcc98c4683abf7928a978400a7","baseRef":"refs/heads/main","baseCommit":"e84d1430b2af73610a8f2fc76821738ef8eceb65","sourceTree":"867ec80a8a7e1081704a313e792b808af1dd8a49","landing":"local-merge","absentOptional":[]} -->

## Findings

### 28b/F-11 [P2] closed - Join rate limit key is spoofable, shared when absent, and the map is unbounded

**File:** web/src/server/waitlist-api.ts:24, web/src/server/rate-limit.ts:12
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** `clientIp` trusts `cf-connecting-ip`, then the first `x-forwarded-for` entry, from any caller. Where no proxy overwrites them, a client rotates the header to get a fresh 5-per-10-minutes bucket per request, so the limit that protects the sender domain from being used to mail arbitrary addresses is bypassed. With no header at all every visitor shares the single `unknown` bucket, so five joins in ten minutes lock out all real users. Each distinct key adds a map entry; the sweep runs only above 10,000 entries and removes only expired ones, so a rotating-header flood grows memory for the window and costs an O(n) scan per request. The spec defers header trust to 28b, but the code ships with no fail-closed behaviour and no test for the absent-header case.
**Suggested fix:** Decide the trusted source in 28b and read only that header (for Caddy behind Cloudflare, `cf-connecting-ip`, and ignore `x-forwarded-for`). Do not fall back to a shared bucket silently: log a warning or use a stricter global cap. Hard-cap the map size (reject or evict oldest). Must land before the public launch.
**Resolution:** Feature 28b: `handleJoin` takes the per-IP limit first, then the global one, so requests the per-IP limit rejects no longer spend the global budget (test added); `TRUST_PROXY_HEADERS` is documented as safe only together with `CLOUDFLARE_ONLY=true`, which Caddy enforces.
Re-examined 2026-11-07 by independent review (28b4397): the original defects are gone (`x-forwarded-for` never read, `cf-connecting-ip` only with `TRUST_PROXY_HEADERS=true`, no shared `unknown` bucket, keys hard-capped at 10,000 with expired-first then oldest eviction, tests for each). The repair adds a new defect, so this is reopened rather than closed: `handleJoin` (`waitlist-api.ts:56-58`) takes from the global limiter BEFORE the per-IP limiter, and before the email is validated. A single address that is already over its own 5-per-10-minutes limit still spends the global budget on every rejected request, so 60 requests from one client lock every visitor out of the waitlist for 10 minutes. The per-IP limit therefore does not isolate abusers even when the header is trusted, and the global cap becomes a cheap denial of service. Fix: check the per-IP limiter first and only spend a global token for requests that pass it (and ideally after the honeypot/validation checks); add a test that a limited IP does not consume global tokens.
Closed 2026-11-07 by independent review of e84d143..ea5904f: `waitlist-api.ts:54-58` now takes the per-IP token first and the global one only for requests that pass it. The new test (`waitlist-api.test.ts:135`, one unit of a 3-token global budget, 20 rejections, then two other IPs succeed) fails against the old order, so it proves the fix. Remaining: the global token is still spent before email validation, which a single IP can do at most five times per window; accepted as part of the design, no new defect introduced.

### 28b/F-23 [P1] closed - restore.sh --into-live drops the live database before checking the backup or the key

**File:** deploy/restore.sh:48
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** With `--into-live` the script terminates connections, runs `drop database jobmigo` and recreates it empty (lines 48-49) BEFORE the source is read or decrypted (line 54). A wrong object name, an unset or wrong `AGE_IDENTITY_FILE` (checked only inside `decrypt`, which runs afterwards), a missing `rclone` remote or a truncated download all leave the live database dropped or half-restored (psql runs without `--single-transaction`, so a mid-stream error keeps the partial data). The typed confirmation does not protect against these ordinary mistakes, and nothing takes a pre-restore dump. The runbook only says to stop web first, which the script does not check.
**Suggested fix:** For `--into-live`, first fetch, decrypt and gunzip the backup into a temp file (or restore into a scratch database and swap by rename) and verify it, check `AGE_IDENTITY_FILE` up front, require the web container to be stopped, take a safety dump of the current database, and restore with `--single-transaction`. Nothing is lost.
**Resolution:** Step 7: `restore.sh` restores into a scratch database in one transaction first and checks the identity file up front; `--into-live` also requires web stopped and the typed confirmation, then swaps by renaming and keeps the old database. Local drills: wrong object name, corrupt file, missing identity, web running and wrong confirmation all left the live database untouched; a good swap kept the old database.
Closed 2026-11-07 by independent review of e84d143..b1de666: Drilled on a scratch Postgres (prod compose db): a wrong object name and a truncated gzip both ended in 'restore failed' with the scratch database removed and the live one untouched; a good `--into-live` swapped databases and kept `jobmigo_before_restore_<time>` with the original rows. Code read: identity-file check, web-running check and typed confirmation precede any change.

### 28b/F-24 [P1] closed - The documented POSTGRES_PASSWORD generator produces values that break DATABASE_URL

**File:** deploy/docker-compose.prod.yml:28, docs/deploy.md:138, deploy/.env.production.example:2
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** The runbook and env example tell the founder to generate `POSTGRES_PASSWORD` with `openssl rand -base64 32`, and compose interpolates it unescaped into `postgresql://jobmigo:${POSTGRES_PASSWORD}@db:5432/jobmigo`. Base64 uses `/` in roughly half of 32-byte outputs; `pg-connection-string` throws `Invalid URL` on such a URL (reproduced with a stand-in value). The first deploy then fails at migration. Worse, the Postgres volume has already been initialised with that password, so fixing `.env.production` afterwards changes nothing for the database and the founder must discover that the volume has to be wiped. Following the runbook as written fails about half the time.
**Suggested fix:** Generate URL-safe secrets (`openssl rand -hex 24`) in the runbook and example, or build the URL in `migrate.mjs` and the app from separate parts, or URL-encode in compose. Nothing is lost.
**Resolution:** Step 7: runbook and example generate secrets with `openssl rand -hex 24`; `deploy.sh` refuses a POSTGRES_PASSWORD with characters outside `[A-Za-z0-9._~-]` (drilled with a `/`).
Closed 2026-11-07 by independent review of e84d143..b1de666: `deploy.sh` refused a `POSTGRES_PASSWORD` containing `/` (drilled); the runbook and example now say `openssl rand -hex 24`.

### 28b/F-25 [P2] closed - deploy.sh --rollback re-deploys the current commit after a successful deploy

**File:** deploy/deploy.sh:60, deploy/deploy.sh:73, docs/deploy.md:243
**Found:** 2026-11-07 by /audit (scope: current; lens: quality)
**Why it matters:** `.last-good-commit` is overwritten with the commit that has just become healthy. After deploy A (healthy) then deploy B (healthy but functionally broken), `--rollback` resets to B, so the runbook's "Roll back to the last good commit" is a no-op in the main case it exists for. It works only after an automatic rollback or a failed deploy. Dry-run of `--rollback` does not show this.
**Suggested fix:** Keep the previous good commit too (write the old value to a second line or file before overwriting) and have `--rollback` use it, or let it take an explicit commit argument; correct the runbook text.
**Resolution:** Step 7: `deploy.sh` keeps `.last-good-commit` and `.previous-good-commit`; `--rollback` redeploys the previous one. Drilled A, B, rollback returns to A.
Closed 2026-11-07 by independent review of e84d143..b1de666: Read `deploy.sh:86-97`: on a healthy normal deploy the old last-good moves to `.previous-good-commit` before being overwritten, and `--rollback` resets to it. Dry-run of `--rollback` with no record refuses. A follow-on edge case is F-36.

### 28b/F-26 [P2] closed - Runbook firewall step does not restrict Docker-published ports

**File:** docs/deploy.md:174
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** Step 9.5 uses `ufw` to limit 80/443 to Cloudflare ranges. Docker publishes Caddy's ports through its own iptables chains, which bypass ufw's INPUT rules, so the loop has no effect on those ports (and the stated "lock the origin" layer does not exist). The `CLOUDFLARE_ONLY` guard is then the only control. The same loop also adds one rule per range with no mention of IPv6 being enabled in ufw.
**Suggested fix:** Drop the ufw loop or replace it with `DOCKER-USER` rules / a provider-level firewall, and say that `CLOUDFLARE_ONLY` is the control. The spec's wording about firewalling to Cloudflare ranges then needs a user decision.
**Resolution:** Step 7: the ufw loop is removed; the runbook explains Docker bypasses ufw, names `CLOUDFLARE_ONLY` as the control and suggests an optional provider-level firewall.
Closed 2026-11-07 by independent review of e84d143..b1de666: Read `docs/deploy.md:174-180`: the ufw loop is gone and the text names `CLOUDFLARE_ONLY` as the control.

### 28b/F-27 [P2] closed - Refreshing the Cloudflare ranges does not work with the stack as documented

**File:** deploy/update-cloudflare-ips.sh:27, docs/deploy.md:183, deploy/docker-compose.prod.yml:44
**Found:** 2026-11-07 by /audit (scope: current; lens: quality)
**Why it matters:** The script rewrites a tracked file with `mv`, so (1) the checkout becomes dirty and `deploy.sh` refuses to run until it is committed or discarded, (2) the single-file bind mount keeps pointing at the old inode and Caddy reads its config only at start, so the container keeps the old list until it is recreated, (3) nothing validates that the downloaded text is CIDRs before it is written into Caddy config. A stale list silently starts returning 403 to new Cloudflare ranges once `CLOUDFLARE_ONLY=true`. The runbook says only to re-run the script.
**Suggested fix:** Document the sequence (run the script on a laptop, commit, push, deploy) or mount the directory; validate with a CIDR regex before writing; `docker compose restart caddy` after a change.
**Resolution:** Step 7: Caddy files moved to `deploy/caddy/` and the directory is mounted; `deploy.sh` runs `caddy reload`; the ranges script validates CIDRs and refuses a bad or short list (drilled); the runbook says to refresh on a laptop, commit, push and deploy.
Closed 2026-11-07 by independent review of e84d143..b1de666: Caddy files are in `deploy/caddy/` and mounted as a directory; `update-cloudflare-ips.sh` validates CIDRs and a minimum count (read). The reload step itself has a new defect, recorded as F-33.

### 28b/F-28 [P2] closed - TRUST_PROXY_HEADERS=true is not tied to CLOUDFLARE_ONLY=true by any check

**File:** deploy/docker-compose.prod.yml:26, deploy/deploy.sh:29, web/src/server/waitlist-api.ts:30
**Found:** 2026-11-07 by /audit (scope: current; lens: security)
**Why it matters:** The spec's trust rule (header trusted only with the Cloudflare-only guard) lives in comments and the runbook. Both flags are independent lines in one file, Caddy reads `CLOUDFLARE_ONLY` through compose interpolation while the web container reads `TRUST_PROXY_HEADERS` through `env_file`, so a typo, one flag edited without the other, or a non-default `ENV_FILE` leaves the per-IP limit keyed on a client-supplied header and bypassable by header rotation. The failure is silent.
**Suggested fix:** Have `deploy.sh` (and optionally the container entrypoint) refuse to start when `TRUST_PROXY_HEADERS=true` and `CLOUDFLARE_ONLY` is not `true`. Nothing is lost.
**Resolution:** Step 7: the web entrypoint exits for TRUST_PROXY_HEADERS=true without CLOUDFLARE_ONLY=true (compose passes both) and `deploy.sh` refuses it earlier. Both drilled.
Closed 2026-11-07 by independent review of e84d143..b1de666: Built the image at the target: `TRUST_PROXY_HEADERS=true` alone exits 1 with the explanatory message; `deploy.sh` has the same check before starting (read).

### 28b/F-29 [P3] closed - Restore drill instructions cannot work as written

**File:** docs/deploy.md:199
**Found:** 2026-11-07 by /audit (scope: current; lens: tests)
**Why it matters:** The drill says to run `restore.sh` from a laptop "with an SSH tunnel". The script runs `docker compose exec db` against the local Docker daemon, so a laptop would need its own full stack, `.env.production` and rclone remote; an SSH tunnel to Postgres does nothing. The tested path (copy the key to the server, restore to a scratch database, drop it, remove the key) is mentioned only as an aside, and the scratch drop command is not given. An unreliable drill erodes the one verification that proves the backups are usable.
**Suggested fix:** Document the server path with explicit copy, restore, drop and delete-key commands.
**Resolution:** Step 7: the runbook now gives the server-side restore drill with explicit copy, restore, check, drop and delete-key commands, and the disaster-recovery steps.
Closed 2026-11-07 by independent review of e84d143..b1de666: The drill commands in `docs/deploy.md:205-235` match the options and output of `restore.sh` (scratch restore, check, drop, remove key), and the scratch path ran correctly in my drill.

### 28b/F-32 [P3] closed - Migration dependencies are not pinned by the lockfile and the containers are not hardened

**File:** web/Dockerfile:9, deploy/docker-compose.prod.yml:21
**Found:** 2026-11-07 by /audit (scope: current; lens: quality)
**Why it matters:** The migration runner's `drizzle-orm` and `pg` are installed with `npm install` from a semver range in a scratch directory, ignoring `package-lock.json`, so the version that migrates the production database can differ from the one tested and may drift between builds. The web container has no `cap_drop`, `no-new-privileges` or read-only filesystem.
**Suggested fix:** Copy the lockfile into `/migrate` and run `npm ci --omit=dev`, or prune the build stage's `node_modules` with `npm ci --omit=dev`; add `security_opt: [no-new-privileges:true]` and `cap_drop: [ALL]` to web.
**Resolution:** Step 7: migration dependencies are installed at the exact versions from the lockfile (checked in the image: drizzle-orm 0.45.4, pg 8.23.1); the web service has `no-new-privileges` and `cap_drop: ALL` and is healthy.
Closed 2026-11-07 by independent review of e84d143..b1de666: Built the image at the target: migration dependencies are installed at the lockfile's resolved `drizzle-orm` and `pg` versions (transitive packages of `pg` are still resolved fresh, which is minor); the web service has `no-new-privileges` and `cap_drop: ALL` in `docker-compose.prod.yml:32-35`.

## Independent review

**Status:** passed
**Target commit:** b1de666dda67cfbcc98c4683abf7928a978400a7
**Base commit:** e84d1430b2af73610a8f2fc76821738ef8eceb65
**Base ref:** main
**Spec hash:** 1290545f37ef371a603302b85d43827af655b2f607a205d52466464583321d94
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-07T20:10:00Z
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-07T20:58:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `git rev-parse HEAD`, `git merge-base main HEAD`, `shasum -a 256 blueprint/context/current-feature.md`, `git status --porcelain`: pass (HEAD equals target, merge base equals base commit, spec hash matches, only review.md modified)
- `npm run lint && npm run typecheck && npm run build && npm test` (in web/): pass (7 test files, 72 tests)
- `bash -n` on deploy/backup.sh, deploy/restore.sh, deploy/deploy.sh, deploy/update-cloudflare-ips.sh, web/docker-entrypoint.sh: pass
- `shellcheck` on the same scripts: unavailable (not installed)
- Local restore drill on a scratch Postgres 17 (prod compose `db` service in a copy of deploy/ under the scratchpad, rclone replaced by a directory stand-in, no real remote or key): scratch restore, wrong object name and corrupt file behaved as specified; `--into-live` swapped databases and kept the old one: pass. The stand-in's `size` output made `backup.sh` report a small upload (stand-in artefact, not a product defect).
- `deploy/deploy.sh --dry-run`, `--rollback --dry-run`, and a `POSTGRES_PASSWORD` containing `/` (with `ENV_FILE` pointing at a scratch file): pass (expected sequence, refusals as designed)
- `docker build web` at the target, then `id`, `ls`, a run with `TRUST_PROXY_HEADERS=true` alone, and a run with an unreachable `DATABASE_URL`: pass (non-root user, no tests or `.env` in the image, entrypoint and migrate refuse with exit 1 and a clear message)
- `docker run caddy:2` followed immediately by `caddy reload`: fail on the first attempt (connection refused), which is finding F-33
- `age`, `rclone`: unavailable (not installed); no encrypted backup run was possible

## Evidence

- Reviewed the complete `e84d143..b1de666` delta (37 files): deploy/ scripts, compose and Caddy files, web/Dockerfile, docker-entrypoint.sh, migrate.mjs, vite and package config, waitlist-api.ts and its test, homepage and privacy copy, og.png, docs/deploy.md, docs/technical-design.md, AGENTS.md.
- The F-11 test (`web/tests/waitlist-api.test.ts`) fails against the previous check order, so it proves the fix.
- Findings F-23 to F-29 and F-32 re-examined against the new code and closed; one new P2 (F-33) and P3 or unverified items F-34 to F-39 recorded in blueprint/context/findings.md.
- Scratch containers, volume and image from the drills were removed; no real server, secret, mail service or remote storage was touched.

## Findings

- New: F-33 (P2 open), F-34 (P3 unverified), F-35 (P3 open), F-36 (P3 open), F-37 (P3 open), F-38 (P3 unverified), F-39 (P3 open)
- Closed by this review: F-23, F-24, F-25, F-26, F-27, F-28, F-29, F-32
- Left as found: F-30 (P3 open), F-31 (P3 unverified) and the earlier open or unverified items; no P0 or P1 finding is open or fixed

## Remaining risk

- `shellcheck`, `age` and `rclone` were unavailable: no static check of the scripts, no encrypted backup run, no real object-storage run.
- TLS issuance, Cloudflare behaviour (including whether Caddy sees Cloudflare's real peer address through Docker on Linux, F-31), real email delivery and the SSH hardening result on the actual server are covered only by the runbook's checklist (F-34).
- F-33 can cause a healthy deploy to be rolled back or a first deploy to report a false failure; repair before relying on `deploy.sh` unattended.
- Backups can fail silently (F-37) and the scripts have no repeatable tests (F-39).
