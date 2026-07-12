/**
 * Cloudflare Worker for relocation.ge
 *
 * Serves the static site, plus ONE dynamic endpoint: POST /api/match.
 *
 * THE ONE RULE THIS FILE EXISTS TO ENFORCE
 * ----------------------------------------
 * The model is allowed to do RETRIEVAL and nothing else. It maps a free-text
 * description of what someone does onto one of the activity codes WE already hold
 * in src/data/small-business-activity-data.ts. It never decides whether an
 * activity is prohibited, never states the law, and never explains the tax
 * consequences. Those come from the dataset, rendered on the client.
 *
 * Enforcement is not a matter of trusting the prompt:
 *   - the response is parsed as JSON and every returned code is checked against
 *     our own code set; anything unrecognised is dropped;
 *   - if nothing survives, we return noMatch and the user is sent to the
 *     deterministic list;
 *   - the model is given ONLY code + name, never our verdicts, so it cannot
 *     parrot a legal conclusion back at us.
 *
 * Privacy: the request body describes what a person does for a living. It is not
 * logged, not stored, and not sent anywhere except the Anthropic API.
 */
import { activities } from "../src/data/small-business-activity-data";

export interface Env {
  ASSETS: Fetcher;
  ANTHROPIC_API_KEY?: string;
}

const MODEL = "claude-haiku-4-5-20251001";
const MAX_QUERY = 400;
const CACHE_TTL = 60 * 60 * 24 * 30; // 30 days — the query space is small and repetitive

/** The catalogue the model is allowed to choose from. Code + name only — no verdicts. */
const CATALOGUE = activities
  .map((a) => `${a.code} ${a.name}`)
  .join("\n");

const VALID_CODES = new Set(activities.map((a) => a.code));

const SYSTEM = `You map a person's description of their work onto activity codes from a fixed catalogue.

CATALOGUE (the ONLY codes you may return):
${CATALOGUE}

Your job is retrieval, not judgement. You must NOT say whether an activity is allowed, prohibited, taxed, or eligible for any regime. You do not know the tax rules and must not speculate about them. Someone else decides that.

Return STRICT JSON, no prose, no markdown fence:
{
  "matches": [{"code": "62.01", "confidence": "high"|"medium"|"low", "why": "one short sentence, plain English, describing why this code fits what they said"}],
  "clarifyingQuestion": "optional — ask ONLY if the description is genuinely ambiguous between codes",
  "noMatch": false
}

Rules:
- Return at most 3 matches, best first. Only codes copied exactly from the catalogue.
- If the description is too vague or matches nothing, return {"matches": [], "noMatch": true} and, if useful, a clarifyingQuestion.
- Prefer a clarifyingQuestion over a low-confidence guess when the answer would change the code.
- One distinction matters more than any other: whether the person ADVISES (recommends, strategises, counsels) or EXECUTES (builds, designs, writes, delivers). These map to different codes. If the description does not make that clear and it would change the code, ASK.
- "why" describes the fit with their words. It must not mention tax, eligibility, permission, or law.`;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

async function hash(s: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

interface Match {
  code: string;
  confidence: string;
  why: string;
}

/** Keep only codes we actually hold. The model does not get to invent one. */
function sanitise(raw: unknown): { matches: Match[]; clarifyingQuestion?: string; noMatch: boolean } {
  const out: Match[] = [];
  const obj = (raw ?? {}) as Record<string, unknown>;
  const list = Array.isArray(obj.matches) ? obj.matches : [];

  for (const m of list.slice(0, 3)) {
    const item = (m ?? {}) as Record<string, unknown>;
    const code = String(item.code ?? "").trim();
    if (!VALID_CODES.has(code)) continue; // <- the guardrail
    const confidence = ["high", "medium", "low"].includes(String(item.confidence))
      ? String(item.confidence)
      : "low";
    const why = String(item.why ?? "").slice(0, 240);
    out.push({ code, confidence, why });
  }

  const q = typeof obj.clarifyingQuestion === "string" ? obj.clarifyingQuestion.slice(0, 240) : undefined;
  return { matches: out, clarifyingQuestion: q || undefined, noMatch: out.length === 0 };
}

async function handleMatch(request: Request, env: Env): Promise<Response> {
  if (request.method !== "POST") return json({ error: "method_not_allowed" }, 405);
  if (!env.ANTHROPIC_API_KEY) return json({ error: "unavailable" }, 503);

  let query = "";
  try {
    const body = (await request.json()) as { query?: unknown };
    query = String(body.query ?? "").trim().slice(0, MAX_QUERY);
  } catch {
    return json({ error: "bad_request" }, 400);
  }
  if (query.length < 3) return json({ error: "too_short" }, 400);

  // Cache on a normalised hash of the query. Cheap, and the query space repeats.
  const key = `https://cache.internal/match/${await hash(query.toLowerCase())}`;
  const cache = caches.default;
  const hit = await cache.match(new Request(key));
  if (hit) return hit;

  let upstream: Response;
  try {
    upstream = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 700,
        system: SYSTEM,
        messages: [{ role: "user", content: query }],
      }),
    });
  } catch {
    return json({ error: "upstream_unreachable" }, 502);
  }
  if (!upstream.ok) return json({ error: "upstream_error" }, 502);

  let parsed: unknown = null;
  try {
    const data = (await upstream.json()) as { content?: { type: string; text?: string }[] };
    const text = (data.content ?? [])
      .filter((b) => b.type === "text")
      .map((b) => b.text ?? "")
      .join("")
      .trim()
      .replace(/^```(?:json)?\s*/i, "")
      .replace(/\s*```$/, "");
    parsed = JSON.parse(text);
  } catch {
    return json({ matches: [], noMatch: true, error: "unparsable" });
  }

  const result = sanitise(parsed);
  const response = json(result);

  // Store a cacheable copy (the live response keeps no-store for the client).
  const cacheable = new Response(JSON.stringify(result), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": `public, max-age=${CACHE_TTL}`,
    },
  });
  await cache.put(new Request(key), cacheable);

  return response;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/api/match") return handleMatch(request, env);
    return env.ASSETS.fetch(request);
  },
};
