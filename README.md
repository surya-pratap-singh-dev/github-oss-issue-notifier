# GitHub OSS Issue Notifier

This service watches selected GitHub organizations for **newly opened issues** and sends an **email digest every hour**.

---

## 1. What this project does

1. Calls GitHub API for org issues (PRs are ignored).
2. Finds only newly opened issues since last check.
3. Sends one digest email (hourly by default).
4. Saves already-sent issues in SQLite (`/data/notifier.db`) to prevent duplicates.

---

## 2. Prerequisites

1. A Linux cloud VM (Ubuntu recommended).
2. Docker + Docker Compose installed.
3. A Gmail account with **2-Step Verification** enabled.
4. A destination email address to receive alerts.
5. Optional: GitHub Personal Access Token (recommended for higher API limits).

---

## 3. Get the required `.env` values (with sources)

Use this table while filling `.env`:

| Variable | Required | Example | Where to get it |
|---|---|---|---|
| `GITHUB_TOKEN` | No (Recommended) | `github_pat_xxx` | GitHub -> Settings -> Developer settings -> Personal access tokens -> Fine-grained token (read-only is enough). |
| `GITHUB_ORGS` | Yes | `supabase,python,digitalocean,pytorch,the-algorithms,freeCodeCamp` | Organization names from GitHub URLs, e.g. `https://github.com/python` -> `python`. |
| `CHECK_INTERVAL_MINUTES` | Yes | `60` | Your preference (60 = hourly). |
| `STARTUP_LOOKBACK_HOURS` | Yes | `2` | Your preference for first-run lookback. |
| `GITHUB_PER_PAGE` | Yes | `100` | Keep `100` (GitHub max per page). |
| `SMTP_HOST` | Yes | `smtp.gmail.com` | Gmail SMTP host (fixed value). |
| `SMTP_PORT` | Yes | `587` | Gmail SMTP TLS port (fixed value). |
| `SMTP_USER` | Yes | `you@gmail.com` | Your Gmail address. |
| `SMTP_PASS` | Yes | `abcd efgh ijkl mnop` | Google Account -> Security -> 2-Step Verification -> App passwords -> create app password. |
| `EMAIL_FROM` | Yes | `you@gmail.com` | Usually same as `SMTP_USER`. |
| `EMAIL_TO` | Yes | `alerts@yourmail.com` | Email(s) that should receive digest (comma-separated for multiple). |
| `DB_PATH` | Yes | `/data/notifier.db` | Keep default unless you need a custom path. |
| `LOG_LEVEL` | Yes | `INFO` | Usually `INFO`. Use `DEBUG` only for troubleshooting. |

---

## 4. Deploy on cloud VM (step-by-step)

1. SSH into VM.
2. Clone/copy this project folder to VM.
3. Go to project directory.
4. Create `.env` from example.
5. Edit `.env` and fill real values.
6. Start service with Docker Compose.
7. Watch logs for first run.

Commands:

```bash
cd github-oss-issue-notifier
cp .env.example .env
nano .env
docker compose up -d --build
docker compose logs -f
```

---

## 5. Useful operations

Restart after config change:

```bash
docker compose up -d --build
```

Stop service:

```bash
docker compose down
```

Check running container:

```bash
docker ps
```

---

## 6. Verify it is working

1. Logs should show monitored org names.
2. Logs should show either:
   - `No new issues found.`
   - or `Digest sent with X issues.`
3. Check inbox (and spam folder) for subject like:
   - `[OSS Watch] X new GitHub issues (...)`

---

## 7. Notes and tips

1. If you monitor many orgs, set `GITHUB_TOKEN` to avoid strict unauthenticated rate limits.
2. Wrong org names are skipped with an error in logs.
3. Keep `.env` private. Never commit it to public repos.
4. For Gmail, normal account password will not work; App Password is required.
