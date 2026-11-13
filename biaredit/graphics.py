"""Chapter cards and outro as transparent 4K PNG overlays, named by output frame number.

Usage: graphics.py WORKDIR   (reads render/segments.json for the source->output mapping)
Writes WORKDIR/gfx/g_<frame>.png and gfx/windows.json [[first_frame, last_frame], ...].
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage as nd

W = sys.argv[1]
OUT = os.path.join(W, "gfx"); os.makedirs(OUT, exist_ok=True)
FPS = 60000 / 1001
SW, SH = 3840, 2160
segs = json.load(open(os.path.join(W, "render", "segments.json")))
rng = np.random.default_rng(11)

def out_frame(src):
    for s in segs:
        if s["src"] <= src < s["end"]:
            return round((s["o0"] + src - s["src"]) * FPS)
    nxt = min((s for s in segs if s["src"] >= src), key=lambda s: s["src"])
    return round(nxt["o0"] * FPS)

def grain(h, w, amt):
    return (nd.gaussian_filter(rng.normal(0, 1, (h, w)), 0.8) * amt)[..., None]

def strip(text, font, fill, ink, pad=(46, 22)):
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    w, h = r - l + 2 * pad[0], b - t + 2 * pad[1]
    pts = [(20 + x, 20 + rng.uniform(-3, 3)) for x in np.linspace(0, w, 40)]
    pts += [(20 + w + rng.uniform(-9, 9), 20 + y) for y in np.linspace(0, h, 14)]
    pts += [(20 + x, 20 + h + rng.uniform(-3, 3)) for x in np.linspace(w, 0, 40)]
    pts += [(20 + rng.uniform(-9, 9), 20 + y) for y in np.linspace(h, 0, 14)]
    size = (w + 40, h + 40)
    a = Image.new("L", size, 0); ImageDraw.Draw(a).polygon(pts, fill=255)
    base = np.clip(np.array(fill, np.float32) + grain(size[1], size[0], 7), 0, 255)
    img = Image.fromarray(np.dstack([base, np.array(a)]).astype(np.uint8), "RGBA")
    ImageDraw.Draw(img).text((20 + pad[0] - l, 20 + pad[1] - t), text, font=font, fill=ink)
    return img

def shadow(img, blur, alpha):
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(img.split()[-1].filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * alpha)))
    return sh

def ease(x):
    x = min(max(x, 0), 1); return 1 - (1 - x) ** 3

FUT = "/System/Library/Fonts/Supplemental/Futura.ttc"
AVC = "/System/Library/Fonts/Avenir Next Condensed.ttc"
num_f = ImageFont.truetype(FUT, 120, index=4)
ttl_f = ImageFont.truetype(FUT, 150, index=4)
hand_f = ImageFont.truetype(AVC, 96, index=2)
INK, PAPER, YEL = (22, 22, 24), (244, 240, 231), (255, 196, 46)

# card: list of (strip, x, y, angle, delay); slides in from the left (chapters) or right (outro)
CARDS = []
_cfg = json.load(open(os.path.join(W, "chapters.json"))) if os.path.exists(os.path.join(W, "chapters.json")) else {
    "chapters": [{"src": 313.8, "num": "01", "title": "THE EVOLUTION OF SOFTWARE"}], "outro": {"src": 1449.3}}
for src, n, title in [(c["src"], c["num"], c["title"]) for c in _cfg["chapters"]]:
    CARDS.append({"f0": out_frame(src) - 6, "dur": 3.8, "dir": -1, "parts": [
        (strip(n, num_f, YEL, INK, pad=(34, 14)), 170, 1500, -3.0, 0.0),
        (strip(title, ttl_f, PAPER, INK), 170, 1690, 1.5, 0.12)]})
f_end = round(segs[-1]["o1"] * FPS)
f_out = out_frame(_cfg["outro"]["src"]) if _cfg.get("outro") else None
if f_out is not None: CARDS.append({"f0": f_out, "dur": (f_end - f_out) / FPS + 1, "dir": 1, "hold_to_end": True, "parts": [
    (strip("BIAR", ImageFont.truetype(FUT, 220, index=4), PAPER, INK, pad=(54, 16)), 2550, 1240, -3.0, 0.0),
    (strip("@justbiar  ·  biar.dev", hand_f, YEL, INK), 2420, 1560, 2.0, 0.15)]})

windows = []
for c in CARDS:
    nfr = int(round(c["dur"] * FPS))
    windows.append([c["f0"], c["f0"] + nfr - 1])
    rot = [(s.rotate(a, Image.BICUBIC, expand=True), x, y, d) for s, x, y, a, d in c["parts"]]
    for i in range(nfr):
        u = i / FPS
        canvas = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
        for s, x, y, d in rot:
            q_in = ease((u - d) / 0.35)
            q_out = 1.0 if c.get("hold_to_end") else ease((c["dur"] - 0.35 - u + d * 0.5) / 0.35)
            q = min(q_in, q_out)
            if q <= 0:
                continue
            dx = int((1 - q) * 520) * (1 if c["dir"] > 0 else -1)
            ss = s.copy(); ss.putalpha(s.split()[-1].point(lambda v: int(v * q)))
            canvas.alpha_composite(shadow(ss, 14, 0.45), (x + dx + 12, y + 16))
            canvas.alpha_composite(ss, (x + dx, y))
        canvas.save(os.path.join(OUT, f"g_{c['f0'] + i:06d}.png"), compress_level=3)
json.dump(windows, open(os.path.join(OUT, "windows.json"), "w"))
print("windows (output frames):", windows)
