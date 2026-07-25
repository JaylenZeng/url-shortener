# Deploying to a single EC2 host

The whole stack (FastAPI app, arq worker, Postgres, Redis, Caddy) runs via
`docker-compose.prod.yml` on one EC2 instance. Caddy terminates TLS and reverse-
proxies to the app, so only ports 80/443 are exposed.

## Domains

The redirect route lives at the root (`/{code}`), which collides with the SPA's
own routes, so use two names:

| Domain              | Serves                                        |
| ------------------- | --------------------------------------------- |
| `example.com`       | Short links / redirects (`/{code}`)           |
| `app.example.com`   | React dashboard + `/auth`, `/links` API       |

Point both at the instance's Elastic IP with A records in Route 53 (or any DNS).

## 1. Launch the instance

- **Type:** `t4g.small` (2 GB RAM, ARM/Graviton — cheapest that comfortably runs
  Postgres + Redis + app + worker). `t3.small` if you prefer x86.
- **OS:** Amazon Linux 2023 or Ubuntu 24.04.
- **Elastic IP:** allocate one and associate it, so the IP survives reboots.
- **Security group inbound:** 22 (SSH, ideally your IP only), 80, 443.

## 2. Install Docker on the box

Amazon Linux 2023:

```bash
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user   # log out/in for this to take effect
```

Docker Compose v2 ships as a plugin with recent Docker; if `docker compose
version` fails, install the `docker-compose-plugin` package.

## 3. Get the code and configure secrets

```bash
git clone <your-repo-url> url-shortener
cd url-shortener/deploy
cp .env.example .env
openssl rand -hex 32          # paste into JWT_SECRET
# also set a strong POSTGRES_PASSWORD
$EDITOR .env
```

## 4. Set your domain in the Caddyfile

Edit `deploy/Caddyfile` and replace both `example.com` / `app.example.com`
occurrences with your real domain.

## 5. Build the frontend

The dashboard is served as static files by Caddy from `web/dist`. Short links
must point at the short domain, so set `VITE_SHORT_BASE_URL` at build time:

```bash
cd ../web
corepack enable
VITE_SHORT_BASE_URL=https://example.com yarn install --immutable
VITE_SHORT_BASE_URL=https://example.com yarn build
cd ../deploy
```

(You can build locally and `scp` the `web/dist` folder up instead, if the box is
tight on memory during the Node build.)

## 6. Launch

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This builds the image, runs `alembic upgrade head` (the `migrate` service) before
the app starts, then brings up app, worker, Postgres, Redis, and Caddy. Caddy
fetches Let's Encrypt certs automatically once DNS resolves to the box.

Check it:

```bash
docker compose -f docker-compose.prod.yml ps
curl -fsS https://example.com/health
curl -fsS https://app.example.com/       # SPA index
```

## Updating after code changes

```bash
git pull
# rebuild frontend if web/ changed (step 5), then:
docker compose -f docker-compose.prod.yml up -d --build
```

Migrations run automatically on each `up` via the `migrate` service.

## Notes & gotchas

- **Secrets:** generate a fresh `JWT_SECRET` — the one in the repo's `.env`
  files is committed and must not be used in production.
- **Backups:** Postgres data lives in the `pgdata` named volume. For real
  durability, either move to RDS or add a `pg_dump` cron to S3.
- **Redis:** used for caching and the arq job queue. Data is ephemeral here; the
  app tolerates a cold cache, but in-flight queued jobs are lost on restart.
- **Email verification:** `verify_email_deliverability` does live MX lookups on
  registration — make sure the instance has outbound DNS/network access.
- **Cost:** ~$15/mo (t4g.small on-demand) + Elastic IP (free while associated) +
  minimal Route 53. A reserved/savings-plan instance drops it further.
