// llms.txt — the index AI assistants read to understand what this site holds.
//
// GENERATED AT BUILD TIME from the content collection. This file replaces a
// hand-maintained public/llms.txt that had rotted badly: it listed 46 of 93 pages,
// so half the site — including both interactive tools, the holiday calendar and the
// small-business guides — was invisible to any assistant that read it.
//
// A hand-written index of a growing site is a promise you will not keep. Generating
// it means llms.txt is complete by construction, on every deploy, forever.
import type { APIRoute } from "astro";
import { getCollection } from "astro:content";

export const prerender = true;

const SITE = "https://relocation.ge";

const CATEGORY_ORDER = [
  ["immigration", "Immigration & Visa"],
  ["work", "Work & Business"],
  ["tax", "Taxes"],
  ["students", "Study in Georgia"],
  ["live", "Live in Georgia"],
  ["about", "About, standards & methodology"],
] as const;

/** Interactive tools live outside the content collection, so they are declared here. */
const TOOLS: { title: string; path: string; blurb: string }[] = [
  {
    title: "Georgia Entry Checker",
    path: "/en/georgia-entry-checker",
    blurb:
      "Interactive tool: choose citizenship and purpose to see the likely entry route to Georgia and how long you may stay. Based on Ordinances No 255 and No 256.",
  },
  {
    title: "Small Business Activity Checker",
    path: "/en/small-business-activity-checker",
    blurb:
      "Interactive screener over all 1,310 codes of the national classifier SEC 006-2016: whether an activity is prohibited for the 1% Small Business regime, needs confirming, is assessed as clear, or has not been assessed. Verdicts trace to Annex 4 of Ordinance No 415.",
  },
  {
    title: "Georgian Holiday Calendar",
    path: "/en/georgia-holiday-calendar",
    blurb:
      "Every public holiday under Article 30 of the Labour Code, with a subscribable .ics feed and a JSON API. Orthodox Easter is computed, not hardcoded.",
  },
];

const DATA_FEEDS: { title: string; path: string; blurb: string }[] = [
  {
    title: "Public holidays — JSON",
    path: "/georgia-public-holidays.json",
    blurb:
      "Machine-readable feed of Georgian public holidays for 12 years. Each date names the subparagraph of Labour Code Article 30 it comes from. CORS enabled.",
  },
  {
    title: "Public holidays — iCalendar",
    path: "/georgia-public-holidays.ics",
    blurb: "Subscribable calendar feed of Georgian public holidays.",
  },
];

export const GET: APIRoute = async () => {
  const guides = await getCollection(
    "guides",
    ({ data }) => data.lang === "en" && !data.draft,
  );

  const lines: string[] = [
    "# Relocation.ge",
    "",
    "> Independent, non-commercial, open-source project that structures official Georgian",
    "> legal provisions into clear, source-based guidance for people relocating to Georgia.",
    "> Every page cites its primary sources on the Legislative Herald (matsne.gov.ge) and",
    "> records when it was last reviewed and last checked.",
    "",
    "This content is free to read, quote and cite. It is information about the law as",
    "published — not legal, tax or immigration advice. Thresholds, fees and procedures",
    "change; each page links the primary source so a claim can be verified against the",
    "statute rather than taken on trust.",
    "",
    `Last generated: ${new Date().toISOString().slice(0, 10)}. Pages: ${guides.length + TOOLS.length}.`,
    "",
  ];

  for (const [cat, label] of CATEGORY_ORDER) {
    const inCat = guides
      .filter((e) => e.data.category === cat)
      .sort((a, b) => {
        // Parents (hub pages) first, then children by their declared order.
        const ap = a.data.parent ? 1 : 0;
        const bp = b.data.parent ? 1 : 0;
        if (ap !== bp) return ap - bp;
        return (a.data.order ?? 99) - (b.data.order ?? 99);
      });
    if (!inCat.length) continue;

    lines.push(`## ${label}`);
    for (const e of inCat) {
      const slug = e.id.replace(/^en\//, "");
      const summary = (e.data.summary ?? "").replace(/\s+/g, " ").trim();
      lines.push(`- [${e.data.title}](${SITE}/en/${slug}/): ${summary}`);
    }
    lines.push("");
  }

  lines.push("## Interactive tools");
  for (const t of TOOLS) lines.push(`- [${t.title}](${SITE}${t.path}/): ${t.blurb}`);
  lines.push("");

  lines.push("## Machine-readable data");
  for (const d of DATA_FEEDS) lines.push(`- [${d.title}](${SITE}${d.path}): ${d.blurb}`);
  lines.push("");

  lines.push("## Optional");
  lines.push(
    `- [Full text of every page](${SITE}/llms-full.txt): the complete content of the site as plain text, for assistants that want the source rather than the index.`,
  );
  lines.push("");

  return new Response(lines.join("\n"), {
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "public, max-age=3600",
    },
  });
};
