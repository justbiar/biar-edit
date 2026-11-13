// biar-edit · Edit stili: the versioned recipe every Ranked Legends video is made with.
// Change something, write why, save: it becomes the next version and applies from the next video on.
"use strict";
let SY = null;   // { state, draft }

const sgClone = o => JSON.parse(JSON.stringify(o));
const sgFlat = (o, pre = "") => Object.entries(o).reduce((a, [k, v]) => {
  if (["version", "note", "date", "after_video"].includes(k)) return a;
  if (v && typeof v === "object" && !Array.isArray(v)) Object.assign(a, sgFlat(v, pre + k + "."));
  else a[pre + k] = v;
  return a;
}, {});
function sgPatch() {   // only what differs from HEAD
  const h = sgFlat(SY.state.head), d = sgFlat(SY.draft), patch = {}, list = [];
  for (const k of Object.keys(d)) if (JSON.stringify(h[k]) !== JSON.stringify(d[k])) {
    const parts = k.split("."); let o = patch; parts.slice(0, -1).forEach(p => o = o[p] = o[p] || {}); o[parts.at(-1)] = d[k];
    list.push(SY.state.labels[k] || k);
  }
  return { patch, list };
}

async function viewStyle() {
  R = null;
  const st = await api("/api/style"); A.styleV = st.head.version; renderNav();
  SY = { state: st, draft: sgClone(st.head) };
  toolbar(`<span class="title">Edit stili</span><span class="sub">v${st.head.version} · ${st.next_video}. video bu tarifle yapılır</span><span class="sp"></span>
    <button class="btn" id="sgdoc">${I("ext", 14)} STYLE.md</button>`);
  $("#sgdoc").onclick = () => api("/api/reveal", { body: { path: st.files.style } }).catch(fail);
  drawStyle();
}

function drawStyle() {
  const st = SY.state, L = st.library, d = SY.draft, v = $("#view"); v.className = "view";
  const snd = (id, val) => `<div style="display:flex;gap:6px;align-items:center"><select data-k="${id}">${id.startsWith("comment.") ? `<option value="" ${val ? "" : "selected"}>yok (sessiz)</option>` : ""}${L.sounds.map(s => `<option value="${s.id}" ${s.id === val ? "selected" : ""}>${s.real ? "★ " : ""}${s.id}${s.desc ? " · " + s.desc : ""}</option>`).join("")}</select>
      <button class="btn icon" data-play="${id}" title="Dinle">${I("play", 12)}</button></div>`;
  const rng = (id, val, min, max, step, fmtf) => `<div style="display:flex;gap:8px;align-items:center"><input type="range" data-k="${id}" min="${min}" max="${max}" step="${step}" value="${val}" style="width:150px"><span class="small mono" data-out="${id}">${fmtf(val)}</span></div>`;
  const pct = x => "%" + Math.round(x * 100), db = x => x + " dB";
  const arr = (id, vals) => `<div style="display:flex;gap:6px">${[0, 1].map(k => `<select data-arr="${id}" data-i="${k}"><option value="">yok</option>${L.sounds.map(s => `<option value="${s.id}" ${vals[k] === s.id ? "selected" : ""}>${s.real ? "★ " : ""}${s.id}</option>`).join("")}</select>`).join("")}</div>`;
  const sw = (id, val) => `<input type="checkbox" class="switch" data-k="${id}" ${val ? "checked" : ""}>`;
  const seg = (id, opts, val) => `<div class="seg" data-seg="${id}">${Object.entries(opts).map(([k, o]) => `<button data-v="${k}" class="${k === val ? "on" : ""}">${esc(o.name || o)}</button>`).join("")}</div>`;
  const row = (t, sub, ctl) => `<div class="row"><div class="lbl"><b>${t}</b>${sub ? `<span>${sub}</span>` : ""}</div>${ctl}</div>`;
  v.innerHTML = `<div class="page" style="max-width:980px">
    <h2>Ranked Legends · edit tarifi <span class="tag">v${st.head.version}</span></h2>
    <p>Burada ne değiştirirsen yeni bir sürüm olur ve <b>${st.next_video}. videodan itibaren</b> bütün videolar öyle üretilir. Yayındaki ve onay bekleyen videolar değişmez. Değişiklik yoksa tarif aynen devam eder. Her videonun klasöründe ne ile yapıldığını yazan bir VIDEO.md var.</p>

    <div class="group-title">Filtre <span class="small muted">klip ve arka plan</span></div>
    <div class="fxgrid sgfilters">${Object.entries(L.filters).map(([k, f]) => `<div class="fxcard sgf ${d.filter === k ? "on" : ""}" data-f="${k}"><div class="fxprev sgfp" style="${st.sample ? `background-image:url('${st.sample}');` : ""}filter:${SG_CSS[k] || "none"}"></div><b>${esc(f.name)}</b><span class="small muted">${esc(f.why)}</span></div>`).join("")}</div>

    <div class="group-title">Geçiş ve sesler</div>
    <div class="group">
      ${row("Geçiş sesi", "her sıra açılırken", snd("transition.sound", d.transition.sound))}
      ${row("Geçiş sesi seviyesi", "", rng("transition.vol", d.transition.vol, 0, 1.5, 0.05, pct))}
      ${row("Geçiş görüntüsü", "", seg("transition.flash", L.flash, d.transition.flash))}
      ${row("Numara çıkış sesi", "#5, #4… ekrana gelince", snd("hit.sound", d.hit.sound))}
      ${row("Numara sesi seviyesi", "", rng("hit.vol", d.hit.vol, 0, 1.5, 0.05, pct))}
      ${row("#1 sesleri", "iki ses üst üste", arr("number1.sounds", d.number1.sounds))}
      ${row("#1 öncesi gerilim", "#2 biterken çalar", sw("number1.buildup", d.number1.buildup))}
      ${row("Gerilim sesleri", "ör. drumroll + riser", arr("number1.buildup_sounds", d.number1.buildup_sounds))}
      ${row("Olay anına otomatik ses", "elle an seçilmemiş sıralarda klipteki en sert anı bulup oraya ses koyar (referans kanallar böyle yapıyor)", sw("moment.auto", d.moment.auto))}
      ${row("An seslerini olaya yapıştır", "elle verilen saniyeyi ±0.8 sn içindeki gerçek darbeye kaydırır", sw("moment.snap", d.moment.snap))}
      ${row("Olay anı sesi", "", snd("moment.sound", d.moment.sound))}
      ${row("Olay anı sesi seviyesi", "", rng("moment.vol", d.moment.vol, 0, 1.5, 0.05, pct))}
      ${row("Yorum kayma sesi", "yorum yazısı gelirken", snd("comment.slide", d.comment.slide))}
      ${row("Yorum tık sesi", "", snd("comment.tick", d.comment.tick))}
      ${row("Giriş sesleri", "başlık kartı", arr("intro_outro.intro", d.intro_outro.intro))}
      ${row("Kapanış sesleri", "CTA kartı", arr("intro_outro.outro", d.intro_outro.outro))}
      ${row("Tüm SFX seviyesi", "", rng("sfx_gain", d.sfx_gain, 0, 1.6, 0.05, pct))}
    </div>

    <div class="group-title">Efektler</div>
    <div class="group">
      ${row("Kamera sallama", L.shake[d.effects.shake].why, seg("effects.shake", L.shake, d.effects.shake))}
      ${row("Vuruşta zoom", "numara çıkınca ve vuruş SFX'lerinde görüntü içeri zıplar", sw("effects.zoom_punch", d.effects.zoom_punch))}
      ${row("Film kumlanması", "", sw("effects.grain", d.effects.grain))}
      ${row("Kenar karartma", "gözü klibe toplar", sw("effects.vignette", d.effects.vignette))}
    </div>

    <div class="group-title">Yazı</div>
    <div class="group">
      ${row("Vurgu rengi", L.accents[d.text.accent].why, `<div style="display:flex;gap:8px">${Object.entries(L.accents).map(([k, a]) => `<button class="sgsw ${d.text.accent === k ? "on" : ""}" data-acc="${k}" title="${esc(a.name)}" style="background:rgb(${a.rgb.join(",")})"></button>`).join("")}</div>`)}
      ${row("Numarada parlama", "numaranın arkasında vurgu renginde ışık", sw("text.glow", d.text.glow))}
    </div>

    <div class="group-title">CTA</div>
    <div class="group">
      ${row("Giriş etiketi", "", `<input type="text" data-k="cta.intro" value="${esc(d.cta.intro)}" style="width:320px">`)}
      ${row("Kapanış sorusu", "yorum getiren soru", `<input type="text" data-k="cta.question" value="${esc(d.cta.question)}" style="width:320px">`)}
      ${row("Kapanış butonu", "", `<input type="text" data-k="cta.button" value="${esc(d.cta.button)}" style="width:320px">`)}
    </div>

    <div class="group-title">Müzik</div>
    <div class="group">
      ${row("Müzik seviyesi", "konuşmada otomatik kısılır", rng("music.gain_db", d.music.gain_db, -26, -8, 1, db))}
      ${row("Drop #1'e denk gelsin", "", sw("music.sync_drop", d.music.sync_drop))}
    </div>

    <div class="sgbar" id="sgbar"></div>

    <div class="group-title">Sürüm geçmişi</div>
    <div class="group">${st.history.map(h => `<div class="row" style="align-items:flex-start"><div class="lbl"><b>v${h.version} <span class="small muted">${h.date} · ${h.from_video}. videodan itibaren</span></b>
      <span>${esc(h.note)}</span>${h.changes.length ? `<span class="small">${h.changes.map(esc).join("<br>")}</span>` : ""}</div>
      <span class="small muted">${h.videos.length ? "videolar: " + h.videos.map(n => String(n).padStart(2, "0")).join(", ") : "henüz video yok"}</span></div>`).join("")}</div>
  </div>`;
  bindStyle(); drawBar();
}

const SG_CSS = { bw_contrast: "grayscale(1) contrast(1.35)", vivid: "saturate(1.6) contrast(1.1)", teal_orange: "sepia(.25) hue-rotate(-12deg) saturate(1.3) contrast(1.06)",
  cinematic: "contrast(1.12) saturate(.85) brightness(.95)", warm: "sepia(.35) saturate(1.2)", cold: "hue-rotate(15deg) saturate(.9) brightness(1.05) contrast(1.08)",
  vhs: "saturate(1.4) contrast(1.05) blur(.6px)" };

function sgSet(key, val) {
  const p = key.split("."); let o = SY.draft; p.slice(0, -1).forEach(k => o = o[k]); o[p.at(-1)] = val;
}
function bindStyle() {
  const v = $("#view");
  v.querySelectorAll(".sgf").forEach(c => c.onclick = () => { SY.draft.filter = c.dataset.f; v.querySelectorAll(".sgf").forEach(x => x.classList.toggle("on", x === c)); drawBar(); });
  v.querySelectorAll("[data-k]").forEach(el => {
    const upd = () => {
      const val = el.type === "checkbox" ? el.checked : el.type === "range" ? Number(el.value) : el.value.replace(/—/g, ",");
      sgSet(el.dataset.k, val);
      const o = v.querySelector(`[data-out="${el.dataset.k}"]`); if (o) o.textContent = el.dataset.k === "music.gain_db" ? val + " dB" : "%" + Math.round(val * 100);
      if (el.tagName === "SELECT" && el.value) preview(`/api/sfx/${el.value}.wav`);   // hear it right away
      drawBar();
    };
    if (el.tagName === "SELECT") el.onchange = upd; else { el.oninput = upd; el.onchange = upd; }
  });
  v.querySelectorAll("[data-seg]").forEach(sg => sg.querySelectorAll("button").forEach(b => b.onclick = () => {
    sgSet(sg.dataset.seg, b.dataset.v); sg.querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b));
    if (sg.dataset.seg === "effects.shake") { const s = sg.closest(".row").querySelector(".lbl span"); if (s) s.textContent = SY.state.library.shake[b.dataset.v].why; }
    drawBar();
  }));
  v.querySelectorAll("[data-arr]").forEach(s => s.onchange = () => {
    sgSet(s.dataset.arr, [...v.querySelectorAll(`[data-arr="${s.dataset.arr}"]`)].map(x => x.value).filter(Boolean));
    if (s.value) preview(`/api/sfx/${s.value}.wav`);
    drawBar();
  });
  v.querySelectorAll("[data-acc]").forEach(b => b.onclick = () => {
    SY.draft.text.accent = b.dataset.acc; v.querySelectorAll("[data-acc]").forEach(x => x.classList.toggle("on", x === b));
    b.closest(".row").querySelector(".lbl span").textContent = SY.state.library.accents[b.dataset.acc].why; drawBar();
  });
  // macOS opens the popup on arrow keys; here up/down step through the sounds and play each one
  v.querySelectorAll("select").forEach(sel => sel.addEventListener("keydown", e => {
    if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
    e.preventDefault();
    const i = clamp(sel.selectedIndex + (e.key === "ArrowDown" ? 1 : -1), 0, sel.options.length - 1);
    if (i === sel.selectedIndex) return;
    sel.selectedIndex = i; sel.dispatchEvent(new Event("change"));
  }));
  v.querySelectorAll("[data-play]").forEach(b => b.onclick = () => {
    const sel = v.querySelector(`select[data-k="${b.dataset.play}"]`); preview(`/api/sfx/${sel.value}.wav`);
  });
}

function drawBar() {
  const { list } = sgPatch(), el = $("#sgbar"), next = SY.state.head.version + 1;
  el.innerHTML = `<div class="group" style="margin:18px 0">
    <div class="row"><div class="lbl"><b>${list.length ? `${list.length} değişiklik` : "Değişiklik yok"}</b><span>${list.length ? esc(list.join(", ")) : "Bir şey değiştirince burada görünür. Önizle ile son videonun #1'ini yeni stille görebilirsin."}</span></div>
      <button class="btn" id="sgpv">${I("play", 13)} Önizle</button></div>
    ${list.length ? `<div class="row"><input type="text" id="sgnote" placeholder="Neden? (ör. 2. videoda CTA zayıf kaldı)" style="flex:1">
      <button class="btn" id="sgreset">Vazgeç</button><button class="btn primary" id="sgsave">${I("save", 13)} v${next} olarak kaydet</button></div>` : ""}
    <div id="sgpvbox"></div></div>`;
  $("#sgpv").onclick = stylePreview;
  if (list.length) {
    $("#sgreset").onclick = () => { SY.draft = sgClone(SY.state.head); drawStyle(); };
    $("#sgsave").onclick = async () => {
      const note = $("#sgnote").value.trim();
      if (!note) { toast("Kısa bir not yaz: neden değiştiriyorsun? Sürüm geçmişinde ve VIDEO.md'de görünecek."); $("#sgnote").focus(); return; }
      if (!await ask(`Yeni sürüm v${next}: ${list.join(", ")}. ${SY.state.next_video}. videodan itibaren bütün videolar böyle üretilecek.`, `v${next} olarak kaydet`)) return;
      try { const r = await api("/api/style", { body: { patch: sgPatch().patch, note } }); toast(`v${r.version} kaydedildi`); viewStyle(); } catch (e) { fail(e); }
    };
  }
}

async function stylePreview() {
  const b = $("#sgpv"), box = $("#sgpvbox"); b.disabled = true; b.innerHTML = `${I("render", 13)} hazırlanıyor… (~20 sn)`;
  try {
    const r = await api("/api/style/preview", { body: { patch: sgPatch().patch } });
    box.innerHTML = `<div class="row" style="justify-content:center"><video src="${r.url}" controls autoplay playsinline style="height:520px;border-radius:12px;background:#000"></video></div>
      <div class="row small muted" style="justify-content:center">${esc(r.project)} · #1 sırası, ilk 4.5 saniye. Kaydetmeden önce istediğin kadar dene.</div>`;
  } catch (e) { fail(e); }
  b.disabled = false; b.innerHTML = `${I("play", 13)} Önizle`;
}
