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
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = "claude-sonnet-4-6"

# Send a message even when there were no documents today.
SEND_IF_EMPTY = os.environ.get("SEND_IF_EMPTY", "1").strip() != "0"

# Window in days (Tbilisi). Default 1 = today only (original daily behaviour).
# Set DIGEST_DAYS=7 for a weekly digest.
try:
    DIGEST_DAYS = max(1, int(os.environ.get("DIGEST_DAYS", "1") or "1"))
except ValueError:
    DIGEST_DAYS = 1

# When "1", keep only entries relevant to relocation topics (immigration, work,
# tax, residence). Matches Georgian OR English title text.
RELEVANT_ONLY = os.environ.get("RELEVANT_ONLY", "0").strip() == "1"

# Lower-cased substrings. Georgian first, English equivalents second.
RELEVANT_KEYWORDS = [
    "ბინადრობის", "ვიზა", "ვიზის", "უცხოელ", "იმიგრ", "მიგრაც",
    "მოქალაქეობ", "შრომითი საქმიანობის უფლებ", "შრომით იმიგრ", "თავშესაფ",
    "გადასახად", "საგადასახადო",
    "residence permit", "visa", "alien", "foreigner", "immigra", "migration",
    "citizenship", "right to work", "work permit", "labour", "asylum", "tax",
]

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
                "title_ka": _field(body, "Title (KA)"),
                "link": link,
                "published": published,
            }
        )
    return entries


def is_relevant(entry: dict) -> bool:
    text = f"{entry.get('title_en', '')} {entry.get('title_ka', '')}".lower()
    return any(kw in text for kw in RELEVANT_KEYWORDS)


def translate_ka_to_en(text: str) -> str:
    """Best-effort Georgian->English for a title. Returns '' on any failure."""
    if not (text and ANTHROPIC_API_KEY):
        return ""
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": CLAUDE_MODEL, "max_tokens": 512,
                  "messages": [{"role": "user", "content":
                                "Translate this Georgian legal-document title into "
                                "concise English. Return ONLY the translation.\n\n"
                                + text}]},
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        parts = [b.get("text", "") for b in resp.json().get("content", [])
                 if b.get("type") == "text"]
        return "".join(parts).strip()
    except (requests.RequestException, ValueError, KeyError):
        return ""


def _field(body: str, label: str) -> str:
    m = re.search(rf"-\s+\*\*{re.escape(label)}:\*\*\s*(.+)", body)
    return m.group(1).strip() if m else ""


def window_entries(entries: list[dict], now_utc: datetime, days: int) -> list[dict]:
    """Entries whose Tbilisi date falls within the last `days` days (inclusive)."""
    today = now_utc.astimezone(TBILISI).date()
    cutoff = today - timedelta(days=days - 1)
    return [e for e in entries if cutoff <= e["utc"].astimezone(TBILISI).date() <= today]


def build_message(items: list[dict], now_utc: datetime, days: int,
                  relevant_only: bool) -> str:
    day = now_utc.astimezone(TBILISI).strftime("%d.%m.%Y")
    scope = "today" if days == 1 else f"last {days} days"
    tag = " · relocation-relevant" if relevant_only else ""
    header = f"<b>📋 Matsne digest — {scope} ({day}){tag}</b>"

    if not items:
        none = "documents" if not relevant_only else "relevant documents"
        return f"{header}\n\nNo new {none} in this window."

    lines = [header, "", f"New documents: {len(items)}", ""]
    for n, it in enumerate(items, 1):
        title = html.escape(it["title_en"] or it.get("title_ka") or "—")
        stamp = it["utc"].astimezone(TBILISI).strftime("%d.%m")
        lines.append(f"{n}. [{stamp}] {title}")
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
    items = window_entries(parse_entries(text), now_utc, DIGEST_DAYS)
    if RELEVANT_ONLY:
        items = [e for e in items if is_relevant(e)]
    scope = "today" if DIGEST_DAYS == 1 else f"last {DIGEST_DAYS} days"
    filt = " relevant" if RELEVANT_ONLY else ""
    print(f"{len(items)}{filt} document(s) logged in {scope} (Tbilisi).")

    # For the digest, fill in any missing English titles on the fly (cheap: only
    # the filtered items). Existing log entries may be Georgian-only if monitor.py
    # ran without a translation key.
    if ANTHROPIC_API_KEY:
        for it in items:
            if not it.get("title_en") and it.get("title_ka"):
                it["title_en"] = translate_ka_to_en(it["title_ka"])

    if not items and not SEND_IF_EMPTY:
        print("Nothing in window and SEND_IF_EMPTY=0 — nothing sent.")
        return 0

    send_telegram(build_message(items, now_utc, DIGEST_DAYS, RELEVANT_ONLY))
    return 0


if __name__ == "__main__":
    sys.exit(main())
