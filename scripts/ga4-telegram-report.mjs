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

// --- GA4 Data API: batch several reports in one call ---------------------
async function runReports(token) {
  const yesterday = [{ startDate: 'yesterday', endDate: 'yesterday' }];
  const body = {
    requests: [
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
    ],
  };

  const res = await fetch(
    `https://analyticsdata.googleapis.com/v1beta/properties/${GA4_PROPERTY_ID}:batchRunReports`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    }
  );
  if (!res.ok) {
    throw new Error(`GA4 API failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

// --- Formatting ----------------------------------------------------------
const escapeHtml = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const num = (n) => Number(n || 0).toLocaleString('en-US');

function metricValue(report, index) {
  const row = report?.rows?.[0];
  return row ? row.metricValues[index].value : '0';
}

function buildMessage(batch) {
  const [totals, pages, channels] = batch.reports;

  const d = new Date(Date.now() - 24 * 60 * 60 * 1000);
  const dateStr = d.toISOString().slice(0, 10);

  const sessions = metricValue(totals, 0);
  const users = metricValue(totals, 1);
  const views = metricValue(totals, 2);

  let msg = `📊 <b>Relocation.ge — статистика за ${dateStr}</b>\n\n`;
  msg += `👥 Посещения (sessions): <b>${num(sessions)}</b>\n`;
  msg += `🧑 Пользователи (active users): <b>${num(users)}</b>\n`;
  msg += `📄 Просмотры страниц: <b>${num(views)}</b>\n`;

  // Top pages
  msg += `\n<b>Топ страниц:</b>\n`;
  if (pages?.rows?.length) {
    pages.rows.forEach((r, i) => {
      const path = escapeHtml(r.dimensionValues[0].value);
      const v = num(r.metricValues[0].value);
      msg += `${i + 1}. <code>${path}</code> — ${v}\n`;
    });
  } else {
    msg += `— нет данных\n`;
  }

  // Traffic sources
  msg += `\n<b>Источники трафика:</b>\n`;
  if (channels?.rows?.length) {
    channels.rows.forEach((r) => {
      const ch = escapeHtml(r.dimensionValues[0].value);
      const v = num(r.metricValues[0].value);
      msg += `• ${ch}: ${v}\n`;
    });
  } else {
    msg += `— нет данных\n`;
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
