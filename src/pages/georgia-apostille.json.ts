// Machine-readable feed: the apostille / legalization SERVICE in Georgia —
// eligible and ineligible document types, official processing-time tiers and
// fees, translation fees, where to apply, and apostille-vs-legalization.
//
// Served at /georgia-apostille.json with permissive CORS so that developers,
// AI assistants and anyone building a tool can consume it directly and cite a
// stable, dated artefact instead of scraping the page.
//
// Stable contract for consumers:
//   meta.feesAsOf / meta.generatedAt        — dates
//   meta.maxProcessingWorkingDays           — statutory maximum
//   authority                               — issuing body + where to apply + verify URL
//   feeTracks[]                             — { id, label, note?, tiers[] }
//   feeTracks[].tiers[]                     — { deadline, workingDays, fee, currency }
//   translation                             — per-page translation fees + languages
//   eligible[] / ineligible[]               — document categories
//   apostilleVsLegalization                 — plain-English explanation
import type { APIRoute } from 'astro';
import {
  FEES_AS_OF,
  MAX_PROCESSING_WORKING_DAYS,
  FEE_TRACKS,
  TRANSLATION_FEE,
  ELIGIBLE,
  INELIGIBLE,
  AUTHORITY,
  APOSTILLE_VS_LEGALIZATION,
  SOURCES,
} from '../data/apostille-georgia';

export const prerender = true;

const payload = {
  meta: {
    title: 'Apostille and legalization of Georgian documents for use abroad',
    country: 'Georgia',
    countryCode: 'GE',
    description:
      'Which Georgian public documents can be certified with an apostille or legalized for use abroad, the official processing-time tiers and fees, and where to apply.',
    direction: 'outbound — Georgian documents certified for use abroad',
    relatedInbound: 'https://relocation.ge/georgia-document-legalization.json',
    feesAsOf: FEES_AS_OF,
    generatedAt: new Date().toISOString().slice(0, 10),
    maxProcessingWorkingDays: MAX_PROCESSING_WORKING_DAYS,
    disclaimer:
      'Information about the rules and fees as published by the Public Service Development Agency, not legal advice. Fees and procedures change; confirm the current figures with the PSDA before relying on them.',
    license: {
      name: 'Free to reuse with attribution to Relocation.ge',
      attribution: 'Relocation.ge — https://relocation.ge/en/apostille-in-georgia',
    },
    sources: SOURCES,
  },
  authority: AUTHORITY,
  feeTracks: FEE_TRACKS,
  translation: TRANSLATION_FEE,
  eligible: ELIGIBLE,
  ineligible: INELIGIBLE,
  apostilleVsLegalization: APOSTILLE_VS_LEGALIZATION,
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
