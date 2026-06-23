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
      // Add more locales here as they launch (e.g. ru, de, fr ...)
      i18n: {
        defaultLocale: 'en',
        locales: { en: 'en' },
      },
    }),
  ],
  build: {
    format: 'directory',
  },
});
