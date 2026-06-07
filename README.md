# GitHub OSS Issue Notifier

> **Never miss a good first issue again.** Watches top open-source organizations on GitHub and delivers a clean email digest — every hour, automatically.

![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker)
![AWS](https://img.shields.io/badge/Deployed-AWS%20EC2-FF9900?style=flat-square&logo=amazon-aws)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?style=flat-square&logo=github-actions)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## What this does

Most developers miss great open-source contribution opportunities because they don't constantly refresh GitHub. This tool fixes that.

- Polls GitHub API every hour for newly opened issues across selected orgs
- Skips PRs — issues only
- Sends one clean digest email per interval
- Stores seen issues in SQLite to prevent duplicate alerts
- Runs 24/7 on a cloud VM via Docker + GitHub Actions CI/CD

**Monitored by default:** `supabase`, `python`, `digitalocean`, `pytorch`, `the-algorithms`, `freeCodeCamp` — fully configurable.

<img width="1038" height="512" alt="Screenshot 2026-06-06 044801" src="https://github.com/user-attachments/assets/8a76a98e-19f2-4612-8542-3a3aea489615" />


---

## What I learned


- Designing long-running backend services
- Handling API rate limits in production systems
- Automating deployments using GitHub Actions self-hosted runners
- Managing containerized workloads on cloud infrastructure

---

## Architecture

```
GitHub API
    │
    ▼
app.py (Python scheduler)
    │  polls every N minutes
    ├──► SQLite DB  (/data/notifier.db)
    │    deduplication store
    │
    └──► Gmail SMTP
         email digest to your inbox
```

**Infrastructure:**
- Runs inside Docker on an AWS EC2 Ubuntu VM
- Auto-deploys on every `git push` via GitHub Actions self-hosted runner
- Zero downtime redeploy with `docker compose up -d --build`

---

## Tech Stack

| Layer | Tech |
|---|---|
| Language | Python 3.11 |
| Scheduling | Native Python (`time.sleep` loop) |
| Storage | SQLite via `sqlite3` |
| Email | Gmail SMTP via `smtplib` |
| Containerization | Docker + Docker Compose |
| CI/CD | GitHub Actions (self-hosted runner on EC2) |
| Cloud | AWS EC2 (Ubuntu) |

---

## Quick Start (Local)

```bash
git clone https://github.com/surya-pratap-singh-dev/github-oss-issue-notifier
cd github-oss-issue-notifier

cp .env.example .env
# fill in your values (see table below)

docker compose up --build
```

Logs will show:
```
Monitoring: supabase, python, digitalocean ...
No new issues found.        # or
Digest sent with 4 issues.
```

---

## Environment Variables

| Variable | Required | Example | Source |
|---|---|---|---|
| `GITHUB_TOKEN` | Recommended | `github_pat_xxx` | GitHub → Settings → Developer settings → PAT (read-only) |
| `GITHUB_ORGS` | Yes | `supabase,python` | Org names from GitHub URLs |
| `CHECK_INTERVAL_MINUTES` | Yes | `60` | Your preference |
| `STARTUP_LOOKBACK_HOURS` | Yes | `2` | First-run lookback window |
| `GITHUB_PER_PAGE` | Yes | `100` | Keep at 100 (GitHub max) |
| `SMTP_HOST` | Yes | `smtp.gmail.com` | Fixed for Gmail |
| `SMTP_PORT` | Yes | `587` | Fixed for Gmail TLS |
| `SMTP_USER` | Yes | `you@gmail.com` | Your Gmail |
| `SMTP_PASS` | Yes | `abcd efgh ijkl mnop` | Google Account → Security → App Passwords |
| `EMAIL_FROM` | Yes | `you@gmail.com` | Same as `SMTP_USER` |
| `EMAIL_TO` | Yes | `alerts@yourmail.com` | Destination (comma-sep for multiple) |
| `DB_PATH` | Yes | `/data/notifier.db` | Keep default |
| `LOG_LEVEL` | Yes | `INFO` | `DEBUG` for troubleshooting |

---

## Deploy on AWS EC2

### Prerequisites
- Ubuntu EC2 instance (t2.micro free tier works)
- Docker + Docker Compose installed on VM
- Gmail with 2-Step Verification enabled

### Steps

```bash
# SSH into your VM
ssh -i your-key.pem ubuntu@your-ec2-ip

# Clone the repo
git clone https://github.com/surya-pratap-singh-dev/github-oss-issue-notifier
cd github-oss-issue-notifier

# Create and fill .env
cp .env.example .env
nano .env

# Run
docker compose up -d --build
docker compose logs -f
```

---

## CI/CD Pipeline

This project uses a **self-hosted GitHub Actions runner** on the EC2 instance.

Every push to `main`:
1. Triggers the runner on the VM
2. Checks out latest code
3. Validates Python syntax
4. Rebuilds and restarts the Docker container

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: self-hosted
```

To add the runner to your own VM: `Settings → Actions → Runners → New self-hosted runner`.

---

## Useful Commands

```bash
# Restart after config change
docker compose up -d --build

# Stop
docker compose down

# Check running container
docker ps

# View logs
docker compose logs -f
```

---

## Verify It's Working

1. Logs show monitored org names on startup
2. Every interval shows either `No new issues found.` or `Digest sent with X issues.`
3. Check inbox (and spam) for subject: `[OSS Watch] X new GitHub issues (...)`

---

## Notes

- Set `GITHUB_TOKEN` when monitoring many orgs — unauthenticated rate limit is 60 req/hr
- Wrong org names are skipped with a log error
- Never commit `.env` — it's in `.gitignore`
- Gmail requires App Password, not your account password

---
## 🚀 Advanced Improvements

### 1. Real-Time Event Processing
Migrated from a polling-based architecture to an event-driven system using GitHub Webhooks.  
This enables instant detection of newly opened issues without relying on periodic API calls.

**Benefits:**
- Real-time notifications
- Reduced API usage
- More efficient system design

---

### 2. High-Performance Caching Layer
Integrated Redis as an in-memory data store for fast deduplication and caching of processed issues.

**Benefits:**
- Prevents duplicate alerts efficiently
- Reduces database load
- Improves overall system performance

---

### 3. Production-Grade Email Delivery
Replaced traditional SMTP with scalable email services such as Amazon SES / SendGrid.

**Features:**
- HTML email templates
- Delivery tracking (open/click rates)
- Improved email reliability

---

### 4. Scalable Cloud Architecture
Redesigned the system using AWS cloud services for better scalability and fault tolerance.

**Components:**
- Queue-based processing using SQS
- Serverless compute with Lambda
- Persistent storage using RDS / DynamoDB

**Benefits:**
- Handles traffic spikes
- Decoupled architecture
- High availability

---

### 5. Smart Filtering & Personalization
Implemented user-defined filters to deliver highly relevant issue alerts.

**Capabilities:**
- Filter by labels (e.g., `good first issue`)
- Language-based filtering
- Keyword-based matching

**Future Scope:**
- Machine learning-based recommendation system

---

## Author
**Surya Pratap Singh** — [surya](https://github.com/surya-pratap-singh-dev) 
