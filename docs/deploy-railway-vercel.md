# Deploying Gulp — Vercel (web) + Railway (backend)

Managed, push-to-deploy private beta. Design: [`superpowers/specs/2026-07-15-deployment-railway-vercel-active.md`](superpowers/specs/2026-07-15-deployment-railway-vercel-active.md).

## Division of labor

| Step | Who | Why |
|---|---|---|
| Code changes + push to GitHub `main` | **Claude** | in-repo work |
| Railway project · plugins · volume · env vars · connect GitHub | **You** | I can't log into your Railway account |
| Vercel import · root dir · env var · connect GitHub | **You** | I can't log into your Vercel account |
| Cross-wire the two URLs, verify, add BYOK key, invite users | **You** (I can guide) | dashboard + app UI |

Both platforms deploy **from the connected GitHub repo on every push to `main`**. So the one thing I do is get the code onto GitHub; you do the one-time dashboard setup.

## What you give me / never paste

- **I need:** your OK to `git push origin main`, and later the two **public URLs** (Railway app URL, Vercel domain) to help cross-wire — both non-secret.
- **Never paste into chat:** Railway/Vercel account logins; `AUTH_SECRET` / `CREDENTIAL_SECRET` values; any LLM API key. Secrets are typed **directly into the Railway dashboard**; generate with `openssl rand -hex 32`.

---

## Part A — Railway (backend)

1. **New Project → Deploy from GitHub repo** → `mark15213/gulp`, branch `main`. Railway reads `railway.json` and builds `infra/Dockerfile.python`. This is the **app** service (runs api + worker via `infra/start-combined.sh`).
2. **Add Postgres** and **Add Redis** (Railway plugins).
3. On the **app** service:
   - **Volume:** add one, mount path `/data/media`.
   - **Variables** (reference the plugin vars for DB/Redis):
     ```
     DATABASE_URL       = ${{Postgres.DATABASE_URL}}     # bare postgresql:// — normalized in-app
     REDIS_URL          = ${{Redis.REDIS_URL}}
     AUTH_SECRET        = <openssl rand -hex 32>
     CREDENTIAL_SECRET  = <openssl rand -hex 32>          # back up off-platform — losing it kills all BYOK keys
     SESSION_COOKIE_SECURE = true
     INVITE_CODE        = 5566
     ANTHROPIC_API_KEY  =                                 # empty (BYOK)
     WEB_ORIGIN         = https://<your-vercel-domain>    # fill after Part B
     MEDIA_DIR          = /data/media
     EXPORT_DIR         = /data/exports
     RSSHUB_BASE_URL    =                                 # optional (see step 5)
     LOG_LEVEL          = INFO
     ```
   - **Networking → Generate Domain** for the app service; note the URL (e.g. `https://gulp-production.up.railway.app`) — Vercel needs it.
   - Start command (`bash infra/start-combined.sh`) and healthcheck (`/health`) come from `railway.json`. **Migrations run inside the start script** (`alembic upgrade head`, idempotent) — nothing to configure.
4. **(Optional) RSSHub** for feed subscriptions: New service → Docker image `diygod/rsshub:2025-10-20`, env `CACHE_TYPE=redis`, `REDIS_URL=${{Redis.REDIS_URL}}` (append `/1`). Set the app's `RSSHUB_BASE_URL` to the rsshub service's private URL. Skip if you don't need feeds initially.

---

## Part B — Vercel (web)

1. **Import** the GitHub repo `mark15213/gulp`.
2. **Root Directory = `apps/web`.** Framework preset **Next.js** (auto-detected).
3. **Monorepo build:** Vercel's Turborepo detection usually handles the workspace automatically. **Only if the build fails on missing `@gulp/*` deps**, override:
   - Install Command: `cd ../.. && pnpm install --frozen-lockfile`
   - Build Command: `cd ../.. && pnpm turbo run build --filter=@gulp/web`
4. **Environment Variable:**
   ```
   API_INTERNAL_URL = https://<railway-app-url>     # from Part A step 3
   ```
   (The Next rewrite proxies `/api/*` to this; the browser stays same-origin on the Vercel domain, so the session cookie is first-party. `NEXT_PUBLIC_API_URL` is not used.)
5. **Deploy** → note the production URL `https://<vercel-domain>`.

---

## Part C — Cross-wire

1. Put the **Vercel production URL** into Railway's `WEB_ORIGIN`; the app redeploys.
2. Confirm Vercel's `API_INTERNAL_URL` = the **Railway app public URL**.
3. Custom domains on either are optional; the platform domains are fine for a beta.

---

## Part D — Verify & go live

1. `curl https://<railway-app>/health` → `{"status":"ok"}`.
2. Open `https://<vercel-domain>`; browser Network tab shows `/api/*` → `200` (same-origin rewrite, first-party cookie).
3. Register with invite code **`5566`**; a wrong/absent code is rejected.
4. **Remove or rotate** the seeded `dev@example.com` account.
5. In **Settings → AI**, add your own **BYOK** key (encrypted with `CREDENTIAL_SECRET`).
6. Forward a paper → the worker (same service) picks up the job → the pack and its **figures** render (proves the shared volume).
7. Trigger one redeploy; confirm figures still render (volume persistence) and re-login works.

---

## Can Claude run the deploy?

- **Code + GitHub push:** yes — me.
- **Railway/Vercel dashboard setup** (project, plugins, volume, env, connect GitHub): you — I can't access your Railway/Vercel accounts.
- **CLI alternative:** after you `railway login` / `vercel login` in your own terminal, I could drive `railway up` / `vercel deploy` from here — but the plugin/volume/env setup is still dashboard work. Since you chose **push-to-deploy**, the flow is: I push `main`; you do the one-time connect + config in each dashboard; every later push auto-deploys.
