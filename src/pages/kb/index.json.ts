// Compact catalogue of English guides for the site assistant. See src/lib/kb.ts.
import type { APIRoute } from "astro";
import { getCollection } from "astro:content";
import { slugOf } from "../../lib/kb";

export const prerender = true;

const clip = (s: string, n: number) => {
  const t = s.replace(/\s+/g, " ").trim();
  return t.length <= n ? t : t.slice(0, t.lastIndexOf(" ", n)) + "…";
};

export const GET: APIRoute = async () => {
  const guides = (
    await getCollection("guides", ({ data }) => data.lang === "en" && !data.draft)
  ).sort((a, b) => a.id.localeCompare(b.id));
  const ru = new Set(
    (await getCollection("guides", ({ data }) => data.lang === "ru" && !data.draft)).map((e) =>
      e.id.replace(/^ru\//, ""),
    ),
  );
  const pages = guides.map((e) => {
    const d = e.data as any;
    const slug = slugOf(e);
    return {
      slug,
      title: d.title,
      category: d.category,
      summary: clip(String(d.summary ?? ""), 320),
      ru: ru.has(slug),
    };
  });
  return new Response(JSON.stringify({ generated: new Date().toISOString().slice(0, 10), pages }), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
};
