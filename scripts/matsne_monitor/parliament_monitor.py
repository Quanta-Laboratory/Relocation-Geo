"""
Parliament Monitor (advance-signal watcher)
===========================================

The matsne monitor sees a law only once it is PUBLISHED. This watcher looks
upstream at the Parliament of Georgia's official bill registry
(info.parliament.ge → "კანონპროექტები"), where draft laws appear on
registration and move through committee and the three readings — weeks to
months BEFORE they reach matsne.

Source (Nov 2026): the registry's own JSON endpoint, the same one its web UI
uses — https://info.parliament.ge/law/1/bill (newest first). It replaced
scraping parliament.ge news, which started answering automated requests with
HTTP 403.

Alerts:
  🆕 a new draft LAW is registered (bill type contains "კანონის პროექტი");
  📈 a tracked draft law reaches a reading (I/II/III მოსმენა) or adoption.
Only the newest MAX_ITEMS registry entries are scanned, so stage changes are
caught for bills registered in roughly the last 1–2 months.

Scope note: an ADVANCE signal, not the final legal text. A bill can change
between readings or fail. Announcements built from it must say
"in progress — not yet in force".

Environment (all optional):
  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID   Telegram push (skipped if absent)
  ANTHROPIC_API_KEY                       translate titles to English

Usage:
  python scripts/matsne_monitor/parliament_monitor.py [--check-only]
  python scripts/matsne_monitor/parliament_monitor.py --selftest
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "parliament_state.json"
LOG_FILE = HERE / "parliament_log.md"

API = "https://info.parliament.ge/law/1/bill"
BILL_URL = "https://info.parliament.ge/#law-drafting/{id}"
UA = "relocation-ge-parliament-monitor/2.0 (+https://relocation.ge)"
HTTP_TIMEOUT = 45
MAX_ITEMS = 100
STATE_VERSION = 2

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

LAW_TYPE = "კანონის პროექტი"  # "draft law" (ordinary, organic, constitutional)
# Review stages worth an alert, in order. Matched as substrings of
# billReviewTypes[].name.
STAGES = [
    ("I მოსმენა", "I reading"),
    ("II მოსმენა", "II reading"),
    ("III მოსმენა", "III reading"),
    ("მიღებული", "adopted"),
]

try:  # site-aware relevance filter (relevance.py); optional
    sys.path.insert(0, str(HERE))
    import relevance  # type: ignore
except Exception:  # noqa: BLE001
    relevance = None  # type: ignore

try:  # reuse the matsne monitor's Claude translation if available
    sys.path.insert(0, str(HERE))
    from monitor import translate_text  # type: ignore
except Exception:  # noqa: BLE001
    def translate_text(text: str) -> tuple[str, bool]:  # type: ignore
        return text, False


# --------------------------------------------------------------------------- #
# Fetch + normalise
# --------------------------------------------------------------------------- #

def fetch_bills(limit: int = MAX_ITEMS) -> list[dict] | None:
    params = {
        "searchItem": "",
        "page": "1",
        "start": "0",
        "limit": str(limit),
        "sort": json.dumps([{"property": "billPackage.registrationDate", "direction": "DESC"}]),
    }
    url = f"{API}?{urllib.parse.urlencode(params)}"
    try:
        req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urlopen(req, timeout=HTTP_TIMEOUT) as r:  # noqa: S310 (official registry)
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"WARN: could not fetch bill registry: {e}", file=sys.stderr)
        return None
    items = data.get("list") if isinstance(data, dict) else None
    if not isinstance(items, list):
        print("WARN: unexpected registry response shape.", file=sys.stderr)
        return None
    return [normalise(b) for b in items]


def normalise(b: dict) -> dict:
    pkg = b.get("billPackage") or {}
    reviews = [t.get("name", "") for t in (b.get("billReviewTypes") or [])]
    return {
        "id": str(b.get("id")),
        "name": " ".join((b.get("billName") or pkg.get("packageName") or "").split()),
        "reg_no": pkg.get("registrationNumber") or "",
        "date": pkg.get("registrationDate") or "",
        "initiator": pkg.get("initiator") or "",
        "type": (b.get("billType") or {}).get("name") or "",
        "stages": [en for ka, en in STAGES if any(ka in r for r in reviews)],
        "url": BILL_URL.format(id=b.get("id")),
    }


def is_law(bill: dict) -> bool:
    return LAW_TYPE in bill["type"]


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def send_telegram(text: str) -> bool:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    try:
        urlopen(  # noqa: S310
            Request(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data=data),
            timeout=30,
        )
        return True
    except Exception as e:  # noqa: BLE001
        print(f"WARN: Telegram send failed: {e}", file=sys.stderr)
        return False


def format_alert(bill: dict, title_en: str, event: str) -> str:
    head = {
        "new": "🆕 <b>Parliament — new draft law registered</b>",
    }.get(event, f"📈 <b>Parliament — draft law reached: {html.escape(event)}</b>")
    lines = [
        head,
        "",
        f"📄 {html.escape(title_en or bill['name'] or '—')}",
    ]
    if title_en and title_en != bill["name"]:
        lines.append(f"🇬🇪 {html.escape(bill['name'])}")
    lines += [
        f"🔢 {html.escape(bill['reg_no'] or '—')} · 📅 {html.escape(bill['date'] or '—')}",
        f"👤 {html.escape(bill['initiator'] or '—')}",
        f"🔗 {html.escape(bill['url'])}",
        "",
        "<i>Advance signal — a bill in progress, not yet in force.</i>",
    ]
    return "\n".join(lines)


def ensure_log() -> None:
    if not LOG_FILE.exists():
        LOG_FILE.write_text(
            "# Parliament advance-signal log\n\n"
            "Draft laws from the official bill registry (info.parliament.ge), "
            "before the law reaches matsne. Maintained by `parliament_monitor.py`. "
            "**Advance signal — not yet in force.**\n",
            encoding="utf-8",
        )


def append_log(bill: dict, title_en: str, event: str) -> None:
    ensure_log()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    label = "new draft law" if event == "new" else event
    block = [
        f"\n## {stamp} — {label} — {bill['reg_no'] or bill['id']}\n",
        f"- **Title (EN):** {title_en or '—'}",
        f"- **Title (KA):** {bill['name'] or '—'}",
        f"- **Registered:** {bill['date'] or '—'}",
        f"- **Initiator:** {bill['initiator'] or '—'}",
        f"- **Link:** {bill['url']}",
        "",
    ]
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(block) + "\n")


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            s = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if s.get("version") == STATE_VERSION:
                return s
        except (json.JSONDecodeError, OSError):
            pass
    # Missing or from the old news-scraper: start a fresh baseline.
    return {"version": STATE_VERSION, "initialized": False, "bills": {}}


def save_state(state: dict) -> None:
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def diff(bills: list[dict], known: dict[str, list[str]]) -> list[tuple[dict, str]]:
    """Events to announce: ('new') for unseen law drafts, stage name for new stages."""
    events: list[tuple[dict, str]] = []
    for b in bills:
        if not is_law(b):
            continue
        if b["id"] not in known:
            events.append((b, "new"))
            continue
        for st in b["stages"]:
            if st not in known[b["id"]]:
                events.append((b, st))
    return events


def run(check_only: bool) -> int:
    print(f"Parliament Monitor run at {datetime.now(timezone.utc).isoformat()}")
    bills = fetch_bills()
    if not bills:
        print("No bills fetched (registry down, changed, or blocked). State left unchanged.")
        return 1
    laws = [b for b in bills if is_law(b)]
    print(f"Fetched {len(bills)} registry entries; {len(laws)} draft laws.")

    state = load_state()
    known: dict[str, list[str]] = state.get("bills", {})

    if not state.get("initialized"):
        state["initialized"] = True
        state["bills"] = {b["id"]: b["stages"] for b in laws}
        if not check_only:
            save_state(state)
        print(f"First run: baseline of {len(laws)} draft laws recorded. No alerts sent.")
        return 0

    events = diff(bills, known)
    events.reverse()  # oldest-first
    print(f"{len(events)} event(s).")
    pages = relevance.sync_catalogue(send_telegram) if relevance else []
    scores: dict = state.setdefault("scores", {})
    for bill, event in events:
        title_en, _ = translate_text(bill["name"])
        append_log(bill, title_en, event)
        # Relevance: scored once when first seen; stage alerts follow that score.
        if relevance and bill["id"] not in scores:
            res = relevance.score(bill["name"], title_en, pages)
            scores[bill["id"]] = res
        res = scores.get(bill["id"])
        if relevance and res and not relevance.is_alert(res):
            continue
        text = format_alert(bill, title_en, event)
        if relevance and res:
            text = text.replace("\n\n", "\n\n" + relevance.format_block(res, pages) + "\n\n", 1)
        send_telegram(text)
        time.sleep(1)

    for b in laws:
        known[b["id"]] = sorted(set(known.get(b["id"], [])) | set(b["stages"]))
    # Keep state bounded: current window + the most recent 400 ids.
    ids = [b["id"] for b in laws] + [k for k in known if k not in {b["id"] for b in laws}]
    state["bills"] = {k: known[k] for k in ids[:400]}
    state["scores"] = {k: v for k, v in state.get("scores", {}).items() if k in state["bills"]}
    if not check_only:
        save_state(state)
    return 0


# --------------------------------------------------------------------------- #
# Offline self-test
# --------------------------------------------------------------------------- #

FIXTURE = [
    {"id": 2, "billName": "„X-ის შესახებ“ საქართველოს კანონში ცვლილების შეტანის თაობაზე",
     "billPackage": {"registrationNumber": "07-3/1", "registrationDate": "20-11-2026",
                     "initiator": "საქართველოს მთავრობა"},
     "billType": {"name": "საქართველოს კანონის პროექტი"},
     "billReviewTypes": [{"name": "ინიციირებული ვარიანტი"}, {"name": "I მოსმენა"}]},
    {"id": 3, "billName": "კომიტეტის ანგარიში",
     "billPackage": {"registrationDate": "21-11-2026"}, "billType": {"name": "ანგარიში"},
     "billReviewTypes": []},
    {"id": 4, "billName": "ახალი კანონპროექტი",
     "billPackage": {"registrationDate": "22-11-2026"},
     "billType": {"name": "საქართველოს კანონის პროექტი"},
     "billReviewTypes": [{"name": "ინიციირებული ვარიანტი"}]},
]


def selftest() -> int:
    bills = [normalise(b) for b in FIXTURE]
    known = {"2": []}  # bill 2 known, no stages yet; bill 4 unseen; bill 3 not a law
    ev = [(b["id"], e) for b, e in diff(bills, known)]
    ok = ev == [("2", "I reading"), ("4", "new")] and bills[0]["url"].endswith("/2")
    print(ev)
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true",
                    help="fetch and report but do not write parliament_state.json")
    ap.add_argument("--selftest", action="store_true", help="run the offline test and exit")
    args = ap.parse_args()
    sys.exit(selftest() if args.selftest else run(args.check_only))
