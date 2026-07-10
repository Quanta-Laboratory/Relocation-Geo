# Matsne Monitor

Watches [matsne.gov.ge](https://www.matsne.gov.ge/en) (the Legislative Herald of
Georgia) for newly published legal documents, translates each new document's
title and topic into English with the Claude API, and sends a Telegram
notification. Every change is also appended to a history log that keeps the
Georgian original.

## Files

| File | Purpose |
| --- | --- |
| `monitor.py` | The script that checks matsne and notifies on each new document. |
| `digest.py` | Sends one daily summary of the documents detected today. |
| `state.json` | Saved state (which documents have been seen). Committed back by the workflow. Created automatically. |
| `changes_log.md` | Human-readable history of every detected document, EN + KA. Committed back by the workflow. Created automatically. |
| `../../.github/workflows/monitor.yml` | Runs `monitor.py` twice a day. |
| `../../.github/workflows/digest.yml` | Runs `digest.py` once a day (evening summary). |

## Schedule

Cron is always UTC:

- Monitor: `08:00 UTC` → 12:00 Tbilisi, and `16:00 UTC` → 20:00 Tbilisi — checks matsne and sends a notification per new document.
- Digest: `17:00 UTC` → 21:00 Tbilisi — one message summarising the documents detected today. Reads `changes_log.md` (no extra translation). Sends "No new documents today" on empty days; set the workflow env `SEND_IF_EMPTY: '0'` to stay silent instead.

You can also trigger either from the **Actions** tab (**Run workflow**).

## Secrets

Add these under **Settings → Secrets and variables → Actions**:

| Secret | Required? | Notes |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Optional | Claude API key for translation. If missing, notifications/log use the Georgian original with a note. |
| `TELEGRAM_BOT_TOKEN` | Optional | Already used by the analytics workflow — reuse the same secret. If missing, the run still updates the log, just no push. |
| `TELEGRAM_CHAT_ID` | Optional | Same as above. |

The script never prints secret values; it reads them from environment variables only.

## First run

The first successful run records a **baseline** of the current documents and
sends **no** notifications, so you are not flooded on day one. From the second
run onward, only genuinely new documents trigger a Telegram message and a log
entry.

## How it works

1. Downloads matsne's RSS feed of published documents
   (`https://www.matsne.gov.ge/en/document/feed`).
2. Parses each `<item>` into a document id, title, topic, link and publish date.
3. Compares document ids against `state.json`.
4. For each new document: translates title + topic via Claude (one at a time,
   with a short pause), appends to `changes_log.md`, and sends a Telegram
   message.
5. Saves the updated `state.json`. The workflow commits `state.json` and
   `changes_log.md` back to the repo with `[skip ci]`.

## If it stops finding documents

matsne may change its site over time. Everything site-specific lives in two
places in `monitor.py`:

- `FEED_URL` — the feed address.
- `parse_feed()` / `fetch_feed()` — how items are read from the feed.

If a run logs *"no documents parsed from the feed"*, adjust those and re-run.

## Run locally

```bash
pip install requests
export ANTHROPIC_API_KEY=...      # optional
export TELEGRAM_BOT_TOKEN=...     # optional
export TELEGRAM_CHAT_ID=...       # optional
python scripts/matsne_monitor/monitor.py
```

Without any secrets it still runs: it parses the feed, writes the baseline (or
logs new documents using the Georgian original), and skips the Telegram push.

## Redaction check (staleness probe)

Separate from the feed monitor, this watches the **specific laws the site cites**
(not the whole feed) and flags when one has been amended since a page last
reflected it. Detection is free: matsne's public document page lists every
consolidated-publication date even though the amended *text* is paywalled.

| File | Purpose |
| --- | --- |
| `source_index.py` | Scans `src/` and builds `source_index.json` — a reverse index mapping each matsne document id to the pages that cite it, with their `reviewed`/`checked` dates. Pure local, no network. |
| `source_index.json` | The generated impact map (regenerated on each run). |
| `redaction_check.py` | Fetches each tracked document's public page, extracts the latest consolidated-redaction date, and reports (1) laws amended after a citing page was last `checked`, (2) laws with a NEW redaction since the last probe (→ Telegram). |
| `redaction_state.json` | Last-seen latest redaction per document. Committed back by the workflow. |
| `staleness_report.md` | Human-readable report from the latest run. Committed back. |
| `../../.github/workflows/redaction.yml` | Runs the two scripts weekly (Mon 09:00 UTC = 13:00 Tbilisi). |

Run locally (stdlib only, no pip needed):

```bash
python scripts/matsne_monitor/source_index.py       # rebuild the index
python scripts/matsne_monitor/redaction_check.py     # probe + report
python scripts/matsne_monitor/redaction_check.py --selftest   # offline parser test
```

The probe only reads free public pages. Reading the amended consolidated *text*
(to analyse exactly what changed) still requires a paid matsne account — that is
a later, separate module.
