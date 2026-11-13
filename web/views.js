// biar-edit · media library, audio, effects and product recording pages.
"use strict";
const KIND_TR = { video: "Video", audio: "Ses", image: "Görsel", music: "Müzik", sfx: "SFX", transition: "Geçiş", lut: "LUT" };
const SPEAK_TR = { yes: "yüzüm görünüyor", no: "yüzüm yok", sometimes: "bazen görünüyor", unknown: "belirsiz" };
const LOOK_CSS = { none: "none", dogal: "contrast(1.04) saturate(1.05)", canli: "contrast(1.08) saturate(1.3)", sicak: "sepia(.18) saturate(1.1)",
  soguk: "hue-rotate(-12deg) saturate(.95)", sinematik: "contrast(1.1) saturate(.9) hue-rotate(-6deg)", soluk: "contrast(.88) saturate(.8) brightness(1.05)",
  siyahbeyaz: "grayscale(1) contrast(1.12)", gece: "brightness(.9) contrast(1.12) saturate(.85) hue-rotate(10deg)" };
const fsize = b => b > 1e9 ? (b / 1e9).toFixed(1) + " GB" : (b / 1e6).toFixed(0) + " MB";
const fdur = s => s ? (s >= 60 ? `${Math.floor(s / 60)} dk ${Math.round(s % 60)} sn` : `${s.toFixed(1)} sn`) : "";

function sheet(title, body, actions) {
  const scr = document.createElement("div"); scr.className = "scrim";
  scr.innerHTML = `<div class="sheet"><h3>${title}</h3>${body}<div class="actions">${actions || '<button class="btn" data-x>Kapat</button>'}</div></div>`;
  document.body.appendChild(scr);
  const close = () => scr.remove(); scr.onclick = e => { if (e.target === scr || e.target.hasAttribute("data-x")) close(); };
  return { el: scr, close };
}
// in-page confirm: native confirm() dialogs are swallowed in some embedded browsers
function ask(msg, ok = "Onayla", danger = false) {
  return new Promise(res => {
    const s = sheet("Emin misin?", `<p style="margin:4px 0 8px;line-height:1.5">${esc(msg)}</p>`,
      `<button class="btn" data-x>Vazgeç</button><button class="btn ${danger ? "danger" : "primary"}" id="askok">${esc(ok)}</button>`);
    let done = false; const fin = v => { if (!done) { done = true; res(v); } };
    s.el.querySelector("#askok").onclick = () => { fin(true); s.close(); };
    s.el.addEventListener("click", e => { if (e.target === s.el || e.target.hasAttribute("data-x")) fin(false); });
    s.el.querySelector("#askok").focus();
  });
}
let _audio = null;
function preview(url) { if (_audio) { _audio.pause(); } _audio = new Audio(url); _audio.play().catch(fail); }

// =====================================================================
// Kaynaklar (media library)
// =====================================================================
let MEDIA_FILTER = "all";
async function viewMedia() {
  R = null;
  toolbar(`<span class="title">Kaynaklar</span><span class="sub">çalışacağın dosyalar · dosyalar yerinde kalır, kopyalanmaz</span><span class="sp"></span>
    <button class="btn" id="mfolder">${I("ext", 14)} Dışa aktarma klasörü</button>
    <button class="btn primary" id="madd">${I("plus", 14)} Dosya ekle</button>`);
  const [lib, st] = await Promise.all([api("/api/media"), api("/api/settings")]);
  const kinds = ["all", "video", "audio", "music", "image", "sfx", "transition", "lut"];
  const list = lib.filter(i => MEDIA_FILTER === "all" || i.kind === MEDIA_FILTER);
  const v = $("#view"); v.className = "view";
  v.innerHTML = `<div class="libbar"><div class="seg" id="mseg">${kinds.map(k => `<button data-k="${k}" class="${MEDIA_FILTER === k ? "on" : ""}">${k === "all" ? "Tümü" : KIND_TR[k]} <span class="muted">${k === "all" ? lib.length : lib.filter(i => i.kind === k).length}</span></button>`).join("")}</div>
      <span class="sp" style="flex:1"></span><span class="small muted">Dışa aktarma: <span class="mono">${esc(st.export_dir)}</span></span></div>
    ${list.length ? `<div class="mgrid">${list.map(i => `<div class="mitem ${i.missing ? "missing" : ""}" data-id="${i.id}" tabindex="0">
        <div class="mthumb ${i.kind}" style="background-image:url('/api/media/${i.id}/thumb?t=2')">${i.kind === "lut" ? "<b>LUT</b>" : ""}${i.duration ? `<span class="mdur">${fdur(i.duration)}</span>` : ""}</div>
        <div class="mmeta"><b title="${esc(i.path)}">${esc(i.name)}</b><span><span class="tag">${KIND_TR[i.kind] || i.kind}</span>${i.kind === "video" ? ` <span class="small muted">${SPEAK_TR[i.speaker] || ""}</span>` : ""}${i.missing ? ' <span class="tag err">dosya yok</span>' : ""}${(i.tags || []).includes("referans") ? ' <span class="tag warn">referans</span>' : ""}</span></div></div>`).join("")}</div>`
      : `<div class="list-empty">Burada henüz bir şey yok.<br><br><button class="btn primary" id="madd2">${I("plus", 14)} Dosya ekle</button></div>`}`;
  v.querySelectorAll("#mseg button").forEach(b => b.onclick = () => { MEDIA_FILTER = b.dataset.k; viewMedia(); });
  const add = async () => {
    const k = MEDIA_FILTER === "all" ? null : MEDIA_FILTER;
    try { const r = await api("/api/media/pick", { body: { kind: k } }); if (r.items.length) { toast(`${r.items.length} dosya eklendi`); viewMedia(); } } catch (e) { fail(e); }
  };
  $("#madd").onclick = add; if ($("#madd2")) $("#madd2").onclick = add;
  $("#mfolder").onclick = async () => { try { const r = await api("/api/pick/folder", { body: { prompt: "Render edilen videolar nereye kaydedilsin?" } });
    if (r.path) { await api("/api/settings", { body: { patch: { export_dir: r.path } } }); toast("Dışa aktarma klasörü: " + r.path); viewMedia(); } } catch (e) { fail(e); } };
  v.querySelectorAll(".mitem").forEach(el => {
    const it = lib.find(i => i.id === el.dataset.id);
    el.ondblclick = () => mediaPreview(it);
    el.oncontextmenu = e => { e.preventDefault(); mediaMenu(it, e.clientX, e.clientY); };
    el.onclick = e => mediaMenu(it, e.clientX, e.clientY);
  });
}
function mediaMenu(it, x, y) {
  const reels = A.projects.filter(p => p.kind === "reel");
  const setKind = k => api(`/api/media/${it.id}`, { body: { kind: k } }).then(viewMedia).catch(fail);
  const setSp = s => api(`/api/media/${it.id}`, { body: { speaker: s } }).then(viewMedia).catch(fail);
  const items = [{ icon: "play", label: "Önizle", keys: KB("↩"), run: () => mediaPreview(it) }];
  if (["video", "image", "audio", "music"].includes(it.kind)) {
    items.push({ icon: "plus", label: "Yeni reel başlat", run: () => newReelFrom(it) });
    items.push({ icon: "paste", label: "Bir projeye kaynak olarak ekle", run: () => addToProject(it, reels) });
  }
  items.push("-");
  if (it.kind === "video") {
    items.push({ icon: "person", label: "Yüzüm görünüyor", badge: it.speaker === "yes" ? '<span class="new">✓</span>' : "", run: () => setSp("yes") });
    items.push({ icon: "person", label: "Bazen görünüyor", badge: it.speaker === "sometimes" ? '<span class="new">✓</span>' : "", run: () => setSp("sometimes") });
    items.push({ icon: "person", label: "Yüzüm yok (ara plan)", badge: it.speaker === "no" ? '<span class="new">✓</span>' : "", run: () => setSp("no") });
    if ((it.tags || []).includes("indirilen")) {
      const ref = it.tags.includes("referans"), sw = (a, b) => api(`/api/media/${it.id}`, { body: { tags: it.tags.map(t => t === a ? b : t) } }).then(viewMedia).catch(fail);
      items.push({ icon: "link", label: ref ? "Kendi içeriğim (paylaşılabilir)" : "Referans yap (paylaşılmaz)", run: () => ref ? sw("referans", "kaynak") : sw("kaynak", "referans") });
      if (it.source && it.source.url) items.push({ icon: "ext", label: "Kaynağı aç", run: () => window.open(it.source.url, "_blank") });
    }
    items.push({ icon: "wand", label: "Geçiş efekti olarak kullan", run: () => setKind("transition") }, "-");
  }
  if (["audio", "music", "sfx"].includes(it.kind)) {
    items.push({ icon: "wave", label: "Müzik", run: () => setKind("music") }, { icon: "wave", label: "SFX", run: () => setKind("sfx") }, { icon: "mic", label: "Konuşma sesi", run: () => setKind("audio") }, "-");
  }
  items.push({ icon: "ext", label: "Finder'da göster", run: () => api("/api/reveal", { body: { path: it.path } }) });
  items.push({ icon: "trash", label: "Kütüphaneden çıkar", keys: KB("⌫"), run: async () => { if (!confirm(`${it.name} kütüphaneden çıkarılsın mı? (dosya silinmez)`)) return; await api(`/api/media/${it.id}`, { method: "DELETE" }); viewMedia(); } });
  showMenu(x, y, items);
}
function mediaPreview(it) {
  const url = `/api/media/${it.id}/file`;
  const body = it.kind === "image" ? `<img src="${url}" style="max-width:100%;border-radius:8px">`
    : ["audio", "music", "sfx"].includes(it.kind) ? `<img src="/api/media/${it.id}/thumb" style="width:100%;border-radius:8px;background:#111"><audio controls autoplay src="${url}" style="width:100%;margin-top:10px"></audio>`
    : it.kind === "lut" ? `<p class="mono">${esc(it.path)}</p>` : `<video controls autoplay src="${url}" style="width:100%;max-height:60vh;border-radius:8px;background:#000"></video>`;
  sheet(esc(it.name), body + `<p class="small muted mono" style="margin-top:8px">${esc(it.path)}${it.w ? ` · ${it.w}×${it.h}` : ""}${it.hdr ? " · HDR" : ""}</p>`);
}
async function newReelFrom(it) {
  const title = prompt("Yeni reelin adı:", it.name); if (!title) return;
  try { const r = await api("/api/projects/new", { body: { title, media_id: it.id } }); await refreshProjects(); go(`#/p/${r.name}`); } catch (e) { fail(e); }
}
function addToProject(it, reels) {
  if (!reels.length) return newReelFrom(it);
  const s = sheet(`${I("paste", 16)} Kaynak olarak ekle · ${esc(it.name)}`,
    `<div class="group">${reels.map(p => `<div class="row"><div class="lbl"><b>${esc(p.title)}</b></div><button class="btn" data-p="${p.name}">Ekle</button></div>`).join("")}</div>
     <div class="group"><div class="row"><div class="lbl"><b>Bu videoda yüzün görünüyor mu?</b><span>görünüyorsa sadece senkron kullanılabilir, dudaklar kaymasın diye</span></div>
       <select id="asp"><option value="no">Hayır</option><option value="sometimes">Bazen</option><option value="yes">Evet</option></select></div></div>`);
  $("#asp").value = ["yes", "no", "sometimes"].includes(it.speaker) ? it.speaker : "sometimes";
  s.el.querySelectorAll("[data-p]").forEach(b => b.onclick = async () => {
    try { await api(`/api/p/${b.dataset.p}/source`, { body: { media_id: it.id, speaker: $("#asp").value } }); s.close(); toast("Kaynak eklendi"); } catch (e) { fail(e); } });
}

// =====================================================================
// Ses (voice models + audio defaults)
// =====================================================================
async function viewAudio() {
  R = null;
  toolbar(`<span class="title">Ses</span><span class="sub">ses modelleri, seslendirme ve müzik</span><span class="sp"></span><button class="btn primary" id="vadd">${I("plus", 14)} Ses modeli ekle</button>`);
  const [st, lib] = await Promise.all([api("/api/settings"), api("/api/media")]);
  const voices = st.voices || [], el = st.providers.elevenlabs;
  const v = $("#view"); v.className = "view";
  v.innerHTML = `<div class="page"><h2>Ses</h2><p>Seslendirme için ses modellerin. ElevenLabs'teki hazır bir sesi ekleyebilir ya da kendi kayıtlarından sesini klonlayabilirsin.</p>
    ${el.has_key ? "" : `<div class="prob warn">ElevenLabs anahtarı yok. Önce <a href="#/models">Modeller</a> sayfasından ekle.</div>`}
    <div class="group-title">${I("mic", 14)} Ses modelleri</div>
    <div class="group">${voices.length ? voices.map((x, i) => `<div class="row"><span class="prov-logo" style="background:#000">11</span><div class="lbl"><b>${esc(x.name)} ${x.default ? '<span class="tag ok">varsayılan</span>' : ""}</b><span class="mono">${esc(x.voice_id)} · ${esc(x.model_id)}</span></div>
        <button class="btn" data-vt="${i}">${I("play", 12)} Dinle</button><button class="btn" data-ve="${i}">Düzenle</button></div>`).join("") : '<div class="list-empty">Henüz ses modeli yok.</div>'}</div>
    <div class="group-title">${I("wave", 14)} Seslendirme dene</div>
    <div class="group"><div class="row stack"><textarea id="ttxt" rows="3">Merhaba, ben Biar. Bu ses biar-edit ile üretildi.</textarea></div>
      <div class="row"><div class="lbl"><b>Ses</b></div><select id="tvoice">${voices.map(x => `<option value="${x.id}" ${x.default ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select><button class="btn primary" id="tgo">${I("mic", 14)} Seslendir</button></div>
      <div class="row" id="tout" hidden></div></div>
    <div class="group-title">${I("wave", 14)} Müzik kütüphanesi</div>
    <div class="group">${lib.filter(i => i.kind === "music").map(i => `<div class="row"><div class="lbl"><b>${esc(i.name)}</b><span>${fdur(i.duration)}</span></div><button class="btn" data-pl="${i.id}">${I("play", 12)}</button></div>`).join("") || '<div class="row muted">Müzik yok. Kaynaklar\'dan ses dosyası ekleyip türünü Müzik yap.</div>'}
      <div class="row"><div class="lbl"></div><button class="btn" id="maddm">${I("plus", 14)} Müzik ekle</button></div></div>
  </div>`;
  const editVoice = (idx) => {
    const x = idx === undefined ? { id: Math.random().toString(16).slice(2, 10), name: "", provider: "elevenlabs", voice_id: "", model_id: "eleven_multilingual_v2", stability: 0.5, similarity: 0.8, style: 0, speed: 1, default: !voices.length } : { ...voices[idx] };
    const audios = lib.filter(i => ["audio", "music", "video"].includes(i.kind));
    const s = sheet(idx === undefined ? `${I("mic", 16)} Ses modeli ekle` : `${I("mic", 16)} ${esc(x.name)}`,
      `<div class="seg" id="vmode" style="margin-bottom:12px"><button class="on" data-m="id">ElevenLabs sesi</button>${idx === undefined ? '<button data-m="clone">Sesimi klonla</button>' : ""}</div>
      <div class="group">
        <div class="row"><div class="lbl"><b>Ad</b></div><input type="text" id="vn" value="${esc(x.name)}" placeholder="ör. Biar · sahne"></div>
        <div class="row" data-only="id"><div class="lbl"><b>Ses</b><span>ElevenLabs kütüphanendeki sesler</span></div><input type="search" id="vid" list="vlist" value="${esc(x.voice_id)}" placeholder="voice id"><datalist id="vlist"></datalist></div>
        <div class="row stack" data-only="clone" hidden><div class="lbl"><b>Kayıtlar</b><span>temiz, tek kişilik 1-3 dakikalık konuşma en iyisi. Video seçersen sesi kullanılır.</span></div>
          ${audios.map(i => `<label class="small"><input type="checkbox" data-cf="${i.id}"> ${esc(i.name)} <span class="muted">${fdur(i.duration)}</span></label>`).join("<br>") || '<span class="muted small">Kaynaklar\'a önce ses ya da video ekle.</span>'}</div>
        <div class="row"><div class="lbl"><b>Model</b></div><select id="vm">${["eleven_multilingual_v2", "eleven_v3", "eleven_turbo_v2_5", "eleven_flash_v2_5"].map(m => `<option ${m === x.model_id ? "selected" : ""}>${m}</option>`).join("")}</select></div>
        <div class="row"><div class="lbl"><b>Kararlılık</b><span>düşük: daha duygulu, yüksek: daha düz</span></div><input type="range" id="vs" min="0" max="1" step="0.05" value="${x.stability}"></div>
        <div class="row"><div class="lbl"><b>Benzerlik</b></div><input type="range" id="vsi" min="0" max="1" step="0.05" value="${x.similarity}"></div>
        <div class="row"><div class="lbl"><b>Stil</b></div><input type="range" id="vst" min="0" max="1" step="0.05" value="${x.style}"></div>
        <div class="row"><div class="lbl"><b>Hız</b></div><input type="range" id="vsp" min="0.7" max="1.2" step="0.05" value="${x.speed}"></div>
        <div class="row"><div class="lbl"><b>Varsayılan</b></div><input type="checkbox" class="switch" id="vdef" ${x.default ? "checked" : ""}></div>
      </div>`,
      `${idx !== undefined ? '<button class="btn danger" id="vdel">Sil</button><span style="flex:1"></span>' : ""}<button class="btn" data-x>Vazgeç</button><button class="btn primary" id="vsave">Kaydet</button>`);
    let mode = "id";
    s.el.querySelectorAll("#vmode button").forEach(b => b.onclick = () => { mode = b.dataset.m; s.el.querySelectorAll("#vmode button").forEach(y => y.classList.toggle("on", y === b));
      s.el.querySelectorAll("[data-only]").forEach(r => r.hidden = r.dataset.only !== mode); });
    api("/api/ai/models?provider=elevenlabs").then(r => { $("#vlist").innerHTML = r.models.map(m => `<option value="${m.id}">${esc(m.name)}</option>`).join(""); }).catch(() => { });
    const collect = () => ({ ...x, name: $("#vn").value.trim() || "Ses", voice_id: $("#vid").value.trim(), model_id: $("#vm").value, stability: +$("#vs").value, similarity: +$("#vsi").value, style: +$("#vst").value, speed: +$("#vsp").value, default: $("#vdef").checked });
    const persist = async list => { if (list.some(y => y.default)) { const d = list.filter(y => y.default).pop(); list.forEach(y => y.default = y === d); } await api("/api/settings", { body: { patch: { voices: list } } }); };
    $("#vsave").onclick = async () => {
      try {
        if (mode === "clone") {
          const ids = [...s.el.querySelectorAll("[data-cf]:checked")].map(c => c.dataset.cf);
          if (!ids.length) return toast("En az bir kayıt seç");
          if (!confirm("Seçtiğin kayıtlar ElevenLabs'e yüklenecek ve sesinden bir model oluşturulacak. Devam edilsin mi?")) return;
          toast("Ses klonlanıyor…", 8000); await api("/api/ai/clone", { body: { name: $("#vn").value.trim() || "Sesim", media_ids: ids } });
        } else {
          const c = collect(); if (!c.voice_id) return toast("Bir ses seç");
          const list = voices.slice(); if (idx === undefined) list.push(c); else list[idx] = c; await persist(list);
        }
        s.close(); toast("Ses modeli kaydedildi"); viewAudio();
      } catch (e) { fail(e); } };
    if ($("#vdel")) $("#vdel").onclick = async () => { if (!confirm("Bu ses modeli silinsin mi? (ElevenLabs'teki ses silinmez)")) return; const list = voices.filter((_, i) => i !== idx); await persist(list); s.close(); viewAudio(); };
  };
  $("#vadd").onclick = () => editVoice();
  v.querySelectorAll("[data-ve]").forEach(b => b.onclick = () => editVoice(+b.dataset.ve));
  const say = async (text, profile) => { toast("Seslendiriliyor…"); const r = await api("/api/ai/tts", { body: { text, profile } }); preview(r.url); return r; };
  v.querySelectorAll("[data-vt]").forEach(b => b.onclick = () => say("Merhaba, bu ses modelinin denemesi.", voices[+b.dataset.vt].id).catch(fail));
  $("#tgo").onclick = async () => { try { const r = await say($("#ttxt").value, $("#tvoice").value); const o = $("#tout"); o.hidden = false;
    o.innerHTML = `<audio controls src="${r.url}" style="flex:1"></audio><button class="btn" id="taddlib">Kütüphaneye ekle</button>`;
    $("#taddlib").onclick = () => api("/api/media/add", { body: { paths: [r.path], kind: "audio" } }).then(() => toast("Kaynaklar'a eklendi")).catch(fail); } catch (e) { fail(e); } };
  v.querySelectorAll("[data-pl]").forEach(b => b.onclick = () => preview(`/api/media/${b.dataset.pl}/file`));
  $("#maddm").onclick = async () => { try { const r = await api("/api/media/pick", { body: { kind: "music" } }); if (r.items.length) viewAudio(); } catch (e) { fail(e); } };
}

// =====================================================================
// Efektler (transitions, SFX, looks)
// =====================================================================
const TR_DESC = { flas: "Kesimde kısa beyaz parlama", karart: "Siyaha inip geri açılır", zoom: "Kesimde hızlı yakınlaşma vuruşu", bulanik: "Kesim anında bulanıklaşır", kaydir: "Yana hızlı kaydırma hissi" };
let FX_TAB = "transitions";
async function viewEffects() {
  R = null;
  toolbar(`<span class="title">Efektler</span><span class="sub">geçişler, ses efektleri ve filtreler</span><span class="sp"></span>
    <div class="seg" id="fxseg">${[["transitions", "Geçişler"], ["sfx", "SFX"], ["looks", "Filtreler"]].map(([k, n]) => `<button data-k="${k}" class="${FX_TAB === k ? "on" : ""}">${n}</button>`).join("")}</div>
    <button class="btn primary" id="fxup">${I("plus", 14)} Yükle</button>`);
  const fx = await api("/api/fx"); const v = $("#view"); v.className = "view";
  $("#fxseg").querySelectorAll("button").forEach(b => b.onclick = () => { FX_TAB = b.dataset.k; viewEffects(); });
  const upKind = { transitions: "transition", sfx: "sfx", looks: "lut" }[FX_TAB];
  $("#fxup").onclick = async () => { try { const r = await api("/api/media/pick", { body: { kind: upKind } }); if (r.items.length) { toast(`${r.items.length} dosya eklendi`); viewEffects(); } } catch (e) { fail(e); } };
  const sample = (A.projects.find(p => p.kind === "reel") || {}).name;
  const sampleImg = sample ? `/api/p/${sample}/thumb?src=main&t=660` : "";
  if (FX_TAB === "transitions") {
    v.innerHTML = `<div class="page" style="max-width:980px"><h2>Geçişler</h2><p>Bir reelde cümleye tıkla, sağdaki panelden "Sonraki geçiş"i seç. Geçişler kesimi kaydırmaz, ses ile görüntü hep senkron kalır.</p>
      <div class="fxgrid">${fx.transitions.filter(t => t.id !== "none").map(t => `<div class="fxcard"><div class="fxprev tr-${t.id}" style="background-image:url('${sampleImg}')"><i></i></div><b>${t.name}</b><span class="small muted">${TR_DESC[t.id] || ""}</span></div>`).join("")}</div>
      <div class="group-title">Yüklediğin geçişler <span class="small muted">siyah zeminli ışık sızıntısı, film yanığı gibi videolar ya da şeffaf .mov</span></div>
      <div class="fxgrid">${fx.transition_assets.map(t => `<div class="fxcard" data-id="${t.id}"><div class="fxprev" style="background-image:url('/api/media/${t.id}/thumb?t=0.5')"></div><b>${esc(t.name)}</b><span class="small muted">${fdur(t.duration)}</span></div>`).join("") || '<div class="muted small">Henüz yok. Sağ üstten Yükle.</div>'}</div></div>`;
  } else if (FX_TAB === "sfx") {
    v.innerHTML = `<div class="page" style="max-width:980px"><h2>Ses efektleri</h2><p>Reelde zaman çizelgesine sağ tıklayıp "SFX ekle" ile oynatma çizgisinin olduğu yere koyarsın.</p>
      <div class="fxgrid">${fx.sfx.map(s => `<div class="fxcard sfx" data-id="${s.id}"><div class="fxprev wavep" style="background-image:url('/api/media/${s.id}/thumb')">${I("play", 22)}</div><b>${esc(s.name)}</b><span class="small muted">${s.builtin ? "hazır" : "yüklendi"} · ${fdur(s.duration)}</span></div>`).join("")}</div></div>`;
    v.querySelectorAll(".fxcard.sfx").forEach(c => { c.onclick = () => preview(`/api/media/${c.dataset.id}/file`);
      c.oncontextmenu = e => { e.preventDefault(); const it = fx.sfx.find(s => s.id === c.dataset.id); mediaMenu(it, e.clientX, e.clientY); }; });
  } else {
    v.innerHTML = `<div class="page" style="max-width:980px"><h2>Filtreler</h2><p>Bir reelin tamamına sağ paneldeki "Görünüm"den, tek bir plana da planın ayarlarından uygulanır. Önizleme yaklaşık, gerçek renk render'da.</p>
      <div class="fxgrid">${fx.looks.map(l => `<div class="fxcard"><div class="fxprev" style="background-image:url('${sampleImg}');filter:${LOOK_CSS[l.id] || "none"}"></div><b>${l.name}</b></div>`).join("")}</div>
      <div class="group-title">LUT dosyaların (.cube)</div>
      <div class="group">${fx.luts.map(l => `<div class="row"><div class="lbl"><b>${esc(l.name)}</b><span class="mono">${esc(l.path)}</span></div></div>`).join("") || '<div class="row muted">Henüz yok. Sağ üstten .cube dosyası yükle.</div>'}</div></div>`;
  }
}

// =====================================================================
// Ürün kaydı (Recordly)
// =====================================================================
async function viewRecord() {
  R = null;
  toolbar(`<span class="title">Ürün kaydı</span><span class="sub">ekran kaydı · Recordly ile</span><span class="sp"></span><button class="btn" id="rly">${I("ext", 14)} Recordly'yi aç</button>`);
  const d = await api("/api/rec"); const v = $("#view"); v.className = "view";
  v.innerHTML = `<div class="page"><h2>Ürün kaydı</h2><p>Ekranının ya da bir pencerenin kaydını al. Kayıt doğrudan Kaynaklar'a düşer. İmleç efektleri ve otomatik zoom için Recordly'de açabilirsin.</p>
    <div class="recbox">
      <div class="group" style="margin:0">
        <div class="row"><div class="lbl"><b>Ne kaydedilsin?</b></div><select id="rsrc">${d.displays.map(x => `<option value="d:${x.id}">${esc(x.name)} · ${x.w}×${x.h}</option>`).join("")}
          <optgroup label="Pencere">${d.windows.map(w => `<option value="w:${w.id}">${esc(w.app)} · ${esc((w.title || "").slice(0, 40))}</option>`).join("")}</optgroup></select></div>
        <div class="row"><div class="lbl"><b>Sistem sesi</b><span>bilgisayarda çalan ses</span></div><input type="checkbox" class="switch" id="rsys" checked></div>
        <div class="row"><div class="lbl"><b>Mikrofon</b></div><input type="checkbox" class="switch" id="rmic"></div>
        <div class="row"><div class="lbl"><b>İmleci videoya kaydet</b><span>kapalıysa imleç ayrı kaydedilir, Recordly sonradan şık bir imleç çizer</span></div><input type="checkbox" class="switch" id="rcur" checked></div>
      </div>
      <div class="recbtnwrap"><button class="recbtn ${d.running ? "on" : ""}" id="rgo"><i></i></button><div class="rectime" id="rtime">${d.running ? fmt(d.elapsed) : "hazır"}</div>
        <div class="small muted">${d.running ? "Durdurmak için tekrar bas" : "Başlatmak için bas"}</div></div>
    </div>
    <div class="group-title">${I("film", 14)} Kayıtlar</div>
    <div class="group">${d.recordings.length ? d.recordings.map(r => `<div class="row"><div class="lbl"><b>${esc(r.name)}</b><span>${r.source} · ${fsize(r.size)} · ${new Date(r.mtime * 1000).toLocaleString("tr-TR")}${r.cursor ? " · imleç verisi var" : ""}</span></div>
        <button class="btn" data-lib="${esc(r.path)}">Kaynaklar'a ekle</button><button class="btn" data-rl="${esc(r.path)}">Recordly'de cilala</button><button class="btn icon" data-fd="${esc(r.path)}" title="Finder'da göster">${I("ext", 14)}</button></div>`).join("") : '<div class="list-empty">Henüz kayıt yok.</div>'}</div>
    ${d.recordly_installed ? "" : '<div class="prob warn">Recordly.app ~/Applications altında bulunamadı. Kayıt yine çalışır, sadece cilalama için gerekli.</div>'}
  </div>`;
  $("#rly").onclick = () => api("/api/rec/recordly", { body: {} }).catch(fail);
  let timer = null;
  const tick = async () => { const s = await api("/api/rec"); if (!$("#rtime")) return clearInterval(timer); $("#rtime").textContent = s.running ? fmt(s.elapsed) : "hazır"; };
  if (d.running) timer = setInterval(tick, 500);
  $("#rgo").onclick = async () => {
    const b = $("#rgo");
    try {
      if (b.classList.contains("on")) { toast("Kayıt kapatılıyor…"); const r = await api("/api/rec/stop", { method: "POST" }); clearInterval(timer); toast("Kayıt Kaynaklar'a eklendi: " + r.item.name, 5000); viewRecord(); return; }
      const [k, id] = $("#rsrc").value.split(":");
      await api("/api/rec/start", { body: { display_id: k === "d" ? +id : null, window_id: k === "w" ? +id : null, system_audio: $("#rsys").checked, mic: $("#rmic").checked, cursor: $("#rcur").checked } });
      b.classList.add("on"); timer = setInterval(tick, 500); toast("Kayıt başladı");
    } catch (e) { fail(e); }
  };
  v.querySelectorAll("[data-lib]").forEach(b => b.onclick = () => api("/api/media/add", { body: { paths: [b.dataset.lib], kind: "video", speaker: "no" } }).then(() => toast("Kaynaklar'a eklendi")).catch(fail));
  v.querySelectorAll("[data-rl]").forEach(b => b.onclick = () => api("/api/rec/recordly", { body: { path: b.dataset.rl } }).then(() => toast("Recordly açılıyor")).catch(fail));
  v.querySelectorAll("[data-fd]").forEach(b => b.onclick = () => api("/api/reveal", { body: { path: b.dataset.fd } }));
}

// =====================================================================
// İndir (yt-dlp: TikTok, YouTube, Instagram, X ...)
// =====================================================================
const DL_ST = { "indiriliyor": "", "bitti": "ok", "hata": "err", "iptal": "" };
const fnum = n => n == null ? "" : n >= 1e6 ? (n / 1e6).toFixed(1) + " M" : n >= 1e3 ? (n / 1e3).toFixed(1) + " B" : String(n);
function dlForm(w = {}) {
  return `<div class="row"><div class="lbl"><b>Bağlantı</b><span>video, profil, hashtag, oynatma listesi</span></div><input type="text" id="durl" placeholder="https://www.tiktok.com/@kullanici" value="${esc(w.url || "")}" style="width:340px"></div>
    <div class="row"><div class="lbl"><b>Amaç</b><span>referans videolar sadece inceleme içindir, paylaşım kuyruğu onları reddeder</span></div>
      <div class="seg" id="dpur">${["kaynak", "referans"].map(k => `<button data-k="${k}" class="${(w.purpose || "kaynak") === k ? "on" : ""}">${k === "kaynak" ? "Kendi içeriğim" : "Referans"}</button>`).join("")}</div></div>
    <div class="row"><div class="lbl"><b>En fazla kaç video</b><span>profil ya da hashtag için, en yeniden başlar</span></div><input type="number" id="dlim" min="1" max="500" value="${w.limit || 10}" style="width:80px"></div>
    <div class="row"><div class="lbl"><b>Süre</b><span>saniye, boş bırakırsan sınır yok</span></div><input type="number" id="dmin" placeholder="en az" value="${w.min_dur || ""}" style="width:80px"><input type="number" id="dmax" placeholder="en çok" value="${w.max_dur || ""}" style="width:80px"></div>
    <div class="row"><div class="lbl"><b>En az izlenme</b></div><input type="number" id="dviews" placeholder="ör. 100000" value="${w.min_views || ""}" style="width:120px"></div>
    <div class="row"><div class="lbl"><b>Tarayıcı çerezleri</b><span>giriş isteyen ya da özel videolar için, oturumun o tarayıcıdan okunur</span></div>
      <select id="dck" style="width:140px">${["", "safari", "chrome", "firefox", "brave", "arc"].map(b => `<option value="${b}" ${w.cookies_browser === b ? "selected" : ""}>${b || "kullanma"}</option>`).join("")}</select></div>`;
}
function dlRead() {
  const n = id => $(id).value ? +$(id).value : null;
  return { url: $("#durl").value.trim(), purpose: $("#dpur .on").dataset.k, limit: n("#dlim"), min_dur: n("#dmin"), max_dur: n("#dmax"),
           min_views: n("#dviews"), cookies_browser: $("#dck").value || null };
}
function dlSeg(root) { root.querySelectorAll("#dpur button").forEach(b => b.onclick = () => { root.querySelectorAll("#dpur button").forEach(x => x.classList.remove("on")); b.classList.add("on"); }); }

async function viewDownload() {
  R = null;
  toolbar(`<span class="title">İndir</span><span class="sub">yt-dlp · TikTok, YouTube, Instagram, X ve daha fazlası</span><span class="sp"></span>
    <button class="btn" id="dfold">${I("ext", 14)} İndirme klasörü</button><button class="btn" id="dupd">${I("down", 14)} yt-dlp'yi güncelle</button>`);
  const d = await api("/api/dl"); const v = $("#view"); v.className = "view";
  try { A.settings = await api("/api/settings"); } catch (e) { /* switch just shows off */ }
  const running = d.jobs.some(j => j.status === "indiriliyor");
  v.innerHTML = `<div class="page"><h2>Video indir</h2><p>Bağlantıyı yapıştır, videolar indirilip Kaynaklar'a eklenir. Aynı video iki kez inmez. yt-dlp ${esc(d.version || "bulunamadı")} · <span class="mono small">${esc(d.folder)}</span></p>
    <div class="group">${dlForm()}<div class="row" style="justify-content:flex-end"><button class="btn" id="dwatch">${I("bolt", 14)} Takibe al</button><button class="btn primary" id="dgo">${I("down", 14)} İndir</button></div></div>
    <div class="group"><div class="row"><div class="lbl"><b>Video üretildikten sonra kullanılan videoları sil</b>
      <span>Sıralama render'ı bitince o videonun indirilen kaynak klipleri silinir, yer açılır. Sadece indirme önbelleğindekiler (_siralama) silinir, senin kendi dosyaların ve bitmiş videolar kalır. Sonradan yeniden render edersen kaynaklar tekrar indirilir.</span></div>
      <input type="checkbox" class="switch" id="dclean" ${A.settings && A.settings.cleanup_sources ? "checked" : ""}></div></div>
    <div class="group-title">${I("bolt", 14)} Takipler <span class="small muted" style="font-weight:400">belirli aralıkla yeni videoları kendisi indirir</span></div>
    <div class="group">${d.watches.length ? d.watches.map(w => `<div class="row"><div class="lbl"><b>${esc(w.name)}</b><span>${esc(w.url)} · her ${w.every_hours} saatte · en fazla ${w.limit} · ${w.purpose}${w.last_run ? " · son: " + new Date(w.last_run * 1000).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" }) : " · henüz çalışmadı"}</span></div>
        <input type="checkbox" class="switch" data-wen="${w.id}" ${w.enabled ? "checked" : ""} title="açık/kapalı"><button class="btn" data-wrun="${w.id}">Şimdi çalıştır</button><button class="btn icon" data-wdel="${w.id}" title="Takibi sil">${I("trash", 14)}</button></div>`).join("")
      : '<div class="list-empty">Takip yok. Bir profil ya da hashtag bağlantısı girip "Takibe al"a bas.</div>'}</div>
    <div class="group-title">${I("tray", 14)} İndirmeler</div>
    <div id="djobs">${dlJobs(d.jobs)}</div></div>`;
  dlSeg(v);
  $("#dclean").onchange = async e => {
    const on = e.target.checked;
    if (on && !await ask("Bundan sonra her sıralama videosu bitince, o videoda kullanılan indirilmiş kaynak klipler silinecek. Bitmiş videolar ve kendi dosyaların kalır.", "Aç")) { e.target.checked = false; return; }
    try { const r = await api("/api/settings", { body: { patch: { cleanup_sources: on } } }); A.settings = r.settings; toast(on ? "Açık: kaynaklar render sonrası silinecek" : "Kapalı: kaynaklar saklanacak"); } catch (err) { fail(err); e.target.checked = !on; }
  };
  $("#dgo").onclick = async () => { const o = dlRead(); if (!o.url) return toast("Önce bağlantı yapıştır");
    try { await api("/api/dl", { body: o }); toast("İndirme başladı"); viewDownload(); } catch (e) { fail(e); } };
  $("#dwatch").onclick = () => {
    const o = dlRead(); if (!o.url) return toast("Önce bağlantı yapıştır");
    const s = sheet("Takibe al", `<div class="group" style="margin:8px 0"><div class="row"><div class="lbl"><b>Ad</b></div><input type="text" id="wname" value="${esc(o.url.replace(/^https?:\/\/(www\.)?/, "").slice(0, 40))}"></div>
      <div class="row"><div class="lbl"><b>Kaç saatte bir</b></div><select id="wev">${[1, 3, 6, 12, 24, 72, 168].map(h => `<option value="${h}" ${h === 24 ? "selected" : ""}>${h < 24 ? h + " saat" : h / 24 + " gün"}</option>`).join("")}</select></div></div>`,
      `<button class="btn" data-x>Vazgeç</button><button class="btn primary" id="wok">Kaydet ve çalıştır</button>`);
    $("#wok").onclick = async () => { try { const r = await api("/api/dl/watch", { body: { ...o, name: $("#wname").value, every_hours: +$("#wev").value, enabled: true } });
      await api(`/api/dl/watch/${r.watch.id}/run`, { body: {} }); s.close(); toast("Takip kaydedildi, ilk indirme başladı"); viewDownload(); } catch (e) { fail(e); } };
  };
  v.querySelectorAll("[data-wrun]").forEach(b => b.onclick = () => api(`/api/dl/watch/${b.dataset.wrun}/run`, { body: {} }).then(() => { toast("Takip çalışıyor"); viewDownload(); }).catch(fail));
  v.querySelectorAll("[data-wdel]").forEach(b => b.onclick = async () => { if (!confirm("Bu takip silinsin mi? İndirilen videolar silinmez.")) return;
    await api(`/api/dl/watch/${b.dataset.wdel}`, { method: "DELETE" }).catch(fail); viewDownload(); });
  v.querySelectorAll("[data-wen]").forEach(b => b.onchange = () => { const w = d.watches.find(x => x.id === b.dataset.wen);
    api("/api/dl/watch", { body: { ...w, enabled: b.checked } }).then(() => toast(b.checked ? "Takip açık" : "Takip kapalı")).catch(fail); });
  $("#dupd").onclick = async () => { toast("yt-dlp güncelleniyor…", 8000); try { const r = await api("/api/dl/update", { body: {} }); toast(r.ok ? "yt-dlp " + r.version : "Güncellenemedi", 5000); viewDownload(); } catch (e) { fail(e); } };
  $("#dfold").onclick = async () => { try { const r = await api("/api/pick/folder", { body: { prompt: "İndirilen videolar nereye kaydedilsin?" } });
    if (r.path) { await api("/api/dl/folder", { body: { path: r.path } }); viewDownload(); } } catch (e) { fail(e); } };
  dlBind(v);
  if (running) A.poll = setInterval(async () => {
    if (!$("#djobs")) return; const n = await api("/api/dl"); $("#djobs").innerHTML = dlJobs(n.jobs); dlBind(v);
    if (!n.jobs.some(j => j.status === "indiriliyor")) { clearInterval(A.poll); A.poll = null; refreshProjects(); }
  }, 1200);
}
function dlJobs(jobs) {
  if (!jobs.length) return '<div class="group"><div class="list-empty">Henüz indirme yok.</div></div>';
  return jobs.map(j => `<div class="group"><div class="row"><div class="lbl"><b>${esc(j.url.replace(/^https?:\/\/(www\.)?/, ""))}</b>
      <span>${j.status === "indiriliyor" ? `%${Math.round(j.pct)} · ${esc(j.current || "hazırlanıyor")}` : new Date(j.started * 1000).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" })}
      · ${j.done} video${j.skipped ? ` · ${j.skipped} atlandı` : ""}</span></div>
      <span class="tag ${j.purpose === "referans" ? "warn" : ""}">${j.purpose}</span><span class="tag ${DL_ST[j.status] || ""}">${j.status}</span>
      ${j.status === "indiriliyor" ? `<button class="btn" data-dcan="${j.id}">Durdur</button>` : ""}</div>
    ${j.status === "indiriliyor" ? `<div class="row"><div class="bar" style="flex:1;height:4px;border-radius:2px;background:var(--line2);overflow:hidden"><i style="display:block;height:100%;width:${j.pct}%;background:var(--accent)"></i></div></div>` : ""}
    ${j.error ? `<div class="row"><div class="prob ${j.status === "hata" ? "error" : "warn"}" style="flex:1;margin:0">${esc(j.error)}</div></div>` : ""}
    ${j.items.map(it => `<div class="row"><div class="mthumb video" style="width:42px;height:56px;flex:none;border-radius:6px;background:#111 center/cover;background-image:url('/api/media/${it.id}/thumb?t=1')"></div>
      <div class="lbl"><b>${esc(it.title || it.name)}</b><span>${it.uploader ? "@" + esc(String(it.uploader).replace(/^@/, "")) : ""}${it.views != null ? " · " + fnum(it.views) + " izlenme" : ""}${it.duration ? " · " + fdur(it.duration) : ""}</span></div>
      ${j.purpose === "kaynak" ? `<button class="btn" data-reel="${it.id}" data-t="${esc(it.title || it.name)}">${I("phone", 14)} Reel yap</button>` : ""}
      <button class="btn icon" data-dfd="${esc(it.path)}" title="Finder'da göster">${I("ext", 14)}</button></div>`).join("")}</div>`).join("");
}
function dlBind(v) {
  v.querySelectorAll("[data-dcan]").forEach(b => b.onclick = () => api(`/api/dl/${b.dataset.dcan}/cancel`, { body: {} }).then(viewDownload).catch(fail));
  v.querySelectorAll("[data-dfd]").forEach(b => b.onclick = () => api("/api/reveal", { body: { path: b.dataset.dfd } }));
  v.querySelectorAll("[data-reel]").forEach(b => b.onclick = async () => {
    try { const r = await api("/api/projects/new", { body: { title: b.dataset.t.slice(0, 40), media_id: b.dataset.reel } }); await refreshProjects(); go(`#/p/${r.name}`); } catch (e) { fail(e); } });
}
