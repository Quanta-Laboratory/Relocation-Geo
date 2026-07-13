// iCalendar feed of Georgian public holidays.
//
// Served at /georgia-public-holidays.ics so it can be SUBSCRIBED to in Google
// Calendar, Apple Calendar or Outlook — not merely downloaded once. Subscribers
// pick up future years automatically, which matters because the Easter block moves.
//
// The fourteen fixed holidays are emitted as YEARLY recurring events, so they are
// correct forever with no maintenance. The Easter block is movable, so it is
// enumerated explicitly for a rolling window of years.
import type { APIRoute } from "astro";
import { FIXED, easterBlock, LABOUR_CODE_URL } from "../data/georgia-holidays";

export const prerender = true;

const DOMAIN = "relocation.ge";
const YEARS_AHEAD = 12;

function fold(line: string): string {
  // RFC 5545: lines longer than 75 octets must be folded.
  if (line.length <= 75) return line;
  const parts: string[] = [line.slice(0, 75)];
  let rest = line.slice(75);
  while (rest.length > 74) {
    parts.push(" " + rest.slice(0, 74));
    rest = rest.slice(74);
  }
  if (rest) parts.push(" " + rest);
  return parts.join("\r\n");
}

function esc(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
}

/** All-day events use DTSTART;VALUE=DATE and a DTEND of the NEXT day. */
function ymd(iso: string): string {
  return iso.replace(/-/g, "");
}
function nextDay(iso: string): string {
  const d = new Date(iso + "T00:00:00Z");
  return new Date(d.getTime() + 86400000).toISOString().slice(0, 10).replace(/-/g, "");
}

export const GET: APIRoute = () => {
  const stamp = new Date().toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
  const thisYear = new Date().getUTCFullYear();

  const lines: string[] = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    `PRODID:-//Relocation.ge//Georgian Public Holidays//EN`,
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Georgian Public Holidays",
    "X-WR-CALDESC:Public holidays of Georgia under Article 30 of the Labour Code. Maintained by Relocation.ge — a non-commercial, source-based project.",
    "X-WR-TIMEZONE:Asia/Tbilisi",
    "REFRESH-INTERVAL;VALUE=DURATION:P30D",
    "X-PUBLISHED-TTL:P30D",
  ];

  // Fixed holidays — one recurring event each.
  for (const h of FIXED) {
    const mm = String(h.month).padStart(2, "0");
    const dd = String(h.day).padStart(2, "0");
    const start = `${thisYear}${mm}${dd}`;
    const end = nextDay(`${thisYear}-${mm}-${dd}`);
    const desc = [h.note, `Statutory basis: Labour Code, Article ${h.article}.`, LABOUR_CODE_URL]
      .filter(Boolean)
      .join(" ");
    lines.push(
      "BEGIN:VEVENT",
      `UID:fixed-${mm}${dd}@${DOMAIN}`,
      `DTSTAMP:${stamp}`,
      `DTSTART;VALUE=DATE:${start}`,
      `DTEND;VALUE=DATE:${end}`,
      "RRULE:FREQ=YEARLY",
      fold(`SUMMARY:${esc(h.name)}`),
      fold(`DESCRIPTION:${esc(desc)}`),
      "TRANSP:TRANSPARENT",
      "CATEGORIES:Public holiday",
      "END:VEVENT",
    );
  }

  // Easter block — movable, so enumerated year by year.
  for (let y = thisYear; y < thisYear + YEARS_AHEAD; y++) {
    for (const h of easterBlock(y)) {
      const desc = [
        h.note,
        "Movable feast — the Orthodox Easter date changes every year.",
        `Statutory basis: Labour Code, Article ${h.article}.`,
        LABOUR_CODE_URL,
      ]
        .filter(Boolean)
        .join(" ");
      lines.push(
        "BEGIN:VEVENT",
        `UID:easter-${h.date}@${DOMAIN}`,
        `DTSTAMP:${stamp}`,
        `DTSTART;VALUE=DATE:${ymd(h.date)}`,
        `DTEND;VALUE=DATE:${nextDay(h.date)}`,
        fold(`SUMMARY:${esc(h.name)}`),
        fold(`DESCRIPTION:${esc(desc)}`),
        "TRANSP:TRANSPARENT",
        "CATEGORIES:Public holiday",
        "END:VEVENT",
      );
    }
  }

  lines.push("END:VCALENDAR");

  return new Response(lines.join("\r\n") + "\r\n", {
    headers: {
      "content-type": "text/calendar; charset=utf-8",
      "content-disposition": 'inline; filename="georgia-public-holidays.ics"',
      "cache-control": "public, max-age=86400",
    },
  });
};
