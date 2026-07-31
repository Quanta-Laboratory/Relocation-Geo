#!/usr/bin/env node
/**
 * Aggregate public EV charging stations in Georgia from open, reusable sources
 * and write a normalized snapshot to public/data/ev-charging-stations.json.
 *
 * Sources (both open data, attribution required):
 *   - Open Charge Map   https://openchargemap.org  (CC BY-SA 4.0-style terms; needs a free API key)
 *   - OpenStreetMap     https://www.openstreetmap.org  via Overpass API (ODbL)
 *
 * Design goals:
 *   - Deterministic output (stable sort + rounded coords) so a git diff is
 *     small and reviewable — this file feeds a manual PR-review gate, it is not
 *     auto-merged.
 *   - Never invent data. If a source is unreachable we skip it and keep the
 *     other; if both fail the previous snapshot is left untouched.
 *
 * Usage:
 *   OCM_API_KEY=xxxxx node scripts/fetch-ev-stations.mjs
 * (OCM_API_KEY is optional — without it, only OpenStreetMap is used.)
 */

import { writeFile, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_PATH = resolve(__dirname, '../public/data/ev-charging-stations.json');
const EMOTORS_PATH = resolve(__dirname, '../src/data/ev-stations-emotors.json');

const OCM_API_KEY = process.env.OCM_API_KEY || '';
const COORD_PRECISION = 4; // ~11 m — used only for de-duplication keys

/* ------------------------------- helpers -------------------------------- */

const round = (n) => Number(n).toFixed(COORD_PRECISION);
const dedupeKey = (lat, lng) => `${round(lat)},${round(lng)}`;

function normalizeConnector(raw) {
  if (!raw) return null;
  const s = String(raw).toLowerCase();
  if (s.includes('ccs') || s.includes('combo') || s.includes('type2_combo')) return 'CCS2';
  if (s.includes('chademo')) return 'CHAdeMO';
  if (s.includes('type 2') || s === 'type2' || s.includes('mennekes')) return 'Type 2';
  if (s.includes('type 1') || s === 'type1' || s.includes('j1772')) return 'Type 1';
  if (s.includes('gb/t') || s.includes('gbt')) return 'GB/T';
  if (s.includes('tesla') || s.includes('nacs')) return 'Tesla/NACS';
  if (s.includes('domestic') || s.includes('schuko') || s.includes('household')) return 'Domestic socket';
  return null;
}

function classifyCurrent(connectors, powerKw) {
  if (connectors.includes('CCS2') || connectors.includes('CHAdeMO') || connectors.includes('GB/T')) return 'DC';
  if (powerKw && powerKw >= 43) return 'DC';
  if (connectors.length) return 'AC';
  return 'unknown';
}

async function fetchJson(url, opts = {}) {
  const res = await fetch(url, { headers: { 'User-Agent': 'relocation.ge EV map (open data)' }, ...opts });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url.split('?')[0]}`);
  return res.json();
}

/* ------------------------------ Open Charge Map ------------------------- */

async function fromOpenChargeMap() {
  if (!OCM_API_KEY) {
    console.warn('! OCM_API_KEY not set — skipping Open Charge Map, using OpenStreetMap only.');
    return [];
  }
  const url =
    'https://api.openchargemap.io/v3/poi/?output=json&countrycode=GE' +
    `&maxresults=10000&compact=false&verbose=false&key=${encodeURIComponent(OCM_API_KEY)}`;
  const data = await fetchJson(url);
  const out = [];
  for (const poi of data) {
    const a = poi.AddressInfo;
    if (!a || a.Latitude == null || a.Longitude == null) continue;
    const connections = Array.isArray(poi.Connections) ? poi.Connections : [];
    const connectors = [
      ...new Set(
        connections
          .map((c) => normalizeConnector(c.ConnectionType && c.ConnectionType.Title))
          .filter(Boolean),
      ),
    ];
    const powerKw = connections.reduce((m, c) => Math.max(m, Number(c.PowerKW) || 0), 0) || null;
    const currentTitles = connections
      .map((c) => (c.CurrentType && c.CurrentType.Title) || '')
      .join(' ')
      .toUpperCase();
    let current = classifyCurrent(connectors, powerKw);
    if (currentTitles.includes('DC')) current = 'DC';
    else if (currentTitles.includes('AC') && current === 'unknown') current = 'AC';

    out.push({
      id: `ocm-${poi.ID}`,
      name: (a.Title || '').trim() || null,
      lat: Number(a.Latitude),
      lng: Number(a.Longitude),
      operator: (poi.OperatorInfo && poi.OperatorInfo.Title) || null,
      town: (a.Town || '').trim() || null,
      connectors,
      power_kw: powerKw,
      current,
      source: 'Open Charge Map',
      source_url: `https://openchargemap.org/site/poi/details/${poi.ID}`,
    });
  }
  console.log(`  Open Charge Map: ${out.length} stations`);
  return out;
}

/* ------------------------------ E-Motors (curated) ---------------------- */

async function fromEmotors() {
  // Operator map captured from https://www.emotors.ge/en/map and stored as a
  // reviewed, curated file. This is the authoritative base layer for Georgia.
  try {
    const stations = JSON.parse(await readFile(EMOTORS_PATH, 'utf8'));
    console.log(`  E-Motors (curated): ${stations.length} stations`);
    return stations;
  } catch (e) {
    console.warn(`  E-Motors curated file not readable: ${e.message}`);
    return [];
  }
}

/* ------------------------------ OpenStreetMap --------------------------- */

async function fromOpenStreetMap() {
  const query = `
    [out:json][timeout:90];
    area["ISO3166-1"="GE"][admin_level=2]->.ge;
    (
      node["amenity"="charging_station"](area.ge);
      way["amenity"="charging_station"](area.ge);
    );
    out center tags;`;
  const endpoints = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
  ];
  let data = null;
  let lastErr = null;
  for (const ep of endpoints) {
    try {
      data = await fetchJson(ep, { method: 'POST', body: 'data=' + encodeURIComponent(query) });
      break;
    } catch (e) {
      lastErr = e;
      console.warn(`  Overpass endpoint failed (${ep.split('/')[2]}): ${e.message}`);
    }
  }
  if (!data) throw lastErr || new Error('All Overpass endpoints failed');

  const out = [];
  for (const el of data.elements || []) {
    const lat = el.lat ?? (el.center && el.center.lat);
    const lng = el.lon ?? (el.center && el.center.lon);
    if (lat == null || lng == null) continue;
    const t = el.tags || {};
    const connectors = [];
    for (const key of Object.keys(t)) {
      if (key.startsWith('socket:')) {
        const c = normalizeConnector(key.replace('socket:', '').replace(/:.*/, ''));
        if (c) connectors.push(c);
      }
    }
    if (t['bicycle'] === undefined && t['socket'] === undefined && !connectors.length) {
      const c = normalizeConnector(t['socket'] || t['connector']);
      if (c) connectors.push(c);
    }
    const uniqConnectors = [...new Set(connectors)];
    const powerKw =
      Number(String(t['charging_station:output'] || t['maxpower'] || '').replace(/[^\d.]/g, '')) || null;
    out.push({
      id: `osm-${el.type}-${el.id}`,
      name: (t.name || t['operator'] || '').trim() || null,
      lat: Number(lat),
      lng: Number(lng),
      operator: (t.operator || '').trim() || null,
      town: (t['addr:city'] || '').trim() || null,
      connectors: uniqConnectors,
      power_kw: powerKw,
      current: classifyCurrent(uniqConnectors, powerKw),
      source: 'OpenStreetMap',
      source_url: `https://www.openstreetmap.org/${el.type}/${el.id}`,
    });
  }
  console.log(`  OpenStreetMap: ${out.length} stations`);
  return out;
}

/* ------------------------------ merge & write --------------------------- */

function mergeSources(lists) {
  // Open Charge Map first so its (usually richer) records win on a coordinate clash.
  const merged = new Map();
  for (const list of lists) {
    for (const s of list) {
      const key = dedupeKey(s.lat, s.lng);
      const existing = merged.get(key);
      if (!existing) {
        merged.set(key, s);
        continue;
      }
      // Keep the first (higher-priority) record but backfill missing fields and
      // union the connector list so nothing verifiable is lost.
      existing.name = existing.name || s.name;
      existing.operator = existing.operator || s.operator;
      existing.town = existing.town || s.town;
      existing.power_kw = existing.power_kw || s.power_kw;
      existing.connectors = [...new Set([...existing.connectors, ...s.connectors])];
      if (existing.current === 'unknown') existing.current = s.current;
      if (!existing.also_listed_in) existing.also_listed_in = [];
      existing.also_listed_in.push({ source: s.source, source_url: s.source_url });
    }
  }
  return [...merged.values()].sort((a, b) => {
    const ta = (a.town || 'zzz').localeCompare(b.town || 'zzz');
    if (ta !== 0) return ta;
    return (a.name || 'zzz').localeCompare(b.name || 'zzz');
  });
}

async function main() {
  console.log('Fetching Georgian EV charging stations…');
  // Order = merge priority. E-Motors (curated operator map) is the base and wins
  // on a coordinate clash; Open Charge Map and OpenStreetMap add coverage on top.
  const sources = [
    { name: 'E-Motors', fn: fromEmotors },
    { name: 'Open Charge Map', fn: fromOpenChargeMap },
    { name: 'OpenStreetMap', fn: fromOpenStreetMap },
  ];
  const results = await Promise.allSettled(sources.map((s) => s.fn()));
  const lists = [];
  const usedSources = [];
  for (const [i, r] of results.entries()) {
    const name = sources[i].name;
    if (r.status === 'fulfilled') {
      lists.push(r.value);
      if (r.value.length) usedSources.push(name);
    } else {
      console.warn(`! ${name} failed: ${r.reason.message}`);
    }
  }

  const stations = mergeSources(lists);

  if (!stations.length) {
    console.error('No stations fetched from any source — leaving the existing snapshot untouched.');
    try {
      await readFile(OUT_PATH); // confirm a prior snapshot exists
      process.exit(2);
    } catch {
      console.error('No prior snapshot exists either; writing an empty (but valid) file.');
    }
  }

  const byCurrent = stations.reduce((m, s) => ((m[s.current] = (m[s.current] || 0) + 1), m), {});
  const payload = {
    meta: {
      generated: new Date().toISOString(),
      sources: usedSources,
      counts: { total: stations.length, by_current: byCurrent },
      attribution: {
        'E-Motors': 'Charger locations from the E-Motors / E-Space public map — https://www.emotors.ge/en/map',
        'Open Charge Map': 'Data © Open Charge Map contributors — https://openchargemap.org',
        OpenStreetMap: 'Data © OpenStreetMap contributors, ODbL — https://www.openstreetmap.org/copyright',
      },
      note:
        'Community-maintained open data. Coverage and accuracy vary; always confirm a station in its operator app before relying on it. Not an official government register.',
    },
    stations,
  };

  await writeFile(OUT_PATH, JSON.stringify(payload, null, 2) + '\n');
  console.log(`Wrote ${stations.length} stations to public/data/ev-charging-stations.json`);
  console.log(`  by current: ${JSON.stringify(byCurrent)}`);
}

main().catch((e) => {
  console.error('Fatal:', e.message);
  process.exit(1);
});
