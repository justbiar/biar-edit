"""Media library, file pickers, sound effects, transitions, looks and product recording.

Library items live in ~/Library/Application Support/biar-edit/library.json; files stay where they
are (nothing is copied), so adding a 10 GB video is instant.
"""
import json, os, subprocess, threading, time, uuid
import settings as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(ROOT, "media")
LIB = os.path.join(S.APP_DIR, "library.json")
BIN = os.path.join(ROOT, "bin")
RECORDLY_APP = os.path.expanduser("~/Applications/Recordly.app")
RECORDLY_REC = os.path.expanduser("~/Library/Application Support/Recordly/recordings")
_lock = threading.Lock()

VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".lrf", ".avi"}
AUDIO = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".aif", ".aiff", ".ogg"}
IMAGE = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif"}
KINDS = ("video", "audio", "image", "music", "sfx", "transition", "lut")

def kind_of(path):
    e = os.path.splitext(path)[1].lower()
    return "lut" if e == ".cube" else "video" if e in VIDEO else "audio" if e in AUDIO else "image" if e in IMAGE else None

def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,color_transfer",
                        "-of", "json", path], capture_output=True, text=True)
    try: d = json.loads(r.stdout)
    except json.JSONDecodeError: return {}
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"duration": float(d.get("format", {}).get("duration") or 0) or None, "w": v.get("width"), "h": v.get("height"),
            "hdr": v.get("color_transfer") in ("arib-std-b67", "smpte2084"), "has_audio": any(s.get("codec_type") == "audio" for s in d.get("streams", []))}

def _load():
    try: return json.load(open(LIB))
    except (FileNotFoundError, json.JSONDecodeError): return []

def _save(items):
    os.makedirs(S.APP_DIR, exist_ok=True); tmp = LIB + ".tmp"
    json.dump(items, open(tmp, "w"), ensure_ascii=False, indent=1); os.replace(tmp, LIB)

def library():
    ensure_builtin()
    with _lock:
        items = _load()
    for it in items:
        it["missing"] = not os.path.exists(it["path"])
    return items

def add(paths, kind=None, speaker=None, tags=None, builtin=False):
    out = []
    with _lock:
        items = _load(); have = {i["path"]: i for i in items}
        for p in paths:
            p = os.path.abspath(os.path.expanduser(p))
            if not os.path.isfile(p): continue
            k = kind or kind_of(p)
            if not k: continue
            if p in have:
                it = have[p]
                if kind: it["kind"] = kind
                if speaker: it["speaker"] = speaker
                out.append(it); continue
            info = probe(p) if k != "lut" else {}
            it = {"id": uuid.uuid4().hex[:10], "path": p, "name": os.path.splitext(os.path.basename(p))[0], "kind": k,
                  "speaker": speaker or ("no" if k in ("sfx", "music", "transition", "audio") else "unknown"),
                  "tags": tags or [], "added": time.time(), "builtin": builtin, **info}
            items.append(it); have[p] = it; out.append(it)
        _save(items)
    return out

def update(item_id, patch):
    with _lock:
        items = _load()
        for it in items:
            if it["id"] == item_id:
                for k in ("name", "kind", "speaker", "tags", "source"):
                    if k in patch: it[k] = patch[k]
                _save(items); return it
    raise KeyError(item_id)

def remove(item_id):
    with _lock:
        _save([i for i in _load() if i["id"] != item_id])

def get(item_id):
    return next((i for i in _load() if i["id"] == item_id), None)

# ---- native pickers (osascript shows the real macOS Open panel) ------------------------------
def _osa(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode == 0:
        return r.stdout.strip()
    if "-128" in r.stderr:          # user pressed Cancel
        return None
    raise RuntimeError(r.stderr.strip()[:200])

def pick_files(prompt="Dosya seç", multiple=True):
    s = (f'set fs to choose file with prompt "{prompt}" {"with multiple selections allowed" if multiple else ""}\n'
         'set out to ""\nrepeat with f in (fs as list)\nset out to out & POSIX path of f & linefeed\nend repeat\nreturn out')
    r = _osa(s)
    return [x for x in (r or "").splitlines() if x]

def pick_folder(prompt="Klasör seç"):
    r = _osa(f'return POSIX path of (choose folder with prompt "{prompt}")')
    return r.rstrip("/") if r else None

def reveal(path):
    subprocess.run(["open", "-R", path])

# ---- built-in sound effects (synthesised once with ffmpeg) -------------------------------------
SFX = {
    "whoosh": "anoisesrc=d=0.7:c=pink:a=0.6,highpass=f=300,lowpass=f=4000,afade=t=in:d=0.35,afade=t=out:st=0.35:d=0.35,vibrato=f=3:d=0.4",
    "pop": "sine=f=520:d=0.12,afade=t=out:st=0.02:d=0.1,volume=1.6",
    "tik": "sine=f=2200:d=0.03,afade=t=out:st=0.005:d=0.025",
    "yukselen": "aevalsrc='0.4*sin(2*PI*(200+900*t*t)*t)':d=1.6:s=48000,afade=t=in:d=1.2,afade=t=out:st=1.5:d=0.1",
    "darbe": "aevalsrc='0.9*sin(2*PI*55*t)*exp(-5*t)':d=1.0:s=48000,lowpass=f=200,volume=2",
    "ding": "aevalsrc='0.5*sin(2*PI*1320*t)*exp(-4*t)+0.25*sin(2*PI*2640*t)*exp(-6*t)':d=1.2:s=48000",
    "zil": "aevalsrc='0.4*sin(2*PI*880*t)*exp(-3*t)+0.4*sin(2*PI*1108*t)*exp(-3*t)':d=1.0:s=48000",
    "impact": "aevalsrc='0.9*sin(2*PI*(38+120*exp(-14*t))*t)*exp(-3.2*t)':d=1.4:s=48000[a];anoisesrc=d=0.25:c=white:a=0.5:r=48000,highpass=f=1500,afade=t=out:d=0.25[b];[a][b]amix=inputs=2:normalize=0,volume=1.5[out0]",
    "davul": "anoisesrc=d=1.6:c=pink:a=0.7:r=48000,bandpass=f=1800:w=1200,tremolo=f=22:d=1,afade=t=in:d=1.4,afade=t=out:st=1.5:d=0.1",
    "kayma": "anoisesrc=d=0.35:c=white:a=0.5:r=48000,bandpass=f=2500:w=3000,afade=t=in:d=0.15,afade=t=out:st=0.15:d=0.2",
    "bass": "aevalsrc='0.9*sin(2*PI*(80-50*t)*t)*exp(-1.5*t)':d=1.5:s=48000",
    # meme-style hits (synthesized, so no Content ID)
    "vine_boom": "aevalsrc='1.0*sin(2*PI*(95*t-30*t*t))*exp(-2.4*t)+0.35*sin(2*PI*(190*t-60*t*t))*exp(-4*t)':d=1.8:s=48000,aecho=0.8:0.55:70|140:0.35|0.2,lowpass=f=600,volume=2.2",
    "sinematik_boom": "aevalsrc='1.0*sin(2*PI*(60*t-12*t*t))*exp(-1.1*t)':d=3.2:s=48000[a];anoisesrc=d=0.6:c=brown:a=0.8:r=48000,lowpass=f=900,afade=t=out:d=0.6[b];[a][b]amix=inputs=2:normalize=0,aecho=0.8:0.6:120|260:0.4|0.25,volume=1.8[out0]",
    "cam_kirilma": "aevalsrc='0.28*(sin(2*PI*3100*t)*exp(-9*t)+sin(2*PI*4700*t)*exp(-12*t)+sin(2*PI*6200*t)*exp(-7*t)+sin(2*PI*5300*t)*exp(-15*t)+sin(2*PI*7400*t)*exp(-10*t))':d=1.3:s=48000[a];anoisesrc=d=0.6:c=white:a=0.7:r=48000,highpass=f=2200,afade=t=out:st=0.04:d=0.55[b];[a][b]amix=inputs=2:normalize=0,volume=1.4[out0]",
    "siren": "aevalsrc='0.42*sin(2*PI*(850*t-(380/(2*PI*1.6))*cos(2*PI*1.6*t)))':d=2.4:s=48000,afade=t=in:d=0.08,afade=t=out:st=2.1:d=0.3",
    "flas": "anoisesrc=d=0.18:c=white:a=0.8:r=48000,highpass=f=1800,volume='if(lt(t,0.025),1,if(between(t,0.085,0.11),0.75,0))':eval=frame",
    "kasa": "aevalsrc='0.45*sin(2*PI*2637*t)*exp(-7*t)+0.35*(gte(t,0.11))*sin(2*PI*3520*(t-0.11))*exp(-5*(t-0.11))':d=1.2:s=48000[a];anoisesrc=d=0.1:c=white:a=0.4:r=48000,highpass=f=3000,afade=t=out:d=0.1[b];[a][b]amix=inputs=2:normalize=0[out0]",
    "buzzer": "aevalsrc='0.35*sgn(sin(2*PI*140*t))+0.2*sgn(sin(2*PI*147*t))':d=0.75:s=48000,lowpass=f=1800,afade=t=out:st=0.65:d=0.1",
    "gong": "aevalsrc='0.4*sin(2*PI*110*t)*exp(-0.9*t)+0.3*sin(2*PI*247*t)*exp(-1.3*t)+0.25*sin(2*PI*389*t)*exp(-1.7*t)+0.15*sin(2*PI*611*t)*exp(-2.4*t)':d=3.5:s=48000,afade=t=in:d=0.01",
    "metal_boru": "aevalsrc='0.35*sin(2*PI*523*t)*exp(-2.5*t)+0.3*sin(2*PI*1371*t)*exp(-3.2*t)+0.25*sin(2*PI*2213*t)*exp(-4*t)+0.2*sin(2*PI*3170*t)*exp(-5*t)':d=2.0:s=48000[a];anoisesrc=d=0.05:c=white:a=0.8:r=48000[b];[a][b]amix=inputs=2:normalize=0,aecho=0.7:0.4:90:0.3,volume=1.6[out0]",
    "flashbang": "anoisesrc=d=0.4:c=white:a=0.9:r=48000,afade=t=out:d=0.4[a];aevalsrc='0.25*sin(2*PI*3900*t)*exp(-0.9*t)':d=3.0:s=48000[b];[a][b]amix=inputs=2:normalize=0[out0]",
    "plak_cizik": "aevalsrc='0.5*sin(2*PI*(600*t+90*sin(2*PI*7*t)))*exp(-2*t)':d=0.55:s=48000[a];anoisesrc=d=0.55:c=pink:a=0.5:r=48000,bandpass=f=1400:w=900,afade=t=out:d=0.55[b];[a][b]amix=inputs=2:normalize=0[out0]",
    "tiktak": "aevalsrc='0.5*(lt(mod(t,0.5),0.02))*sin(2*PI*(if(lt(mod(t,1),0.5),2100,1600))*t)':d=3.0:s=48000",
    "coin": "aevalsrc='0.25*sgn(sin(2*PI*if(lt(t,0.08),988,1319)*t))*exp(-4*t)':d=0.5:s=48000,lowpass=f=6000",
    "gerilim": "anoisesrc=d=3.5:c=pink:a=0.5:r=48000,highpass=f=400,volume='t/3.5':eval=frame[a];aevalsrc='0.3*sin(2*PI*(200*t+60*t*t))*(t/3.5)':d=3.5:s=48000[b];[a][b]amix=inputs=2:normalize=0,afade=t=out:st=3.4:d=0.1[out0]",
}
TRANSITIONS = [
    {"id": "none", "name": "Yok"}, {"id": "flas", "name": "Beyaz flaş"}, {"id": "karart", "name": "Karartma"},
    {"id": "zoom", "name": "Zoom vuruşu"}, {"id": "bulanik", "name": "Bulanık geçiş"}, {"id": "kaydir", "name": "Hızlı kaydırma"},
]
LOOKS = [
    {"id": "none", "name": "Orijinal"}, {"id": "dogal", "name": "Doğal"}, {"id": "canli", "name": "Canlı"}, {"id": "sicak", "name": "Sıcak"},
    {"id": "soguk", "name": "Soğuk"}, {"id": "sinematik", "name": "Sinematik"}, {"id": "soluk", "name": "Soluk film"},
    {"id": "siyahbeyaz", "name": "Siyah beyaz"}, {"id": "gece", "name": "Gece"},
]
_built = False
def ensure_builtin():
    global _built
    if _built: return
    d = os.path.join(MEDIA, "sfx"); os.makedirs(d, exist_ok=True); made = []
    for n, f in SFX.items():
        p = os.path.join(d, f"{n}.wav")
        if not os.path.exists(p):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f, "-ac", "2", "-ar", "48000", p])
        made.append(p)
    with _lock:
        have = {i["path"] for i in _load()}
    new = [p for p in made if p not in have and os.path.exists(p)]
    if new: add(new, kind="sfx", tags=["hazır"], builtin=True)
    _built = True

# ---- product recording (Recordly's ScreenCaptureKit recorder) ----------------------------------
REC = {"proc": None, "path": None, "started": None, "log": [], "cursor": None}

def displays():
    import Quartz
    err, ids, n = Quartz.CGGetActiveDisplayList(16, None, None)
    out = []
    for i, did in enumerate(ids[:n]):
        b = Quartz.CGDisplayBounds(did)
        out.append({"id": int(did), "name": f"Ekran {i + 1}" + (" (ana)" if Quartz.CGDisplayIsMain(did) else ""),
                    "w": int(b.size.width), "h": int(b.size.height), "x": int(b.origin.x), "y": int(b.origin.y)})
    return out

def windows():
    try:
        r = subprocess.run([os.path.join(BIN, "window-list")], capture_output=True, text=True, timeout=8)
        ws = json.loads(r.stdout or "[]")
    except Exception:
        return []
    out = []
    for w in ws:
        try: wid = int(str(w["id"]).split(":")[1])
        except (IndexError, ValueError): continue
        if w.get("bundleId") in ("dev.biar.edit",): continue
        out.append({"id": wid, "app": w.get("appName"), "title": w.get("windowTitle") or w.get("name"), "w": w.get("width"), "h": w.get("height")})
    return out

def _cursor_logger(path, bounds, stop):
    """Writes Recordly's v2 cursor file next to the video so Recordly can add cursor effects later."""
    import Quartz
    samples, t0, down = [], time.time(), False
    x0, y0, W, H = bounds
    while not stop.is_set():
        ev = Quartz.CGEventCreate(None); p = Quartz.CGEventGetLocation(ev)
        btn = Quartz.CGEventSourceButtonState(Quartz.kCGEventSourceStateCombinedSessionState, Quartz.kCGMouseButtonLeft)
        typ = "click" if btn and not down else "move"; down = bool(btn)
        samples.append({"timeMs": int((time.time() - t0) * 1000), "cx": (p.x - x0) / W, "cy": (p.y - y0) / H, "interactionType": typ, "cursorType": "arrow"})
        time.sleep(1 / 60)
    json.dump({"version": 2, "samples": samples}, open(path + ".cursor.json", "w"))

def rec_start(display_id=None, window_id=None, system_audio=True, mic=False, cursor=True, fps=60):
    if REC["proc"] and REC["proc"].poll() is None:
        raise RuntimeError("Kayıt zaten sürüyor.")
    d = os.path.join(MEDIA, "recordings"); os.makedirs(d, exist_ok=True)
    out = os.path.join(d, time.strftime("urun-%Y%m%d-%H%M%S.mp4"))
    cfg = {"fps": fps, "outputPath": out, "capturesSystemAudio": bool(system_audio), "capturesMicrophone": bool(mic), "showsCursor": bool(cursor)}
    if window_id: cfg["windowId"] = int(window_id)
    else: cfg["displayId"] = int(display_id or displays()[0]["id"])
    if system_audio: cfg["systemAudioOutputPath"] = out[:-4] + ".system.m4a"
    if mic: cfg["microphoneOutputPath"] = out[:-4] + ".mic.m4a"
    p = subprocess.Popen([os.path.join(BIN, "sck-recorder"), json.dumps(cfg)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, bufsize=1)
    REC.update(proc=p, path=out, started=time.time(), log=[], cfg=cfg)
    def reader():
        for line in p.stdout: REC["log"].append(line.strip())
    threading.Thread(target=reader, daemon=True).start()
    if not cursor:   # cursor hidden in video: log it for Recordly
        disp = next((x for x in displays() if x["id"] == cfg.get("displayId")), None) or displays()[0]
        stop = threading.Event(); REC["cursor"] = stop
        threading.Thread(target=_cursor_logger, args=(out, (disp["x"], disp["y"], disp["w"], disp["h"]), stop), daemon=True).start()
    time.sleep(1.0)
    if p.poll() is not None:
        msg = " ".join(REC["log"])[-300:]
        if "PERMISSION" in msg:
            raise RuntimeError("Ekran kaydı izni yok. Sistem Ayarları > Gizlilik ve Güvenlik > Ekran Kaydı'ndan biar-edit'e izin ver, sonra tekrar dene.")
        raise RuntimeError("Kayıt başlamadı: " + msg)
    return rec_status()

def _mux(out):
    """Put system audio and microphone into the video file so it is one clip in the library."""
    sysa, mica = out[:-4] + ".system.m4a", out[:-4] + ".mic.m4a"
    extra = [a for a in (sysa, mica) if os.path.exists(a) and os.path.getsize(a) > 1000]
    if not extra: return
    tmp = out[:-4] + ".mux.mp4"; ins = ["-i", out]
    for a in extra: ins += ["-i", a]
    if len(extra) == 2:
        fl = ["-filter_complex", "[1:a][2:a]amix=inputs=2:normalize=0[a]", "-map", "0:v", "-map", "[a]"]
    else:
        fl = ["-map", "0:v", "-map", "1:a"]
    r = subprocess.run(["ffmpeg", "-v", "error", "-y"] + ins + fl + ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", tmp])
    if r.returncode == 0:
        os.replace(tmp, out)
        for a in extra: os.remove(a)

def rec_stop():
    p = REC["proc"]
    if not p or p.poll() is not None:
        raise RuntimeError("Süren bir kayıt yok.")
    p.stdin.write("stop\n"); p.stdin.flush()
    try: p.wait(timeout=30)
    except subprocess.TimeoutExpired: p.kill()
    if REC.get("cursor"): REC["cursor"].set(); time.sleep(0.2)
    out = REC["path"]
    if not os.path.exists(out):
        raise RuntimeError("Kayıt dosyası oluşmadı: " + " ".join(REC["log"])[-300:])
    _mux(out)
    item = add([out], kind="video", speaker="no", tags=["ürün kaydı"])[0]
    REC.update(proc=None)
    return item

def rec_status():
    p = REC["proc"]; running = bool(p and p.poll() is None)
    return {"running": running, "path": REC["path"], "elapsed": round(time.time() - REC["started"], 1) if running else 0,
            "log": REC["log"][-5:], "recordly_installed": os.path.isdir(RECORDLY_APP)}

def recordings():
    out = []
    for d, src in ((os.path.join(MEDIA, "recordings"), "biar-edit"), (RECORDLY_REC, "Recordly")):
        if not os.path.isdir(d): continue
        for f in sorted(os.listdir(d), reverse=True):
            if f.endswith((".mp4", ".mov", ".webm")) and ".mux." not in f:
                p = os.path.join(d, f)
                out.append({"path": p, "name": f, "source": src, "size": os.path.getsize(p), "mtime": os.path.getmtime(p),
                            "cursor": os.path.exists(p + ".cursor.json")})
    return out

def open_in_recordly(path=None):
    if not os.path.isdir(RECORDLY_APP):
        raise RuntimeError("Recordly.app bulunamadı (~/Applications).")
    subprocess.run(["open", "-a", RECORDLY_APP] + ([path] if path else []))
