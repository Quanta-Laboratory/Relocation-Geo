// Daily GA4 -> Telegram report.
//
// Pulls yesterday's traffic from the GA4 Data API and posts a summary to a
// Telegram chat. Written with zero npm dependencies (Node 20 built-ins only):
// a service-account JWT is signed with `node:crypto`, requests use global fetch.
//
// Required environment variables (set as GitHub Actions secrets):
//   GA4_PROPERTY_ID         - numeric GA4 property ID (e.g. 123456789)
//   GA_SERVICE_ACCOUNT_JSON - full JSON key of a Google service account that has
//                             "Viewer" access on the GA4 property
//   TELEGRAM_BOT_TOKEN      - bot token from @BotFather
//   TELEGRAM_CHAT_ID        - target chat/channel ID (or @channelusername)

import crypto from 'node:crypto';

const {
  GA4_PROPERTY_ID,
  GA_SERVICE_ACCOUNT_JSON,
  TELEGRAM_BOT_TOKEN,
  TELEGRAM_CHAT_ID,
} = process.env;

function requireEnv(name, value) {
  if (!value) {
    console.error(`Missing required env var: ${name}`);
    process.exit(1);
  }
}
requireEnv('GA4_PROPERTY_ID', GA4_PROPERTY_ID);
requireEnv('GA_SERVICE_ACCOUNT_JSON', GA_SERVICE_ACCOUNT_JSON);
requireEnv('TELEGRAM_BOT_TOKEN', TELEGRAM_BOT_TOKEN);
requireEnv('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID);

// --- Google auth: sign a JWT and exchange it for an access token ---------
async function getAccessToken() {
  const sa = JSON.parse(GA_SERVICE_ACCOUNT_JSON);
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: 'RS256', typ: 'JWT' };
  const claim = {
    iss: sa.client_email,
    scope: 'https://www.googleapis.com/auth/analytics.readonly',
    aud: 'https://oauth2.googleapis.com/token',
    iat: now,
    exp: now + 3600,
  };
  const enc = (obj) => Buffer.from(JSON.stringify(obj)).toString('base64url');
  const signingInput = `${enc(header)}.${enc(claim)}`;
  const signer = crypto.createSign('RSA-SHA256');
  signer.update(signingInput);
  const signature = signer.sign(sa.private_key).toString('base64url');
  const jwt = `${signingInput}.${signature}`;

  const res = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion: jwt,
    }),
  });
  if (!res.ok) {
    throw new Error(`Token exchange failed: ${res.status} ${await res.text()}`);
  }
  const data = await res.json();
  return data.access_token;
}

// --- GA4 Data API: batch several reports -----------------------------------
// NOTE: batchRunReports allows at most 5 requests per call, so the 8 reports
// below are split across two batches and merged back in order.
async function batchRunReports(token, requests) {
  const res = await fetch(
    `https://analyticsdata.googleapis.com/v1beta/properties/${GA4_PROPERTY_ID}:batchRunReports`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ requests }),
    }
  );
  if (!res.ok) {
    throw new Error(`GA4 API failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

async function runReports(token) {
  const yesterday = [{ startDate: 'yesterday', endDate: 'yesterday' }];
  const requests = [
    // 0: totals
    {
      dateRanges: yesterday,
      metrics: [
        { name: 'sessions' },
        { name: 'activeUsers' },
        { name: 'screenPageViews' },
      ],
    },
    // 1: top pages
    {
      dateRanges: yesterday,
      dimensions: [{ name: 'pagePath' }],
      metrics: [{ name: 'screenPageViews' }],
      orderBys: [{ metric: { metricName: 'screenPageViews' }, desc: true }],
      limit: 10,
    },
    // 2: traffic sources (channel grouping)
    {
      dateRanges: yesterday,
      dimensions: [{ name: 'sessionDefaultChannelGroup' }],
      metrics: [{ name: 'sessions' }],
      orderBys: [{ metric: { metricName: 'sessions' }, desc: true }],
      limit: 10,
    },
    // 3: top countries
    {
      dateRanges: yesterday,
      dimensions: [{ name: 'country' }],
      metrics: [{ name: 'sessions' }],
      orderBys: [{ metric: { metricName: 'sessions' }, desc: true }],
      limit: 7,
    },
    // 4: top cities
    {
      dateRanges: yesterday,
      dimensions: [{ name: 'city' }],
      metrics: [{ name: 'sessions' }],
      orderBys: [{ metric: { metricName: 'sessions' }, desc: true }],
      limit: 7,
    },
    // 5: sessions by hour of day (00–23, local property time)
    {
      dateRanges: yesterday,
      dimensions: [{ name: 'hour' }],
      metrics: [{ name: 'sessions' }],
      orderBys: [{ dimension: { dimensionName: 'hour' } }],
      limit: 24,
    },
    // 6: new vs returning users
    {
      dateRanges: yesterday,
      dimensions: [{ name: 'newVsReturning' }],
      metrics: [{ name: 'activeUsers' }],
      orderBys: [{ metric: { metricName: 'activeUsers' }, desc: true }],
      limit: 5,
    },
    // 7: top landing pages
    {
      dateRanges: yesterday,
      dimensions: [{ name: 'landingPagePlusQueryString' }],
      metrics: [{ name: 'sessions' }],
      orderBys: [{ metric: { metricName: 'sessions' }, desc: true }],
      limit: 10,
    },
  ];

  // Split into chunks of <= 5 requests, run each batch, merge reports in order.
  const chunkSize = 5;
  const batches = [];
  for (let i = 0; i < requests.length; i += chunkSize) {
    batches.push(requests.slice(i, i + chunkSize));
  }
  const results = await Promise.all(
    batches.map((chunk) => batchRunReports(token, chunk))
  );
  const reports = results.flatMap((r) => r.reports || []);

  // 8: AI assistant referrals (custom event ai_referral, broken down by
  // ai_source). Run separately and tolerate failure: the `customEvent:ai_source`
  // dimension only exists once a matching custom dimension is registered in GA4,
  // so until then this query 400s. We don't want that to sink the whole report —
  // on any error we append null and the AI section renders "no data".
  let aiReport = null;
  try {
    const aiBatch = await batchRunReports(token, [
      {
        dateRanges: yesterday,
        dimensions: [{ name: 'customEvent:ai_source' }],
        metrics: [{ name: 'eventCount' }],
        dimensionFilter: {
          filter: {
            fieldName: 'eventName',
            stringFilter: { value: 'ai_referral' },
          },
        },
        orderBys: [{ metric: { metricName: 'eventCount' }, desc: true }],
        limit: 10,
      },
    ]);
    aiReport = (aiBatch.reports && aiBatch.reports[0]) || null;
  } catch (err) {
    console.error('AI referrals query failed (skipping section):', err.message);
  }
  reports.push(aiReport);

  return { reports };
}

// --- Formatting ----------------------------------------------------------
const escapeHtml = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const num = (n) => Number(n || 0).toLocaleString('en-US');

function metricValue(report, index) {
  const row = report?.rows?.[0];
  return row ? row.metricValues[index].value : '0';
}

// Render a "dimension — value" list block with a heading; falls back to "no data".
function listBlock(title, report, { bullet = '•', code = false } = {}) {
  let out = `\n<b>${title}</b>\n`;
  if (report?.rows?.length) {
    report.rows.forEach((r) => {
      const label0 = escapeHtml(r.dimensionValues[0].value || '(not set)');
      const label = code ? `<code>${label0}</code>` : label0;
      const v = num(r.metricValues[0].value);
      out += `${bullet} ${label}: ${v}\n`;
    });
  } else {
    out += `— no data\n`;
  }
  return out;
}

function buildMessage(batch) {
  const [totals, pages, channels, countries, cities, hours, newReturning, landing, ai] =
    batch.reports;

  const d = new Date(Date.now() - 24 * 60 * 60 * 1000);
  const dateStr = d.toISOString().slice(0, 10);

  const sessions = metricValue(totals, 0);
  const users = metricValue(totals, 1);
  const views = metricValue(totals, 2);

  let msg = `📊 <b>Relocation.ge — stats for ${dateStr}</b>\n\n`;
  msg += `👥 Sessions: <b>${num(sessions)}</b>\n`;
  msg += `🧑 Active users: <b>${num(users)}</b>\n`;
  msg += `📄 Page views: <b>${num(views)}</b>\n`;

  // Top pages
  msg += `\n<b>Top pages:</b>\n`;
  if (pages?.rows?.length) {
    pages.rows.forEach((r, i) => {
      const path = escapeHtml(r.dimensionValues[0].value);
      const v = num(r.metricValues[0].value);
      msg += `${i + 1}. <code>${path}</code> — ${v}\n`;
    });
  } else {
    msg += `— no data\n`;
  }

  // Traffic sources
  msg += `\n<b>Traffic sources:</b>\n`;
  if (channels?.rows?.length) {
    channels.rows.forEach((r) => {
      const ch = escapeHtml(r.dimensionValues[0].value);
      const v = num(r.metricValues[0].value);
      msg += `• ${ch}: ${v}\n`;
    });
  } else {
    msg += `— no data\n`;
  }

  // Geography
  msg += listBlock('🌍 Top countries:', countries);
  msg += listBlock('🏙 Top cities:', cities);

  // Landing pages
  msg += listBlock('🛬 Top landing pages:', landing, { code: true });

  // New vs returning users
  msg += listBlock('🔁 New vs returning (users):', newReturning);

  // Busiest hours of day (sort by sessions desc, show top 6; hour is "00".."23")
  msg += `\n<b>⏰ Busiest hours (by sessions):</b>\n`;
  if (hours?.rows?.length) {
    const top = [...hours.rows]
      .sort(
        (a, b) =>
          Number(b.metricValues[0].value) - Number(a.metricValues[0].value)
      )
      .slice(0, 6);
    top.forEach((r) => {
      const h = String(r.dimensionValues[0].value).padStart(2, '0');
      const v = num(r.metricValues[0].value);
      msg += `• ${h}:00 — ${v}\n`;
    });
  } else {
    msg += `— no data\n`;
  }

  // AI assistant referrals
  msg += `\n<b>🤖 AI referrals:</b>\n`;
  const aiRows = (ai?.rows || []).filter(
    (r) => r.dimensionValues[0].value && r.dimensionValues[0].value !== '(not set)'
  );
  if (aiRows.length) {
    const aiTotal = aiRows.reduce((s, r) => s + Number(r.metricValues[0].value || 0), 0);
    msg += `Total: <b>${num(aiTotal)}</b>\n`;
    aiRows.forEach((r) => {
      const src = escapeHtml(r.dimensionValues[0].value);
      const v = num(r.metricValues[0].value);
      msg += `• ${src}: ${v}\n`;
    });
  } else {
    msg += `— no AI-referred visits\n`;
  }

  return msg;
}

// --- Telegram ------------------------------------------------------------
async function sendTelegram(text) {
  const res = await fetch(
    `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: TELEGRAM_CHAT_ID,
        text,
        parse_mode: 'HTML',
        disable_web_page_preview: true,
      }),
    }
  );
  if (!res.ok) {
    throw new Error(`Telegram send failed: ${res.status} ${await res.text()}`);
  }
}

// --- Main ----------------------------------------------------------------
try {
  const token = await getAccessToken();
  const batch = await runReports(token);
  const message = buildMessage(batch);
  await sendTelegram(message);
  console.log('Report sent to Telegram.');
} catch (err) {
  console.error(err);
  process.exit(1);
}
