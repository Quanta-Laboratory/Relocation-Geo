#!/usr/bin/env python3
"""
Matsne Monitor — daily digest
=============================

Sends a single Telegram summary of the documents recorded in ``changes_log.md``
by ``monitor.py`` since the previous digest.

Intended to run once a day at 21:00 Tbilisi (17:00 UTC), after the day's
monitor runs (08:00 and 16:00 UTC). It reads the log and keeps one small state
file, ``digest_state.json`` (committed back by the workflow).

Why "since the previous digest" and not "today": GitHub's cron routinely starts
jobs hours late (7–8 h observed in Nov 2026), so the 21:00 digest often ran
after midnight Tbilisi and a calendar-day filter returned the new, empty day
while the previous day's documents were never digested. A watermark makes the
digest independent of when it actually runs: no gaps, no duplicates.

Environment variables
----------------------
TELEGRAM_BOT_TOKEN  Telegram bot token (required to send; otherwise prints only)
TELEGRAM_CHAT_ID    Telegram chat id  (required to send; otherwise prints only)

Behaviour
---------
* Parses every entry in ``changes_log.md``.
* DIGEST_MODE=scheduled (cron / external scheduler): keeps entries logged after
  the watermark in ``digest_state.json`` (= newest entry of the previous
  digest), then advances it. First run without state: last 24 hours.
* DIGEST_MODE=manual (default, "Run workflow"): rolling window of the last
  DIGEST_DAYS × 24 hours; the watermark is left untouched.
* Sends one message. If there were no documents today, sends a short
  "no new documents" line so you know the job is alive. Set SEND_IF_EMPTY=0
  to stay silent on empty days instead.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import relevance

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "changes_log.md"
STATE_FILE = BASE_DIR / "digest_state.json"

# Tbilisi is UTC+4 all year (no daylight saving).
TBILISI = timezone(timedelta(hours=4))

HTTP_TIMEOUT = 30

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = "claude-sonnet-4-6"

# Send a message even when there were no documents today.
SEND_IF_EMPTY = os.environ.get("SEND_IF_EMPTY", "1").strip() != "0"

# "scheduled" = since previous digest (watermark); "manual" = rolling window.
DIGEST_MODE = os.environ.get("DIGEST_MODE", "manual").strip().lower()

# Never reach back further than this, even if the watermark is very old
# (e.g. the digest was broken for weeks).
MAX_LOOKBACK = timedelta(days=7)

# Manual mode window, in days of 24 h. Default 1 = last 24 hours.
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
                "rel": relevance.parse_log_line(_field(body, "Relevance")),
            }
        )
    return entries


def is_relevant(entry: dict) -> bool:
    # Prefer the monitor's site-aware score (relevance.py); old entries: keywords.
    if entry.get("rel"):
        return entry["rel"]["score"] >= relevance.ALERT_MIN_SCORE
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


def load_state() -> tuple[datetime | None, datetime | None]:
    """Return (watermark, last_run) from digest_state.json, or (None, None)."""
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        wm, lr = data.get("watermark_utc"), data.get("last_run_utc")
        return (datetime.fromisoformat(wm) if wm else None,
                datetime.fromisoformat(lr) if lr else None)
    except (OSError, ValueError, json.JSONDecodeError):
        return None, None


def save_watermark(watermark: datetime, now_utc: datetime, sent: int) -> None:
    STATE_FILE.write_text(
        json.dumps(
            {
                "watermark_utc": watermark.isoformat(),
                "last_run_utc": now_utc.isoformat(timespec="seconds"),
                "last_count": sent,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def window_entries(entries: list[dict], since: datetime, now_utc: datetime) -> list[dict]:
    """Entries logged strictly after `since` and not after `now_utc`."""
    return [e for e in entries if since < e["utc"] <= now_utc]


def needs_translation(entry: dict) -> bool:
    """True when the log has no real English title (monitor ran without a key,
    in which case it stores the Georgian original under "Title (EN)")."""
    en, ka = entry.get("title_en", ""), entry.get("title_ka", "")
    return bool(ka) and (not en or en == ka or "_(translation skipped)_" in en)


# Telegram hard limit is 4096 chars/message; stay comfortably under it.
TG_LIMIT = 3500


def build_messages(items: list[dict], shown_from: datetime, now_utc: datetime,
                   relevant_only: bool) -> list[str]:
    """Build one or more Telegram messages, each under TG_LIMIT characters.

    A single long digest (e.g. a 7-day window with 100+ documents) exceeds
    Telegram's per-message limit and is rejected with HTTP 400, so we split
    the item list across as few messages as possible.
    """
    fmt = "%d.%m %H:%M"
    period = f"{shown_from.astimezone(TBILISI):{fmt}} – {now_utc.astimezone(TBILISI):{fmt}}"
    tag = " · relocation-relevant" if relevant_only else ""
    header = f"<b>📋 Matsne digest — {period} (Tbilisi){tag}</b>"

    if not items:
        none = "documents" if not relevant_only else "relevant documents"
        return [f"{header}\n\nNo new {none} in this window."]

    rel = [it for it in items if is_relevant(it)]
    other = [it for it in items if not is_relevant(it)]
    # Most important first: score 3 (pages to update), then 2.
    rel.sort(key=lambda it: -((it.get("rel") or {}).get("score", 2)))
    intro = (f"{header}\n\nNew documents: {len(items)} · relevant to the site: {len(rel)}")
    messages: list[str] = []
    current = intro

    def add(block: str) -> None:
        nonlocal current
        if len(current) + len(block) > TG_LIMIT:
            messages.append(current)
            current = f"{header} (cont.){block}"
        else:
            current += block

    for n, it in enumerate(rel, 1):
        title = html.escape(it["title_en"] or it.get("title_ka") or "—")
        stamp = it["utc"].astimezone(TBILISI).strftime("%d.%m")
        r = it.get("rel") or {}
        badge = "🔴" if r.get("score") == 3 else "🟠"
        block = f"\n\n{badge} {n}. [{stamp}] {title}"
        if r.get("pages"):
            block += "\n📚 " + ", ".join(
                f'<a href="{relevance.SITE}/en/{s}/">{html.escape(s)}</a>' for s in r["pages"])
        elif r.get("gap"):
            block += "\n✍️ not covered on the site yet"
        if it["link"]:
            block += f"\n🔗 {html.escape(it['link'])}"
        add(block)
    if other and not relevant_only:
        add(f"\n\n<i>Not relevant to the site: {len(other)} document(s) — see changes_log.md.</i>")
    messages.append(current)
    return messages


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
    print(f"Digest run at {now_utc.isoformat()} (Tbilisi {now_utc.astimezone(TBILISI):%Y-%m-%d %H:%M}), mode={DIGEST_MODE}")

    text = LOG_FILE.read_text(encoding="utf-8") if LOG_FILE.exists() else ""
    entries = parse_entries(text)

    scheduled = DIGEST_MODE == "scheduled"
    if scheduled:
        watermark, last_run = load_state()
        since = watermark or (now_utc - timedelta(hours=24))
        print(f"Watermark: {watermark.isoformat() if watermark else 'none (first run, last 24 h)'}")
        since = max(since, now_utc - MAX_LOOKBACK)
        # Header shows "since the previous digest", which reads naturally;
        # filtering still uses the watermark.
        shown_from = last_run or since
    else:
        since = now_utc - timedelta(days=DIGEST_DAYS)
        shown_from = since

    window = window_entries(entries, since, now_utc)
    items = [e for e in window if is_relevant(e)] if RELEVANT_ONLY else window
    filt = " relevant" if RELEVANT_ONLY else ""
    print(f"{len(items)}{filt} document(s) logged since {since.isoformat(timespec='minutes')}.")

    # Fill in English titles on the fly when the log only has the Georgian one
    # (monitor.py ran without a translation key). Only the items being sent.
    if ANTHROPIC_API_KEY:
        for it in items:
            if needs_translation(it):
                it["title_en"] = translate_ka_to_en(it["title_ka"]) or it["title_en"]

    if items or SEND_IF_EMPTY:
        messages = build_messages(items, shown_from, now_utc, RELEVANT_ONLY)
        print(f"Sending {len(messages)} message(s).")
        for msg in messages:
            send_telegram(msg)
    else:
        print("Nothing in window and SEND_IF_EMPTY=0 — nothing sent.")

    # Advance the watermark to the newest entry this digest saw (not to "now"):
    # a monitor run still committing while we ran will have later timestamps
    # and lands in the next digest instead of being skipped.
    if scheduled:
        newest = max((e["utc"] for e in window), default=None)
        save_watermark(newest or since, now_utc, len(items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
