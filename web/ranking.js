// biar-edit · ranking ("5'ten 1'e") editor: quoted clips + our board, comment and credit.
"use strict";
let K = null;   // { name, spec, saveT, problems }

const partsStr = p => (p || []).map(([a, b]) => `${a}-${b}`).join(", ");
const partsParse = s => s.split(",").map(x => x.trim()).filter(Boolean).map(x => x.split("-").map(Number)).filter(p => p.length === 2 && p.every(n => !isNaN(n)));

async function viewRanking(name, d) {
  R = null; K = { name, spec: d.ranking, problems: d.problems, hasOut: d.has_output, outM: d.output_mtime };
  toolbar(`<span class="title">${esc(K.spec.name)}</span><span class="sub">sıralama · 9:16</span><span class="sp"></span>
    <span class="small muted" id="ksave"></span>
    <button class="btn" id="kreveal">${I("ext", 14)} Finder</button>
    <button class="btn" id="kshare">${I("share", 14)} Paylaş</button>
    <button class="btn primary" id="krender">${I("render", 14)} <span id="rlab">Render</span></button>`);
  const v = $("#view"); v.className = "view editor rked";
  v.innerHTML = `<div class="stagewrap"><div class="stage">${K.hasOut ? `<video id="kvid" controls playsinline src="/api/p/${name}/output?m=${K.outM}"></video>` : '<div class="empty">Henüz render yok.<br>Sıraları doldurup Render\'a bas.</div>'}</div></div>
    <div class="insp rk" id="kinsp"></div>`;
  drawRanking();
  $("#krender").onclick = rankRender;
  $("#kreveal").onclick = () => api("/api/reveal", { body: { path: K.spec.output } }).catch(fail);
  $("#kshare").onclick = () => openShare({ project: name, title: K.spec.name, autogen: true });
  watchRankRender(true);
}

function drawRanking() {
  const s = K.spec, el = $("#kinsp");
  const probs = K.problems || [];
  el.innerHTML = `<div class="ihead">Başlık</div><div class="group" style="margin:6px 10px 14px">
      <div class="row stack"><span class="small muted">Üst satır</span><input type="text" data-h="kicker" value="${esc(s.kicker || "")}"></div>
      <div class="row stack"><span class="small muted">Başlık</span><input type="text" data-h="title" value="${esc(s.title || "")}"></div>
      <div class="row stack"><span class="small muted">Kapanış sorusu</span><input type="text" data-o="0" value="${esc((s.outro || [])[0] || "")}"></div></div>
    <div class="ihead">Müzik ve efekt sesleri</div><div class="group" style="margin:6px 10px 14px" id="kmusic"><div class="row"><span class="small muted">yükleniyor…</span></div></div>
    <div id="kprobs" style="padding:0 10px">${probHtml(probs)}</div>
    <div class="ihead">Sıralar <span class="small muted">gösterim sırasıyla, en üstteki ilk çıkar</span></div>
    ${s.items.map((it, i) => `<div class="group rkitem" data-i="${i}" style="margin:6px 10px 12px">
      <div class="row"><b class="rknum ${it.rank === 1 ? "gold" : ""}">#${it.rank}</b><input type="text" data-f="label" placeholder="kısa ad" value="${esc(it.label)}" style="flex:1">
        <button class="btn icon" data-up="${i}" title="Yukarı" ${i ? "" : "disabled"}>${I("up", 13)}</button><button class="btn icon" data-dn="${i}" title="Aşağı" ${i < s.items.length - 1 ? "" : "disabled"}>${I("down", 13)}</button><button class="btn icon" data-del="${i}" title="Sil">${I("trash", 13)}</button></div>
      <div class="row stack"><input type="text" data-f="sub" placeholder="alt satır (ör. Google I/O 2012)" value="${esc(it.sub || "")}"></div>
      <div class="row stack"><textarea data-f="comment" rows="2" placeholder="senin yorumun (videoyu yorum içeriği yapan kısım)">${esc(it.comment || "")}</textarea></div>
      <div class="row stack"><div style="display:flex;gap:6px"><input type="text" data-f="url" placeholder="YouTube / TikTok bağlantısı" value="${esc(it.url || "")}" style="flex:1"><button class="btn" data-find="${i}" title="YouTube'da ara">${I("zoomin", 13)}</button></div></div>
      <div class="row stack"><div style="display:flex;gap:6px"><input type="text" data-f="parts" placeholder="kesit sn: 12.5-20, 31-36" value="${partsStr(it.parts)}" style="flex:1"><button class="btn" data-cue="${i}" title="Altyazıda an bul">${I("wave", 13)}</button></div>
        <span class="small muted">${it.parts && it.parts.length ? (it.parts.reduce((t, [a, b]) => t + b - a, 0)).toFixed(1) + " sn alıntı" : ""}</span></div>
      <div class="row stack"><input type="text" data-f="credit" placeholder="kaynak (ör. Google · YouTube)" value="${esc(it.credit || "")}"></div>
    </div>`).join("")}
    <div style="padding:0 10px 30px;display:flex;gap:8px"><button class="btn" id="kadd">${I("plus", 13)} Sıra ekle</button><button class="btn" id="krenum" title="Üstten alta N..1 numarala">Yeniden numarala</button></div>`;
  el.querySelectorAll("[data-h]").forEach(x => x.oninput = () => { s[x.dataset.h] = x.value; rankDirty(); });
  el.querySelectorAll("[data-o]").forEach(x => x.oninput = () => { s.outro = s.outro || ["", "Yorumlara yaz"]; s.outro[0] = x.value; rankDirty(); });
  el.querySelectorAll(".rkitem").forEach(box => {
    const it = s.items[+box.dataset.i];
    box.querySelectorAll("[data-f]").forEach(x => x.oninput = () => { const f = x.dataset.f; it[f] = f === "parts" ? partsParse(x.value) : x.value; rankDirty(); });
  });
  const move = (i, j) => { const a = s.items; [a[i], a[j]] = [a[j], a[i]]; renumber(); rankDirty(); drawRanking(); };
  el.querySelectorAll("[data-up]").forEach(b => b.onclick = () => move(+b.dataset.up, +b.dataset.up - 1));
  el.querySelectorAll("[data-dn]").forEach(b => b.onclick = () => move(+b.dataset.dn, +b.dataset.dn + 1));
  el.querySelectorAll("[data-del]").forEach(b => b.onclick = () => { if (!confirm("Bu sıra silinsin mi?")) return; s.items.splice(+b.dataset.del, 1); renumber(); rankDirty(); drawRanking(); });
  $("#kadd").onclick = () => { s.items.unshift({ rank: 0, label: "", sub: "", comment: "", credit: "", url: "", parts: [] }); renumber(); rankDirty(); drawRanking(); };
  $("#krenum").onclick = () => { renumber(); rankDirty(); drawRanking(); };
  drawMusic();
  el.querySelectorAll("[data-find]").forEach(b => b.onclick = () => findClip(s.items[+b.dataset.find]));
  el.querySelectorAll("[data-cue]").forEach(b => b.onclick = () => findMoment(s.items[+b.dataset.cue]));
}
function renumber() { const n = K.spec.items.length; K.spec.items.forEach((it, i) => it.rank = n - i); }

function rankDirty() {
  $("#ksave").textContent = "kaydediliyor…"; clearTimeout(K.saveT);
  K.saveT = setTimeout(async () => {
    try { const r = await api(`/api/p/${K.name}`, { body: K.spec }); K.problems = r.problems; $("#ksave").textContent = "kaydedildi"; $("#kprobs").innerHTML = probHtml(r.problems); } catch (e) { fail(e); }
  }, 900);
}
function probHtml(probs) { return (probs || []).map(p => `<div class="prob ${p.level}">${esc(p.msg)}</div>`).join(""); }

async function findClip(it) {
  const q = prompt("YouTube'da ne arayalım?", [it.label, it.sub].filter(Boolean).join(" ")); if (!q) return;
  toast("Aranıyor…");
  try {
    const res = await api(`/api/dl/search?q=${encodeURIComponent(q)}&n=8`);
    const s = sheet("Klip seç", `<div class="group" style="margin:8px 0;max-height:60vh;overflow:auto">${res.map((r, k) => `<div class="row"><div class="lbl"><b>${esc(r.title)}</b>
        <span>${esc(r.channel || "")} · ${r.duration ? fdur(r.duration) : ""}${r.views != null ? " · " + fnum(r.views) + " izlenme" : ""}</span></div>
        <button class="btn icon" data-open="${k}" title="YouTube'da aç">${I("ext", 13)}</button><button class="btn primary" data-pick="${k}">Seç</button></div>`).join("") || '<div class="list-empty">Sonuç yok.</div>'}</div>`);
    s.el.querySelectorAll("[data-open]").forEach(b => b.onclick = () => window.open(res[+b.dataset.open].url, "_blank"));
    s.el.querySelectorAll("[data-pick]").forEach(b => b.onclick = () => { const r = res[+b.dataset.pick]; it.url = r.url; if (!it.credit) it.credit = `${r.channel} · YouTube`; s.close(); rankDirty(); drawRanking(); });
  } catch (e) { fail(e); }
}

async function findMoment(it) {
  if (!it.url) return toast("Önce bağlantı ekle");
  const f = prompt("Altyazıda hangi ifadeyi arayalım? (boş = tümü)", ""); if (f === null) return;
  toast("Altyazı okunuyor…", 6000);
  try {
    const c = await api(`/api/dl/cues?url=${encodeURIComponent(it.url)}&find=${encodeURIComponent(f)}`);
    const s = sheet("Ana tıkla, kesit olarak eklensin", `<div class="small muted" style="margin-bottom:6px">Tıkladığın satırdan başlayan 8 saniyelik kesit eklenir, sonra kutuda düzeltebilirsin.</div>
      <div class="group" style="margin:0;max-height:60vh;overflow:auto">${c.slice(0, 300).map((x, k) => `<div class="row" data-k="${k}" style="cursor:default"><span class="mono small" style="width:64px">${x.t.toFixed(1)}</span><div class="lbl">${esc(x.text)}</div></div>`).join("") || '<div class="list-empty">Altyazı bulunamadı.</div>'}</div>`);
    s.el.querySelectorAll("[data-k]").forEach(r => r.onclick = () => { const t = c[+r.dataset.k].t; it.parts = [...(it.parts || []), [Math.max(0, +(t - 0.3).toFixed(1)), +(t + 7.7).toFixed(1)]]; s.close(); rankDirty(); drawRanking(); });
  } catch (e) { fail(e); }
}

async function rankRender() {
  clearTimeout(K.saveT); const r = await api(`/api/p/${K.name}`, { body: K.spec }); K.problems = r.problems;
  if (r.problems.some(p => p.level === "error")) { drawRanking(); return toast("Kırmızı uyarılar var, önce onları düzelt."); }
  const s = await api(`/api/p/${K.name}/render`, { method: "POST" }); if (s.ok === false) return toast(s.msg);
  toast("Render başladı. İlk seferde klipler indirilir."); watchRankRender();
}
function watchRankRender(quiet) {
  if (A.poll) clearInterval(A.poll);
  let was = null; const name = K.name;
  const tick = async () => {
    if (!K || K.name !== name || !$("#rlab")) return;
    try {
      const s = await api(`/api/p/${name}/status`);
      $("#rlab").textContent = s.running ? `%${s.pct ?? 0}` : "Render";
      if (s.running) $("#ksave").textContent = s.step;
      if (was === true && !s.running) {
        if (s.step === "bitti") {
          const d = await api(`/api/p/${name}`);
          $(".stage").innerHTML = `<video id="kvid" controls playsinline src="/api/p/${name}/output?m=${d.output_mtime}"></video>`;
          $("#ksave").textContent = "render bitti"; toast("Render bitti, oynatılıyor"); $("#kvid").play().catch(() => { });
        } else toast("Render durdu: " + s.step, 8000);
      }
      was = s.running;
    } catch (e) { }
  };
  tick(); A.poll = setInterval(tick, 1500);
}

async function drawMusic() {
  const s = K.spec, box = $("#kmusic"); if (!box) return;
  const lib = (await api("/api/media")).filter(i => i.kind === "music" && !i.missing);
  const mu = s.music || {}; const cur = lib.find(i => mu.path && (i.path === mu.path || i.path.endsWith("/" + mu.path)));
  const sfxOn = s.sfx_on !== false, g = mu.gain_db ?? -15, sg = s.sfx_gain ?? 1;
  box.innerHTML = `<div class="row stack"><span class="small muted">Arka plan müziği</span><select id="kmsel"><option value="">müzik yok</option>${lib.map(i => `<option value="${i.id}" ${cur && cur.id === i.id ? "selected" : ""}>${esc(i.name)}${(i.tags || []).includes("ncs") ? " · NCS" : ""}</option>`).join("")}</select></div>
    ${cur ? `<div class="row"><div class="lbl"><b>Müzik seviyesi</b><span>${g} dB · konuşma girince otomatik kısılır</span></div><input type="range" id="kmg" min="-28" max="-6" step="1" value="${g}" style="width:120px"></div>
    <div class="row"><div class="lbl"><b>Drop'u #1'e denk getir</b><span>parçanın patladığı an 1 numara açılırken gelir</span></div><input type="checkbox" class="switch" id="kmdrop" ${mu.sync_drop !== false ? "checked" : ""}></div>
    ${cur.source && cur.source.credit ? `<div class="row stack"><span class="small muted">Açıklamaya eklenecek kredi (render sonrası krediler.txt'de de var)</span><textarea readonly rows="3" style="font-size:11px">${esc(cur.source.credit)}</textarea><button class="btn" id="kmcopy">${I("copy", 13)} Krediyi kopyala</button></div>` : ""}` : ""}
    <div class="row"><div class="lbl"><b>Efekt sesleri</b><span>whoosh, darbe, davul ve 1 numarada ding</span></div><input type="checkbox" class="switch" id="ksfx" ${sfxOn ? "checked" : ""}></div>
    ${sfxOn ? `<div class="row"><div class="lbl"><b>Efekt seviyesi</b><span>%${Math.round(sg * 100)}</span></div><input type="range" id="ksg" min="0.2" max="1.6" step="0.1" value="${sg}" style="width:120px"></div>` : ""}
    <div class="row" style="justify-content:flex-end"><button class="btn" id="kmadd">${I("plus", 13)} Müzik ekle</button></div>`;
  $("#kmsel").onchange = e => { const it = lib.find(i => i.id === e.target.value);
    s.music = it ? { path: it.path, credit: (it.source || {}).credit || "", gain_db: g, sync_drop: true } : null; rankDirty(); drawMusic(); };
  if ($("#kmg")) $("#kmg").oninput = e => { s.music.gain_db = +e.target.value; delete s.music.drop; e.target.closest(".row").querySelector(".lbl span").textContent = `${e.target.value} dB · konuşma girince otomatik kısılır`; rankDirty(); };
  if ($("#kmdrop")) $("#kmdrop").onchange = e => { s.music.sync_drop = e.target.checked; delete s.music.drop; rankDirty(); };
  if ($("#kmcopy")) $("#kmcopy").onclick = () => navigator.clipboard.writeText(cur.source.credit).then(() => toast("Kredi kopyalandı"));
  $("#ksfx").onchange = e => { s.sfx_on = e.target.checked; rankDirty(); drawMusic(); };
  if ($("#ksg")) $("#ksg").oninput = e => { s.sfx_gain = +e.target.value; e.target.closest(".row").querySelector(".lbl span").textContent = `%${Math.round(e.target.value * 100)}`; rankDirty(); };
  $("#kmadd").onclick = async () => { try { const r = await api("/api/media/pick", { body: { kind: "music", speaker: "no" } }); if (r.items.length) { toast("Müzik eklendi"); drawMusic(); } } catch (e) { fail(e); } };
}
