"""
Relevance filter — decides which incoming legal documents matter to relocation.ge.

The topic model is the SITE ITSELF: on every run we read the live catalogue of
published guides (https://relocation.ge/kb/index.json — slug, title, category,
summary). Each new matsne / parliament document is scored by Claude against
that catalogue:

  3  changes a rule, fee, deadline or procedure described on a site page
  2  relevant to foreigners relocating to / living / working / doing business
     in Georgia — either touches a page, or is a gap the site does not cover yet
  1  tangential (general administration that rarely affects the audience)
  0  not relevant

Only score >= ALERT_MIN_SCORE (default 2) is pushed to Telegram; everything is
still logged with its score so the digest can rank it.

The filter widens on its own: a new guide published on the site enters the
catalogue, so documents on that topic start scoring as relevant from the next
run. Catalogue changes are announced in Telegram ("filter expanded: +N pages").

Without ANTHROPIC_API_KEY it degrades to a keyword match built from
FALLBACK_KEYWORDS plus words from the catalogue titles.

State: topics_state.json (last known catalogue slugs; committed by the workflow).
"""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "topics_state.json"
CATALOGUE_URL = os.environ.get("KB_CATALOGUE_URL", "https://relocation.ge/kb/index.json")
SITE = "https://relocation.ge"
MODEL = "claude-sonnet-4-6"
HTTP_TIMEOUT = 45
ALERT_MIN_SCORE = int(os.environ.get("ALERT_MIN_SCORE", "2"))
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()

SCORE_BADGE = {3: "🔴 affects site content", 2: "🟠 relevant", 1: "⚪ tangential", 0: "⚪ not relevant"}

FALLBACK_KEYWORDS = [
    "ბინადრობის", "ვიზა", "ვიზის", "უცხოელ", "იმიგრ", "მიგრაც", "მოქალაქეობ",
    "შრომითი საქმიანობის", "შრომით", "თავშესაფ", "გადასახად", "საგადასახადო",
    "მეწარმე", "მცირე ბიზნეს", "საბანკო", "ნოტარ", "აპოსტილ", "ლეგალიზაც",
    "residence permit", "visa", "alien", "foreigner", "immigra", "migration",
    "citizenship", "right to work", "work permit", "labour", "asylum", "tax",
    "entrepreneur", "small business", "bank", "notar", "apostille", "legaliz",
]


# --------------------------------------------------------------------------- #
# Catalogue
# --------------------------------------------------------------------------- #

def _load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_catalogue() -> list[dict]:
    """Live catalogue from the site; falls back to the copy saved last run."""
    try:
        r = requests.get(CATALOGUE_URL, timeout=HTTP_TIMEOUT,
                         headers={"User-Agent": "relocation-ge-monitor/1.0"})
        r.raise_for_status()
        pages = r.json().get("pages") or []
        if pages:
            return pages
    except (requests.RequestException, ValueError) as exc:
        print(f"WARN: catalogue fetch failed ({exc}); using cached copy.")
    return _load_state().get("pages", [])


def sync_catalogue(send) -> list[dict]:
    """Load the catalogue, announce added/removed pages, persist. Returns pages."""
    pages = load_catalogue()
    if not pages:
        return []
    state = _load_state()
    old = {p["slug"]: p for p in state.get("pages", [])}
    new = {p["slug"]: p for p in pages}
    if old:  # skip the announcement on the very first run
        added = [new[s] for s in new if s not in old]
        removed = [old[s] for s in old if s not in new]
        if added or removed:
            lines = [f"🧭 <b>Monitor filter updated from the site</b> — now {len(new)} topics"]
            if added:
                lines.append(f"\n➕ New pages ({len(added)}) — related documents will now be flagged:")
                lines += [f"• <a href=\"{SITE}/en/{p['slug']}/\">{html.escape(p['title'])}</a>" for p in added[:20]]
            if removed:
                lines.append(f"\n➖ Removed ({len(removed)}): " + ", ".join(html.escape(p["title"]) for p in removed[:10]))
            send("\n".join(lines))
    _save_state({"pages": pages})
    return pages


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #

def _system_prompt(pages: list[dict]) -> str:
    cat = "\n".join(f"- {p['slug']} | {p['title']} | {p.get('summary', '')}" for p in pages)
    return f"""You triage new Georgian legal acts and draft laws for relocation.ge, a guide for foreigners relocating to Georgia (visas and entry, residence permits, right to work, citizenship, taxes, Individual Entrepreneur and Small Business status, banking, documents/apostille/notary, property, driving, education, healthcare, everyday life).

Score the document:
3 = changes a rule, fee, threshold, deadline, form or procedure that a page below describes (the page will need updating)
2 = relevant to foreigners moving to, living, working or doing business in Georgia, even if no page covers it yet
1 = tangential: general administration, internal statutes of agencies, budgets of specific bodies, appointments — rarely matters to this audience
0 = not relevant (municipal acts, local property transfers, unrelated sectors)

Be strict: most acts are 0–1. Amendments to a ministry's internal statute are 1 unless they change a public service foreigners use. Municipal acts, auctions, single-property decisions and procurement rules are 0.
But summaries below are short — pages also cover their sub-topics. If an act changes how a sub-topic a page plainly belongs to works (e.g. pension-contribution rules or their enforcement → tax/IE pages; Public Service Hall or civil-registry procedures → documents/residence pages; NBG banking rules → banking pages), score it at least 2 and name the page.

Return ONLY JSON: {{"score": 0-3, "pages": ["slug", ...] (0–3 most affected slugs from the catalogue, exact), "topic": "≤8-word English topic", "why": "≤25-word reason", "gap": true|false (true when score>=2 but no page covers it — a candidate new article)}}

SITE CATALOGUE (slug | title | summary):
{cat}"""


def _keyword_score(text: str, pages: list[dict]) -> dict:
    t = text.lower()
    hit = any(k in t for k in FALLBACK_KEYWORDS)
    return {"score": 2 if hit else 0, "pages": [], "topic": "", "why": "keyword match" if hit else "",
            "gap": False, "method": "keywords"}


def score(doc_ka: str, doc_en: str, pages: list[dict], extra: str = "") -> dict:
    """Score one document. Never raises; falls back to keywords."""
    text = f"{doc_en}\n{doc_ka}\n{extra}".strip()
    if not ANTHROPIC_API_KEY or not pages:
        return _keyword_score(text, pages)
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={
                "model": MODEL,
                "max_tokens": 300,
                "system": [{"type": "text", "text": _system_prompt(pages),
                            "cache_control": {"type": "ephemeral"}}],
                "messages": [{"role": "user", "content": f"DOCUMENT:\n{text[:4000]}"}],
            },
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        out = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
        m = re.search(r"\{.*\}", out, re.S)
        data = json.loads(m.group(0)) if m else {}
        known = {p["slug"] for p in pages}
        res = {
            "score": max(0, min(3, int(data.get("score", 0)))),
            "pages": [s for s in data.get("pages", []) if s in known][:3],
            "topic": str(data.get("topic", ""))[:80],
            "why": str(data.get("why", ""))[:200],
            "gap": bool(data.get("gap", False)),
            "method": "claude",
        }
        return res
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        print(f"WARN: relevance scoring failed ({exc}); using keywords.")
        return _keyword_score(text, pages)


def is_alert(res: dict) -> bool:
    return res.get("score", 0) >= ALERT_MIN_SCORE


# --------------------------------------------------------------------------- #
# Formatting helpers shared by the monitors
# --------------------------------------------------------------------------- #

def page_title(slug: str, pages: list[dict]) -> str:
    return next((p["title"] for p in pages if p["slug"] == slug), slug)


def format_block(res: dict, pages: list[dict]) -> str:
    """Telegram lines describing the relevance verdict."""
    lines = [f"{SCORE_BADGE.get(res['score'], '')}" + (f" · {html.escape(res['topic'])}" if res.get("topic") else "")]
    if res.get("why"):
        lines.append(f"💡 {html.escape(res['why'])}")
    if res.get("pages"):
        lines.append("📚 Site pages to check: " + ", ".join(
            f"<a href=\"{SITE}/en/{s}/\">{html.escape(page_title(s, pages))}</a>" for s in res["pages"]))
    elif res.get("gap"):
        lines.append("✍️ Not covered on the site yet — candidate for a new article")
    return "\n".join(lines)


def log_line(res: dict) -> str:
    """One markdown line for changes_log.md (parsed back by digest.py)."""
    pages = ",".join(res.get("pages", []))
    gap = " gap" if res.get("gap") else ""
    return (f"- **Relevance:** {res['score']}{gap} | pages: {pages or '—'} | "
            f"topic: {res.get('topic') or '—'} | {res.get('method', '')}")


LOG_RE = re.compile(r"^(\d)(\s+gap)?\s*\|\s*pages:\s*([^|]*)\|\s*topic:\s*([^|]*)\|", re.S)


def parse_log_line(value: str) -> dict | None:
    m = LOG_RE.match(value.strip())
    if not m:
        return None
    pages = [s.strip() for s in m.group(3).split(",") if s.strip() and s.strip() != "—"]
    topic = m.group(4).strip()
    return {"score": int(m.group(1)), "gap": bool(m.group(2)), "pages": pages,
            "topic": "" if topic == "—" else topic}


# --------------------------------------------------------------------------- #
# Backtest: score the last N logged documents and report (no state changes)
# --------------------------------------------------------------------------- #

def backtest(n: int, send) -> int:
    import digest  # local import: digest imports this module

    pages = load_catalogue()
    entries = digest.parse_entries(digest.LOG_FILE.read_text(encoding="utf-8"))[-n:]
    hits = []
    for e in entries:
        res = score(e.get("title_ka", ""), e.get("title_en", ""), pages)
        print(f"{res['score']} {e['id']} {res.get('topic','')} | {e['title_en'][:90]}")
        if is_alert(res):
            hits.append((e, res))
    lines = [f"🧪 <b>Relevance filter backtest</b> — last {len(entries)} matsne documents, "
             f"{len(pages)} site topics: <b>{len(hits)}</b> would have been sent"]
    for e, res in hits[:15]:
        lines.append(f"\n• {html.escape(e['title_en'][:160])}\n{format_block(res, pages)}")
    msg = "\n".join(lines)
    send(msg[:4000])
    return 0


if __name__ == "__main__":
    import sys

    from monitor import send_telegram

    if len(sys.argv) > 2 and sys.argv[1] == "--backtest":
        sys.exit(backtest(int(sys.argv[2]), send_telegram))
    print("usage: relevance.py --backtest N")
