# Deployment Runbook — Parenting Roundtable (Pilot)

This describes deploying the pilot: **frontend on Vercel/Netlify**, **backend on Fly.io**
(single Docker container, single worker, persistent disk). It is sized for *a handful of
trusted users* — see **Pilot ceiling** before scaling.

> ⚠️ Two things are load-bearing and easy to get wrong:
> 1. **Persistent disk** — the JSON store MUST live on a mounted persistent volume. A PaaS
>    ephemeral filesystem loses every conversation on redeploy/restart.
> 2. **Single worker** — the storage lock, the in-memory rate limiter, and the daily quota
>    all assume one process. Do **not** run `--workers 2+` or multiple machines.

---

## 1. Environment variables

Copy `.env.example` → `.env` (local) or set as platform secrets (prod). Required in production:

| Var | Notes |
| --- | --- |
| `OPENROUTER_API_KEY` | Paid LLM access. |
| `SESSION_SECRET` | Random, ≥32 chars. **The app refuses to start in production without it.** Generate: `python -c "import secrets;print(secrets.token_urlsafe(32))"` |
| `ENVIRONMENT=production` | Turns on Secure/SameSite=None cookies, HSTS, strict CORS, secret fail-fast. |
| `DATA_DIR=/data/conversations` | Absolute path on the **persistent disk**. |
| `CORS_ORIGINS=https://app.yourdomain.com` | Exact frontend origin(s), comma-separated. **Never `*`** (invalid with credentials; startup refuses it). |
| `FRONTEND_URL=https://app.yourdomain.com` | Must be https and present in `CORS_ORIGINS` (OAuth redirect target; validated at startup). |
| `KAKAO_*` / `NAVER_*` | Per provider; redirect URIs must be https in production. |

Tunable (defaults are fine for a pilot): `RATE_LIMIT_MESSAGES=10/minute`,
`QUOTA_DAILY_MESSAGES=50`, stage/pipeline timeouts, `MAX_MESSAGE_CHARS=5000`, `LOG_LEVEL`.

---

## 2. Cross-site cookies & CSRF (why it's set up this way)

The frontend (`app.yourdomain.com`) and backend (`api.yourdomain.com`) are **different sites**.
For the session cookie to ride along on `credentials:'include'` fetches it must be
`SameSite=None; Secure` — which the app sets automatically when `ENVIRONMENT=production`.
Because `SameSite=None` removes SameSite's CSRF protection, every state-changing request must
carry the custom header `X-Requested-With: parenting-roundtable` (the SPA sends it; a
cross-site attacker page cannot, because the strict CORS allowlist rejects the preflight).

**Alternative (simpler):** serve both from one apex domain (e.g. `yourdomain.com` +
`yourdomain.com/api` via a proxy/rewrite). Then cookies are same-site and you can drop to
`SameSite=Lax`. If you choose this, set `ENVIRONMENT=production` still, but you may relax the
cookie policy in `auth.cookie_security_kwargs()`. The default (None+Secure+CSRF) is assumed here.

---

## 3. Backend → Fly.io

```bash
fly launch --no-deploy            # or `fly apps create parenting-roundtable`
fly volumes create pr_data --size 1 --region nrt          # persistent disk (durability backbone)
fly secrets set \
  SESSION_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(32))") \
  OPENROUTER_API_KEY=sk-or-... \
  KAKAO_REST_API_KEY=... KAKAO_CLIENT_SECRET=... \
  KAKAO_REDIRECT_URI=https://api.yourdomain.com/api/auth/kakao/callback
fly deploy
```

`fly.toml` already pins `ENVIRONMENT=production`, `DATA_DIR=/data/conversations`, the `pr_data`
mount at `/data`, `min_machines_running=1`, and a `/health` check. Adjust `CORS_ORIGINS` /
`FRONTEND_URL` in `[env]` to your real frontend domain.

The container runs `gunicorn -k uvicorn.workers.UvicornWorker -w 1` (single worker, by design).

---

## 4. Frontend → Vercel / Netlify

- **Root directory:** `frontend`
- **Build:** `npm run build` → **Output:** `dist` (SPA rewrite to `/index.html` via `vercel.json` / `netlify.toml`).
- **Build env:** `VITE_API_BASE=https://api.yourdomain.com`

---

## 5. OAuth provider registration (Kakao / Naver)

Register the **production** redirect URI in each provider console:
`https://api.yourdomain.com/api/auth/{kakao|naver}/callback`. It must match the
`*_REDIRECT_URI` secret exactly and be https.

---

## 6. Pre / post-deploy checks

```bash
# Local container smoke
docker build -t pr-backend .
docker run --rm -e SESSION_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(32))") \
  -e OPENROUTER_API_KEY=test -e ENVIRONMENT=production \
  -e DATA_DIR=/data/conversations -e CORS_ORIGINS=https://app.example.com \
  -e FRONTEND_URL=https://app.example.com -v pr-data:/data -p 8001:8001 pr-backend
curl -s localhost:8001/health                                  # {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}\n" localhost:8001/ready  # 200 if key+secret+writable disk
```

**Persistent-disk durability smoke (manual launch gate):** create a conversation + send a
benign message, then `fly deploy` again (or restart the machine) and confirm the conversation
still loads. If it vanished, the volume is not mounted at `DATA_DIR` — **do not invite users**.

**Safety spot-checks (must pass before any user touches it):**
- Newborn + fever (`아이 나이 = 신생아`, "*아기 열이 38.1도예요*") → final answer leads with a red
  `> 응급:` banner, exactly once, with trusted-domain sources.
- Benign (`아이 나이 = 유아`, "*낮잠 전환*") → no emergency banner, calm tone, sources present.

---

## 7. Backups

A pilot backup is a **disk snapshot** (`fly volumes snapshots create <vol>`), scheduled daily.

> ⚠️ Snapshots are **per-file crash-consistent** (atomic writes guarantee each file is whole)
> but **not transactionally consistent across files**. An account and its identity index may
> snapshot at slightly different instants, so a restore must tolerate a *dangling identity*
> (an identity index pointing at an account, or vice-versa). A re-login re-links cleanly.

---

## 8. Rollback

`fly releases` → `fly deploy --image <previous>` (or `fly releases rollback`). The persistent
volume is untouched by rollback, so data survives. If a release corrupts data, restore the
latest volume snapshot before rolling the image back.

---

## 9. Pilot ceiling (when to graduate)

This configuration is deliberately bounded. Move off it when you need any of:

- **More than one worker/instance** — the `asyncio.Lock` storage guard, in-memory rate
  limiter, and disk-backed quota are all single-process. Multi-worker silently breaks them.
  → migrate to **Postgres** (the `StorageBackend` seam is ready) + a **Redis-backed rate
  limiter**, then scale workers.
- **Encryption at rest / audit trail / formal data-retention / data-deletion rights** — out
  of scope for the pilot (trusted users, disk-level protection only). Required before a broad,
  regulated launch under PIPA/GDPR.
- **A clinical fact-check layer / broadened red-flag detection** — current safety is
  prompt-based + the deterministic newborn-fever net + the bilingual triage; not a medical device.

These deferrals are intentional and are tracked in `.omc/plans/production-readiness-pilot.md` §9.
