"""biar-edit local server.  Usage: python -I biaredit/server.py [port]   (default 8790)

Pages
  GET  /                          app (macOS-style editor)
API (state-changing calls need header X-Biar-Token; the pages get it injected, automation reads
it from the Keychain: `security find-generic-password -s biar-edit -a api_token -w`)
  GET  /api                       machine-readable list of every endpoint
  ...  see API_DOC below
"""
import http.server, json, os, re, subprocess, sys, threading, time, urllib.parse, uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.join(ROOT, "projects")
WEB = os.path.join(ROOT, "web")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PATH"] = "/opt/homebrew/opt/ffmpeg-full/bin:" + os.environ.get("PATH", "")
from render_project import validate
from reel_project import validate as validate_reel
from ranking import validate as validate_ranking
import settings as S, ai, social, media, fetch, style as STY

RENDERS = {}
PORT = 8790
TOKEN = None

API_DOC = [
    ("GET", "/api/projects", "Proje listesi (tür ile)."),
    ("GET", "/api/p/{name}", "Proje içeriği. Reel ise {reel, problems, has_output}."),
    ("POST", "/api/p/{name}", "Projeyi kaydet (gövde = reel.json ya da project.json). Her kayıt history/ altına yedeklenir."),
    ("POST", "/api/p/{name}/render", "Render başlat. Kırmızı uyarı varsa reddeder."),
    ("GET", "/api/p/{name}/status", "Render ilerlemesi {step, pct, running}."),
    ("GET", "/api/p/{name}/output", "Render edilmiş reel videosu."),
    ("GET", "/api/p/{name}/peaks?src=&a=&b=&n=", "Ses dalga formu (0-1 arası n değer)."),
    ("GET", "/api/p/{name}/thumb?src=&t=", "Kaynaktan küçük kare (jpg)."),
    ("GET", "/api/media", "Medya kütüphanesi (video, ses, müzik, sfx, geçiş, lut)."),
    ("POST", "/api/media/pick", "{kind?, speaker?} macOS dosya seçme penceresini açar, seçilenleri kütüphaneye ekler."),
    ("POST", "/api/media/add", "{paths:[], kind?, speaker?} yol ile ekler."),
    ("POST", "/api/media/{id}", "{name?, kind?, speaker?, tags?} günceller."),
    ("DELETE", "/api/media/{id}", "Kütüphaneden çıkarır (dosyayı silmez)."),
    ("GET", "/api/dl", "İndirme işleri, takipler, yt-dlp sürümü ve indirme klasörü."),
    ("POST", "/api/dl", "{url, purpose: kaynak|referans, limit?, max_dur?, min_dur?, min_views?, after?, cookies_browser?} yt-dlp ile indirir, Kaynaklar'a ekler."),
    ("GET", "/api/dl/{id}", "Tek indirme işi (son log satırları ile)."),
    ("POST", "/api/dl/{id}/cancel", "İndirmeyi durdurur."),
    ("POST", "/api/dl/watch", "{id?, name, url, every_hours, limit, purpose, max_dur?, min_views?, enabled} takip ekler/günceller."),
    ("POST", "/api/dl/watch/{id}/run", "Takibi şimdi çalıştırır."),
    ("DELETE", "/api/dl/watch/{id}", "Takibi siler (indirilen dosyalara dokunmaz)."),
    ("GET", "/api/dl/search?q=&n=", "YouTube araması (indirmeden): id, başlık, kanal, süre, izlenme."),
    ("GET", "/api/dl/cues?url=&find=&lang=", "Videonun zaman damgalı altyazısı; find ile içinde geçen satırlar. Kesit bulmak için."),
    ("GET", "/api/style", "Kanalın sürümlü edit stili: şu anki tarif, sürüm geçmişi, kütüphane (filtre, efekt, ses)."),
    ("POST", "/api/style", "{patch, note} yeni stil sürümü oluşturur. Sonraki videodan itibaren geçerli. Sadece kullanıcı isteyince."),
    ("POST", "/api/style/preview", "{patch?, project?} son videonun #1'ini bu stille birkaç saniye render eder, url döner."),
    ("POST", "/api/youtube/{video_id}", "{privacy?: public|unlisted|private, title?, description?} yüklenmiş YouTube videosunu günceller."),
    ("POST", "/api/dl/update", "yt-dlp'yi Homebrew ile günceller."),
    ("POST", "/api/dl/folder", "{path} indirme klasörünü değiştirir."),
    ("GET", "/api/fx", "Geçişler, filtreler, SFX ve LUT listesi."),
    ("POST", "/api/projects/new", "{title, media_id?} yeni reel projesi."),
    ("POST", "/api/p/{name}/source", "{media_id, key?, speaker?} projeye kaynak ekler."),
    ("POST", "/api/p/{name}/output", "{dir} çıktı klasörünü değiştirir."),
    ("GET", "/api/rec", "Ürün kaydı: durum, ekranlar, pencereler, kayıtlar."),
    ("POST", "/api/rec/start", "{display_id?|window_id?, system_audio, mic, cursor} kaydı başlatır."),
    ("POST", "/api/rec/stop", "Kaydı bitirir, kütüphaneye ekler."),
    ("POST", "/api/rec/recordly", "{path?} Recordly'de açar (imleç efektleri, otomatik zoom)."),
    ("POST", "/api/ai/clone", "{name, media_ids:[]} ElevenLabs ile ses klonlar, ses modeli olarak kaydeder."),
    ("GET", "/api/settings", "Ayarlar. Anahtarların kendisi değil, sadece var/yok bilgisi döner."),
    ("POST", "/api/settings", "{patch:{...}, secrets:{anthropic_api_key:'...'}} Anahtarlar Keychain'e yazılır."),
    ("GET", "/api/ai/models?provider=", "anthropic | openrouter | ollama | elevenlabs modelleri/sesleri."),
    ("POST", "/api/ai/test", "{provider} bağlantı testi."),
    ("POST", "/api/ai/chat", "{provider?, model?, system?, messages:[{role,content}]} -> {text}"),
    ("POST", "/api/ai/caption", "{project, platform?} reel altyazılarından paylaşım metni üretir."),
    ("POST", "/api/ai/tts", "{text, voice_id?} ElevenLabs ile seslendirir -> {url, path}"),
    ("GET", "/api/social", "Platformlar, bağlantı durumu ve callback adresi."),
    ("POST", "/api/social/{x|linkedin|instagram|youtube}/connect", "OAuth giriş adresini döner."),
    ("POST", "/api/social/{p}/paste", "{url} giriş sonrası adres (https zorunlu platformlar için)."),
    ("POST", "/api/social/{p}/disconnect", "Bağlantıyı kaldırır."),
    ("GET", "/api/posts", "Paylaşım kuyruğu."),
    ("POST", "/api/posts", "{video|project, captions:{default,x,...}, platforms:[], when?, approved?} Otomasyondan gelen gönderi onay bekler (hesapta otomatik paylaş açık değilse)."),
    ("POST", "/api/posts/{id}", "{approve:true} | {cancel:true} | {captions} | {when}"),
    ("DELETE", "/api/posts/{id}", "Gönderiyi kuyruktan sil."),
]

def words_of(pdir):
    v = os.path.join(pdir, "data", "verbatim.json")
    if not os.path.exists(v):
        return []
    words = [{"w": x["w"], "s": x["s"], "e": x["e"]} for x in json.load(open(v))]
    g = os.path.join(pdir, "data", "gaps.json")
    if words and os.path.exists(g):
        first = words[0]["s"]
        words = [{"w": x["w"], "s": x["s"], "e": x["e"]} for x in json.load(open(g))["words"] if x["e"] <= first - 0.05] + words
    return words

PJ = {"reel": "reel.json", "film": "project.json", "ranking": "ranking.json"}
def project_kind(d):
    return next((k for k, f in PJ.items() if os.path.exists(os.path.join(d, f))), None)

def reel_output(d):
    k = project_kind(d)
    if k == "ranking":
        r = json.load(open(os.path.join(d, "ranking.json")))
        return r.get("output") or os.path.join(d, "work", "preview.mp4")
    return json.load(open(os.path.join(d, "reel.json")))["output"]

def validator(kind):
    return {"reel": validate_reel, "film": validate, "ranking": validate_ranking}[kind]

def source_path(d, src):
    f = "reel.json" if project_kind(d) == "reel" else "project.json"
    s = json.load(open(os.path.join(d, f)))["sources"].get(src)
    if not s: raise KeyError(src)
    return s["path"], s.get("hdr")

def peaks(d, src, a, b, n):
    cache = os.path.join(d, "work", "peaks"); os.makedirs(cache, exist_ok=True)
    key = os.path.join(cache, f"{src}_{a:.2f}_{b:.2f}_{n}.json")
    if os.path.exists(key): return json.load(open(key))
    path, _ = source_path(d, src)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(max(0.05, b - a)), "-i", path, "-map", "0:a:0",
                          "-ac", "1", "-ar", "4000", "-f", "s16le", "-"], capture_output=True).stdout
    import numpy as np
    x = np.abs(np.frombuffer(raw, np.int16).astype(np.float32)) / 32768
    if len(x) < n: out = [0.0] * n
    else:
        x = x[: len(x) // n * n].reshape(n, -1)
        v = np.sqrt((x ** 2).mean(1)); v = v / max(1e-6, np.percentile(v, 98))
        out = [round(float(min(1, t)), 3) for t in v]
    json.dump(out, open(key, "w")); return out

def thumb(d, src, t):
    cache = os.path.join(d, "work", "thumbs"); os.makedirs(cache, exist_ok=True)
    key = os.path.join(cache, f"{src}_{t:.1f}.jpg")
    if not os.path.exists(key):
        path, hdr = source_path(d, src)
        vf = "scale=-2:180"
        if hdr:
            vf = "zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0:peak=4,zscale=t=bt709:m=bt709:r=tv,format=yuv420p," + vf
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", path, "-frames:v", "1", "-vf", vf + ",format=yuvj420p", "-q:v", "4", key])
    return key

def media_thumb(it, t):
    cache = os.path.join(S.APP_DIR, "thumbs"); os.makedirs(cache, exist_ok=True)
    key = os.path.join(cache, f"{it['id']}_{t:.1f}.jpg")
    if not os.path.exists(key):
        if it["kind"] in ("audio", "music", "sfx", "lut"):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", it["path"], "-filter_complex", "showwavespic=s=320x120:colors=#11e08a", "-frames:v", "1", key])
        else:
            vf = "scale=-2:200"
            if it.get("hdr"):
                vf = "zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0:peak=4,zscale=t=bt709:m=bt709:r=tv,format=yuv420p," + vf
            tt = min(t, max(0, (it.get("duration") or 2) - 0.2)) if it["kind"] != "image" else 0
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(tt), "-i", it["path"], "-frames:v", "1", "-vf", vf + ",format=yuvj420p", "-q:v", "4", key])
    return key

def new_reel(b):
    title = (b.get("title") or "Yeni reel").strip()
    n = 1
    while os.path.exists(os.path.join(PROJ, f"reel{n:02d}")): n += 1
    name = f"reel{n:02d}"; d = os.path.join(PROJ, name); os.makedirs(d)
    sources, beats = {}, []
    it = media.get(b["media_id"]) if b.get("media_id") else None
    if it:
        key = re.sub(r"\W+", "_", it["name"]).strip("_")[:24] or "kaynak"
        sources[key] = {"path": it["path"], "speaker": it["speaker"] if it["speaker"] in ("yes", "no", "sometimes") else "sometimes"}
        dur = min(8.0, it.get("duration") or 8.0)
        beats.append({"audio": {"src": key, "a": 0.0, "b": round(dur, 2)}, "shots": [{"kind": "sync", "layout": "crop"}], "caps": [], "titles": []})
    out_dir = S.load().get("export_dir") or os.path.expanduser("~/Desktop")
    safe = re.sub(r"[^\w\- ]+", "", title).strip() or name
    r = {"type": "reel", "name": f"Reel {n:02d} · {title}", "cap_y": 1400, "output": os.path.join(out_dir, f"reel {n:02d} - {safe}.mp4"),
         "sources": sources, "beats": beats, "end_card": None, "audio": {"lufs": -14}, "look": {"filter": "none"}, "sfx": []}
    json.dump(r, open(os.path.join(d, "reel.json"), "w"), ensure_ascii=False, indent=1)
    return name

def new_ranking(b):
    title = (b.get("title") or "Yeni sıralama").strip()
    n = 1
    while os.path.exists(os.path.join(PROJ, f"rank{n:02d}")): n += 1
    name = f"rank{n:02d}"; d = os.path.join(PROJ, name); os.makedirs(d)
    out_dir = S.load().get("export_dir") or os.path.expanduser("~/Desktop")
    safe = re.sub(r"[^\w\- ]+", "", title).strip() or name
    r = {"type": "ranking", "name": f"Sıralama {n:02d} · {title}", "kicker": "EN İYİ 5", "title": title.upper(), "intro": "5'ten 1'e",
         "outro": ["Sence 1 numara hangisi olmalıydı?", "Yorumlara yaz"], "output": os.path.join(out_dir, f"siralama {n:02d} - {safe}.mp4"),
         "items": [{"rank": k, "label": "", "sub": "", "comment": "", "credit": "", "url": "", "parts": []} for k in range(5, 0, -1)]}
    json.dump(r, open(os.path.join(d, "ranking.json"), "w"), ensure_ascii=False, indent=1)
    return name

def reel_text(d):
    if project_kind(d) == "ranking":
        r = json.load(open(os.path.join(d, "ranking.json")))
        items = " / ".join(f"#{it['rank']} {it['label']}" for it in r["items"])
        return r.get("name", ""), " ".join(it.get("comment", "").replace("*", "") for it in r["items"]), f"{r.get('kicker', '')} {r.get('title', '')}: {items}"
    r = json.load(open(os.path.join(d, "reel.json")))
    caps = " ".join(c["text"] for b in r["beats"] for c in b.get("caps", []))
    titles = " / ".join(t["text"] for b in r["beats"] for t in b.get("titles", []))
    return r.get("name", ""), caps, titles

def make_caption(d, platform=None):
    name, caps, titles = reel_text(d)
    prov, model = ai.pick_text_provider()
    cfg = S.load()
    style = {"x": "X için en fazla 260 karakter, 2-3 hashtag.", "linkedin": "LinkedIn için profesyonel ama samimi, 3-5 cümle, 3 hashtag.",
             "instagram": "Instagram için kısa, samimi, emoji az, sonunda 5-7 hashtag.",
             "youtube": "YouTube Shorts için: ilk satır en fazla 70 karakterlik merak uyandıran başlık, altına 2-3 cümle açıklama ve 3 hashtag. Kanal İngilizce ise İngilizce yaz."}.get(platform, "")
    prompt = (f"{cfg['automation']['caption_prompt']}\n{style}\n\nReel adı: {name}\nEkrandaki başlıklar: {titles}\n"
              f"Konuşmanın altyazısı: {caps}\n\nSadece paylaşım metnini yaz, açıklama ekleme.")
    text = ai.chat(prov, model, [{"role": "user", "content": prompt}], max_tokens=600)
    return text.replace("\u2014", ",").strip(), prov, model

def after_render(name, d, proc):
    """Automation hook: when a reel render finishes, optionally draft a post into the queue."""
    proc.wait()
    rule = S.load()["automation"].get("after_render") or {}
    if proc.returncode != 0 or not rule.get("enabled") or project_kind(d) != "reel":
        return
    try:
        caps = {"default": make_caption(d)[0]}
    except Exception as e:
        caps = {"default": "", "note": f"Açıklama üretilemedi: {e}"}
    try:
        social.create_post(reel_output(d), caps, rule.get("platforms", []), source="otomasyon: render sonrası", project=name)
    except Exception:
        pass

def inject(html):
    js = ("<script>window.BIAR_TOKEN=%s;(function(){const f=window.fetch;window.fetch=(u,o={})=>{"
          "if(typeof u==='string'&&u.startsWith('/')){o.headers=Object.assign({'X-Biar-Token':window.BIAR_TOKEN},o.headers||{})}"
          "return f(u,o)}})();</script>") % json.dumps(TOKEN)
    return html.replace("<head>", "<head>" + js, 1)

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass

    # ---- plumbing ----
    def send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)

    def send_html(self, html, code=200):
        b = html.encode(); self.send_response(code); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)

    def send_file(self, path):
        if not os.path.isfile(path): return self.send_error(404)
        ext = os.path.splitext(path)[1].lower()
        if ext == ".html": return self.send_html(inject(open(path, encoding="utf-8").read()))
        size = os.path.getsize(path)
        ctype = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".png": "image/png", ".mp3": "audio/mpeg", ".svg": "image/svg+xml",
                 ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json"}.get(ext, "application/octet-stream")
        rng = self.headers.get("Range"); start, end = 0, size - 1
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            start = int(m.group(1)) if m.group(1) else 0
            end = min(int(m.group(2)) if m.group(2) else size - 1, size - 1)
            self.send_response(206); self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype); self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1)); self.send_header("Cache-Control", "no-store"); self.end_headers()
        with open(path, "rb") as f:
            f.seek(start); left = end - start + 1
            try:
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk: break
                    self.wfile.write(chunk); left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError): pass

    def body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def project_dir(self, name):
        d = os.path.realpath(os.path.join(PROJ, name))
        if not d.startswith(os.path.realpath(PROJ) + os.sep) or not os.path.isdir(d): return None
        return d

    def host_ok(self):
        # refuse DNS-rebinding: only answer to our own host names
        h = (self.headers.get("Host") or "").split(":")[0]
        return h in ("localhost", "127.0.0.1", "[::1]")

    def guarded(self):
        if not self.host_ok():
            self.send_error(403); return False
        if self.headers.get("X-Biar-Token") != TOKEN:
            self.send_json({"ok": False, "msg": "X-Biar-Token eksik ya da yanlış."}, 401); return False
        return True

    def q(self):
        return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()}

    # ---- GET ----
    def do_GET(self):
        if not self.host_ok(): return self.send_error(403)
        path = urllib.parse.unquote(self.path.split("?")[0]); q = self.q()
        try:
            if path in ("/", "/app", "/index.html"): return self.send_file(os.path.join(WEB, "app.html"))
            m = re.match(r"^/web/([\w.\-]+)$", path)
            if m: return self.send_file(os.path.join(WEB, m.group(1)))
            if path == "/api/style": return self.send_json(style_state())
            m = re.match(r"^/api/sfx/(\w+)\.wav$", path)
            if m: return self.send_file(os.path.join(ROOT, "media", "sfx", m.group(1) + ".wav"))
            if path == "/api/style/preview.mp4": return self.send_file(os.path.join(S.APP_DIR, "style_preview.mp4"))
            if path == "/api": return self.send_json([{"method": a, "path": b, "info": c} for a, b, c in API_DOC])
            if path == "/api/projects":
                out = []
                for n in sorted(os.listdir(PROJ)):
                    d = os.path.join(PROJ, n); k = project_kind(d)
                    if not k: continue
                    meta = json.load(open(os.path.join(d, PJ[k])))
                    out.append({"name": n, "kind": k, "title": meta.get("name", n), "modified": os.path.getmtime(os.path.join(d, PJ[k]))})
                return self.send_json(out)
            if path == "/api/settings": return self.send_json({**S.public_view(), "root": ROOT})
            if path == "/api/media": return self.send_json(media.library())
            if path == "/api/fx":
                lib = media.library()
                return self.send_json({"transitions": media.TRANSITIONS, "looks": media.LOOKS,
                                       "sfx": [i for i in lib if i["kind"] == "sfx"], "music": [i for i in lib if i["kind"] in ("music", "audio")],
                                       "transition_assets": [i for i in lib if i["kind"] == "transition"], "luts": [i for i in lib if i["kind"] == "lut"]})
            m = re.match(r"^/api/media/(\w+)/(file|thumb)$", path)
            if m:
                it = media.get(m.group(1))
                if not it: return self.send_error(404)
                if m.group(2) == "file": return self.send_file(it["path"])
                return self.send_file(media_thumb(it, float(q.get("t", 1))))
            if path == "/api/dl":
                return self.send_json({"jobs": fetch.jobs(), "watches": fetch.watches(), "version": fetch.version(), "folder": fetch.folder()})
            if path == "/api/dl/search": return self.send_json(fetch.search(q.get("q", ""), int(q.get("n", 6))))
            if path == "/api/dl/cues":
                c = fetch.cues(q["url"], q.get("lang", "en")); f = q.get("find", "").lower()
                return self.send_json([x for x in c if f in x["text"].lower()] if f else c)
            m = re.match(r"^/api/dl/(\w+)$", path)
            if m:
                j = fetch.job(m.group(1))
                return self.send_json(j) if j else self.send_error(404)
            if path == "/api/rec":
                return self.send_json({**media.rec_status(), "displays": media.displays(), "windows": media.windows(), "recordings": media.recordings()})
            if path == "/api/ai/models":
                return self.send_json({"ok": True, "models": ai.models(q.get("provider", ""))})
            if path == "/api/social":
                cfg = S.public_view()["accounts"]
                return self.send_json({"redirect": social.REDIRECT.format(port=PORT),
                                       "platforms": {k: {**v, **cfg[k]} for k, v in social.PLATFORMS.items()}})
            if path == "/api/posts": return self.send_json(social.list_posts())
            m = re.match(r"^/api/tts/([0-9a-f]+\.mp3)$", path)
            if m: return self.send_file(os.path.join(S.APP_DIR, "tts", m.group(1)))
            if path == "/oauth/callback":
                if "error" in q:
                    return self.send_html(f"<h2>Bağlantı iptal edildi</h2><p>{q.get('error_description', q['error'])}</p>")
                p, handle = social.finish_oauth(q.get("code", ""), q.get("state", ""), PORT)
                return self.send_html(f"<body style='font:15px -apple-system;padding:40px'><h2>{social.PLATFORMS[p]['name']} bağlandı: {handle}</h2>"
                                      "<p>Bu pencereyi kapatabilirsin.</p><script>setTimeout(()=>window.close(),1500)</script></body>")
            m = re.match(r"^/api/p/([^/]+)/(output|preview|peaks|thumb|status)$", path)
            if m:
                d = self.project_dir(m.group(1))
                if not d: return self.send_error(404)
                what = m.group(2)
                if what == "output": return self.send_file(reel_output(d))
                if what == "preview": return self.send_file(os.path.join(d, "work", "preview.mp4"))
                if what == "peaks": return self.send_json(peaks(d, q["src"], float(q["a"]), float(q["b"]), int(q.get("n", 200))))
                if what == "thumb": return self.send_file(thumb(d, q["src"], float(q.get("t", 0))))
                st = os.path.join(d, "work", "status.json")
                s = json.load(open(st)) if os.path.exists(st) else {"step": "hazır", "pct": None}
                s["running"] = m.group(1) in RENDERS and RENDERS[m.group(1)].poll() is None
                return self.send_json(s)
            m = re.match(r"^/api/p/([^/]+)$", path)
            if m:
                d = self.project_dir(m.group(1))
                if not d: return self.send_error(404)
                if project_kind(d) == "reel":
                    r = json.load(open(os.path.join(d, "reel.json"))); out = r["output"]
                    pv = os.path.join(d, "work", "preview.mp4")
                    return self.send_json({"reel": r, "problems": validate_reel(r), "has_output": os.path.exists(out),
                                           "output_mtime": os.path.getmtime(out) if os.path.exists(out) else None,
                                           "has_preview": os.path.exists(pv), "preview_mtime": os.path.getmtime(pv) if os.path.exists(pv) else None,
                                           "rendered": json.load(open(os.path.join(d, "work", "rendered.json"))) if os.path.exists(os.path.join(d, "work", "rendered.json")) else None})
                if project_kind(d) == "ranking":
                    r = json.load(open(os.path.join(d, "ranking.json"))); out = reel_output(d); rj = os.path.join(d, "work", "rendered.json")
                    return self.send_json({"ranking": r, "problems": validate_ranking(r), "has_output": os.path.exists(out),
                                           "output_mtime": os.path.getmtime(out) if os.path.exists(out) else None,
                                           "rendered": json.load(open(rj)) if os.path.exists(rj) else None})
                p = json.load(open(os.path.join(d, "project.json")))
                return self.send_json({"project": p, "words": words_of(d), "problems": validate(p)})
            m = re.match(r"^/p/([^/]+)/(.+)$", path)
            if m:
                d = self.project_dir(m.group(1)); f = os.path.realpath(os.path.join(d or "", m.group(2)))
                if not d or not f.startswith(d + os.sep): return self.send_error(404)
                return self.send_file(f)
            self.send_error(404)
        except (ai.AIError, social.SocialError) as e:
            self.send_json({"ok": False, "msg": str(e)}, 400)
        except KeyError as e:
            self.send_json({"ok": False, "msg": f"eksik alan: {e}"}, 400)

    # ---- POST / DELETE ----
    def do_DELETE(self):
        if not self.guarded(): return
        path = self.path.split("?")[0]
        m = re.match(r"^/api/dl/watch/(\w+)$", path)
        if m: fetch.delete_watch(m.group(1)); return self.send_json({"ok": True})
        m = re.match(r"^/api/(posts|media)/(\w+)$", path)
        if not m: return self.send_error(404)
        (social.delete_post if m.group(1) == "posts" else media.remove)(m.group(2))
        moved = []
        if m.group(1) == "posts":                       # a freed publish slot pulls the later autopilot videos up
            try: import autopilot; moved = autopilot.compact()
            except Exception as e: moved = [{"error": str(e)}]
        self.send_json({"ok": True, "moved": moved})

    def do_POST(self):
        if not self.guarded(): return
        path = self.path.split("?")[0]
        try:
            b = self.body()
            if path == "/api/dl":
                o = {k: b.get(k) for k in ("purpose", "limit", "max_dur", "min_dur", "min_views", "after", "speaker", "cookies_browser") if b.get(k) not in (None, "")}
                return self.send_json({"ok": True, "job": {k: v for k, v in fetch.start(b["url"], **o).items() if k != "log"}})
            if path == "/api/dl/update": return self.send_json(fetch.update_ytdlp())
            if path == "/api/style":
                try: v, ch = STY.commit(b.get("patch") or {}, b.get("note"))
                except ValueError as e: return self.send_json({"ok": False, "msg": str(e)}, 400)
                return self.send_json({"ok": True, "version": v["version"], "changes": ch, **style_state()})
            if path == "/api/style/preview":
                import ranking
                vids = STY.channel_videos(); proj = b.get("project") or (vids[-1][1] if vids else None)
                if not proj: return self.send_json({"ok": False, "msg": "Önizleme için en az bir Ranked Legends videosu lazım."}, 400)
                st = STY.merge(STY.head(), b.get("patch") or {})
                errs = STY.validate(st)
                if errs: return self.send_json({"ok": False, "msg": "; ".join(errs)}, 400)
                ranking.preview(os.path.join(PROJ, proj), st, os.path.join(S.APP_DIR, "style_preview.mp4"), b.get("rank_index"))
                return self.send_json({"ok": True, "url": f"/api/style/preview.mp4?m={int(time.time())}", "project": proj})
            if path == "/api/dl/folder":
                S.save({**S.load(), "download_dir": b["path"]}); return self.send_json({"ok": True, "folder": fetch.folder()})
            if path == "/api/dl/watch": return self.send_json({"ok": True, "watch": fetch.save_watch(b)})
            m = re.match(r"^/api/dl/watch/(\w+)/run$", path)
            if m: j = fetch.run_watch(m.group(1)); return self.send_json({"ok": True, "job": {k: v for k, v in j.items() if k != "log"}})
            m = re.match(r"^/api/dl/(\w+)/cancel$", path)
            if m: return self.send_json({"ok": fetch.cancel(m.group(1))})
            if path == "/api/media/pick":
                paths = media.pick_files("biar-edit · kaynak ekle")
                return self.send_json({"ok": True, "items": media.add(paths, b.get("kind"), b.get("speaker"))})
            if path == "/api/media/add": return self.send_json({"ok": True, "items": media.add(b["paths"], b.get("kind"), b.get("speaker"))})
            if path == "/api/pick/folder": return self.send_json({"ok": True, "path": media.pick_folder(b.get("prompt", "Klasör seç"))})
            if path == "/api/reveal": media.reveal(b["path"]); return self.send_json({"ok": True})
            m = re.match(r"^/api/media/(\w+)$", path)
            if m: return self.send_json({"ok": True, "item": media.update(m.group(1), b)})
            if path == "/api/rec/start":
                return self.send_json({"ok": True, **media.rec_start(b.get("display_id"), b.get("window_id"), b.get("system_audio", True), b.get("mic", False), b.get("cursor", True))})
            if path == "/api/rec/stop": return self.send_json({"ok": True, "item": media.rec_stop()})
            if path == "/api/rec/recordly": media.open_in_recordly(b.get("path")); return self.send_json({"ok": True})
            if path == "/api/ai/clone":
                files = [media.get(i)["path"] for i in b["media_ids"]]
                vid = ai.clone_voice(b["name"], files, "biar-edit ile klonlandı")
                cfg = S.load(); vs = cfg.get("voices") or []
                vs.append({"id": uuid.uuid4().hex[:8], "name": b["name"], "provider": "elevenlabs", "voice_id": vid, "model_id": "eleven_multilingual_v2",
                           "stability": 0.5, "similarity": 0.8, "style": 0.0, "speed": 1.0, "default": not vs})
                S.update({"voices": vs}); return self.send_json({"ok": True, "voice_id": vid})
            if path == "/api/projects/new": return self.send_json({"ok": True, "name": new_ranking(b) if b.get("kind") == "ranking" else new_reel(b)})
            m = re.match(r"^/api/p/([^/]+)/(source|output)$", path)
            if m:
                d = self.project_dir(m.group(1))
                if not d or project_kind(d) != "reel": return self.send_error(404)
                rj = os.path.join(d, "reel.json"); r = json.load(open(rj))
                if m.group(2) == "source":
                    it = media.get(b["media_id"]); key = b.get("key") or re.sub(r"\W+", "_", it["name"]).strip("_")[:24] or it["id"]
                    r["sources"][key] = {"path": it["path"], "speaker": b.get("speaker") or (it["speaker"] if it["speaker"] in ("yes", "no", "sometimes") else "sometimes")}
                else:
                    r["output"] = os.path.join(os.path.expanduser(b["dir"]), os.path.basename(r["output"]))
                json.dump(r, open(rj, "w"), ensure_ascii=False, indent=1)
                return self.send_json({"ok": True, "reel": r})
            if path == "/api/settings":
                allowed = set(S.SECRET_NAMES.values())
                for k, v in (b.get("secrets") or {}).items():
                    if k not in allowed: return self.send_json({"ok": False, "msg": f"bilinmeyen anahtar: {k}"}, 400)
                    S.set_secret(k, (v or "").strip())
                if b.get("patch"): S.update(b["patch"])
                return self.send_json({"ok": True, "settings": S.public_view()})
            if path == "/api/ai/test": return self.send_json(ai.test(b["provider"]))
            if path == "/api/ai/chat":
                prov, model = (b.get("provider"), b.get("model"))
                if not prov: prov, model = ai.pick_text_provider()
                return self.send_json({"ok": True, "provider": prov, "text": ai.chat(prov, model, b["messages"], b.get("system"), b.get("max_tokens", 1024))})
            if path == "/api/ai/caption":
                d = self.project_dir(b["project"])
                if not d: return self.send_error(404)
                text, prov, model = make_caption(d, b.get("platform"))
                return self.send_json({"ok": True, "text": text, "provider": prov, "model": model})
            if path == "/api/ai/tts":
                audio = ai.tts(b["text"], b.get("voice_id"), profile=b.get("profile"))
                os.makedirs(os.path.join(S.APP_DIR, "tts"), exist_ok=True)
                fn = uuid.uuid4().hex + ".mp3"; fp = os.path.join(S.APP_DIR, "tts", fn); open(fp, "wb").write(audio)
                return self.send_json({"ok": True, "url": f"/api/tts/{fn}", "path": fp})
            m = re.match(r"^/api/social/(x|linkedin|instagram|youtube)/(connect|paste|disconnect)$", path)
            if m:
                p, act = m.groups()
                if act == "connect": return self.send_json({"ok": True, "url": social.auth_url(p, PORT)})
                if act == "disconnect": social.disconnect(p); return self.send_json({"ok": True})
                code, state = social.code_from_pasted_url(b["url"])
                p2, handle = social.finish_oauth(code, state, PORT)
                return self.send_json({"ok": True, "handle": handle})
            if path == "/api/posts":
                video = b.get("video")
                if b.get("project"):
                    d = self.project_dir(b["project"]); video = video or (reel_output(d) if d and project_kind(d) in ("reel", "ranking") else None)
                if fetch.is_reference(video) or reel_uses_reference(b.get("project")):
                    return self.send_json({"ok": False, "msg": "Bu video 'referans' olarak indirilmiş başka birinin içeriğini kullanıyor, paylaşım kuyruğuna eklenemez. Kendi içeriğinse Kaynaklar'da etiketini 'kaynak' yap."}, 400)
                post = social.create_post(video, b.get("captions") or {"default": b.get("text", "")}, b.get("platforms", []),
                                          b.get("when"), b.get("source", "api"), bool(b.get("approved")), b.get("project"), b.get("options"))
                return self.send_json({"ok": True, "post": post})
            m = re.match(r"^/api/youtube/([\w-]{6,})$", path)
            if m:
                r = social.youtube_update(m.group(1), b.get("privacy"), b.get("title"), b.get("description"))
                return self.send_json({"ok": True, "privacy": (r.get("status") or {}).get("privacyStatus"), "title": (r.get("snippet") or {}).get("title")})
            m = re.match(r"^/api/posts/(\w+)$", path)
            if m:
                post = social.edit_post(m.group(1), b); moved = []
                if b.get("cancel"):
                    try: import autopilot; moved = autopilot.compact()
                    except Exception as e: moved = [{"error": str(e)}]
                return self.send_json({"ok": True, "post": post, "moved": moved})
            m = re.match(r"^/api/p/([^/]+)(/render)?$", path)
            if m:
                name = m.group(1); d = self.project_dir(name)
                if not d: return self.send_error(404)
                kind = project_kind(d); pj = os.path.join(d, PJ[kind])
                if m.group(2):
                    if name in RENDERS and RENDERS[name].poll() is None:
                        return self.send_json({"ok": False, "msg": "Render zaten çalışıyor."})
                    p = json.load(open(pj)); probs = validator(kind)(p)
                    if any(x["level"] == "error" for x in probs):
                        return self.send_json({"ok": False, "msg": "Önce kırmızı uyarıları düzelt.", "problems": probs})
                    os.makedirs(os.path.join(d, "work"), exist_ok=True)
                    log = open(os.path.join(d, "work", "render.log"), "w")
                    runner = {"reel": "reel_project.py", "film": "render_project.py", "ranking": "ranking.py"}[kind]
                    RENDERS[name] = subprocess.Popen([sys.executable, "-I", os.path.join(ROOT, "biaredit", runner), d], stdout=log, stderr=subprocess.STDOUT)
                    threading.Thread(target=after_render, args=(name, d, RENDERS[name]), daemon=True).start()
                    return self.send_json({"ok": True})
                bdir = os.path.join(d, "history"); os.makedirs(bdir, exist_ok=True)
                if os.path.exists(pj):
                    os.replace(pj, os.path.join(bdir, time.strftime(PJ[kind][:-5] + "-%Y%m%d-%H%M%S.json")))
                tmp = pj + ".tmp"; json.dump(b, open(tmp, "w"), ensure_ascii=False, indent=1); os.replace(tmp, pj)
                return self.send_json({"ok": True, "problems": validator(kind)(b)})
            self.send_error(404)
        except (ai.AIError, social.SocialError) as e:
            self.send_json({"ok": False, "msg": str(e)}, 400)
        except KeyError as e:
            self.send_json({"ok": False, "msg": f"eksik alan: {e}"}, 400)
        except RuntimeError as e:
            self.send_json({"ok": False, "msg": str(e)}, 400)

def style_state():
    vs = STY.versions(); vids = STY.channel_videos(); prev = None; hist = []
    for v in vs:
        hist.append({"version": v["version"], "date": v["date"], "note": v.get("note", ""), "from_video": v.get("after_video", 0) + 1,
                     "changes": [] if prev is None else [c["text"] for c in STY.diff(STY.merge(STY.DEFAULT, prev), STY.merge(STY.DEFAULT, v))],
                     "videos": [n for n, _, sp in vids if sp.get("style_version", 1) == v["version"]]})
        prev = v
    return {"head": STY.head(), "history": hist[::-1], "next_video": STY.last_video_no() + 1, "labels": STY.LABELS,
            "library": {"filters": {k: {"name": v["name"], "why": v["why"]} for k, v in STY.FILTERS.items()},
                        "shake": {k: {"name": v["name"], "why": v["why"]} for k, v in STY.SHAKE.items()}, "flash": STY.FLASH,
                        "accents": {k: {"name": v["name"], "why": v["why"], "rgb": v["rgb"]} for k, v in STY.ACCENTS.items()},
                        "sounds": STY.sound_info()},
            "videos": [{"no": n, "project": p, "version": sp.get("style_version", 1), "title": sp.get("name")} for n, p, sp in vids],
            "sample": next((f"/p/{p}/work/{f}" for _, p, sp in vids[::-1] for f in (f"chk{2 * len(sp['items'])}.jpg", "chk2.jpg")
                            if os.path.exists(os.path.join(PROJ, p, "work", f))), ""),
            "files": {"style": os.path.join(STY.CDIR, "STYLE.md"), "library": os.path.join(STY.CDIR, "LIBRARY.md")}}

def reel_uses_reference(name):
    d = os.path.join(PROJ, name) if name and re.match(r"^[\w.\-]+$", name) else None
    if not d or not os.path.exists(os.path.join(d, "reel.json")): return False
    srcs = json.load(open(os.path.join(d, "reel.json"))).get("sources", {})
    return any(fetch.is_reference(v.get("path")) for v in srcs.values())

if __name__ == "__main__":
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8790
    TOKEN = S.api_token()
    social.start_scheduler()
    fetch.start_scheduler()
    print(f"biar-edit → http://localhost:{PORT}")
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
