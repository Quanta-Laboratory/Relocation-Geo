"""
Shared helpers for the article-edit flow (Telegram → draft → review → publish).

Flow
  1. monitor.py alert (score >= 2) carries a "✍️ Prepare edit" URL button,
     signed with sign("start", doc_id, slugs).
  2. worker/edits.ts verifies it and dispatches draft-edit.yml.
  3. draft.py asks Claude for minimal edits to the affected guides (EN + RU),
     commits them to branch edit/doc-<id> (no PR), uploads a Cloudflare
     preview version, writes .edits/proposal.json on the branch and sends a
     Telegram message with Review / Full page / Publish / Reject buttons.
  4. The review page (worker /edits/<doc>) reads proposal.json from the branch
     at an exact commit (raw.githubusercontent.com), shows a before/after diff,
     lets you edit the new text, publish or reject → apply-edit.yml.

Signing: HMAC-SHA256 with a key derived from ANTHROPIC_API_KEY, which both
GitHub Actions and the Worker already hold (kept in sync by
sync-worker-secrets.yml). No extra secret to manage. Links expire after 14 days.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import time

import requests

REPO = "Quanta-Laboratory/Relocation-Geo"
SITE = "https://relocation.ge"
LINK_TTL = 14 * 24 * 3600
MODEL = "claude-sonnet-4-6"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


# --------------------------------------------------------------------------- #
# Signed links (must match worker/edits.ts)
# --------------------------------------------------------------------------- #

def _key() -> bytes:
    return hashlib.sha256(f"relocation-edits:v1:{ANTHROPIC_API_KEY}".encode()).digest()


def sign(*parts: str, exp: int | None = None) -> tuple[int, str]:
    exp = exp or int(time.time()) + LINK_TTL
    msg = ":".join([*map(str, parts), str(exp)])
    return exp, hmac.new(_key(), msg.encode(), hashlib.sha256).hexdigest()[:40]


def start_url(doc_id: str, slugs: list[str], source: str = "matsne") -> str:
    s = ",".join(slugs)
    exp, sig = sign("start", source, doc_id, s)
    return (f"{SITE}/api/edits/start?src={source}&doc={doc_id}&slugs={s}"
            f"&exp={exp}&sig={sig}")


def review_url(doc: str, sha: str) -> str:
    exp, sig = sign("view", doc, sha)
    return f"{SITE}/edits/{doc}?ref={sha}&exp={exp}&sig={sig}"


def action_url(action: str, doc: str, sha: str) -> str:
    exp, sig = sign(action, doc, sha)
    return f"{SITE}/edits/{doc}?ref={sha}&do={action}&exp={exp}&sig={sig}"


# --------------------------------------------------------------------------- #
# Telegram
# --------------------------------------------------------------------------- #

def telegram(text: str, buttons: list[list[dict]] | None = None) -> bool:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("Telegram not configured; message:\n" + text)
        return False
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text[:4000], "parse_mode": "HTML",
               "disable_web_page_preview": True}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    try:
        r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                          json=payload, timeout=30)
        r.raise_for_status()
        return True
    except requests.RequestException as exc:
        print(f"WARN: Telegram send failed: {exc}")
        return False


# --------------------------------------------------------------------------- #
# Claude
# --------------------------------------------------------------------------- #

def claude(system: str, user: str, max_tokens: int = 8000) -> str:
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": max_tokens, "system": system,
              "messages": [{"role": "user", "content": user}]},
        timeout=300,
    )
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")


def extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


# --------------------------------------------------------------------------- #
# Shell / git / gh
# --------------------------------------------------------------------------- #

def sh(*cmd: str, check: bool = True, capture: bool = True) -> str:
    print("+ " + " ".join(cmd))
    p = subprocess.run(cmd, check=False, text=True, capture_output=capture)
    if capture and p.stdout:
        print(p.stdout[-3000:])
    if capture and p.stderr:
        print(p.stderr[-3000:])
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(cmd)}")
    return (p.stdout or "") + (p.stderr or "")


def preview_upload(alias: str) -> str:
    """Build the site and upload a non-production Worker version with a preview
    alias. Returns the preview URL or '' if unavailable."""
    try:
        sh("npm", "ci", "--no-audit", "--no-fund")
        sh("npm", "run", "build")
        out = sh("npx", "--yes", "wrangler@4.114.0", "versions", "upload",
                 "--preview-alias", alias, "--message", f"edit preview {alias}")
    except RuntimeError as exc:
        print(f"WARN: preview upload failed: {exc}")
        return ""
    for line in out.splitlines():
        if "Preview Alias URL" in line or ("https://" in line and alias in line):
            url = line[line.find("https://"):].strip()
            return url.split()[0]
    return ""
