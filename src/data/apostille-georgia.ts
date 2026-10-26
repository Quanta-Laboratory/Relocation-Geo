// Canonical dataset: the apostille / legalization SERVICE in Georgia — which
// Georgian public documents can be certified for use abroad, the official
// processing-time tiers and fees, and where to apply.
//
// This module is the SINGLE SOURCE OF TRUTH. It feeds both the human page
// (/en/apostille-in-georgia) and the machine-readable API
// (/georgia-apostille.json), so the two can never drift apart.
//
// Sourcing: the Public Service Development Agency (PSDA) "Apostille and
// Legalization" service page, and Government of Georgia Decree No 405 of
// 18 August 2016 "On approving the rule of certifying a document with an
// apostille" (as amended by Decree No 604 of 29 September 2020). This is
// information about the rules as published, not legal advice.
//
// Note on direction: this covers OUTBOUND documents — Georgian documents being
// certified for use abroad. For the INBOUND question (does a FOREIGN document
// need an apostille / legalization to be used IN Georgia), see
// /en/georgia-document-legalization and /georgia-document-legalization.json.

export const FEES_AS_OF = '2026-01-20'; // PSDA service page last-modified date used
export const MAX_PROCESSING_WORKING_DAYS = 10; // statutory maximum (Decree No 405, art. 9.3)

export interface FeeTier {
  /** Human label for the deadline, e.g. "8th working day" or "Same day". */
  deadline: string;
  /** Working days to completion; null for same-day. */
  workingDays: number | null;
  fee: number;
  currency: 'GEL' | 'USD';
}

export interface FeeTrack {
  id: string;
  label: string;
  note?: string;
  tiers: FeeTier[];
}

// Processing-time / fee tracks (PSDA, as published).
export const FEE_TRACKS: FeeTrack[] = [
  {
    id: 'standard',
    label: 'Standard document (apostille or legalization)',
    tiers: [
      { deadline: '8th working day', workingDays: 8, fee: 30, currency: 'GEL' },
      { deadline: '4th working day', workingDays: 4, fee: 60, currency: 'GEL' },
      { deadline: '2nd working day', workingDays: 2, fee: 120, currency: 'GEL' },
      { deadline: 'Same day', workingDays: 0, fee: 150, currency: 'GEL' },
    ],
  },
  {
    id: 'education',
    label: 'Documents of the Ministry of Education, Science and Youth and its system',
    note: 'No same-day tier for these documents.',
    tiers: [
      { deadline: '8th working day', workingDays: 8, fee: 30, currency: 'GEL' },
      { deadline: '4th working day', workingDays: 4, fee: 60, currency: 'GEL' },
      { deadline: '2 working days', workingDays: 2, fee: 120, currency: 'GEL' },
    ],
  },
  {
    id: 'remote',
    label: 'Physical document certified remotely (applicant abroad, by electronic visual contact), or e-apostille of an electronic document',
    tiers: [
      { deadline: 'Within 3 working days', workingDays: 3, fee: 55, currency: 'GEL' },
    ],
  },
  {
    id: 'e_apostille',
    label: 'E-apostille of an electronic document, applied for with a qualified electronic signature on the website',
    tiers: [
      { deadline: 'Within 3 working days', workingDays: 3, fee: 50, currency: 'GEL' },
    ],
  },
  {
    id: 'consular',
    label: 'Processing when applying through a Georgian consular office abroad',
    tiers: [
      { deadline: 'Within 8 working days', workingDays: 8, fee: 10, currency: 'USD' },
    ],
  },
];

// Translation of the document into a foreign language, per page (or part page).
export const TRANSLATION_FEE = {
  domestic: { fee: 30, currency: 'GEL' as const },
  consular: { fee: 10, currency: 'USD' as const },
  languages: ['English', 'Italian', 'French', 'Spanish', 'Greek', 'Russian', 'German', 'Turkish'],
};

// Document categories that CAN be certified with apostille/legalization.
export const ELIGIBLE: string[] = [
  'Documents issued by medical institutions within the scope of their authority',
  'Documents issued by the Ministry of Education, Science and Youth and the agencies in its system, and by educational institutions within their authority',
  'Documents issued by judicial (court) authorities',
  'Notarial acts',
  'Documents issued by administrative bodies of Georgia',
  'A letter by an administrative body certifying that a copy matches the original',
  'A translation of an eligible document made by an administrative body',
];

// Document categories that CANNOT be certified with apostille/legalization.
export const INELIGIBLE: string[] = [
  "Documents issued by Georgia's diplomatic missions and consular offices abroad",
  'Documents issued by private-law legal entities (except medical and educational institutions)',
  'Administrative-body documents related to customs and commercial operations',
  'Identity documents and their copies — except an issuer-certified copy of a Georgian citizen’s passport',
  'Military service record card',
  'Vehicle registration document (technical passport) and driver’s licence',
  'Receipts issued by administrative bodies',
  'Notarial acts certifying a copy’s accuracy against the original, or the accuracy of a translation',
  'Normative (legislative) acts',
];

export const AUTHORITY = {
  name: 'Public Service Development Agency (PSDA)',
  parent: 'Ministry of Justice of Georgia',
  servicePage: 'https://sda.gov.ge/en/products/apostille-and-legalization/',
  // The MIA Service Agency apostilles documents it issues itself.
  otherAuthority: 'Service Agency of the Ministry of Internal Affairs — for documents it issues itself (sa.gov.ge)',
  verify: 'https://apostille.cra.ge',
  applyChannels: [
    'PSDA territorial offices',
    'Public Service Hall branches',
    'Online via sda.gov.ge and the unified government portal my.gov.ge',
    'Georgian consular offices abroad',
  ],
};

export const APOSTILLE_VS_LEGALIZATION = {
  apostille:
    'For countries party to the Hague Convention of 5 October 1961 (Apostille Convention). A single apostille stamp issued by the PSDA makes the document usable in any member state.',
  legalization:
    'For countries that are NOT party to the Apostille Convention. A two-step chain: the PSDA performs the first stage and the Consular Department of the Ministry of Foreign Affairs the second, handled on a single-window principle at the PSDA. The document must then be additionally certified by the destination country’s diplomatic/consular office before it can be used there.',
};

export const SOURCES = [
  {
    name: 'Public Service Development Agency — Apostille and Legalization (document types, processing times and fees)',
    url: 'https://sda.gov.ge/en/products/apostille-and-legalization/',
  },
  {
    name: 'Government of Georgia Decree No 405 of 18 August 2016 — rule for certifying a document with an apostille (as amended by Decree No 604, 29.09.2020); matsne doc. 3378264',
    url: 'https://matsne.gov.ge/ka/document/view/3378264',
  },
  {
    name: 'HCCH — Georgia, Competent Authority under the 1961 Apostille Convention',
    url: 'https://www.hcch.net/en/states/authorities/details3/?aid=700',
  },
  {
    name: 'Apostille verification (PSDA)',
    url: 'https://apostille.cra.ge',
  },
];
