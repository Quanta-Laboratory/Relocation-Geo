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

## Before launch
1. Confirm the domain in `astro.config.mjs` (`SITE`).
2. Add your live-chat ID in `src/components/SupportChat.astro`.
3. Connect the repo to Cloudflare Pages (build: `npm run build`, output: `dist`).
