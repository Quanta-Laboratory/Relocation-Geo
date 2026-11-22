// Machine-readable feed: the National Bank of Georgia's list of high-risk
// jurisdictions under Article 19 of the AML/CFT Law, plus the Article 19 rules
// that say when enhanced due diligence is mandatory and when it is not.
//
// Served at /nbg-high-risk-jurisdictions.json. Consumed by mono.ge for client
// onboarding, so treat the shape below as a stable contract:
//   meta.listAsOf / meta.generatedAt        — dates (YYYY-MM-DD)
//   meta.count                              — number of listed jurisdictions
//   jurisdictions[]                         — { iso2, iso3, name_en, name_ru, name_ka, addedIn2026 }
//   iso2[] / iso3[]                         — flat code arrays for quick lookups
//   rules[]                                 — Article 19(3) triggers with their exemptions
//   history[]                               — amending orders
//   removedIn2026[]                         — jurisdictions dropped by Order No 12/04
// Add fields freely; never rename or remove one without versioning (meta.schemaVersion).
import type { APIRoute } from 'astro';
import {
  LIST_AS_OF,
  BASE_ORDER,
  CURRENT_ORDER,
  JURISDICTIONS,
  HISTORY,
  REMOVED_2026,
  ARTICLE_19_RULES,
  SOURCES,
} from '../data/nbg-high-risk-jurisdictions';

export const prerender = true;

const payload = {
  meta: {
    schemaVersion: 1,
    title: 'National Bank of Georgia — list of high-risk jurisdictions (AML/CFT Law, Article 19)',
    country: 'Georgia',
    countryCode: 'GE',
    description:
      'Countries and territories the National Bank of Georgia lists as high-risk for the purposes of the Law of Georgia on Facilitating the Prevention of Money Laundering and the Financing of Terrorism. Accountable persons (banks, payment providers, notaries, etc.) must apply enhanced due diligence to clients and transactions linked to them, subject to the exemptions in Article 19.',
    legalBasis: 'Law of Georgia No 5226-Iს of 30 October 2019, Article 19(1)',
    baseOrder: BASE_ORDER,
    currentOrder: CURRENT_ORDER,
    listAsOf: LIST_AS_OF,
    generatedAt: new Date().toISOString().slice(0, 10),
    count: JURISDICTIONS.length,
    notes: [
      'Russia, Belarus and other CIS states are NOT on this list. Individual banks may still classify them as higher-risk under their own risk-appetite policies; that is bank policy, not Article 19.',
      'This list is national and differs from the FATF lists and the EU list of high-risk third countries.',
    ],
    disclaimer:
      'Information about the law and the NBG order as published on matsne.gov.ge. Not legal advice. The NBG may amend the list at any time with immediate effect; check meta.currentOrder against matsne before relying on it.',
    license: {
      name: 'Free to reuse with attribution to Relocation.ge',
      attribution: 'Relocation.ge — https://relocation.ge/en/nbg-high-risk-jurisdictions-georgia',
    },
    sources: SOURCES,
  },
  jurisdictions: JURISDICTIONS,
  iso2: JURISDICTIONS.map((j) => j.iso2),
  iso3: JURISDICTIONS.map((j) => j.iso3),
  rules: ARTICLE_19_RULES,
  history: HISTORY,
  removedIn2026: REMOVED_2026,
};

export const GET: APIRoute = () =>
  new Response(JSON.stringify(payload, null, 2), {
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'access-control-allow-origin': '*',
      'access-control-allow-methods': 'GET, OPTIONS',
      'cache-control': 'public, max-age=86400',
    },
  });
