/**
 * Telegram review flow for article edits (see scripts/edits/lib.py).
 *
 *   GET  /api/edits/start?src&doc&slugs&exp&sig  → dispatch draft-edit.yml
 *   GET  /edits/<doc>?ref&exp&sig                → review page (before/after diff,
 *                                                   inline editing, publish/reject)
 *   GET  /edits/<doc>?ref&do=publish|reject&…    → confirmation page
 *   POST /edits/<doc>/act {action, ref, exp, sig, changes?} → dispatch apply-edit.yml
 *
 * Every link is HMAC-signed (key derived from ANTHROPIC_API_KEY, shared with
 * GitHub Actions) and expires. The proposal itself is read from the public repo
 * at an exact commit (raw.githubusercontent.com), so nothing is stored here.
 */

export interface EditsEnv {
  ANTHROPIC_API_KEY?: string;
  GH_DISPATCH_TOKEN?: string;
}

const REPO = "Quanta-Laboratory/Relocation-Geo";
const enc = new TextEncoder();

async function hmacKey(env: EditsEnv): Promise<CryptoKey> {
  const raw = await crypto.subtle.digest("SHA-256", enc.encode(`relocation-edits:v1:${env.ANTHROPIC_API_KEY}`));
  return crypto.subtle.importKey("raw", raw, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
}

async function sign(env: EditsEnv, parts: (string | number)[], exp: number): Promise<string> {
  const mac = await crypto.subtle.sign("HMAC", await hmacKey(env), enc.encode([...parts, exp].join(":")));
  return [...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 40);
}

async function verify(env: EditsEnv, parts: (string | number)[], exp: string | null, sig: string | null) {
  const e = Number(exp);
  if (!env.ANTHROPIC_API_KEY || !sig || !Number.isFinite(e) || e < Date.now() / 1000) return false;
  const want = await sign(env, parts, e);
  if (want.length !== sig.length) return false;
  let diff = 0;
  for (let i = 0; i < want.length; i++) diff |= want.charCodeAt(i) ^ sig.charCodeAt(i);
  return diff === 0;
}

async function dispatch(env: EditsEnv, workflow: string, inputs: Record<string, string>) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${env.GH_DISPATCH_TOKEN}`,
      accept: "application/vnd.github+json",
      "x-github-api-version": "2022-11-28",
      "user-agent": "relocation-ge-edits",
      "content-type": "application/json",
    },
    body: JSON.stringify({ ref: "main", inputs }),
  });
  if (r.status !== 204) throw new Error(`GitHub dispatch ${r.status}`);
}

const esc = (s: unknown) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

function page(title: string, body: string, status = 200): Response {
  return new Response(
    `<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>${esc(title)}</title><style>${CSS}</style></head>
<body><main>${body}</main></body></html>`,
    {
      status,
      headers: {
        "content-type": "text/html; charset=utf-8",
        "cache-control": "no-store",
        "x-robots-tag": "noindex, nofollow",
        "referrer-policy": "no-referrer",
      },
    },
  );
}

const msgPage = (title: string, text: string, status = 200) =>
  page(title, `<h1>${esc(title)}</h1><p>${text}</p>`, status);

export async function handleEdits(request: Request, env: EditsEnv): Promise<Response | null> {
  const url = new URL(request.url);
  const p = url.searchParams;

  // ---- start drafting -------------------------------------------------------
  if (url.pathname === "/api/edits/start") {
    const src = p.get("src") || "matsne";
    const doc = (p.get("doc") || "").replace(/[^0-9A-Za-z-]/g, "");
    const slugs = (p.get("slugs") || "").replace(/[^a-z0-9,-]/g, "");
    if (!doc || !(await verify(env, ["start", src, doc, slugs], p.get("exp"), p.get("sig"))))
      return msgPage("Ссылка недействительна", "Ссылка устарела или повреждена.", 403);
    try {
      await dispatch(env, "draft-edit.yml", { doc_id: doc, slugs, source: src });
    } catch (e) {
      return msgPage("Не удалось запустить", esc((e as Error).message), 502);
    }
    return msgPage(
      "✍️ Готовлю правку",
      `Claude читает документ ${esc(doc)} и ${slugs ? "статьи: " + esc(slugs.replace(/,/g, ", ")) : "готовит черновик новой статьи"}. ` +
        "Через 3–5 минут в Telegram придёт сообщение с кнопками «Посмотреть», «Опубликовать» и «Отклонить». Эту страницу можно закрыть.",
    );
  }

  // ---- "no change needed" for a 🔴 alert (lifts the pending banner) ------------
  if (url.pathname === "/api/edits/dismiss") {
    const doc = (p.get("doc") || "").replace(/[^0-9A-Za-z-]/g, "");
    if (!doc || !(await verify(env, ["dismiss", doc], p.get("exp"), p.get("sig"))))
      return msgPage("Ссылка недействительна", "Ссылка устарела или повреждена.", 403);
    return page(
      "Не требует изменений",
      `<h1>✅ Не требует изменений</h1><p>Документ ${esc(doc)} не меняет статьи сайта. Пометка «Готовится обновление» будет снята, дата проверки снова начнёт обновляться.</p>
<button class="btn pub" id="go">Подтвердить</button><p id="st"></p>
<script>const T=${JSON.stringify({ action: "dismiss", exp: Number(p.get("exp")), sig: p.get("sig") })};
document.getElementById('go').onclick=async function(){this.disabled=true;const st=document.getElementById('st');st.textContent='Отправляю…';
const r=await fetch('/edits/${doc}/act',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(T)});
st.textContent=r.ok?'Готово. Подтверждение придёт в Telegram.':'Ошибка: '+((await r.json().catch(()=>({}))).error||r.status);};</script>`,
    );
  }

  const m = url.pathname.match(/^\/edits\/([0-9A-Za-z-]+)(\/act)?\/?$/);
  if (!m) return null;
  const doc = m[1];

  // ---- actions (POST from the review / confirmation page) -------------------
  if (m[2]) {
    if (request.method !== "POST") return new Response("method not allowed", { status: 405 });
    let b: any;
    try {
      b = await request.json();
    } catch {
      return Response.json({ ok: false, error: "bad_request" }, { status: 400 });
    }
    const action = String(b.action || "");
    const ref = String(b.ref || "");
    if (action === "dismiss") {
      if (!(await verify(env, ["dismiss", doc], String(b.exp), String(b.sig))))
        return Response.json({ ok: false, error: "forbidden" }, { status: 403 });
    } else {
      if (!["publish", "reject", "update"].includes(action) || !/^[0-9a-f]{40}$/.test(ref))
        return Response.json({ ok: false, error: "bad_request" }, { status: 400 });
      if (!(await verify(env, [action, doc, ref], String(b.exp), String(b.sig))))
        return Response.json({ ok: false, error: "forbidden" }, { status: 403 });
    }
    const changes = action === "update" ? JSON.stringify(b.changes || []) : "[]";
    if (changes.length > 60000) return Response.json({ ok: false, error: "too_large" }, { status: 413 });
    try {
      await dispatch(env, "apply-edit.yml", { doc_id: doc, action, changes });
    } catch (e) {
      return Response.json({ ok: false, error: (e as Error).message }, { status: 502 });
    }
    return Response.json({ ok: true });
  }

  const ref = p.get("ref") || "";
  if (!/^[0-9a-f]{40}$/.test(ref)) return msgPage("Ссылка недействительна", "Нет версии правки.", 400);
  const exp = Number(p.get("exp"));

  // ---- confirmation page for publish / reject buttons -----------------------
  const doAction = p.get("do");
  if (doAction) {
    if (!["publish", "reject"].includes(doAction) || !(await verify(env, [doAction, doc, ref], p.get("exp"), p.get("sig"))))
      return msgPage("Ссылка недействительна", "Ссылка устарела или повреждена.", 403);
    const label = doAction === "publish" ? "✅ Опубликовать правку" : "❌ Отклонить правку";
    return page(
      label,
      `<h1>${label}</h1><p>Документ ${esc(doc)}. ${doAction === "publish" ? "Изменения появятся на сайте через 2–3 минуты." : "Сайт не изменится."}</p>
<button class="btn ${doAction === "publish" ? "pub" : "rej"}" id="go">${label}</button><p id="st"></p>
<script>const T=${JSON.stringify({ action: doAction, ref, exp, sig: p.get("sig") })};
document.getElementById('go').onclick=async function(){this.disabled=true;const st=document.getElementById('st');st.textContent='Отправляю…';
const r=await fetch(location.pathname.replace(/\\/?$/,'/act'),{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(T)});
st.textContent=r.ok?'Готово. Подтверждение придёт в Telegram.':'Ошибка: '+((await r.json().catch(()=>({}))).error||r.status);};</script>`,
    );
  }

  // ---- review page ----------------------------------------------------------
  if (!(await verify(env, ["view", doc, ref], p.get("exp"), p.get("sig"))))
    return msgPage("Ссылка недействительна", "Ссылка устарела или повреждена.", 403);
  const raw = await fetch(`https://raw.githubusercontent.com/${REPO}/${ref}/.edits/proposal.json`, {
    cf: { cacheTtl: 300 },
  } as RequestInit);
  if (!raw.ok) return msgPage("Правка не найдена", "Возможно, она уже опубликована или отклонена.", 404);
  const prop: any = await raw.json();
  const tokens = {
    ref,
    exp,
    publish: await sign(env, ["publish", doc, ref], exp),
    reject: await sign(env, ["reject", doc, ref], exp),
    update: await sign(env, ["update", doc, ref], exp),
  };
  const d = prop.doc || {};
  const body = `
<header><div class="kicker">Правка статьи · документ ${esc(doc)}${prop.kind === "new" ? " · <b>новая статья</b>" : ""}</div>
<h1>${esc(d.title_en || "Изменение законодательства")}</h1>
<p class="reason">${esc(prop.reason_ru)}</p>
<pre class="summary">${esc(prop.summary_ru)}</pre>
<p class="links"><a href="${esc(d.link)}" target="_blank" rel="noopener">Документ на matsne ↗</a>${
    prop.preview_url ? ` · <a href="${esc(prop.preview_url)}" target="_blank" rel="noopener">Страница целиком (предпросмотр) ↗</a>` : ""
  }</p>
${prop.problems?.length ? `<p class="warn">⚠️ ${esc(prop.problems.join("; "))}</p>` : ""}
</header>
<div id="files"></div>
<div class="bar"><button class="btn rej" id="reject">❌ Отклонить</button><button class="btn sec" id="save" hidden>💾 Сохранить мои правки</button><button class="btn pub" id="publish">✅ Опубликовать</button></div>
<p id="st" class="st"></p>
<script>window.PROP=${JSON.stringify(prop).replace(/</g, "\\u003c")};window.TOK=${JSON.stringify(tokens)};</script>
<script>${CLIENT}</script>`;
  return page(`Правка: ${d.title_en || doc}`, body);
}

const CSS = `
*{box-sizing:border-box}body{margin:0;font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f3f2f1;color:#0b0c0c}
main{max-width:860px;margin:0 auto;padding:16px 14px 110px}h1{font-size:22px;line-height:1.25;margin:6px 0 10px}
header{background:#fff;border-radius:12px;padding:16px;margin-bottom:14px;border:1px solid #d8d8d8}
.kicker{font-size:13px;color:#505a5f}.reason{margin:6px 0}.summary{white-space:pre-wrap;font:inherit;background:#f8f8f8;border-left:4px solid #1d70b8;padding:8px 10px;margin:8px 0}
.links a{color:#1d70b8}.warn{color:#b35900}
.file{background:#fff;border-radius:12px;border:1px solid #d8d8d8;margin-bottom:14px;overflow:hidden}
.file h2{font-size:16px;margin:0;padding:10px 14px;background:#12436d;color:#fff}.file h2 a{color:#cfe3f5}
.para{padding:8px 14px;border-top:1px solid #eee;white-space:pre-wrap;word-wrap:break-word}
.same{color:#505a5f;font-size:13px;background:#fafafa;text-align:center}
del{background:#fde2e1;color:#7a1111;text-decoration:line-through}ins{background:#d7f5dd;color:#0b5a1e;text-decoration:none}
.old{background:#fff6f6}.new{background:#f4fff6}.tag{font-size:11px;font-weight:700;color:#505a5f;margin-bottom:2px}
.edit{float:right;font-size:13px;border:1px solid #1d70b8;color:#1d70b8;background:#fff;border-radius:6px;padding:2px 8px;cursor:pointer}
textarea{width:100%;min-height:120px;font:15px/1.45 ui-monospace,Menlo,monospace;border:2px solid #1d70b8;border-radius:8px;padding:8px}
.bar{position:fixed;left:0;right:0;bottom:0;display:flex;gap:8px;justify-content:center;padding:10px;background:#fff;border-top:1px solid #ccc}
.btn{border:0;border-radius:8px;padding:12px 16px;font-weight:700;font-size:15px;cursor:pointer;color:#fff}
.pub{background:#00703c}.rej{background:#d4351c}.sec{background:#1d70b8}.btn:disabled{opacity:.5}
.st{text-align:center;font-weight:600}
@media (prefers-color-scheme:dark){body{background:#111315;color:#e9ebed}header,.file,.bar{background:#1b1d1f;border-color:#3a3f44}
.summary{background:#24282c}.same{background:#1f2225;color:#b1b4b6}.old{background:#2a1c1c}.new{background:#1b2a1f}del{background:#5c1f1f;color:#ffd6d6}ins{background:#1f4d2b;color:#d6ffe0}.para{border-color:#2c3034}}`;

// Client-side: paragraph diff with word-level highlighting and inline editing.
const CLIENT = `
(function(){
const P=window.PROP,T=window.TOK,files=document.getElementById('files'),st=document.getElementById('st');
const edits=[];const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const paras=t=>String(t||'').split(/\\n{2,}/);
function lcs(a,b){const n=a.length,m=b.length,d=Array.from({length:n+1},()=>new Int32Array(m+1));
 for(let i=n-1;i>=0;i--)for(let j=m-1;j>=0;j--)d[i][j]=a[i]===b[j]?d[i+1][j+1]+1:Math.max(d[i+1][j],d[i][j+1]);
 const ops=[];let i=0,j=0;while(i<n&&j<m){if(a[i]===b[j]){ops.push(['=',a[i]]);i++;j++}else if(d[i+1][j]>=d[i][j+1])ops.push(['-',a[i++]]);else ops.push(['+',b[j++]]);}
 while(i<n)ops.push(['-',a[i++]]);while(j<m)ops.push(['+',b[j++]]);return ops;}
function words(a,b){const A=a.split(/(\\s+)/),B=b.split(/(\\s+)/);if(A.length*B.length>400000)return['<del>'+esc(a)+'</del>','<ins>'+esc(b)+'</ins>'];
 let o='',n='';for(const [k,w] of lcs(A,B)){if(k==='=') {o+=esc(w);n+=esc(w);}else if(k==='-')o+='<del>'+esc(w)+'</del>';else n+='<ins>'+esc(w)+'</ins>';}return[o,n];}
function div(cls,html){const d=document.createElement('div');d.className='para '+cls;d.innerHTML=html;return d;}
for(const f of P.files){
 const box=document.createElement('section');box.className='file';
 const url='https://relocation.ge/'+f.lang+'/'+f.slug+'/';
 box.innerHTML='<h2>'+(f.new?'🆕 ':'')+esc(f.slug)+' · '+f.lang.toUpperCase()+(f.new?'':' · <a href="'+url+'" target="_blank" rel="noopener">текущая версия ↗</a>')+'</h2>';
 const ops=lcs(paras(f.before),paras(f.after));let same=0;
 const flush=()=>{if(same){box.appendChild(div('same','… без изменений: '+same+' абз.'));same=0;}};
 for(let k=0;k<ops.length;k++){const [op,t]=ops[k];
  if(op==='='){same++;continue;}flush();
  if(op==='-'&&ops[k+1]&&ops[k+1][0]==='+'){const [o,n]=words(t,ops[k+1][1]);
   box.appendChild(div('old','<div class="tag">БЫЛО</div>'+o));box.appendChild(editable(f,ops[k+1][1],n));k++;}
  else if(op==='-')box.appendChild(div('old','<div class="tag">УДАЛЕНО</div><del>'+esc(t)+'</del>'));
  else box.appendChild(editable(f,t,'<ins>'+esc(t)+'</ins>'));}
 flush();files.appendChild(box);}
function editable(f,text,html){const d=div('new','<button class="edit">✏️ Править</button><div class="tag">СТАНЕТ</div><div class="v">'+html+'</div>');
 d.querySelector('.edit').onclick=function(){if(d.querySelector('textarea'))return;const ta=document.createElement('textarea');ta.value=text;
  d.querySelector('.v').replaceWith(ta);ta.focus();this.remove();
  const rec={path:f.path,find:text,replace:text};edits.push(rec);ta.oninput=()=>{rec.replace=ta.value;document.getElementById('save').hidden=false;};};
 return d;}
async function act(action,body){st.textContent='Отправляю…';for(const b of document.querySelectorAll('.btn'))b.disabled=true;
 const r=await fetch(location.pathname.replace(/\\/?$/,'/act'),{method:'POST',headers:{'content-type':'application/json'},
  body:JSON.stringify(Object.assign({action,ref:T.ref,exp:T.exp,sig:T[action]},body||{}))});
 const j=await r.json().catch(()=>({}));
 st.textContent=r.ok?({publish:'✅ Публикую. Подтверждение придёт в Telegram, сайт обновится через 2–3 минуты.',reject:'❌ Правка отклонена.',update:'💾 Сохраняю. Обновлённая правка с новыми кнопками придёт в Telegram через 3–5 минут.'}[action]):'Ошибка: '+(j.error||r.status);
 if(!r.ok)for(const b of document.querySelectorAll('.btn'))b.disabled=false;}
document.getElementById('publish').onclick=()=>{const ch=edits.filter(e=>e.replace!==e.find);
 if(ch.length){if(confirm('Есть несохранённые правки. Сохранить их перед публикацией?'))return act('update',{changes:ch});}
 if(confirm('Опубликовать изменения на сайте?'))act('publish');};
document.getElementById('reject').onclick=()=>{if(confirm('Отклонить правку? Сайт не изменится.'))act('reject');};
document.getElementById('save').onclick=()=>{const ch=edits.filter(e=>e.replace!==e.find);if(ch.length)act('update',{changes:ch});};
})();`;
