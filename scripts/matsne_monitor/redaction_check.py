#!/usr/bin/env python3
"""Redaction-staleness probe for tracked matsne documents.

For every document in source_index.json it opens the PUBLIC matsne page
(no login, free) and reads the list of consolidated publications — i.e. the
dates on which the law was last amended. It then reports:

  1. Which laws were amended AFTER the citing page was last `checked`
     (so the page may not reflect the current text) — the staleness signal.
  2. Which laws got a NEW redaction since the probe last ran
     (compared against redaction_state.json) — the change alert.

Detecting THAT a law changed needs no paid access: the public page lists every
consolidated-publication date even though the consolidated TEXT is paywalled.

Usage:
    python scripts/matsne_monitor/redaction_check.py            # probe + report
    python scripts/matsne_monitor/redaction_check.py --check-only   # don't write state
    python scripts/matsne_monitor/redaction_check.py --selftest     # offline parser test

Optional Telegram push reuses the same secrets as monitor.py
(TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID). No secrets required to run.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INDEX_FILE = HERE / "source_index.json"
STATE_FILE = HERE / "redaction_state.json"
REPORT_FILE = HERE / "staleness_report.md"

BASE = "https://matsne.gov.ge/en/document/view/"
UA = "Mozilla/5.0 (compatible; relocation-ge-redaction-probe/1.0)"

DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def to_iso(dmy: str) -> str:
    """'24/02/2026' -> '2026-02-24'."""
    d, m, y = dmy.split("/")
    return f"{y}-{m}-{d}"


def parse_publications(html: str, doc_id: str) -> list[tuple[int, str]]:
    """Return [(publication_no, iso_date)] found for this document.

    Primary strategy: match the consolidated-publication anchors, which are
    doc-specific: .../document/view/<id>?publication=<n>">DD/MM/YYYY<
    Fallback: dates in the 'Consolidated publications' info-table cell.
    """
    pubs: dict[int, str] = {}
    anchor_re = re.compile(
        rf"view/{doc_id}\?publication=(\d+)[^>]*>\s*(\d{{2}}/\d{{2}}/\d{{4}})"
    )
    for pub_no, dmy in anchor_re.findall(html):
        pubs[int(pub_no)] = to_iso(dmy)

    if not pubs:
        # Fallback: grab the info-table row labelled "Consolidated publications".
        m = re.search(
            r"Consolidated publications.*?(\d{2}/\d{2}/\d{4}(?:\s+\d{2}/\d{2}/\d{4})*)",
            html,
            re.DOTALL,
        )
        if m:
            for i, dmy in enumerate(DATE_RE.findall(m.group(1))):
                pubs[i] = to_iso("/".join(dmy))
    return sorted(pubs.items())


def parse_title(html: str) -> str | None:
    m = re.search(r'meta\s+property="og:title"\s+content="([^"]+)"', html)
    if not m:
        m = re.search(r"<title>([^<|]+)", html)
    return m.group(1).strip() if m else None


def fetch(doc_id: str) -> str:
    req = Request(BASE + doc_id, headers={"User-Agent": UA})
    with urlopen(req, timeout=60) as r:  # noqa: S310 (trusted gov URL)
        return r.read().decode("utf-8", errors="replace")


def probe_doc(doc_id: str) -> dict:
    html = fetch(doc_id)
    pubs = parse_publications(html, doc_id)
    latest = pubs[-1][1] if pubs else None
    return {
        "title": parse_title(html),
        "publications": [d for _, d in pubs],
        "latest_redaction": latest,
        "redaction_count": len(pubs),
    }


def min_checked(pages: list[dict]) -> str | None:
    dates = [p.get("checked") for p in pages if p.get("checked")]
    return min(dates) if dates else None


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def notify_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return
    import urllib.parse

    data = urllib.parse.urlencode(
        {"chat_id": chat, "text": text, "parse_mode": "Markdown",
         "disable_web_page_preview": "true"}
    ).encode()
    try:
        urlopen(  # noqa: S310
            Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data),
            timeout=30,
        )
    except Exception as e:  # pragma: no cover
        print(f"[telegram] skipped: {e}", file=sys.stderr)


def run(check_only: bool) -> int:
    index = load_json(INDEX_FILE, {}).get("index", {})
    if not index:
        print("No source_index.json — run source_index.py first.", file=sys.stderr)
        return 1
    state = load_json(STATE_FILE, {})
    new_state = dict(state)

    stale, changed, errors = [], [], []
    for doc_id, pages in index.items():
        try:
            info = probe_doc(doc_id)
        except Exception as e:  # network/parse issues shouldn't abort the sweep
            errors.append((doc_id, str(e)))
            continue
        time.sleep(1.0)  # be polite to the server

        latest = info["latest_redaction"]
        new_state[doc_id] = {
            "title": info["title"],
            "latest_redaction": latest,
            "redaction_count": info["redaction_count"],
            "checked_at": date.today().isoformat(),
        }

        # (1) staleness vs the citing pages' `checked` dates
        oldest_check = min_checked(pages)
        if latest and oldest_check and latest > oldest_check:
            stale.append((doc_id, info, pages, oldest_check))

        # (2) new redaction since last probe
        prev = state.get(doc_id, {}).get("latest_redaction")
        if latest and prev and latest > prev:
            changed.append((doc_id, info, prev))

    report = build_report(stale, changed, errors)
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(report)

    if changed:
        lines = [f"⚠️ {len(changed)} tracked law(s) got a NEW redaction:"]
        for doc_id, info, prev in changed:
            lines.append(f"• {info['title']}: {prev} → {info['latest_redaction']}")
        notify_telegram("\n".join(lines))

    if not check_only:
        STATE_FILE.write_text(
            json.dumps(new_state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0


def build_report(stale, changed, errors) -> str:
    today = date.today().isoformat()
    out = [f"# Matsne redaction staleness — {today}", ""]

    out.append("## New redactions since last probe")
    if changed:
        for doc_id, info, prev in changed:
            out.append(f"- **{info['title']}** (`{doc_id}`): {prev} → "
                       f"**{info['latest_redaction']}**")
    else:
        out.append("_None._")
    out.append("")

    out.append("## Laws amended after the citing page was last checked")
    if stale:
        out.append("| Doc | Latest redaction | Page checked ≤ | Affected pages |")
        out.append("| --- | --- | --- | --- |")
        for doc_id, info, pages, oldest_check in stale:
            titles = ", ".join(
                f"{p.get('title') or p['path']}" for p in pages[:6]
            )
            more = "" if len(pages) <= 6 else f" (+{len(pages) - 6})"
            out.append(
                f"| {info['title']} (`{doc_id}`) | {info['latest_redaction']} "
                f"| {oldest_check} | {titles}{more} |"
            )
    else:
        out.append("_None — every citing page was checked at or after its law's "
                   "latest redaction._")
    out.append("")

    if errors:
        out.append("## Could not read")
        for doc_id, err in errors:
            out.append(f"- `{doc_id}`: {err}")
        out.append("")

    out.append("---")
    out.append("_Detection uses only the free public pages (consolidated-publication "
               "dates). Reading the amended TEXT still requires paid matsne access._")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Offline self-test: proves the publication parser on captured fixtures.
FIXTURES = {
    "2867361": (
        'href="/en/document/view/2867361?publication=8">24/02/2026</a>'
        'href="/en/document/view/2867361?publication=7">02/04/2025</a>'
        'href="/en/document/view/2867361?publication=0">08/06/2015</a>',
        "2026-02-24", 3,
    ),
    "2867377": (
        'href="/en/document/view/2867377?publication=1">17/04/2025</a>'
        'href="/en/document/view/2867377?publication=0">08/06/2015</a>',
        "2025-04-17", 2,
    ),
}


def selftest() -> int:
    ok = True
    for doc_id, (html, want_latest, want_count) in FIXTURES.items():
        pubs = parse_publications(html, doc_id)
        latest = pubs[-1][1] if pubs else None
        status = "ok" if (latest == want_latest and len(pubs) == want_count) else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"[{status}] {doc_id}: latest={latest} (want {want_latest}), "
              f"count={len(pubs)} (want {want_count})")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true",
                    help="probe and report but do not write redaction_state.json")
    ap.add_argument("--selftest", action="store_true",
                    help="run the offline parser test and exit")
    args = ap.parse_args()
    sys.exit(selftest() if args.selftest else run(args.check_only))
