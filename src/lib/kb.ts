// Knowledge base for the site assistant (worker/assistant.ts).
//
// The assistant may only answer from what this site publishes. At build time we
// emit, from the same content collection the pages are rendered from:
//   /kb/index.json      — compact catalogue (slug, title, category, summary)
//   /kb/<slug>.txt      — the full plain text of one English guide
// The Worker reads both from its own static assets, so the knowledge base can
// never drift from the published pages.
import type { CollectionEntry } from "astro:content";

export const SITE = "https://relocation.ge";

export function toPlain(md: string): string {
  return md
    .replace(/<svg[\s\S]*?<\/svg>/g, "")
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\[([^\]]+)\]\((\/[^)]+)\)/g, `$1 (${SITE}$2)`)
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "$1")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export const isoDate = (v: unknown) =>
  v instanceof Date ? v.toISOString().slice(0, 10) : String(v ?? "").slice(0, 10);

export const slugOf = (e: CollectionEntry<"guides">) => e.id.replace(/^en\//, "");

export function pageText(e: CollectionEntry<"guides">): string {
  const d = e.data as any;
  const out: string[] = [
    `# ${d.title}`,
    `URL: ${SITE}/en/${slugOf(e)}/`,
  ];
  if (d.reviewed) out.push(`Last reviewed: ${isoDate(d.reviewed)}`);
  if (d.checked) out.push(`Last checked: ${isoDate(d.checked)}`);
  if (d.notice) out.push(`Notice: ${toPlain(String(d.notice))}`);
  out.push("");
  if (d.summary) out.push(`Summary: ${String(d.summary).replace(/\s+/g, " ").trim()}`, "");
  out.push(toPlain(e.body ?? ""), "");
  if (Array.isArray(d.faq) && d.faq.length) {
    out.push("## Questions and answers");
    for (const f of d.faq) out.push(`Q: ${f.q}`, `A: ${String(f.a).replace(/\s+/g, " ").trim()}`, "");
  }
  if (Array.isArray(d.sources) && d.sources.length) {
    out.push("## Primary sources");
    for (const s of d.sources) out.push(`- ${s.name}: ${s.url}`);
  }
  return out.join("\n");
}
