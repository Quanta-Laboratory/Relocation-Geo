/**
 * Telegram webhook — the "one tap" behind matsne impact alerts.
 *
 * scripts/matsne_monitor/impact.py opens a PR with the proposed page edits and
 * posts a Telegram message with two buttons:
 *   ✅ Применить  → callback_data "mx:a:<pr>"  → squash-merge the PR
 *   ❌ Отклонить  → callback_data "mx:r:<pr>"  → close the PR
 * Merging to main triggers the normal production deploy (deploy.yml).
 *
 * Security
 *   - Telegram must send X-Telegram-Bot-Api-Secret-Token = TELEGRAM_WEBHOOK_SECRET
 *     (set by setWebhook in .github/workflows/sync-worker-secrets.yml).
 *   - Only callbacks from TELEGRAM_CHAT_ID are honoured; if TELEGRAM_ADMIN_IDS
 *     (comma-separated user ids) is set, only those users may press.
 *   - Only PRs whose head branch starts with "matsne/" can be merged or closed.
 *
 * Secrets (Worker):
 *   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_WEBHOOK_SECRET,
 *   GH_CONTENT_TOKEN — fine-grained PAT on this repo with Contents: RW and
 *   Pull requests: RW (falls back to GH_DISPATCH_TOKEN if that PAT has them).
 *   TELEGRAM_ADMIN_IDS (optional).
 */

const REPO = "Quanta-Laboratory/Relocation-Geo";

export interface TelegramEnv {
  TELEGRAM_BOT_TOKEN?: string;
  TELEGRAM_CHAT_ID?: string;
  TELEGRAM_WEBHOOK_SECRET?: string;
  TELEGRAM_ADMIN_IDS?: string;
  GH_CONTENT_TOKEN?: string;
  GH_DISPATCH_TOKEN?: string;
}

type CallbackQuery = {
  id: string;
  from: { id: number; username?: string; first_name?: string };
  message?: { message_id: number; chat: { id: number } };
  data?: string;
};

async function tg(env: TelegramEnv, method: string, body: unknown): Promise<void> {
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function gh(env: TelegramEnv, method: string, path: string, body?: unknown): Promise<Response> {
  const token = env.GH_CONTENT_TOKEN || env.GH_DISPATCH_TOKEN;
  return fetch(`https://api.github.com/repos/${REPO}${path}`, {
    method,
    headers: {
      authorization: `Bearer ${token}`,
      accept: "application/vnd.github+json",
      "x-github-api-version": "2022-11-28",
      "user-agent": "relocation-ge-telegram",
      ...(body ? { "content-type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
}

function safeEqual(a: string, b: string): boolean {
  if (!a || a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

async function act(env: TelegramEnv, action: "a" | "r", pr: number, who: string): Promise<string> {
  const res = await gh(env, "GET", `/pulls/${pr}`);
  if (!res.ok) return `PR #${pr} не найден (HTTP ${res.status})`;
  const p = (await res.json()) as { state: string; merged: boolean; title: string; head: { ref: string } };
  if (!p.head.ref.startsWith("matsne/")) return "Этот PR не из монитора — действие запрещено";
  if (p.merged) return `Уже применено (PR #${pr})`;
  if (p.state !== "open") return `PR #${pr} уже закрыт`;

  if (action === "a") {
    const m = await gh(env, "PUT", `/pulls/${pr}/merge`, {
      merge_method: "squash",
      commit_title: `${p.title} (#${pr})`,
      commit_message: `Approved in Telegram by ${who}`,
    });
    if (!m.ok) {
      const t = (await m.text()).slice(0, 150);
      return `Не удалось применить (HTTP ${m.status}): ${t}`;
    }
  } else {
    const c = await gh(env, "PATCH", `/pulls/${pr}`, { state: "closed" });
    if (!c.ok) return `Не удалось отклонить (HTTP ${c.status})`;
  }
  await gh(env, "DELETE", `/git/refs/heads/${encodeURIComponent(p.head.ref).replace(/%2F/g, "/")}`);
  return action === "a" ? `✅ Применено — деплой запущен` : `❌ Отклонено`;
}

export async function handleTelegram(request: Request, env: TelegramEnv): Promise<Response> {
  if (request.method !== "POST") return new Response("Method Not Allowed", { status: 405 });
  const secret = request.headers.get("x-telegram-bot-api-secret-token") ?? "";
  if (!env.TELEGRAM_WEBHOOK_SECRET || !safeEqual(secret, env.TELEGRAM_WEBHOOK_SECRET)) {
    return new Response("Unauthorized", { status: 401 });
  }

  let update: { callback_query?: CallbackQuery };
  try {
    update = await request.json();
  } catch {
    return new Response("ok");
  }
  const cq = update.callback_query;
  // Always 200 for anything we don't handle, so Telegram doesn't retry.
  if (!cq?.data || !cq.message) return new Response("ok");

  const m = cq.data.match(/^mx:([ar]):(\d+)$/);
  if (!m) return new Response("ok");

  const chatOk = String(cq.message.chat.id) === String(env.TELEGRAM_CHAT_ID ?? "");
  const admins = (env.TELEGRAM_ADMIN_IDS ?? "").split(",").map((s) => s.trim()).filter(Boolean);
  const userOk = !admins.length || admins.includes(String(cq.from.id));
  if (!chatOk || !userOk) {
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Нет прав", show_alert: true });
    return new Response("ok");
  }

  const pr = Number(m[2]);
  const who = cq.from.username ? `@${cq.from.username}` : cq.from.first_name ?? String(cq.from.id);
  let result: string;
  try {
    result = await act(env, m[1] as "a" | "r", pr, who);
  } catch (e) {
    result = `Ошибка: ${(e as Error).message}`;
  }

  const done = result.startsWith("✅") || result.startsWith("❌") || result.startsWith("Уже") || result.includes("закрыт");
  await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: result.slice(0, 190), show_alert: !done });
  if (done) {
    await tg(env, "editMessageReplyMarkup", {
      chat_id: cq.message.chat.id,
      message_id: cq.message.message_id,
      reply_markup: {
        inline_keyboard: [[{ text: `${result} · ${who}`, url: `https://github.com/${REPO}/pull/${pr}` }]],
      },
    });
  }
  return new Response("ok");
}
