"""Resend all 'outdated' audit findings to Telegram (no Claude calls)."""
from __future__ import annotations
import html, json, sys, time
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).parent))
from lib import SITE, start_url, telegram

state = json.loads((Path(__file__).parent / "audits/state.json").read_text(encoding="utf-8"))
titles = {p["slug"]: p["title"] for p in requests.get(f"{SITE}/kb/index.json", timeout=30).json()["pages"]}
outdated = [(s, f) for s, fs in state.get("findings", {}).items() for f in fs if f.get("status") == "outdated"]
telegram(f"🔁 <b>Предлагаемые правки по аудиту</b>: {len(outdated)}")
for slug, f in outdated:
    telegram(f"🔴 <b>{html.escape(titles.get(slug, slug))}</b>\n{SITE}/en/{slug}/\n\n"
             f"📄 {html.escape(f.get('title_en', '')[:250])} ({html.escape(f.get('published') or '')})\n"
             f"⚠️ {html.escape(f.get('what_ru', ''))}",
             [[{"text": "✍️ Подготовить правку", "url": start_url(f["id"], [slug])}]])
    time.sleep(1)
