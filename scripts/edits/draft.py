"""
Draft an article edit for a legal change on branch edit/doc-<id>, and send review buttons.

Env (from draft-edit.yml): DOC_ID, SLUGS (comma-separated, may be empty →
draft a NEW article), SOURCE (matsne), plus ANTHROPIC_API_KEY, TELEGRAM_*,
CLOUDFLARE_API_TOKEN (git push uses the workflow's GITHUB_TOKEN).
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending  # noqa: E402
from lib import (SITE, action_url, claude, extract_json, preview_upload, review_url,  # noqa: E402
                 sh, telegram)

ROOT = Path(__file__).resolve().parents[2]
GUIDES = ROOT / "src/content/guides"
LOG = ROOT / "scripts/matsne_monitor/changes_log.md"
TODAY = dt.date.today().isoformat()

DOC_ID = re.sub(r"[^0-9A-Za-z-]", "", os.environ.get("DOC_ID", ""))
SLUGS = [s for s in re.sub(r"[^a-z0-9,-]", "", os.environ.get("SLUGS", "")).split(",") if s][:3]
SOURCE = os.environ.get("SOURCE", "matsne")
BRANCH = f"edit/doc-{DOC_ID}"


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #

def doc_meta() -> dict:
    text = LOG.read_text(encoding="utf-8") if LOG.exists() else ""
    m = re.search(rf"^## [^\n]*— doc {re.escape(DOC_ID)}\b[\s\S]*?(?=^## |\Z)", text, re.M)
    body = m.group(0) if m else ""

    def f(label: str) -> str:
        mm = re.search(rf"\*\*{re.escape(label)}:\*\*\s*(.+)", body)
        return mm.group(1).strip() if mm else ""

    return {"id": DOC_ID, "title_en": f("Title (EN)"), "title_ka": f("Title (KA)"),
            "published": f("Published"),
            "link": f("Link") or f"https://matsne.gov.ge/ka/document/view/{DOC_ID}"}


def doc_text(link: str) -> str:
    try:
        r = requests.get(link, timeout=60, headers={"User-Agent": "relocation-ge-editor/1.0 (+https://relocation.ge)"})
        r.raise_for_status()
        h = r.text
        i = h.find('id="maindoc"')
        h = h[i:] if i >= 0 else h
        h = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", h)
        t = html.unescape(re.sub(r"<[^>]+>", " ", h))
        t = re.sub(r"[ \t\r\f]+", " ", t)
        t = re.sub(r"\n\s*\n+", "\n\n", t).strip()
        return t[:25000]
    except requests.RequestException as exc:
        print(f"WARN: could not fetch document text: {exc}")
        return ""


# --------------------------------------------------------------------------- #
# Editing helpers
# --------------------------------------------------------------------------- #

def bump_frontmatter(md: str, source: dict | None) -> str:
    end = md.find("\n---", 3)
    if not md.startswith("---") or end < 0:
        return md
    fm, rest = md[: end], md[end:]
    fm = re.sub(r"^reviewed:.*$", f"reviewed: {TODAY}", fm, count=1, flags=re.M)
    # `checked:` is bumped daily by daily-checked.yml on main — leave it alone to avoid merge conflicts.
    if source and source.get("url") and source["url"] not in fm:
        entry = f'  - name: {json.dumps(source["name"], ensure_ascii=False)}\n    url: {source["url"]}\n'
        if re.search(r"^sources:\s*\[\]\s*$", fm, re.M):
            fm = re.sub(r"^sources:\s*\[\]\s*$", "sources:\n" + entry.rstrip("\n"), fm, count=1, flags=re.M)
        elif re.search(r"^sources:\s*$", fm, re.M):
            fm = re.sub(r"^sources:\s*$", "sources:\n" + entry.rstrip("\n"), fm, count=1, flags=re.M)
        else:
            fm = fm.rstrip("\n") + "\nsources:\n" + entry.rstrip("\n")
    return fm + rest


EDIT_SYSTEM = """You maintain relocation.ge, a factual guide for foreigners relocating to Georgia. A new legal act was published. Decide whether the given guide page(s) must change, and if so propose MINIMAL, precise edits.

Rules
- Base every change strictly on the act's text. Never invent numbers, dates or rules. If the act's text is missing or unclear, change nothing and say so.
- Change only what the act changes: amounts, thresholds, deadlines, procedures, document lists, effective dates. Keep the page's tone, structure and markdown.
- Mention the act (number, date) where the changed rule is stated, e.g. "(Government Ordinance No 412 of 20 Nov 2026)", and the date it takes effect if given.
- If a Russian page is provided, mirror every substantive change there in natural Russian.
- Each edit is an exact find/replace: "find" must be copied VERBATIM from the page (at least ~40 characters, unique on the page); "replace" is the new text. Do not edit the YAML frontmatter except the `notice:` line when a prominent warning is justified.
- Prefer 1–6 edits. If nothing on the page is affected, return needed=false.

Return ONLY JSON:
{"needed": true|false,
 "summary_ru": "2–5 short bullet lines in Russian: what changes on the site",
 "reason_ru": "1–2 sentences in Russian: what the act changes and since when",
 "source_name": "English name of the act for the sources list, e.g. 'Government Ordinance No 412 of 20 November 2026 amending Ordinance No 70'",
 "edits": [{"slug": "...", "lang": "en"|"ru", "find": "...", "replace": "..."}]}"""

NEW_SYSTEM = """You write for relocation.ge, a factual guide for foreigners relocating to Georgia. A new legal act covers a topic the site has no page for. Draft a NEW English guide page based strictly on the act's text (never invent facts; if the text is insufficient, keep the page short and say what is not yet known).

Write markdown with YAML frontmatter exactly in this shape (copy field names; category must be one of immigration, work, tax, students, live, about):
---
title: "…(2026)"
category: …
lang: en
summary: "2–3 sentence answer-first summary"
reviewed: {today}
checked: {today}
order: 50
sources:
  - name: "<act name>"
    url: <act link>
faq:
  - q: "…"
    a: "…"
---
Body: H2 sections (##), short paragraphs and lists, 400–900 words, practical: who it affects, what changes, from when, what to do.

Return ONLY JSON: {"slug": "kebab-case-slug-georgia", "markdown": "<full file>", "summary_ru": "2–4 bullet lines in Russian", "reason_ru": "1–2 sentences in Russian"}"""


def apply_edits(files: dict, edits: list[dict], failed: list | None = None) -> list[str]:
    """Apply find/replace edits in-memory. Returns problems (skipped edits);
    edits whose fragment was not found are appended to `failed`."""
    problems = []
    for e in edits:
        key = (e.get("slug"), e.get("lang"))
        if key not in files:
            problems.append(f"unknown page {key}")
            continue
        find, repl = e.get("find", ""), e.get("replace", "")
        n = files[key]["after"].count(find) if find else 0
        if n != 1:
            problems.append(f"{key[0]}/{key[1]}: fragment found {n}× — skipped")
            if failed is not None:
                failed.append(e)
            continue
        files[key]["after"] = files[key]["after"].replace(find, repl, 1)
    return problems


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    if not DOC_ID:
        print("DOC_ID missing")
        return 1

    # Already drafted? Re-send the links instead of drafting twice.
    remote = sh("git", "ls-remote", "--heads", "origin", BRANCH, check=False).strip()
    if remote and remote.split()[0] and len(remote.split()[0]) == 40:
        sha = remote.split()[0]
        telegram(f"ℹ️ Правка по документу {DOC_ID} уже подготовлена.",
                 [[{"text": "👀 Посмотреть правку", "url": review_url(DOC_ID, sha)}]])
        return 0

    meta = doc_meta()
    act = doc_text(meta["link"])
    print(f"Document {DOC_ID}: {meta['title_en'][:120]} | text {len(act)} chars")
    act_block = (f"ACT: {meta['title_en']}\nGeorgian title: {meta['title_ka']}\nPublished: {meta['published']}\n"
                 f"Link: {meta['link']}\n\nTEXT (Georgian, may be truncated):\n{act or '(text unavailable — use the title only)'}")

    files: dict = {}
    new_article = not SLUGS
    if new_article:
        out = extract_json(claude(NEW_SYSTEM.replace("{today}", TODAY), act_block, 9000))
        slug = re.sub(r"[^a-z0-9-]", "", out.get("slug", ""))[:80] or f"law-{DOC_ID}"
        path = GUIDES / "en" / f"{slug}.md"
        if path.exists():
            slug, path = f"{slug}-{DOC_ID}", GUIDES / "en" / f"{slug}-{DOC_ID}.md"
        files[(slug, "en")] = {"path": str(path.relative_to(ROOT)), "before": "", "after": out["markdown"].strip() + "\n", "new": True}
        plan = {"summary_ru": out.get("summary_ru", ""), "reason_ru": out.get("reason_ru", ""), "problems": []}
    else:
        pages_text = []
        for slug in SLUGS:
            for lang in ("en", "ru"):
                p = GUIDES / lang / f"{slug}.md"
                if p.exists():
                    t = p.read_text(encoding="utf-8")
                    files[(slug, lang)] = {"path": str(p.relative_to(ROOT)), "before": t, "after": t, "new": False}
                    pages_text.append(f"=== PAGE slug={slug} lang={lang} ===\n{t}")
        if not files:
            telegram(f"⚠️ Не нашёл страниц {', '.join(SLUGS)} для правки по документу {DOC_ID}.")
            return 1
        out = extract_json(claude(EDIT_SYSTEM, act_block + "\n\n" + "\n\n".join(pages_text), 8000))
        if not out.get("needed") or not out.get("edits"):
            if pending.remove(DOC_ID) and pending.commit_to_main(f"Resolve pending update for doc {DOC_ID}: no change needed [skip ci]"):
                pending.deploy()
            telegram(f"✅ <b>Правка не требуется</b> — документ {DOC_ID}\n{html.escape(out.get('reason_ru', ''))}\n"
                     f"🔗 {html.escape(meta['link'])}")
            return 0
        failed: list = []
        problems = apply_edits(files, out["edits"], failed)
        if failed:
            # One retry: show the model the exact current text and ask it to re-anchor.
            fix = (act_block[:3000] + "\n\nThese edits could not be applied because 'find' was not copied verbatim "
                   "(or not unique). Re-issue them with 'find' copied EXACTLY from the page text below.\n"
                   + json.dumps(failed, ensure_ascii=False) + "\n\n"
                   + "\n\n".join(f"=== PAGE slug={k[0]} lang={k[1]} ===\n{v['after']}" for k, v in files.items()))
            try:
                retry = extract_json(claude(EDIT_SYSTEM, fix, 6000)).get("edits", [])
                problems = [p for p in problems if "fragment" not in p] + apply_edits(files, retry)
            except Exception as exc:  # noqa: BLE001
                print(f"WARN: retry failed: {exc}")
        source = {"name": out.get("source_name") or meta["title_en"][:200], "url": meta["link"]}
        for f in files.values():
            if f["after"] != f["before"]:
                f["after"] = bump_frontmatter(f["after"], source)
        plan = {"summary_ru": out.get("summary_ru", ""), "reason_ru": out.get("reason_ru", ""), "problems": problems}

    changed = {k: v for k, v in files.items() if v["after"] != v["before"]}
    if not changed:
        telegram(f"⚠️ Не удалось применить правку по документу {DOC_ID}: "
                 + html.escape("; ".join(plan["problems"]) or "модель не нашла точных фрагментов"))
        return 1

    # Write files, build + upload a preview version, record the proposal, commit.
    sh("git", "checkout", "-b", BRANCH)
    for f in changed.values():
        Path(ROOT / f["path"]).write_text(f["after"], encoding="utf-8")
    alias = f"edit-{DOC_ID}".lower()
    preview = preview_upload(alias)
    first_slug, first_lang = next(iter(changed))
    proposal = {
        "doc": meta, "branch": BRANCH, "created": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "kind": "new" if new_article else "update",
        "summary_ru": plan["summary_ru"], "reason_ru": plan["reason_ru"], "problems": plan["problems"],
        "preview_url": f"{preview.rstrip('/')}/{first_lang}/{first_slug}/" if preview else "",
        "files": [{"slug": k[0], "lang": k[1], **v} for k, v in changed.items()],
    }
    (ROOT / ".edits").mkdir(exist_ok=True)
    (ROOT / ".edits/proposal.json").write_text(json.dumps(proposal, ensure_ascii=False, indent=1), encoding="utf-8")

    sh("git", "config", "user.name", "relocation-bot")
    sh("git", "config", "user.email", "bot@users.noreply.github.com")
    sh("git", "add", "-A", "src/content", ".edits")
    sh("git", "commit", "-m", f"Draft: update for matsne doc {DOC_ID}\n\n{meta['title_en'][:300]}")
    sh("git", "push", "-u", "origin", BRANCH)
    sha = sh("git", "rev-parse", "HEAD").strip().splitlines()[-1]
    pages = ", ".join(f'<a href="{SITE}/{k[1]}/{k[0]}/">{k[0]} ({k[1]})</a>' for k in changed)
    msg = ("✍️ <b>Правка готова к проверке</b>" + (" — <b>новая статья</b>" if new_article else "") + "\n\n"
           f"📄 {html.escape(meta['title_en'][:300])}\n"
           f"💡 {html.escape(plan['reason_ru'])}\n\n{html.escape(plan['summary_ru'])}\n\n📚 {pages}")
    if plan["problems"]:
        msg += "\n\n⚠️ Пропущено: " + html.escape("; ".join(plan["problems"]))
    buttons = [[{"text": "👀 Посмотреть правку", "url": review_url(DOC_ID, sha)}]]
    if proposal["preview_url"]:
        buttons.append([{"text": "🌐 Страница целиком", "url": proposal["preview_url"]}])
    buttons.append([{"text": "✅ Опубликовать", "url": action_url("publish", DOC_ID, sha)},
                    {"text": "❌ Отклонить", "url": action_url("reject", DOC_ID, sha)}])
    telegram(msg, buttons)
    print(f"Draft {BRANCH} @ {sha} preview={preview}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        telegram(f"⚠️ Не удалось подготовить правку по документу {DOC_ID}: {html.escape(str(exc)[:300])}")
        raise
