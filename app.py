import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Iterable

import requests
import smtplib


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
LOGGER = logging.getLogger("oss-issue-notifier")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_github_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalize_org_name(org: str) -> str:
    alias_map = {
        "superbase": "supabase",
        "digital ocean": "digitalocean",
        "the algorithms": "the-algorithms",
        "free code camp": "freeCodeCamp",
        "awosme": "awesome",
    }
    cleaned = org.strip()
    return alias_map.get(cleaned.lower(), cleaned)


def parse_orgs(raw_orgs: str) -> list[str]:
    if not raw_orgs:
        raise ValueError("GITHUB_ORGS is required.")
    orgs = [normalize_org_name(o) for o in raw_orgs.split(",") if o.strip()]
    if not orgs:
        raise ValueError("GITHUB_ORGS must contain at least one organization.")
    return orgs


@dataclass(frozen=True)
class Issue:
    issue_id: int
    org: str
    repo: str
    title: str
    url: str
    created_at: datetime
    author: str


class Store:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_issues (
                issue_id INTEGER PRIMARY KEY,
                org TEXT NOT NULL,
                issue_url TEXT NOT NULL,
                seen_at TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def is_seen(self, issue_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM seen_issues WHERE issue_id = ? LIMIT 1", (issue_id,)
        ).fetchone()
        return row is not None

    def mark_seen(self, issues: Iterable[Issue]) -> None:
        now = utc_now().isoformat()
        self.conn.executemany(
            """
            INSERT OR IGNORE INTO seen_issues (issue_id, org, issue_url, seen_at)
            VALUES (?, ?, ?, ?)
            """,
            [(i.issue_id, i.org, i.url, now) for i in issues],
        )
        self.conn.commit()

    def get_last_checked(self) -> datetime | None:
        row = self.conn.execute(
            "SELECT value FROM app_state WHERE key = 'last_checked_utc'"
        ).fetchone()
        if not row:
            return None
        return parse_github_datetime(row[0])

    def set_last_checked(self, checked_at: datetime) -> None:
        self.conn.execute(
            """
            INSERT INTO app_state (key, value)
            VALUES ('last_checked_utc', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (checked_at.isoformat(),),
        )
        self.conn.commit()


def build_session(github_token: str | None) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "oss-issue-notifier",
        }
    )
    if github_token:
        session.headers["Authorization"] = f"Bearer {github_token}"
    return session


def get_org_issues(
    session: requests.Session,
    org: str,
    last_checked: datetime,
    per_page: int,
) -> list[Issue]:
    results: list[Issue] = []
    page = 1

    while True:
        url = f"https://api.github.com/orgs/{org}/issues"
        response = session.get(
            url,
            params={
                "filter": "all",
                "state": "open",
                "sort": "created",
                "direction": "desc",
                "per_page": per_page,
                "page": page,
            },
            timeout=30,
        )

        if response.status_code == 404:
            LOGGER.error("Organization not found: %s", org)
            return results

        response.raise_for_status()
        payload = response.json()

        if not payload:
            return results

        stop_paging = False
        for item in payload:
            if "pull_request" in item:
                continue

            created_at = parse_github_datetime(item["created_at"])
            if created_at <= last_checked:
                stop_paging = True
                continue

            repo_full = item["repository"]["full_name"]
            results.append(
                Issue(
                    issue_id=item["id"],
                    org=org,
                    repo=repo_full,
                    title=item["title"],
                    url=item["html_url"],
                    created_at=created_at,
                    author=item["user"]["login"],
                )
            )

        if stop_paging:
            return results

        page += 1
        if page > 5:
            return results


def send_digest_email(
    issues: list[Issue],
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    email_from: str,
    email_to: list[str],
) -> None:
    timestamp = utc_now().strftime("%Y-%m-%d %H:%M UTC")
    subject = f"[OSS Watch] {len(issues)} new GitHub issues ({timestamp})"
    lines = [f"New issues found: {len(issues)}", ""]
    for issue in sorted(issues, key=lambda x: x.created_at, reverse=True):
        lines.append(
            f"- [{issue.org}] {issue.repo}: {issue.title} "
            f"(by @{issue.author})\n  {issue.url}"
        )
    body = "\n".join(lines)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = ", ".join(email_to)
    msg.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_pass)
        smtp.send_message(msg)


def run_once(
    store: Store,
    session: requests.Session,
    orgs: list[str],
    lookback_hours: int,
    per_page: int,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    email_from: str,
    email_to: list[str],
) -> None:
    last_checked = store.get_last_checked()
    if last_checked is None:
        last_checked = utc_now() - timedelta(hours=lookback_hours)

    LOGGER.info("Checking orgs since %s", last_checked.isoformat())
    candidates: list[Issue] = []
    for org in orgs:
        org_issues = get_org_issues(
            session=session, org=org, last_checked=last_checked, per_page=per_page
        )
        for issue in org_issues:
            if not store.is_seen(issue.issue_id):
                candidates.append(issue)

    if candidates:
        send_digest_email(
            issues=candidates,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_pass=smtp_pass,
            email_from=email_from,
            email_to=email_to,
        )
        store.mark_seen(candidates)
        LOGGER.info("Digest sent with %s issues.", len(candidates))
    else:
        LOGGER.info("No new issues found.")

    store.set_last_checked(utc_now())


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise ValueError(f"Missing required env var: {name}")
    return value


def main() -> None:
    orgs = parse_orgs(env("GITHUB_ORGS"))
    github_token = os.getenv("GITHUB_TOKEN")
    db_path = env("DB_PATH", "/data/notifier.db")
    check_interval_minutes = int(env("CHECK_INTERVAL_MINUTES", "60"))
    startup_lookback_hours = int(env("STARTUP_LOOKBACK_HOURS", "2"))
    per_page = int(env("GITHUB_PER_PAGE", "100"))

    smtp_host = env("SMTP_HOST")
    smtp_port = int(env("SMTP_PORT", "587"))
    smtp_user = env("SMTP_USER")
    smtp_pass = env("SMTP_PASS")
    email_from = env("EMAIL_FROM")
    email_to = [e.strip() for e in env("EMAIL_TO").split(",") if e.strip()]
    if not email_to:
        raise ValueError("EMAIL_TO must contain at least one address.")

    session = build_session(github_token)
    store = Store(db_path)
    LOGGER.info("Monitoring orgs: %s", ", ".join(orgs))
    LOGGER.info("Check interval: %s minutes", check_interval_minutes)

    try:
        while True:
            run_once(
                store=store,
                session=session,
                orgs=orgs,
                lookback_hours=startup_lookback_hours,
                per_page=per_page,
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_user=smtp_user,
                smtp_pass=smtp_pass,
                email_from=email_from,
                email_to=email_to,
            )
            time.sleep(check_interval_minutes * 60)
    finally:
        store.close()


if __name__ == "__main__":
    main()
