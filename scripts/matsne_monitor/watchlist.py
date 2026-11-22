"""
Watchlist — priority alerts for specific acts that feed site datasets.

The general monitor announces every new matsne document. Some acts matter more:
when they change, a dataset on relocation.ge (and the services consuming it,
e.g. mono.ge) must be updated by hand. This module raises a separate, loud
Telegram alert for those.

Two independent detection paths, so one failing does not hide a change:

1. Feed match  — every NEW item the monitor sees is matched against WATCHES
   (title patterns). Called from monitor.py for each new item.
2. Search sweep — once per run we query matsne's search for each watch's
   `search_query` and compare the document ids found with the ids recorded in
   watchlist_state.json. Catches documents the RSS window missed (the feed only
   carries the newest ~60 items).

State: watchlist_state.json (committed back by the workflow).
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "watchlist_state.json"

HTTP_TIMEOUT = 30
USER_AGENT = "relocation-ge-matsne-monitor/1.0 (+https://relocation.ge)"

# Each watch: what to look for, and what to do when it fires.
WATCHES = [
    {
        "id": "nbg-high-risk-jurisdictions",
        "label": "NBG list of high-risk jurisdictions (Order No 240/04)",
        # Title patterns (Georgian). Any match on a new feed item fires.
        "title_patterns": [
            r"მაღალი რისკის იურისდიქციების ნუსხ",
            r"№?\s*240/04",
        ],
        # matsne full-text search used by the sweep. Results = base order + every
        # amending order (all of them cite "240/04" in their title).
        "search_query": "240/04",
        # Known document ids at the time the dataset was last updated.
        # 6755467 = Order 12/04 (21.01.2026), 5030955 = 197/04, 4862800 = 99/04.
        "known_ids": ["6755467", "5030955", "4862800"],
        "action": (
            "Update src/data/nbg-high-risk-jurisdictions.ts (JURISDICTIONS, "
            "LIST_AS_OF, CURRENT_ORDER, HISTORY), the RU/EN guide tables and "
            "`reviewed` dates, then notify mono.ge — it reads "
            "https://relocation.ge/nbg-high-risk-jurisdictions.json"
        ),
    },
    {
        "id": "aml-cft-law",
        "label": "AML/CFT Law of Georgia (No 5226-Iს) — amendment",
        "title_patterns": [
            # Amending laws are titled "„ფულის გათეთრებისა და ტერორიზმის
            # დაფინანსების აღკვეთის ხელშეწყობის შესახებ“ საქართველოს კანონში
            # ცვლილების შეტანის შესახებ". Require "კანონში" so NBG orders that
            # merely cite the law do not fire here.
            r"ფულის გათეთრებისა და ტერორიზმის დაფინანსების აღკვეთის ხელშეწყობის შესახებ.{0,5}საქართველოს კანონში",
        ],
        "search_query": None,
        "known_ids": [],
        "action": (
            "Check whether Article 16, 18 or 19 changed; if so update ARTICLE_19_RULES "
            "in src/data/nbg-high-risk-jurisdictions.ts and the RU/EN guide pages."
        ),
    },
]


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _known(state: dict, watch: dict) -> set[str]:
    entry = state.setdefault(watch["id"], {})
    ids = set(entry.get("known_ids", [])) | set(watch["known_ids"])
    entry["known_ids"] = sorted(ids)
    return ids


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #

def _format_alert(watch: dict, doc_id: str, title: str, link: str, via: str) -> str:
    return "\n".join(
        [
            "🚨 <b>WATCHLIST: change detected</b>",
            f"<b>{html.escape(watch['label'])}</b>",
            "",
            f"🔢 {html.escape(doc_id)}",
            f"📄 {html.escape(title or '—')}",
            f"🔗 {html.escape(link)}",
            f"🔎 detected via {via}",
            "",
            f"➡️ {html.escape(watch['action'])}",
        ]
    )


def match_item(item: dict) -> list[dict]:
    """Return the watches a feed item matches (by title/topic)."""
    text = f"{item.get('title', '')} {item.get('topic', '')}"
    return [w for w in WATCHES if any(re.search(p, text) for p in w["title_patterns"])]


def check_feed_items(new_items: list[dict], send) -> int:
    """Path 1: alert on new feed items that match a watch. Returns alerts sent.

    `send(text) -> bool`; an id is recorded as known only after a successful send,
    so an undelivered alert is retried by the sweep / next run.
    """
    state = _load_state()
    sent = 0
    for item in new_items:
        for watch in match_item(item):
            known = _known(state, watch)
            if item["id"] in known:
                continue
            link = item.get("link") or f"https://matsne.gov.ge/ka/document/view/{item['id']}"
            if not send(_format_alert(watch, item["id"], item.get("title", ""), link, "RSS feed")):
                print(f"WARN: watchlist alert for doc {item['id']} not delivered; will retry next run.")
                continue
            state[watch["id"]]["known_ids"] = sorted(known | {item["id"]})
            state[watch["id"]]["last_alert"] = datetime.now(timezone.utc).isoformat()
            sent += 1
    _save_state(state)
    return sent


def _search_ids(query: str) -> list[tuple[str, str]] | None:
    """Run a matsne search; return [(doc_id, title)] or None on failure."""
    url = "https://matsne.gov.ge/ka/document/search"
    try:
        resp = requests.get(
            url,
            params={"additional_search": "false", "query": query},
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"WARN: watchlist search failed for {query!r}: {exc}")
        return None
    # Only parse the results list, so links elsewhere on the page never count.
    start = resp.text.find("document-search-result-items")
    if start == -1:
        print(f"WARN: watchlist search for {query!r}: results block not found (markup change or WAF).")
        return None
    found: dict[str, str] = {}
    for m in re.finditer(r'href="[^"]*/document/view/(\d+)[^"]*"[^>]*>(.*?)</a>', resp.text[start:], re.S):
        doc_id, raw = m.group(1), m.group(2)
        title = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()
        found.setdefault(doc_id, title)
    if not found:
        # Search page served but no results parsed: markup change or WAF page.
        print(f"WARN: watchlist search for {query!r} returned no parseable results.")
        return None
    return list(found.items())


def sweep(send) -> int:
    """Path 2: compare matsne search results with known ids. Returns alerts sent."""
    state = _load_state()
    sent = 0
    for watch in WATCHES:
        query = watch.get("search_query")
        if not query:
            continue
        results = _search_ids(query)
        entry = state.setdefault(watch["id"], {})
        entry["last_sweep"] = datetime.now(timezone.utc).isoformat()
        if results is None:
            entry["last_sweep_ok"] = False
            continue
        entry["last_sweep_ok"] = True
        known = _known(state, watch)
        for doc_id, title in results:
            if doc_id in known:
                continue
            link = f"https://matsne.gov.ge/ka/document/view/{doc_id}"
            if not send(_format_alert(watch, doc_id, title, link, f"matsne search “{query}”")):
                print(f"WARN: watchlist alert for doc {doc_id} not delivered; will retry next run.")
                continue
            known.add(doc_id)
            entry["last_alert"] = datetime.now(timezone.utc).isoformat()
            sent += 1
        entry["known_ids"] = sorted(known)
    _save_state(state)
    return sent
