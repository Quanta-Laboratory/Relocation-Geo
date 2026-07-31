#!/usr/bin/env node
/**
 * Normalize the E-Motors (E-Space) charging map capture into the station schema
 * used by public/data/ev-charging-stations.json, and (re)seed that public file.
 *
 * Source: https://www.emotors.ge/en/map — the operator's own public charger map.
 * We store the raw [name, lat, lng] in scripts/data/emotors-stations-raw.json and
 * derive only what the labels justify (a "Fast Charger"/"Sinexcel" label ⇒ DC).
 * Nothing is invented.
 */
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const RAW = resolve(__dirname, 'data/emotors-stations-raw.json');
const CURATED = resolve(__dirname, '../src/data/ev-stations-emotors.json');
const PUBLIC = resolve(__dirname, '../public/data/ev-charging-stations.json');

const CITIES = ['Tbilisi','Batumi','Kutaisi','Rustavi','Gori','Telavi','Zugdidi','Borjomi','Kazbegi','Khashuri','Zestafoni','Terjola','Samtredia','Abasha','Chkhorotsku','Argveta','Kachreti','Gurjaani','Tsinandali','Kvareli'];

const round = (n) => Math.round(n * 1e6) / 1e6;

function townFrom(name) {
  for (const c of CITIES) if (new RegExp(`\\b${c}\\b`, 'i').test(name)) return c;
  return null;
}
function currentFrom(name) {
  return /fast charger|sinexcel/i.test(name) ? 'DC' : 'unknown';
}

const raw = JSON.parse(await readFile(RAW, 'utf8'));
const stations = raw.stations.map(([name, lat, lng], i) => ({
  id: `emotors-${String(i + 1).padStart(3, '0')}`,
  name,
  lat: round(lat),
  lng: round(lng),
  operator: 'E-Motors (E-Space)',
  town: townFrom(name),
  connectors: [],
  power_kw: null,
  current: currentFrom(name),
  source: 'E-Motors',
  source_url: 'https://www.emotors.ge/en/map',
})).sort((a, b) => (a.town || 'zzz').localeCompare(b.town || 'zzz') || a.name.localeCompare(b.name));

await mkdir(dirname(CURATED), { recursive: true });
await writeFile(CURATED, JSON.stringify(stations, null, 2) + '\n');

// Seed the public file so the map works immediately. The weekly Action then
// merges Open Charge Map + OpenStreetMap on top of this curated base.
const byCurrent = stations.reduce((m, s) => ((m[s.current] = (m[s.current] || 0) + 1), m), {});
const payload = {
  meta: {
    generated: new Date().toISOString(),
    sources: ['E-Motors'],
    counts: { total: stations.length, by_current: byCurrent },
    attribution: {
      'E-Motors': 'Charger locations from the E-Motors / E-Space public map — https://www.emotors.ge/en/map',
      'Open Charge Map': 'Data © Open Charge Map contributors — https://openchargemap.org',
      OpenStreetMap: 'Data © OpenStreetMap contributors, ODbL — https://www.openstreetmap.org/copyright',
    },
    note:
      'Base layer from the E-Motors / E-Space operator map; Open Charge Map + OpenStreetMap are merged in by the weekly refresh. Community/operator data — confirm a station in its app before relying on it. Not an official government register.',
  },
  stations,
};
await writeFile(PUBLIC, JSON.stringify(payload, null, 2) + '\n');
console.log(`Wrote ${stations.length} E-Motors stations → curated + public seed. by_current: ${JSON.stringify(byCurrent)}`);
