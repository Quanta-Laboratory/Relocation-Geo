// Activity screening data for Small Business Status (1% regime).
//
// HOW TO READ THIS FILE — AND ITS LIMITS
// --------------------------------------
// Georgian law does NOT list prohibited activities by classifier code. Annex 4 to
// Government Ordinance No 415 states seven categories in WORDS. This dataset maps
// activity codes onto those seven categories, and that mapping is our reading, not
// the law. That is why every entry carries a verdict of three values and never a
// bare yes/no:
//
//   "prohibited" — the activity is named in Annex 4 in terms that leave little room
//                  (medical practice, notarial work, auditing, gambling, staffing,
//                   excisable manufacture, currency operations).
//   "grey"       — the activity sits on or near the boundary of an Annex 4 category,
//                  most often the word "consulting". Only the Revenue Service can
//                  settle these, and the cost of guessing wrong is retroactive loss
//                  of the status for the whole calendar year.
//   "clear"      — nothing in Annex 4 appears to reach this activity.
//
// "clear" is not a guarantee. Two further traps sit outside Annex 4:
//   * any activity requiring a LICENCE or PERMIT is prohibited (Annex 4, item 1),
//     and that list lives in a separate law we do not reproduce here;
//   * some INCOME is taxed under ordinary rules even for an eligible business
//     (Annex 5) — rent, interest, dividends, royalties and similar.
//
// Codes follow the Georgian national classifier SEC 006-2016, which is built on
// NACE Rev. 2. Confirm the exact code recorded against your registration with the
// Revenue Service — the code the tax authority holds is the one that governs.
//
// The consolidated (current) text of Ordinance No 415 is paywalled on matsne; the
// free text is the 2010 original. The categories below reflect the list as we
// understand it to stand, but it has been amended fifteen times.

export const dataAsOf = "2026-07-12";

export const sources = [
  {
    name: "Government Ordinance No 415 of 29 December 2010 — On Special Taxation Regimes (Annex 4: prohibited activities; Annex 5: excluded income)",
    url: "https://matsne.gov.ge/ka/document/view/1164635",
  },
  {
    name: "Tax Code of Georgia (Chapter XII — special taxation regimes)",
    url: "https://matsne.gov.ge/en/document/view/1043717",
  },
  {
    name: "Order of the Minister of Finance No 999 of 31 December 2010 — application of special taxation regimes",
    url: "https://matsne.gov.ge/ka/document/view/1168081",
  },
  { name: "Revenue Service of Georgia", url: "https://www.rs.ge/" },
];

// The seven prohibited categories, verbatim in substance, from Annex 4.
export const prohibitedCategories: { id: number; label: string }[] = [
  { id: 1, label: "Activities requiring a licence or permit (except the M1 taxi permit in the capital)" },
  { id: 2, label: "Activities requiring significant investment (manufacture of excisable goods)" },
  { id: 3, label: "Foreign-currency operations" },
  { id: 4, label: "Medical, architectural, legal advocacy or notarial, auditing, or consulting activities (including tax consulting)" },
  { id: 5, label: "Gambling business" },
  { id: 6, label: "Provision of personnel (staffing)" },
  { id: 7, label: "Manufacture of excisable goods" },
];

// Plain-language terms people actually type, mapped to codes. This is the FIRST
// layer of search and it is deterministic — no model involved. It exists because
// nobody searches for "62.01"; they search for "I build websites".
//
// Keep entries lower-case. Matching is substring-based on the whole query.
export const aliases: Record<string, string[]> = {
  "62.01": ["website", "websites", "web development", "web dev", "webdev", "developer",
    "software", "software development", "programmer", "programming", "coding", "coder",
    "frontend", "front-end", "backend", "back-end", "full stack", "fullstack", "app",
    "mobile app", "ios", "android", "engineer", "software engineer", "devops"],
  "62.02": ["it consulting", "it consultancy", "tech consulting", "technical consulting",
    "solution architect", "architecture consulting", "cto for hire", "fractional cto",
    "it advisory", "systems consulting"],
  "62.03": ["infrastructure", "sysadmin", "system administration", "server management",
    "it support", "managed services", "helpdesk"],
  "62.09": ["it services", "it", "tech services", "qa", "quality assurance", "testing",
    "tester", "data engineer", "database"],
  "63.11": ["hosting", "data processing", "cloud", "saas hosting", "data centre"],
  "63.12": ["web portal", "portal", "marketplace", "aggregator"],
  "58.21": ["game development", "gamedev", "game developer", "video games", "game studio"],
  "58.29": ["software publishing", "publish software", "app store"],
  "69.10": ["lawyer", "legal", "attorney", "advocate", "notary", "law firm", "legal services",
    "paralegal"],
  "69.20": ["accountant", "accounting", "bookkeeping", "bookkeeper", "audit", "auditor",
    "auditing", "tax consultant", "tax consulting", "tax advisor", "tax advisory", "cfo"],
  "70.21": ["pr", "public relations", "communications", "press", "publicist", "media relations"],
  "70.22": ["management consulting", "management consultancy", "business consulting",
    "business consultant", "consultant", "consulting", "strategy", "strategy consulting",
    "business advisor", "advisory", "coach", "business coach", "growth consulting"],
  "71.11": ["architect", "architecture", "architectural"],
  "71.12": ["engineering", "engineer consulting", "technical consultancy", "surveying",
    "civil engineering"],
  "73.11": ["advertising", "ads", "ad agency", "marketing", "marketing agency", "smm",
    "social media marketing", "ppc", "seo", "performance marketing", "campaigns",
    "copywriting", "copywriter", "content marketing"],
  "73.12": ["media buying", "ad sales", "media representation"],
  "73.20": ["market research", "surveys", "polling", "user research", "focus groups"],
  "74.10": ["design", "designer", "graphic design", "graphic designer", "ux", "ui", "ux/ui",
    "product design", "interior design", "branding", "logo", "illustration", "illustrator"],
  "74.20": ["photography", "photographer", "video", "videographer", "filming"],
  "74.30": ["translation", "translator", "interpreting", "interpreter", "localisation",
    "localization", "subtitling", "proofreading", "editing"],
  "74.90": ["freelance", "freelancer", "other professional", "misc services"],
  "82.11": ["office admin", "administrative support", "virtual assistant", "va",
    "back office", "assistant"],
  "82.99": ["business support", "outsourcing", "bpo", "customer support", "call centre",
    "call center", "support agent"],
  "78.10": ["recruitment", "recruiter", "recruiting", "headhunting", "headhunter",
    "employment agency", "talent acquisition"],
  "78.20": ["staffing", "temp agency", "temporary staffing", "labour hire", "outstaffing"],
  "78.30": ["hr provision", "personnel provision", "staff leasing", "outstaffing"],
  "92.00": ["gambling", "betting", "casino", "bookmaker", "poker", "lottery"],
  "86.21": ["doctor", "physician", "gp", "general practice", "medical practice"],
  "86.22": ["specialist doctor", "surgeon", "medical specialist"],
  "86.23": ["dentist", "dental"],
  "86.90": ["nurse", "therapist", "physiotherapy", "psychologist", "psychotherapy",
    "medical", "health", "healthcare", "clinic"],
  "66.12": ["brokerage", "broker", "securities", "trading securities", "commodities"],
  "66.19": ["currency exchange", "money exchange", "forex", "money transfer", "payments",
    "fintech", "crypto exchange"],
  "64.19": ["bank", "banking", "lending", "credit", "microfinance"],
  "11.01": ["spirits", "distillery", "vodka", "chacha", "brandy"],
  "11.02": ["winery", "wine production", "wine making", "winemaking"],
  "11.05": ["brewery", "beer production", "craft beer"],
  "12.00": ["tobacco", "cigarettes", "vape liquid"],
  "19.20": ["fuel", "petroleum", "refinery"],
  "47.19": ["shop", "store", "retail", "retail store"],
  "47.91": ["ecommerce", "e-commerce", "online shop", "online store", "dropshipping",
    "amazon", "etsy", "shopify"],
  "46.19": ["wholesale", "trading", "trade", "import", "export", "reseller", "commission agent"],
  "55.10": ["hotel", "guesthouse", "hostel", "airbnb", "short term rental", "accommodation"],
  "56.10": ["restaurant", "cafe", "food", "catering", "kitchen", "chef"],
  "56.30": ["bar", "pub", "coffee shop", "beverages"],
  "85.59": ["teaching", "teacher", "tutor", "tutoring", "training", "courses", "language school",
    "coaching lessons", "instructor", "education"],
  "90.03": ["artist", "writer", "author", "creative", "musician", "composer", "art"],
  "59.11": ["film production", "video production", "tv production", "filmmaker"],
  "59.20": ["music", "recording studio", "sound", "audio", "podcast"],
  "41.20": ["construction", "builder", "building", "contractor", "renovation"],
  "43.39": ["finishing works", "interior finishing", "plastering", "painting", "tiling"],
  "68.20": ["rent out", "renting property", "landlord", "letting", "lease property",
    "rental income", "property rental"],
  "68.31": ["real estate agent", "realtor", "estate agency", "property agent"],
  "49.32": ["taxi", "bolt", "yandex taxi", "ride hailing", "driver"],
  "49.41": ["trucking", "haulage", "freight", "logistics", "delivery by road"],
  "53.20": ["courier", "delivery", "postal", "parcel"],
  "95.11": ["computer repair", "laptop repair", "pc repair"],
  "96.02": ["hairdresser", "barber", "salon", "beauty", "manicure", "nails", "cosmetology"],
  "45.20": ["car repair", "auto repair", "garage", "mechanic", "car service"],
  "01.11": ["farming", "agriculture", "crops", "grain", "farmer"],
};

export type Verdict = "prohibited" | "grey" | "clear";

export interface Activity {
  code: string;
  name: string;
  verdict: Verdict;
  /** Which Annex 4 category this touches, if any. */
  category?: number;
  /** Why — shown to the user. */
  note: string;
  /** Extra warning even when the activity itself is fine (e.g. income type). */
  incomeWarning?: string;
}

export const activities: Activity[] = [
  // ---------------------------------------------------------------- IT & digital
  { code: "62.01", name: "Computer programming activities", verdict: "clear",
    note: "Software development is not named in Annex 4. The most common eligible activity among foreign IEs." },
  { code: "62.02", name: "Computer consultancy activities", verdict: "grey", category: 4,
    note: "The code carries the word 'consultancy'. Annex 4 prohibits 'consulting'. Whether advisory IT work is caught, or is treated as technical service, is exactly the boundary the Revenue Service must settle for you." },
  { code: "62.03", name: "Computer facilities management activities", verdict: "clear",
    note: "Operational management of IT infrastructure — service delivery rather than advice." },
  { code: "62.09", name: "Other information technology and computer service activities", verdict: "clear",
    note: "Catch-all IT services. If your work is in substance advisory, see 62.02." },
  { code: "63.11", name: "Data processing, hosting and related activities", verdict: "clear",
    note: "Infrastructure and processing services." },
  { code: "63.12", name: "Web portals", verdict: "clear", note: "Operating web portals." },
  { code: "58.21", name: "Publishing of computer games", verdict: "clear",
    note: "Publishing games is not gambling. Annex 4 item 5 targets gambling and betting operations (see 92.00)." },
  { code: "58.29", name: "Other software publishing", verdict: "clear", note: "Software publishing." },

  // ------------------------------------------------------- Professional services
  { code: "69.10", name: "Legal activities", verdict: "prohibited", category: 4,
    note: "Annex 4 names legal advocacy and notarial activity outright. Not available." },
  { code: "69.20", name: "Accounting, bookkeeping and auditing activities; tax consultancy", verdict: "prohibited", category: 4,
    note: "Annex 4 names both auditing and tax consulting expressly. This code is the clearest prohibition of all." },
  { code: "70.21", name: "Public relations and communication activities", verdict: "grey", category: 4,
    note: "PR sits close to advisory work. Execution (running campaigns, writing releases) reads differently from counselling management — but the line is not drawn in the law." },
  { code: "70.22", name: "Business and other management consultancy activities", verdict: "prohibited", category: 4,
    note: "This is management consulting by name. Annex 4 prohibits consulting. If this is your registered code, do not plan on the 1% rate." },
  { code: "71.11", name: "Architectural activities", verdict: "prohibited", category: 4,
    note: "Annex 4 names architectural activity outright. Not available." },
  { code: "71.12", name: "Engineering activities and related technical consultancy", verdict: "grey", category: 4,
    note: "The code bundles engineering work with technical consultancy. Engineering execution and advisory work may be treated differently — confirm which your engagement is." },
  { code: "73.11", name: "Advertising agencies", verdict: "clear",
    note: "Creating and placing advertising is execution, not advice — though a strategy-only engagement moves toward 70.22." },
  { code: "73.12", name: "Media representation", verdict: "clear", note: "Selling advertising space and time." },
  { code: "73.20", name: "Market research and public opinion polling", verdict: "grey", category: 4,
    note: "Research delivered as a report can look like an advisory deliverable. Confirm the classification." },
  { code: "74.10", name: "Specialised design activities", verdict: "clear",
    note: "Graphic, product, interior and UX design. A common and comfortable code for freelancers." },
  { code: "74.20", name: "Photographic activities", verdict: "clear", note: "Photography and videography." },
  { code: "74.30", name: "Translation and interpretation activities", verdict: "clear",
    note: "Translation is a service, not advice." },
  { code: "74.90", name: "Other professional, scientific and technical activities n.e.c.", verdict: "grey", category: 4,
    note: "A residual code. Because it holds whatever does not fit elsewhere, the tax authority will look through it to what you actually do — which may or may not be consulting." },
  { code: "82.11", name: "Combined office administrative service activities", verdict: "clear",
    note: "Administrative support and back-office services." },
  { code: "82.99", name: "Other business support service activities n.e.c.", verdict: "grey", category: 4,
    note: "Residual business-support code. As with 74.90, the substance of the work governs." },

  // ------------------------------------------------------------------- Prohibited
  { code: "78.10", name: "Activities of employment placement agencies", verdict: "prohibited", category: 6,
    note: "Annex 4 item 6 prohibits provision of personnel. Recruitment and placement fall squarely inside." },
  { code: "78.20", name: "Temporary employment agency activities", verdict: "prohibited", category: 6,
    note: "Supplying workers to clients is the textbook case of 'provision of personnel'." },
  { code: "78.30", name: "Other human resources provision", verdict: "prohibited", category: 6,
    note: "Provision of personnel — prohibited by Annex 4 item 6." },
  { code: "92.00", name: "Gambling and betting activities", verdict: "prohibited", category: 5,
    note: "Annex 4 item 5 prohibits the gambling business. Also requires a licence, so item 1 applies too." },
  { code: "86.21", name: "General medical practice activities", verdict: "prohibited", category: 4,
    note: "Medical activity is named in Annex 4 and is also licensed." },
  { code: "86.22", name: "Specialist medical practice activities", verdict: "prohibited", category: 4,
    note: "Medical activity — prohibited, and licensed." },
  { code: "86.23", name: "Dental practice activities", verdict: "prohibited", category: 4,
    note: "Medical activity — prohibited, and licensed." },
  { code: "86.90", name: "Other human health activities", verdict: "prohibited", category: 4,
    note: "Health activities are named in Annex 4 and generally licensed." },
  { code: "66.12", name: "Security and commodity contracts brokerage", verdict: "prohibited", category: 3,
    note: "Currency and securities dealing engages Annex 4 item 3 (foreign-currency operations) and is licensed." },
  { code: "66.19", name: "Other activities auxiliary to financial services", verdict: "prohibited", category: 3,
    note: "Money changing and similar operations engage item 3, and financial services are licensed." },
  { code: "64.19", name: "Other monetary intermediation", verdict: "prohibited", category: 1,
    note: "Banking and monetary intermediation are licensed activities — Annex 4 item 1." },
  { code: "11.01", name: "Distilling, rectifying and blending of spirits", verdict: "prohibited", category: 7,
    note: "Alcohol is an excisable good. Annex 4 items 2 and 7 both bite." },
  { code: "11.02", name: "Manufacture of wine from grape", verdict: "prohibited", category: 7,
    note: "Excisable goods. Note this is MANUFACTURE — wine tourism services are a different matter and have their own higher threshold." },
  { code: "11.05", name: "Manufacture of beer", verdict: "prohibited", category: 7,
    note: "Excisable goods — prohibited." },
  { code: "12.00", name: "Manufacture of tobacco products", verdict: "prohibited", category: 7,
    note: "Excisable goods — prohibited." },
  { code: "19.20", name: "Manufacture of refined petroleum products", verdict: "prohibited", category: 7,
    note: "Excisable goods — prohibited." },

  // ----------------------------------------------------------- Trade & hospitality
  { code: "47.19", name: "Other retail sale in non-specialised stores", verdict: "clear",
    note: "Retail trade is open to Small Business Status (unlike Micro Business Status, which excludes trade)." },
  { code: "47.91", name: "Retail sale via mail order houses or via Internet", verdict: "clear",
    note: "E-commerce. Watch the VAT registration threshold as turnover grows." },
  { code: "46.19", name: "Agents involved in the sale of a variety of goods", verdict: "clear",
    note: "Commission agency and wholesale intermediation." },
  { code: "55.10", name: "Hotels and similar accommodation", verdict: "clear",
    note: "Check whether your specific operation needs a permit — Annex 4 item 1 would then apply.",
    incomeWarning: "If you are in substance letting property rather than running an accommodation business, the income may be treated as rent — which is taxed under ordinary rules and does not benefit from the 1% rate." },
  { code: "56.10", name: "Restaurants and mobile food service activities", verdict: "clear",
    note: "Food service. Confirm any permit requirements applicable to your premises." },
  { code: "56.30", name: "Beverage serving activities", verdict: "clear",
    note: "Serving beverages is not manufacturing excisable goods. Confirm permit requirements." },

  // ---------------------------------------------------------- Education & creative
  { code: "85.59", name: "Other education n.e.c.", verdict: "clear",
    note: "Tutoring, language teaching, professional training. Confirm whether any licensing applies to your format." },
  { code: "90.03", name: "Artistic creation", verdict: "clear",
    note: "Independent artists and writers.",
    incomeWarning: "Income received as ROYALTIES is taxed under ordinary rules and falls outside the regime — see Annex 5. Fee-for-work income does not." },
  { code: "59.11", name: "Motion picture, video and television programme production", verdict: "clear",
    note: "Production services." },
  { code: "59.20", name: "Sound recording and music publishing activities", verdict: "clear",
    note: "Recording services.",
    incomeWarning: "Publishing income in the form of royalties falls outside the regime (Annex 5)." },

  // ------------------------------------------------------- Construction & property
  { code: "41.20", name: "Construction of residential and non-residential buildings", verdict: "clear",
    note: "Construction itself is not on the Annex 4 list — but read the income warning, which is the real trap here.",
    incomeWarning: "Income from construction, civil-engineering and specialised construction services in group 41.2 is EXCLUDED from the regime where the recipient is an enterprise, organisation or entrepreneurial natural person. Supplying businesses therefore does not get the 1% rate; supplying private individuals is treated differently." },
  { code: "43.39", name: "Other building completion and finishing", verdict: "clear",
    note: "Finishing works. Check whether construction permits apply to your scope." },
  { code: "68.20", name: "Renting and operating of own or leased real estate", verdict: "clear",
    note: "The ACTIVITY is not prohibited — but the income is the problem.",
    incomeWarning: "Income from leasing out property is taxed under ordinary rules and is NOT counted in the small-business regime at all (Annex 5, item 1). Small Business Status gives you nothing here." },
  { code: "68.31", name: "Real estate agencies", verdict: "clear",
    note: "Agency and brokerage commission — distinct from rental income. Confirm any licensing." },

  // -------------------------------------------------------------------- Transport
  { code: "49.32", name: "Taxi operation", verdict: "grey", category: 1,
    note: "Taxi work needs a permit, which normally triggers Annex 4 item 1. But the rule carves out the M1-category taxi permit for the capital — so the answer depends on your permit and city. Confirm with the Revenue Service." },
  { code: "49.41", name: "Freight transport by road", verdict: "grey", category: 1,
    note: "Road haulage can require permits depending on vehicle and cargo. Where a permit is required, item 1 prohibits the status." },
  { code: "53.20", name: "Other postal and courier activities", verdict: "clear",
    note: "Courier and delivery services." },

  // ------------------------------------------------------------------ Repair, misc
  { code: "95.11", name: "Repair of computers and peripheral equipment", verdict: "clear",
    note: "Repair services." },
  { code: "96.02", name: "Hairdressing and other beauty treatment", verdict: "clear",
    note: "Eligible — but compare [Fixed Taxpayer Status](/en/fixed-taxpayer-status-georgia), which may be cheaper for this trade." },
  { code: "45.20", name: "Maintenance and repair of motor vehicles", verdict: "clear",
    note: "Eligible — but compare Fixed Taxpayer Status, which sets a flat monthly amount per repair place." },
  { code: "01.11", name: "Growing of cereals, leguminous crops and oil seeds", verdict: "clear",
    note: "Agricultural production. Separate agricultural reliefs may be more favourable — check before choosing." },
];
