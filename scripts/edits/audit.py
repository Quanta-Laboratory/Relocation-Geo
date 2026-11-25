"""
Content audit: check every guide against the legal acts the matsne monitor has
logged (changes_log.md, since 2026-07-07) and report pages that are out of date.

  1. Score all logged documents against the live site catalogue (batched).
  2. For each page with relevant acts, read the acts' text and the page, and ask
     whether each act is already reflected, makes the page outdated, or doesn't
     apply.
  3. Write a report (scripts/edits/audits/<date>.md) and send Telegram messages
     with "✍️ Подготовить правку" buttons for every outdated finding.

Does not change any page or the pending-updates banner.
Env: ANTHROPIC_API_KEY, TELEGRAM_*, AUDIT_SINCE (YYYY-MM-DD, optional).
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts/matsne_monitor"))

import relevance  # noqa: E402
from draft import doc_text  # noqa: E402
from lib import SITE, claude, extract_json, start_url, telegram  # noqa: E402

LOG = ROOT / "scripts/matsne_monitor/changes_log.md"
GUIDES = ROOT / "src/content/guides"
OUT_DIR = HERE / "audits"
SINCE = os.environ.get("AUDIT_SINCE", "")
BATCH = 25
MAX_ACTS_PER_PAGE = 6


def entries() -> list[dict]:
    text = LOG.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"^## (\S+) [^\n]*— doc (\d+)[^\n]*\n([\s\S]*?)(?=^## |\Z)", text, re.M):
        body = m.group(3)

        def f(label: str) -> str:
            mm = re.search(rf"\*\*{re.escape(label)}:\*\*\s*(.+)", body)
            return mm.group(1).strip() if mm else ""

        if SINCE and m.group(1) < SINCE:
            continue
        out.append({"date": m.group(1), "id": m.group(2), "title_en": f("Title (EN)"),
                    "title_ka": f("Title (KA)"), "published": f("Published"),
                    "link": f("Link") or f"https://matsne.gov.ge/ka/document/view/{m.group(2)}"})
    # de-duplicate by id, keep latest
    return list({e["id"]: e for e in out}.values())


def score_batch(batch: list[dict], pages: list[dict]) -> list[dict]:
    system = relevance._system_prompt(pages).replace(
        'Return ONLY JSON: {"score"',
        'You will receive SEVERAL documents. Return ONLY a JSON object {"results": [one object per document, same order, each with an extra "id" field]}. Each object: {"score"',
    )
    docs = "\n".join(f'- id={d["id"]} | {d["title_en"][:400]} | {d["title_ka"][:400]}' for d in batch)
    data = extract_json(claude(system, f"DOCUMENTS:\n{docs}", 4000))
    known = {p["slug"] for p in pages}
    res = []
    for r in data.get("results", []):
        res.append({"id": str(r.get("id")), "score": int(r.get("score", 0)),
                    "pages": [s for s in r.get("pages", []) if s in known][:3],
                    "topic": str(r.get("topic", ""))[:80], "gap": bool(r.get("gap"))})
    return res


CHECK_SYSTEM = """You audit a page of relocation.ge (a factual guide for foreigners in Georgia) against legal acts published since July 2026. For EACH act decide:
- "outdated": the act changes something the page states (amount, threshold, deadline, procedure, list, effective date) and the page does NOT yet reflect it;
- "reflected": the page already states the new rule (or cites the act);
- "not_applicable": the act doesn't affect what the page says.
Use only the act texts and the page. Be precise and conservative: "outdated" only when you can name the concrete discrepancy.

Return ONLY JSON: {"acts": [{"id": "...", "status": "outdated|reflected|not_applicable", "what_ru": "≤40 words in Russian: the concrete discrepancy (for outdated) or why"}]}"""


def check_page(slug: str, acts: list[dict]) -> list[dict]:
    page = (GUIDES / "en" / f"{slug}.md")
    if not page.exists():
        return []
    blocks = []
    for a in acts:
        txt = doc_text(a["link"])[:6000].encode("utf-8", "ignore").decode("utf-8")
        txt = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", txt)
        blocks.append(f"=== ACT id={a['id']} published={a['published'] or a['date']} ===\n{a['title_en']}\n{a['title_ka']}\n{txt or '(text unavailable)'}")
        time.sleep(1)
    out = extract_json(claude(CHECK_SYSTEM, f"PAGE slug={slug}:\n{page.read_text(encoding='utf-8')}\n\n" + "\n\n".join(blocks), 3000))
    return out.get("acts", [])


def main() -> int:
    pages = relevance.load_catalogue()
    titles = {p["slug"]: p["title"] for p in pages}
    docs = entries()
    print(f"Auditing {len(docs)} logged documents against {len(pages)} pages.")

    # Scores and page verdicts are cached in audits/state.json so a re-run only
    # does the missing work (e.g. pages that failed last time).
    OUT_DIR.mkdir(exist_ok=True)
    state_file = OUT_DIR / "state.json"
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    scores: dict[str, dict] = state.get("scores", {})
    todo = [d for d in docs if d["id"] not in scores]
    print(f"Cached scores: {len(scores)}; to score: {len(todo)}")
    docs_all, docs = docs, todo
    for i in range(0, len(docs), BATCH):
        try:
            for r in score_batch(docs[i:i + BATCH], pages):
                scores[r["id"]] = r
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: batch {i} failed: {exc}")
        print(f"scored {min(i + BATCH, len(docs))}/{len(docs)}")
    docs = docs_all
    state["scores"] = scores
    state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    by_id = {d["id"]: d for d in docs}
    relevant = [(by_id[i], s) for i, s in scores.items() if i in by_id and s["score"] >= 2]
    per_page: dict[str, list[dict]] = defaultdict(list)
    gaps = []
    for d, s in relevant:
        if s["pages"]:
            for slug in s["pages"]:
                per_page[slug].append({**d, "score": s["score"], "topic": s["topic"]})
        elif s["gap"]:
            gaps.append((d, s))
    print(f"Relevant: {len(relevant)} docs; pages to check: {len(per_page)}; gaps: {len(gaps)}")

    findings: dict[str, list[dict]] = state.get("findings", {})
    for slug, acts in sorted(per_page.items(), key=lambda kv: -len(kv[1])):
        if slug in findings:
            continue
        acts = sorted(acts, key=lambda a: (-a["score"], a["date"]), reverse=False)[:MAX_ACTS_PER_PAGE]
        try:
            verdicts = check_page(slug, acts)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: check {slug} failed: {exc}")
            continue
        findings[slug] = [{**next((a for a in acts if a["id"] == str(v.get("id"))), {"id": str(v.get("id"))}), **v}
                          for v in verdicts]
        print(slug, [(v.get("id"), v.get("status")) for v in verdicts])
        state["findings"] = findings
        state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    # ---- report -----------------------------------------------------------------
    today = dt.date.today().isoformat()
    outdated = [(slug, f) for slug, fs in findings.items() for f in fs if f.get("status") == "outdated"]
    lines = [f"# Content audit {today}", "",
             f"Documents scanned: {len(docs)} (matsne log since {docs[0]['date'] if docs else '—'}). "
             f"Relevant: {len(relevant)}. Pages checked: {len(findings)}. Outdated findings: {len(outdated)}.", ""]
    for slug, fs in findings.items():
        lines.append(f"## {titles.get(slug, slug)} — {SITE}/en/{slug}/")
        for f in fs:
            lines.append(f"- **{f.get('status')}** — [{f.get('title_en', '')[:160]}]({f.get('link', '')}) ({f.get('published') or f.get('date', '')}): {f.get('what_ru', '')}")
        lines.append("")
    if gaps:
        lines.append("## Topics not covered on the site (candidates for new articles)")
        for d, s in gaps:
            lines.append(f"- {s['topic']} — [{d['title_en'][:160]}]({d['link']})")
    OUT_DIR.mkdir(exist_ok=True)
    report = OUT_DIR / f"{today}.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report: {report}")

    # ---- Telegram ---------------------------------------------------------------
    telegram(f"🔍 <b>Аудит статей по изменениям законодательства</b>\n"
             f"Документов с {docs[0]['date'] if docs else '—'}: {len(docs)} · относятся к сайту: {len(relevant)}\n"
             f"Проверено страниц: {len(findings)} · <b>устарело: {len(outdated)}</b> · тем без статьи: {len(gaps)}\n"
             f"Полный отчёт: https://github.com/Quanta-Laboratory/Relocation-Geo/blob/main/scripts/edits/audits/{today}.md")
    sent = set(state.get("sent", []))
    for slug, f in outdated:
        key = f"{slug}:{f.get('id')}"
        if key in sent:
            continue
        sent.add(key)
        telegram(f"🔴 <b>{html.escape(titles.get(slug, slug))}</b>\n{SITE}/en/{slug}/\n\n"
                 f"📄 {html.escape(f.get('title_en', '')[:250])} ({html.escape(f.get('published') or f.get('date', ''))})\n"
                 f"⚠️ {html.escape(f.get('what_ru', ''))}",
                 [[{"text": "✍️ Подготовить правку", "url": start_url(f["id"], [slug])}]])
        time.sleep(1)
    state["sent"] = sorted(sent)
    state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    if gaps:
        msg = "✍️ <b>Темы, которых нет на сайте</b> (кандидаты на новые статьи):\n" + "\n".join(
            f"• {html.escape(s['topic'] or d['title_en'][:100])}" for d, s in gaps[:15])
        telegram(msg, [[{"text": f"✍️ Черновик: {(s['topic'] or d['id'])[:40]}", "url": start_url(d["id"], [])}]
                       for d, s in gaps[:8]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
