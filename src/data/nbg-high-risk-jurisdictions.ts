// NBG list of high-risk jurisdictions for the purposes of the AML/CFT Law of Georgia.
//
// Single source of truth for:
//   - /nbg-high-risk-jurisdictions.json  (machine-readable feed, consumed by mono.ge)
//   - the guide pages that render the list
//
// Primary source: Order of the President of the National Bank of Georgia
// No 240/04 of 18 December 2019, Article 1 as last restated by Order No 12/04
// of 21 January 2026 (in force on publication). Verified against the Georgian
// text on matsne.gov.ge. Georgian names below are copied from the order.
//
// When the NBG amends the list: update JURISDICTIONS, LIST_AS_OF, CURRENT_ORDER,
// push PREVIOUS into HISTORY, and bump the guide pages' `reviewed` date.

export const LIST_AS_OF = '2026-01-21';

export const BASE_ORDER = {
  number: '240/04',
  date: '2019-12-18',
  title_ka:
    '„ფულის გათეთრებისა და ტერორიზმის დაფინანსების აღკვეთის ხელშეწყობის შესახებ“ საქართველოს კანონის მიზნებისათვის მაღალი რისკის იურისდიქციების ნუსხის დამტკიცების თაობაზე',
  title_en:
    'On approval of the list of high-risk jurisdictions for the purposes of the Law of Georgia on Facilitating the Prevention of Money Laundering and the Financing of Terrorism',
};

export const CURRENT_ORDER = {
  number: '12/04',
  date: '2026-01-21',
  inForce: 'on publication',
  url: 'https://matsne.gov.ge/ka/document/view/6755467',
};

export type Jurisdiction = {
  iso2: string;
  iso3: string;
  name_en: string;
  name_ru: string;
  name_ka: string;
  /** true = added by Order No 12/04 of 21 Jan 2026; false = already on the 2020 list */
  addedIn2026: boolean;
};

// Order of the list follows the Georgian alphabetical order in Order No 12/04 (ა–ჰ).
export const JURISDICTIONS: Jurisdiction[] = [
  { iso2: 'AF', iso3: 'AFG', name_en: 'Afghanistan', name_ru: 'Афганистан', name_ka: 'ავღანეთის ისლამური რესპუბლიკა', addedIn2026: false },
  { iso2: 'AL', iso3: 'ALB', name_en: 'Albania', name_ru: 'Албания', name_ka: 'ალბანეთის რესპუბლიკა', addedIn2026: false },
  { iso2: 'BB', iso3: 'BRB', name_en: 'Barbados', name_ru: 'Барбадос', name_ka: 'ბარბადოსი', addedIn2026: false },
  { iso2: 'BS', iso3: 'BHS', name_en: 'Bahamas', name_ru: 'Багамские Острова', name_ka: 'ბაჰამის კუნძულების თანამეგობრობა', addedIn2026: false },
  { iso2: 'BF', iso3: 'BFA', name_en: 'Burkina Faso', name_ru: 'Буркина-Фасо', name_ka: 'ბურკინა ფასო', addedIn2026: true },
  { iso2: 'GI', iso3: 'GIB', name_en: 'Gibraltar', name_ru: 'Гибралтар', name_ka: 'გიბრალტარი', addedIn2026: false },
  { iso2: 'DM', iso3: 'DMA', name_en: 'Dominica', name_ru: 'Доминика', name_ka: 'დომინიკის თანამეგობრობა', addedIn2026: false },
  { iso2: 'IQ', iso3: 'IRQ', name_en: 'Iraq', name_ru: 'Ирак', name_ka: 'ერაყის რესპუბლიკა', addedIn2026: false },
  { iso2: 'VU', iso3: 'VUT', name_en: 'Vanuatu', name_ru: 'Вануату', name_ka: 'ვანუატუს რესპუბლიკა', addedIn2026: false },
  { iso2: 'VE', iso3: 'VEN', name_en: 'Venezuela', name_ru: 'Венесуэла', name_ka: 'ვენესუელა', addedIn2026: true },
  { iso2: 'VN', iso3: 'VNM', name_en: 'Vietnam', name_ru: 'Вьетнам', name_ka: 'ვიეტნამი', addedIn2026: true },
  { iso2: 'TC', iso3: 'TCA', name_en: 'Turks and Caicos Islands', name_ru: 'Острова Теркс и Кайкос', name_ka: 'თერქს-ქაიქოსის კუნძულები', addedIn2026: false },
  { iso2: 'JM', iso3: 'JAM', name_en: 'Jamaica', name_ru: 'Ямайка', name_ka: 'იამაიკა', addedIn2026: false },
  { iso2: 'YE', iso3: 'YEM', name_en: 'Yemen', name_ru: 'Йемен', name_ka: 'იემენის რესპუბლიკა', addedIn2026: false },
  { iso2: 'IR', iso3: 'IRN', name_en: 'Iran', name_ru: 'Иран', name_ka: 'ირანის ისლამური რესპუბლიკა', addedIn2026: false },
  { iso2: 'KY', iso3: 'CYM', name_en: 'Cayman Islands', name_ru: 'Каймановы Острова', name_ka: 'კაიმანის კუნძულები', addedIn2026: false },
  { iso2: 'CM', iso3: 'CMR', name_en: 'Cameroon', name_ru: 'Камерун', name_ka: 'კამერუნის რესპუბლიკა', addedIn2026: true },
  { iso2: 'CO', iso3: 'COL', name_en: 'Colombia', name_ru: 'Колумбия', name_ka: 'კოლუმბიის რესპუბლიკა', addedIn2026: false },
  { iso2: 'KP', iso3: 'PRK', name_en: "Democratic People's Republic of Korea (North Korea)", name_ru: 'КНДР (Северная Корея)', name_ka: 'კორეის სახალხო დემოკრატიული რესპუბლიკა', addedIn2026: false },
  { iso2: 'LB', iso3: 'LBN', name_en: 'Lebanon', name_ru: 'Ливан', name_ka: 'ლიბანი', addedIn2026: true },
  { iso2: 'MM', iso3: 'MMR', name_en: 'Myanmar', name_ru: 'Мьянма', name_ka: 'მიანმარის კავშირის რესპუბლიკა', addedIn2026: false },
  { iso2: 'MZ', iso3: 'MOZ', name_en: 'Mozambique', name_ru: 'Мозамбик', name_ka: 'მოზამბიკი', addedIn2026: true },
  { iso2: 'NG', iso3: 'NGA', name_en: 'Nigeria', name_ru: 'Нигерия', name_ka: 'ნიგერიის ფედერაციული რესპუბლიკა', addedIn2026: false },
  { iso2: 'NI', iso3: 'NIC', name_en: 'Nicaragua', name_ru: 'Никарагуа', name_ka: 'ნიკარაგუის რესპუბლიკა', addedIn2026: false },
  { iso2: 'PK', iso3: 'PAK', name_en: 'Pakistan', name_ru: 'Пакистан', name_ka: 'პაკისტანის ისლამური რესპუბლიკა', addedIn2026: false },
  { iso2: 'PA', iso3: 'PAN', name_en: 'Panama', name_ru: 'Панама', name_ka: 'პანამის რესპუბლიკა', addedIn2026: false },
  { iso2: 'ZA', iso3: 'ZAF', name_en: 'South Africa', name_ru: 'ЮАР', name_ka: 'სამხრეთ აფრიკა', addedIn2026: true },
  { iso2: 'SS', iso3: 'SSD', name_en: 'South Sudan', name_ru: 'Южный Судан', name_ka: 'სამხრეთ სუდანი', addedIn2026: true },
  { iso2: 'SC', iso3: 'SYC', name_en: 'Seychelles', name_ru: 'Сейшельские Острова', name_ka: 'სეიშელის რესპუბლიკა', addedIn2026: false },
  { iso2: 'VC', iso3: 'VCT', name_en: 'Saint Vincent and the Grenadines', name_ru: 'Сент-Винсент и Гренадины', name_ka: 'სენტ-ვინსენტი და გრენადინები', addedIn2026: false },
  { iso2: 'SY', iso3: 'SYR', name_en: 'Syria', name_ru: 'Сирия', name_ka: 'სირიის არაბთა რესპუბლიკა', addedIn2026: false },
  { iso2: 'UG', iso3: 'UGA', name_en: 'Uganda', name_ru: 'Уганда', name_ka: 'უგანდის რესპუბლიკა', addedIn2026: false },
  { iso2: 'HT', iso3: 'HTI', name_en: 'Haiti', name_ru: 'Гаити', name_ka: 'ჰაიტი', addedIn2026: true },
];

/**
 * Amendment history of Article 1 of Order No 240/04 (amended by Orders No 99/04
 * of 1 May 2020, No 197/04 of 10 Nov 2020 and No 12/04 of 21 Jan 2026).
 * The diff below is computed from the full texts of 197/04 and 12/04.
 */
export const HISTORY = [
  {
    order: '197/04',
    date: '2020-11-10',
    url: 'https://matsne.gov.ge/ka/document/view/5030955',
    count: 30,
  },
  {
    order: '12/04',
    date: '2026-01-21',
    url: 'https://matsne.gov.ge/ka/document/view/6755467',
    count: 33,
    added_iso2: ['BF', 'VE', 'VN', 'CM', 'LB', 'MZ', 'ZA', 'SS', 'HT'],
    removed_iso2: ['BW', 'GH', 'ZW', 'KH', 'MU', 'TJ'],
  },
];

/** Jurisdictions removed by Order No 12/04 — kept so consumers can explain a change. */
export const REMOVED_2026 = [
  { iso2: 'BW', iso3: 'BWA', name_en: 'Botswana', name_ru: 'Ботсвана', name_ka: 'ბოტსვანის რესპუბლიკა' },
  { iso2: 'GH', iso3: 'GHA', name_en: 'Ghana', name_ru: 'Гана', name_ka: 'განას რესპუბლიკა' },
  { iso2: 'ZW', iso3: 'ZWE', name_en: 'Zimbabwe', name_ru: 'Зимбабве', name_ka: 'ზიმბაბვეს რესპუბლიკა' },
  { iso2: 'KH', iso3: 'KHM', name_en: 'Cambodia', name_ru: 'Камбоджа', name_ka: 'კამბოჯის სამეფო' },
  { iso2: 'MU', iso3: 'MUS', name_en: 'Mauritius', name_ru: 'Маврикий', name_ka: 'მავრიკის რესპუბლიკა' },
  { iso2: 'TJ', iso3: 'TJK', name_en: 'Tajikistan', name_ru: 'Таджикистан', name_ka: 'ტაჯიკეთის რესპუბლიკა' },
];

/**
 * Article 19 of the AML/CFT Law (as amended by Law No 4237 of 30 May 2024),
 * expressed as rules a consumer can apply. `trigger` = what makes enhanced
 * due diligence (EDD, Article 18) mandatory; `exemption` = when it is not.
 */
export const ARTICLE_19_RULES = [
  {
    id: 'legal_person',
    paragraph: '19(3)(a)',
    trigger:
      'Client is a legal person registered in a listed jurisdiction, a Georgian branch of such a legal person, and/or a legal person managed or operated from a listed jurisdiction.',
    exemption: null,
  },
  {
    id: 'natural_person_residence',
    paragraph: '19(3)(b)',
    trigger:
      'Client is a natural person whose place of registration and/or actual residence is in a listed jurisdiction.',
    exemption: {
      paragraph: '19(4)',
      text: 'EDD under 19(3)(b) is not mandatory if the client is a citizen of Georgia or a foreigner holding a Georgian residence permit.',
    },
  },
  {
    id: 'financial_institution',
    paragraph: '19(3)(c)',
    trigger:
      'A transaction is concluded or executed through a financial institution located in a listed jurisdiction.',
    exemption: {
      paragraph: '19(5)',
      text: 'EDD under 19(3)(c) is not mandatory if that financial institution is a subsidiary or branch of a financial institution registered in Georgia and group-level compliance manages ML/TF risk.',
    },
  },
];

export const SOURCES = [
  {
    name: 'Law of Georgia on Facilitating the Prevention of Money Laundering and the Financing of Terrorism, No 5226-Iს (consolidated)',
    url: 'https://matsne.gov.ge/ka/document/view/4690334',
  },
  {
    name: 'Order of the President of the NBG No 12/04 of 21 January 2026 amending Order No 240/04',
    url: 'https://matsne.gov.ge/ka/document/view/6755467',
  },
  {
    name: 'Order of the President of the NBG No 197/04 of 10 November 2020 amending Order No 240/04',
    url: 'https://matsne.gov.ge/ka/document/view/5030955',
  },
  {
    name: 'Financial Monitoring Service of Georgia — high-risk jurisdictions list',
    url: 'https://www.fms.gov.ge/ka',
  },
];
