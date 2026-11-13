"""Versioned edit style ("edit tarifi") for a channel, like git for the look of the videos.

  channels/<slug>/style.json          HEAD: the recipe the next video will be made with
  channels/<slug>/versions/v003.json  every committed version, never edited afterwards
  channels/<slug>/STYLE.md            the rules, the current recipe and the change log (generated)
  channels/<slug>/LIBRARY.md          every filter / effect / sound you can pick (generated)
  projects/<rankNN>/VIDEO.md          what one video was made with and what changed since the last one

A video is locked to the style version that was HEAD when it was created (ranking.json
"style_version"), so re-rendering an old video gives the same result. Changing the style makes a new
version that applies from the next video on.

  python -I biaredit/style.py show            current version as JSON
  python -I biaredit/style.py docs            regenerate STYLE.md, LIBRARY.md and every VIDEO.md
"""
import copy, datetime, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
CHANNEL = "ranked-legends"
CDIR = os.path.join(ROOT, "channels", CHANNEL)
VDIR = os.path.join(CDIR, "versions")
PROJ = os.path.join(ROOT, "projects")

# ---------------------------------------------------------------- library
# Everything the style can point at. "why" is the reason it holds attention, shown in the app and LIBRARY.md.
FILTERS = {
    "none":        {"name": "Yok", "ff": "", "why": "Kaynağın kendi rengi."},
    "bw_contrast": {"name": "Siyah beyaz kontrast", "ff": "hue=s=0,eq=contrast=1.32:brightness=-0.03,unsharp=5:5:0.9",
                    "why": "Anime/edit hesaplarının imza görünümü. Renk gidince göz yazıya ve yüze kayar, renkli yazı çok öne çıkar."},
    "vivid":       {"name": "Canlı pop", "ff": "eq=saturation=1.45:contrast=1.1,unsharp=5:5:0.5",
                    "why": "Akışta en parlak video olur, kaydırırken durdurur. Gün ışığı, spor, oyun kliplerinde iyi."},
    "teal_orange": {"name": "Teal and orange", "ff": "colorbalance=rs=-0.1:gs=-0.02:bs=0.12:rh=0.1:gh=0.02:bh=-0.1,eq=saturation=1.15:contrast=1.06",
                    "why": "Hollywood fragmanı rengi. Ten tonu turuncu, gölgeler mavi, her şey 'film' gibi durur."},
    "cinematic":   {"name": "Sinematik", "ff": "eq=contrast=1.12:saturation=0.85:gamma=0.95,colorbalance=bs=0.06:rh=0.05",
                    "why": "Biraz soluk, kontrastlı. Ciddi, epik konularda (uzay, tarih) ağırlık katar."},
    "warm":        {"name": "Sıcak altın", "ff": "colortemperature=temperature=4800,eq=saturation=1.15",
                    "why": "Nostalji ve 'efsane an' hissi. Eski klipleri birbirine benzetir."},
    "cold":        {"name": "Soğuk mavi", "ff": "colortemperature=temperature=8500,eq=contrast=1.08",
                    "why": "Teknoloji, gerilim, gece. Sarı yazıyla en yüksek kontrastı verir."},
    "vhs":         {"name": "VHS retro", "ff": "rgbashift=rh=5:bh=-5,eq=saturation=1.3:contrast=1.05,noise=alls=14:allf=t,gblur=sigma=0.6",
                    "why": "Renk kayması ve kumlanma. 90'lar/2000'ler anları için, meme hissi verir."},
}
SHAKE = {
    "off":      {"name": "Kapalı", "amp": 0, "base": 0, "why": ""},
    "hit":      {"name": "Vuruşlarda", "amp": 14, "base": 0, "why": "Numara çıkınca ve SFX vuruşlarında kısa sarsıntı. Darbeyi 'hissettirir'."},
    "strong":   {"name": "Güçlü vuruş", "amp": 28, "base": 0, "why": "Daha sert sarsıntı. Kaza, patlama, çarpma anlarında etkili; her videoda yorabilir."},
    "handheld": {"name": "El kamerası", "amp": 14, "base": 3, "why": "Sürekli çok hafif sallanma + vuruşlar. Edit hesaplarında 'canlı' görüntü hissi."},
}
FLASH = {"white": "Beyaz flaş", "black": "Siyaha kesme", "none": "Düz kesme"}
ACCENTS = {
    "yellow": {"name": "Sarı", "rgb": [255, 214, 10], "why": "Koyu zeminde en okunur renk. Şu ana kadarki imza rengimiz."},
    "red":    {"name": "Kırmızı", "rgb": [255, 38, 38], "why": "Örnekteki edit görünümü. Siyah beyaz filtreyle çok güçlü durur."},
    "cyan":   {"name": "Camgöbeği", "rgb": [0, 229, 255], "why": "Teknoloji ve oyun konularında. Sıcak kliplerin üstünde ayrışır."},
    "green":  {"name": "Neon yeşil", "rgb": [57, 255, 20], "why": "Oyun ve 'kazandı' anları. Çok dikkat çeker, az kullan."},
    "pink":   {"name": "Neon pembe", "rgb": [255, 46, 160], "why": "Viral/meme konularında, TikTok rengi."},
}
HIT_SOUNDS = {"vine_boom", "sinematik_boom", "cam_kirilma", "flashbang", "impact", "bass", "metal_boru", "darbe", "gong", "kasa"}
SOUND_DESC = {
    "whoosh": "hızlı rüzgar, geçişin standart sesi", "kayma": "yumuşak kayma, sakin geçiş", "pop": "baloncuk, hafif ve eğlenceli",
    "tik": "tık, yazı belirince", "impact": "kısa darbe, numara çıkınca", "bass": "derin bas vuruşu", "vine_boom": "meme boom, şaşırtıcı an",
    "sinematik_boom": "fragman boom'u, epik an", "cam_kirilma": "cam kırılması", "siren": "alarm/siren, kaos anı", "flas": "kamera flaşı",
    "flashbang": "kulak çınlaması, şok anı", "kasa": "yazar kasa, para", "buzzer": "yanlış cevap", "gong": "gong, final", "metal_boru": "metal boru düşmesi, meme",
    "plak_cizik": "plak cızırtısı, 'dur bir saniye' anı", "tiktak": "saat tik takı, gerilim", "coin": "oyun parası", "gerilim": "gerilim yükselişi",
    "ding": "zil, doğru cevap", "davul": "trampet, #1 öncesi", "yukselen": "yükselen ses, #1 öncesi", "darbe": "boğuk darbe", "zil": "zil",
}

def _fs():
    try: return json.load(open(os.path.join(ROOT, "media", "sfx", "freesound.json")))
    except (FileNotFoundError, json.JSONDecodeError): return {}

def sounds():
    return sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(ROOT, "media", "sfx", "*.wav")))

def sound_info():
    """[{id, desc, hit, real}] real recordings (Freesound CC0) first, then the old synthesized ones."""
    fs = _fs(); out = []
    for s in sounds():
        if s in fs: out.append({"id": s, "desc": f"{fs[s]['use']} ({fs[s]['title'][:30]})", "hit": fs[s]["hit"], "real": True})
        else: out.append({"id": s, "desc": "sentez · " + SOUND_DESC.get(s, ""), "hit": s in HIT_SOUNDS, "real": False})
    return sorted(out, key=lambda x: (not x["real"], x["id"]))

def is_hit(name): return name in HIT_SOUNDS or bool(_fs().get(name, {}).get("hit"))

# ---------------------------------------------------------------- the recipe
# v1 reproduces exactly how videos 01 to 03 were made.
DEFAULT = {
    "transition": {"sound": "whoosh", "vol": 0.55, "flash": "white"},
    "hit": {"sound": "impact", "vol": 0.9},
    "number1": {"sounds": ["ding", "bass"], "buildup": True, "buildup_sounds": ["davul", "yukselen"]},
    "comment": {"slide": "kayma", "tick": "tik"},
    "moment": {"auto": False, "snap": False, "sound": "impact", "vol": 0.85},
    "intro_outro": {"intro": ["yukselen", "impact"], "outro": ["whoosh", "pop"]},
    "filter": "none",
    "effects": {"shake": "off", "zoom_punch": False, "grain": False, "vignette": False},
    "text": {"accent": "yellow", "glow": False},
    "cta": {"intro": "5 to 1", "question": "Which one deserved #1?", "button": "Tell us in the comments"},
    "music": {"gain_db": -15, "sync_drop": True},
    "sfx_gain": 1.0,
}
LABELS = {
    "transition.sound": "Geçiş sesi", "transition.vol": "Geçiş sesi seviyesi", "transition.flash": "Geçiş görüntüsü",
    "hit.sound": "Numara çıkış sesi", "hit.vol": "Numara sesi seviyesi", "number1.sounds": "#1 sesleri", "number1.buildup": "#1 öncesi gerilim", "number1.buildup_sounds": "#1 öncesi gerilim sesleri",
    "moment.auto": "Olay anına otomatik ses", "moment.snap": "An seslerini olaya yapıştır",
    "moment.sound": "Olay anı sesi", "moment.vol": "Olay anı sesi seviyesi", "comment.slide": "Yorum kayma sesi", "comment.tick": "Yorum tık sesi", "intro_outro.intro": "Giriş sesleri", "intro_outro.outro": "Kapanış sesleri",
    "filter": "Filtre", "effects.shake": "Kamera sallama", "effects.zoom_punch": "Vuruşta zoom", "effects.grain": "Film kumlanması",
    "effects.vignette": "Kenar karartma", "text.accent": "Vurgu rengi", "text.glow": "Numarada parlama", "cta.intro": "Giriş etiketi",
    "cta.question": "Kapanış sorusu (CTA)", "cta.button": "Kapanış butonu (CTA)", "music.gain_db": "Müzik seviyesi (dB)",
    "music.sync_drop": "Drop #1'e denk gelsin", "sfx_gain": "Tüm SFX seviyesi",
}

def merge(base, patch):
    out = copy.deepcopy(base)
    for k, v in (patch or {}).items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out

def flat(d, pre=""):
    out = {}
    for k, v in d.items():
        if k in ("version", "note", "date", "after_video"): continue
        if isinstance(v, dict): out.update(flat(v, pre + k + "."))
        else: out[pre + k] = v
    return out

def pretty(key, v):
    if key == "filter": return FILTERS.get(v, {}).get("name", v)
    if key == "effects.shake": return SHAKE.get(v, {}).get("name", v)
    if key == "transition.flash": return FLASH.get(v, v)
    if key == "text.accent": return ACCENTS.get(v, {}).get("name", v)
    if isinstance(v, bool): return "açık" if v else "kapalı"
    if isinstance(v, list): return ", ".join(map(str, v)) or "yok"
    if key.endswith(".vol") or key == "sfx_gain": return f"%{round(float(v) * 100)}"
    if isinstance(v, str) and key.startswith("cta."): return f'"{v}"'
    return str(v)

def diff(a, b):
    fa, fb = flat(a or {}), flat(b or {})
    return [{"key": k, "label": LABELS.get(k, k), "old": fa.get(k), "new": fb.get(k), "text": f"{LABELS.get(k, k)}: {pretty(k, fa.get(k))} → {pretty(k, fb.get(k))}"}
            for k in sorted(set(fa) | set(fb), key=lambda k: list(LABELS).index(k) if k in LABELS else 99) if fa.get(k) != fb.get(k)]

def validate(st):
    errs = []
    if st["filter"] not in FILTERS: errs.append(f"bilinmeyen filtre: {st['filter']}")
    if st["effects"]["shake"] not in SHAKE: errs.append(f"bilinmeyen sallama: {st['effects']['shake']}")
    if st["transition"]["flash"] not in FLASH: errs.append("geçiş görüntüsü white/black/none olmalı")
    if st["text"]["accent"] not in ACCENTS: errs.append(f"bilinmeyen renk: {st['text']['accent']}")
    have = set(sounds())
    for s in [st["transition"]["sound"], st["hit"]["sound"], *st["number1"]["sounds"], *st["number1"]["buildup_sounds"],
              st["comment"]["slide"], st["comment"]["tick"], st["moment"]["sound"], *st["intro_outro"]["intro"], *st["intro_outro"]["outro"]]:
        if s and s not in have: errs.append(f"ses yok: {s}")    # "" = silent
    for k in ("intro", "question", "button"):
        if "—" in st["cta"][k]: errs.append("CTA'da uzun tire (—) kullanma")
    return errs

# ---------------------------------------------------------------- store
def _vpath(n): return os.path.join(VDIR, f"v{n:03d}.json")

def versions():
    out = []
    for p in sorted(glob.glob(os.path.join(VDIR, "v*.json"))):
        try: out.append(json.load(open(p)))
        except json.JSONDecodeError: pass
    return out

def ensure():
    if not versions():
        os.makedirs(VDIR, exist_ok=True)
        v1 = {"version": 1, "date": datetime.date.today().isoformat(), "after_video": 0,
              "note": "İlk stil: Ranked Legends 01-03 bu tarifle yapıldı.", **copy.deepcopy(DEFAULT)}
        json.dump(v1, open(_vpath(1), "w"), ensure_ascii=False, indent=1)
        json.dump(v1, open(os.path.join(CDIR, "style.json"), "w"), ensure_ascii=False, indent=1)

def head():
    ensure()
    return merge(DEFAULT, versions()[-1])

def get(n):
    ensure()
    if n is None: return merge(DEFAULT, {})
    p = _vpath(int(n))
    return merge(DEFAULT, json.load(open(p))) if os.path.exists(p) else head()

def commit(patch, note):
    """New version from HEAD + patch. Returns (version, changes); no new version if nothing changed."""
    cur = head(); new = merge(cur, patch)
    for k in ("version", "date", "note", "after_video"): new.pop(k, None)
    ch = diff(cur, new)
    if not ch: return cur, []
    errs = validate(merge(DEFAULT, new))
    if errs: raise ValueError("; ".join(errs))
    note = (note or "").replace("—", ",").strip() or "not yok"
    new = {"version": cur["version"] + 1, "date": datetime.date.today().isoformat(), "after_video": last_video_no(), "note": note, **new}
    json.dump(new, open(_vpath(new["version"]), "w"), ensure_ascii=False, indent=1)
    json.dump(new, open(os.path.join(CDIR, "style.json"), "w"), ensure_ascii=False, indent=1)
    write_docs()
    return new, ch

# ---------------------------------------------------------------- videos
def video_no(spec):
    m = re.match(r"Ranked Legends (\d+)", spec.get("name", ""))
    return int(m.group(1)) if m else None

def channel_videos():
    """[(no, project, spec)] for every Ranked Legends video, oldest first."""
    out = []
    for d in sorted(glob.glob(os.path.join(PROJ, "rank*"))):
        try: spec = json.load(open(os.path.join(d, "ranking.json")))
        except (FileNotFoundError, json.JSONDecodeError): continue
        n = video_no(spec)
        if n: out.append((n, os.path.basename(d), spec))
    return sorted(out)

def last_video_no():
    v = channel_videos(); return v[-1][0] if v else 0

def describe(st):
    """The recipe as markdown bullet lines."""
    e, t, c = st["effects"], st["text"], st["cta"]
    return [f"- **Filtre:** {pretty('filter', st['filter'])}",
            f"- **Geçiş:** {st['transition']['sound']} sesi ({pretty('transition.vol', st['transition']['vol'])}), {FLASH[st['transition']['flash']].lower()}",
            f"- **Numara çıkışı:** {st['hit']['sound']} sesi ({pretty('hit.vol', st['hit']['vol'])}), pop animasyonu",
            f"- **#1:** {pretty('number1.sounds', st['number1']['sounds'])}" + (f", öncesinde {pretty('', st['number1']['buildup_sounds'])}" if st["number1"]["buildup"] else ""),
            f"- **Olay anı:** " + (f"klipteki en sert ana otomatik {st['moment']['sound']}" if st["moment"]["auto"] else "sadece elle seçilen anlar")
            + (", an sesleri gerçek olaya yapıştırılır" if st["moment"]["snap"] else ""),
            f"- **Yorum:** {st['comment']['slide'] or 'sessiz'} + {st['comment']['tick'] or 'sessiz'} · **Giriş:** {pretty('', st['intro_outro']['intro'])} · **Kapanış:** {pretty('', st['intro_outro']['outro'])}",
            f"- **Efektler:** kamera sallama {SHAKE[e['shake']]['name'].lower()}, vuruşta zoom {pretty('', e['zoom_punch'])}, "
            f"kumlanma {pretty('', e['grain'])}, kenar karartma {pretty('', e['vignette'])}",
            f"- **Yazı:** beyaz + siyah kontur, vurgu rengi {ACCENTS[t['accent']]['name'].lower()}" + (", numarada parlama" if t["glow"] else ""),
            f"- **CTA:** giriş \"{c['intro']}\", kapanış \"{c['question']}\" + buton \"{c['button']}\"",
            f"- **Müzik:** en az kullanılan NCS parçası, {st['music']['gain_db']} dB, konuşmada kısılır" + (", drop #1'e denk gelir" if st["music"]["sync_drop"] else ""),
            f"- **SFX seviyesi:** {pretty('sfx_gain', st['sfx_gain'])}"]

RULES = """## Kurallar (her güncellemede aynen uygulanır)

1. **Stil = edit tarifi.** Geçiş sesi, filtre, efektler, renk, CTA ve müzik ayarı `style.json`'da durur. Videonun konusu ve klipleri tarif değildir, her gün değişir.
2. **Değişiklik = yeni sürüm.** Uygulamada Stil ekranından ya da `style.commit()` ile yapılır. Her sürüm bir not taşır ("CTA zayıf kaldı" gibi). Eski sürüm dosyaları (`versions/vNNN.json`) asla düzenlenmez.
3. **Sürüm sonraki videodan itibaren geçerli.** Video oluşturulduğu anki sürüme kilitlenir (`ranking.json` > `style_version`). Yayındaki ya da onay bekleyen video kendiliğinden değişmez. Yeniden render aynı sonucu verir.
4. **Değişiklik yoksa tarif aynen devam eder.** Bir sonraki video aynı sürümle yapılır, VIDEO.md'de "değişiklik yok" yazar.
5. **Her videonun VIDEO.md dosyası var.** Konu, sıralama, kaynaklar, kullanılan stil sürümü, tarifin tamamı ve bir önceki videoya göre ne değiştiği yazar. Elle düzenleme, otomatik üretilir.
6. **Otomasyon stili kendisi değiştirmez.** Günlük çalışma sadece öneri yazabilir ("şu filtre denenebilir"). Yeni sürümü sen onaylarsın.
7. **Kütüphane dışından seçim yok.** Filtre, efekt ve ses `LIBRARY.md`'deki listeden seçilir. Yeni bir şey eklenecekse önce kütüphaneye eklenir, sonra seçilir.
8. **Telif.** Ses efektleri kendi ürettiğimiz sentez sesler, müzik NCS (kredi açıklamaya otomatik eklenir). Başkasının SFX derlemesinden ses kesilmez.
9. **Yazım.** Ekrandaki hiçbir yazıda, başlıkta ve açıklamada uzun tire (—) kullanılmaz.
"""

def write_style_md():
    st = head(); vs = versions(); vids = channel_videos()
    used = {}
    for n, p, s in vids: used.setdefault(s.get("style_version", 1), []).append(n)
    lines = [f"# Ranked Legends · edit stili", "",
             f"Şu anki sürüm: **v{st['version']}** ({st['date']}). Bir sonraki video bu tarifle yapılır.", "",
             *describe(st), "", RULES, "## Sürüm geçmişi", "",
             "| Sürüm | Tarih | Hangi videodan itibaren | Not | Değişenler | Kullanan videolar |", "|---|---|---|---|---|---|"]
    prev = None
    for v in vs:
        ch = "ilk sürüm" if prev is None else "<br>".join(c["text"] for c in diff(merge(DEFAULT, prev), merge(DEFAULT, v)))
        lines.append(f"| v{v['version']} | {v['date']} | {v.get('after_video', 0) + 1}. video | {v.get('note', '')} | {ch} | "
                     f"{', '.join(f'{x:02d}' for x in used.get(v['version'], [])) or 'henüz yok'} |")
        prev = v
    lines += ["", "Seçilebilir her şey: [LIBRARY.md](LIBRARY.md)", ""]
    open(os.path.join(CDIR, "STYLE.md"), "w").write("\n".join(lines))

def write_library_md():
    L = ["# Ranked Legends · efekt kütüphanesi", "",
         "Stil sadece bu listeden seçer. Yeni bir filtre ya da efekt bulunursa önce buraya (`biaredit/style.py`) eklenir.", "",
         "## Filtreler", "", "| id | Ad | Neden dikkat çeker | ffmpeg |", "|---|---|---|---|"]
    L += [f"| `{k}` | {v['name']} | {v['why']} | `{v['ff'] or '-'}` |" for k, v in FILTERS.items()]
    L += ["", "## Kamera sallama", "", "| id | Ad | Ne zaman |", "|---|---|---|"]
    L += [f"| `{k}` | {v['name']} | {v['why'] or '-'} |" for k, v in SHAKE.items()]
    L += ["", "## Diğer efektler", "",
          "| id | Ad | Neden |", "|---|---|---|",
          "| `zoom_punch` | Vuruşta zoom | Numara çıkınca ve vuruşlarda görüntü bir an içeri zıplar. Sallamayla birlikte en çok kullanılan edit hareketi. |",
          "| `grain` | Film kumlanması | Farklı kaynakları tek bir 'film' gibi gösterir, sinematik/VHS filtreyle iyi gider. |",
          "| `vignette` | Kenar karartma | Gözü ortadaki klibe toplar. |",
          "| `glow` | Numarada parlama | Numaranın arkasında vurgu renginde ışık. Örnekteki kırmızı parlayan yazı gibi. |",
          "", "## Geçiş görüntüsü", "", *[f"- `{k}`: {v}" for k, v in FLASH.items()],
          "", "## Vurgu renkleri", "", "| id | Ad | Neden |", "|---|---|---|"]
    L += [f"| `{k}` | {v['name']} | {v['why']} |" for k, v in ACCENTS.items()]
    L += ["", "## Ses efektleri", "", "Gerçek kayıtlar Freesound'dan, hepsi CC0 (telifsiz, kredi gerekmez, kaynaklar `media/sfx/CREDITS.md`). "
          "'sentez' olanlar ffmpeg ile ürettiğimiz eski sesler. Paketi büyütmek: `biaredit/sfxpack.py`'ye kategori ekle, çalıştır.", "",
          "| id | Ne | Vuruş |", "|---|---|---|"]
    L += [f"| `{x['id']}` | {x['desc']} | {'evet, sallama/zoom tetikler' if x['hit'] else ''} |" for x in sound_info()]
    open(os.path.join(CDIR, "LIBRARY.md"), "w").write("\n".join(L) + "\n")

def write_video_md(project, posts=None):
    d = os.path.join(PROJ, project); spec = json.load(open(os.path.join(d, "ranking.json")))
    n = video_no(spec)
    if not n: return None
    sv = spec.get("style_version", 1); st = get(sv)
    vids = channel_videos(); prev = next((x for x in reversed(vids) if x[0] < n), None)
    rj = os.path.join(d, "work", "rendered.json")
    rend = json.load(open(rj)) if os.path.exists(rj) else {}
    post = next((p for p in (posts or []) if p.get("project") == project), None)
    status = "henüz kuyrukta değil"; link = ""
    if post:
        t = post["targets"].get("youtube") or {}; status = t.get("status", "?"); link = t.get("url", "")
        pa = (post.get("options", {}).get("youtube") or {}).get("publish_at")
        if pa:
            from zoneinfo import ZoneInfo
            status += " · yayın " + datetime.datetime.fromtimestamp(pa, ZoneInfo("Europe/Istanbul")).strftime("%d.%m %H:%M") + " (TR)"
    mu = spec.get("music") or {}
    L = [f"# {spec.get('name', project)}", "",
         "| | |", "|---|---|", f"| Proje | `{project}` |", f"| Video no | {n:02d} |", f"| Stil | v{sv} ([STYLE.md](../../channels/{CHANNEL}/STYLE.md)) |",
         f"| Durum | {status} |", f"| YouTube | {link or '-'} |", f"| Süre | {round(rend['duration'], 1)} sn |" if rend.get("duration") else "| Süre | render yok |",
         f"| Müzik | {(mu.get('credit') or '').splitlines()[0] if mu.get('credit') else None or os.path.basename(mu.get('path', '')) or '-'} |", f"| Dosya | `{spec.get('output', '')}` |", "",
         "## Sıralama", ""]
    for it in spec["items"]:
        L.append(f"**#{it['rank']} {it['label']}** · {it.get('sub', '')}  ")
        L.append(f"{it.get('comment', '').replace('*', '')}  ")
        L.append(f"Kaynak: {it.get('credit', '')} · {it.get('url', '')} · kesit {', '.join(f'{a}-{b}' for a, b in it.get('parts', []))}"
                 + (f" · SFX {', '.join(f'{s[0]}@{s[1]}' for s in it.get('sfx') or [])}" if it.get("sfx") else ""))
        L.append("")
    L += [f"## Edit tarifi (stil v{sv})", "", *describe(st), "", "## Önceki videoya göre", ""]
    if not prev:
        L.append("Kanalın ilk videosu.")
    else:
        pv = prev[2].get("style_version", 1)
        if pv == sv: L.append(f"Değişiklik yok. Ranked Legends {prev[0]:02d} ile aynı tarif (v{sv}).")
        else:
            L.append(f"Stil v{pv} → v{sv}. Ranked Legends {prev[0]:02d}'e göre değişenler:")
            L.append("")
            for k in range(pv + 1, sv + 1):
                v = get(k); L.append(f"- v{k} notu: {v.get('note', '')}")
            L += [f"- {c['text']}" for c in diff(get(pv), st)]
    L.append("")
    open(os.path.join(d, "VIDEO.md"), "w").write("\n".join(L))
    return os.path.join(d, "VIDEO.md")

def write_docs(posts=None):
    ensure(); os.makedirs(CDIR, exist_ok=True)
    if posts is None:
        try:
            sys.path.insert(0, HERE); import social; posts = social.list_posts()
        except Exception: posts = []
    write_style_md(); write_library_md()
    return [write_video_md(p, posts) for _, p, _ in channel_videos()]

if __name__ == "__main__":
    a = sys.argv[1:] or ["show"]
    if a[0] == "show": print(json.dumps(head(), ensure_ascii=False, indent=1))
    elif a[0] == "docs": print(json.dumps(write_docs(), ensure_ascii=False))
