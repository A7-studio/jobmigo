# Deploying Jobmigo

This is the founder's checklist for putting Jobmigo on one small server behind
Cloudflare. The repository does the engineering; the steps below are the ones that
need your accounts. Do them in order. Where a price, a limit or a screen in a
provider's dashboard may have changed, it says **verify**.

What you end up with: Caddy (HTTPS) in front of the app and Postgres on one VPS,
Cloudflare in front of Caddy, nightly encrypted database backups in object storage,
and `deploy/deploy.sh` for updates and rollbacks.

Cost to expect (**verify** current prices): the domain about 10 to 12 US dollars a
year, a 2 vCPU / 4 GB server about 5 to 20 US dollars a month, Resend and Cloudflare
free tiers to start, object storage a few cents.

## 0. What you need on your laptop

- A terminal with `ssh`.
- `age` (`brew install age` on macOS) to make the backup key.
- A private Git repository for this code (GitHub or GitLab). The repo has no remote
  yet: create an empty private repo and push this one to it.
- A password manager for the backup private key and the server passwords.

## 1. Buy the domain

1. Cloudflare dashboard, Domain Registration, Register Domains, search `jobmigo.com`
   and buy it. Cloudflare charges wholesale price and puts DNS on Cloudflare
   automatically. (Another registrar works too: then add the domain to Cloudflare and
   change the nameservers.)
2. Before buying, search the trademark databases for an existing "Jobmigo" mark.

## 2. Create the server

1. Pick a provider and region closest to Kenya that fits your budget (Hetzner,
   DigitalOcean, Vultr, Linode, Lightsail Cape Town; **verify** price and stock).
   Choose Ubuntu 24.04 LTS, 2 vCPU, 4 GB RAM, 40 GB disk or more. Add your SSH public
   key during creation.
2. Note the server's public IPv4 address. Log in as root once:

   ```bash
   ssh root@SERVER_IP
   ```

3. Create a non-root user, lock down SSH, and turn on the firewall:

   ```bash
   adduser --disabled-password --gecos "" jobmigo
   usermod -aG sudo jobmigo
   mkdir -p /home/jobmigo/.ssh && cp ~/.ssh/authorized_keys /home/jobmigo/.ssh/
   chown -R jobmigo:jobmigo /home/jobmigo/.ssh && chmod 700 /home/jobmigo/.ssh
   echo "jobmigo ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/jobmigo
   sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/; s/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
   systemctl restart ssh
   ufw default deny incoming && ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
   apt-get update && apt-get install -y unattended-upgrades fail2ban
   ```

   Open a second terminal and check `ssh jobmigo@SERVER_IP` works **before** closing
   the root session.

4. Install Docker (follow the official steps for Ubuntu at
   `https://docs.docker.com/engine/install/ubuntu/`), then:

   ```bash
   sudo usermod -aG docker jobmigo   # log out and back in afterwards
   docker compose version            # must work
   ```

## 3. Get the code onto the server

1. On your laptop push the repository to your private Git host.
2. On the server, as `jobmigo`, create a read-only deploy key and add it to the
   repository (GitHub: Settings, Deploy keys):

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/jobmigo_deploy -N ""
   cat ~/.ssh/jobmigo_deploy.pub     # paste into the deploy keys page
   printf 'Host github.com\n  IdentityFile ~/.ssh/jobmigo_deploy\n' >> ~/.ssh/config
   sudo mkdir -p /opt/jobmigo && sudo chown jobmigo:jobmigo /opt/jobmigo
   git clone git@github.com:YOUR_ORG/jobmigo.git /opt/jobmigo
   ```

## 4. DNS in Cloudflare

1. DNS, Add record: type `A`, name `@`, IPv4 = the server IP, **Proxy status: DNS only
   (grey cloud) for now**. Caddy needs to answer the certificate challenge directly the
   first time.
2. Add `www` as a `CNAME` to `@` (also DNS only for now). You can add a redirect rule
   from `www` to the root domain later.

## 5. Email: Resend and your contact address

1. Create a Resend account (resend.com), Domains, Add domain `jobmigo.com`. Resend
   shows the DNS records (SPF, DKIM, and optionally DMARC). Add each in Cloudflare DNS
   exactly as shown, with **DNS only**. Click Verify in Resend. (**Verify** the record
   names in Resend; they differ by region.)
2. Add a DMARC record if Resend did not: type `TXT`, name `_dmarc`, value
   `v=DMARC1; p=none; rua=mailto:hello@jobmigo.com` (tighten to `quarantine` after a
   few weeks of clean sending).
3. API Keys, Create API key with sending access. Keep it for step 8. Sender address:
   `Jobmigo <hello@jobmigo.com>`.
4. Cloudflare dashboard, Email, Email Routing, enable it for the domain and create
   `hello@jobmigo.com` forwarding to your Gmail (Cloudflare asks you to verify the
   destination address). This is also the `CONTACT_EMAIL` shown on the site.

## 6. Backup storage and keys

1. Cloudflare dashboard, R2, create a bucket `jobmigo-backups` (**verify** the free
   allowance and that you need to add a payment method). Create an API token with
   Object Read and Write on that bucket and note the Access Key ID, Secret and the
   account's S3 endpoint.
2. On the server install the tools and make an `rclone` remote called `r2`:

   ```bash
   sudo apt-get install -y rclone age
   rclone config    # n) New remote, name: r2, type: s3, provider: Cloudflare,
                    # paste the keys, endpoint: https://ACCOUNT_ID.r2.cloudflarestorage.com
   rclone lsd r2:   # must list your bucket
   ```

3. **On your laptop** (not the server) make the backup key pair:

   ```bash
   age-keygen -o jobmigo-backup.key
   ```

   The line starting `age1...` printed (also inside the file as "public key") is the
   public key for the server. The file `jobmigo-backup.key` is the **private** key:
   put it in your password manager and keep a second copy offline. Without it the
   backups cannot be read; the server never needs it.

## 7. Configure the server

```bash
cd /opt/jobmigo/deploy
cp .env.production.example .env.production
chmod 600 .env.production
openssl rand -hex 24    # run twice: one for POSTGRES_PASSWORD, one for BETTER_AUTH_SECRET
openssl rand -hex 32    # once more: ENGINE_TOKEN, the secret the web app and the AI engine share
nano .env.production
```

Fill in: `SITE_ADDRESS=jobmigo.com`, `BETTER_AUTH_URL` and `PUBLIC_URL` as
`https://jobmigo.com`, the three secrets (including `ENGINE_TOKEN`, at least 32
characters; `deploy.sh` refuses to run without it), `RESEND_API_KEY`, `MAIL_FROM`,
`CONTACT_EMAIL`, `BACKUP_REMOTE=r2:jobmigo-backups`, `AGE_RECIPIENT=age1...`. Leave
`TRUST_PROXY_HEADERS=false` and `CLOUDFLARE_ONLY=false` for now.

## 8. First deploy

```bash
cd /opt/jobmigo
./deploy/deploy.sh --dry-run   # read what it will do
./deploy/deploy.sh
```

It builds the image, starts the database, applies migrations, starts the app and
Caddy, and waits for the app to be healthy. If it is not healthy in two minutes it
puts the previous version back and exits with an error. On a first deploy there is no
previous version, so read the logs:

```bash
docker compose --env-file deploy/.env.production -f deploy/docker-compose.prod.yml logs --tail=100
```

## 9. Turn on the Cloudflare proxy

1. Check `https://jobmigo.com` loads over HTTPS (Caddy fetched a certificate).
2. In Cloudflare DNS switch the `@` and `www` records to **Proxied** (orange cloud).
3. SSL/TLS, Overview: set the mode to **Full (strict)**.
4. Check the site still loads. Then lock the origin so only Cloudflare can reach it:
   in `deploy/.env.production` set `CLOUDFLARE_ONLY=true` and
   `TRUST_PROXY_HEADERS=true` **together**, then `./deploy/deploy.sh` again. The
   second setting makes the waitlist rate limit trust Cloudflare's header, which is
   only safe because the first makes direct requests fail.
5. About the firewall: Docker publishes Caddy's ports itself and bypasses `ufw`, so
   `ufw` rules for ports 80 and 443 do **not** limit who can reach the site. The
   control is `CLOUDFLARE_ONLY=true` (Caddy returns 403 to any request whose network
   address is not in Cloudflare's published ranges). For an extra layer, use your
   server provider's cloud firewall (outside Docker) to allow 80 and 443 only from
   `https://www.cloudflare.com/ips-v4` and `ips-v6` (**verify** your provider
   supports this). Leave port 22 limited to your own address if you can.
6. Cloudflare occasionally changes its ranges (they announce it; check every few
   months). To refresh: on **your laptop** run `./deploy/update-cloudflare-ips.sh`,
   review the change in `deploy/caddy/cloudflare-ips.caddy`, commit and push it, then
   run `./deploy/deploy.sh` on the server (it reloads Caddy). The script refuses a
   list that is empty or malformed.

## 10. Backups

```bash
cd /opt/jobmigo
./deploy/backup.sh            # must end with "removed backups older than 30d"
rclone ls r2:jobmigo-backups  # the new file ends in .sql.gz.age
sudo cp deploy/jobmigo-backup.service deploy/jobmigo-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now jobmigo-backup.timer
systemctl list-timers jobmigo-backup.timer
```

(Without systemd, a cron line works: `30 2 * * * /opt/jobmigo/deploy/backup.sh >> /var/log/jobmigo-backup.log 2>&1`.)

**Restore drill, do this once before launch and then every few months.** It proves the
backups can be read. The private key stays off the server except for the minutes this
takes:

```bash
# 1. On your laptop: copy the private key to the server's home directory
scp ~/jobmigo-backup.key jobmigo@SERVER_IP:~/backup.key

# 2. On the server: pick the newest backup and restore it into a scratch database
cd /opt/jobmigo
rclone lsf r2:jobmigo-backups | sort | tail -3
AGE_IDENTITY_FILE=~/backup.key ./deploy/restore.sh jobmigo-YYYYMMDDTHHMMSSZ.sql.gz.age
# it prints the scratch database name, e.g. jobmigo_restore_20261107120000

# 3. Check it has your data (replace the name), then drop it and delete the key
docker compose --env-file deploy/.env.production -f deploy/docker-compose.prod.yml exec -T db \
  psql -U jobmigo -d jobmigo_restore_20261107120000 -c "select count(*) from waitlist_signup"
docker compose --env-file deploy/.env.production -f deploy/docker-compose.prod.yml exec -T db \
  psql -U jobmigo -d postgres -c 'drop database "jobmigo_restore_20261107120000"'
shred -u ~/backup.key
```

A failed restore (wrong key, wrong file name, corrupt download) removes its scratch
database and changes nothing else.

**Disaster recovery: replace the live database.** Only when the live data is lost or
damaged. Stop the app first, run the same command with `--into-live` and type the
confirmation sentence. The restored copy is checked in a scratch database first, then
swapped in by renaming. The old live database is kept as
`jobmigo_before_restore_<time>`:

```bash
docker compose --env-file deploy/.env.production -f deploy/docker-compose.prod.yml stop web
AGE_IDENTITY_FILE=~/backup.key ./deploy/restore.sh jobmigo-YYYYMMDDTHHMMSSZ.sql.gz.age --into-live
docker compose --env-file deploy/.env.production -f deploy/docker-compose.prod.yml start web
```

Check the site, then drop the old database once you are sure.

## 11. Verification checklist

Tick each one on the real server before posting on LinkedIn.

| Check | How | Expected |
|---|---|---|
| HTTPS and certificate | open `https://jobmigo.com` | padlock, no warning |
| Redirect from http | `curl -sI http://jobmigo.com` | redirects to https |
| Security headers | `curl -sI https://jobmigo.com` | HSTS, nosniff, X-Frame-Options, Referrer-Policy, Permissions-Policy |
| Direct-to-origin blocked | `curl -sk https://SERVER_IP -H 'Host: jobmigo.com'` | 403 (after step 9.4) |
| Health | `curl https://jobmigo.com/healthz` and `/readyz` | `{"status":"ok"}` |
| Share card | paste the URL into LinkedIn Post Inspector (linkedin.com/post-inspector) | title, description and the 1200 by 630 image |
| Waitlist join | join with an address you own | success message |
| Confirmation email | check inbox and spam | arrives from `MAIL_FROM`, link opens the confirm page |
| Confirm | press "Confirm my email" | "You're on the list" |
| Unsubscribe | open the unsubscribe link, press the button | "You are unsubscribed" |
| Rate limit | submit six joins quickly from one connection | the sixth shows the "too many attempts" message |
| Backup and restore | steps in section 10 | a file in the bucket; scratch restore row counts match |
| Uptime monitor | section 12 | alerts when you stop the app |

## 12. Uptime monitoring

Create a free monitor (UptimeRobot or Better Stack; **verify** current free limits)
for `https://jobmigo.com/healthz` every 5 minutes with email alerts to you.

## 13. Everyday operations

| Task | Command (on the server, in `/opt/jobmigo`) |
|---|---|
| Deploy the latest commit | `./deploy/deploy.sh` |
| Roll back to the commit before the current one (it keeps the last two good deploys) | `./deploy/deploy.sh --rollback` |
| Look at logs | `docker compose --env-file deploy/.env.production -f deploy/docker-compose.prod.yml logs -f web` |
| See waitlist signups | `docker compose --env-file deploy/.env.production -f deploy/docker-compose.prod.yml exec db psql -U jobmigo -d jobmigo -c "select email, status, source, created_at from waitlist_signup order by created_at"` |
| Count by source | same, with `select source, status, count(*) from waitlist_signup group by 1,2` |
| Restart | `docker compose --env-file deploy/.env.production -f deploy/docker-compose.prod.yml restart web` |

Database migrations only go forward. A rollback restores the previous code, not the
previous data. A change that deletes or reshapes data must come with its own restore
note in its feature.

## 14. When something fails

| Symptom | Likely cause and fix |
|---|---|
| `deploy.sh` says the web container is not healthy | read the web logs; a bad `.env.production` value or a failed migration is the usual cause; fix it and deploy again |
| Site shows a Cloudflare 52x error | the origin is down or Caddy has no certificate: check `docker compose ... ps` and Caddy's logs; temporarily set the DNS records to DNS only |
| Caddy cannot get a certificate | DNS must point at the server with the grey cloud, and ports 80 and 443 must be open |
| Confirmation emails do not arrive | check Resend's Logs page, the domain's verified status, and spam; the app logs `waitlist email failed` when a send fails |
| Everyone gets "too many attempts" | `TRUST_PROXY_HEADERS` is true without Cloudflare in front, or the global limit (60 joins per 10 minutes) was hit by a flood: check the logs |
| Backup fails | run `./deploy/backup.sh` by hand and read the message; check `rclone lsd r2:` and that `AGE_RECIPIENT` starts with `age1` |
| Disk is full | `docker system df`, then `docker image prune -a` (keeps running containers) |

## 15. What is not covered yet

CI, a container registry, error tracking (Sentry), metrics, a second server, a managed
database and a staging environment. They are later work; none is needed for the
waitlist launch.
