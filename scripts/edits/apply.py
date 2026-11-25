"""
Act on a drafted edit (branch edit/doc-<id>): publish, reject, or update text.

Env (from apply-edit.yml): ACTION=publish|reject|update, DOC_ID, CHANGES (JSON
list of {"path": "...", "find": "...", "replace": "..."} for ACTION=update),
plus TELEGRAM_*, ANTHROPIC_API_KEY, CLOUDFLARE_API_TOKEN, GH_TOKEN (to dispatch
the deploy). Pushes use the workflow's GITHUB_TOKEN.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import SITE, action_url, preview_upload, review_url, sh, telegram  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ACTION = os.environ.get("ACTION", "")
DOC_ID = re.sub(r"[^0-9A-Za-z-]", "", os.environ.get("DOC_ID", ""))
BRANCH = f"edit/doc-{DOC_ID}"


def git_identity() -> None:
    sh("git", "config", "user.name", "relocation-bot")
    sh("git", "config", "user.email", "bot@users.noreply.github.com")


def branch_exists() -> bool:
    return bool(sh("git", "ls-remote", "--heads", "origin", BRANCH, check=False).strip())


def checkout_branch() -> dict:
    sh("git", "fetch", "origin", BRANCH)
    sh("git", "checkout", "-B", BRANCH, f"origin/{BRANCH}")
    p = ROOT / ".edits/proposal.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def publish() -> int:
    prop = checkout_branch()
    git_identity()
    sh("git", "checkout", "main")
    sh("git", "pull", "--ff-only", "origin", "main")
    sh("git", "merge", "--squash", f"origin/{BRANCH}")
    sh("git", "rm", "-r", "-q", "--cached", "--ignore-unmatch", ".edits")
    sh("rm", "-rf", ".edits")
    title = (prop.get("doc") or {}).get("title_en", "")[:200]
    sh("git", "commit", "-m", f"Content update for matsne doc {DOC_ID}\n\n{title}\n\nApproved via Telegram review.")
    sh("git", "push", "origin", "main")
    sh("git", "push", "origin", "--delete", BRANCH, check=False)
    # Pushes made with GITHUB_TOKEN don't trigger push workflows — deploy explicitly.
    sh("gh", "workflow", "run", "deploy.yml", "--ref", "main")
    pages = ", ".join(f'<a href="{SITE}/{f["lang"]}/{f["slug"]}/">{f["slug"]} ({f["lang"]})</a>'
                      for f in prop.get("files", []))
    telegram(f"✅ <b>Опубликовано</b> — документ {DOC_ID}\n{pages}\nСайт обновится через 2–3 минуты.")
    return 0


def reject() -> int:
    sh("git", "push", "origin", "--delete", BRANCH)
    telegram(f"❌ Правка по документу {DOC_ID} отклонена. Сайт не изменён.")
    return 0


def update() -> int:
    changes = json.loads(os.environ.get("CHANGES", "[]") or "[]")
    prop = checkout_branch()
    content_root = str((ROOT / "src/content").resolve())
    applied, problems = 0, []
    for c in changes:
        path = (ROOT / c.get("path", "")).resolve()
        if not path.is_file() or not str(path).startswith(content_root):
            problems.append(f"bad path {c.get('path')}")
            continue
        text = path.read_text(encoding="utf-8")
        if not c.get("find") or text.count(c["find"]) != 1:
            problems.append(f"{c.get('path')}: fragment not found exactly once")
            continue
        path.write_text(text.replace(c["find"], c.get("replace", ""), 1), encoding="utf-8")
        applied += 1
    if not applied:
        telegram(f"⚠️ Не удалось применить ваши правки (документ {DOC_ID}): " + html.escape("; ".join(problems)))
        return 1

    for f in prop.get("files", []):
        f["after"] = (ROOT / f["path"]).read_text(encoding="utf-8")
    preview = preview_upload(f"edit-{DOC_ID}".lower())
    if preview and prop.get("files"):
        f0 = prop["files"][0]
        prop["preview_url"] = f"{preview.rstrip('/')}/{f0['lang']}/{f0['slug']}/"
    prop["problems"] = problems
    (ROOT / ".edits/proposal.json").write_text(json.dumps(prop, ensure_ascii=False, indent=1), encoding="utf-8")

    git_identity()
    sh("git", "add", "-A", "src/content", ".edits")
    sh("git", "commit", "-m", f"Edit draft updated from the review page (doc {DOC_ID})")
    sh("git", "push", "origin", BRANCH)
    sha = sh("git", "rev-parse", "HEAD").strip().splitlines()[-1]

    buttons = [[{"text": "👀 Посмотреть правку", "url": review_url(DOC_ID, sha)}]]
    if prop.get("preview_url"):
        buttons.append([{"text": "🌐 Страница целиком", "url": prop["preview_url"]}])
    buttons.append([{"text": "✅ Опубликовать", "url": action_url("publish", DOC_ID, sha)},
                    {"text": "❌ Отклонить", "url": action_url("reject", DOC_ID, sha)}])
    msg = f"✏️ <b>Правка обновлена</b> — документ {DOC_ID}: изменений применено: {applied}."
    if problems:
        msg += "\n⚠️ " + html.escape("; ".join(problems))
    telegram(msg, buttons)
    return 0


def main() -> int:
    if not branch_exists():
        telegram(f"ℹ️ Правка по документу {DOC_ID} уже опубликована или отклонена — ничего не сделано.")
        return 0
    return {"publish": publish, "reject": reject, "update": update}[ACTION]()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        telegram(f"⚠️ Действие «{ACTION}» для документа {DOC_ID} не выполнено: {html.escape(str(exc)[:300])}")
        raise
