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
| `relevance.py` | **Relevance filter.** Scores every new matsne/parliament document 0–3 against the live catalogue of site pages (`/kb/index.json`); only score ≥ 2 (`ALERT_MIN_SCORE`) is pushed to Telegram, with the site pages to check or a ✍️ "not covered yet" flag. New site pages widen the filter automatically and are announced. Backtest: Run workflow → `relevance_backtest: 40`. |
| `topics_state.json` | Last known catalogue of site topics (for change announcements and offline fallback). |
| `watchlist.py` | Priority alerts (🚨) for acts that feed site datasets — e.g. the NBG high-risk jurisdictions list behind `/nbg-high-risk-jurisdictions.json` (used by mono.ge). Matches new feed items by title **and** sweeps matsne search each run, so a change is caught even if it scrolled out of the RSS window. Add a watch = add an entry to `WATCHES`. |
| `watchlist_state.json` | Document ids already known per watch. Committed back by the workflow. |
| `digest.py` | Sends one daily summary of the documents detected since the previous digest. |
| `digest_state.json` | Digest watermark (newest log entry already digested). Committed back by the digest workflow. |
| `state.json` | Saved state (which documents have been seen). Committed back by the workflow. Created automatically. |
| `changes_log.md` | Human-readable history of every detected document, EN + KA. Committed back by the workflow. Created automatically. |
| `../../.github/workflows/monitor.yml` | Runs `monitor.py` twice a day. |
| `../../.github/workflows/digest.yml` | Runs `digest.py` once a day (evening summary). |

## Schedule

Cron is always UTC:

- Monitor: `08:00 UTC` → 12:00 Tbilisi, and `16:00 UTC` → 20:00 Tbilisi — checks matsne and sends a notification per new document.
- Digest: `17:00 UTC` → 21:00 Tbilisi — one message summarising the documents detected **since the previous digest** (watermark in `digest_state.json`), so a late cron start never drops or repeats documents. Manual runs (`mode=manual`) use a rolling `digest_days × 24 h` window and leave the watermark alone. Reads `changes_log.md` (no extra translation). Sends "No new documents today" on empty days; set the workflow env `SEND_IF_EMPTY: '0'` to stay silent instead.

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

## Parliament monitor (advance signals)

matsne sees a law only once it is **published**. This watcher looks **upstream**
at the Parliament of Georgia news stream (parliament.ge), where bills are
reported as they pass committee and the three readings — weeks to months before
they reach matsne — so you can prepare and publish "upcoming change"
announcements early.

| File | Purpose |
| --- | --- |
| `parliament_monitor.py` | Fetches parliament.ge news (server-rendered HTML — no RSS/API), keeps only legislative items (draft law / reading / migration / visa / residence permit / citizenship, etc.), and on a new one appends to the log and sends a Telegram alert. |
| `parliament_state.json` | Seen article slugs. Committed back by the workflow. |
| `parliament_log.md` | History of detected legislative items. Committed back. |
| `../../.github/workflows/parliament.yml` | Runs daily (07:00 UTC = 11:00 Tbilisi). |

```bash
python scripts/matsne_monitor/parliament_monitor.py            # probe + alert
python scripts/matsne_monitor/parliament_monitor.py --selftest  # offline parser test
```

Notes:
- This is an **advance signal, not the final text** — a bill can change between
  readings or fail. Announcements built from it must say "in progress, not yet
  in force" (use the site's `notice:` front-matter block, as on the students page).
- parliament.ge sits behind Cloudflare. If a CI run reports it could not fetch
  the page, the server may be challenging the runner; the script fails safe
  (logs a warning, leaves state unchanged) rather than inventing data.
- The main news feed already surfaces bill items; add committee feeds to `FEEDS`
  in the script for finer coverage.

## Impact analysis → one-tap page updates (`impact.py`)

Turns "a new act was published" into "here is the exact edit to our page — apply?".

1. `monitor.py` scores each new document with `relevance.py` (0–3, alert at ≥2) and hands the run's documents with their verdict to `impact.py` (`.new_docs.json`, not committed).
2. Documents scored **3** (changes what a page states) with named pages go straight to the proposal step — no second classification. Threshold: `IMPACT_MIN_SCORE` (default 3).
3. Fallback for documents without a verdict (manual runs): regex pre-filter, then one Claude call against the catalogue of `src/content/guides/en/*`.
4. **Propose**: reads the act's full text from matsne (amending acts are public) and the affected English pages; Claude returns exact find/replace edits. Each `find` must occur exactly once or the edit is dropped and listed for manual review.
5. **Localise**: the same change is carried into every existing translation (`de/fr/he/ka/ru/uk/<slug>.md`), verified the same way.
6. **PR** on branch `matsne/<doc_id>` + **Telegram** message with before/after and buttons **✅ Применить / ❌ Отклонить**.
7. The buttons hit `POST /api/telegram` on the site Worker (`worker/telegram.ts`), which squash-merges or closes the PR. Merge → push to main → `deploy.yml` → live.

Acts that look relevant but can't be expressed as safe edits arrive as ℹ️ messages without buttons. Everything is logged to `impact_log.md`.

Manual run / test: **Actions → Matsne Impact (manual)** with one or more document ids (tick *dry_run* to only see the proposal in the log).

### One-time setup

| Where | What |
| --- | --- |
| GitHub → Settings → Secrets → Actions | `ANTHROPIC_API_KEY` (also fixes title translation). Optional `GH_CONTENT_TOKEN`, `TELEGRAM_ADMIN_IDS`. |
| GitHub → Settings → Actions → General → Workflow permissions | Tick **Allow GitHub Actions to create and approve pull requests**. |
| Fine-grained PAT used by the Worker | `GH_CONTENT_TOKEN`, or add to the existing `GH_DISPATCH_TOKEN`: **Contents: Read and write**, **Pull requests: Read and write**. |
| After this is deployed | Run **Actions → Sync Worker secrets** once: copies Telegram secrets into the Worker and registers the webhook `https://relocation.ge/api/telegram` with a fresh secret. |

Self-test (offline): `python scripts/matsne_monitor/impact.py --selftest`
