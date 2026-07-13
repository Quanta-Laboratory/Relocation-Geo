// Machine-readable feed of Georgian public holidays.
//
// Served at /georgia-public-holidays.json so that developers, AI assistants and
// anyone building a tool can consume the dates directly rather than scraping a
// page — and so that whoever cites us can point at a stable, dated artefact.
//
// Every entry names the subparagraph of Article 30 it comes from. That is the
// whole point: the dates are checkable against the statute, not taken on trust.
import type { APIRoute } from "astro";
import { holidaysFor, calendarYears, weekdayOf, LABOUR_CODE_URL, dataAsOf } from "../data/georgia-holidays";

export const prerender = true;

export const GET: APIRoute = () => {
  const years = calendarYears(new Date().getUTCFullYear(), 12);

  const payload = {
    country: "Georgia",
    countryCode: "GE",
    source: {
      law: "Organic Law of Georgia — Labour Code of Georgia, Article 30 (Holidays)",
      url: LABOUR_CODE_URL,
      note:
        "Fourteen holidays fall on fixed dates. The four-day Easter block is a movable feast on the Orthodox calendar and is computed, not hardcoded.",
    },
    publisher: {
      name: "Relocation.ge",
      url: "https://relocation.ge/en/public-holidays-in-georgia",
      nonCommercial: true,
    },
    dataAsOf,
    generatedAt: new Date().toISOString().slice(0, 10),
    disclaimer:
      "Information about the law as published, not legal advice. The Government may declare additional days off by ordinance during the year (Article 30(3)); those are not included here.",
    years: years.map((year) => ({
      year,
      count: holidaysFor(year).length,
      holidays: holidaysFor(year).map((h) => ({
        date: h.date,
        weekday: weekdayOf(h.date),
        name: h.name,
        nameKa: h.nameKa ?? null,
        movable: h.movable,
        article: `Article ${h.article}`,
        note: h.note ?? null,
      })),
    })),
  };

  return new Response(JSON.stringify(payload, null, 2), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "access-control-allow-origin": "*",
      "cache-control": "public, max-age=86400",
    },
  });
};
