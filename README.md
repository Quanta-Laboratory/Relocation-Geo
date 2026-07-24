# Relocation.ge

Independent, open-source information resource on relocating to Georgia.
Built with [Astro](https://astro.build) — static HTML, optimised to be cited by
AI assistants (Claude, ChatGPT, Gemini, Perplexity) and ranked by search engines.

The **software** in this repository is open-source under the **AGPL-3.0** licence.
The **content** (guide text, datasets and the classification/taxonomy work) is **not**
covered by that licence — see [Licensing](#licensing) below.

## Tech
- **Astro** static site generator
- **Markdown** content with a typed frontmatter schema (`src/content.config.ts`)
- **Cloudflare Workers** (Static Assets) hosting — deploy manually with `npx wrangler deploy` (config in `wrangler.jsonc`, worker entry `worker/index.ts`). There is **no** auto-deploy on push.
- **GitHub Actions** daily "checked date" automation and law monitors (deploy is **not** part of CI)

## Develop locally
```bash
npm install
npm run dev      # http://localhost:4321
npm run build    # output in dist/
npm run preview  # preview the production build
```

## Content
Pages live in `src/content/guides/<lang>/<slug>.md`. Each file needs:

```yaml
---
title: "..."
category: "immigration"   # immigration | work | live | about
lang: "en"
summary: "Answer-first description (used for SEO + AI extraction)."
reviewed: 2026-06-12      # change ONLY on a real content review
checked: 2026-06-22       # auto-updated daily by GitHub Actions
sources:
  - name: "..."
    url: "https://..."
faq:
  - q: "..."
    a: "..."
order: 1
---
```

Add a new page = add a Markdown file. It appears automatically under its hub.

## Two-date system
- **reviewed** — last real human/editor review (trust signal).
- **checked** — bumped daily by `.github/workflows/daily-checked.yml`.

## GEO / SEO built in
- schema.org JSON-LD (Organization, WebSite, Article, BreadcrumbList, FAQPage)
- `sitemap-index.xml`, `robots.txt` (AI crawlers allowed), `llms.txt`
- canonical + hreflang, semantic HTML, fast static output

## Analytics (marketing stack)
Tag management is done through **Google Tag Manager (GTM)**, loaded with **Google
Consent Mode v2** and a GDPR cookie-consent banner (deny-by-default until accepted).

Inside GTM you then add, with no code changes:
- **GA4** — traffic, campaigns/UTM, conversions, funnels, audiences (incl. AI referrals).
- **Microsoft Clarity** — heatmaps and session recordings.

**Google Search Console** is set up separately (domain verification, no on-page script).

To enable analytics, set one environment variable in Cloudflare Pages:
```
PUBLIC_GTM_ID = GTM-XXXXXXX
```
If it is unset, no tags load and no banner shows — the site still works.

Implementation: `src/components/Analytics.astro` (GTM + consent mode) and
`src/components/ConsentBanner.astro` (cookie banner).

## Support widget
Floating "Support" button (`src/components/SupportChat.astro`) with Telegram and
WhatsApp links, plus an optional **Chatwoot live chat** that lazy-loads only on
click. Enable chat by setting two env vars in Cloudflare Pages:
```
PUBLIC_CHATWOOT_BASE_URL = https://app.chatwoot.com   # or your self-hosted URL
PUBLIC_CHATWOOT_TOKEN    = <website inbox token>
```
Create one Website inbox per domain in Chatwoot; each gives its own token.
If unset, the live-chat option simply doesn't appear.

## Before launch
1. Confirm the domain in `astro.config.mjs` (`SITE`).
2. Set `PUBLIC_CHATWOOT_*` env vars (per-domain website token) to enable live chat.
3. Set `PUBLIC_GTM_ID` in Cloudflare Pages and wire GA4 + Clarity inside GTM.
4. Deploy to Cloudflare Workers: `npm run build` then `npx wrangler deploy`
   (the worker serves `dist/` as static assets and handles `/api/match`).
   Set the `ANTHROPIC_API_KEY` secret once with `npx wrangler secret put ANTHROPIC_API_KEY`
   (used by `/api/match`; without it the checker falls back to keyword search).

## Licensing

This project is split into two licences.

**Software — AGPL-3.0.** All code (the Astro site, the Cloudflare Worker, build
scripts and monitoring scripts) is licensed under the GNU Affero General Public
License v3.0 — see [`LICENSE`](LICENSE). In short: you may use, study, modify and
redistribute it, but if you run a modified version as a network service you must
make your modified source available to its users. Because this is a web
application, AGPL section 13 applies — a public deployment must offer users a way
to obtain the source.

**Content — separate terms, not AGPL.** The guide text, FAQs, datasets and the
activity classification / taxonomy work in `src/content/` and `src/data/` are
**not** open-source. They remain © Relocation.ge and are governed by the
[Use of Materials](https://relocation.ge/en/use-of-materials) terms: personal,
non-commercial, academic and research use with attribution is permitted;
scraping, bulk extraction, training commercial AI models, and reuse of the
datasets or taxonomy to build competing services are not. Commercial content use
requires a separate agreement.

**Contributions.** By opening a pull request you agree that your code
contribution is licensed under AGPL-3.0. For content contributions, note the
separate terms above.

When re-using this repository, keep the software and the content licences
distinct: forking the code is fine under AGPL; copying the guides or datasets is
governed by the content terms.
