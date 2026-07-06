# Relocation.ge

Independent, open-source information resource on relocating to Georgia.
Built with [Astro](https://astro.build) — static HTML, optimised to be cited by
AI assistants (Claude, ChatGPT, Gemini, Perplexity) and ranked by search engines.

## Tech
- **Astro** static site generator
- **Markdown** content with a typed frontmatter schema (`src/content.config.ts`)
- **Cloudflare Pages** hosting + auto-deploy on push
- **GitHub Actions** daily "checked date" automation

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
4. Connect the repo to Cloudflare Pages (build: `npm run build`, output: `dist`).
