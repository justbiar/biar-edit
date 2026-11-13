"""Real-recording SFX pack from Freesound, CC0 only (no copyright, no attribution needed).

  python -I biaredit/sfxpack.py            fetch every category that is still missing
  python -I biaredit/sfxpack.py --force    fetch again

The categories are the sounds short-form ranking / edit videos lean on. For each one we take the most
downloaded CC0 results of a fitting length, trim the silence, peak-normalise and save
media/sfx/<id>.wav. Sources and licences go to media/sfx/CREDITS.md. Add a category here to grow it.
"""
import html, json, os, re, subprocess, sys, tempfile, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ["PATH"] = "/opt/homebrew/opt/ffmpeg-full/bin:/opt/homebrew/bin:" + os.environ.get("PATH", "")
OUT = os.path.join(ROOT, "media", "sfx")
META = os.path.join(OUT, "freesound.json")

# id prefix: (query, how many, min s, max s, tail fade s, what it is for)
CATS = {
    "whoosh":     ("whoosh", 4, 0.3, 2.0, 0.15, "geçiş, sıra değişirken"),
    "swoosh":     ("swoosh transition", 3, 0.3, 1.6, 0.12, "hızlı geçiş, yazı kayarken"),
    "riser":      ("riser", 3, 2.0, 6.0, 0.3, "#1 öncesi gerilim yükselişi"),
    "boom":       ("cinematic boom", 3, 1.0, 6.0, 0.6, "numara çıkışı, büyük an"),
    "impact":     ("impact hit", 4, 0.2, 2.5, 0.3, "numara çıkışı, darbe"),
    "bassdrop":   ("bass drop", 2, 0.8, 4.0, 0.5, "#1 çıkışı"),
    "shutter":    ("camera shutter", 2, 0.1, 1.2, 0.05, "flaş, fotoğraf anı"),
    "ding":       ("ding", 3, 0.3, 2.5, 0.4, "doğru cevap, liste dolunca"),
    "pop":        ("pop", 3, 0.05, 0.6, 0.05, "yazı belirince"),
    "tick":       ("clock tick", 2, 0.5, 4.0, 0.1, "gerilim, sayaç"),
    "scratch":    ("record scratch", 2, 0.3, 2.5, 0.1, "'dur bir saniye' anı"),
    "glitch":     ("glitch", 3, 0.2, 2.0, 0.1, "bozulma, hata, teknoloji"),
    "heartbeat":  ("heartbeat", 1, 1.0, 5.0, 0.3, "gerilim"),
    "drumroll":   ("drum roll", 2, 1.5, 6.0, 0.2, "#1 öncesi trampet"),
    "gasp":       ("crowd gasp", 2, 0.5, 4.0, 0.4, "seyirci şaşırıyor"),
    "crowdwow":   ("crowd wow", 2, 0.5, 4.0, 0.4, "seyirci 'vay'"),
    "cheer":      ("crowd cheer", 2, 1.5, 6.0, 0.6, "kazanma anı"),
    "applause":   ("applause", 1, 2.0, 7.0, 0.8, "final, alkış"),
    "laugh":      ("crowd laugh", 1, 1.0, 5.0, 0.5, "komik an"),
    "cash":       ("cash register", 1, 0.4, 2.5, 0.2, "para, rekor"),
    "explosion":  ("explosion", 2, 1.0, 5.0, 0.8, "patlama"),
    "glass":      ("glass break", 2, 0.4, 3.0, 0.4, "kırılma"),
    "slash":      ("sword swoosh", 2, 0.2, 1.5, 0.1, "keskin geçiş, vuruş"),
    "revcymbal":  ("reverse cymbal", 2, 1.0, 4.0, 0.05, "geçişe doğru emme"),
    "notif":      ("notification", 2, 0.2, 1.5, 0.2, "bildirim, yazı"),
    "typewriter": ("typewriter", 1, 0.5, 3.0, 0.1, "yazı yazılıyor"),
    "hit":        ("cinematic hit", 3, 0.3, 3.5, 0.4, "numara çıkışı, sinematik darbe"),
    "punch":      ("punch", 2, 0.1, 1.0, 0.1, "kısa yumruk darbesi, vuruş anı"),
    "airhorn":    ("air horn", 1, 0.5, 3.0, 0.2, "meme, abartı an"),
    "buzzer":     ("wrong buzzer", 1, 0.3, 2.0, 0.2, "yanlış, fail"),
    "fail":       ("fail trombone", 1, 1.0, 4.0, 0.3, "fail anı"),
}
HIT_PREFIX = ("boom", "impact", "hit", "punch", "bassdrop", "explosion", "glass", "slash")

UA = {"User-Agent": "Mozilla/5.0 (Macintosh) biar-edit"}

def search(q):
    url = "https://freesound.org/search/?" + urllib.parse.urlencode(
        {"q": q, "f": 'license:"Creative Commons 0"', "s": "Downloads (most first)"})
    page = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "replace")
    out = []
    for blk in page.split('class="bw-player"')[1:]:
        g = lambda k: (re.search(rf'data-{k}="([^"]*)"', blk) or [None, ""])[1]
        if not g("sound-id"): continue
        out.append({"id": g("sound-id"), "user": html.unescape(g("username")), "title": html.unescape(g("title")),
                    "dur": float(g("duration") or 0), "downloads": int(g("num-downloads") or 0),
                    "mp3": g("mp3").replace("-lq.mp3", "-hq.mp3")})
    return out

def process(src, dst, fade):
    """Trim leading silence, cut to the sound, peak-normalise to -1 dBFS, 48 kHz stereo wav."""
    tmp = dst + ".tmp.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af",
                    "silenceremove=start_periods=1:start_threshold=-50dB,aresample=48000,aformat=channel_layouts=stereo",
                    tmp], check=True)
    r = subprocess.run(["ffmpeg", "-i", tmp, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    peak = float((re.search(r"max_volume: (-?[\d.]+) dB", r.stderr) or [0, "0"])[1])
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", tmp],
                             capture_output=True, text=True).stdout.strip() or 0)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af",
                    f"volume={-1 - peak:.2f}dB,afade=t=out:st={max(0, d - fade):.3f}:d={fade}", dst], check=True)
    os.remove(tmp)
    return d

BLOCK_WORDS = re.compile(r"door|knock|gun|shot|mouse|click sounds|fart|scream", re.I)

def main(force=False):
    meta = json.load(open(META)) if os.path.exists(META) else {}
    if force:
        for k in list(meta):
            f = os.path.join(OUT, k + ".wav")
            if os.path.exists(f): os.remove(f)
        meta = {}
    used = {re.search(r"/sounds/(\d+)/", v["url"]).group(1) for v in meta.values()}
    work = tempfile.mkdtemp(prefix="fs_dl_")              # downloads stay in their own folder
    made = []
    for cat, (q, n, lo, hi, fade, use) in CATS.items():
        have = [k for k in meta if k.rsplit("_", 1)[0] == cat]
        need = n - len(have)
        if need <= 0: continue
        nxt = max([int(k.rsplit("_", 1)[1]) for k in have] or [0]) + 1
        try: res = [r for r in search(q) if lo <= r["dur"] <= hi and r["mp3"] and r["id"] not in used and not BLOCK_WORDS.search(r["title"])]
        except Exception as e: print(json.dumps({"cat": cat, "error": str(e)[:200]})); continue
        k = 0
        for r in res:
            if k >= need: break
            name = f"{cat}_{nxt}"; raw = os.path.join(work, r["id"] + ".mp3"); dst = os.path.join(OUT, name + ".wav")
            try:
                urllib.request.urlretrieve(r["mp3"], raw)
                d = process(raw, dst, fade)
            except Exception as e:
                print(json.dumps({"cat": cat, "skip": r["id"], "error": str(e)[:150]})); continue
            meta[name] = {"use": use, "title": r["title"], "author": r["user"], "license": "CC0 1.0",
                          "url": f"https://freesound.org/people/{urllib.parse.quote(r['user'])}/sounds/{r['id']}/",
                          "downloads": r["downloads"], "secs": round(d, 2), "hit": cat.startswith(HIT_PREFIX)}
            used.add(r["id"]); made.append(dst); k += 1; nxt += 1
            time.sleep(0.4)
        print(json.dumps({"cat": cat, "got": k}), flush=True)
        time.sleep(1.0)
    json.dump(meta, open(META, "w"), ensure_ascii=False, indent=1)
    lines = ["# Ses efekti kaynakları", "",
             "Hepsi Freesound'dan **CC0 1.0** (kamu malı): ticari kullanım serbest, kredi gerekmez. Yine de kaynakları burada tutuyoruz.", "",
             "| Dosya | Ne için | Orijinal | Yapan | Bağlantı |", "|---|---|---|---|---|"]
    lines += [f"| `{k}` | {v['use']} | {v['title']} | {v['author']} | {v['url']} |" for k, v in sorted(meta.items())]
    open(os.path.join(OUT, "CREDITS.md"), "w").write("\n".join(lines) + "\n")
    import media                                            # library: exactly the files in META
    paths = {os.path.join(OUT, k + ".wav") for k in meta}
    for it in media.library():
        if "freesound" in (it.get("tags") or []) and it["path"] not in paths: media.remove(it["id"])
    have = {it["path"] for it in media.library()}
    new = sorted(p for p in paths if p not in have and os.path.exists(p))
    if new: media.add(new, kind="sfx", tags=["freesound", "cc0"])
    print(json.dumps({"ok": True, "new": len(made), "total": len(meta)}))

if __name__ == "__main__":
    main("--force" in sys.argv)
