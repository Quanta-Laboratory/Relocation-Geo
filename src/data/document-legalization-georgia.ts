// Canonical dataset: how a foreign public document must be authenticated to be
// used in Georgia — apostille, consular legalization, or nothing beyond a
// notarized Georgian translation (a legal-assistance-treaty exemption).
//
// This module is the SINGLE SOURCE OF TRUTH. It feeds both the human page
// (/en/georgia-document-legalization) and the machine-readable API
// (/georgia-document-legalization.json), so the two can never drift apart.
//
// Sourcing: the Hague Apostille Convention status table (HCCH) for the
// apostille members, and the Georgian National Notary Chamber list of applicable
// international acts + matsne ratification records for the treaty exemptions.
// Everything not covered by a treaty or the Apostille Convention falls back to
// consular legalization. This is information about the rules as published, not
// legal advice.

export const DATA_AS_OF = '2026-06-30'; // HCCH status table last update used
export const HAGUE_PARTIES_TOTAL = 130; // contracting parties on that date

export type Regime =
  | 'none' // nothing beyond notarized Georgian translation
  | 'apostille' // single apostille in the country of origin
  | 'legalization'; // full consular legalization chain

export type Basis =
  | 'bilateral_treaty' // Georgia has a bilateral legal-assistance treaty
  | 'minsk_convention' // 1993 Minsk Convention (applied in practice — see caveat)
  | 'hague_1961' // Hague Apostille Convention 1961
  | 'default'; // no instrument — consular legalization

export interface CountryRule {
  code: string; // ISO 3166-1 alpha-2
  name: string;
  regime: Regime;
  basis: Basis;
  /** Set when the classification is not a hard guarantee (Minsk group). */
  caveat?: string;
  /** For members whose apostille is not yet in force: date it becomes effective. */
  effectiveFrom?: string;
  note?: string;
}

/** Any country not listed below defaults to consular legalization. */
export const DEFAULT_REGIME: Regime = 'legalization';

export const SOURCES = [
  {
    name: 'HCCH — Hague Apostille Convention (No. 12) status table',
    url: 'https://www.hcch.net/en/instruments/conventions/status-table/?cid=41',
  },
  {
    name: 'National Notary Chamber of Georgia — international legal acts',
    url: 'https://www.notary.ge/geo-2334-saertashoriso-samartlebrivi-aqtebi',
  },
  {
    name: "Georgia's accession to the 1993 Minsk Convention — Decree No. 93 (matsne)",
    url: 'https://matsne.gov.ge/ka/document/view/37708',
  },
  {
    name: 'Public Service Development Agency of Georgia (PSDA)',
    url: 'https://sda.gov.ge/en',
  },
];

const MINSK_CAVEAT =
  'Accepted in current Georgian practice under the 1993 Minsk Convention, which Georgia continues to apply despite leaving the CIS in 2009. Its strict treaty status is debated — confirm with the receiving authority or a notary for high-stakes documents.';

// --- Group 1a: bilateral legal-assistance treaties (well-supported) ---------
const TREATY: CountryRule[] = [
  { code: 'UA', name: 'Ukraine', regime: 'none', basis: 'bilateral_treaty', note: 'Bilateral treaty 1995. (Also has an apostille alternative.)' },
  { code: 'BG', name: 'Bulgaria', regime: 'none', basis: 'bilateral_treaty', note: 'Bilateral treaty 1995. Also a Hague member (apostille also accepted).' },
  { code: 'AZ', name: 'Azerbaijan', regime: 'none', basis: 'bilateral_treaty', note: 'Bilateral treaty 1996.' },
  { code: 'TM', name: 'Turkmenistan', regime: 'none', basis: 'bilateral_treaty', note: 'Bilateral treaty 1996. (Not a Hague member.)' },
  { code: 'AM', name: 'Armenia', regime: 'none', basis: 'bilateral_treaty', note: 'Bilateral treaty 1996.' },
  { code: 'TR', name: 'Türkiye', regime: 'none', basis: 'bilateral_treaty', note: 'Bilateral treaty 1996. Also a Hague member (apostille also accepted).' },
  { code: 'KZ', name: 'Kazakhstan', regime: 'none', basis: 'bilateral_treaty', note: 'Bilateral treaty 1996.' },
  { code: 'GR', name: 'Greece', regime: 'none', basis: 'bilateral_treaty', note: 'Bilateral treaty 1999. Also a Hague member (apostille also accepted).' },
];

// --- Group 1b: Minsk Convention only (applied in practice, with caveat) ------
const MINSK: CountryRule[] = [
  { code: 'RU', name: 'Russian Federation', regime: 'none', basis: 'minsk_convention', caveat: MINSK_CAVEAT, note: 'No bilateral treaty; relies on the Minsk Convention. Georgia–Russia consular legalization is unavailable (no diplomatic relations since 2008).' },
  { code: 'BY', name: 'Belarus', regime: 'none', basis: 'minsk_convention', caveat: MINSK_CAVEAT },
  { code: 'UZ', name: 'Uzbekistan', regime: 'none', basis: 'minsk_convention', caveat: MINSK_CAVEAT },
  { code: 'KG', name: 'Kyrgyzstan', regime: 'none', basis: 'minsk_convention', caveat: MINSK_CAVEAT },
  { code: 'MD', name: 'Moldova', regime: 'none', basis: 'minsk_convention', caveat: MINSK_CAVEAT },
  { code: 'TJ', name: 'Tajikistan', regime: 'none', basis: 'minsk_convention', caveat: MINSK_CAVEAT },
];

// --- Group 2: Apostille (Hague 1961 members, excluding the treaty group) -----
const APOSTILLE_NAMES: [string, string][] = [
  ['AL', 'Albania'], ['DZ', 'Algeria'], ['AD', 'Andorra'], ['AG', 'Antigua and Barbuda'],
  ['AR', 'Argentina'], ['AU', 'Australia'], ['AT', 'Austria'], ['BS', 'Bahamas'],
  ['BH', 'Bahrain'], ['BD', 'Bangladesh'], ['BB', 'Barbados'], ['BE', 'Belgium'],
  ['BZ', 'Belize'], ['BO', 'Bolivia'], ['BA', 'Bosnia and Herzegovina'], ['BW', 'Botswana'],
  ['BR', 'Brazil'], ['BN', 'Brunei Darussalam'], ['BI', 'Burundi'], ['CV', 'Cabo Verde'],
  ['CA', 'Canada'], ['CL', 'Chile'], ['CN', 'China'], ['CO', 'Colombia'],
  ['CK', 'Cook Islands'], ['CR', 'Costa Rica'], ['HR', 'Croatia'], ['CY', 'Cyprus'],
  ['CZ', 'Czechia'], ['DK', 'Denmark'], ['DM', 'Dominica'], ['DO', 'Dominican Republic'],
  ['EC', 'Ecuador'], ['SV', 'El Salvador'], ['EE', 'Estonia'], ['SZ', 'Eswatini'],
  ['FJ', 'Fiji'], ['FI', 'Finland'], ['FR', 'France'], ['DE', 'Germany'],
  ['GD', 'Grenada'], ['GT', 'Guatemala'], ['GY', 'Guyana'], ['HN', 'Honduras'],
  ['HU', 'Hungary'], ['IS', 'Iceland'], ['IN', 'India'], ['ID', 'Indonesia'],
  ['IE', 'Ireland'], ['IL', 'Israel'], ['IT', 'Italy'], ['JM', 'Jamaica'],
  ['JP', 'Japan'], ['LV', 'Latvia'], ['LS', 'Lesotho'], ['LR', 'Liberia'],
  ['LI', 'Liechtenstein'], ['LT', 'Lithuania'], ['LU', 'Luxembourg'], ['MW', 'Malawi'],
  ['MT', 'Malta'], ['MH', 'Marshall Islands'], ['MU', 'Mauritius'], ['MX', 'Mexico'],
  ['MC', 'Monaco'], ['MN', 'Mongolia'], ['ME', 'Montenegro'], ['MA', 'Morocco'],
  ['NA', 'Namibia'], ['NL', 'Netherlands'], ['NZ', 'New Zealand'], ['NI', 'Nicaragua'],
  ['NU', 'Niue'], ['MK', 'North Macedonia'], ['NO', 'Norway'], ['OM', 'Oman'],
  ['PK', 'Pakistan'], ['PW', 'Palau'], ['PA', 'Panama'], ['PY', 'Paraguay'],
  ['PE', 'Peru'], ['PH', 'Philippines'], ['PL', 'Poland'], ['PT', 'Portugal'],
  ['KR', 'Republic of Korea'], ['RO', 'Romania'], ['RW', 'Rwanda'], ['KN', 'Saint Kitts and Nevis'],
  ['LC', 'Saint Lucia'], ['VC', 'Saint Vincent and the Grenadines'], ['WS', 'Samoa'], ['SM', 'San Marino'],
  ['ST', 'Sao Tome and Principe'], ['SA', 'Saudi Arabia'], ['SN', 'Senegal'], ['RS', 'Serbia'],
  ['SC', 'Seychelles'], ['SG', 'Singapore'], ['SK', 'Slovakia'], ['SI', 'Slovenia'],
  ['ZA', 'South Africa'], ['ES', 'Spain'], ['SR', 'Suriname'], ['SE', 'Sweden'],
  ['CH', 'Switzerland'], ['TO', 'Tonga'], ['TT', 'Trinidad and Tobago'], ['TN', 'Tunisia'],
  ['GB', 'United Kingdom'], ['US', 'United States of America'], ['UY', 'Uruguay'], ['VU', 'Vanuatu'],
  ['VE', 'Venezuela'],
];
const APOSTILLE: CountryRule[] = APOSTILLE_NAMES.map(([code, name]) => ({
  code,
  name,
  regime: 'apostille',
  basis: 'hague_1961',
}));

// --- Special cases -----------------------------------------------------------
const SPECIAL: CountryRule[] = [
  { code: 'VN', name: 'Viet Nam', regime: 'legalization', basis: 'default', effectiveFrom: '2026-09-11', note: 'Joined the Apostille Convention; apostille becomes effective 11 Sep 2026. Until then, consular legalization.' },
  { code: 'TH', name: 'Thailand', regime: 'legalization', basis: 'default', effectiveFrom: '2027-02-28', note: 'Joined the Apostille Convention; apostille becomes effective 28 Feb 2027. Until then, consular legalization.' },
  { code: 'XK', name: 'Kosovo', regime: 'legalization', basis: 'default', note: 'Georgia objected to Kosovo’s accession and does not recognise Kosovo, so apostille does not operate between them.' },
];

export const COUNTRIES: CountryRule[] = [...TREATY, ...MINSK, ...APOSTILLE, ...SPECIAL].sort((a, b) =>
  a.name.localeCompare(b.name),
);

export const COUNTS = {
  none_bilateral_treaty: TREATY.length,
  none_minsk_convention: MINSK.length,
  apostille: APOSTILLE.length,
  special_cases: SPECIAL.length,
  total_listed: COUNTRIES.length,
};

const BY_CODE = new Map(COUNTRIES.map((c) => [c.code, c]));

/**
 * Look up the authentication regime for a country used in Georgia.
 * Returns the listed rule, or a synthetic default (consular legalization) for
 * any country not covered by a treaty or the Apostille Convention.
 */
export function regimeFor(code: string): CountryRule {
  const hit = BY_CODE.get(code.toUpperCase());
  if (hit) return hit;
  return {
    code: code.toUpperCase(),
    name: code.toUpperCase(),
    regime: DEFAULT_REGIME,
    basis: 'default',
    note: 'Not covered by an apostille or a legal-assistance treaty with Georgia — full consular legalization applies.',
  };
}

export const ALWAYS_REQUIRED_NOTE =
  'In every case the document must still be translated into Georgian and the translation notarized in Georgia. A private document such as a power of attorney is first certified by a notary in the country of origin; the apostille / legalization / treaty exemption then applies to that notarial certification.';
