/**
 * Resolve Obsidian-style wiki links in guide markdown.
 *
 * Content is edited in Obsidian, whose link picker always emits `[[slug]]`
 * rather than a markdown link. Astro's markdown parser has no notion of that
 * syntax, so the brackets were being printed to the page as literal text and
 * the link was silently lost. Rather than asking editors to remember to type
 * markdown links by hand, we translate the syntax at build time.
 *
 * Supported forms:
 *   [[small-business-status-georgia]]        -> same language as the current file
 *   [[en/right-to-work-georgia]]             -> explicit language
 *   [[en/right-to-work-georgia|custom text]] -> explicit link text
 *
 * When no link text is given we use the target page's own `title` from its
 * frontmatter, so the prose reads properly instead of showing a raw slug.
 *
 * A wiki link pointing at a page that does not exist is a content bug, not a
 * rendering bug: we fail the build rather than emit a dead link.
 */
import fs from 'node:fs';
import path from 'node:path';

const GUIDES_DIR = path.resolve('src/content/guides');
const LANGS = ['en', 'ka', 'ru', 'uk', 'de', 'fr', 'he'];
const WIKILINK = /\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]/g;

/** slug -> { lang -> title }, built once per build from the guide frontmatter. */
function buildTitleIndex() {
  const index = new Map();
  for (const lang of LANGS) {
    const dir = path.join(GUIDES_DIR, lang);
    if (!fs.existsSync(dir)) continue;
    for (const file of fs.readdirSync(dir)) {
      if (!file.endsWith('.md')) continue;
      const slug = file.replace(/\.md$/, '');
      const raw = fs.readFileSync(path.join(dir, file), 'utf8');
      // Only the frontmatter block, and only its top-level `title:` key.
      const fm = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/);
      const title = fm?.[1].match(/^title:\s*(.+)$/m)?.[1].trim().replace(/^["']|["']$/g, '');
      if (!index.has(slug)) index.set(slug, {});
      index.get(slug)[lang] = title || slug;
    }
  }
  return index;
}

let titleIndex;

export default function remarkWikilink() {
  return (tree, file) => {
    titleIndex ??= buildTitleIndex();

    const filePath = file.history?.[0] ?? file.path ?? '';
    const fileLang = LANGS.find((l) => filePath.includes(`${path.sep}guides${path.sep}${l}${path.sep}`)) ?? 'en';

    visitText(tree, (node, parent, i) => {
      if (!node.value.includes('[[')) return;

      const children = [];
      let last = 0;
      for (const m of node.value.matchAll(WIKILINK)) {
        const [full, rawTarget, rawLabel] = m;

        // `en/slug` or bare `slug`
        const parts = rawTarget.trim().split('/').filter(Boolean);
        const lang = LANGS.includes(parts[0]) ? parts.shift() : fileLang;
        const slug = parts.join('/').replace(/\.md$/, '');

        const langs = titleIndex.get(slug);
        if (!langs) {
          throw new Error(
            `[remark-wikilink] ${path.relative(process.cwd(), filePath)}: ` +
              `wiki link [[${rawTarget}]] points at a guide that does not exist ` +
              `(looked for src/content/guides/*/${slug}.md).`
          );
        }
        // Fall back to English if the target has not been translated yet.
        const targetLang = langs[lang] ? lang : 'en';
        const label = rawLabel?.trim() || langs[targetLang];

        if (m.index > last) {
          children.push({ type: 'text', value: node.value.slice(last, m.index) });
        }
        children.push({
          type: 'link',
          url: `/${targetLang}/${slug}`,
          children: [{ type: 'text', value: label }],
        });
        last = m.index + full.length;
      }
      if (!children.length) return;

      if (last < node.value.length) {
        children.push({ type: 'text', value: node.value.slice(last) });
      }
      parent.children.splice(i, 1, ...children);
      return i + children.length;
    });
  };
}

/** Minimal text-node walker: avoids adding unist-util-visit as a direct dep. */
function visitText(node, fn, parent = null, index = 0) {
  if (node.type === 'text' && parent) {
    const next = fn(node, parent, index);
    if (typeof next === 'number') return next;
    return index + 1;
  }
  // Never rewrite inside code, or inside an existing link's text.
  if (node.type === 'code' || node.type === 'inlineCode' || node.type === 'link') {
    return index + 1;
  }
  if (Array.isArray(node.children)) {
    let i = 0;
    while (i < node.children.length) {
      i = visitText(node.children[i], fn, node, i);
    }
  }
  return index + 1;
}
