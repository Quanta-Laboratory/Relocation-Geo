#!/usr/bin/env python3
"""
Matsne Monitor
==============

Watches matsne.gov.ge (the Legislative Herald of Georgia) for newly published
legal documents, translates the title and topic into English with the Claude
API, and sends a Telegram notification. Every change is also appended to a
human-readable history log that keeps the Georgian original.

Design goals
------------
* Robust data source: the site exposes an RSS feed of published documents, so we
  parse that instead of scraping fragile HTML. If matsne ever changes the feed,
  only ``fetch_items`` / ``parse_feed`` below need editing.
* Idempotent: state is stored in ``state.json``. On the very first run we only
  record a baseline and send NO notifications (so you are not flooded).
* Graceful degradation:
    - No ANTHROPIC_API_KEY  -> we still notify/log, using the Georgian original
      with a note that translation was skipped.
    - No Telegram secrets    -> we still update state and the log, just no push.

Environment variables
----------------------
ANTHROPIC_API_KEY   Claude API key (optional; translation is skipped if absent)
TELEGRAM_BOT_TOKEN  Telegram bot token (optional; push is skipped if absent)
TELEGRAM_CHAT_ID    Telegram chat id  (optional; push is skipped if absent)
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# Primary data source: matsne's RSS feed of published documents.
#
# We read the GEORGIAN feed because that is where documents actually appear as
# soon as they are published; the English feed is sparse and updates rarely, so
# relying on it meant the monitor almost never saw anything "new". Titles/topics
# arrive in Georgian and are translated to English by translate_text() below.
#
# We try several candidates in order and use the first that yields items, so a
# single URL change on matsne's side does not silently break detection. The
# winning URL is printed to the run log for easy verification.
FEED_CANDIDATES = [
    "https://www.matsne.gov.ge/ka/document/feed",
    "https://matsne.gov.ge/ka/document/feed",
    "https://www.matsne.gov.ge/en/document/feed",
]

# How many of the newest items to consider per run. Guards against a huge diff
# if the feed ever returns an unusually large payload.
MAX_ITEMS = 60

# Claude model used for translation.
CLAUDE_MODEL = "claude-sonnet-4-6"

# Pause (seconds) between Claude calls so we translate one-by-one politely.
TRANSLATE_PAUSE = 1.5

# Files live next to this script so the GitHub Action can commit them back.
BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "state.json"
LOG_FILE = BASE_DIR / "changes_log.md"

# Tbilisi is UTC+4 all year (no daylight saving) — used to decide "today".
TBILISI = timezone(timedelta(hours=4))

# Request settings.
HTTP_TIMEOUT = 30
USER_AGENT = "relocation-ge-matsne-monitor/1.0 (+https://relocation.ge)"

# Secrets (all optional — see graceful degradation above).
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


# --------------------------------------------------------------------------- #
# State helpers
# --------------------------------------------------------------------------- #

def load_state() -> dict:
    """Return saved state, or an empty first-run structure."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARN: could not read state.json ({exc}); treating as first run.")
    return {"initialized": False, "seen_ids": [], "last_run": None}


def save_state(state: dict) -> None:
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Fetch + parse the matsne feed
#
# If matsne changes its markup and the script stops finding documents, this is
# the section to adjust: point FEED_URL elsewhere or tweak the field extraction
# in parse_feed().
# --------------------------------------------------------------------------- #

def _fetch_one(url: str) -> str | None:
    """Download a single feed URL. Returns text, or None on failure."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml"},
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"WARN: could not fetch {url}: {exc}")
        return None
    # requests transparently decompresses gzip; .text handles the encoding.
    return resp.text


def fetch_feed() -> tuple[str, str] | None:
    """
    Try each candidate feed in order; return (xml_text, url) for the first that
    downloads AND parses into at least one item. Returns None if all fail.
    """
    for url in FEED_CANDIDATES:
        xml_text = _fetch_one(url)
        if xml_text is None:
            continue
        if parse_feed(xml_text):
            print(f"Feed OK: {url}")
            return xml_text, url
        print(f"WARN: {url} returned no parseable items; trying next candidate.")
    return None


def _extract_doc_id(link: str, guid: str) -> str:
    """Derive a stable id from the document URL (…/view/<id> or …/node/<id>)."""
    for candidate in (guid, link):
        if not candidate:
            continue
        m = re.search(r"/(?:view|node)/(\d+)", candidate)
        if m:
            return m.group(1)
    # Fall back to the guid/link itself so we still have *some* stable key.
    return (guid or link or "").strip()


def _clean(text: str | None) -> str:
    if not text:
        return ""
    # Unescape HTML entities and strip any stray tags from descriptions.
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_feed(xml_text: str) -> list[dict]:
    """Parse RSS <item> elements into normalized dicts (newest first)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        print(f"ERROR: could not parse feed XML: {exc}")
        return []

    # Dublin Core namespace is commonly used by Drupal feeds for <dc:date>.
    ns = {"dc": "http://purl.org/dc/elements/1.1/"}

    items: list[dict] = []
    for item in root.iter("item"):
        title = _clean(item.findtext("title"))
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        description = _clean(item.findtext("description"))
        pub_date = (
            item.findtext("pubDate")
            or item.findtext("dc:date", namespaces=ns)
            or ""
        ).strip()

        if not (title or link or guid):
            continue

        doc_id = _extract_doc_id(link, guid)
        items.append(
            {
                "id": doc_id,
                "title": title,
                "topic": description,
                "link": link or guid,
                "pub_date": pub_date,
            }
        )

    return items[:MAX_ITEMS]


# --------------------------------------------------------------------------- #
# Translation (Claude API)
# --------------------------------------------------------------------------- #

def translate_text(text: str) -> tuple[str, bool]:
    """
    Translate Georgian -> English. Returns (translated_text, translated_flag).
    When translation is unavailable, returns the original text with flag False.
    """
    if not text:
        return "", False
    if not ANTHROPIC_API_KEY:
        return text, False

    prompt = (
        "Translate the following Georgian legal-document text into clear, natural "
        "English. Return ONLY the translation, with no preamble or quotes.\n\n"
        f"{text}"
    )
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        translated = "".join(parts).strip()
        if translated:
            return translated, True
    except (requests.RequestException, ValueError, KeyError) as exc:
        print(f"WARN: translation failed ({exc}); using original text.")
    return text, False


# --------------------------------------------------------------------------- #
# Telegram
# --------------------------------------------------------------------------- #

def telegram_enabled() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def send_telegram(text: str) -> bool:
    if not telegram_enabled():
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        print(f"WARN: Telegram send failed ({exc}).")
        return False


def format_message(item: dict, title_en: str, topic_en: str, translated: bool) -> str:
    note = "" if translated else "\n\n<i>Translation skipped — showing Georgian original.</i>"
    lines = [
        "<b>🆕 New document on matsne.gov.ge</b>",
        "",
        f"📅 {html.escape(item.get('pub_date') or '—')}",
        f"🔢 {html.escape(item.get('id') or '—')}",
        f"📄 {html.escape(title_en or '—')}",
    ]
    if topic_en:
        lines.append(f"📝 {html.escape(topic_en)}")
    if item.get("link"):
        lines.append(f"🔗 {html.escape(item['link'])}")
    return "\n".join(lines) + note


# --------------------------------------------------------------------------- #
# History log
# --------------------------------------------------------------------------- #

def ensure_log_header() -> None:
    if not LOG_FILE.exists():
        LOG_FILE.write_text(
            "# Matsne changes log\n\n"
            "Automatically maintained by `scripts/matsne_monitor/monitor.py`. "
            "Newest entries are appended at the bottom.\n",
            encoding="utf-8",
        )


def append_log(item: dict, title_en: str, topic_en: str, translated: bool) -> None:
    ensure_log_header()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    flag = "" if translated else " _(translation skipped)_"
    block = [
        f"\n## {stamp} — doc {item.get('id') or '—'}{flag}\n",
        f"- **Published:** {item.get('pub_date') or '—'}",
        f"- **Title (EN):** {title_en or '—'}",
        f"- **Title (KA):** {item.get('title') or '—'}",
    ]
    if topic_en or item.get("topic"):
        block.append(f"- **Topic (EN):** {topic_en or '—'}")
        block.append(f"- **Topic (KA):** {item.get('topic') or '—'}")
    if item.get("link"):
        block.append(f"- **Link:** {item['link']}")
    block.append("")
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(block) + "\n")


# --------------------------------------------------------------------------- #
# On-demand "documents published today" list
#
# Triggered from `Run workflow` (TODAY_LIST=true). Unlike digest.py, which reads
# the history log, this pulls the live feed and filters by today's Tbilisi date,
# so it works even right after a baseline reset. It changes no state.
# --------------------------------------------------------------------------- #

def _parse_pub_date(raw: str) -> datetime | None:
    """Parse an RSS pubDate (RFC 822) into an aware datetime, or None."""
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _chunk_messages(blocks: list[str], limit: int = 3500) -> list[str]:
    """Join blocks into as few Telegram messages as possible under `limit`."""
    messages: list[str] = []
    current = ""
    for block in blocks:
        if current and len(current) + len(block) > limit:
            messages.append(current)
            current = block
        else:
            current += block
    if current:
        messages.append(current)
    return messages


def send_today_list() -> int:
    """Fetch the feed and send today's (Tbilisi) documents as a list."""
    if not telegram_enabled():
        print("Today-list requested, but Telegram secrets are missing.")
        return 1
    fetched = fetch_feed()
    if fetched is None:
        print("Today-list: feed unavailable. Nothing sent.")
        return 1

    xml_text, _ = fetched
    items = parse_feed(xml_text)
    today = datetime.now(TBILISI).date()
    todays = [
        it for it in items
        if (dt := _parse_pub_date(it.get("pub_date"))) and dt.astimezone(TBILISI).date() == today
    ]
    day_s = today.strftime("%d.%m.%Y")

    if not todays:
        send_telegram(
            f"📋 <b>Matsne — {day_s}</b>\n\n"
            "No documents dated today are in the feed yet."
        )
        print("Today-list: 0 documents dated today.")
        return 0

    header = (
        f"📋 <b>Matsne — documents published today ({day_s})</b>\n"
        f"Total: {len(todays)}\n"
    )
    blocks = [header]
    for n, it in enumerate(todays, 1):
        title_en, _ = translate_text(it["title"])
        if ANTHROPIC_API_KEY:
            time.sleep(TRANSLATE_PAUSE)
        line = f"\n{n}. {html.escape(title_en or it['title'] or '—')} (#{html.escape(it['id'])})"
        if it.get("link"):
            line += f"\n🔗 {html.escape(it['link'])}"
        blocks.append(line + "\n")

    messages = _chunk_messages(blocks)
    ok_all = True
    for msg in messages:
        ok_all = send_telegram(msg) and ok_all
    print(f"Today-list: {len(todays)} document(s) sent in {len(messages)} message(s); ok={ok_all}.")
    return 0 if ok_all else 1


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    print(f"Matsne Monitor run at {datetime.now(timezone.utc).isoformat()}")
    if not ANTHROPIC_API_KEY:
        print("NOTE: ANTHROPIC_API_KEY not set — translation will be skipped.")
    if not telegram_enabled():
        print("NOTE: Telegram secrets not set — notifications will be skipped.")

    # Manual preview: `Run workflow` with the sample checkbox ticked sets
    # TEST_TELEGRAM=true. We take the newest document currently in the feed and
    # send it formatted exactly like a real alert, then exit. State and the feed
    # baseline are left untouched — this is purely a sample so you can see how
    # notifications look without waiting for a fresh publication.
    if os.environ.get("TEST_TELEGRAM", "").strip().lower() in ("1", "true", "yes"):
        if not telegram_enabled():
            print("Preview requested, but Telegram secrets are missing. "
                  "Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
            return 1
        fetched = fetch_feed()
        if fetched is None:
            print("Preview: feed unavailable; sending a plain connectivity test instead.")
            sent = send_telegram("✅ Matsne Monitor test — Telegram delivery works.")
            print(f"Preview fallback; message sent={sent}.")
            return 0 if sent else 1
        xml_text, _ = fetched
        latest = parse_feed(xml_text)[0]
        title_en, t1 = translate_text(latest["title"])
        topic_en, t2 = translate_text(latest["topic"])
        translated = t1 or t2
        preview = (
            "🔎 <b>SAMPLE / PREVIEW</b> — this is how a real alert looks. Showing "
            "the newest document currently in the matsne feed; nothing was changed.\n\n"
            + format_message(latest, title_en, topic_en, translated)
        )
        sent = send_telegram(preview)
        print(f"Preview of doc {latest['id']} sent={sent}.")
        if not sent:
            print("Telegram accepted no message — check the bot token and that the "
                  "bot is a member of the target chat/channel.")
            return 1
        return 0

    # On-demand list of everything published today (TODAY_LIST=true). Reads the
    # live feed, changes no state.
    if os.environ.get("TODAY_LIST", "").strip().lower() in ("1", "true", "yes"):
        return send_today_list()

    state = load_state()
    seen_ids = set(state.get("seen_ids", []))

    fetched = fetch_feed()
    if fetched is None:
        print(
            "Aborting: no feed candidate returned parseable items. matsne may be "
            "down or may have changed its feed — check FEED_CANDIDATES / parse_feed(). "
            "State left unchanged."
        )
        return 1

    xml_text, _feed_url = fetched
    items = parse_feed(xml_text)

    print(f"Parsed {len(items)} items from feed.")

    # First run: record a baseline only, no notifications.
    if not state.get("initialized"):
        state["initialized"] = True
        state["seen_ids"] = [it["id"] for it in items]
        save_state(state)
        print(f"First run: baseline of {len(items)} documents recorded. No notifications sent.")
        return 0

    # Feed is newest-first; process oldest-of-the-new first so the log/notifs
    # read chronologically.
    new_items = [it for it in items if it["id"] not in seen_ids]
    new_items.reverse()

    if not new_items:
        print("No new documents since last run.")
        save_state(state)
        return 0

    print(f"Found {len(new_items)} new document(s).")

    for idx, item in enumerate(new_items):
        title_en, t1 = translate_text(item["title"])
        if idx < len(new_items) - 1 or item["topic"]:
            time.sleep(TRANSLATE_PAUSE)
        topic_en, t2 = translate_text(item["topic"])
        translated = t1 or t2

        append_log(item, title_en, topic_en, translated)
        send_telegram(format_message(item, title_en, topic_en, translated))

        seen_ids.add(item["id"])
        if idx < len(new_items) - 1:
            time.sleep(TRANSLATE_PAUSE)

    # Keep the seen list bounded but comfortably larger than MAX_ITEMS.
    all_current = [it["id"] for it in items]
    merged = list(dict.fromkeys(all_current + list(seen_ids)))
    state["seen_ids"] = merged[: MAX_ITEMS * 5]
    save_state(state)

    print(f"Done. Logged {len(new_items)} new document(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
