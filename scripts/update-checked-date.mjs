// Updates the `checked:` frontmatter date on every content page to today.
// Run daily by GitHub Actions. Keeps "Last checked" fresh without touching
// the human-set "reviewed" date.
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { join, basename } from 'node:path';

const ROOT = 'src/content/guides';
const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD

// Pages with an unresolved 🔴 legal change (src/data/pending-updates.json,
// maintained by the matsne monitor and the Telegram edit flow) keep their old
// `checked:` date until the change is published or dismissed — we don't claim a
// page is "checked today" while a known update is pending.
let pending = new Set();
try {
  const data = JSON.parse(await readFile('src/data/pending-updates.json', 'utf8'));
  pending = new Set(Object.values(data.items || {}).flatMap((i) => i.slugs || []));
} catch {}

async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(full)));
    else if (entry.name.endsWith('.md') || entry.name.endsWith('.mdx')) out.push(full);
  }
  return out;
}

let changed = 0, held = 0;
for (const file of await walk(ROOT)) {
  if (pending.has(basename(file).replace(/\.mdx?$/, ''))) { held++; continue; }
  const text = await readFile(file, 'utf8');
  const updated = text.replace(/^checked:\s*.*$/m, `checked: ${today}`);
  if (updated !== text) {
    await writeFile(file, updated, 'utf8');
    changed++;
  }
}
console.log(`Stamped checked: ${today} on ${changed} file(s); held ${held} with a pending update.`);
