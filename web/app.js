// biar-edit app · plain JS, no build step. Talks to biaredit/server.py.
"use strict";
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const fmt = t => { t = Math.max(0, t || 0); const m = Math.floor(t / 60), s = t - m * 60; return `${String(m).padStart(2, "0")}:${s.toFixed(2).padStart(5, "0")}`; };
if (new URLSearchParams(location.search).has("native")) document.body.classList.add("native");

async function api(path, opt = {}) {
  const o = { ...opt };
  if (o.body && typeof o.body !== "string") { o.body = JSON.stringify(o.body); o.method = o.method || "POST"; }
  const r = await fetch(path, o);
  const ct = r.headers.get("content-type") || "";
  const d = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok || (d && d.ok === false)) throw new Error((d && d.msg) || `${r.status}`);
  return d;
}
function toast(msg, ms = 2600) {
  const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; document.body.appendChild(t);
  setTimeout(() => t.remove(), ms);
}
const fail = e => toast("Hata: " + (e.message || e), 5000);

// ---------- icons (SF Symbols-like strokes) ----------
const P = {
  film: "M4 5h16v14H4z M8 5v14 M16 5v14 M4 9h4 M4 15h4 M16 9h4 M16 15h4",
  phone: "M8 3h8a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z M11 18h2",
  grid: "M4 4h7v7H4z M13 4h7v7h-7z M4 13h7v7H4z M13 13h7v7h-7z",
  tray: "M4 13l2-8h12l2 8 M4 13v6h16v-6 M4 13h5l1 2h4l1-2h5",
  cpu: "M7 7h10v10H7z M10 10h4v4h-4z M9 3v4 M15 3v4 M9 17v4 M15 17v4 M3 9h4 M3 15h4 M17 9h4 M17 15h4",
  person: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 21c1-4 4.5-6 8-6s7 2 8 6",
  bolt: "M13 2L4 14h7l-1 8 9-12h-7z",
  copy: "M9 9h11v11H9z M5 15H4V4h11v1",
  cut: "M6 6m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0 M6 18m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0 M8 8l12 10 M8 16L20 6",
  paste: "M9 4h6v3H9z M7 5H5v15h14V5h-2 M10 13h6 M13 10l3 3-3 3",
  dup: "M8 8h12v12H8z M4 16V4h12 M14 11v6 M11 14h6",
  split: "M12 3v18 M5 8l-3 4 3 4 M19 8l3 4-3 4",
  wand: "M4 20L16 8 M14 6l4 4 M18 3v3 M16.5 4.5h3 M21 8v2 M20 9h2 M10 3v2 M9 4h2",
  wave: "M3 12h2 M7 8v8 M11 5v14 M15 9v6 M19 7v10 M21 12h1",
  up: "M12 19V5 M6 11l6-6 6 6",
  down: "M12 5v14 M6 13l6 6 6-6",
  trash: "M4 7h16 M9 7V4h6v3 M6 7l1 13h10l1-13",
  play: "M7 4l13 8-13 8z",
  pause: "M7 4h3v16H7z M14 4h3v16h-3z",
  back: "M11 17l-5-5 5-5 M18 17l-5-5 5-5",
  fwd: "M13 17l5-5-5-5 M6 17l5-5-5-5",
  undo: "M9 14L4 9l5-5 M4 9h10a6 6 0 0 1 0 12h-3",
  redo: "M15 14l5-5-5-5 M20 9H10a6 6 0 0 0 0 12h3",
  save: "M5 4h11l3 3v13H5z M8 4v5h7V4 M8 14h8v6H8z",
  render: "M12 3a9 9 0 1 0 9 9 M12 7v5l3 2",
  share: "M12 3v12 M7 8l5-5 5 5 M5 12v8h14v-8",
  plus: "M12 5v14 M5 12h14",
  key: "M15 9a3 3 0 1 0 0-.01 M12.5 11.5L4 20 M7 17l2 2 M5 19l2 2",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1 M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  check: "M5 12l5 5 9-10",
  x: "M6 6l12 12 M18 6L6 18",
  zoomin: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z M20 20l-4-4 M8 11h6 M11 8v6",
  zoomout: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z M20 20l-4-4 M8 11h6",
  ext: "M14 4h6v6 M20 4l-9 9 M18 14v6H4V6h6",
  mic: "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z M6 11a6 6 0 0 0 12 0 M12 17v4",
};
const I = (n, s = 16) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="${P[n] || ""}"/></svg>`;
const KB = (...k) => `<span class="kbd">${k.map(x => `<i>${x}</i>`).join("")}</span>`;

// ---------- app state + router ----------
const A = { projects: [], settings: null, route: "", poll: null };
function go(h) { if (location.hash !== h) location.hash = h; else route(); }
window.addEventListener("hashchange", route);

async function refreshProjects() {
  A.projects = await api("/api/projects");
  renderNav();
}
function renderNav() {
  const r = location.hash || "#/library";
  const link = (h, icon, label, meta = "") => `<a href="${h}" class="${r === h ? "on" : ""}">${I(icon)}<span>${esc(label)}</span>${meta ? `<span class="meta">${meta}</span>` : ""}</a>`;
  const reels = A.projects.filter(p => p.kind === "reel"), films = A.projects.filter(p => p.kind === "film"), ranks = A.projects.filter(p => p.kind === "ranking");
  $("#nav").innerHTML =
    `<h6>Kütüphane</h6>${link("#/library", "grid", "Projeler", A.projects.length)}${link("#/media", "tray", "Kaynaklar")}${link("#/download", "down", "İndir")}${link("#/record", "render", "Ürün kaydı")}` +
    `<h6>Reels</h6>${reels.map(p => link(`#/p/${p.name}`, "phone", p.title.replace(/^Reel \d+ · /, ""), p.name.replace("reel", ""))).join("") || '<a class="muted">yok</a>'}` +
    `<h6>Sıralama</h6>${ranks.map(p => link(`#/p/${p.name}`, "grid", p.title.replace(/^Sıralama \d+ · /, ""), p.name.replace("rank", ""))).join("") || '<a class="muted">yok</a>'}` +
    `<h6>Uzun video</h6>${films.map(p => link(`#/p/${p.name}`, "film", p.title || p.name)).join("")}` +
    `<h6>Stüdyo</h6>${link("#/style", "wand", "Edit stili", A.styleV ? "v" + A.styleV : "")}${link("#/audio", "mic", "Ses")}${link("#/effects", "wand", "Efektler")}` +
    `<h6>Yayın</h6>${link("#/queue", "tray", "Paylaşım kuyruğu", A.pending ? `<span class="tag warn">${A.pending}</span>` : "")}` +
    `<h6>Ayarlar</h6>${link("#/models", "cpu", "Modeller")}${link("#/accounts", "person", "Hesaplar")}${link("#/automation", "bolt", "Otomasyon ve API")}`;
}
function toolbar(html) { $("#toolbar").innerHTML = html; }
function route() {
  const h = location.hash || "#/library"; A.route = h; renderNav(); closeMenu(); F = null;
  if (A.poll) { clearInterval(A.poll); A.poll = null; }
  const m = h.match(/^#\/p\/(.+)$/);
  if (m) return openProject(decodeURIComponent(m[1])).catch(fail);
  ({ "#/queue": viewQueue, "#/models": viewModels, "#/accounts": viewAccounts, "#/automation": viewAutomation, "#/media": viewMedia,
     "#/audio": viewAudio, "#/effects": viewEffects, "#/record": viewRecord, "#/download": viewDownload, "#/style": viewStyle }[h] || viewLibrary)().catch(fail);
}

// ---------- library ----------
async function viewLibrary() {
  R = null;
  toolbar(`<span class="title">Projeler</span><span class="sp"></span><button class="btn" id="newk">${I("grid", 14)} Yeni sıralama</button><button class="btn primary" id="newp">${I("plus", 14)} Yeni reel</button>`);
  $("#newk").onclick = async () => { const t = prompt("Sıralamanın konusu:", "En iyi sahne demoları"); if (!t) return;
    try { const r = await api("/api/projects/new", { body: { title: t, kind: "ranking" } }); await refreshProjects(); go(`#/p/${r.name}`); } catch (e) { fail(e); } };
  $("#newp").onclick = async () => { const t = prompt("Yeni reelin adı:", "Yeni reel"); if (!t) return;
    try { const r = await api("/api/projects/new", { body: { title: t } }); await refreshProjects(); go(`#/p/${r.name}`); } catch (e) { fail(e); } };
  const v = $("#view"); v.className = "view";
  v.innerHTML = `<div class="cards">${A.projects.map(p => `<div class="card" data-go="#/p/${esc(p.name)}">
      <div class="cv" style="${p.kind !== "film" ? "aspect-ratio:16/10" : ""}" data-thumb="${esc(p.name)}"></div>
      <div class="cb"><b>${esc(p.title)}</b><span class="muted small">${p.kind === "reel" ? "Reels · 9:16" : p.kind === "ranking" ? "Sıralama · 9:16" : "Uzun video · 4K"} · ${new Date(p.modified * 1000).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" })}</span></div></div>`).join("")}</div>`;
  v.querySelectorAll(".card").forEach(c => c.onclick = () => go(c.dataset.go));
  for (const el of v.querySelectorAll("[data-thumb]")) {
    try {
      const d = await api(`/api/p/${el.dataset.thumb}`);
      if (d.ranking) { if (d.has_output) el.style.backgroundImage = `url("/p/${el.dataset.thumb}/work/card${Math.max(0, d.ranking.items.length - 1)}.png"), url("/p/${el.dataset.thumb}/work/intro.png")`; el.style.backgroundColor = "#1b1530"; continue; }
      if (d.reel && !d.reel.beats.length) continue;
      const src = d.reel ? d.reel.beats[0].audio.src : "main", t = d.reel ? d.reel.beats[0].audio.a + 1 : 120;
      el.style.backgroundImage = `url("/api/p/${el.dataset.thumb}/thumb?src=${encodeURIComponent(src)}&t=${t}")`;
    } catch (e) { }
  }
}

async function openProject(name) {
  const d = await api(`/api/p/${name}`);
  if (d.reel) return viewReel(name, d);
  if (d.ranking) return viewRanking(name, d);
  return viewFilm(name, d);
}

// =====================================================================
// Reel editor
// =====================================================================
let R = null;
const KIND = { sync: "Senkron", clip: "Ara plan", native: "Dikey klip", paper: "Kağıt efekti" };
const CLS = { sync: "sync", clip: "clip_", native: "native", paper: "paper" };
const peaksCache = {};

function rvalidate(r) {
  const out = [];
  r.beats.forEach((b, bi) => {
    const d = b.audio.b - b.audio.a;
    if (d <= 0) out.push({ level: "error", beat: bi, msg: `Cümle ${bi + 1}: ses bitişi başlangıçtan önce.` });
    const fixed = b.shots.reduce((s, x) => s + (+x.dur || 0), 0);
    if (fixed > d + 0.01) out.push({ level: "error", beat: bi, msg: `Cümle ${bi + 1}: planların süresi sesten uzun.` });
    b.shots.forEach((s, si) => {
      if (s.kind === "sync" || s.kind === "paper") return;
      const src = r.sources[s.src] || {};
      if (src.speaker === "yes" && !s.synced) out.push({ level: "error", beat: bi, shot: si, msg: `Cümle ${bi + 1}, plan ${si + 1} (${s.src}): yüzün görünüyor ama ses başka andan. Dudaklar kayar.` });
      else if (src.speaker === "sometimes" && !s.synced) out.push({ level: "warn", beat: bi, shot: si, msg: `Cümle ${bi + 1}, plan ${si + 1} (${s.src}): bazen konuşmacı görünüyor, kontrol et.` });
    });
  });
  return out;
}
function layout(r) {
  let t = 0; const beats = [], shots = [], caps = [], titles = [];
  r.beats.forEach((b, bi) => {
    const D = Math.max(0, b.audio.b - b.audio.a); beats.push({ bi, start: t, dur: D });
    const fixed = b.shots.reduce((s, x) => s + (+x.dur || 0), 0), free = b.shots.filter(x => !x.dur).length;
    const rest = free ? Math.max(0, D - fixed) / free : 0; let u = t;
    b.shots.forEach((s, si) => { const d = s.dur ? +s.dur : rest; shots.push({ bi, si, start: u, dur: d }); u += d; });
    (b.caps || []).forEach((c, ci) => caps.push({ bi, ci, start: t + (c.s - b.audio.a), dur: c.e - c.s }));
    (b.titles || []).forEach((x, ti) => { const e = x.d1 == null ? D : Math.min(+x.d1, D); titles.push({ bi, ti, start: t + (+x.d0 || 0), dur: Math.max(0.05, e - (+x.d0 || 0)) }); });
    t += D;
  });
  return { beats, shots, caps, titles, total: t };
}

async function viewReel(name, d) {
  R = { name, reel: d.reel, hasOut: d.has_output, outM: d.output_mtime, live: d.has_preview, pvM: d.preview_mtime, sel: null, hist: [], fut: [], dirty: false, pps: 0, clip: null,
        mod: (A.projects.find(p => p.name === name) || {}).modified || 0 };
  const norm = rr => { rr.audio = rr.audio || { lufs: -14 }; rr.audio.music = rr.audio.music || {}; rr.look = rr.look || { filter: "none" }; rr.sfx = rr.sfx || []; return rr; };
  norm(R.reel);
  R.sig0 = d.rendered ? visualSig(norm(d.rendered)) : R.mod > (Math.max(R.outM || 0, R.pvM || 0)) + 1 ? null : visualSig(R.reel);
  toolbar(`<span class="title">${esc(R.reel.name)}</span><span class="sub" id="rdirty"></span><span class="sp"></span>
    <button class="btn icon" id="bundo" title="Geri al ⌘Z">${I("undo")}</button><button class="btn icon" id="bredo" title="Yinele ⇧⌘Z">${I("redo")}</button>
    <button class="btn" id="bsave">${I("save", 14)} Kaydet</button>
    <button class="btn" id="bsrc">${I("plus", 14)} Kaynak</button>
    <button class="btn" id="bshare">${I("share", 14)} Paylaş</button>
    <button class="btn primary" id="brender">${I("render", 14)} <span id="rlab">Render</span></button>`);
  const v = $("#view"); v.className = "view fill";
  v.innerHTML = `<div class="editor">
      <div class="stagewrap"><div class="stage"><video id="vid" playsinline preload="auto"></video><div class="ovl" id="ovl"></div><div class="empty" id="vempty">Henüz render yok.<br>Sağ üstten Render'a bas.</div></div><span class="stale tag warn" id="stale" hidden>görüntü değişti · render'a bas</span><span class="stale tag" id="nolive" hidden style="top:auto;bottom:22px">yazıları canlı görmek için bir kez render et</span></div>
      <div class="insp" id="insp"></div></div>
    <div class="transport">
      <button class="btn icon" id="tback" title="Başa">${I("back", 14)}</button>
      <button class="btn icon" id="tplay" title="Oynat (boşluk)">${I("play", 14)}</button>
      <span class="tc" id="tc">00:00.00 / 00:00.00</span><span class="sp" style="flex:1"></span>
      <span class="small" style="color:#888">yakınlaştır</span><input type="range" id="tzoom" min="10" max="240" value="60">
    </div>
    <div class="timeline"><div class="tl-heads"><div>Görüntü</div><div>Ses</div><div class="thin">Altyazı</div><div class="lanes">Başlık</div><div class="thin">SFX</div></div>
      <div class="tl-scroll" id="tls"><div class="tl-inner" id="tli"></div></div></div>`;
  const vid = $("#vid");
  setVideoSrc();
  vid.ontimeupdate = () => drawPlayhead();
  const loop = () => { if (!R || R.name !== name || !$("#vid")) return; drawOverlay(); requestAnimationFrame(loop); }; requestAnimationFrame(loop);
  new ResizeObserver(() => fitOverlay()).observe(v.querySelector(".stage")); vid.onplay = vid.onpause = () => $("#tplay").innerHTML = I(vid.paused ? "play" : "pause", 14);
  $("#tplay").onclick = () => vid.paused ? vid.play() : vid.pause();
  $("#tback").onclick = () => { vid.currentTime = 0; drawPlayhead(); };
  const fit = () => { const w = $("#tls").clientWidth - 40, T = layout(R.reel).total || 1; R.pps = clamp(w / T, 10, 240); $("#tzoom").value = R.pps; };
  fit();
  $("#tzoom").oninput = e => { R.pps = +e.target.value; drawTimeline(); };
  $("#bundo").onclick = undo; $("#bredo").onclick = redo; $("#bsave").onclick = () => saveReel().catch(fail);
  $("#brender").onclick = () => startRender().catch(fail);
  $("#bshare").onclick = () => openShare({ project: name, title: R.reel.name });
  $("#bsrc").onclick = () => pickSourceForReel();
  api("/api/fx").then(f => { R.fx = f; drawInspector(); }).catch(() => { });
  $("#tls").addEventListener("mousedown", tlMouseDown);
  $("#tls").addEventListener("contextmenu", tlContext);
  drawAll(); watchRender(true);
}
function setDirty(b) { R.dirty = b; const e = $("#rdirty"); if (e) e.textContent = b ? "● kaydediliyor…" : (R.savedAt ? "✓ kaydedildi" : ""); updateStale(); if (b) autosave(); }
// only changes that alter the picture need a new render; text is drawn live on top of the clean preview
function visualSig(r) { return JSON.stringify([r.beats.map(b => [b.audio, b.gain, b.shots, b.transition]), r.look, r.audio, r.sfx, R && R.live ? null : r.beats.map(b => [b.caps, b.titles])]); }
function updateStale() { const s = $("#stale"); if (s) s.hidden = !(R.hasOut && R.sig0 !== visualSig(R.reel)); const n = $("#nolive"); if (n) n.hidden = !!R.live || !R.hasOut; }
function setVideoSrc() {
  const v = $("#vid"); if (!v) return;
  if (R.live) v.src = `/api/p/${R.name}/preview?m=${R.pvM}`; else if (R.hasOut) v.src = `/api/p/${R.name}/output?m=${R.outM}`;
  $("#vempty").hidden = !(R.live || R.hasOut) ? false : true; buildOverlay(); updateStale();
}
function autosave() {
  clearTimeout(R.saveT); const name = R.name;
  R.saveT = setTimeout(async () => { if (!R || R.name !== name || !R.dirty) return;
    try { await api(`/api/p/${R.name}`, { body: R.reel }); R.savedAt = Date.now(); R.mod = Date.now() / 1000; setDirty(false); } catch (e) { fail(e); } }, 700);
}
function snap() { R.hist.push(JSON.stringify(R.reel)); if (R.hist.length > 200) R.hist.shift(); R.fut = []; setDirty(true); }
function undo() { if (!R || !R.hist.length) return; R.fut.push(JSON.stringify(R.reel)); R.reel = JSON.parse(R.hist.pop()); setDirty(true); drawAll(); }
function redo() { if (!R || !R.fut.length) return; R.hist.push(JSON.stringify(R.reel)); R.reel = JSON.parse(R.fut.pop()); setDirty(true); drawAll(); }
async function saveReel() {
  clearTimeout(R.saveT); const r = await api(`/api/p/${R.name}`, { body: R.reel }); R.savedAt = Date.now(); setDirty(false); R.mod = Date.now() / 1000; updateStale();
  toast(r.problems.some(p => p.level === "error") ? "Kaydedildi, ama kırmızı uyarılar var" : "Kaydedildi");
}
async function startRender() {
  if (rvalidate(R.reel).some(p => p.level === "error")) { toast("Kırmızı uyarılar var, önce onları düzelt."); R.sel = null; drawInspector(); return; }
  if (R.dirty) await saveReel();
  await api(`/api/p/${R.name}/render`, { method: "POST" }); toast("Render başladı"); watchRender();
}
function watchRender(quiet) {
  if (A.poll) clearInterval(A.poll);
  let was = null; const name = R.name;
  const tick = async () => {
    if (!R || R.name !== name) return;
    try {
      const s = await api(`/api/p/${name}/status`); const lab = $("#rlab"); if (!lab) return;
      lab.textContent = s.running ? `%${s.pct ?? 0}` : "Render";
      if (was === true && !s.running) {
        if (s.step === "bitti") {
          const d = await api(`/api/p/${name}`); R.hasOut = true; R.outM = d.output_mtime; R.live = d.has_preview; R.pvM = d.preview_mtime; R.sig0 = visualSig(R.reel);
          setVideoSrc(); toast("Render bitti, oynatılıyor"); $("#vid").play().catch(() => { });
        } else toast("Render durdu: " + (s.msg || s.step), 6000);
      }
      was = s.running;
    } catch (e) { }
  };
  tick(); A.poll = setInterval(tick, 1500);
}

// ---- timeline drawing ----
function drawAll() { drawTimeline(); drawInspector(); buildOverlay(); }
function selIs(type, bi, i) { const s = R.sel; return s && s.type === type && s.bi === bi && (i === undefined || s.i === i); }
function drawTimeline() {
  const L = layout(R.reel), pps = R.pps, W = Math.max(L.total * pps + 120, $("#tls").clientWidth);
  const probs = rvalidate(R.reel);
  const badShot = (bi, si) => probs.some(p => p.level === "error" && p.beat === bi && p.shot === si);
  const badBeat = bi => probs.some(p => p.level === "error" && p.beat === bi && p.shot === undefined);
  const step = pps > 90 ? 1 : pps > 40 ? 2 : pps > 18 ? 5 : 10;
  let ruler = ""; for (let t = 0; t <= L.total + step; t += step) ruler += `<span style="left:${t * pps}px">${fmt(t).slice(0, 5)}</span>`;
  for (let t = 0; t <= L.total + 1; t += step / 5) ruler += `<i style="left:${t * pps}px"></i>`;
  const clip = (cls, x, w, attrs, label, extra = "") =>
    `<div class="clip ${cls}" style="left:${x * pps}px;width:${Math.max(4, w * pps - 3)}px" ${attrs}>${extra}<span class="lbl">${esc(label)}</span><i class="h l"></i><i class="h r"></i></div>`;
  const b = R.reel.beats;
  const shots = L.shots.map(s => { const sh = b[s.bi].shots[s.si];
    return clip(`${CLS[sh.kind] || "sync"} ${selIs("shot", s.bi, s.si) ? "sel" : ""} ${badShot(s.bi, s.si) ? "bad" : ""}`, s.start, s.dur,
      `data-t="shot" data-b="${s.bi}" data-i="${s.si}"`, `${KIND[sh.kind] || sh.kind}${sh.src ? " · " + sh.src : ""}`, `<div class="thumb" data-th="${s.bi}:${s.si}"></div>`); }).join("");
  const audio = L.beats.map(x => { const be = b[x.bi];
    return clip(`audio ${selIs("beat", x.bi) ? "sel" : ""} ${badBeat(x.bi) ? "bad" : ""}`, x.start, x.dur, `data-t="beat" data-b="${x.bi}"`,
      `${x.bi + 1} · ${be.audio.src}`, `<canvas data-pk="${x.bi}"></canvas>`); }).join("");
  const caps = L.caps.map(c => clip(`cap ${selIs("cap", c.bi, c.ci) ? "sel" : ""}`, c.start, c.dur, `data-t="cap" data-b="${c.bi}" data-i="${c.ci}"`, b[c.bi].caps[c.ci].text)).join("");
  const lanes = []; // overlapping title strips go to separate lanes so their labels stay readable
  const titles = L.titles.map(c => { let ln = lanes.findIndex(e => e <= c.start + 0.01); if (ln < 0 || ln > 2) { ln = lanes.length < 3 ? lanes.length : 2; } lanes[ln] = c.start + c.dur;
    return clip(`title ${selIs("title", c.bi, c.ti) ? "sel" : ""}`, c.start, c.dur, `data-t="title" data-b="${c.bi}" data-i="${c.ti}" style2`, b[c.bi].titles[c.ti].text).replace('style2', '').replace('px" ', `px;top:${4 + ln * 16}px" `); }).join("");
  const sfx = (R.reel.sfx || []).map((e, i) => clip(`sfxc ${selIs("sfx", -1, i) ? "sel" : ""}`, e.t, Math.max(0.3, e.dur || 0.6), `data-t="sfx" data-b="-1" data-i="${i}"`, "♪ " + (e.name || "sfx")).replace(/<i class="h l"><\/i><i class="h r"><\/i>/, "")).join("");
  const trans = L.beats.slice(0, -1).map(x => { const tr = b[x.bi].transition; return tr && tr.name && tr.name !== "none" ? `<div class="trmark" style="left:${(x.start + x.dur) * pps}px" title="${esc(tr.name)}" data-tr="${x.bi}"></div>` : ""; }).join("");
  $("#tli").style.width = W + "px";
  $("#tli").innerHTML = `<div class="ruler" data-ruler>${ruler}</div><div class="track">${shots}</div><div class="track">${audio}</div>
    <div class="track thin">${caps}</div><div class="track lanes">${titles}</div><div class="track thin">${sfx}</div>${trans}<div class="playhead" id="ph"></div>`;
  drawPlayhead(); drawWaves(L); drawThumbs(L);
}
function drawPlayhead() {
  const v = $("#vid"), ph = $("#ph"); if (!v || !ph) return;
  const T = layout(R.reel).total;
  ph.style.left = (v.currentTime * R.pps) + "px";
  $("#tc").textContent = `${fmt(v.currentTime)} / ${fmt(T)}`;
}
async function drawWaves(L) {
  for (const cv of document.querySelectorAll("canvas[data-pk]")) {
    const bi = +cv.dataset.pk, be = R.reel.beats[bi]; if (!be) continue;
    const w = cv.clientWidth, h = cv.clientHeight; if (!w) continue;
    const n = clamp(Math.round(w / 4), 8, 600), key = `${be.audio.src}|${be.audio.a}|${be.audio.b}|${n}`;
    try {
      const pk = peaksCache[key] || (peaksCache[key] = await api(`/api/p/${R.name}/peaks?src=${encodeURIComponent(be.audio.src)}&a=${be.audio.a}&b=${be.audio.b}&n=${n}`));
      const dpr = devicePixelRatio || 1; cv.width = w * dpr; cv.height = h * dpr;
      const g = cv.getContext("2d"); g.scale(dpr, dpr); g.fillStyle = "rgba(0,0,0,.82)";
      const bw = w / n;
      pk.forEach((p, i) => { const bh = Math.max(1.5, p * (h - 18)); g.beginPath(); g.roundRect(i * bw + bw * 0.3, h / 2 + 5 - bh / 2, Math.max(1.2, bw * 0.4), bh, 1); g.fill(); });
    } catch (e) { }
  }
}
function drawThumbs(L) {
  for (const el of document.querySelectorAll("[data-th]")) {
    const [bi, si] = el.dataset.th.split(":").map(Number), be = R.reel.beats[bi], sh = be.shots[si];
    const sp = L.shots.find(s => s.bi === bi && s.si === si); if (!sh || sh.kind === "paper") continue;
    const src = sh.kind === "sync" ? be.audio.src : sh.src, t = sh.kind === "sync" ? be.audio.a + (sp.start - L.beats[bi].start) + 0.3 : (+sh.t || 0) + 0.3;
    if (src) el.style.backgroundImage = `url("/api/p/${R.name}/thumb?src=${encodeURIComponent(src)}&t=${t.toFixed(1)}")`;
  }
}

// ---- timeline interaction ----
function itemOf(el) { const c = el.closest(".clip"); return c ? { type: c.dataset.t, bi: +c.dataset.b, i: c.dataset.i !== undefined ? +c.dataset.i : undefined } : null; }
function seek(t) { const v = $("#vid"); if (v && R.hasOut) { v.currentTime = clamp(t, 0, v.duration || t); } drawPlayhead(); }
function tlMouseDown(e) {
  if (e.button !== 0) return; closeMenu();
  const box = $("#tli").getBoundingClientRect(), t = (e.clientX - box.left) / R.pps;
  const it = itemOf(e.target);
  if (!it) { R.sel = null; drawAll(); seek(t); return; }
  R.sel = it; const L = layout(R.reel);
  const span = it.type === "sfx" ? null : it.type === "beat" ? L.beats[it.bi] : it.type === "shot" ? L.shots.find(s => s.bi === it.bi && s.si === it.i) : it.type === "cap" ? L.caps.find(c => c.bi === it.bi && c.ci === it.i) : L.titles.find(c => c.bi === it.bi && c.ti === it.i);
  if (it.type === "sfx") {   // drag a sound effect along the timeline
    const ev0 = R.reel.sfx[it.i], x0 = e.clientX, t0 = ev0.t, before = JSON.stringify(R.reel);
    const mv = ev => { ev0.t = Math.max(0, +(t0 + (ev.clientX - x0) / R.pps).toFixed(2)); drawTimeline(); };
    const up = () => { removeEventListener("mousemove", mv); removeEventListener("mouseup", up); if (JSON.stringify(R.reel) !== before) { R.hist.push(before); R.fut = []; setDirty(true); } drawAll(); };
    addEventListener("mousemove", mv); addEventListener("mouseup", up); drawAll(); return;
  }
  const edge = e.target.classList.contains("h") ? (e.target.classList.contains("l") ? "l" : "r") : null;
  if (!edge) { seek(span ? span.start + 0.02 : t); drawAll(); return; }
  // edge drag = trim
  const x0 = e.clientX, before = JSON.stringify(R.reel), b = R.reel.beats[it.bi], orig = JSON.parse(JSON.stringify(b));
  const move = ev => {
    const dt = Math.round(((ev.clientX - x0) / R.pps) * 100) / 100;
    if (it.type === "beat") { if (edge === "l") b.audio.a = Math.min(orig.audio.b - 0.1, +(orig.audio.a + dt).toFixed(2)); else b.audio.b = Math.max(orig.audio.a + 0.1, +(orig.audio.b + dt).toFixed(2)); }
    else if (it.type === "shot") { const s = b.shots[it.i]; if (edge === "r") s.dur = Math.max(0.2, +((orig.shots[it.i].dur || span.dur) + dt).toFixed(2)); }
    else if (it.type === "cap") { const c = b.caps[it.i], o = orig.caps[it.i]; if (edge === "l") c.s = Math.min(o.e - 0.1, +(o.s + dt).toFixed(2)); else c.e = Math.max(o.s + 0.1, +(o.e + dt).toFixed(2)); }
    else { const x = b.titles[it.i], o = orig.titles[it.i]; if (edge === "l") x.d0 = Math.max(0, +((+o.d0 || 0) + dt).toFixed(2)); else x.d1 = Math.max((+o.d0 || 0) + 0.1, +(((o.d1 == null ? span.start - layout(JSON.parse(before)).beats[it.bi].start + span.dur : +o.d1)) + dt).toFixed(2)); }
    drawTimeline();
  };
  const up = () => { removeEventListener("mousemove", move); removeEventListener("mouseup", up);
    if (JSON.stringify(R.reel) !== before) { R.hist.push(before); R.fut = []; setDirty(true); } drawAll(); };
  addEventListener("mousemove", move); addEventListener("mouseup", up);
}

// ---- edit operations ----
function listOf(sel) { if (sel.type === "sfx") return (R.reel.sfx = R.reel.sfx || []); const b = R.reel.beats[sel.bi]; return sel.type === "shot" ? b.shots : sel.type === "cap" ? (b.caps = b.caps || []) : sel.type === "title" ? (b.titles = b.titles || []) : R.reel.beats; }
function idxOf(sel) { return sel.type === "beat" ? sel.bi : sel.i; }
function opCopy() { if (!R.sel) return; R.clip = { type: R.sel.type, data: JSON.parse(JSON.stringify(listOf(R.sel)[idxOf(R.sel)])) }; toast("Kopyalandı"); }
function opDelete() {
  const s = R.sel; if (!s) return;
  if (s.type === "beat" && !confirm(`Cümle ${s.bi + 1} silinsin mi? (geri alınabilir)`)) return;
  if (s.type === "shot" && R.reel.beats[s.bi].shots.length === 1) { toast("Bir cümlede en az bir plan olmalı"); return; }
  snap(); listOf(s).splice(idxOf(s), 1); R.sel = null; drawAll();
}
function opCut() { opCopy(); opDelete(); }
function opPaste() {
  if (!R.clip) return; const c = R.clip, s = R.sel; snap();
  if (c.type === "beat") { const at = s ? s.bi + 1 : R.reel.beats.length; R.reel.beats.splice(at, 0, JSON.parse(JSON.stringify(c.data))); R.sel = { type: "beat", bi: at }; }
  else {
    const bi = s ? s.bi : 0, tgt = { type: c.type, bi }, list = listOf(tgt), at = s && s.type === c.type ? s.i + 1 : list.length;
    list.splice(at, 0, JSON.parse(JSON.stringify(c.data))); R.sel = { type: c.type, bi, i: at };
  }
  drawAll();
}
function opDup() { if (!R.sel) return; const keep = R.clip; opCopy(); opPaste(); R.clip = keep; }
function opMove(dir) {
  const s = R.sel; if (!s) return; const list = listOf(s), i = idxOf(s), j = i + dir; if (j < 0 || j >= list.length) return;
  snap(); [list[i], list[j]] = [list[j], list[i]]; if (s.type === "beat") s.bi = j; else s.i = j; drawAll();
}
function opSplit() {
  const v = $("#vid"), T = v ? v.currentTime : 0, L = layout(R.reel);
  const x = L.beats.find(b => T > b.start + 0.1 && T < b.start + b.dur - 0.1);
  if (!x) { toast("Oynatma çizgisini bir cümlenin ortasına getir"); return; }
  snap(); const b = R.reel.beats[x.bi], ts = +(b.audio.a + (T - x.start)).toFixed(2);
  const A1 = JSON.parse(JSON.stringify(b)), B1 = JSON.parse(JSON.stringify(b));
  A1.audio.b = ts; B1.audio.a = ts;
  A1.caps = (b.caps || []).filter(c => c.s < ts).map(c => ({ ...c, e: Math.min(c.e, ts) }));
  B1.caps = (b.caps || []).filter(c => c.e > ts).map(c => ({ ...c, s: Math.max(c.s, ts) }));
  B1.titles = []; const fit = (sh, D) => { let left = D; return sh.map(s => { if (s.dur) { const d = Math.min(+s.dur, left); left -= d; return d > 0.15 ? { ...s, dur: +d.toFixed(2) } : null; } return { ...s }; }).filter(Boolean); };
  A1.shots = fit(b.shots, ts - b.audio.a); if (!A1.shots.length) A1.shots = [{ ...b.shots[0], dur: null }];
  B1.shots = [{ ...b.shots[b.shots.length - 1], dur: null }];
  R.reel.beats.splice(x.bi, 1, A1, B1); R.sel = { type: "beat", bi: x.bi + 1 }; drawAll(); toast(`Cümle ${x.bi + 1} ${fmt(ts - b.audio.a)} noktasından bölündü`);
}
async function opAICaption() { openShare({ project: R.name, title: R.reel.name, autogen: true }); }
async function opVoice() {
  const s = R.sel, txt = s && s.type === "cap" ? R.reel.beats[s.bi].caps[s.i].text : prompt("Seslendirilecek metin:");
  if (!txt) return; toast("ElevenLabs ile seslendiriliyor…");
  try { const r = await api("/api/ai/tts", { body: { text: txt } }); new Audio(r.url).play();
    await api("/api/media/add", { body: { paths: [r.path], kind: "audio" } }); toast("Ses hazır, Kaynaklar'a eklendi", 5000); } catch (e) { fail(e); }
}
function addItem(type) {
  const bi = R.sel && R.sel.bi >= 0 ? R.sel.bi : R.reel.beats.length - 1; snap(); const b = R.reel.beats[bi];
  if (type === "beat") { const last = R.reel.beats[R.reel.beats.length - 1], src0 = Object.keys(R.reel.sources)[0];
    if (!last && !src0) { R.hist.pop(); toast("Önce Kaynak ile bir video ekle"); return pickSourceForReel(); }
    R.reel.beats.push({ audio: { src: last ? last.audio.src : src0, a: last ? last.audio.b : 0, b: +((last ? last.audio.b : 0) + 3).toFixed(2) }, shots: [{ kind: "sync", layout: "crop" }], caps: [], titles: [] }); R.sel = { type: "beat", bi: R.reel.beats.length - 1 }; }
  if (!b) { drawAll(); return; }
  if (type === "shot") { b.shots.push({ kind: "sync", layout: "crop" }); R.sel = { type, bi, i: b.shots.length - 1 }; }
  if (type === "cap") { (b.caps = b.caps || []).push({ text: "Yeni altyazı", s: b.audio.a, e: Math.min(b.audio.b, b.audio.a + 1.5) }); R.sel = { type, bi, i: b.caps.length - 1 }; }
  if (type === "title") { (b.titles = b.titles || []).push({ text: "YENİ", size: "mid", col: "w", x: 120, y: 260, ang: 0, d0: 0.1, d1: null }); R.sel = { type, bi, i: b.titles.length - 1 }; }
  drawAll();
}

// ---- context menu ----
function closeMenu() { document.querySelectorAll(".menu").forEach(m => m.remove()); }
function showMenu(x, y, items) {
  closeMenu(); const m = document.createElement("div"); m.className = "menu";
  m.innerHTML = items.map((it, i) => it === "-" ? '<div class="sep"></div>' :
    `<div class="it ${it.off ? "off" : ""}" data-i="${i}">${I(it.icon, 18)}<span>${esc(it.label)}</span>${it.badge || ""}<span class="k">${it.keys || ""}</span></div>`).join("");
  document.body.appendChild(m);
  const r = m.getBoundingClientRect(); m.style.left = clamp(x, 8, innerWidth - r.width - 8) + "px"; m.style.top = clamp(y, 8, innerHeight - r.height - 8) + "px";
  m.onclick = e => { const el = e.target.closest(".it"); if (!el) return; closeMenu(); items[+el.dataset.i].run(); };
}
addEventListener("mousedown", e => { if (!e.target.closest(".menu")) closeMenu(); });
function tlContext(e) {
  e.preventDefault(); const it = itemOf(e.target); if (it) { R.sel = it; drawAll(); }
  const has = !!R.sel, AI = '<span class="tag ai">+ AI</span>', NEW = '<span class="new">YENİ</span>';
  showMenu(e.clientX, e.clientY, [
    { icon: "copy", label: "Kopyala", keys: KB("⌘", "C"), run: opCopy, off: !has },
    { icon: "cut", label: "Kes", keys: KB("⌘", "X"), run: opCut, off: !has },
    { icon: "paste", label: "Yapıştır", keys: KB("⌘", "V"), run: opPaste, off: !R.clip },
    { icon: "dup", label: "Çoğalt", keys: KB("⌘", "D"), run: opDup, off: !has }, "-",
    { icon: "split", label: "Oynatma çizgisinden böl", keys: KB("⌘", "B"), run: opSplit },
    { icon: "wand", label: "Paylaşım metni üret", badge: AI, keys: KB("⇧", "G"), run: opAICaption },
    { icon: "mic", label: "Seslendir", badge: NEW, keys: KB("⇧", "V"), run: opVoice }, "-",
    { icon: "up", label: "Öne al", keys: KB("⌘", "↑"), run: () => opMove(-1), off: !has },
    { icon: "down", label: "Geri gönder", keys: KB("⌘", "↓"), run: () => opMove(1), off: !has }, "-",
    { icon: "plus", label: "Yeni altyazı", run: () => addItem("cap") },
    { icon: "plus", label: "Yeni başlık şeridi", run: () => addItem("title") },
    { icon: "plus", label: "Yeni cümle", run: () => addItem("beat") },
    { icon: "wave", label: "Buraya SFX ekle", badge: '<span class="tag ai">♪</span>', keys: KB("⇧", "S"), run: addSfxAtPlayhead },
    { icon: "wand", label: "Sonraki cümleye geçiş", keys: KB("⇧", "T"), run: () => { const s0 = R.sel && R.sel.bi >= 0 ? R.sel.bi : 0; R.sel = { type: "beat", bi: s0 }; drawAll(); toast("Sağdaki panelden geçişi seç"); }, off: R.reel.beats.length < 2 },
    { icon: "plus", label: "Kaynak ekle", run: pickSourceForReel }, "-",
    { icon: "trash", label: "Sil", keys: KB("⇧", "⌫"), run: opDelete, off: !has },
  ]);
}
addEventListener("keydown", e => {
  if (!R || !$("#tli")) return;
  if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) { if ((e.metaKey || e.ctrlKey) && e.key === "s") { e.preventDefault(); saveReel().catch(fail); } return; }
  const k = e.key.toLowerCase(), cmd = e.metaKey || e.ctrlKey;
  const map = cmd ? { c: opCopy, x: opCut, v: opPaste, d: opDup, b: opSplit, s: () => saveReel().catch(fail), z: e.shiftKey ? redo : undo, arrowup: () => opMove(-1), arrowdown: () => opMove(1) }
                  : e.shiftKey ? { g: opAICaption, v: opVoice, s: addSfxAtPlayhead, backspace: opDelete } : { " ": () => { const v = $("#vid"); v.paused ? v.play() : v.pause(); }, backspace: opDelete, delete: opDelete, escape: () => { R.sel = null; drawAll(); } };
  if (map[k]) { e.preventDefault(); map[k](); }
});

// ---- inspector extras: look, output, audio, transitions ----
const INSP_ACT = {
  outdir: async () => { try { const d = await api("/api/pick/folder", { body: { prompt: "Bu reel nereye kaydedilsin?" } }); if (!d.path) return;
    if (R.dirty) await saveReel(); const r = await api(`/api/p/${R.name}/output`, { body: { dir: d.path } }); R.reel.output = r.reel.output; drawInspector(); toast("Çıktı: " + d.path); } catch (e) { fail(e); } },
  reveal: () => api("/api/reveal", { body: { path: R.reel.output } }).catch(fail),
  playsfx: i => { const e = R.reel.sfx[+i]; const m = (R.fx && R.fx.sfx || []).find(x => x.path === e.path); if (m) preview(`/api/media/${m.id}/file`); },
  delsfx: i => { snap(); R.reel.sfx.splice(+i, 1); R.sel = null; drawAll(); },
  addsrc: () => pickSourceForReel(),
  addsfx: () => addSfxAtPlayhead(),
};
function extraInspector(s) {
  const r = R.reel, fx = R.fx || { looks: [], transitions: [], music: [], luts: [], transition_assets: [] };
  if (!s) {
    return `<h4>${I("wand", 14)} Görünüm</h4><div class="f">${field("Filtre", "look.filter", r.look.filter || "none", "select", fx.looks.map(l => [l.id, l.name]))}
        ${field("LUT", "look.lut", r.look.lut || "", "select", [["", "Yok"]].concat(fx.luts.map(l => [l.path, l.name])))}</div>
      <h4>${I("wave", 14)} Ses</h4><div class="f">${field("Ses yüksekliği", "audio.lufs", r.audio.lufs ?? -14, "select", [[-14, "-14 LUFS · Instagram/TikTok"], [-16, "-16 LUFS · YouTube"], [-12, "-12 LUFS · yüksek"]])}
        ${field("Gürültü azalt", "audio.denoise", r.audio.denoise, "check")}
        ${field("Ses rengi", "audio.eq", r.audio.eq || "", "select", [["", "Doğal"], ["net", "Net (konuşma öne)"], ["sicak", "Sıcak"]])}
        ${field("Müzik", "audio.music.path", r.audio.music.path || "", "select", [["", "Yok"]].concat(fx.music.map(m => [m.path, m.name])))}
        ${r.audio.music.path ? field("Müzik seviyesi", "audio.music.gain", r.audio.music.gain ?? 0.18) + field("Konuşmada kıs", "audio.music.duck", r.audio.music.duck !== false, "check") : ""}</div>
      <h4>${I("wave", 14)} Ses efektleri</h4><div class="probs">${r.sfx.map((e, i) => `<div class="small">♪ ${esc(e.name)} · ${(+e.t).toFixed(2)} sn</div>`).join("") || '<div class="small muted">Yok</div>'}
        <button class="btn" data-act="addsfx" style="margin-top:6px">${I("plus", 12)} Oynatma çizgisine SFX</button></div>
      <h4>${I("ext", 14)} Çıktı</h4><div class="probs"><div class="small mono" style="word-break:break-all">${esc(r.output)}</div>
        <div style="display:flex;gap:6px;margin-top:6px"><button class="btn" data-act="outdir">Klasör seç</button><button class="btn" data-act="reveal">Finder'da göster</button></div></div>`;
  }
  if (s.type === "beat") {
    const b = r.beats[s.bi], tr = b.transition || {}, P_ = `beats.${s.bi}.transition`;
    if (s.bi >= r.beats.length - 1) return "";
    b.transition = tr;
    return `<h4>${I("wand", 14)} Sonraki geçiş</h4><div class="f">${field("Geçiş", `${P_}.name`, tr.name === "asset" ? "asset:" + tr.asset : (tr.name || "none"), "select", fx.transitions.map(t => [t.id, t.name]).concat(fx.transition_assets.map(t => ["asset:" + t.path, "▸ " + t.name])))}
      ${tr.name && tr.name !== "none" ? field("Süre (sn)", `${P_}.dur`, tr.dur ?? 0.4) : ""}</div>`;
  }
  if (s.type === "shot") {
    const sh = r.beats[s.bi].shots[s.i];
    if (sh.kind === "paper") return "";
    return `<h4>${I("wand", 14)} Planın filtresi</h4><div class="f">${field("Filtre", `beats.${s.bi}.shots.${s.i}.filter`, sh.filter || "", "select", [["", "Reelin filtresi"]].concat(fx.looks.map(l => [l.id, l.name])))}</div>`;
  }
  return "";
}
async function pickSourceForReel() {
  const lib = (await api("/api/media")).filter(i => ["video", "audio", "image"].includes(i.kind) && !i.missing);
  const s = sheet(`${I("plus", 16)} Reele kaynak ekle`,
    `<div class="row" style="padding:0 0 10px"><div class="lbl small muted">Kütüphanedeki dosyalar. Yeni dosya için Bilgisayardan seç.</div><button class="btn" id="psnew">${I("plus", 14)} Bilgisayardan seç</button></div>
     <div class="mgrid small-grid">${lib.map(i => `<div class="mitem" data-id="${i.id}"><div class="mthumb ${i.kind}" style="background-image:url('/api/media/${i.id}/thumb?t=2')">${i.duration ? `<span class="mdur">${fdur(i.duration)}</span>` : ""}</div>
       <div class="mmeta"><b>${esc(i.name)}</b><span class="small muted">${SPEAK_TR[i.speaker] || KIND_TR[i.kind]}</span></div></div>`).join("") || '<div class="muted">Kütüphane boş.</div>'}</div>
     <div class="group"><div class="row"><div class="lbl"><b>Bu videoda yüzün görünüyor mu?</b><span>görünüyorsa sadece senkron kullanılır</span></div><select id="psp"><option value="">Kütüphanedeki gibi</option><option value="no">Hayır</option><option value="sometimes">Bazen</option><option value="yes">Evet</option></select></div></div>`);
  const addOne = async id => { try { if (R.dirty) await saveReel(); const r = await api(`/api/p/${R.name}/source`, { body: { media_id: id, speaker: $("#psp").value || undefined } });
      R.reel.sources = r.reel.sources; s.close(); toast("Kaynak eklendi. Bir plana ya da cümleye seçebilirsin."); if (!R.reel.beats.length) { addItem("beat"); } drawAll(); } catch (e) { fail(e); } };
  s.el.querySelectorAll(".mitem").forEach(m => m.onclick = () => addOne(m.dataset.id));
  $("#psnew").onclick = async () => { try { const r = await api("/api/media/pick", { body: {} }); if (r.items.length) addOne(r.items[0].id); } catch (e) { fail(e); } };
}
async function addSfxAtPlayhead() {
  const fx = R.fx || await api("/api/fx"); const t = +(($("#vid") || {}).currentTime || 0).toFixed(2);
  const s = sheet(`${I("wave", 16)} ${fmt(t)} noktasına ses efekti`,
    `<div class="fxgrid">${fx.sfx.map(x => `<div class="fxcard sfx" data-id="${x.id}"><div class="fxprev wavep" style="background-image:url('/api/media/${x.id}/thumb')"></div><b>${esc(x.name)}</b>
      <span><button class="btn" data-pl="${x.id}">${I("play", 12)}</button> <button class="btn primary" data-add="${x.id}">Ekle</button></span></div>`).join("")}</div>`);
  s.el.querySelectorAll("[data-pl]").forEach(b => b.onclick = e => { e.stopPropagation(); preview(`/api/media/${b.dataset.pl}/file`); });
  s.el.querySelectorAll("[data-add]").forEach(b => b.onclick = () => { const x = fx.sfx.find(y => y.id === b.dataset.add); snap();
    (R.reel.sfx = R.reel.sfx || []).push({ path: x.path, name: x.name, t, gain: 0.8, dur: x.duration || 0.6 }); R.sel = { type: "sfx", bi: -1, i: R.reel.sfx.length - 1 }; s.close(); drawAll(); });
}

// ---- inspector ----
function field(label, path, val, type = "number", opts) {
  const id = "f_" + path.replace(/\W/g, "_");
  let ctl;
  if (type === "select") ctl = `<select id="${id}" data-p="${path}">${opts.map(o => { const [v, l] = Array.isArray(o) ? o : [o, o]; return `<option value="${esc(v)}" ${String(v) === String(val ?? "") ? "selected" : ""}>${esc(l)}</option>`; }).join("")}</select>`;
  else if (type === "check") ctl = `<input type="checkbox" class="switch" id="${id}" data-p="${path}" ${val ? "checked" : ""}>`;
  else if (type === "textarea") return `<label for="${id}">${label}</label><span></span><textarea id="${id}" data-p="${path}">${esc(val)}</textarea>`;
  else ctl = `<input id="${id}" type="${type}" ${type === "number" ? 'step="0.05"' : ""} data-p="${path}" value="${esc(val ?? "")}">`;
  return `<label for="${id}">${label}</label>${ctl}`;
}
function drawInspector() {
  const el = $("#insp"); if (!el) return; const s = R.sel, r = R.reel, srcs = Object.keys(r.sources);
  r.audio = r.audio || { lufs: -14 }; r.audio.music = r.audio.music || {}; r.look = r.look || { filter: "none" }; r.sfx = r.sfx || [];
  const probs = rvalidate(r); let html = "";
  if (!s) {
    const L = layout(r);
    html = `<h4>Reel</h4><div class="f">${field("Ad", "name", r.name, "text")}${field("Altyazı y", "cap_y", r.cap_y)}</div>
      <div class="f"><label>Süre</label><span>${L.total.toFixed(1)} sn · ${r.beats.length} cümle</span><label>Çıktı</label><span class="small mono" style="word-break:break-all">${esc(r.output.split("/").pop())}</span></div>
      <h4>Uyarılar ${probs.length ? "" : '<span class="tag ok">temiz</span>'}</h4><div class="probs">${probs.map(p => `<div class="prob ${p.level}" data-go="${p.beat}:${p.shot ?? ""}">${esc(p.msg)}</div>`).join("")}</div>
      <h4>Kaynaklar</h4><div class="probs">${srcs.map(k => `<div class="small"><b>${esc(k)}</b> <span class="muted">${esc(r.sources[k].path.split("/").pop())} · yüz: ${esc(r.sources[k].speaker)}</span></div>`).join("")}</div>
      <h4>İpucu</h4><div class="probs small muted">Klibe tıkla: seç. Kenarından sürükle: kırp. Sağ tık: menü. Boşluk: oynat. ⌘B: oynatma çizgisinden böl.</div>`;
  } else if (s.type === "beat") {
    const b = r.beats[s.bi], P_ = `beats.${s.bi}`;
    html = `<h4>${I("wave", 14)} Cümle ${s.bi + 1} · ses</h4><div class="f">${field("Kaynak", `${P_}.audio.src`, b.audio.src, "select", srcs)}
      ${field("Başlangıç", `${P_}.audio.a`, b.audio.a)}${field("Bitiş", `${P_}.audio.b`, b.audio.b)}${field("Ses kazancı", `${P_}.gain`, b.gain ?? 1)}
      ${field("Altyazı y", `${P_}.cap_y`, b.cap_y ?? "")}</div>
      <div class="f"><label>Süre</label><span>${(b.audio.b - b.audio.a).toFixed(2)} sn</span></div>`;
  } else if (s.type === "shot") {
    const sh = r.beats[s.bi].shots[s.i], Q = `beats.${s.bi}.shots.${s.i}`, other = sh.kind === "clip" || sh.kind === "native";
    html = `<h4>${I("film", 14)} Cümle ${s.bi + 1} · plan ${s.i + 1}</h4><div class="f">
      ${field("Tür", `${Q}.kind`, sh.kind, "select", Object.entries(KIND))}
      ${other ? field("Kaynak", `${Q}.src`, sh.src, "select", srcs) + field("Klip içi sn", `${Q}.t`, sh.t ?? 0) : ""}
      ${sh.kind === "paper" ? field("Klasör", `${Q}.dir`, sh.dir ?? "paper", "text") + field("Animasyon sn", `${Q}.offset`, sh.offset ?? 0) : ""}
      ${field("Süre", `${Q}.dur`, sh.dur ?? "", "number")}
      ${sh.kind !== "paper" ? field("Yerleşim", `${Q}.layout`, sh.layout || (sh.kind === "native" ? "native" : "crop"), "select", [["crop", "Kırp (dikey)"], ["fit", "Sığdır"], ["native", "Olduğu gibi"]]) + field("Zoom", `${Q}.zoom`, sh.zoom ?? "") + field("Merkez x", `${Q}.cx`, sh.cx ?? "") + field("Merkez y", `${Q}.cy`, sh.cy ?? "") : ""}
      ${other ? field("Sesle senkron", `${Q}.synced`, sh.synced, "check") : ""}</div>
      <div class="probs">${probs.filter(p => p.beat === s.bi && p.shot === s.i).map(p => `<div class="prob ${p.level}">${esc(p.msg)}</div>`).join("") || '<div class="small muted">Süre boşsa cümlenin kalanını doldurur. Merkez x 4K piksel cinsinden.</div>'}</div>`;
  } else if (s.type === "sfx") {
    const e = r.sfx[s.i], Q = `sfx.${s.i}`;
    html = `<h4>${I("wave", 14)} Ses efekti</h4><div class="f">${field("Ad", `${Q}.name`, e.name, "text")}${field("Zaman (sn)", `${Q}.t`, e.t)}${field("Seviye", `${Q}.gain`, e.gain ?? 0.8)}</div>
      <div class="f"><label></label><span><button class="btn" data-act="playsfx" data-arg="${s.i}">${I("play", 12)} Dinle</button> <button class="btn danger" data-act="delsfx" data-arg="${s.i}">Sil</button></span></div>`;
  } else if (s.type === "cap") {
    const c = r.beats[s.bi].caps[s.i], Q = `beats.${s.bi}.caps.${s.i}`;
    html = `<h4>Altyazı</h4><div class="f">${field("Metin", `${Q}.text`, c.text, "textarea")}${field("Başlangıç", `${Q}.s`, c.s)}${field("Bitiş", `${Q}.e`, c.e)}</div><div class="probs small muted">Zamanlar kaynak videonun saniyesi.</div>`;
  } else {
    const t = r.beats[s.bi].titles[s.i], Q = `beats.${s.bi}.titles.${s.i}`;
    html = `<h4>Başlık şeridi</h4><div class="f">${field("Metin", `${Q}.text`, t.text, "text")}
      ${field("Boyut", `${Q}.size`, t.size, "select", [["huge", "Çok büyük"], ["big", "Büyük"], ["mid", "Orta"], ["sm", "Küçük"]])}
      ${field("Renk", `${Q}.col`, t.col, "select", [["y", "Sarı"], ["w", "Beyaz"]])}
      ${field("x", `${Q}.x`, t.x)}${field("y", `${Q}.y`, t.y)}${field("Açı", `${Q}.ang`, t.ang ?? 0)}
      ${field("Giriş sn", `${Q}.d0`, t.d0 ?? 0)}${field("Çıkış sn", `${Q}.d1`, t.d1 ?? "")}</div><div class="probs small muted">Giriş/çıkış cümle başından saniye. Çıkış boşsa cümle sonuna kadar.</div>`;
  }
  html += extraInspector(s);
  el.innerHTML = html;
  el.querySelectorAll("[data-act]").forEach(b => b.onclick = () => INSP_ACT[b.dataset.act](b.dataset.arg));
  el.querySelectorAll("[data-go]").forEach(p => p.onclick = () => { const [b, sh] = p.dataset.go.split(":"); R.sel = sh !== "" ? { type: "shot", bi: +b, i: +sh } : { type: "beat", bi: +b }; drawAll(); });
  el.querySelectorAll('input[type=text][data-p],textarea[data-p]').forEach(inp => {
    inp.onfocus = () => { inp._snap = JSON.stringify(R.reel); };
    inp.oninput = () => {   // text changes show on the video at once and save themselves
      if (inp._snap) { R.hist.push(inp._snap); R.fut = []; inp._snap = null; }
      const k = inp.dataset.p.split("."), last = k.pop(); let o = R.reel; for (const x of k) o = o[x]; o[last] = inp.value;
      if (inp.dataset.p === "name") $(".toolbar .title").textContent = inp.value;
      setDirty(true); buildOverlay(); clearTimeout(R.tlT); R.tlT = setTimeout(drawTimeline, 200);
    };
    inp.onchange = null;
  });
  el.querySelectorAll("[data-p]").forEach(inp => { if ((inp.type === "text" || inp.tagName === "TEXTAREA") && inp.oninput) return; inp.onchange = () => {
    snap(); let v = inp.type === "checkbox" ? inp.checked : inp.value;
    if (inp.type === "number") v = inp.value === "" ? null : +inp.value;
    const k = inp.dataset.p.split("."), last = k.pop(); let o = R.reel; for (const x of k) o = o[x];
    if (v === null && ["cap_y", "zoom", "cx", "cy", "dur", "d1"].includes(last)) delete o[last]; else o[last] = v;
    if (last === "name" && typeof v === "string" && inp.dataset.p.endsWith("transition.name")) { if (v.startsWith("asset:")) { o.name = "asset"; o.asset = v.slice(6); } else delete o.asset; }
    if (last === "lufs") o[last] = +v;
    if (last === "kind" && (v === "clip" || v === "native") && !o.src) o.src = Object.keys(R.reel.sources).find(x => R.reel.sources[x].speaker === "no") || Object.keys(R.reel.sources)[0];
    drawAll();
  }; });
  if (R.focusText) { const f = el.querySelector(".f textarea, .f input[type=text]"); if (f) { f.focus(); f.select(); } R.focusText = false; }
}

// ---- live text layer on the video (same layout as the render: 1080x1920 canvas) ----
const TITLE_FONT = { huge: [150, "Futura-CondensedExtraBold, Futura, sans-serif", 800], big: [130, "Futura-CondensedExtraBold, Futura, sans-serif", 800],
                     mid: [72, "AvenirNextCondensed-Bold, 'Avenir Next Condensed', sans-serif", 700], sm: [60, "AvenirNextCondensed-DemiBold, 'Avenir Next Condensed', sans-serif", 600] };
const easeOut = x => { x = clamp(x, 0, 1); return 1 - (1 - x) ** 3; };
function fitOverlay() { const st = document.querySelector(".stage"), o = $("#ovl"); if (!st || !o) return; o.style.transform = `scale(${st.clientWidth / 1080})`; }
function buildOverlay() {
  const o = $("#ovl"); if (!o || !R) return;
  if (!R.live) { o.innerHTML = ""; return; }
  const L = layout(R.reel), b = R.reel.beats, items = [];
  L.caps.forEach(c => { const cap = b[c.bi].caps[c.ci]; items.push({ type: "cap", bi: c.bi, i: c.ci, a: c.start, z: c.start + c.dur, text: cap.text, y: b[c.bi].cap_y || R.reel.cap_y || 1400 }); });
  L.titles.forEach(c => { const t = b[c.bi].titles[c.ti]; items.push({ type: "title", bi: c.bi, i: c.ti, a: c.start, z: c.start + c.dur - 0.05, t }); });
  R.ovItems = items;
  o.innerHTML = items.map((x, k) => {
    const sel = selIs(x.type, x.bi, x.i) ? " sel" : "";
    if (x.type === "cap") return `<div class="ocap${sel}" data-k="${k}" style="top:${x.y}px" title="Tıkla: seç · Çift tıkla: düzenle">${esc(x.text)}</div>`;
    const [fs, ff, fw] = TITLE_FONT[x.t.size] || TITLE_FONT.mid, big = x.t.size === "big" || x.t.size === "huge";
    return `<div class="otitle${sel}" data-k="${k}" style="left:${x.t.x + 14}px;top:${x.t.y + 14}px;font:${fw} ${fs}px/1 ${ff};padding:${big ? "10px 34px" : "14px 30px"};
      background:${x.t.col === "y" ? "#ffc42e" : "#f4f0e7"};--r:${-(x.t.ang || 0)}deg" title="Tıkla: seç · Çift tıkla: düzenle">${esc(x.t.text)}</div>`;
  }).join("");
  // like the render: a strip wider than 1020 px is scaled down, never cut
  o.querySelectorAll(".otitle").forEach(el => { el.style.display = "block"; el.style.visibility = "hidden"; const w = el.offsetWidth;
    if (w > 1020) el.style.fontSize = (parseFloat(getComputedStyle(el).fontSize) * 1020 / w).toFixed(1) + "px"; el.style.visibility = ""; el.style.display = "none"; });
  fitOverlay(); R.ovLast = -1; drawOverlay(true);
  o.querySelectorAll("[data-k]").forEach(el => {
    const x = items[+el.dataset.k];
    el.onmousedown = e => e.stopPropagation();
    el.onclick = e => { e.stopPropagation(); if (el.isContentEditable) return; R.sel = { type: x.type, bi: x.bi, i: x.i }; const v = $("#vid"); if (v && !v.paused) v.pause(); R.focusText = true; drawTimeline(); drawInspector(); markOverlaySel(); };
    el.ondblclick = e => { e.stopPropagation(); inlineEdit(el, x); };
    el.oncontextmenu = e => { e.preventDefault(); e.stopPropagation(); R.sel = { type: x.type, bi: x.bi, i: x.i }; drawTimeline(); drawInspector(); markOverlaySel();
      showMenu(e.clientX, e.clientY, [{ icon: "wand", label: "Yazıyı düzenle", keys: KB("↩"), run: () => inlineEdit(el, x) },
        { icon: "dup", label: "Çoğalt", keys: KB("⌘", "D"), run: opDup }, { icon: "trash", label: "Sil", keys: KB("⌫"), run: opDelete }]); };
  });
}
function markOverlaySel() { document.querySelectorAll("#ovl [data-k]").forEach(el => { const x = R.ovItems[+el.dataset.k]; el.classList.toggle("sel", selIs(x.type, x.bi, x.i)); }); }
function inlineEdit(el, x) {
  const v = $("#vid"); if (v && !v.paused) v.pause();
  R.sel = { type: x.type, bi: x.bi, i: x.i }; drawTimeline(); drawInspector(); markOverlaySel();
  const before = JSON.stringify(R.reel); el.contentEditable = "plaintext-only"; el.classList.add("editing"); el.focus();
  const rg = document.createRange(); rg.selectNodeContents(el); const sl = getSelection(); sl.removeAllRanges(); sl.addRange(rg);
  const obj = x.type === "cap" ? R.reel.beats[x.bi].caps[x.i] : R.reel.beats[x.bi].titles[x.i];
  el.oninput = () => { if (before) { if (!el._pushed) { R.hist.push(before); R.fut = []; el._pushed = true; } }
    obj.text = el.innerText.replace(/\n+/g, " ").trimStart(); setDirty(true); clearTimeout(R.tlT); R.tlT = setTimeout(() => { drawTimeline(); const f = $("#insp textarea, #insp .f input[type=text]"); if (f && document.activeElement !== f) f.value = obj.text; }, 150); };
  el.onkeydown = e => { e.stopPropagation(); if (e.key === "Enter" || e.key === "Escape") { e.preventDefault(); el.blur(); } };
  el.onblur = () => { el.contentEditable = "false"; el.classList.remove("editing"); obj.text = obj.text.trim(); buildOverlay(); drawInspector(); };
}
function drawOverlay(force) {
  const o = $("#ovl"), v = $("#vid"); if (!o || !R || !R.live || !R.ovItems) return;
  const t = v.currentTime; if (!force && t === R.ovLast) return; R.ovLast = t;
  o.querySelectorAll("[data-k]").forEach(el => {
    const x = R.ovItems[+el.dataset.k], selected = selIs(x.type, x.bi, x.i), on = t >= x.a && t < x.z;
    if (el.isContentEditable) { el.style.display = "block"; el.style.opacity = 1; return; }
    if (!on && !(selected && v.paused)) { el.style.display = "none"; return; }
    el.style.display = "block";
    if (x.type === "cap") { const pop = on ? 1 + 0.08 * (1 - easeOut((t - x.a) / 0.12)) : 1; el.style.transform = `translate(-50%,-50%) scale(${pop})`; el.style.opacity = on ? 1 : 0.55; }
    else { const q = on ? Math.min(easeOut((t - x.a) / 0.3), easeOut((x.z - t) / 0.25)) : 0.55; el.style.opacity = q; el.style.transform = `translateX(${-(1 - (on ? q : 1)) * 220}px) rotate(var(--r))`; }
  });
}

// =====================================================================
// Share sheet + queue
// =====================================================================
async function openShare({ project, title, autogen }) {
  const st = await api("/api/settings"), acc = st.accounts;
  const plats = [["youtube", "YouTube Shorts"], ["instagram", "Instagram"], ["x", "X"], ["linkedin", "LinkedIn"]];
  const scr = document.createElement("div"); scr.className = "scrim";
  scr.innerHTML = `<div class="sheet"><h3>${I("share", 16)} Paylaş · ${esc(title || project)}</h3>
    <div class="group"><div class="row"><div class="lbl"><b>Video</b><span class="mono">${esc(project)} son render</span></div></div>
      ${plats.map(([k, n]) => `<div class="row"><div class="lbl"><b>${n}</b><span>${acc[k].connected ? esc(acc[k].handle || "bağlı") : "bağlı değil · Hesaplar'dan bağla"}</span></div><input type="checkbox" class="switch" data-pl="${k}" ${acc[k].connected ? "" : "disabled"}></div>`).join("")}
    </div>
    <div class="row" style="padding:0 2px"><div class="lbl"><b>Açıklama</b></div><button class="btn" id="sgen">${I("wand", 14)} AI ile yaz</button></div>
    <textarea id="scap" rows="6" placeholder="Paylaşım metni"></textarea>
    <div class="group"><div class="row"><div class="lbl"><b>Zaman</b><span>boş bırakırsan onaylayınca hemen paylaşılır</span></div><input type="datetime-local" id="swhen"></div></div>
    <div class="actions"><button class="btn" id="sx">Vazgeç</button><button class="btn" id="sdraft">Taslak olarak kuyruğa ekle</button><button class="btn primary" id="sgo">Onayla ve paylaş</button></div></div>`;
  document.body.appendChild(scr);
  const close = () => scr.remove(); scr.onclick = e => { if (e.target === scr) close(); }; $("#sx").onclick = close;
  const gen = async () => { $("#sgen").disabled = true; $("#sgen").innerHTML = "yazıyor…";
    try { const r = await api("/api/ai/caption", { body: { project } }); $("#scap").value = r.text; toast(`${r.provider} · ${r.model}`); } catch (e) { fail(e); }
    $("#sgen").disabled = false; $("#sgen").innerHTML = `${I("wand", 14)} AI ile yaz`; };
  $("#sgen").onclick = gen; if (autogen) gen();
  const send = async approved => {
    const platforms = [...scr.querySelectorAll("[data-pl]:checked")].map(x => x.dataset.pl), text = $("#scap").value.trim();
    if (!platforms.length) return toast("En az bir hesap seç");
    if (!text) return toast("Açıklama boş");
    const w = $("#swhen").value ? new Date($("#swhen").value).getTime() / 1000 : null;
    if (approved && !await ask(`${platforms.join(", ")} hesaplarında ${w ? new Date(w * 1000).toLocaleString("tr-TR") + " tarihinde" : "hemen"} paylaşılacak.`, "Onayla ve paylaş")) return;
    try { await api("/api/posts", { body: { project, captions: { default: text }, platforms, when: w, approved, source: "arayüz" } }); close(); toast(approved ? "Kuyruğa alındı, paylaşılacak" : "Taslak kuyruğa eklendi"); refreshPending(); }
    catch (e) { fail(e); }
  };
  $("#sdraft").onclick = () => send(false); $("#sgo").onclick = () => send(true);
}
async function refreshPending() { try { const q = await api("/api/posts"); A.pending = q.filter(p => Object.values(p.targets).some(t => t.status === "onay bekliyor" || t.status === "hata")).length; renderNav(); } catch (e) { } }
const STAG = { "onay bekliyor": "warn", "bekliyor": "", "paylaşılıyor": "warn", "paylaşıldı": "ok", "hata": "err", "iptal": "" };
async function viewQueue() {
  R = null;
  toolbar(`<span class="title">Paylaşım kuyruğu</span><span class="sub">otomasyonun hazırladığı gönderiler önce burada onay bekler</span><span class="sp"></span><button class="btn" id="qref">Yenile</button>`);
  $("#qref").onclick = viewQueue;
  const q = await api("/api/posts"); const v = $("#view"); v.className = "view";
  v.innerHTML = `<div class="page" style="max-width:860px"><div class="group">${q.length ? q.map(p => `<div class="post">
      ${p.project ? `<div class="pvwrap" data-play="${esc(p.project)}" title="Büyük izle"><video class="pv" muted playsinline preload="metadata" src="/api/p/${esc(p.project)}/output#t=1"></video><span class="pvbtn">${I("play", 18)}</span></div>` : `<div class="pv"></div>`}
      <div><div class="small muted">${new Date(p.when * 1000).toLocaleString("tr-TR")} · ${esc(p.source)}${p.project ? " · " + esc(p.project) : ""}</div>
        <div class="cap" contenteditable="${Object.values(p.targets).some(t => ["onay bekliyor", "bekliyor", "hata"].includes(t.status))}" data-cap="${p.id}">${esc(p.captions.default || "")}</div>
        ${p.captions.note ? `<div class="small" style="color:var(--orange)">${esc(p.captions.note)}</div>` : ""}
        ${((p.options || {}).youtube || {}).publish_at ? `<div class="small" style="margin-top:4px">${I("play", 12)} YouTube'da yayın: <b>${new Date(p.options.youtube.publish_at * 1000).toLocaleString("tr-TR", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</b> · onaylayınca hemen yüklenir, o saatte kendiliğinden yayına girer</div>` : ""}
        <div class="tg">${Object.entries(p.targets).map(([k, t]) => `<span class="tag ${STAG[t.status] || ""}" title="${esc(t.error || "")}">${k} · ${t.status}</span>${t.url ? `<a class="small" href="${esc(t.url)}" target="_blank">aç</a>` : ""}`).join("")}</div>
        ${Object.values(p.targets).filter(t => t.error).map(t => `<div class="small" style="color:var(--red);margin-top:4px">${esc(t.error)}</div>`).join("")}</div>
      <div class="acts">${Object.values(p.targets).some(t => t.status === "onay bekliyor" || t.status === "hata") ? `<button class="btn primary" data-ap="${p.id}">${I("check", 14)} Onayla</button>` : ""}
        ${Object.values(p.targets).some(t => ["onay bekliyor", "bekliyor"].includes(t.status)) ? `<button class="btn" data-cn="${p.id}">İptal</button>` : ""}
        <button class="btn danger" data-dl="${p.id}">${I("trash", 14)}</button></div></div>`).join("") : '<div class="list-empty">Kuyruk boş. Bir reelde Paylaş\'a bas ya da otomasyonu aç.</div>'}</div></div>`;
  v.querySelectorAll("[data-play]").forEach(el => el.onclick = () => {
    const p = q.find(x => x.project === el.dataset.play) || {};
    const s = sheet(esc(((p.captions || {}).default || "").split("\n")[0] || el.dataset.play),
      `<video class="bigplay" controls autoplay playsinline src="/api/p/${esc(el.dataset.play)}/output?t=${Date.now()}"></video>`,
      Object.values(p.targets || {}).some(t => t.status === "onay bekliyor") ? `<button class="btn" data-x>Kapat</button><button class="btn primary" id="bpok">${I("check", 14)} Onayla</button>` : null);
    const ok = s.el.querySelector("#bpok"); if (ok) ok.onclick = () => { s.el.querySelector("video").pause(); s.close(); v.querySelector(`[data-ap="${p.id}"]`).click(); };
    s.el.addEventListener("click", e => { if (e.target === s.el || e.target.hasAttribute("data-x")) s.el.querySelector("video")?.pause(); });
  });
  v.querySelectorAll("[data-cap]").forEach(el => el.onblur = async () => { try { const p = q.find(x => x.id === el.dataset.cap); await api(`/api/posts/${p.id}`, { body: { captions: { ...p.captions, default: el.innerText } } }); toast("Metin güncellendi"); } catch (e) { fail(e); } });
  v.querySelectorAll("[data-ap]").forEach(b => b.onclick = async () => { const p = q.find(x => x.id === b.dataset.ap);
    const pa = ((p.options || {}).youtube || {}).publish_at;
    if (!await ask(`${Object.keys(p.targets).join(", ")} hesabında paylaşılacak${pa ? ". YouTube'da yayın: " + new Date(pa * 1000).toLocaleString("tr-TR", { hour: "2-digit", minute: "2-digit", day: "numeric", month: "short" }) : ""}.`, "Onayla ve yükle")) return;
    try { await api(`/api/posts/${p.id}`, { body: { approve: true } }); toast("Onaylandı"); viewQueue(); refreshPending(); } catch (e) { fail(e); } });
  v.querySelectorAll("[data-cn]").forEach(b => b.onclick = async () => { if (!await ask("Bu gönderi iptal edilsin mi? Hiçbir şey yüklenmez.", "İptal et", true)) return; await api(`/api/posts/${b.dataset.cn}`, { body: { cancel: true } }); viewQueue(); refreshPending(); });
  v.querySelectorAll("[data-dl]").forEach(b => b.onclick = async () => { if (!await ask("Gönderi kuyruktan silinsin mi? Paylaşılmış bir gönderiyse platformdan silinmez.", "Sil", true)) return; await api(`/api/posts/${b.dataset.dl}`, { method: "DELETE" }); viewQueue(); refreshPending(); });
  A.poll = setInterval(async () => { const n = await api("/api/posts"); if (JSON.stringify(n.map(p => p.targets)) !== JSON.stringify(q.map(p => p.targets)) && !document.activeElement.isContentEditable) viewQueue(); }, 5000);
}

// =====================================================================
// Settings: models
// =====================================================================
const PROV = {
  anthropic: { name: "Claude (Anthropic)", color: "#d97757", ch: "A", key: "anthropic_api_key", hint: "console.anthropic.com > API Keys" },
  openrouter: { name: "OpenRouter", color: "#6467f2", ch: "OR", key: "openrouter_api_key", hint: "openrouter.ai/keys · yüzlerce modele tek anahtar" },
  ollama: { name: "Ollama (yerel)", color: "#111", ch: "O", hint: "Bilgisayarındaki açık kaynak modeller. Kurulu değilse: ollama.com" },
  elevenlabs: { name: "ElevenLabs", color: "#000", ch: "11", key: "elevenlabs_api_key", hint: "elevenlabs.io > Profile > API key · seslendirme" },
};
async function viewModels() {
  R = null; toolbar(`<span class="title">Modeller</span><span class="sub">anahtarlar macOS Anahtar Zinciri'nde saklanır</span><span class="sp"></span>`);
  const st = await api("/api/settings"); A.settings = st; const pv = st.providers;
  const v = $("#view"); v.className = "view";
  v.innerHTML = `<div class="page"><h2>Modeller</h2><p>Metin işleri (paylaşım metni, otomasyon) için varsayılan sağlayıcıyı seç. Ses için ElevenLabs.</p>
    <div class="group"><div class="row"><div class="lbl"><b>Varsayılan metin modeli</b><span>açık olan ve modeli seçilmiş sağlayıcılardan</span></div>
      <div class="seg" id="defprov">${["anthropic", "openrouter", "ollama"].map(k => `<button data-k="${k}" class="${st.default_text_provider === k ? "on" : ""}">${PROV[k].name.split(" ")[0]}</button>`).join("")}</div></div></div>
    ${Object.entries(PROV).map(([k, p]) => `<div class="group-title"><span class="prov-logo" style="background:${p.color}">${p.ch}</span>${p.name}<span class="sp" style="flex:1"></span><span id="st_${k}">${pv[k].has_key || k === "ollama" ? "" : '<span class="tag">anahtar yok</span>'}</span></div>
      <div class="group">
        <div class="row"><div class="lbl"><b>Açık</b><span>${p.hint}</span></div><input type="checkbox" class="switch" data-en="${k}" ${pv[k].enabled ? "checked" : ""}></div>
        ${p.key ? `<div class="row"><div class="lbl"><b>API anahtarı</b><span>${pv[k].has_key ? "Anahtar Zinciri'nde kayıtlı" : "henüz yok"}</span></div><input type="password" data-key="${p.key}" placeholder="${pv[k].has_key ? "•••••••• değiştirmek için yaz" : "yapıştır"}" autocomplete="off"></div>` : ""}
        ${k === "ollama" ? `<div class="row"><div class="lbl"><b>Adres</b></div><input type="text" data-ourl value="${esc(pv.ollama.base_url)}"></div>` : ""}
        <div class="row"><div class="lbl"><b>${k === "elevenlabs" ? "Ses" : "Model"}</b><span id="mc_${k}"></span></div>
          <input type="search" list="ml_${k}" data-model="${k}" value="${esc(k === "elevenlabs" ? pv[k].voice_id : pv[k].default_model)}" placeholder="listeden seç ya da yaz"><datalist id="ml_${k}"></datalist></div>
        <div class="row"><div class="lbl"></div><button class="btn" data-load="${k}">Modelleri getir</button><button class="btn" data-test="${k}">Bağlantıyı test et</button></div>
      </div>`).join("")}
    <div class="group-title">${I("bolt", 14)} Hızlı deneme</div>
    <div class="group"><div class="chat" id="chat"><div class="small muted">Varsayılan modelle konuş. Bağlantıyı denemenin en hızlı yolu.</div></div>
      <div class="row"><input type="text" id="chatin" style="flex:1;width:auto" placeholder="Mesaj yaz, Enter"><button class="btn" id="ttsbtn">${I("mic", 14)} Seslendir</button></div></div>
  </div>`;
  const saveP = async (patch, secrets) => { try { const r = await api("/api/settings", { body: { patch, secrets } }); A.settings = r.settings; toast("Kaydedildi"); return r; } catch (e) { fail(e); } };
  v.querySelectorAll("#defprov button").forEach(b => b.onclick = async () => { await saveP({ default_text_provider: b.dataset.k }); v.querySelectorAll("#defprov button").forEach(x => x.classList.toggle("on", x === b)); });
  v.querySelectorAll("[data-en]").forEach(x => x.onchange = () => saveP({ providers: { [x.dataset.en]: { enabled: x.checked } } }));
  v.querySelectorAll("[data-key]").forEach(x => x.onchange = async () => { if (!x.value.trim()) return; await saveP(null, { [x.dataset.key]: x.value.trim() }); x.value = ""; x.placeholder = "•••••••• değiştirmek için yaz"; });
  v.querySelector("[data-ourl]").onchange = e => saveP({ providers: { ollama: { base_url: e.target.value.trim() } } });
  v.querySelectorAll("[data-model]").forEach(x => x.onchange = () => { const k = x.dataset.model; saveP({ providers: { [k]: k === "elevenlabs" ? { voice_id: x.value.trim() } : { default_model: x.value.trim() } } }); });
  const load = async k => { const c = $("#mc_" + k); c.textContent = "getiriliyor…";
    try { const r = await api(`/api/ai/models?provider=${k}`); $("#ml_" + k).innerHTML = r.models.map(m => `<option value="${esc(m.id)}">${esc(m.name)}${m.ctx ? " · " + Math.round(m.ctx / 1000) + "k" : ""}</option>`).join(""); c.textContent = `${r.models.length} ${k === "elevenlabs" ? "ses" : "model"} · kutuya tıklayıp ara`; }
    catch (e) { c.textContent = e.message; } };
  v.querySelectorAll("[data-load]").forEach(b => b.onclick = () => load(b.dataset.load));
  v.querySelectorAll("[data-test]").forEach(b => b.onclick = async () => { const k = b.dataset.test, s = $("#st_" + k); s.innerHTML = '<span class="tag">deneniyor</span>';
    try { const r = await api("/api/ai/test", { body: { provider: k } }); s.innerHTML = `<span class="tag ok">${esc(r.detail)}</span>`; } catch (e) { s.innerHTML = `<span class="tag err" title="${esc(e.message)}">hata</span>`; toast(e.message, 6000); } });
  for (const k of Object.keys(PROV)) if (pv[k].has_key || (k === "ollama" && pv[k].enabled)) load(k);
  const hist = [];
  $("#chatin").onkeydown = async e => { if (e.key !== "Enter" || !e.target.value.trim()) return; const t = e.target.value.trim(); e.target.value = "";
    hist.push({ role: "user", content: t }); const c = $("#chat"); c.insertAdjacentHTML("beforeend", `<div class="m u">${esc(t)}</div>`);
    const w = document.createElement("div"); w.className = "m a"; w.textContent = "…"; c.appendChild(w); c.scrollTop = 1e9;
    try { const r = await api("/api/ai/chat", { body: { messages: hist } }); w.textContent = r.text; hist.push({ role: "assistant", content: r.text }); w.title = r.provider; } catch (err) { w.textContent = "Hata: " + err.message; hist.pop(); }
    c.scrollTop = 1e9; };
  $("#ttsbtn").onclick = async () => { const t = $("#chatin").value.trim() || "Merhaba, ben Biar. Sui Basecamp'ten selamlar."; toast("Seslendiriliyor…");
    try { const r = await api("/api/ai/tts", { body: { text: t } }); new Audio(r.url).play(); } catch (e) { fail(e); } };
}

// =====================================================================
// Settings: accounts
// =====================================================================
async function viewAccounts() {
  R = null; toolbar(`<span class="title">Hesaplar</span><span class="sub">otomatik paylaşım için</span><span class="sp"></span>`);
  const d = await api("/api/social"), v = $("#view"); v.className = "view";
  const COL = { x: "#000", linkedin: "#0a66c2", instagram: "linear-gradient(45deg,#f9ce34,#ee2a7b,#6228d7)", youtube: "#ff0033" };
  v.innerHTML = `<div class="page"><h2>Hesaplar</h2><p>Her platform için kendi geliştirici uygulamanı açıp client id ve secret'ı buraya gir. Sonra Bağlan'a bas, giriş tarayıcıda yapılır, şifren bu uygulamaya hiç gelmez.</p>
    <div class="group"><div class="row"><div class="lbl"><b>Callback (redirect) adresi</b><span>uygulamanın ayarlarına bunu yaz</span></div><span class="mono">${esc(d.redirect)}</span><button class="btn" id="cpy">Kopyala</button></div></div>
    ${Object.entries(d.platforms).sort(([a], [b]) => (b === "youtube") - (a === "youtube")).map(([k, p]) => `<div class="group-title"><span class="prov-logo" style="background:${COL[k]}">${p.name[0]}</span>${p.name}<span style="flex:1"></span>${p.connected ? `<span class="tag ok">${esc(p.handle || "bağlı")}</span>` : '<span class="tag">bağlı değil</span>'}</div>
      <div class="group">
        <div class="row stack"><span class="small muted">${esc(p.help)}</span></div>
        <div class="row"><div class="lbl"><b>Client ID</b></div><input type="text" data-cid="${k}" value="${esc(p.client_id)}"></div>
        <div class="row"><div class="lbl"><b>Client secret</b><span>${p.has_secret ? "Anahtar Zinciri'nde kayıtlı" : "henüz yok"}</span></div><input type="password" data-sec="${k}" placeholder="${p.has_secret ? "•••••••• değiştirmek için yaz" : "yapıştır"}" autocomplete="off"></div>
        <div class="row"><div class="lbl"><b>Otomatik paylaş</b><span>açıksa otomasyonun hazırladığı gönderiler onay beklemeden paylaşılır</span></div><input type="checkbox" class="switch" data-auto="${k}" ${p.auto_post ? "checked" : ""}></div>
        ${k === "youtube" ? `<div class="row"><div class="lbl"><b>Görünürlük</b><span>yüklenen videonun ilk durumu</span></div><select data-ytp>${[["public", "Herkese açık"], ["unlisted", "Liste dışı"], ["private", "Gizli"]].map(([v2, n]) => `<option value="${v2}" ${p.privacy === v2 ? "selected" : ""}>${n}</option>`).join("")}</select></div>
        <div class="row"><div class="lbl"><b>Başlığa #Shorts ekle</b><span>metnin ilk satırı başlık, gerisi açıklama olur · sıralama kredileri açıklamaya otomatik eklenir</span></div><input type="checkbox" class="switch" data-yts ${p.shorts_tag !== false ? "checked" : ""}></div>` : ""}
        <div class="row"><div class="lbl"></div>${p.connected ? `<button class="btn danger" data-dis="${k}">Bağlantıyı kes</button>` : ""}<button class="btn primary" data-con="${k}">${I("link", 14)} ${p.connected ? "Yeniden bağlan" : "Bağlan"}</button></div>
        <div class="row"><div class="lbl"><b>Kodu yapıştır</b><span>girişten sonra sayfa açılmazsa adres çubuğundaki adresi buraya yapıştır</span></div><input type="text" data-paste="${k}" placeholder="https://…?code=…&state=…"></div>
      </div>`).join("")}</div>`;
  $("#cpy").onclick = () => navigator.clipboard.writeText(d.redirect).then(() => toast("Kopyalandı"));
  const save = (patch, secrets) => api("/api/settings", { body: { patch, secrets } }).then(() => toast("Kaydedildi")).catch(fail);
  v.querySelectorAll("[data-cid]").forEach(x => x.onchange = () => save({ accounts: { [x.dataset.cid]: { client_id: x.value.trim() } } }));
  v.querySelectorAll("[data-sec]").forEach(x => x.onchange = async () => { if (!x.value.trim()) return; await save(null, { [`${x.dataset.sec}_client_secret`]: x.value.trim() }); x.value = ""; viewAccounts(); });
  v.querySelectorAll("[data-ytp]").forEach(x => x.onchange = () => save({ accounts: { youtube: { privacy: x.value } } }));
  v.querySelectorAll("[data-yts]").forEach(x => x.onchange = () => save({ accounts: { youtube: { shorts_tag: x.checked } } }));
  v.querySelectorAll("[data-auto]").forEach(x => x.onchange = async () => {
    if (x.checked && !await ask("Otomatik paylaşım açılırsa otomasyonun hazırladığı gönderiler sana sormadan bu hesapta yayınlanır.", "Aç")) { x.checked = false; return; }
    save({ accounts: { [x.dataset.auto]: { auto_post: x.checked } } }); });
  v.querySelectorAll("[data-con]").forEach(b => b.onclick = async () => { try { const r = await api(`/api/social/${b.dataset.con}/connect`, { method: "POST" }); window.open(r.url, "_blank");
    toast("Girişi tarayıcıda tamamla, sonra bu sayfaya dön", 5000); const t0 = Date.now(), iv = setInterval(async () => { const s = await api("/api/social"); if (s.platforms[b.dataset.con].connected || Date.now() - t0 > 300000) { clearInterval(iv); if (location.hash === "#/accounts") viewAccounts(); } }, 3000); } catch (e) { fail(e); } });
  v.querySelectorAll("[data-dis]").forEach(b => b.onclick = async () => { if (!await ask("Bağlantı kesilsin mi? Token Anahtar Zinciri'nden silinir.", "Bağlantıyı kes", true)) return; await api(`/api/social/${b.dataset.dis}/disconnect`, { method: "POST" }); viewAccounts(); });
  v.querySelectorAll("[data-paste]").forEach(x => x.onchange = async () => { try { const r = await api(`/api/social/${x.dataset.paste}/paste`, { body: { url: x.value } }); toast("Bağlandı: " + r.handle); viewAccounts(); } catch (e) { fail(e); } });
}

// =====================================================================
// Settings: automation + API
// =====================================================================
async function viewAutomation() {
  R = null; toolbar(`<span class="title">Otomasyon ve API</span><span class="sp"></span>`);
  const st = await api("/api/settings"), ep = await api("/api"), rule = st.automation.after_render || {};
  const v = $("#view"); v.className = "view";
  const py = `${st.root}/.venv/bin/python`, mcp = `${st.root}/biaredit/mcp_server.py`;
  v.innerHTML = `<div class="page"><h2>Otomasyon ve API</h2><p>Bu uygulamayı bir insan da, bir yapay zeka ajanı da aynı şekilde kullanır: arayüzün yaptığı her şey API'den ve MCP'den de yapılabilir.</p>
    <div class="group-title">${I("bolt", 14)} Kural: render bitince</div>
    <div class="group">
      <div class="row"><div class="lbl"><b>Paylaşım taslağı hazırla</b><span>reel render'ı bitince varsayılan modelle açıklama yazar ve kuyruğa ekler</span></div><input type="checkbox" class="switch" id="arule" ${rule.enabled ? "checked" : ""}></div>
      <div class="row"><div class="lbl"><b>Hesaplar</b><span>otomatik paylaş kapalıysa kuyrukta onay bekler</span></div>${["youtube", "instagram", "x", "linkedin"].map(k => `<label class="small"><input type="checkbox" data-rp="${k}" ${(rule.platforms || []).includes(k) ? "checked" : ""}> ${k}</label>`).join(" ")}</div>
      <div class="row stack"><div class="lbl"><b>Açıklama talimatı</b><span>modelin her seferinde aldığı yönerge</span></div><textarea id="aprompt">${esc(st.automation.caption_prompt)}</textarea></div>
    </div>
    <div class="group-title">${I("cpu", 14)} Claude ve diğer ajanlar (MCP)</div>
    <div class="group"><div class="row stack"><span class="small muted">Claude Code'a bağlamak için terminalde bir kez çalıştır. Claude Desktop ve diğer MCP istemcileri de aynı komutu kullanır.</span>
      <code class="mono" style="user-select:all;background:var(--hover);padding:8px;border-radius:6px;display:block">claude mcp add biar-edit -- ${py} -I ${mcp}</code>
      <span class="small muted">Araçlar: projeleri listele, reeli oku ve düzenle, render başlat, durum, paylaşım metni üret, kuyruğa gönderi ekle (onaylı paylaşım yalnızca arayüzden ya da otomatik paylaş açık hesaplarda).</span></div></div>
    <div class="group-title">${I("key", 14)} HTTP API</div>
    <div class="group">
      <div class="row"><div class="lbl"><b>API anahtarı</b><span>değiştiren her istekte X-Biar-Token başlığı olarak gönder</span></div><span class="mono" id="tok">••••••••</span><button class="btn" id="tshow">Göster</button><button class="btn" id="tcopy">Kopyala</button></div>
      <div class="row stack"><span class="small muted">Terminalden: <span class="mono" style="user-select:all">security find-generic-password -s biar-edit -a api_token -w</span></span>
        <code class="mono" style="white-space:pre-wrap;background:var(--hover);padding:8px;border-radius:6px;display:block">curl -s localhost:8790/api/projects
curl -s -X POST localhost:8790/api/p/reel01/render -H "X-Biar-Token: $TOKEN"</code></div>
      ${ep.map(e => `<div class="row"><span class="tag" style="min-width:52px;justify-content:center">${e.method}</span><span class="mono" style="min-width:250px">${esc(e.path)}</span><span class="small muted" style="flex:1">${esc(e.info)}</span></div>`).join("")}
    </div></div>`;
  const saveRule = () => api("/api/settings", { body: { patch: { automation: { after_render: { enabled: $("#arule").checked, platforms: [...v.querySelectorAll("[data-rp]:checked")].map(x => x.dataset.rp) } } } } }).then(() => toast("Kural kaydedildi")).catch(fail);
  $("#arule").onchange = saveRule; v.querySelectorAll("[data-rp]").forEach(x => x.onchange = saveRule);
  $("#aprompt").onchange = e => api("/api/settings", { body: { patch: { automation: { caption_prompt: e.target.value } } } }).then(() => toast("Kaydedildi")).catch(fail);
  $("#tshow").onclick = () => { const t = $("#tok"); t.textContent = t.textContent.startsWith("•") ? window.BIAR_TOKEN : "••••••••"; };
  $("#tcopy").onclick = () => navigator.clipboard.writeText(window.BIAR_TOKEN).then(() => toast("Kopyalandı"));
}

// ---------- boot ----------
(async function boot() {
  try { await refreshProjects(); $("#srvdot").className = "dot ok"; $("#srvtxt").textContent = "sunucu çalışıyor · 8790"; }
  catch (e) { $("#srvdot").className = "dot bad"; $("#srvtxt").textContent = "sunucuya ulaşılamıyor"; }
  refreshPending(); route();
  addEventListener("resize", () => { if (R && $("#tli")) drawTimeline(); });
})();
