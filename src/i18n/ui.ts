// Lightweight i18n for the multilingual pilot.
//
// Only page-level chrome is translated here (Contents, Sources, breadcrumbs,
// date stamp, FAQ heading, feedback). The global Header/Nav/Footer remain in
// English for now. Article body + FAQ text live in the per-language content
// files under src/content/guides/<lang>/.
//
// To add a language: add it to LANGS, add a UI block below, add a routing page
// src/pages/<lang>/[...slug].astro, and add translated content files.

export type LangCode = 'en' | 'ka' | 'ru' | 'uk' | 'de' | 'fr' | 'he';

export interface LangMeta {
  code: LangCode;
  /** Endonym shown in the language switcher. */
  native: string;
  /** Text direction for <html dir>. */
  dir: 'ltr' | 'rtl';
  /** BCP-47 locale used for date formatting. */
  locale: string;
}

// Display order in the switcher.
export const LANGS: LangMeta[] = [
  { code: 'en', native: 'English', dir: 'ltr', locale: 'en-GB' },
  { code: 'ka', native: 'ქართული', dir: 'ltr', locale: 'ka-GE' },
  { code: 'ru', native: 'Русский', dir: 'ltr', locale: 'ru-RU' },
  { code: 'uk', native: 'Українська', dir: 'ltr', locale: 'uk-UA' },
  { code: 'de', native: 'Deutsch', dir: 'ltr', locale: 'de-DE' },
  { code: 'fr', native: 'Français', dir: 'ltr', locale: 'fr-FR' },
  { code: 'he', native: 'עברית', dir: 'rtl', locale: 'he-IL' },
];

export const LANG_MAP: Record<string, LangMeta> = Object.fromEntries(
  LANGS.map((l) => [l.code, l])
);

export function dirFor(lang: string): 'ltr' | 'rtl' {
  return LANG_MAP[lang]?.dir ?? 'ltr';
}

export function localeFor(lang: string): string {
  return LANG_MAP[lang]?.locale ?? 'en-GB';
}

export interface UIStrings {
  home: string;
  contents: string;
  inThisSection: string;
  faqHeading: string;
  sources: string;
  usefulHeading: string;
  yes: string;
  no: string;
  reviewed: string;
  checked: string;
  language: string;
  categories: Record<string, string>;
}

export const UI: Record<LangCode, UIStrings> = {
  en: {
    home: 'Home',
    contents: 'Contents',
    inThisSection: 'In this section',
    faqHeading: 'Frequently asked questions',
    sources: 'Sources',
    usefulHeading: 'Is this page useful?',
    yes: 'Yes',
    no: 'No',
    reviewed: 'Last reviewed',
    checked: 'Last checked',
    language: 'Language',
    categories: {
      immigration: 'Immigration & Visa',
      work: 'Work & Business',
      tax: 'Taxes',
      students: 'Study in Georgia',
      live: 'Live in Georgia',
      about: 'About',
    },
  },
  ka: {
    home: 'მთავარი',
    contents: 'შინაარსი',
    inThisSection: 'ამ განყოფილებაში',
    faqHeading: 'ხშირად დასმული კითხვები',
    sources: 'წყაროები',
    usefulHeading: 'გამოგადგათ ეს გვერდი?',
    yes: 'დიახ',
    no: 'არა',
    reviewed: 'ბოლო გადახედვა',
    checked: 'ბოლო შემოწმება',
    language: 'ენა',
    categories: {
      immigration: 'იმიგრაცია და ვიზა',
      work: 'სამუშაო და ბიზნესი',
      tax: 'გადასახადები',
      students: 'სწავლა საქართველოში',
      live: 'ცხოვრება საქართველოში',
      about: 'შესახებ',
    },
  },
  ru: {
    home: 'Главная',
    contents: 'Содержание',
    inThisSection: 'В этом разделе',
    faqHeading: 'Часто задаваемые вопросы',
    sources: 'Источники',
    usefulHeading: 'Эта страница была полезна?',
    yes: 'Да',
    no: 'Нет',
    reviewed: 'Последняя проверка редактором',
    checked: 'Последняя автопроверка',
    language: 'Язык',
    categories: {
      immigration: 'Иммиграция и визы',
      work: 'Работа и бизнес',
      tax: 'Налоги',
      students: 'Учёба в Грузии',
      live: 'Жизнь в Грузии',
      about: 'О проекте',
    },
  },
  uk: {
    home: 'Головна',
    contents: 'Зміст',
    inThisSection: 'У цьому розділі',
    faqHeading: 'Часті запитання',
    sources: 'Джерела',
    usefulHeading: 'Чи була ця сторінка корисною?',
    yes: 'Так',
    no: 'Ні',
    reviewed: 'Останній перегляд редактором',
    checked: 'Остання автоперевірка',
    language: 'Мова',
    categories: {
      immigration: 'Імміграція та візи',
      work: 'Робота та бізнес',
      tax: 'Податки',
      students: 'Навчання в Грузії',
      live: 'Життя в Грузії',
      about: 'Про проєкт',
    },
  },
  de: {
    home: 'Startseite',
    contents: 'Inhalt',
    inThisSection: 'In diesem Abschnitt',
    faqHeading: 'Häufig gestellte Fragen',
    sources: 'Quellen',
    usefulHeading: 'War diese Seite hilfreich?',
    yes: 'Ja',
    no: 'Nein',
    reviewed: 'Zuletzt geprüft',
    checked: 'Zuletzt kontrolliert',
    language: 'Sprache',
    categories: {
      immigration: 'Einwanderung & Visum',
      work: 'Arbeit & Unternehmen',
      tax: 'Steuern',
      students: 'Studium in Georgien',
      live: 'Leben in Georgien',
      about: 'Über uns',
    },
  },
  fr: {
    home: 'Accueil',
    contents: 'Sommaire',
    inThisSection: 'Dans cette rubrique',
    faqHeading: 'Questions fréquentes',
    sources: 'Sources',
    usefulHeading: 'Cette page vous a-t-elle été utile ?',
    yes: 'Oui',
    no: 'Non',
    reviewed: 'Dernière révision',
    checked: 'Dernière vérification',
    language: 'Langue',
    categories: {
      immigration: 'Immigration et visa',
      work: 'Travail et entreprise',
      tax: 'Fiscalité',
      students: 'Étudier en Géorgie',
      live: 'Vivre en Géorgie',
      about: 'À propos',
    },
  },
  he: {
    home: 'דף הבית',
    contents: 'תוכן העניינים',
    inThisSection: 'בחלק זה',
    faqHeading: 'שאלות נפוצות',
    sources: 'מקורות',
    usefulHeading: 'האם הדף הזה היה מועיל?',
    yes: 'כן',
    no: 'לא',
    reviewed: 'נבדק לאחרונה',
    checked: 'עודכן לאחרונה',
    language: 'שפה',
    categories: {
      immigration: 'הגירה ואשרות',
      work: 'עבודה ועסקים',
      tax: 'מיסים',
      students: 'לימודים בגאורגיה',
      live: 'חיים בגאורגיה',
      about: 'אודות',
    },
  },
};

export function ui(lang: string): UIStrings {
  return UI[(lang as LangCode)] ?? UI.en;
}
