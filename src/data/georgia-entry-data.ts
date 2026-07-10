// Data compiled from Georgian Government Ordinances No 255 and No 256 (5 June 2015),
// cross-checked against the MFA consular portal (geoconsul.gov.ge). Lists change —
// treat as guidance and verify on geoconsul before travel.
//
// SCOPE / VERIFICATION NOTES (read before relying on these arrays):
// - The country names below are transcribed from the official ENGLISH text of the
//   *initial* (08/06/2015) publications of Ordinance No 255 (94 numbered rows) and
//   Ordinance No 256 (50 numbered rows) on matsne.gov.ge.
// - Non-sovereign territory rows in the ordinances (Faroe Islands & Greenland; UK
//   overseas territories; UK crown dependencies — Jersey, Guernsey, Isle of Man;
//   Aruba & Netherlands Antilles; French Polynesia & New Caledonia) are covered by
//   the ordinances but are intentionally omitted here, since these arrays hold
//   full country names only. EU member-state ID-card holders and UN Laissez-Passer
//   holders also enjoy visa-free entry under Ord. 255 notes but are not countries.
// - Ordinance No 255 has since been amended eight times (last: 24/02/2026) and
//   Ordinance No 256 once (17/04/2025). The consolidated ENGLISH versions on
//   matsne.gov.ge are paywalled, and the amendment ordinances carry no official
//   English translation, so post-2015 additions/removals could NOT be individually
//   confirmed from the official text. The MFA currently cites ~98 visa-free
//   countries, so a small number of later additions are likely missing below.
//   No unconfirmed entries have been invented to close that gap — verify on
//   geoconsul.gov.ge before travel.
export const dataAsOf = "2026-07-10";
export const sources = [
  { name: "Ordinance No 255 (visa-free list) — Legislative Herald", url: "https://matsne.gov.ge/en/document/view/2867361" },
  { name: "Ordinance No 256 (visa/residence-permit holders) — Legislative Herald", url: "https://matsne.gov.ge/en/document/view/2867377" },
  { name: "MFA consular & e-Visa portal", url: "https://www.geoconsul.gov.ge/en" }
];
// Citizens of these countries may enter visa-free and stay up to 1 year (Ord. 255).
export const visaFreeOneYear: string[] = [
  "Albania",
  "Andorra",
  "Antigua and Barbuda",
  "Argentina",
  "Armenia",
  "Australia",
  "Austria",
  "Azerbaijan",
  "Bahamas",
  "Bahrain",
  "Barbados",
  "Belarus",
  "Belgium",
  "Belize",
  "Bosnia and Herzegovina",
  "Botswana",
  "Brazil",
  "Brunei",
  "Bulgaria",
  "Canada",
  "Colombia",
  "Costa Rica",
  "Croatia",
  "Cyprus",
  "Czech Republic",
  "Denmark",
  "Dominican Republic",
  "Ecuador",
  "El Salvador",
  "Estonia",
  "Finland",
  "France",
  "Germany",
  "Greece",
  "Holy See",
  "Honduras",
  "Hungary",
  "Iceland",
  "Ireland",
  "Israel",
  "Italy",
  "Japan",
  "Kazakhstan",
  "Kuwait",
  "Kyrgyzstan",
  "Latvia",
  "Lebanon",
  "Liechtenstein",
  "Lithuania",
  "Luxembourg",
  "Malaysia",
  "Malta",
  "Mauritius",
  "Mexico",
  "Moldova",
  "Monaco",
  "Montenegro",
  "Netherlands",
  "New Zealand",
  "Norway",
  "Oman",
  "Panama",
  "Poland",
  "Portugal",
  "Qatar",
  "Romania",
  "Russia",
  "Saint Vincent and the Grenadines",
  "San Marino",
  "Saudi Arabia",
  "Serbia",
  "Seychelles",
  "Singapore",
  "Slovakia",
  "Slovenia",
  "South Africa",
  "South Korea",
  "Spain",
  "Sweden",
  "Switzerland",
  "Tajikistan",
  "Thailand",
  "Turkey",
  "Turkmenistan",
  "Ukraine",
  "United Arab Emirates",
  "United Kingdom",
  "United States",
  "Uzbekistan"
];
// Holders of a valid visa or residence permit of these countries may enter visa-free for up to 90 days in any 180-day period (Ord. 256).
export const designatedDocCountries: string[] = [
  "Australia",
  "Austria",
  "Bahrain",
  "Belgium",
  "Bulgaria",
  "Canada",
  "Croatia",
  "Cyprus",
  "Czech Republic",
  "Denmark",
  "Estonia",
  "Finland",
  "France",
  "Germany",
  "Greece",
  "Hungary",
  "Iceland",
  "Ireland",
  "Israel",
  "Italy",
  "Japan",
  "Kuwait",
  "Latvia",
  "Liechtenstein",
  "Lithuania",
  "Luxembourg",
  "Malta",
  "Netherlands",
  "New Zealand",
  "Norway",
  "Oman",
  "Poland",
  "Portugal",
  "Qatar",
  "Romania",
  "Saudi Arabia",
  "Slovakia",
  "Slovenia",
  "South Korea",
  "Spain",
  "Sweden",
  "Switzerland",
  "United Arab Emirates",
  "United Kingdom",
  "United States"
];
