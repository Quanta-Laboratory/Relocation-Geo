#!/usr/bin/env python3
"""
Matsne → relocation.ge impact analysis
=====================================

Runs after monitor.py. For every newly published matsne document it answers
"does this touch anything we publish?" and, if it does, prepares the edit:

  1. Pre-filter   — drop obvious noise (auction notices, awards, pardons,
                    personnel orders) with a cheap title regex. No API cost.
  2. Classify     — ONE Claude call for the whole batch: Georgian titles vs. a
                    catalogue of our English pages (slug, title, cited laws).
                    Returns only the documents that affect a page.
  3. Propose      — for each relevant document: read the act's full text from
                    matsne (amending acts are public, no paywall), give Claude
                    the affected English pages, get back exact find/replace
                    edits. Every `find` is verified to occur exactly once.
  4. Localise     — the same edits are carried into every existing translation
                    of the page (de/fr/he/ka/ru/uk), again verified.
  5. Pull request — branch matsne/<doc_id>, one commit, PR with the summary.
  6. Telegram     — summary + before/after + buttons ✅ Apply / ❌ Reject.
                    The buttons are handled by the site Worker
                    (worker/telegram.ts), which merges or closes the PR; the
                    merge to main triggers the normal production deploy.

Nothing is ever committed to main from here: a human presses the button.

Input
-----
  scripts/matsne_monitor/.new_docs.json   written by monitor.py (not committed)

Usage
-----
  python scripts/matsne_monitor/impact.py                 # normal run (CI)
  python scripts/matsne_monitor/impact.py --doc 7050116   # analyse one doc by id
  python scripts/matsne_monitor/impact.py --dry-run ...   # no branch/PR/Telegram
  python scripts/matsne_monitor/impact.py --selftest      # offline tests

Environment
-----------
  ANTHROPIC_API_KEY                    required (without it the step is skipped)
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID optional (no message without them)
  GH_TOKEN                             for `gh pr create` (GITHUB_TOKEN in CI)
  GITHUB_REPOSITORY                    owner/repo (set by Actions)
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GUIDES = ROOT / "src" / "content" / "guides"
NEW_DOCS_FILE = HERE / ".new_docs.json"
IMPACT_LOG = HERE / "impact_log.md"

SITE = "https://relocation.ge"
LANGS = ["en", "de", "fr", "he", "ka", "ru", "uk"]

MODEL_CLASSIFY = "claude-sonnet-4-6"
MODEL_PROPOSE = "claude-sonnet-4-6"
HTTP_TIMEOUT = 60
UA = "relocation-ge-impact/1.0 (+https://relocation.ge)"

MAX_DOCS_TO_CLASSIFY = 60
# monitor.py scores every document with relevance.py (0–3). Only documents that
# change something a page states (3) and name the pages get a proposed edit.
IMPACT_MIN_SCORE = int(os.environ.get("IMPACT_MIN_SCORE", "3"))
MAX_PROPOSALS_PER_RUN = 5
MAX_ACT_CHARS = 60_000

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
REPO = os.environ.get("GITHUB_REPOSITORY", "Quanta-Laboratory/Relocation-Geo")

TBILISI = timezone(timedelta(hours=4))

# --------------------------------------------------------------------------- #
# 1. Pre-filter
# --------------------------------------------------------------------------- #

# Titles that are never about rules our readers live under. Conservative on
# purpose: when in doubt, let Claude decide.
NOISE_RE = re.compile(
    "|".join([
        r"აუქციონ",                 # auction
        r"საჯარო შეტყობინებ",        # public notice (bailiffs, auctions)
        r"დაჯილდოებ",               # state awards
        r"შეწყალებ",                # pardons
        r"თანამდებობაზე დანიშვნ",    # appointment to office
        r"თანამდებობიდან გათავისუფლ", # dismissal from office
        r"სამხედრო წოდებ",          # military ranks
        r"ანტიდემპინგ",             # anti-dumping trade procedure
    ])
)


def prefilter(items: list[dict]) -> list[dict]:
    kept = [it for it in items if not NOISE_RE.search(f"{it.get('title','')} {it.get('topic','')}")]
    return kept[:MAX_DOCS_TO_CLASSIFY]


# --------------------------------------------------------------------------- #
# Page catalogue
# --------------------------------------------------------------------------- #

FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _fm_field(fm: str, name: str) -> str:
    m = re.search(rf"^{name}:\s*(.+?)\s*$", fm, re.MULTILINE)
    return m.group(1).strip().strip('"').strip("'") if m else ""


def build_catalogue() -> list[dict]:
    pages = []
    for path in sorted((GUIDES / "en").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        m = FM_RE.match(text)
        fm = m.group(1) if m else ""
        if _fm_field(fm, "draft") == "true" or _fm_field(fm, "category") == "about":
            continue
        sources = re.findall(r"^\s*-\s*name:\s*(.+?)\s*$", fm, re.MULTILINE)
        pages.append({
            "slug": path.stem,
            "title": _fm_field(fm, "title"),
            "category": _fm_field(fm, "category"),
            "sources": [s.strip().strip('"') for s in sources],
        })
    return pages


def catalogue_text(pages: list[dict]) -> str:
    lines = []
    for p in pages:
        src = "; ".join(p["sources"][:6])
        lines.append(f"{p['slug']} | {p['category']} | {p['title']} | cites: {src}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Claude
# --------------------------------------------------------------------------- #

def claude(system: str, user: str, model: str, max_tokens: int = 4096, cache_system: bool = False) -> str:
    sys_block: list[dict] = [{"type": "text", "text": system}]
    if cache_system:
        sys_block[0]["cache_control"] = {"type": "ephemeral"}
    for attempt in range(3):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "system": sys_block,
                    "messages": [{"role": "user", "content": user}],
                },
                timeout=180,
            )
            if r.status_code in (429, 500, 502, 503, 529):
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json()
            return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        except requests.RequestException as exc:
            print(f"WARN: Claude call failed ({exc}); attempt {attempt + 1}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("Claude API unavailable")


def parse_json(text: str):
    """Extract the first JSON object/array from a model reply."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    start = min([i for i in (t.find("{"), t.find("[")) if i != -1], default=-1)
    if start == -1:
        raise ValueError("no JSON in reply")
    end = max(t.rfind("}"), t.rfind("]"))
    return json.loads(t[start:end + 1])


# --------------------------------------------------------------------------- #
# 2. Classify
# --------------------------------------------------------------------------- #

CLASSIFY_SYSTEM = """You triage newly published Georgian legal acts for relocation.ge, a site that explains Georgian rules to foreigners: visas, residence permits, work, business registration, taxes (incl. small business 1%, individual entrepreneurs), banking/AML, property, study, healthcare, everyday life.

Below is the catalogue of the site's English pages: slug | category | title | laws the page cites.

A document is RELEVANT only if it changes a rule, rate, deadline, fee, document list, eligibility condition, procedure or list that a reader of one of these pages relies on — or it amends a law that a page cites in a way that plausibly affects that page's content.
NOT relevant: acts about a single named company/person/plot, municipal property disposal, internal staffing/charters of state bodies, budget allocations, technical standards unrelated to the pages, ratification of treaties unrelated to tax/visas/residence.

Be strict: a false alarm costs a human review; a miss costs a stale page. When an amending act's title names a law that pages cite (e.g. Tax Code, Law on the Legal Status of Aliens and Stateless Persons, Law on Entrepreneurs, Law on Facilitating the Prevention of Money Laundering), mark it relevant unless the title makes clear the change is elsewhere.

CATALOGUE
{catalogue}"""

CLASSIFY_USER = """New documents (Georgian titles):

{docs}

Reply with JSON only: an array containing ONLY the relevant documents, each
{{"id": "<doc id>", "slugs": ["<slug>", ...], "title_en": "<short English title>", "reason": "<one sentence, English>"}}
Use only slugs from the catalogue, at most 6 per document. Reply [] if none."""


def from_relevance(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """Reuse relevance.py's verdict (attached by monitor.py) instead of a second
    classification call. Returns (relevant, unscored)."""
    relevant, unscored = [], []
    for it in items:
        rel = it.get("relevance")
        if not isinstance(rel, dict):
            unscored.append(it)
            continue
        slugs = [s for s in rel.get("pages", []) if (GUIDES / "en" / f"{s}.md").exists()]
        if rel.get("score", 0) >= IMPACT_MIN_SCORE and slugs:
            relevant.append({**it, "slugs": slugs, "title_en": rel.get("topic", ""), "reason": rel.get("why", "")})
    return relevant, unscored


def classify(items: list[dict], pages: list[dict]) -> list[dict]:
    if not items:
        return []
    docs = "\n".join(f"- id {it['id']}: {it.get('title','')}" + (
        f" — {it['topic']}" if it.get("topic") and it["topic"] != it.get("title") else "") for it in items)
    reply = claude(
        CLASSIFY_SYSTEM.format(catalogue=catalogue_text(pages)),
        CLASSIFY_USER.format(docs=docs),
        MODEL_CLASSIFY,
        max_tokens=4096,
        cache_system=True,
    )
    data = parse_json(reply)
    valid_slugs = {p["slug"] for p in pages}
    by_id = {it["id"]: it for it in items}
    out = []
    for d in data if isinstance(data, list) else []:
        doc_id = str(d.get("id", ""))
        slugs = [s for s in d.get("slugs", []) if s in valid_slugs][:6]
        if doc_id in by_id and slugs:
            out.append({**by_id[doc_id], "slugs": slugs,
                        "title_en": d.get("title_en", ""), "reason": d.get("reason", "")})
    return out


# --------------------------------------------------------------------------- #
# Fetch the act text
# --------------------------------------------------------------------------- #

def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>|</tr>", "\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t\xa0]+", " ", raw)
    raw = re.sub(r"\n\s*\n+", "\n", raw)
    return raw.strip()


def fetch_act_text(doc_id: str) -> str:
    url = f"https://www.matsne.gov.ge/ka/document/view/{doc_id}"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    page = r.text
    # The act body sits in <div id="maindoc">; fall back to the whole page.
    i = page.find('id="maindoc"')
    if i != -1:
        page = page[i:]
    text = html_to_text(page)
    return text[:MAX_ACT_CHARS]


# --------------------------------------------------------------------------- #
# 3. Propose edits (English)
# --------------------------------------------------------------------------- #

PROPOSE_SYSTEM = """You keep relocation.ge accurate. You receive a newly published Georgian legal act (full Georgian text) and the Markdown source of the English pages that may be affected.

Decide whether the act actually changes anything these pages state. If it does, write the minimal edits.

Rules for edits:
- Each edit is an exact find/replace on ONE file. `find` must be copied verbatim from the file (same punctuation, Markdown and line breaks) and must occur exactly once; keep it short — the sentence, list item, table row or FAQ answer that changes.
- You may edit body text, the front-matter `summary`, `faq` answers and `notice`. Never touch `reviewed`, `checked`, `order`, `category`, `parent`, `lang`.
- When the act is a source the page should cite, add it to `sources` (edit the last existing source entry to append a new `  - name: ...\\n    url: https://matsne.gov.ge/ka/document/view/<id>` entry; name in English, e.g. "Law of Georgia No 123 of 1 Nov 2026 amending the Tax Code (Georgian original)").
- If the change takes effect later, say so in the text ("From 1 March 2027, ..."), keeping the current rule until then.
- Match the page's voice: plain, factual, answer-first, British spelling. No hedging boilerplate.
- State only what the act says. Do not guess numbers. If the act's effect on the page is unclear, return no edits and explain in `manual_ru`.

Reply with JSON only:
{
  "applies": true|false,
  "title_en": "short English title of the act",
  "summary_ru": "2–3 sentences in Russian: what changed and for whom",
  "effective": "date or condition it takes effect, in Russian",
  "edits": [{"file": "en/<slug>.md", "find": "...", "replace": "...", "why_ru": "one line in Russian"}],
  "manual_ru": "anything a human must check that is not expressed as edits, in Russian ('' if none)"
}"""


def read_page(rel: str) -> str:
    return (GUIDES / rel).read_text(encoding="utf-8")


def propose(doc: dict, act_text: str) -> dict:
    files = []
    for slug in doc["slugs"]:
        rel = f"en/{slug}.md"
        files.append(f"===== FILE {rel} =====\n{read_page(rel)}")
    user = (
        f"ACT: matsne document {doc['id']} — {doc.get('title','')}\n"
        f"Link: https://www.matsne.gov.ge/ka/document/view/{doc['id']}\n"
        f"Published: {doc.get('pub_date','')}\n"
        f"Why it was flagged: {doc.get('reason','')}\n\n"
        f"===== ACT TEXT (Georgian) =====\n{act_text}\n\n" + "\n\n".join(files)
    )
    result = parse_json(claude(PROPOSE_SYSTEM, user, MODEL_PROPOSE, max_tokens=8000))
    if not isinstance(result, dict):
        raise ValueError("proposal is not an object")
    result.setdefault("edits", [])
    return result


def validate_edits(edits: list[dict], allowed_prefix: str | None = None) -> tuple[list[dict], list[str]]:
    """Keep edits whose `find` occurs exactly once in the target file."""
    good, problems = [], []
    for e in edits:
        rel = str(e.get("file", "")).lstrip("/")
        rel = rel.removeprefix("src/content/guides/")
        find, repl = e.get("find", ""), e.get("replace", "")
        if allowed_prefix and not rel.startswith(allowed_prefix):
            problems.append(f"{rel}: outside {allowed_prefix}")
            continue
        path = GUIDES / rel
        if not path.exists() or ".." in rel:
            problems.append(f"{rel}: file not found")
            continue
        if not find or find == repl:
            problems.append(f"{rel}: empty or no-op edit")
            continue
        n = path.read_text(encoding="utf-8").count(find)
        if n != 1:
            problems.append(f"{rel}: `find` matched {n} times")
            continue
        good.append({**e, "file": rel})
    return good, problems


# --------------------------------------------------------------------------- #
# 4. Localise the edits into existing translations
# --------------------------------------------------------------------------- #

LOCALISE_SYSTEM = """You carry an approved content change from the English page into its translation, keeping the translation's language, terminology and style.

You get the English edits (find → replace) and the full Markdown of the translated page. Locate the passages in the translation that correspond to each English `find`, and write equivalent edits.
`find` must be copied verbatim from the TRANSLATED file and occur exactly once. If a passage has no counterpart in the translation (the translation is shorter), skip it.

Reply with JSON only: {"edits": [{"find": "...", "replace": "..."}]}"""


def localise(slug: str, en_edits: list[dict]) -> tuple[list[dict], list[str]]:
    out, problems = [], []
    pairs = "\n\n".join(f"--- FIND ---\n{e['find']}\n--- REPLACE ---\n{e['replace']}" for e in en_edits)
    for lang in LANGS[1:]:
        rel = f"{lang}/{slug}.md"
        if not (GUIDES / rel).exists():
            continue
        try:
            reply = parse_json(claude(
                LOCALISE_SYSTEM,
                f"ENGLISH EDITS\n{pairs}\n\n===== TRANSLATED FILE {rel} =====\n{read_page(rel)}",
                MODEL_PROPOSE, max_tokens=6000,
            ))
            edits = [{"file": rel, **e} for e in reply.get("edits", [])]
        except Exception as exc:  # noqa: BLE001 — a failed translation must not block the PR
            problems.append(f"{rel}: localisation failed ({exc})")
            continue
        good, bad = validate_edits(edits, allowed_prefix=f"{lang}/")
        out += good
        problems += bad
        if not good and not bad:
            problems.append(f"{rel}: no matching passage — check manually")
    return out, problems


# --------------------------------------------------------------------------- #
# 5. Branch + PR
# --------------------------------------------------------------------------- #

def sh(*args: str, check: bool = True) -> str:
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} → {r.returncode}: {r.stderr.strip()[:500]}")
    return r.stdout.strip()


def branch_exists(branch: str) -> bool:
    return bool(sh("git", "ls-remote", "--heads", "origin", branch, check=False))


def apply_edits(edits: list[dict]) -> None:
    for e in edits:
        path = GUIDES / e["file"]
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace(e["find"], e["replace"], 1), encoding="utf-8")


def pr_body(doc: dict, prop: dict, edits: list[dict], problems: list[str]) -> str:
    link = f"https://www.matsne.gov.ge/ka/document/view/{doc['id']}"
    lines = [
        f"**Акт:** [{prop.get('title_en') or doc.get('title_en') or doc['id']}]({link})",
        f"**Опубликован:** {doc.get('pub_date','—')}",
        f"**Вступает в силу:** {prop.get('effective') or '—'}",
        "",
        prop.get("summary_ru", ""),
        "",
        "### Правки",
    ]
    for e in edits:
        why = f" — {e['why_ru']}" if e.get("why_ru") else ""
        lines.append(f"- `{e['file']}`{why}")
    if prop.get("manual_ru"):
        lines += ["", "### Проверить вручную", prop["manual_ru"]]
    if problems:
        lines += ["", "### Не удалось применить автоматически"] + [f"- {p}" for p in problems]
    lines += ["", "_Создано matsne impact (scripts/matsne_monitor/impact.py). "
              "Слияние — кнопкой «Применить» в Telegram или здесь._"]
    return "\n".join(lines)


def open_pr(doc: dict, prop: dict, edits: list[dict], problems: list[str]) -> tuple[int, str]:
    branch = f"matsne/{doc['id']}"
    base = sh("git", "rev-parse", "--abbrev-ref", "HEAD")
    sh("git", "checkout", "-B", branch)
    try:
        apply_edits(edits)
        sh("git", "add", *[str(GUIDES / e["file"]) for e in edits])
        title = f"matsne {doc['id']}: {prop.get('title_en') or doc.get('title_en') or 'legal update'}"[:120]
        sh("git", "commit", "-m", f"{title}\n\nSource: https://www.matsne.gov.ge/ka/document/view/{doc['id']}")
        sh("git", "push", "-f", "-u", "origin", branch)
        url = sh("gh", "pr", "create", "--base", base, "--head", branch,
                 "--title", title, "--body", pr_body(doc, prop, edits, problems))
        number = int(url.rstrip("/").split("/")[-1])
        return number, url
    finally:
        sh("git", "checkout", base, check=False)
        sh("git", "checkout", "--", ".", check=False)


# --------------------------------------------------------------------------- #
# 6. Telegram
# --------------------------------------------------------------------------- #

def tg(method: str, payload: dict) -> dict | None:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return None
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}",
                          json={"chat_id": TELEGRAM_CHAT_ID, **payload}, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        print(f"WARN: Telegram {method} failed ({exc})")
        return None


def _short(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s.replace("**", "")).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def telegram_text(doc: dict, prop: dict, edits: list[dict], pr_url: str | None, problems: list[str]) -> str:
    e = html.escape
    link = f"https://www.matsne.gov.ge/ka/document/view/{doc['id']}"
    slugs = sorted({x["file"].split("/", 1)[1][:-3] for x in edits} or set(doc["slugs"]))
    parts = [
        "⚖️ <b>Изменение касается relocation.ge</b>",
        f"📄 <a href=\"{link}\">{e(_short(prop.get('title_en') or doc.get('title_en') or doc.get('title',''), 200))}</a>",
        f"🗓 Вступает в силу: {e(prop.get('effective') or '—')}",
        "",
        e(_short(prop.get("summary_ru", ""), 700)),
        "",
        "<b>Страницы:</b> " + ", ".join(f"<a href=\"{SITE}/en/{s}\">{e(s)}</a>" for s in slugs),
    ]
    en_edits = [x for x in edits if x["file"].startswith("en/")]
    for x in en_edits[:3]:
        parts += [
            "",
            f"<b>{e(x['file'])}</b>" + (f" — {e(_short(x.get('why_ru',''), 150))}" if x.get("why_ru") else ""),
            f"<blockquote>Было: {e(_short(x['find'], 300))}</blockquote>",
            f"<blockquote>Станет: {e(_short(x['replace'], 400))}</blockquote>",
        ]
    if len(en_edits) > 3:
        parts.append(f"…и ещё {len(en_edits) - 3} правок (EN)")
    n_loc = len(edits) - len(en_edits)
    if n_loc:
        parts.append(f"🌐 Переводы: {n_loc} правок в других языках")
    if prop.get("manual_ru"):
        parts += ["", "⚠️ <b>Проверить вручную:</b> " + e(_short(prop["manual_ru"], 400))]
    if problems:
        parts.append(f"⚠️ Не применено автоматически: {len(problems)} (см. PR)")
    text = "\n".join(parts)
    return text[:4000]


def notify_proposal(doc: dict, prop: dict, edits: list[dict], pr_number: int, pr_url: str, problems: list[str]) -> None:
    tg("sendMessage", {
        "text": telegram_text(doc, prop, edits, pr_url, problems),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": {"inline_keyboard": [
            [{"text": "✅ Применить", "callback_data": f"mx:a:{pr_number}"},
             {"text": "❌ Отклонить", "callback_data": f"mx:r:{pr_number}"}],
            [{"text": "👀 Посмотреть изменения", "url": f"{pr_url}/files"}],
        ]},
    })


def notify_info(doc: dict, prop: dict | None, note: str) -> None:
    e = html.escape
    link = f"https://www.matsne.gov.ge/ka/document/view/{doc['id']}"
    title = (prop or {}).get("title_en") or doc.get("title_en") or doc.get("title", "")
    lines = [
        "ℹ️ <b>Может касаться relocation.ge</b>",
        f"📄 <a href=\"{link}\">{e(_short(title, 200))}</a>",
        "<b>Страницы:</b> " + ", ".join(e(s) for s in doc["slugs"]),
        "",
        e(_short((prop or {}).get("summary_ru") or doc.get("reason", ""), 700)),
    ]
    if note:
        lines += ["", e(_short(note, 600))]
    tg("sendMessage", {"text": "\n".join(lines)[:4000], "parse_mode": "HTML", "disable_web_page_preview": True})


# --------------------------------------------------------------------------- #
# Log
# --------------------------------------------------------------------------- #

def log(doc: dict, outcome: str) -> None:
    if not IMPACT_LOG.exists():
        IMPACT_LOG.write_text("# Matsne impact log\n\nRelevant documents and what was done.\n", encoding="utf-8")
    stamp = datetime.now(TBILISI).strftime("%Y-%m-%d %H:%M")
    with IMPACT_LOG.open("a", encoding="utf-8") as f:
        f.write(f"\n- {stamp} — doc {doc['id']} → {', '.join(doc['slugs'])}: {outcome}\n")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def process(doc: dict, dry_run: bool) -> None:
    branch = f"matsne/{doc['id']}"
    if not dry_run and branch_exists(branch):
        print(f"doc {doc['id']}: branch exists, skipping")
        return
    try:
        act = fetch_act_text(doc["id"])
    except requests.RequestException as exc:
        notify_info(doc, None, f"Не удалось прочитать текст акта: {exc}")
        log(doc, "act text unavailable")
        return

    prop = propose(doc, act)
    edits, problems = validate_edits(prop.get("edits", []), allowed_prefix="en/")
    if not prop.get("applies") or not edits:
        note = prop.get("manual_ru") or ""
        if prop.get("applies") and problems:
            note = (note + "\nПравки не удалось сопоставить с текстом: " + "; ".join(problems)).strip()
        if prop.get("applies") or note:
            notify_info(doc, prop, note)
        log(doc, "no edit needed" if not prop.get("applies") else "needs manual edit")
        print(f"doc {doc['id']}: applies={prop.get('applies')} edits=0 problems={problems}")
        return

    for slug in sorted({e["file"].split("/", 1)[1][:-3] for e in edits}):
        loc, loc_problems = localise(slug, [e for e in edits if e["file"] == f"en/{slug}.md"])
        edits += loc
        problems += loc_problems

    if dry_run:
        print(json.dumps({"doc": doc["id"], "proposal": prop, "edits": edits, "problems": problems},
                         ensure_ascii=False, indent=2))
        print(telegram_text(doc, prop, edits, None, problems))
        return

    number, url = open_pr(doc, prop, edits, problems)
    notify_proposal(doc, prop, edits, number, url, problems)
    log(doc, f"PR #{number} ({len(edits)} edits)")
    print(f"doc {doc['id']}: PR #{number} {url}")


def load_docs(args) -> list[dict]:
    if args.doc:
        return [{"id": d, "title": f"matsne document {d}", "topic": "", "pub_date": ""} for d in args.doc]
    if not NEW_DOCS_FILE.exists():
        return []
    return json.loads(NEW_DOCS_FILE.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", action="append", help="analyse this matsne doc id (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="print the proposal; no PR, no Telegram")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--sample", action="store_true", help="send a demo alert to Telegram (no Claude, no PR)")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.sample:
        return send_sample()
    if not ANTHROPIC_API_KEY:
        print("NOTE: ANTHROPIC_API_KEY not set — impact analysis skipped.")
        return 0

    docs = load_docs(args)
    if not docs:
        print("No new documents to analyse.")
        return 0

    pages = build_catalogue()
    if args.doc:
        # Manual run: we only have ids — fetch the act and let classify see its opening lines.
        for d in docs:
            try:
                d["title"] = _short(fetch_act_text(d["id"]), 600)
            except requests.RequestException:
                pass
        relevant = classify(docs, pages)
    else:
        relevant, unscored = from_relevance(docs)
        candidates = prefilter(unscored)
        print(f"{len(docs)} new doc(s): {len(relevant)} from relevance filter, {len(candidates)} to classify.")
        relevant += classify(candidates, pages)

    print(f"Relevant: {[(d['id'], d['slugs']) for d in relevant]}")

    for doc in relevant[:MAX_PROPOSALS_PER_RUN]:
        try:
            process(doc, args.dry_run)
        except Exception as exc:  # noqa: BLE001 — one bad document must not stop the rest
            print(f"ERROR: doc {doc['id']}: {exc}")
            notify_info(doc, None, f"Ошибка анализа: {exc}")
            log(doc, f"error: {exc}")
    for doc in relevant[MAX_PROPOSALS_PER_RUN:]:
        notify_info(doc, None, "Лимит анализа за запуск исчерпан — проверьте вручную.")
        log(doc, "over per-run limit")
    return 0


# --------------------------------------------------------------------------- #
# Demo message (layout check — no Claude, no PR)
# --------------------------------------------------------------------------- #

def send_sample() -> int:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("Telegram secrets missing.")
        return 1
    rel = "en/renting-a-home-in-georgia.md"
    find = "Three months, given by either the tenant or the landlord. A lease that does not state a term is treated as indefinite."
    if find not in read_page(rel):
        find = read_page(rel).split("\n---", 1)[1].strip().split("\n")[0]
    doc = {"id": "0000000", "slugs": ["renting-a-home-in-georgia"], "pub_date": ""}
    prop = {
        "title_en": "DEMO — amendment to the Civil Code (not a real act)",
        "effective": "ТЕСТ — с 1 марта 2027",
        "summary_ru": "Это тестовое сообщение, чтобы проверить формат. Реального изменения закона нет, страница не меняется.",
        "manual_ru": "",
    }
    edits = [{"file": rel, "find": find,
              "replace": find.replace("Three months", "Two months (DEMO)"), "why_ru": "пример правки"}]
    text = "🧪 <b>ТЕСТ</b> — так будет выглядеть уведомление. Кнопки заработают после настройки вебхука.\n\n" + \
        telegram_text(doc, prop, edits, None, [])
    r = tg("sendMessage", {
        "text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": True,
        "reply_markup": {"inline_keyboard": [
            [{"text": "✅ Применить", "callback_data": "mx:demo"}, {"text": "❌ Отклонить", "callback_data": "mx:demo"}],
            [{"text": "👀 Посмотреть изменения", "url": f"https://github.com/{REPO}/pull/1/files"}],
        ]},
    })
    print("sent" if r and r.get("ok") else f"failed: {r}")
    return 0 if r and r.get("ok") else 1


# --------------------------------------------------------------------------- #
# Self-test (offline)
# --------------------------------------------------------------------------- #

def selftest() -> int:
    ok = True

    def check(cond: bool, msg: str):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + msg)
        ok = ok and cond

    noise = [{"id": "1", "title": "შპს „კონსალტინგ გრუპსის“ საჯარო შეტყობინება აუქციონის დანიშვნის შესახებ"},
             {"id": "2", "title": "„საქართველოს საგადასახადო კოდექსში“ ცვლილების შეტანის შესახებ"}]
    check([d["id"] for d in prefilter(noise)] == ["2"], "prefilter drops auction notice, keeps Tax Code amendment")

    pages = build_catalogue()
    check(len(pages) > 50, f"catalogue built ({len(pages)} pages)")
    check(any(p["slug"] == "small-business-status-georgia" for p in pages), "catalogue has small-business page")

    check(parse_json('```json\n[{"a":1}]\n```') == [{"a": 1}], "parse_json strips fences")
    check(parse_json('Sure: {"x": 2} done') == {"x": 2}, "parse_json finds embedded object")

    sample = read_page("en/renting-a-home-in-georgia.md")
    unique = "Three months, given by either the tenant or the landlord."
    good, bad = validate_edits([
        {"file": "en/renting-a-home-in-georgia.md", "find": unique, "replace": unique.replace("Three", "Two")},
        {"file": "en/renting-a-home-in-georgia.md", "find": "the", "replace": "THE"},
        {"file": "en/nope.md", "find": "x", "replace": "y"},
        {"file": "../../etc/passwd", "find": "x", "replace": "y"},
    ], allowed_prefix="en/")
    check(unique in sample and len(good) == 1, "validate keeps the unique edit")
    check(len(bad) == 3, "validate rejects ambiguous / missing / traversal edits")

    doc = {"id": "123", "slugs": ["renting-a-home-in-georgia"], "pub_date": "x"}
    prop = {"title_en": "Civil Code amendment", "effective": "с 1 марта 2027", "summary_ru": "Срок уведомления сокращён.",
            "manual_ru": ""}
    text = telegram_text(doc, prop, good, None, [])
    check("Было:" in text and "Станет:" in text and len(text) <= 4000, "telegram text has before/after")

    rel_docs = [
        {"id": "a", "relevance": {"score": 3, "pages": ["renting-a-home-in-georgia", "no-such-page"], "topic": "T", "why": "w"}},
        {"id": "b", "relevance": {"score": 2, "pages": ["renting-a-home-in-georgia"]}},
        {"id": "c", "relevance": {"score": 3, "pages": [], "gap": True}},
        {"id": "d", "title": "x"},
    ]
    r, u = from_relevance(rel_docs)
    check([d["id"] for d in r] == ["a"] and r[0]["slugs"] == ["renting-a-home-in-georgia"],
          "relevance hand-off: only score 3 with existing pages")
    check([d["id"] for d in u] == ["d"], "relevance hand-off: unscored docs go to classify")

    print("ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
