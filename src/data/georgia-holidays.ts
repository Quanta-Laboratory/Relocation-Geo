// Georgian public holidays — the canonical, machine-readable source for the site.
//
// Statutory basis: Article 30 of the Organic Law of Georgia — Labour Code.
// https://matsne.gov.ge/en/document/view/1155567
//
// Fourteen holidays fall on fixed dates. The Easter block — Good Friday, Holy
// Saturday, Easter Sunday and Easter Monday — is a MOVABLE feast on the Orthodox
// calendar, so it is COMPUTED, never hardcoded. Hardcoding it would mean the page
// silently rots the moment the year turns.

export const LABOUR_CODE_URL = "https://matsne.gov.ge/en/document/view/1155567";
export const dataAsOf = "2026-07-13";

export interface Holiday {
  /** ISO date, YYYY-MM-DD */
  date: string;
  name: string;
  /** Georgian name where the holiday has a commonly used one. */
  nameKa?: string;
  /** The subparagraph of Article 30(1) this comes from. */
  article: string;
  movable: boolean;
  note?: string;
}

interface FixedHoliday {
  month: number; // 1-12
  day: number;
  name: string;
  nameKa?: string;
  article: string;
  note?: string;
}

/** Article 30(1), subparagraphs (a)–(m). Fourteen days on fixed dates. */
export const FIXED: FixedHoliday[] = [
  { month: 1, day: 1, name: "New Year's Day", nameKa: "ახალი წელი", article: "30(1)(a)" },
  { month: 1, day: 2, name: "New Year holiday (second day)", nameKa: "ახალი წელი", article: "30(1)(a)" },
  { month: 1, day: 7, name: "Christmas Day — Birth of Our Lord Jesus Christ", nameKa: "შობა", article: "30(1)(b)",
    note: "Georgia follows the Orthodox calendar, so Christmas is on 7 January, not 25 December." },
  { month: 1, day: 19, name: "Epiphany — Baptism of Our Lord Jesus Christ", nameKa: "ნათლისღება", article: "30(1)(c)" },
  { month: 3, day: 3, name: "Mother's Day", nameKa: "დედის დღე", article: "30(1)(d)" },
  { month: 3, day: 8, name: "International Women's Day", nameKa: "ქალთა საერთაშორისო დღე", article: "30(1)(e)" },
  { month: 4, day: 9, name: "Day of National Unity", article: "30(1)(f)",
    note: "The day of adopting the Act of Restoring Independence of Georgia; the day of national unity, national consent, and commemoration of those who died for the national integrity of Georgia." },
  { month: 5, day: 9, name: "Victory Day over Fascism", article: "30(1)(h)" },
  { month: 5, day: 12, name: "St Andrew the Apostle Day — Day of Hope", article: "30(1)(i)",
    note: "Day of Georgia as the abode of the Holy Mother; Commemoration Day of St Andrew the Apostle, Founder of the Apostolic Church of Georgia; Day of Hope." },
  { month: 5, day: 17, name: "Family Purity and Respect for Parents Day", article: "30(1)(i¹)" },
  { month: 5, day: 26, name: "Independence Day of Georgia", nameKa: "დამოუკიდებლობის დღე", article: "30(1)(j)" },
  { month: 8, day: 28, name: "Assumption of the Virgin Mary — Mariamoba", nameKa: "მარიამობა", article: "30(1)(k)" },
  { month: 10, day: 14, name: "Mtskhetoba — Svetitskhovloba", nameKa: "მცხეთობა", article: "30(1)(l)",
    note: "Feast of Svetitskhoveli, the Robe of Jesus." },
  { month: 11, day: 23, name: "St George's Day — Giorgoba", nameKa: "გიორგობა", article: "30(1)(m)" },
];

/**
 * Orthodox Easter Sunday (Gregorian date) for a given year.
 *
 * Meeus's Julian algorithm gives the date on the JULIAN calendar; Georgia's church
 * uses it, but civil life uses the Gregorian, so we add the current Julian–Gregorian
 * offset (13 days for 1900–2099).
 *
 * Verified against the published dates: 2026 → 12 April, 2027 → 2 May.
 */
export function orthodoxEaster(year: number): Date {
  const a = year % 4;
  const b = year % 7;
  const c = year % 19;
  const d = (19 * c + 15) % 30;
  const e = (2 * a + 4 * b - d + 34) % 7;
  const month = Math.floor((d + e + 114) / 31); // 3 = March, 4 = April (Julian)
  const day = ((d + e + 114) % 31) + 1;

  // Julian date -> Gregorian. The offset is 13 days for the whole of 1900–2099.
  const julian = Date.UTC(year, month - 1, day);
  const offsetDays = year < 2100 ? 13 : 14;
  return new Date(julian + offsetDays * 86400000);
}

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function shift(d: Date, days: number): Date {
  return new Date(d.getTime() + days * 86400000);
}

/** Article 30(1)(g) — the four-day movable Easter block. */
export function easterBlock(year: number): Holiday[] {
  const sunday = orthodoxEaster(year);
  return [
    { date: iso(shift(sunday, -2)), name: "Good Friday", article: "30(1)(g)", movable: true,
      nameKa: "წითელი პარასკევი" },
    { date: iso(shift(sunday, -1)), name: "Holy Saturday", article: "30(1)(g)", movable: true },
    { date: iso(sunday), name: "Easter Sunday — Resurrection of Our Lord Jesus Christ", nameKa: "აღდგომა",
      article: "30(1)(g)", movable: true,
      note: "Orthodox Easter. It falls on a different date each year and is usually later than Western Easter." },
    { date: iso(shift(sunday, 1)), name: "Easter Monday — All Souls' Day", nameKa: "შავი ორშაბათი",
      article: "30(1)(g)", movable: true },
  ];
}

/**
 * Every public holiday of a given calendar year, in date order.
 *
 * COLLISIONS ARE REAL. Because Easter moves, a movable day can land on a fixed
 * holiday: in 2029, Easter Monday falls on 9 April, the Day of National Unity.
 * When that happens it is still ONE day off, not two — so we merge the entries.
 *
 * The practical consequence: the number of holiday DAYS is not a constant. It is
 * 18 in a typical year and 17 when the calendars collide. Anything that prints a
 * hardcoded "18" is wrong roughly once a decade.
 */
export function holidaysFor(year: number): Holiday[] {
  const fixed: Holiday[] = FIXED.map((h) => ({
    date: `${year}-${String(h.month).padStart(2, "0")}-${String(h.day).padStart(2, "0")}`,
    name: h.name,
    nameKa: h.nameKa,
    article: h.article,
    movable: false,
    note: h.note,
  }));

  const byDate = new Map<string, Holiday>();
  for (const h of [...fixed, ...easterBlock(year)]) {
    const existing = byDate.get(h.date);
    if (!existing) {
      byDate.set(h.date, { ...h });
      continue;
    }
    // Two holidays, one day. Keep both names and both statutory references.
    byDate.set(h.date, {
      date: h.date,
      name: `${existing.name} · ${h.name}`,
      nameKa: existing.nameKa ?? h.nameKa,
      article: `${existing.article}, ${h.article}`,
      movable: existing.movable || h.movable,
      note:
        "Two holidays coincide this year — the movable Easter block overlaps a fixed holiday. It is one day off, not two.",
    });
  }

  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
}

/** Years the calendar publishes. Kept as a function so it never goes stale. */
export function calendarYears(from = new Date().getUTCFullYear(), count = 6): number[] {
  return Array.from({ length: count }, (_, i) => from + i);
}

export const WEEKDAY = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export function weekdayOf(isoDate: string): string {
  return WEEKDAY[new Date(isoDate + "T00:00:00Z").getUTCDay()];
}
