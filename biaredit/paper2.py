"""Paper-cutout freeze-frame name card.

Usage: paper.py PAPERDIR  (needs frame.jpg = frozen 4K frame, mask_clean.png, end.jpg = first frame after)
Writes PAPERDIR/anim/f_00000.png ... (FREEZE seconds at 59.94 fps) and still.jpg (fully built state).
"""
import math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage as nd

P = sys.argv[1]
FPS = 60000 / 1001
FREEZE = 3.2
rng = np.random.default_rng(7)
os.makedirs(os.path.join(P, "anim"), exist_ok=True)

from PIL import ImageEnhance
V = Image.open(os.path.join(P, "frame.jpg")).convert("RGB")          # 1080x1920 portrait
VM = Image.open(os.path.join(P, "mask_clean.png")).convert("L")
end = Image.open(os.path.join(P, "end.jpg")).convert("RGB")
W, H = 3840, 2160
CROP = (0, 520, 1080, 1600)            # square around the speaker in the portrait frame
PX, SC = 420, 2.0                       # panel x offset, scale
def layout(v, m=None):
    bg = v.resize((W, int(v.height * W / v.width)), Image.LANCZOS)
    top = int(bg.height * 0.42 - H / 2); bg = bg.crop((0, top, W, top + H)).filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Brightness(bg).enhance(0.55)
    panel = v.crop(CROP).resize((int(1080 * SC), int(1080 * SC)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(3, 60, 2))
    # feather the panel's left/right edges into the blurred background
    fm = Image.new("L", panel.size, 255); fd = ImageDraw.Draw(fm); FE = 260
    for i in range(FE):
        v = int(255 * (i / FE) ** 1.5)
        fd.line((i, 0, i, panel.height), fill=v); fd.line((panel.width - 1 - i, 0, panel.width - 1 - i, panel.height), fill=v)
    bg.paste(panel, (PX, 0), fm)
    mm = None
    if m is not None:
        mm = Image.new("L", (W, H), 0); mm.paste(m.crop(CROP).resize(panel.size, Image.LANCZOS), (PX, 0))
    return bg, mm
frame, mmask = layout(V, VM)
frame.save(os.path.join(P, "frame_wide.jpg"), quality=95)
mask = np.array(mmask).astype(np.float32) / 255
F = np.array(frame).astype(np.float32)

def grain(shape, amt):
    g = rng.normal(0, 1, shape[:2]).astype(np.float32)
    g = nd.gaussian_filter(g, 0.8) * amt
    return g[..., None]

PAPER = np.array([244, 240, 231], np.float32)

# ---- background: dimmed, desaturated, paper grain -----------------------------------
grey = F @ np.array([0.299, 0.587, 0.114], np.float32)
BG_DONE = np.clip((F * 0.3 + grey[..., None] * 0.7) * 0.42 + grain(F.shape, 9), 0, 255)

# ---- sticker: person + irregular white paper border + shadow ---------------------------
ys, xs = np.nonzero(mask > 0.5)
x0, x1, y0, y1 = xs.min() - 80, xs.max() + 80, ys.min() - 80, ys.max() + 80
m = mask[y0:y1, x0:x1]
dist = nd.distance_transform_edt(m < 0.5)
wobble = nd.gaussian_filter(rng.normal(0, 1, m.shape), 6) * 60  # torn-paper irregularity
border = np.clip((34 + wobble - dist) / 2.0, 0, 1)                # ~34 px white rim
border = np.maximum(border, m)
paper = np.clip(PAPER + grain(m.shape, 6), 0, 255)
person = F[y0:y1, x0:x1]
rgb = paper * (1 - m[..., None]) + person * m[..., None]
sticker = Image.fromarray(np.dstack([rgb, border * 255]).astype(np.uint8), "RGBA")
CX, CY = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2  # sticker pivot in frame coords

def shadow_of(img, blur, alpha):
    a = img.split()[-1].filter(ImageFilter.GaussianBlur(blur))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(a.point(lambda v: int(v * alpha)))
    return sh

# ---- paper strips with torn edges --------------------------------------------------------
def strip(text, font, fill, ink, pad=(46, 26), icon=None):
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    iw = 0
    if icon:
        iw = int((b - t) * 1.05) + 26
    w, h = r - l + 2 * pad[0] + iw, b - t + 2 * pad[1]
    img = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    # torn polygon
    pts = []
    for x in np.linspace(0, w, 40):
        pts.append((20 + x, 20 + rng.uniform(-3, 3)))
    for y in np.linspace(0, h, 14):
        pts.append((20 + w + rng.uniform(-9, 9), 20 + y))
    for x in np.linspace(w, 0, 40):
        pts.append((20 + x, 20 + h + rng.uniform(-3, 3)))
    for y in np.linspace(h, 0, 14):
        pts.append((20 + rng.uniform(-9, 9), 20 + y))
    a = Image.new("L", img.size, 0); ImageDraw.Draw(a).polygon(pts, fill=255)
    base = np.clip(np.array(fill, np.float32) + grain((img.size[1], img.size[0]), 7), 0, 255)
    img = Image.fromarray(np.dstack([base, np.array(a)]).astype(np.uint8), "RGBA")
    dr = ImageDraw.Draw(img)
    tx = 20 + pad[0] + iw
    dr.text((tx - l, 20 + pad[1] - t), text, font=font, fill=ink)
    if icon == "x":  # simple X mark in a dark rounded square
        s = b - t; ix, iy = 20 + pad[0], 20 + pad[1]
        dr.rounded_rectangle((ix, iy, ix + s, iy + s), radius=s // 5, fill=ink)
        k = s * 0.24; lw = max(4, s // 9)
        dr.line((ix + k, iy + k, ix + s - k, iy + s - k), fill=fill, width=lw)
        dr.line((ix + s - k, iy + k, ix + k, iy + s - k), fill=fill, width=lw)
    if icon == "web":  # globe mark
        s = b - t; ix, iy = 20 + pad[0], 20 + pad[1]; lw = max(4, s // 12)
        dr.ellipse((ix, iy, ix + s, iy + s), outline=ink, width=lw)
        dr.ellipse((ix + s * 0.3, iy, ix + s * 0.7, iy + s), outline=ink, width=lw)
        dr.line((ix, iy + s / 2, ix + s, iy + s / 2), fill=ink, width=lw)
    return img

FUT = "/System/Library/Fonts/Supplemental/Futura.ttc"
AVC = "/System/Library/Fonts/Avenir Next Condensed.ttc"
big = ImageFont.truetype(FUT, 290, index=4)    # Futura Condensed ExtraBold
mid = ImageFont.truetype(AVC, 128, index=0)    # Avenir Next Condensed Bold
small = ImageFont.truetype(AVC, 100, index=2)   # Demi Bold
INK = (22, 22, 24)
S1 = strip("BIAR", big, (244, 240, 231), INK, pad=(60, 18))
S2 = strip("Founder of ArfDAO", mid, (255, 196, 46), INK)
S3 = strip("@justbiar", small, (244, 240, 231), INK, icon="x")
S4 = strip("biar.dev", small, (244, 240, 231), INK, icon="web")
# (image, x, y, angle, start time)
STRIPS = [(S1, 1900, 700, -3.0, 0.32), (S2, 1950, 1010, 2.0, 0.50),
          (S3, 1975, 1220, -1.5, 0.68), (S4, 1975, 1380, 1.0, 0.80)]

def ease_out_back(x, s=1.9):
    x = min(max(x, 0), 1) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2
def ease_out(x):
    x = min(max(x, 0), 1); return 1 - (1 - x) ** 3

def compose(u):
    k = ease_out(u / 0.25)
    bg = F * (1 - k) + BG_DONE * k
    out = Image.fromarray(bg.astype(np.uint8)).convert("RGBA")
    # sticker pop: scale up with overshoot, slight tilt
    p = ease_out_back((u - 0.06) / 0.4)
    if u > 0.06:
        sc, ang = 1 + 0.06 * p, -2.5 * min(1, p)
        st = sticker.resize((int(sticker.width * sc), int(sticker.height * sc)), Image.LANCZOS).rotate(ang, Image.BICUBIC, expand=True)
        sh = shadow_of(st, 22, 0.55)
        px, py = int(CX - st.width / 2), int(CY - st.height / 2 - 30 * min(1, p))
        out.alpha_composite(sh, (px + 18, py + 26)); out.alpha_composite(st, (px, py))
    for img, x, y, ang, t0 in STRIPS:
        q = ease_out((u - t0) / 0.32)
        if q <= 0:
            continue
        s = img.rotate(ang, Image.BICUBIC, expand=True)
        a = s.split()[-1].point(lambda v: int(v * q)); s.putalpha(a)
        dx = int((1 - q) * 260)
        sh = shadow_of(s, 14, 0.45 * q)
        out.alpha_composite(sh, (x + dx + 12, y + 16)); out.alpha_composite(s, (x + dx, y))
    out = out.convert("RGB")
    # hand back to the live video
    if u > FREEZE - 0.15:
        out = Image.blend(out, end, (u - (FREEZE - 0.15)) / 0.15)
    return out

import glob
for i, p in enumerate(sorted(glob.glob(os.path.join(P, "lead", "l_*.jpg")))):
    layout(Image.open(p).convert("RGB"))[0].save(os.path.join(P, "anim", f"a_{i:05d}.jpg"), quality=95)
n = round(FREEZE * FPS)
for i in range(n):
    compose(i / FPS).save(os.path.join(P, "anim", f"f_{i:05d}.jpg"), quality=95)
compose(2.0).save(os.path.join(P, "still.jpg"), quality=92)
print("frames", n)
