// biar-edit · long video editor (transcript-based cuts and cutaways), same look as the reel editor.
"use strict";
const FILL = /^\W*(uh+|um+|uhm+|umm+|er+|ah+|eh+|hmm+)\W*$/i;
let F = null;   // film editor state
const fon = o => o.on !== false;

async function viewFilm(name, d) {
  R = null;
  F = { name, P: d.project, W: d.words, hist: [], fut: [], dirty: false, selA: null, selB: null, drag: false, stopAt: null, edit: true, follow: true,
        tab: "tx", pps: 0, sel: null, last: -1 };
  const P = F.P;
  toolbar(`<span class="title">${esc(P.name || name)}</span><span class="sub" id="fdirty"></span><span class="sp"></span>
    <button class="btn icon" id="fundo" title="Geri al ⌘Z">${I("undo")}</button><button class="btn icon" id="fredo" title="Yinele ⇧⌘Z">${I("redo")}</button>
    <button class="btn" id="fsave">${I("save", 14)} Kaydet</button>
    <button class="btn primary" id="frender">${I("render", 14)} <span id="flab">4K Render</span></button>`);
  const v = $("#view"); v.className = "view fill";
  const others = Object.keys(P.sources).filter(k => k !== P.main);
  v.innerHTML = `<div class="editor film">
      <div class="stagewrap"><div class="stage wide"><video id="fv" playsinline preload="auto"></video><video id="fov" muted playsinline preload="auto"></video><img id="foi" alt="">
        <span class="fbadge" id="fbadge" hidden></span></div></div>
      <div class="insp fpane"><div class="fseg"><div class="seg" id="ftabs">${[["tx", "Transkript"], ["cuts", "Kesimler"], ["ovs", "Yan görüntü"], ["probs", "Uyarılar"]].map(([k, n]) => `<button data-k="${k}" class="${k === "tx" ? "on" : ""}">${n} <span class="muted" id="fn_${k}"></span></button>`).join("")}</div></div>
        <div class="fbody" id="fbody"></div></div></div>
    <div class="transport">
      <button class="btn icon" id="fb5" title="5 sn geri">${I("back", 14)}</button><button class="btn icon" id="fplay" title="Oynat (boşluk)">${I("play", 14)}</button><button class="btn icon" id="ff5" title="5 sn ileri">${I("fwd", 14)}</button>
      <span class="tc" id="ftc"></span>
      <div class="seg dark" id="fmode"><button data-m="1" class="on">Kesimli izle</button><button data-m="0">Ham izle</button></div>
      <span style="flex:1"></span><span class="small" style="color:#888" id="fdur"></span>
      <span class="small" style="color:#888">yakınlaştır</span><input type="range" id="fzoom" min="0.5" max="40" step="0.1" value="1">
    </div>
    <div class="timeline film"><div class="tl-heads"><div class="thin">Bölüm</div><div>Kesim</div><div>Yan görüntü</div></div>
      <div class="tl-scroll" id="fls"><div class="tl-inner" id="fli"></div></div></div>`;
  const fv = $("#fv"); fv.src = `/p/${name}/${P.sources[P.main].proxy}`;
  fv.onplay = fv.onpause = () => $("#fplay").innerHTML = I(fv.paused ? "play" : "pause", 14);
  $("#fplay").onclick = () => fv.paused ? fv.play() : fv.pause();
  $("#fb5").onclick = () => fv.currentTime -= 5; $("#ff5").onclick = () => fv.currentTime += 5;
  $("#fmode").querySelectorAll("button").forEach(b => b.onclick = () => { F.edit = b.dataset.m === "1"; $("#fmode").querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b)); });
  $("#ftabs").querySelectorAll("button").forEach(b => b.onclick = () => { F.tab = b.dataset.k; $("#ftabs").querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b)); fPane(); });
  F.pps = Math.max(0.5, ($("#fls").clientWidth - 30) / (P.duration || 1)); $("#fzoom").value = F.pps;
  $("#fzoom").oninput = e => { F.pps = +e.target.value; fTimeline(); };
  $("#fundo").onclick = fUndo; $("#fredo").onclick = fRedo; $("#fsave").onclick = () => fSave().catch(fail);
  $("#frender").onclick = async () => {
    if (fProblems().some(p => p.level === "error")) { F.tab = "probs"; fPane(); return toast("Kırmızı uyarılar var, önce onları düzelt"); }
    if (!confirm("4K render uzun sürer (bir saatten fazla). Başlatılsın mı?")) return;
    try { if (F.dirty) await fSave(); await api(`/api/p/${name}/render`, { method: "POST" }); toast("Render başladı"); } catch (e) { fail(e); } };
  $("#fls").addEventListener("mousedown", fTlDown); $("#fls").addEventListener("contextmenu", fTlMenu);
  fAll(); requestAnimationFrame(fTick);
  const poll = async () => { if (!F || F.name !== name) return; try { const s = await api(`/api/p/${name}/status`); const l = $("#flab"); if (l) l.textContent = s.running ? `${s.step} · %${Math.round(s.pct || 0)}` : "4K Render"; } catch (e) { } };
  poll(); A.poll = setInterval(poll, 3000);
}
function fDirty(b) { F.dirty = b; const e = $("#fdirty"); if (e) e.textContent = b ? "● kaydediliyor…" : (F.savedAt ? "✓ kaydedildi" : "");
  if (b) { clearTimeout(F.saveT); const n = F.name; F.saveT = setTimeout(async () => { if (!F || F.name !== n || !F.dirty) return;
    try { await api(`/api/p/${F.name}`, { body: F.P }); F.savedAt = Date.now(); fDirty(false); } catch (e) { fail(e); } }, 900); } }
function fSnap() { F.hist.push(JSON.stringify(F.P)); if (F.hist.length > 200) F.hist.shift(); F.fut = []; fDirty(true); }
function fUndo() { if (!F.hist.length) return; F.fut.push(JSON.stringify(F.P)); F.P = JSON.parse(F.hist.pop()); fDirty(true); fAll(); }
function fRedo() { if (!F.fut.length) return; F.hist.push(JSON.stringify(F.P)); F.P = JSON.parse(F.fut.pop()); fDirty(true); fAll(); }
async function fSave() { clearTimeout(F.saveT); const r = await api(`/api/p/${F.name}`, { body: F.P }); F.savedAt = Date.now(); fDirty(false); toast(r.problems.some(p => p.level === "error") ? "Kaydedildi, kırmızı uyarılar var" : "Kaydedildi"); }

// ---- cut math (same rules as the renderer) ----
const fCuts = () => F.P.cuts.filter(fon).sort((a, b) => a.start - b.start);
const fInCut = t => fCuts().find(c => t >= c.start && t < c.end);
const fOvAt = t => F.P.overlays.filter(fon).find(o => t >= o.start && t < o.end);
const fNext = a => a.reduce((m, x) => Math.max(m, x.id), 0) + 1;
function fAddCut(a, b, reason) {
  const P = F.P, ov = P.cuts.filter(c => fon(c) && c.start <= b && c.end >= a); let s = a, e = b;
  ov.forEach(c => { s = Math.min(s, c.start); e = Math.max(e, c.end); });
  P.cuts = P.cuts.filter(c => !ov.includes(c));
  P.cuts.push({ id: fNext(P.cuts), start: +s.toFixed(3), end: +e.toFixed(3), reason: ov.length ? ov.map(c => c.reason).concat(reason).filter((x, i, A_) => A_.indexOf(x) === i).join(" + ") : reason, on: true });
}
function fSubtract(a, b) {
  const out = [];
  F.P.cuts.forEach(c => { if (!fon(c) || c.end <= a || c.start >= b) { out.push(c); return; }
    if (c.start < a - 0.01) out.push({ ...c, end: +a.toFixed(3) });
    if (c.end > b + 0.01) out.push({ ...c, id: fNext(F.P.cuts.concat(out)), start: +b.toFixed(3) }); });
  F.P.cuts = out;
}
const fOutDur = () => fCuts().reduce((d, c) => d - (c.end - c.start), F.P.duration);
function fProblems() {
  const P = F.P, out = [];
  P.overlays.filter(fon).forEach(o => { const s = P.sources[o.src] || {};
    if (s.speaker === "yes" && !o.synced) out.push({ level: "error", id: o.id, kind: "ov", msg: `Yan görüntü #${o.id} (${o.src}): yüzün görünüyor ama ses başka andan. Dudaklar kayar.` });
    else if (s.speaker === "sometimes" && !o.synced) out.push({ level: "warn", id: o.id, kind: "ov", msg: `Yan görüntü #${o.id} (${o.src}): bazen konuşmacı görünüyor, anı kontrol et.` });
    if (o.end <= o.start) out.push({ level: "error", id: o.id, kind: "ov", msg: `Yan görüntü #${o.id}: bitiş başlangıçtan önce.` }); });
  const c = fCuts(); for (let i = 1; i < c.length; i++) { const g = c[i].start - c[i - 1].end; if (g > 0 && g < 0.12) out.push({ level: "warn", id: c[i].id, kind: "cut", msg: `Kesim #${c[i - 1].id} ile #${c[i].id} arası ${(g * 1000).toFixed(0)} ms: kekeme gibi duyulabilir.` }); }
  return out;
}

// ---- rendering ----
function fAll() { fPane(); fTimeline(); const pr = fProblems();
  $("#fn_cuts").textContent = fCuts().length; $("#fn_ovs").textContent = F.P.overlays.filter(fon).length; $("#fn_probs").textContent = pr.length || "";
  $("#fdur").textContent = `çıktı ≈ ${fmt(fOutDur()).slice(0, 5)} / kaynak ${fmt(F.P.duration).slice(0, 5)}`; }
function fWordCls(i) {
  const w = F.W[i], m = (w.s + w.e) / 2; let c = "w";
  if (fInCut(m)) c += " cut"; if (FILL.test(w.w)) c += " fill";
  const o = fOvAt(m); if (o) { c += " ov"; if (o.src === "SCREEN") c += " scr"; else if (o.src === "PAPER" || o.secret) c += " pap"; const s = F.P.sources[o.src]; if (s && s.speaker === "yes" && !o.synced) c += " bad"; }
  if (F.selA !== null) { const a = Math.min(F.selA, F.selB), b = Math.max(F.selA, F.selB); if (i >= a && i <= b) c += " sel"; }
  return c;
}
function fPane() {
  const B = $("#fbody"), P = F.P; if (!B) return;
  if (F.tab === "tx") {
    let h = `<div class="txhelp small">Kelimeleri sürükleyerek seç. Sağ tık: kes, geri getir, yan görüntü. Gri kutucuk: duraklama, tıkla kısalt.</div><div class="tx" id="ftx"><p>`;
    const W = F.W;
    for (let i = 0; i < W.length; i++) {
      if (i > 0) { const g = W[i].s - W[i - 1].e; if (g >= 1.6) h += "</p><p>";
        if (g >= 0.25) { const a = W[i - 1].e, b = W[i].s, cov = fCuts().reduce((s, c) => s + Math.max(0, Math.min(b, c.end) - Math.max(a, c.start)), 0) / g;
          h += `<span class="g ${cov > 0.9 ? "cut" : cov > 0.05 ? "part" : ""}" data-g="${i}">${g.toFixed(1)}s</span>`; } }
      h += `<span class="${fWordCls(i)}" data-i="${i}">${esc(W[i].w)}</span> `;
    }
    B.innerHTML = h + "</p></div>"; fTxEvents();
  } else if (F.tab === "cuts") {
    const c = P.cuts.slice().sort((a, b) => a.start - b.start);
    B.innerHTML = `<div class="flist">${c.map(x => `<div class="frow ${fon(x) ? "" : "off"} ${F.sel && F.sel.k === "cut" && F.sel.id === x.id ? "sel" : ""}" data-id="${x.id}">
      <input type="checkbox" class="switch" data-on ${fon(x) ? "checked" : ""}><div class="fl"><b>#${x.id} · ${fmt(x.start)} → ${fmt(x.end)}</b><span>${esc(x.reason)} · ${(x.end - x.start).toFixed(2)} sn</span></div>
      <span class="nud"><button class="btn mini" data-n="start" data-d="-0.05">−</button><button class="btn mini" data-n="start" data-d="0.05">+</button></span>
      <span class="nud"><button class="btn mini" data-n="end" data-d="-0.05">−</button><button class="btn mini" data-n="end" data-d="0.05">+</button></span>
      <button class="btn icon" data-play>${I("play", 12)}</button></div>`).join("")}</div>`;
    B.querySelectorAll(".frow").forEach(r => { const x = P.cuts.find(c => c.id == r.dataset.id);
      r.onclick = e => { const t = e.target.closest("[data-n],[data-play],[data-on]");
        if (!t) { F.sel = { k: "cut", id: x.id }; fSeek(x.start - 1); fTimeline(); return; }
        if (t.dataset.n) { fSnap(); x[t.dataset.n] = +(x[t.dataset.n] + (+t.dataset.d)).toFixed(3); fAll(); }
        else if (t.hasAttribute("data-play")) { F.edit = true; fSeek(x.start - 1.5); fPlayFor(3.3); } };
      r.querySelector("[data-on]").onchange = e => { fSnap(); x.on = e.target.checked; fAll(); }; });
  } else if (F.tab === "ovs") {
    const pr = fProblems(), srcs = others();
    B.innerHTML = `<div class="flist">${P.overlays.slice().sort((a, b) => a.start - b.start).map(o => { const p = pr.find(x => x.kind === "ov" && x.id === o.id);
      return `<div class="frow ${fon(o) ? "" : "off"} ${p && p.level === "error" ? "bad" : ""} ${F.sel && F.sel.k === "ov" && F.sel.id === o.id ? "sel" : ""}" data-id="${o.id}">
        <input type="checkbox" class="switch" data-on ${fon(o) ? "checked" : ""}><div class="fl"><b>#${o.id} · ${fmt(o.start)} → ${fmt(o.end)}</b>
        <span><select data-src>${srcs.map(s => `<option ${s === o.src ? "selected" : ""}>${s}</option>`).join("")}</select> ${o.secret ? '<span class="tag warn">gizli bilgiyi örtüyor</span>' : ""} ${p ? `<span class="tag ${p.level === "error" ? "err" : "warn"}">${p.level === "error" ? "dudak kayar" : "kontrol et"}</span>` : ""}</span></div>
        <label class="small muted">klip sn <input type="number" step="0.5" data-in value="${o.in}" style="width:62px"></label>
        <button class="btn icon" data-play>${I("play", 12)}</button><button class="btn icon danger" data-del>${I("trash", 12)}</button></div>`; }).join("")}</div>`;
    B.querySelectorAll(".frow").forEach(r => { const o = P.overlays.find(x => x.id == r.dataset.id);
      r.onclick = e => { const t = e.target.closest("[data-play],[data-del],select,input"); if (!t) { F.sel = { k: "ov", id: o.id }; fSeek(o.start - 0.8); fTimeline(); return; }
        if (t.hasAttribute("data-play")) { fSeek(o.start - 0.8); fPlayFor(o.end - o.start + 1.6); }
        if (t.hasAttribute("data-del")) { if (o.secret && !confirm("Bu yan görüntü ekrandaki gizli bir bilgiyi örtüyor. Yine de silinsin mi?")) return; fSnap(); P.overlays = P.overlays.filter(x => x !== o); fAll(); } };
      r.querySelector("[data-on]").onchange = e => { fSnap(); o.on = e.target.checked; fAll(); };
      r.querySelector("[data-src]").onchange = e => { fSnap(); o.src = e.target.value; fAll(); };
      r.querySelector("[data-in]").onchange = e => { fSnap(); o.in = +e.target.value; fAll(); }; });
  } else {
    const pr = fProblems();
    B.innerHTML = `<div class="probs">${pr.map(p => `<div class="prob ${p.level}" data-id="${p.id}" data-k="${p.kind}">${esc(p.msg)}</div>`).join("") || '<div class="list-empty">Sorun yok.</div>'}</div>`;
    B.querySelectorAll(".prob").forEach(d => d.onclick = () => { const x = (d.dataset.k === "ov" ? F.P.overlays : F.P.cuts).find(a => a.id == d.dataset.id); if (x) fSeek(x.start - 1); });
  }
}
const others = () => Object.keys(F.P.sources).filter(k => k !== F.P.main).concat(["SCREEN", "PAPER"]);
function fRefreshWords() { document.querySelectorAll("#ftx .w").forEach(el => el.className = fWordCls(+el.dataset.i)); }
function fTxEvents() {
  const tx = $("#ftx"); if (!tx) return;
  tx.onmousedown = e => { const el = e.target.closest(".w"); if (!el || e.button !== 0) return; const i = +el.dataset.i;
    if (e.shiftKey && F.selA !== null) F.selB = i; else { F.selA = F.selB = i; F.drag = true; } fRefreshWords(); };
  tx.onmouseover = e => { if (!F.drag) return; const el = e.target.closest(".w"); if (el) { F.selB = +el.dataset.i; fRefreshWords(); } };
  tx.onclick = e => { const g = e.target.closest(".g"); if (!g) return; const i = +g.dataset.g, a = F.W[i - 1].e, b = F.W[i].s, pad = 0.18;
    const cov = fCuts().some(c => c.start < b - 0.05 && c.end > a + 0.05);
    if (!cov && b - a <= 2 * pad + 0.1) return toast(`Bu duraklama zaten kısa (${(b - a).toFixed(2)} sn)`);
    fSnap(); if (cov) { fSubtract(a, b); toast("Duraklama geri açıldı"); } else { fAddCut(a + pad, b - pad, "Duraklama (elle)"); toast(`Duraklama ${(b - a).toFixed(1)} → ${(2 * pad).toFixed(2)} sn`); }
    fAll(); fSeek(a - 1.2); fPlayFor(3.2); };
  tx.oncontextmenu = e => { e.preventDefault(); const el = e.target.closest(".w");
    if (el && (F.selA === null || !fSelRange() || +el.dataset.i < fSelRange()[2] || +el.dataset.i > fSelRange()[3])) { F.selA = F.selB = +el.dataset.i; fRefreshWords(); }
    const has = !!fSelRange();
    showMenu(e.clientX, e.clientY, [
      { icon: "cut", label: "Seçimi kes", keys: KB("⌫"), run: fDoCut, off: !has },
      { icon: "undo", label: "Geri getir", keys: KB("R"), run: fDoRestore, off: !has },
      { icon: "film", label: "Yan görüntü ekle…", keys: KB("B"), run: fPickOv, off: !has },
      { icon: "play", label: "Buradan dinle", keys: KB("␣"), run: () => { const r = fSelRange(); if (r) { fSeek(r[0] - 1); fPlayFor(r[1] - r[0] + 2); } }, off: !has }, "-",
      { icon: "copy", label: "Metni kopyala", keys: KB("⌘", "C"), run: () => { const r = fSelRange(); navigator.clipboard.writeText(F.W.slice(r[2], r[3] + 1).map(w => w.w).join(" ")); toast("Kopyalandı"); }, off: !has },
    ]);
  };
}
addEventListener("mouseup", () => { if (!F || !F.drag) return; F.drag = false; if (F.selA === F.selB) fSeek(F.W[F.selA].s - 0.25); });
function fSelRange() { if (F.selA === null) return null; const a = Math.min(F.selA, F.selB), b = Math.max(F.selA, F.selB); return [F.W[a].s, F.W[b].e, a, b]; }
function fDoCut() { const r = fSelRange(); if (!r) return; fSnap(); const W = F.W;
  const pe = r[2] > 0 ? W[r[2] - 1].e : r[0] - 0.1, ns = r[3] < W.length - 1 ? W[r[3] + 1].s : r[1] + 0.1;
  fAddCut(r[0] - Math.min(0.03, Math.max(0, (r[0] - pe) / 2)), r[1] + Math.min(0.03, Math.max(0, (ns - r[1]) / 2)), "Elle kesildi");
  fAll(); toast(`${r[3] - r[2] + 1} kelime kesildi`); fSeek(r[0] - 1.5); fPlayFor(3.5); }
function fDoRestore() { const r = fSelRange(); if (!r) return; fSnap(); const W = F.W;
  const pe = r[2] > 0 ? W[r[2] - 1].e : r[0] - 0.2, ns = r[3] < W.length - 1 ? W[r[3] + 1].s : r[1] + 0.2;
  fSubtract(Math.min(r[0] - 0.05, (pe + r[0]) / 2), Math.max(r[1] + 0.05, (r[1] + ns) / 2)); fAll(); toast("Geri getirildi"); }
function fPickOv() {
  const r = fSelRange(); if (!r) return; const P = F.P;
  const s = sheet(`${I("film", 16)} ${fmt(r[0])} → ${fmt(r[1])} yan görüntü`,
    `<div class="mgrid small-grid">${others().map(k => { const S_ = P.sources[k] || {}; const th = S_.proxy && !S_.image ? `/api/p/${F.name}/thumb?src=${encodeURIComponent(k)}&t=5` : S_.image ? `/p/${F.name}/${S_.proxy}` : "";
      return `<div class="mitem" data-k="${k}"><div class="mthumb video" style="background-image:url('${th}')">${k === "SCREEN" ? "<b>PERDE</b>" : k === "PAPER" ? "<b>KAĞIT</b>" : ""}</div>
        <div class="mmeta"><b>${esc(k)}</b><span class="small ${S_.speaker === "yes" ? "" : "muted"}" style="${S_.speaker === "yes" ? "color:var(--red)" : ""}">${S_.speaker === "yes" ? "yüzün görünüyor: kayar" : S_.speaker === "sometimes" ? "bazen yüzün var" : k === "SCREEN" ? "perde yakın plan" : k === "PAPER" ? "kağıt efekti" : "ara plan"}</span></div></div>`; }).join("")}</div>`);
  s.el.querySelectorAll(".mitem").forEach(m => m.onclick = () => { fSnap(); const src = m.dataset.k;
    P.overlays = P.overlays.filter(o => !(fon(o) && o.start >= r[0] - 0.01 && o.end <= r[1] + 0.01));
    P.overlays.push({ id: fNext(P.overlays), start: +(r[0] - 0.05).toFixed(2), end: +(r[1] + 0.1).toFixed(2), src, in: 0, reason: "Elle eklendi", secret: false, on: true });
    P.overlays.sort((a, b) => a.start - b.start); s.close(); F.tab = "ovs"; $("#ftabs").querySelectorAll("button").forEach(x => x.classList.toggle("on", x.dataset.k === "ovs")); fAll(); });
}

// ---- timeline ----
function fTimeline() {
  const P = F.P, pps = F.pps, W = Math.max(P.duration * pps + 60, $("#fls").clientWidth), pr = fProblems();
  const step = [1, 2, 5, 10, 30, 60, 120, 300].find(s => s * pps > 60) || 600;
  let ruler = ""; for (let t = 0; t <= P.duration; t += step) ruler += `<span style="left:${t * pps}px">${fmt(t).slice(0, 5)}</span><i style="left:${t * pps}px"></i>`;
  const clip = (cls, a, b, attrs, label) => `<div class="clip ${cls}" style="left:${a * pps}px;width:${Math.max(1.5, (b - a) * pps - 0.5)}px" ${attrs}><span class="lbl">${esc(label)}</span><i class="h l"></i><i class="h r"></i></div>`;
  const cuts = P.cuts.map(c => clip(`cutc ${fon(c) ? "" : "offc"} ${F.sel && F.sel.k === "cut" && F.sel.id === c.id ? "sel" : ""}`, c.start, c.end, `data-k="cut" data-id="${c.id}"`, (c.end - c.start) * pps > 50 ? c.reason : "")).join("");
  const ovs = P.overlays.map(o => { const bad = pr.some(p => p.level === "error" && p.kind === "ov" && p.id === o.id);
    const cls = o.src === "SCREEN" ? "sync" : (o.src === "PAPER" || o.secret) ? "paper" : "clip_";
    return clip(`${cls} ${fon(o) ? "" : "offc"} ${bad ? "bad" : ""} ${F.sel && F.sel.k === "ov" && F.sel.id === o.id ? "sel" : ""}`, o.start, o.end, `data-k="ov" data-id="${o.id}"`, o.src); }).join("");
  const ch = (P.chapters || []).map((c, i) => { const nx = (P.chapters[i + 1] || {}).src ?? P.duration; return clip("title", c.src, nx, `data-k="ch"`, `${c.num || ""} ${c.title || ""}`); }).join("");
  $("#fli").style.width = W + "px";
  $("#fli").innerHTML = `<div class="ruler">${ruler}</div><div class="track thin">${ch}</div><div class="track">${cuts}</div><div class="track">${ovs}</div><div class="playhead" id="fph"></div>`;
}
function fTlDown(e) {
  if (e.button !== 0) return; closeMenu();
  const box = $("#fli").getBoundingClientRect(), t = (e.clientX - box.left) / F.pps, c = e.target.closest(".clip");
  if (!c || c.dataset.k === "ch") { F.sel = null; fSeek(t); fTimeline(); return; }
  const arr = c.dataset.k === "cut" ? F.P.cuts : F.P.overlays, x = arr.find(a => a.id == c.dataset.id); F.sel = { k: c.dataset.k, id: x.id };
  const edge = e.target.classList.contains("h") ? (e.target.classList.contains("l") ? "start" : "end") : null;
  if (!edge) { fSeek(x.start - (c.dataset.k === "cut" ? 1 : 0.3)); F.tab = c.dataset.k === "cut" ? "cuts" : "ovs"; $("#ftabs").querySelectorAll("button").forEach(b => b.classList.toggle("on", b.dataset.k === F.tab)); fAll(); return; }
  const x0 = e.clientX, v0 = x[edge], before = JSON.stringify(F.P);
  const mv = ev => { x[edge] = +(v0 + (ev.clientX - x0) / F.pps).toFixed(2); if (x.end - x.start < 0.05) x[edge] = edge === "start" ? x.end - 0.05 : x.start + 0.05; fTimeline(); };
  const up = () => { removeEventListener("mousemove", mv); removeEventListener("mouseup", up); if (JSON.stringify(F.P) !== before) { F.hist.push(before); F.fut = []; fDirty(true); } fAll(); };
  addEventListener("mousemove", mv); addEventListener("mouseup", up);
}
function fTlMenu(e) {
  e.preventDefault(); const c = e.target.closest(".clip"); if (!c || c.dataset.k === "ch") return;
  const arr = c.dataset.k === "cut" ? F.P.cuts : F.P.overlays, x = arr.find(a => a.id == c.dataset.id); F.sel = { k: c.dataset.k, id: x.id }; fTimeline();
  showMenu(e.clientX, e.clientY, [
    { icon: "play", label: "Dinle", keys: KB("␣"), run: () => { fSeek(x.start - 1.5); fPlayFor(x.end - x.start + 3); } },
    { icon: fon(x) ? "x" : "check", label: fon(x) ? "Kapat" : "Aç", run: () => { fSnap(); x.on = !fon(x); fAll(); } }, "-",
    { icon: "trash", label: "Sil", keys: KB("⇧", "⌫"), run: () => { if (x.secret && !confirm("Bu yan görüntü gizli bir bilgiyi örtüyor. Yine de silinsin mi?")) return; fSnap();
      if (c.dataset.k === "cut") F.P.cuts = F.P.cuts.filter(y => y !== x); else F.P.overlays = F.P.overlays.filter(y => y !== x); F.sel = null; fAll(); } },
  ]);
}

// ---- player ----
function fSeek(t) { const v = $("#fv"); if (v) v.currentTime = Math.max(0, t); }
function fPlayFor(sec) { const v = $("#fv"); F.stopAt = v.currentTime + sec + 0.6; v.play(); }
function fTick() {
  if (!F || !$("#fv")) return; const v = $("#fv"), ov = $("#fov"), oi = $("#foi"), bd = $("#fbadge"), P = F.P, t = v.currentTime;
  if (F.edit && !v.paused) { const c = fInCut(t + 0.01); if (c && c.end - t > 0.03) v.currentTime = c.end; }
  if (F.stopAt !== null && t >= F.stopAt) { v.pause(); F.stopAt = null; }
  const o = F.edit && fOvAt(t), S_ = o && P.sources[o.src];
  v.style.transform = "none"; ov.style.display = "none"; oi.style.display = "none"; bd.hidden = true;
  if (o) { bd.hidden = false;
    if (o.src === "SCREEN") { v.style.transformOrigin = "58% 50%"; v.style.transform = "scale(2.63)"; bd.textContent = "PERDE YAKIN PLAN"; bd.className = "fbadge scr"; }
    else if (o.src === "PAPER") { oi.src = `/p/${F.name}/paper/frame.jpg`; oi.style.display = "block"; bd.textContent = "KAĞIT EFEKTİ"; bd.className = "fbadge pap"; }
    else if (S_ && S_.image) { if (!oi.src.endsWith(S_.proxy)) oi.src = `/p/${F.name}/${S_.proxy}`; oi.style.display = "block"; bd.textContent = o.src; bd.className = "fbadge"; }
    else if (S_) { const want = o.in + (t - o.start); if (ov.dataset.k !== o.src) { ov.dataset.k = o.src; ov.src = `/p/${F.name}/${S_.proxy}`; }
      if (Math.abs(ov.currentTime - want) > 0.35) ov.currentTime = want; if (v.paused) ov.pause(); else if (ov.paused) ov.play().catch(() => { });
      ov.style.display = "block"; const bad = S_.speaker === "yes" && !o.synced; bd.textContent = o.src + (bad ? " · DUDAK KAYAR" : "") + (o.secret ? " · GİZLİ ÖRTÜLÜ" : ""); bd.className = "fbadge" + (bad ? " bad" : o.secret ? " pap" : ""); } }
  else if (!ov.paused) ov.pause();
  $("#ftc").textContent = `${fmt(t)} / ${fmt(P.duration)}`;
  const ph = $("#fph"); if (ph) { ph.style.left = t * F.pps + "px"; if (!v.paused) { const sc = $("#fls"), x = t * F.pps; if (x < sc.scrollLeft || x > sc.scrollLeft + sc.clientWidth - 40) sc.scrollLeft = x - 80; } }
  if (F.tab === "tx") { const W = F.W; let lo = 0, hi = W.length - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; if (W[m].s <= t) lo = m; else hi = m - 1; }
    if (lo !== F.last) { document.querySelectorAll("#ftx .w.now").forEach(e => e.classList.remove("now")); const el = document.querySelector(`#ftx .w[data-i="${lo}"]`);
      if (el) { el.classList.add("now"); if (F.follow && !v.paused) { const r = el.getBoundingClientRect(), pr = $("#fbody").getBoundingClientRect(); if (r.top < pr.top + 40 || r.bottom > pr.bottom - 30) el.scrollIntoView({ block: "center" }); } } F.last = lo; } }
  requestAnimationFrame(fTick);
}
addEventListener("keydown", e => {
  if (!F || !$("#fv") || ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
  const k = e.key.toLowerCase(), cmd = e.metaKey || e.ctrlKey, v = $("#fv");
  if (cmd && k === "s") { e.preventDefault(); fSave().catch(fail); }
  else if (cmd && k === "z") { e.preventDefault(); e.shiftKey ? fRedo() : fUndo(); }
  else if (k === " ") { e.preventDefault(); v.paused ? v.play() : v.pause(); }
  else if (k === "backspace" || k === "delete") { e.preventDefault(); fDoCut(); }
  else if (k === "r" && !cmd) fDoRestore(); else if (k === "b" && !cmd) fPickOv();
  else if (k === "arrowleft") v.currentTime -= e.shiftKey ? 5 : 1; else if (k === "arrowright") v.currentTime += e.shiftKey ? 5 : 1;
});
