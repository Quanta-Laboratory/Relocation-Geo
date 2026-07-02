#!/usr/bin/env python3
"""
Matsne Monitor — daily digest
=============================

Sends a single Telegram summary of the documents that were detected *today*
(Tbilisi time) and recorded in ``changes_log.md`` by ``monitor.py``.

Intended to run once a day at 21:00 Tbilisi (17:00 UTC), after the day's
monitor runs (08:00 and 16:00 UTC). It only reads the log — it does not
translate, does not touch state, and commits nothing.

Environment variables
----------------------
TELEGRAM_BOT_TOKEN  Telegram bot token (required to send; otherwise prints only)
TELEGRAM_CHAT_ID    Telegram chat id  (required to send; otherwise prints only)

Behaviour
---------
* Parses every entry in ``changes_log.md``.
* Keeps entries whose timestamp, converted to Tbilisi time (UTC+4), falls on
  today's Tbilisi date.
* Sends one message. If there were no documents today, sends a short
  "no new documents" line so you know the job is alive. Set SEND_IF_EMPTY=0
  to stay silent on empty days instead.
"""

from __future__ import annotations

import html
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "changes_log.md"

# Tbilisi is UTC+4 all year (no daylight saving).
TBILISI = timezone(timedelta(hours=4))

HTTP_TIMEOUT = 30

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# Send a message even when there were no documents today.
SEND_IF_EMPTY = os.environ.get("SEND_IF_EMPTY", "1").strip() != "0"

# One log entry begins with a header like:
#   ## 2026-07-02 15:09 UTC — doc 101 _(translation skipped)_
ENTRY_RE = re.compile(
    r"^##\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+UTC\s+—\s+doc\s+(\S+)",
    re.MULTILINE,
)


def parse_entries(text: str) -> list[dict]:
    """Return a list of {utc, id, title_en, link} from the log."""
    entries: list[dict] = []
    matches = list(ENTRY_RE.finditer(text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]

        date_s, time_s, doc_id = m.group(1), m.group(2), m.group(3)
        try:
            utc = datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue

        title = _field(body, "Title (EN)")
        link = _field(body, "Link")
        published = _field(body, "Published")
        entries.append(
            {
                "utc": utc,
                "id": doc_id,
                "title_en": title,
                "link": link,
                "published": published,
            }
        )
    return entries


def _field(body: str, label: str) -> str:
    m = re.search(rf"-\s+\*\*{re.escape(label)}:\*\*\s*(.+)", body)
    return m.group(1).strip() if m else ""


def todays_entries(entries: list[dict], now_utc: datetime) -> list[dict]:
    today_tbilisi = now_utc.astimezone(TBILISI).date()
    return [e for e in entries if e["utc"].astimezone(TBILISI).date() == today_tbilisi]


def build_message(items: list[dict], now_utc: datetime) -> str:
    day = now_utc.astimezone(TBILISI).strftime("%d.%m.%Y")
    if not items:
        return f"<b>📋 Matsne digest — {day}</b>\n\nNo new documents today."

    lines = [f"<b>📋 Matsne digest — {day}</b>", "", f"New documents today: {len(items)}", ""]
    for n, it in enumerate(items, 1):
        title = html.escape(it["title_en"] or "—")
        lines.append(f"{n}. {title}")
        if it["link"]:
            lines.append(f"🔗 {html.escape(it['link'])}")
    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("Telegram secrets not set — printing digest instead of sending:\n")
        print(text)
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        print(f"WARN: Telegram send failed ({exc}).")
        return False


def main() -> int:
    now_utc = datetime.now(timezone.utc)
    print(f"Digest run at {now_utc.isoformat()} (Tbilisi {now_utc.astimezone(TBILISI):%Y-%m-%d %H:%M})")

    text = LOG_FILE.read_text(encoding="utf-8") if LOG_FILE.exists() else ""
    items = todays_entries(parse_entries(text), now_utc)
    print(f"{len(items)} document(s) logged today (Tbilisi).")

    if not items and not SEND_IF_EMPTY:
        print("No documents today and SEND_IF_EMPTY=0 — nothing sent.")
        return 0

    send_telegram(build_message(items, now_utc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
