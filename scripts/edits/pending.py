"""
Pending content updates — legal acts flagged 🔴 (score 3) for specific guides
that nobody has resolved yet (publish / reject / "no change needed").

While a slug is pending:
  - scripts/update-checked-date.mjs does NOT bump its `checked:` date;
  - ArticleLayout shows an "update in progress" banner linking the act.

File: src/data/pending-updates.json  {"items": {"<doc_id>": {...}}}
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "src/data/pending-updates.json"
REL = "src/data/pending-updates.json"


def load() -> dict:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"items": {}}


def save(data: dict) -> None:
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add(doc_id: str, slugs: list[str], title_en: str, link: str) -> bool:
    data = load()
    if doc_id in data["items"] or not slugs:
        return False
    data["items"][doc_id] = {"slugs": slugs, "title_en": title_en[:300], "link": link,
                             "since": dt.date.today().isoformat()}
    save(data)
    return True


def remove(doc_id: str) -> bool:
    data = load()
    if data["items"].pop(doc_id, None) is None:
        return False
    save(data)
    return True


def commit_to_main(message: str) -> bool:
    """Commit the pending file on main and push (with a rebase retry). Caller
    must be on a checkout of main."""
    def run(*c, check=True):
        return subprocess.run(c, cwd=ROOT, check=check, text=True, capture_output=True)
    run("git", "config", "user.name", "relocation-bot")
    run("git", "config", "user.email", "bot@users.noreply.github.com")
    run("git", "add", REL)
    if run("git", "diff", "--cached", "--quiet", check=False).returncode == 0:
        return False
    run("git", "commit", "-m", message)
    for _ in range(3):
        if run("git", "push", "origin", "HEAD:main", check=False).returncode == 0:
            return True
        run("git", "pull", "--rebase", "origin", "main", check=False)
    raise RuntimeError("could not push pending-updates.json to main")


def deploy() -> None:
    subprocess.run(["gh", "workflow", "run", "deploy.yml", "--ref", "main"], cwd=ROOT, check=False)
