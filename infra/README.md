# Gulp — deployment runbook

Self-hosted single-VPS private beta. Full design:
`docs/superpowers/specs/2026-07-15-deployment-aliyun-selfhost-design.md`.

## Host

Alibaba Cloud **Simple Application Server**, **Singapore**, 2 vCPU / 8 GB
(**linux/amd64** — the images build and run natively there).
Firewall: allow **22 / 80 / 443** only. Install Docker + Compose plugin.
SSH: key auth, root password login disabled.

> Building or smoke-testing the images on an Apple-Silicon Mac needs
> `--platform linux/amd64` — the native arm64 build SIGILLs in `cryptography`'s
> Rust wheel under Docker Desktop. The amd64 host is unaffected.

## First deploy

```bash
git clone <repo> /opt/gulp && cd /opt/gulp
cp infra/env.prod.example infra/.env
# Edit infra/.env: set DOMAIN, ACME_EMAIL, matching POSTGRES/REDIS passwords,
# AUTH_SECRET & CREDENTIAL_SECRET (openssl rand -hex 32), INVITE_CODE=5566.
# >>> Copy CREDENTIAL_SECRET into a password manager NOW — losing it makes every
#     stored BYOK key permanently undecryptable.
```

Point DNS: an **A record** for `DOMAIN` -> the server's public IP; wait for it to
resolve before the first deploy (Caddy needs it to issue the TLS cert).

```bash
./infra/deploy.sh
```

Caddy auto-issues the Let's Encrypt cert on first request. Verify:

```bash
curl -fsS https://<DOMAIN>/api/health    # -> {"status":"ok"}
```

## Post-deploy

- **Remove the seeded dev account** (`dev@example.com`) or change its password immediately.
- **Backups:** `crontab -e` -> `10 4 * * * /opt/gulp/infra/backup.sh >> /var/log/gulp-backup.log 2>&1`.
  Configure `ossutil` and uncomment the OSS upload line in `infra/backup.sh`.
  **Run one restore drill** (`gunzip -c dump.sql.gz | docker compose ... exec -T db psql -U gulp gulp`) on a throwaway DB.
- **Uptime probe:** point UptimeRobot / Aliyun site monitor at `https://<DOMAIN>/api/health`.

## Routine deploy

```bash
cd /opt/gulp && ./infra/deploy.sh
```

## Rollback

```bash
cd /opt/gulp && git checkout <previous-tag> && ./infra/deploy.sh
```

## Rules

- **Worker is a singleton** — never run a second `python -m app.tasks` and never
  `--scale worker=N`. A duplicate arq worker silently eats jobs it can't handle.
- `infra/.env` is secret and git-ignored; only `infra/env.prod.example` is committed.
