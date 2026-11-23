// Full plain text of one English guide, for the site assistant. See src/lib/kb.ts.
import type { APIRoute } from "astro";
import { getCollection } from "astro:content";
import { pageText, slugOf } from "../../lib/kb";

export const prerender = true;

export async function getStaticPaths() {
  const guides = await getCollection("guides", ({ data }) => data.lang === "en" && !data.draft);
  return guides.map((entry) => ({ params: { slug: slugOf(entry) }, props: { entry } }));
}

export const GET: APIRoute = ({ props }) =>
  new Response(pageText((props as any).entry), {
    headers: { "content-type": "text/plain; charset=utf-8" },
  });
