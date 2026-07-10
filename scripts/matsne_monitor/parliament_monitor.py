#!/usr/bin/env python3
"""
Parliament Monitor (advance-signal watcher)
===========================================

The matsne monitor sees a law only once it is PUBLISHED. This watcher looks
upstream at the Parliament of Georgia news stream (parliament.ge), where bills
are reported as they move through committee and the three readings — i.e. weeks
to months BEFORE they reach matsne. It filters for legislative items, and on a
new one it appends to a log and sends a Telegram alert, so you can prepare and
publish "upcoming change" announcements early.

Why this source: parliament.ge is a Nuxt SPA with no RSS, but its news pages are
server-rendered — the plain HTML already contains English titles, dates and
article links, so we parse that (stable) rather than a private JSON API.

Scope note: this is an ADVANCE signal, not the final legal text. A bill can
change between readings or fail. Announcements built from it must say
"in progress — not yet in force", the same way the site's `notice:` blocks do.

Environment (all optional):
  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID   Telegram push (skipped if absent)

Usage:
  python scripts/matsne_monitor/parliament_monitor.py
  python scripts/matsne_monitor/parliament_monitor.py --check-only
  python scripts/matsne_monitor/parliament_monitor.py --selftest
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "parliament_state.json"
LOG_FILE = HERE / "parliament_log.md"

# News pages to scan. The main news feed already surfaces legislative items;
# add committee feeds here later for finer coverage.
FEEDS = [
    "https://parliament.ge/en/media/news",
]

BASE = "https://parliament.ge"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HTTP_TIMEOUT = 45
MAX_ITEMS = 60

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# An item is "legislative" if its English title contains any of these. Kept
# broad on purpose (advance signal) — better a little noise than a missed bill.
LEGISLATIVE_KEYWORDS = [
    "draft law", "draft laws", "draft resolution", "legislative initiative",
    "legislative package", "legislative amendments", "first reading",
    "second reading", "third reading", " reading", "law of georgia on",
    "amendment to the law", "amendments to the law", "adopted the draft",
    "tax code", "organic law", "labour code", "migration", "residence permit",
    "citizenship", "aliens", "visa",
]

# Article link pattern on parliament.ge news pages.
ARTICLE_RE = re.compile(
    r'<a[^>]+href="(/en/media/news/[^"?#]+)"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
DATE_RE = re.compile(r"\b(\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4})\b")
TAG_RE = re.compile(r"<[^>]+>")


def clean_text(raw: str) -> str:
    txt = TAG_RE.sub(" ", raw)
    txt = html.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


def dedupe_title(text: str) -> str:
    """The anchor often repeats the title (image alt + label). Collapse it."""
    # Drop a trailing/leading date token for a cleaner title.
    date = ""
    m = DATE_RE.search(text)
    if m:
        date = m.group(1)
        text = (text[: m.start()] + " " + text[m.end():]).strip()
    # If the remaining text is "X X" (duplicated), keep one half.
    half = len(text) // 2
    if text[:half].strip() and text[:half].strip() == text[half:].strip():
        text = text[:half].strip()
    return re.sub(r"\s+", " ", text).strip(), date


def is_legislative(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in LEGISLATIVE_KEYWORDS)


def parse_articles(page_html: str) -> list[dict]:
    seen_slugs = set()
    out: list[dict] = []
    for href, inner in ARTICLE_RE.findall(page_html):
        slug = href.rsplit("/", 1)[-1]
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        title, date = dedupe_title(clean_text(inner))
        if not title:
            continue
        out.append({
            "slug": slug,
            "url": BASE + href,
            "title": title,
            "date": date,
        })
        if len(out) >= MAX_ITEMS:
            break
    return out


def fetch(url: str) -> str | None:
    try:
        req = Request(url, headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en",
        })
        with urlopen(req, timeout=HTTP_TIMEOUT) as r:  # noqa: S310 (trusted gov URL)
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"WARN: could not fetch {url}: {e}", file=sys.stderr)
        return None


def send_telegram(text: str) -> bool:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False
    import urllib.parse
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML",
        "disable_web_page_preview": "false",
    }).encode()
    try:
        urlopen(  # noqa: S310
            Request(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    data=data),
            timeout=30,
        )
        return True
    except Exception as e:
        print(f"WARN: Telegram send failed: {e}", file=sys.stderr)
        return False


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"initialized": False, "seen_slugs": []}


def save_state(state: dict) -> None:
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                          encoding="utf-8")


def ensure_log() -> None:
    if not LOG_FILE.exists():
        LOG_FILE.write_text(
            "# Parliament advance-signal log\n\n"
            "Legislative items detected on parliament.ge news, before the law "
            "reaches matsne. Maintained by `parliament_monitor.py`. "
            "**Advance signal — not yet in force.**\n",
            encoding="utf-8",
        )


def append_log(item: dict) -> None:
    ensure_log()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    block = [
        f"\n## {stamp} — {item['title']}\n",
        f"- **Parliament date:** {item.get('date') or '—'}",
        f"- **Link:** {item['url']}",
        "",
    ]
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(block) + "\n")


def format_alert(item: dict) -> str:
    return (
        "<b>🏛️ Parliament — legislative activity</b>\n\n"
        f"📅 {html.escape(item.get('date') or '—')}\n"
        f"📄 {html.escape(item['title'])}\n"
        f"🔗 {html.escape(item['url'])}\n\n"
        "<i>Advance signal — a bill in progress, not yet in force.</i>"
    )


def run(check_only: bool) -> int:
    print(f"Parliament Monitor run at {datetime.now(timezone.utc).isoformat()}")
    state = load_state()
    seen = set(state.get("seen_slugs", []))

    articles: list[dict] = []
    for feed in FEEDS:
        page = fetch(feed)
        if page:
            articles.extend(parse_articles(page))

    if not articles:
        print("No articles parsed (site down, markup changed, or blocked). "
              "State left unchanged.")
        return 1

    legislative = [a for a in articles if is_legislative(a["title"])]
    print(f"Parsed {len(articles)} articles; {len(legislative)} legislative.")

    # First run: baseline only, no alerts.
    if not state.get("initialized"):
        state["initialized"] = True
        state["seen_slugs"] = [a["slug"] for a in articles]
        if not check_only:
            save_state(state)
        print(f"First run: baseline of {len(articles)} articles recorded. "
              "No alerts sent.")
        return 0

    new = [a for a in legislative if a["slug"] not in seen]
    new.reverse()  # oldest-first so log/alerts read chronologically

    if not new:
        print("No new legislative items since last run.")
        if not check_only:
            save_state(state)
        return 0

    print(f"Found {len(new)} new legislative item(s).")
    for item in new:
        append_log(item)
        send_telegram(format_alert(item))
        seen.add(item["slug"])

    merged = list(dict.fromkeys([a["slug"] for a in articles] + list(seen)))
    state["seen_slugs"] = merged[: MAX_ITEMS * 5]
    if not check_only:
        save_state(state)
    print(f"Done. Logged {len(new)} new legislative item(s).")
    return 0


# --------------------------------------------------------------------------- #
# Offline self-test: proves the parser + legislative filter on a captured
# snippet (one bill item, one non-legislative item).
FIXTURE = '''
<a href="/en/media/news/parlamentma-mtavrobis-kanonproekti-pirveli-mosmenit-miigho">
  <div class="title">Parliament Passed Government-Initiated Draft Laws in I Reading</div>
  <div class="date">08 Jul 2026</div>
  Parliament Passed Government-Initiated Draft Laws in I Reading
</a>
<a href="/en/media/news/parlamentis-tasi-minifekhburtshi-2026-dasrulda">
  <div class="title">Parliament Mini-Football Cup 2026 Concluded</div>
  <div class="date">10 Jul 2026</div>
</a>
'''


def selftest() -> int:
    arts = parse_articles(FIXTURE)
    leg = [a for a in arts if is_legislative(a["title"])]
    ok = (
        len(arts) == 2
        and len(leg) == 1
        and leg[0]["slug"].startswith("parlamentma-mtavrobis")
        and "Draft Laws" in leg[0]["title"]
        and leg[0]["date"] == "08 Jul 2026"
    )
    print(f"parsed={len(arts)} legislative={len(leg)}")
    for a in arts:
        tag = "LEGIS" if is_legislative(a["title"]) else "skip "
        print(f"  [{tag}] {a['date']!r:>14} | {a['title']}")
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true",
                    help="probe and alert but do not write parliament_state.json")
    ap.add_argument("--selftest", action="store_true",
                    help="run the offline parser test and exit")
    args = ap.parse_args()
    sys.exit(selftest() if args.selftest else run(args.check_only))
