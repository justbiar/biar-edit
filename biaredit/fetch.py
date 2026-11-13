"""Video downloads with yt-dlp (TikTok, YouTube, Instagram, X and ~1800 other sites).

Every download lands in the download folder and goes straight into the media library, tagged with
where it came from. Two purposes:
  kaynak   your own content or content you have the rights to; usable in edits and posts
  referans someone else's video kept only for study (hook, pacing, text style); the post queue
           refuses to publish anything tagged "referans"

Watches ("takip") re-run a source on a schedule (a profile, a hashtag, a playlist). yt-dlp's
download archive makes sure the same video is never fetched twice.
"""
import json, os, re, shutil, subprocess, threading, time, uuid
import settings as S, media

YTDLP = shutil.which("yt-dlp") or "/opt/homebrew/bin/yt-dlp"
STATE = os.path.join(S.APP_DIR, "downloads.json")
ARCHIVE = os.path.join(S.APP_DIR, "yt-dlp-archive.txt")
PURPOSES = ("kaynak", "referans")
_lock = threading.Lock()
JOBS = {}          # id -> live job dict (also persisted, last 60)
_procs = {}

def folder():
    d = S.load().get("download_dir") or os.path.expanduser("~/Movies/biar-edit indirilenler")
    os.makedirs(d, exist_ok=True); return d

def _load():
    try: return json.load(open(STATE))
    except (FileNotFoundError, json.JSONDecodeError): return {"jobs": [], "watches": []}

def _save(st):
    os.makedirs(S.APP_DIR, exist_ok=True); tmp = STATE + ".tmp"
    json.dump(st, open(tmp, "w"), ensure_ascii=False, indent=1); os.replace(tmp, STATE)

def _persist(job):
    with _lock:
        st = _load(); st["jobs"] = [j for j in st["jobs"] if j["id"] != job["id"]]
        st["jobs"].insert(0, {k: v for k, v in job.items() if k != "log"}); st["jobs"] = st["jobs"][:60]; _save(st)

def version():
    try: return subprocess.run([YTDLP, "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.TimeoutExpired): return None

def update_ytdlp():
    r = subprocess.run(["brew", "upgrade", "yt-dlp"], capture_output=True, text=True, timeout=600)
    return {"ok": r.returncode == 0, "version": version(), "log": (r.stdout + r.stderr)[-800:]}

def _filter(o):
    """yt-dlp --match-filter from {max_dur, min_dur, min_views, after} (after = YYYYMMDD)."""
    parts = []
    if o.get("max_dur"): parts.append(f"duration<={int(o['max_dur'])}")
    if o.get("min_dur"): parts.append(f"duration>={int(o['min_dur'])}")
    if o.get("min_views"): parts.append(f"view_count>={int(o['min_views'])}")
    return " & ".join(parts)

def _sanitize(url):
    url = (url or "").strip()
    if not re.match(r"^https?://", url): raise RuntimeError("Geçerli bir bağlantı yapıştır (https:// ile başlamalı).")
    return url

def start(url, purpose="kaynak", limit=10, max_dur=None, min_dur=None, min_views=None, after=None,
          speaker="unknown", cookies_browser=None, watch_id=None):
    url = _sanitize(url)
    if purpose not in PURPOSES: purpose = "kaynak"
    job = {"id": uuid.uuid4().hex[:10], "url": url, "purpose": purpose, "status": "indiriliyor", "pct": 0, "current": "",
           "done": 0, "items": [], "skipped": 0, "error": "", "started": time.time(), "ended": None, "watch": watch_id,
           "opts": {"limit": limit, "max_dur": max_dur, "min_dur": min_dur, "min_views": min_views, "after": after}, "log": []}
    out = os.path.join(folder(), "%(extractor_key)s", "%(uploader|uploader_id|unknown)s", "%(upload_date>%Y-%m-%d|)s %(title).60B [%(id)s].%(ext)s")
    cmd = [YTDLP, url, "-o", out, "--newline", "--no-colors", "--restrict-filenames", "--no-overwrites",
           "--download-archive", ARCHIVE, "--write-info-json", "--no-write-playlist-metafiles",
           "-f", "bv*[vcodec^=avc1]+ba[ext=m4a]/bv*+ba/b", "--merge-output-format", "mp4",
           "--progress-template", "download:PRG %(progress._percent_str)s %(info.title).50s",
           "--print", "after_move:FILE %(filepath)s", "--no-quiet", "--ignore-errors"]
    if limit: cmd += ["--playlist-end", str(int(limit))]
    f = _filter({"max_dur": max_dur, "min_dur": min_dur, "min_views": min_views})
    if f: cmd += ["--match-filter", f]
    if after: cmd += ["--dateafter", re.sub(r"\D", "", str(after))[:8]]
    if cookies_browser: cmd += ["--cookies-from-browser", cookies_browser]
    JOBS[job["id"]] = job; _persist(job)
    threading.Thread(target=_run, args=(job, cmd, speaker), daemon=True).start()
    return job

def _run(job, cmd, speaker):
    env = {**os.environ, "PATH": "/opt/homebrew/opt/ffmpeg-full/bin:/opt/homebrew/bin:" + os.environ.get("PATH", "")}
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, bufsize=1)
    except OSError as e:
        job.update(status="hata", error=f"yt-dlp çalışmadı: {e}", ended=time.time()); _persist(job); return
    _procs[job["id"]] = p
    for line in p.stdout:
        line = line.rstrip(); job["log"] = (job["log"] + [line])[-40:]
        if line.startswith("PRG "):
            m = re.match(r"PRG\s+([\d.]+)%\s*(.*)", line)
            if m: job["pct"] = float(m.group(1)); job["current"] = m.group(2)
        elif line.startswith("FILE "):
            path = line[5:].strip(); _register(job, path, speaker)
        elif "has already been recorded in the archive" in line or "does not pass filter" in line:
            job["skipped"] += 1
        elif "No video formats found" in line:
            job["skipped"] += 1; job["photo"] = job.get("photo", 0) + 1
    rc = p.wait(); _procs.pop(job["id"], None)
    errs = [l for l in job["log"] if l.startswith("ERROR") and "No video formats found" not in l]
    note = f"{job['photo']} fotoğraf/slayt gönderisi atlandı (video değil)." if job.get("photo") else ""
    if job["status"] == "iptal": pass
    elif job["items"] or rc == 0 or not errs: job["status"] = "bitti"; job["error"] = " ".join(x for x in [note, errs[-1][7:] if errs else ""] if x)
    else: job["status"] = "hata"; job["error"] = _friendly(errs[-1] if errs else "\n".join(job["log"][-3:]))
    job["pct"] = 100 if job["status"] == "bitti" else job["pct"]; job["ended"] = time.time(); _persist(job)

def _friendly(msg):
    m = msg.lower()
    if "login" in m or "cookies" in m or "private" in m: return msg + "  · Giriş gerektiriyor olabilir: 'Tarayıcı çerezleri' seçeneğini dene."
    if "unsupported url" in m: return "Bu bağlantı desteklenmiyor."
    if "http error 403" in m or "blocked" in m: return msg + "  · Site isteği engelledi. yt-dlp'yi güncelleyip tekrar dene."
    return msg

def _register(job, path, speaker):
    info = {}
    base = os.path.splitext(path)[0]
    try: info = json.load(open(base + ".info.json"))
    except (OSError, json.JSONDecodeError): pass
    tags = ["indirilen", job["purpose"], info.get("extractor_key", "").lower()]
    who = info.get("uploader") or info.get("uploader_id")
    if who: tags.append("@" + str(who).lstrip("@"))
    items = media.add([path], "video", speaker, [t for t in tags if t])
    if items:
        it = media.update(items[0]["id"], {"source": {"url": info.get("webpage_url") or job["url"], "site": info.get("extractor_key"),
            "uploader": info.get("uploader") or info.get("uploader_id"), "title": info.get("title") or info.get("description", "")[:80],
            "views": info.get("view_count"), "likes": info.get("like_count"), "upload_date": info.get("upload_date"),
            "purpose": job["purpose"], "job": job["id"]}}) or items[0]
        job["items"].append({"id": it["id"], "name": it["name"], "path": path, "title": (info.get("title") or "")[:80],
                             "uploader": info.get("uploader") or info.get("uploader_id"), "views": info.get("view_count"), "duration": info.get("duration")})
    job["done"] = len(job["items"])

def cancel(job_id):
    p = _procs.get(job_id); j = JOBS.get(job_id)
    if j: j["status"] = "iptal"; j["ended"] = time.time()
    if p and p.poll() is None: p.terminate()
    if j: _persist(j)
    return bool(j)

def jobs():
    st = _load(); live = {k: {kk: vv for kk, vv in v.items() if kk != "log"} for k, v in JOBS.items()}
    seen = set(); out = []
    for j in list(live.values()) + st["jobs"]:
        if j["id"] in seen: continue
        seen.add(j["id"]); out.append(live.get(j["id"], j))
    return sorted(out, key=lambda j: -j["started"])[:60]

def job(job_id):
    j = JOBS.get(job_id)
    return j or next((x for x in _load()["jobs"] if x["id"] == job_id), None)

def is_reference(path):
    """True when the file was downloaded as a study reference (must not be published)."""
    if not path: return False
    ap = os.path.abspath(path)
    return any(i["path"] == ap and "referans" in (i.get("tags") or []) for i in media.library())

# ---------- watches (scheduled sources) ----------
def watches(): return _load()["watches"]

def save_watch(w):
    w = dict(w); w["url"] = _sanitize(w.get("url"))
    w.setdefault("id", uuid.uuid4().hex[:10]); w.setdefault("every_hours", 24); w.setdefault("limit", 10)
    w.setdefault("purpose", "kaynak"); w.setdefault("enabled", True); w.setdefault("last_run", None); w.setdefault("name", w["url"])
    with _lock:
        st = _load(); st["watches"] = [x for x in st["watches"] if x["id"] != w["id"]] + [w]; _save(st)
    return w

def delete_watch(wid):
    with _lock:
        st = _load(); st["watches"] = [x for x in st["watches"] if x["id"] != wid]; _save(st)

def run_watch(wid):
    w = next((x for x in watches() if x["id"] == wid), None)
    if not w: raise RuntimeError("Takip bulunamadı.")
    w["last_run"] = time.time(); save_watch(w)
    return start(w["url"], w["purpose"], w.get("limit", 10), w.get("max_dur"), w.get("min_dur"), w.get("min_views"),
                 None, w.get("speaker", "unknown"), w.get("cookies_browser"), w["id"])

def start_scheduler():
    def loop():
        while True:
            try:
                busy = any(j["status"] == "indiriliyor" for j in JOBS.values())
                for w in watches():
                    if busy or not w.get("enabled"): continue
                    if not w.get("last_run") or time.time() - w["last_run"] >= float(w.get("every_hours", 24)) * 3600:
                        run_watch(w["id"]); busy = True
            except Exception: pass
            time.sleep(60)
    threading.Thread(target=loop, daemon=True).start()

# ---------- research helpers (used by the ranking editor and agents) ----------
def search(q, n=6):
    """YouTube search without downloading: [{id, url, title, channel, duration, views}]."""
    out = subprocess.run([YTDLP, "--flat-playlist", "--no-warnings", "-J", f"ytsearch{int(n)}:{q}"], capture_output=True, text=True, timeout=60).stdout
    try: ents = json.loads(out).get("entries", [])
    except json.JSONDecodeError: return []
    return [{"id": e.get("id"), "url": f"https://www.youtube.com/watch?v={e.get('id')}", "title": e.get("title"), "channel": e.get("channel") or e.get("uploader"),
             "duration": e.get("duration"), "views": e.get("view_count")} for e in ents if e.get("id")]

def cues(url, lang="en"):
    """Timestamped subtitle lines of a video (manual subs first, auto captions otherwise)."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([YTDLP, "--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", f"{lang}.*,{lang}", "--sub-format", "vtt",
                        "-o", os.path.join(td, "s"), url], capture_output=True, text=True, timeout=120)
        fs = sorted(f for f in os.listdir(td) if f.endswith(".vtt"))
        if not fs: return []
        pick = next((f for f in fs if "-orig" in f), fs[0])
        out, seen, cur = [], set(), None
        for line in open(os.path.join(td, pick), encoding="utf-8", errors="ignore"):
            m = re.match(r"(\d+):(\d+):([\d.]+) -->", line)
            if m: cur = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]); continue
            t = re.sub(r"<[^>]+>", "", line).strip()
            if t and cur is not None and t not in seen and not t.startswith(("WEBVTT", "Kind:", "Language:")):
                seen.add(t); out.append({"t": round(cur, 2), "text": t})
        return out
