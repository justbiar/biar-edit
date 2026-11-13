"""Render the edit: per-segment 4K SDR video files + one edited audio track.

Usage: render.py WORKDIR SRCDIR [--plan-only]
Writes WORKDIR/render/seg_XXXX.mp4, list.txt, audio.wav, segments.json.
"""
import json, os, subprocess, sys, wave
from concurrent.futures import ThreadPoolExecutor
import numpy as np

W, SRC = sys.argv[1], sys.argv[2]
PLAN_ONLY = "--plan-only" in sys.argv
R = os.path.join(W, "render"); os.makedirs(R, exist_ok=True)
E = json.load(open(os.path.join(W, "edits.json")))
TRACK = {int(k): v for k, v in json.load(open(os.path.join(W, "track.json"))).items()}
DUR = 1474.96
FPS = 60000 / 1001
MAIN = os.path.join(SRC, "ana video.MOV")
def _find(c):
    for ext in (".MP4", ".MOV", ".mp4", ".mov", ".LRF"):
        if os.path.exists(os.path.join(SRC, c + ext)):
            return os.path.join(SRC, c + ext)
    raise SystemExit(f"missing source for {c}")
CLIPS = {c: _find(c) for c in E["clips"] if c not in ("SCREEN", "PHOTO", "PAPER")}
HDR = {"IMG_4257", "IMG_4258"}                 # iPhone HLG
VERTICAL = {"IMG_4257", "20261008_103056"}     # portrait after autorotate
PHOTO = os.path.join(W, "render", "photo.jpg")

# HLG (BT.2020) -> SDR BT.709.
TM = "zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0:peak=4,zscale=t=bt709:m=bt709:r=tv"
OUT = ["-an", "-c:v", "hevc_videotoolbox", "-b:v", "24M", "-maxrate", "36M", "-tag:v", "hvc1", "-g", "120",
       "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-r", "60000/1001"]
FIN = "format=nv12,setsar=1"

# ---- timeline -------------------------------------------------------------------------
cuts = sorted(E["cuts"], key=lambda c: c["start"])
keep, t = [], 0.0
for c in cuts:
    if c["start"] > t + 1e-3:
        keep.append((t, c["start"]))
    t = max(t, c["end"])
if t < DUR:
    keep.append((t, DUR))

def out_len(s, e):
    return sum(max(0, min(e, b) - max(s, a)) for a, b in keep)

broll = sorted(E["broll"], key=lambda b: b["start"])
def visual_at(t):
    for b in broll:
        if b["start"] <= t < b["end"]:
            return b
    return None

segs, o = [], 0.0
for a, b in keep:
    marks = sorted({a, b, *[x for br in broll for x in (br["start"], br["end"]) if a < x < b]})
    for s, e in zip(marks, marks[1:]):
        if e - s < 1e-3:
            continue
        br = visual_at((s + e) / 2)
        segs.append({"src": round(s, 4), "end": round(e, 4), "o0": o, "o1": o + (e - s),
                     "vis": br["clip"] if br else "MAIN",
                     "clipT": (br["clipIn"] + out_len(br["start"], s)) if br and br["clip"] not in ("SCREEN",) else None,
                     "brId": br["id"] if br else None})
        o += e - s
for i, s in enumerate(segs):
    s["f0"], s["f1"] = round(s["o0"] * FPS), round(s["o1"] * FPS)
    s["frames"] = s["f1"] - s["f0"]
    s["i"] = i
total_out = o
json.dump(segs, open(os.path.join(R, "segments.json"), "w"), indent=0)
print(f"{len(segs)} segments, output {total_out/60:.2f} min, {segs[-1]['f1']} frames")

# ---- audio ----------------------------------------------------------------------------
def build_audio():
    wav48 = os.path.join(R, "main48.wav")
    if not os.path.exists(wav48):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", MAIN, "-vn", "-ac", "2", "-ar", "48000", wav48], check=True)
    w = wave.open(wav48); sr = w.getframerate()
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, 2).astype(np.float32)
    fade = int(0.008 * sr)
    parts = []
    for s, e in keep:
        p = a[int(round(s * sr)): int(round(e * sr))].copy()
        if len(p) > 2 * fade:
            ramp = np.linspace(0, 1, fade)[:, None]
            p[:fade] *= ramp; p[-fade:] *= ramp[::-1]
        parts.append(p)
    y = np.clip(np.concatenate(parts), -32768, 32767).astype(np.int16)
    raw = os.path.join(R, "audio_raw.wav")
    o = wave.open(raw, "wb"); o.setnchannels(2); o.setsampwidth(2); o.setframerate(sr); o.writeframes(y.tobytes()); o.close()
    # Even out loudness (speech target for online video).
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af", "highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar", "48000", os.path.join(R, "audio.wav")], check=True)
    print(f"audio {len(y)/sr/60:.2f} min")

# ---- video segments -------------------------------------------------------------------
CW, CH, CX, CY = 1560, 878, 2076, 1125
def crop_expr(s0, dur, axis):
    """Piecewise-linear crop offset following the tracked camera, t = segment-local time."""
    base, size, lim = (CX, CW, 3840) if axis == 0 else (CY, CH, 2160)
    def tr(k):
        return (TRACK[k] if k in TRACK else TRACK[min(TRACK, key=lambda x: abs(x - k))])[axis]
    def at(src):
        k = int(src); f = src - k
        v = base + tr(k) * (1 - f) + tr(k + 1) * f - size / 2
        return max(0, min(lim - size, v))
    knots = [0.0] + [k - s0 for k in range(int(s0) + 1, int(s0 + dur) + 1)] + [dur]
    vals = [at(s0 + k) for k in knots]
    expr = f"{vals[-1]:.1f}"
    for (k0, v0), (k1, v1) in reversed(list(zip(zip(knots, vals), zip(knots[1:], vals[1:])))):
        if k1 - k0 < 1e-6:
            continue
        expr = f"if(lt(t,{k1:.4f}),{v0:.1f}+({v1-v0:.1f})*(t-{k0:.4f})/{k1-k0:.4f},{expr})"
    return expr

# ---- stabilization: keep slow camera moves, remove sway shorter than ~2.5 s -------------
from scipy import ndimage as _nd
_z = np.load(os.path.join(W, "motion2.npz"))
_px, _py = _nd.median_filter(_z["px"], 9), _nd.median_filter(_z["py"], 9)
ZW, ZH = 3728, 2096                       # 3 % zoom gives the room to shift
MX, MY = (3840 - ZW) / 2, (2160 - ZH) / 2
STX = np.clip(_px - _nd.gaussian_filter1d(_px, 150, mode="nearest"), -MX + 2, MX - 2)
STY = np.clip(_py - _nd.gaussian_filter1d(_py, 150, mode="nearest"), -MY + 2, MY - 2)
def sfr(t):
    return min(len(STX) - 1, max(0, int(round(t * FPS))))

def track_at(src, axis):
    k = int(src); f = src - k
    tr = lambda j: (TRACK[j] if j in TRACK else TRACK[min(TRACK, key=lambda x: abs(x - j))])[axis]
    return tr(k) * (1 - f) + tr(k + 1) * f

def sendcmd_file(s, xy):
    """Per-frame crop positions as an ffmpeg sendcmd script (times are segment-local)."""
    path = os.path.join(R, f"cmd_{s['i']:04d}.txt")
    with open(path, "w") as f:
        for i in range(s["frames"]):
            x, y = xy(s["src"] + i / FPS, sfr(s["src"]) + i)
            f.write(f"{i / FPS:.5f} crop x {x:.2f}, crop y {y:.2f};\n")
    return path

GFX = os.path.join(W, "gfx")
GWIN = json.load(open(os.path.join(GFX, "windows.json"))) if os.path.exists(os.path.join(GFX, "windows.json")) else []
PAPER_DIR = os.path.join(W, "paper2", "seq")
PAPER_F0 = min((x["f0"] for x in segs if x["vis"] == "PAPER"), default=None)

def cmd(s):
    out = os.path.join(R, f"seg_{s['i']:04d}.mp4")
    n, vis = s["frames"], s["vis"]
    base = ["ffmpeg", "-v", "error", "-y"]
    if vis == "MAIN":
        c = sendcmd_file(s, lambda t, k: (MX + STX[k], MY + STY[k]))
        inp = ["-hwaccel", "videotoolbox", "-ss", f"{s['src']:.4f}", "-i", MAIN]
        chain = f"sendcmd=f={c},crop={ZW}:{ZH}:{MX}:{MY},{TM},scale=3840:2160:flags=lanczos"
    elif vis == "SCREEN":
        def xy(t, k):
            x = CX + track_at(t, 0) + STX[k] - CW / 2
            y = CY + track_at(t, 1) + STY[k] - CH / 2
            return max(0, min(3840 - CW, x)), max(0, min(2160 - CH, y))
        c = sendcmd_file(s, xy)
        inp = ["-hwaccel", "videotoolbox", "-ss", f"{s['src']:.4f}", "-i", MAIN]
        chain = f"sendcmd=f={c},crop={CW}:{CH}:0:0,{TM},scale=3840:2160:flags=lanczos"
    elif vis == "PAPER":
        inp = ["-framerate", "60000/1001", "-start_number", str(s["f0"] - PAPER_F0), "-i", os.path.join(PAPER_DIR, "p_%05d.jpg")]
        chain = "format=yuv420p"
    elif vis == "PHOTO":
        z0 = 1.0 + 0.0006 * round(s["clipT"] * FPS)
        z = f"zoompan=z='{z0:.4f}+0.0006*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=3840x2160:fps=60000/1001"
        inp = ["-loop", "1", "-framerate", "60000/1001", "-i", PHOTO]
        chain = f"scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160,{z},format=yuv420p"
    else:
        src = CLIPS[vis]
        fmt = ["-f", "mov"] if src.endswith(".LRF") else []   # DJI low-res proxies are MP4 inside
        pre = f"{TM},format=yuv420p" if vis in HDR else "format=yuv420p"
        # low-resolution sources (720p LRF, 1080p phone) get a light sharpen after upscaling
        sharp = ",unsharp=5:5:0.6" if (src.endswith(".LRF") or vis in HDR or vis in VERTICAL) else ""
        inp = ["-ss", f"{s['clipT']:.4f}"] + fmt + ["-i", src]
        if vis in VERTICAL:  # portrait phone clip: blurred fill behind the centred frame
            chain = (f"{pre},split[a][b];[a]scale=384:216:force_original_aspect_ratio=increase,crop=384:216,"
                     f"gblur=sigma=6,scale=3840:2160:flags=bicubic[bg];"
                     f"[b]scale=-2:2160:flags=lanczos{sharp}[fg];[bg][fg]overlay=(W-w)/2:0")
        else:
            chain = f"{pre},fps=60000/1001,scale=3840:2160:flags=lanczos{sharp}"
    # graphics overlay where a chapter card / outro window intersects this segment
    g = [w for w in GWIN if w[0] <= s["f1"] - 1 and w[1] >= s["f0"]]
    if g:
        g0 = max(s["f0"], g[0][0])
        ginp = ["-itsoffset", f"{(g0 - s['f0']) / FPS:.5f}", "-framerate", "60000/1001", "-start_number", str(g0),
                "-i", os.path.join(GFX, "g_%06d.png")]
        fc = f"[0:v]{chain}[v];[1:v]format=rgba[g];[v][g]overlay=0:0:eof_action=pass:format=auto,{FIN}[o]"
        return base + inp + ginp + ["-frames:v", str(n), "-filter_complex", fc, "-map", "[o]"] + OUT + [out]
    return base + inp + ["-frames:v", str(n), "-filter_complex", f"[0:v]{chain},{FIN}[o]", "-map", "[o]"] + OUT + [out]

import hashlib
def seg_key(s):
    k = f"{s['vis']}|{s['src']:.4f}|{s['end']:.4f}|{s['frames']}|{s['clipT']}|{s['f0']}"
    return os.path.join(R, "h_" + hashlib.sha1(k.encode()).hexdigest()[:16] + ".mp4")

def run(s):
    out = os.path.join(R, f"seg_{s['i']:04d}.mp4")
    cached = seg_key(s)
    if os.path.exists(cached) and os.path.getsize(cached) > 0:
        if os.path.exists(out): os.remove(out)
        os.rename(cached, out)                      # reuse an identical segment from the last render
        return s["i"], "reuse"
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return s["i"], "skip"
    r = subprocess.run(cmd(s), capture_output=True, text=True)
    if r.returncode:
        return s["i"], "ERR " + r.stderr[-400:]
    return s["i"], "ok"

if PLAN_ONLY:
    from collections import Counter
    print(Counter(s["vis"] for s in segs if s["frames"] > 0))
    print(cmd(next(s for s in segs if s["vis"] == "SCREEN"))[-25:])
    sys.exit()

if not os.path.exists(PHOTO):
    subprocess.run(["sips", "-s", "format", "jpeg", "-Z", "4800", os.path.join(SRC, "IMG_2262.HEIC"), "--out", PHOTO],
                   check=True, capture_output=True)
build_audio()
todo = [s for s in segs if s["frames"] > 0]
done = 0
with ThreadPoolExecutor(3) as ex:
    for i, st in ex.map(run, todo):
        done += 1
        if st.startswith("ERR"):
            print("segment", i, st, flush=True)
        if done % 20 == 0 or done == len(todo):
            print(f"progress {done}/{len(todo)}", flush=True)
bad = []
for s in todo:
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                        "stream=nb_read_packets", "-of", "csv=p=0", os.path.join(R, f"seg_{s['i']:04d}.mp4")],
                       capture_output=True, text=True).stdout.strip().strip(",").split(",")[0]
    if int(o or 0) != s["frames"]:
        bad.append((s["i"], s["vis"], s["frames"], o))
if bad:
    raise SystemExit(f"frame count mismatch: {bad}")
print("all segments have the planned frame count")
with open(os.path.join(R, "list.txt"), "w") as f:
    for s in todo:
        f.write(f"file 'seg_{s['i']:04d}.mp4'\n")
print("segments done")
