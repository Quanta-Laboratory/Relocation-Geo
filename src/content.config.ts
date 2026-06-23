import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// Content collection for all guide/article pages.
// Files live in src/content/guides/<lang>/<slug>.md
const guides = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/guides' }),
  schema: z.object({
    title: z.string(),
    // Top-level hub the page belongs to
    category: z.enum(['immigration', 'work', 'live', 'about']),
    lang: z.string().default('en'),
    // Answer-first summary used for meta description + AI extraction
    summary: z.string(),
    // "Last reviewed" — changes ONLY on a real content review (trust signal)
    reviewed: z.coerce.date(),
    // "Last checked" — bumped automatically every day by GitHub Actions
    checked: z.coerce.date(),
    // Primary sources, rendered as citations
    sources: z
      .array(z.object({ name: z.string(), url: z.string().url() }))
      .default([]),
    // Optional FAQ block -> rendered + emitted as FAQPage schema.org
    faq: z
      .array(z.object({ q: z.string(), a: z.string() }))
      .default([]),
    // Ordering within a hub
    order: z.number().default(99),
    // Hide from navigation if needed
    draft: z.boolean().default(false),
  }),
});

export const collections = { guides };
