"""Daily Ranked Legends autopilot: the deterministic half of the daily run.

The creative half (topic, clips, moments, comments) is done by the scheduled Claude run that
follows automation/daily-ranking.md; it calls these commands for everything that must be exact.

  python -I biaredit/autopilot.py status                 history, queue, next publish slot, today's state
  python -I biaredit/autopilot.py new SPEC.json          create projects/rankNN from a spec (fills defaults)
  python -I biaredit/autopilot.py render PROJECT         render and wait
  python -I biaredit/autopilot.py check PROJECT          quality gate: black frames, clip lengths, loudness, sheet
  python -I biaredit/autopilot.py queue PROJECT CAPTION.txt   queue the YouTube upload for the next publish slot
  python -I biaredit/autopilot.py log PROJECT "topic"    remember the topic so it is not repeated
  python -I biaredit/autopilot.py remind [--test]        macOS notification if a video waits for approval
  python -I biaredit/autopilot.py style                  current edit style version (what the next video is made with)
  python -I biaredit/autopilot.py docs                   regenerate STYLE.md, LIBRARY.md and every VIDEO.md

The look (transition sound, filter, shake, CTA, accent colour...) is NOT chosen per video: it comes
from the versioned style in channels/ranked-legends (see biaredit/style.py). `new` locks the video to
the current version.

Everything prints JSON. A non-zero exit means: stop and report, do not publish.
"""
import datetime, glob, json, os, subprocess, sys, time
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ["PATH"] = "/opt/homebrew/opt/ffmpeg-full/bin:/opt/homebrew/bin:" + os.environ.get("PATH", "")
import settings as S, media, social, ranking, style as STY

PROJ = os.path.join(ROOT, "projects")
HIST = os.path.join(S.APP_DIR, "autopilot.json")
DEFAULTS = {"publish_time": "03:00", "tz": "Europe/Istanbul", "lang": "en", "channel": "Ranked Legends"}

def cfg(): return {**DEFAULTS, **(S.load().get("autopilot") or {})}

def hist():
    try: return json.load(open(HIST))
    except (FileNotFoundError, json.JSONDecodeError): return {"videos": []}

def save_hist(h):
    os.makedirs(S.APP_DIR, exist_ok=True); json.dump(h, open(HIST, "w"), ensure_ascii=False, indent=1)

def out(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False, indent=1)); sys.exit(code)

def next_slot():
    c = cfg(); tz = ZoneInfo(c["tz"]); now = datetime.datetime.now(tz)
    h, m = map(int, c["publish_time"].split(":"))
    slot = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if slot <= now + datetime.timedelta(minutes=30): slot += datetime.timedelta(days=1)
    taken = {round(pa) for p, pa in scheduled()}
    while round(slot.timestamp()) in taken: slot += datetime.timedelta(days=1)   # one video per day
    return slot

def scheduled():
    """[(post, publish_at)] for YouTube posts that still hold a future slot (waiting, uploading or uploaded and scheduled)."""
    now = time.time(); out = []
    for p in social.list_posts():
        pa = (p.get("options", {}).get("youtube") or {}).get("publish_at"); t = p["targets"].get("youtube") or {}
        if pa and pa > now and t.get("status") in ("onay bekliyor", "bekliyor", "paylaşılıyor", "paylaşıldı"): out.append((p, pa))
    return sorted(out, key=lambda x: x[1])

def compact():
    """Close gaps: when a slot is freed (a post deleted or cancelled), later autopilot videos move up one day each.
    Videos only ever move earlier, never later; uploaded ones are rescheduled on YouTube too."""
    c = cfg(); tz = ZoneInfo(c["tz"]); now = datetime.datetime.now(tz)
    h, m = map(int, c["publish_time"].split(":"))
    slot = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if slot <= now + datetime.timedelta(minutes=30): slot += datetime.timedelta(days=1)
    moved = []
    for p, pa in scheduled():
        if p.get("source") != "autopilot": slot = max(slot, datetime.datetime.fromtimestamp(pa, tz) + datetime.timedelta(days=1)); continue
        if slot.timestamp() < pa - 60:
            try:
                social.set_publish_at(p["id"], slot.timestamp())
                moved.append({"post": p["id"], "project": p.get("project"), "from": datetime.datetime.fromtimestamp(pa, tz).isoformat(), "to": slot.isoformat()})
            except social.SocialError as e:
                moved.append({"post": p["id"], "project": p.get("project"), "error": str(e)}); slot = datetime.datetime.fromtimestamp(pa, tz)
        else: slot = datetime.datetime.fromtimestamp(pa, tz)
        slot += datetime.timedelta(days=1)
    if moved:
        try: STY.write_docs()
        except Exception: pass
    return moved

def music_pick():
    """Least recently used NCS track, so every video sounds different."""
    lib = [i for i in media.library() if i["kind"] == "music" and "ncs" in (i.get("tags") or []) and not i.get("missing")]
    used = [v.get("music") for v in hist()["videos"]]
    lib.sort(key=lambda i: (max([k for k, u in enumerate(used) if u == i["path"]], default=-1), i["name"]))
    return lib[0] if lib else None

def cmd_status():
    h = hist(); posts = social.list_posts(); STY.write_docs(posts); st = STY.head()
    acc = S.load()["accounts"]["youtube"]
    out({"channel": cfg()["channel"], "youtube_connected": S.get_json_secret("youtube_token") is not None, "youtube_handle": acc.get("handle"),
         "auto_post": acc.get("auto_post"), "next_publish_slot": next_slot().isoformat(),
         "published_topics": [v["topic"] for v in h["videos"]],
         "style": {"version": st["version"], "note": st.get("note"), "since_video": st.get("after_video", 0) + 1, "file": os.path.join(STY.CDIR, "STYLE.md")},
         "queue": [{"id": p["id"], "project": p.get("project"), "status": {k: t["status"] for k, t in p["targets"].items()},
                    "publish_at": (p.get("options", {}).get("youtube") or {}).get("publish_at")} for p in posts[:10]]})

def cmd_new(path):
    spec = json.load(open(path))
    n = 1
    while os.path.exists(os.path.join(PROJ, f"rank{n:02d}")): n += 1
    name = f"rank{n:02d}"; d = os.path.join(PROJ, name); os.makedirs(d)
    vid_no = len(hist()["videos"]) + 1
    spec.setdefault("type", "ranking"); spec.setdefault("lang", cfg()["lang"])
    spec.setdefault("name", f"Ranked Legends {vid_no:02d} · {spec.get('topic', spec.get('title', ''))}")
    st = STY.head(); spec["style_version"] = st["version"]          # the look comes from the style, locked here
    for k in ("intro", "outro", "sfx_gain", "style"): spec.pop(k, None)
    spec.setdefault("sfx_on", True)
    safe = "".join(ch for ch in spec.get("topic", name).lower() if ch.isalnum() or ch in " -").strip()[:60]
    spec.setdefault("output", os.path.join(S.load().get("export_dir") or os.path.expanduser("~/Desktop"), f"ranked legends {vid_no:02d} - {safe}.mp4"))
    if not spec.get("music"):
        m = music_pick()
        if m: spec["music"] = {"path": m["path"], "credit": (m.get("source") or {}).get("credit", "")}
    for it in spec["items"]: it.setdefault("sfx", [])
    probs = ranking.validate(spec)
    json.dump(spec, open(os.path.join(d, "ranking.json"), "w"), ensure_ascii=False, indent=1)
    STY.write_docs()
    out({"project": name, "output": spec["output"], "style_version": st["version"], "music": (spec.get("music") or {}).get("path"), "problems": probs},
        1 if any(p["level"] == "error" for p in probs) else 0)

def cmd_render(name):
    d = os.path.join(PROJ, name)
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "ranking.py"), d], capture_output=True, text=True)
    if r.returncode: out({"ok": False, "error": (r.stderr or r.stdout)[-1500:]}, 1)
    STY.write_docs()
    out({"ok": True, "output": r.stdout.strip().splitlines()[-1], "video_md": os.path.join(d, "VIDEO.md")})

def blackspans(clip):
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", clip, "-vf", "blackdetect=d=0.4:pic_th=0.94:pix_th=0.08", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    spans = []
    for line in r.stderr.splitlines():
        if "black_start" in line:
            kv = dict(x.split(":") for x in line.split("] ")[-1].split() if ":" in x)
            spans.append([round(float(kv["black_start"]), 2), round(float(kv["black_end"]), 2)])
    return spans

def cmd_check(name):
    d = os.path.join(PROJ, name); w = os.path.join(d, "work"); spec = json.load(open(os.path.join(d, "ranking.json")))
    issues, items = [], []
    outp = spec["output"]
    if not os.path.exists(outp): out({"ok": False, "issues": ["render yok"]}, 1)
    for i, it in enumerate(spec["items"]):
        clip = os.path.join(w, f"clip{i}.mp4"); dur = ranking.dur(clip)
        bl = blackspans(clip); items.append({"rank": it["rank"], "secs": round(dur, 1), "black": bl})
        if bl: issues.append(f"#{it['rank']}: siyah kare {bl} (kesiti kaydır)")
        if dur < 4: issues.append(f"#{it['rank']}: klip çok kısa ({dur:.1f} sn)")
        if dur > 22: issues.append(f"#{it['rank']}: klip çok uzun ({dur:.1f} sn)")
    total = ranking.dur(outp)
    if total > 175: issues.append(f"toplam {total:.0f} sn, Shorts sınırı 180 sn")
    r = subprocess.run(["ffmpeg", "-nostats", "-i", outp, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    lufs = next((float(l.split()[1]) for l in r.stderr.splitlines()[::-1] if l.strip().startswith("I:")), None)
    if lufs is None or not -17 <= lufs <= -12: issues.append(f"ses seviyesi {lufs} LUFS (hedef -14)")
    # contact sheet: one frame per rank at 1.5 s and 70 %, plus intro and outro
    from PIL import Image
    sheet = os.path.join(w, "check.jpg"); frames = []
    t0 = float(spec.get("intro_secs", 1.8)); times = [0.9]
    for i, it in enumerate(spec["items"]):
        dd = ranking.dur(os.path.join(w, f"seg{i}.mp4")); times += [t0 + 1.5, t0 + dd * 0.7]; t0 += dd
    times.append(total - 1.0)
    for k, t in enumerate(times):
        f = os.path.join(w, f"chk{k}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", outp, "-frames:v", "1", "-vf", "scale=270:-2", f])
        if os.path.exists(f): frames.append(Image.open(f))
    if frames:
        sh = Image.new("RGB", (270 * len(frames), frames[0].height)); [sh.paste(im, (k * 270, 0)) for k, im in enumerate(frames)]; sh.save(sheet)
    out({"ok": not issues, "duration": round(total, 1), "lufs": lufs, "items": items, "issues": issues, "sheet": sheet}, 0 if not issues else 2)

def cmd_queue(name, caption_file):
    d = os.path.join(PROJ, name); spec = json.load(open(os.path.join(d, "ranking.json")))
    cap = open(caption_file, encoding="utf-8").read().strip().replace("—", ",")
    if not cap or len(cap.splitlines()[0]) > 90: out({"ok": False, "error": "ilk satır başlık olmalı ve 90 karakteri geçmemeli"}, 1)
    slot = next_slot()
    post = social.create_post(spec["output"], {"default": cap, "youtube": cap}, ["youtube"], None, "autopilot", False, name,
                              {"youtube": {"publish_at": slot.timestamp()}})
    st = post["targets"]["youtube"]["status"]; uploaded = None
    if st == "bekliyor" and not server_up():         # auto-post on and the app is closed: upload from here
        social.run_due(); p = next(x for x in social.list_posts() if x["id"] == post["id"]); st = p["targets"]["youtube"]["status"]
        uploaded = p["targets"]["youtube"].get("url") or p["targets"]["youtube"].get("error")
    STY.write_docs()
    out({"ok": st != "hata", "post": post["id"], "status": st, "publish_at": slot.isoformat(), "uploaded": uploaded,
         "note": "onay bekliyor: biar-edit > Paylaşım kuyruğu'ndan onaylanınca yüklenir ve YouTube bu saatte yayınlar" if st == "onay bekliyor" else ""},
        0 if st != "hata" else 1)

def server_up():
    import urllib.request
    try: urllib.request.urlopen("http://localhost:8790/api", timeout=2); return True
    except Exception: return False

def cmd_log(name, topic):
    d = os.path.join(PROJ, name); spec = json.load(open(os.path.join(d, "ranking.json")))
    h = hist(); h["videos"].append({"project": name, "topic": topic, "date": time.strftime("%Y-%m-%d"),
                                    "music": (spec.get("music") or {}).get("path"), "items": [it["label"] for it in spec["items"]],
                                    "urls": [it.get("url") for it in spec["items"]]})
    save_hist(h); out({"ok": True, "count": len(h["videos"])})

def notify(title, msg, sub=""):
    tn = "/opt/homebrew/bin/terminal-notifier"
    if os.path.exists(tn):
        subprocess.run([tn, "-title", title, "-subtitle", sub, "-message", msg, "-sound", "Glass", "-group", "ranked-legends",
                        "-open", "biaredit://queue"], capture_output=True)
    else:
        subprocess.run(["osascript", "-e", f'display notification {json.dumps(msg)} with title {json.dumps(title)} subtitle {json.dumps(sub)} sound name "Glass"'])

def cmd_remind(test=False):
    waiting = [p for p in social.list_posts() if p.get("source") == "autopilot"
               and any(t["status"] == "onay bekliyor" for t in p["targets"].values())]
    if test and not waiting:
        notify("Ranked Legends", "Bu bir deneme bildirimi. Tıklayınca Paylaşım kuyruğu açılır.", "Bildirimler çalışıyor"); out({"ok": True, "test": True})
    if not waiting: out({"ok": True, "waiting": 0})
    p = waiting[0]; title = (p["captions"].get("youtube") or p["captions"].get("default", "")).splitlines()[0]
    pa = (p.get("options", {}).get("youtube") or {}).get("publish_at")
    when = datetime.datetime.fromtimestamp(pa, ZoneInfo(cfg()["tz"])).strftime("%H:%M") if pa else "onaylayınca"
    notify("Ranked Legends · onay bekliyor", f"{title}", f"Onaylarsan {when}'te yayına girer · tıkla, izle, onayla")
    out({"ok": True, "waiting": len(waiting), "title": title})

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit(0)
    {"status": lambda: cmd_status(), "new": lambda: cmd_new(a[1]), "render": lambda: cmd_render(a[1]), "check": lambda: cmd_check(a[1]),
     "queue": lambda: cmd_queue(a[1], a[2]), "log": lambda: cmd_log(a[1], a[2]), "remind": lambda: cmd_remind("--test" in a),
     "style": lambda: out(STY.head()), "compact": lambda: out({"ok": True, "moved": compact()}), "docs": lambda: out({"ok": True, "files": STY.write_docs()})}[a[0]]()
