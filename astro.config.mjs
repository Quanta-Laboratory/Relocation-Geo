// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// IMPORTANT: set this to the production domain before launch.
export const SITE = 'https://relocation.ge';

export default defineConfig({
  site: SITE,
  trailingSlash: 'ignore',
  redirects: {
    '/': '/en/',
  },
  integrations: [
    sitemap({
      // Every locale that has at least one translated page. The sitemap emits
      // hreflang alternates from this, so a locale missing here is invisible to
      // search engines even when the page exists.
      i18n: {
        defaultLocale: 'en',
        locales: {
          en: 'en',
          ka: 'ka',
          ru: 'ru',
          uk: 'uk',
          de: 'de',
          fr: 'fr',
          he: 'he',
        },
      },
    }),
  ],
  build: {
    format: 'directory',
  },
});
