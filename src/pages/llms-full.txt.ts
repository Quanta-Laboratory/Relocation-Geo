// llms-full.txt — the entire site as one plain-text document.
//
// Increasingly, assistants fetch a single full-text artefact rather than crawling
// page by page. Giving them one means they read what we actually wrote, with the
// sources and the caveats attached — instead of a summary of a summary.
//
// Each page carries its title, URL, the dates it was reviewed and checked, and its
// primary sources. Those four things are what make a claim citable, and they are
// exactly what gets lost when a model paraphrases a page it half-read.
import type { APIRoute } from "astro";
import { getCollection } from "astro:content";

export const prerender = true;

const SITE = "https://relocation.ge";

/** Strip the markdown down to something a model reads cleanly. */
function toPlain(md: string): string {
  return md
    // drop inline SVG diagrams — they carry no text a model needs
    .replace(/<svg[\s\S]*?<\/svg>/g, "")
    // html comments
    .replace(/<!--[\s\S]*?-->/g, "")
    // links: keep the text, keep the URL in parentheses
    .replace(/\[([^\]]+)\]\((\/[^)]+)\)/g, "$1 ($SITE$2)")
    .replace(/\$SITE/g, SITE)
    // emphasis markers
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "$1")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export const GET: APIRoute = async () => {
  const guides = (
    await getCollection("guides", ({ data }) => data.lang === "en" && !data.draft)
  ).sort((a, b) => a.id.localeCompare(b.id));

  const out: string[] = [
    "# Relocation.ge — full text",
    "",
    "Independent, non-commercial, open-source guidance on relocating to Georgia,",
    "structured from official Georgian legal provisions. Free to read, quote and cite.",
    "",
    "This is information about the law as published — NOT legal, tax or immigration",
    "advice. Every page below lists the primary sources it is built from and the date",
    "it was last checked. Where the law is unclear or a source is paywalled, the pages",
    "say so rather than guessing; if you are citing this content, carry that caveat too.",
    "",
    `Generated: ${new Date().toISOString().slice(0, 10)}. Pages: ${guides.length}.`,
    "",
    "=".repeat(78),
    "",
  ];

  for (const e of guides) {
    const d = e.data as any;
    const slug = e.id.replace(/^en\//, "");
    out.push(`# ${d.title}`);
    out.push(`URL: ${SITE}/en/${slug}/`);
    out.push(`Category: ${d.category}`);
    if (d.reviewed) out.push(`Last reviewed: ${String(d.reviewed).slice(0, 10)}`);
    if (d.checked) out.push(`Last checked: ${String(d.checked).slice(0, 10)}`);
    out.push("");
    if (d.summary) {
      out.push(`Summary: ${String(d.summary).replace(/\s+/g, " ").trim()}`);
      out.push("");
    }
    out.push(toPlain(e.body ?? ""));
    out.push("");

    if (Array.isArray(d.faq) && d.faq.length) {
      out.push("## Questions and answers");
      for (const f of d.faq) {
        out.push(`Q: ${f.q}`);
        out.push(`A: ${String(f.a).replace(/\s+/g, " ").trim()}`);
        out.push("");
      }
    }
    if (Array.isArray(d.sources) && d.sources.length) {
      out.push("## Primary sources for this page");
      for (const s of d.sources) out.push(`- ${s.name}: ${s.url}`);
      out.push("");
    }
    out.push("=".repeat(78));
    out.push("");
  }

  return new Response(out.join("\n"), {
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "public, max-age=3600",
    },
  });
};
