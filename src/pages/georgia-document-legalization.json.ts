// Machine-readable feed: how to authenticate a foreign public document for use
// in Georgia (apostille / consular legalization / nothing beyond a notarized
// Georgian translation).
//
// Served at /georgia-document-legalization.json with permissive CORS so that
// developers, AI assistants and anyone building a tool can consume it directly
// and cite a stable, dated artefact instead of scraping the page.
//
// Stable contract for consumers:
//   meta.dataAsOf / meta.generatedAt — dates
//   defaultRegime                    — regime for any country NOT in `countries`
//   countries[]                      — { code, name, regime, basis, caveat?, effectiveFrom?, note? }
//   regimes / bases                  — enumerations with plain-English labels
import type { APIRoute } from 'astro';
import {
  COUNTRIES,
  COUNTS,
  DATA_AS_OF,
  DEFAULT_REGIME,
  HAGUE_PARTIES_TOTAL,
  SOURCES,
  ALWAYS_REQUIRED_NOTE,
} from '../data/document-legalization-georgia';

export const prerender = true;

const REGIMES = {
  none: 'Nothing beyond a notarized Georgian translation (legal-assistance-treaty exemption).',
  apostille: 'A single apostille obtained in the country of origin (Hague Convention 1961).',
  legalization: 'Full consular legalization chain (origin notary → origin MFA → Georgian consulate).',
};

const BASES = {
  bilateral_treaty: 'Bilateral legal-assistance treaty between Georgia and the country.',
  minsk_convention: '1993 Minsk Convention — applied in Georgian practice; strict treaty status debated.',
  hague_1961: 'Hague Apostille Convention 1961 (Georgia is a party since 2007).',
  default: 'No instrument — consular legalization is the fallback.',
};

const payload = {
  meta: {
    title: 'Document authentication for use in Georgia',
    country: 'Georgia',
    countryCode: 'GE',
    description:
      'Which foreign public documents need an apostille, consular legalization, or nothing beyond a notarized Georgian translation, to be used in the country of Georgia.',
    dataAsOf: DATA_AS_OF,
    generatedAt: new Date().toISOString().slice(0, 10),
    haguePartiesTotal: HAGUE_PARTIES_TOTAL,
    counts: COUNTS,
    alwaysRequired: ALWAYS_REQUIRED_NOTE,
    disclaimer:
      'Information about the rules as published, not legal advice. Treaty statuses and Convention membership change; verify with the receiving authority for high-stakes documents.',
    license: {
      name: 'Free to reuse with attribution to Relocation.ge',
      attribution: 'Relocation.ge — https://relocation.ge/en/georgia-document-legalization',
    },
    sources: SOURCES,
  },
  defaultRegime: DEFAULT_REGIME,
  regimes: REGIMES,
  bases: BASES,
  countries: COUNTRIES,
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

export const OPTIONS: APIRoute = () =>
  new Response(null, {
    headers: {
      'access-control-allow-origin': '*',
      'access-control-allow-methods': 'GET, OPTIONS',
      'access-control-allow-headers': '*',
    },
  });
