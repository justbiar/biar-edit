"""Reusable 9:16 reel builder (1080x1920, 30 fps).

A reel is a list of beats. Each beat plays one audio piece (file, a, b) and shows one or more
shots over it. Shots are either synced to the audio's own video or cutaways from other clips.
Captions are given in SOURCE seconds, so they stay attached to the words.

    beat = dict(audio=(file, a, b), shots=[shot, ...], caps=[(text, s, e), ...], titles=[...])
    shot = dict(kind="sync"|"clip"|"native"|"split", dur=None|sec, file=..., t=..., cx=None|px, hdr=True)

Usage: from reelkit import build; build(beats, out_path, workdir)
"""
import os, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage as nd

FPS, VW, VH = 30, 1080, 1920
TM = "zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0:peak=4,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
FUT = "/System/Library/Fonts/Supplemental/Futura.ttc"
AVC = "/System/Library/Fonts/Avenir Next Condensed.ttc"
INK, PAPER, YEL = (22, 22, 24), (244, 240, 231), (255, 196, 46)
rng = np.random.default_rng(9)

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(" ".join(cmd[:8]) + "\n" + r.stderr[-800:])
    return r.stdout

def probe(src):
    s = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,color_transfer:stream_side_data=rotation",
             "-of", "default=nw=1", src])
    d = dict(l.split("=", 1) for l in s.splitlines() if "=" in l)
    w, h = int(d["width"]), int(d["height"])
    if d.get("rotation", "0").strip("-") in ("90", "270"):
        w, h = h, w
    return w, h, d.get("color_transfer") == "arib-std-b67"

# ---- find the speaker: the brightest-dressed standing person (works for the white outfit) ----------
def speaker_cx(src, t, hdr, default=None):
    import Quartz, Vision
    from Foundation import NSURL
    w, h, _ = probe(src)
    tmp = "/tmp" if False else os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(tmp, "_cx.jpg")
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf",
         (TM + "," if hdr else "") + "scale=960:-2,format=yuvj420p", p])
    img = Quartz.CGImageSourceCreateImageAtIndex(Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(p), None), 0, None)
    req = Vision.VNDetectHumanRectanglesRequest.alloc().initWithCompletionHandler_(None)
    req.setUpperBodyOnly_(False)
    Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None).performRequests_error_([req], None)
    a = np.array(Image.open(p).convert("L")).astype(np.float32); H, Wd = a.shape
    best, score = None, -1
    for o in req.results() or []:
        b = o.boundingBox()
        x0, x1 = int(b.origin.x * Wd), int((b.origin.x + b.size.width) * Wd)
        y1, y0 = int((1 - b.origin.y) * H), int((1 - b.origin.y - b.size.height) * H)
        if b.size.height < 0.12 or y1 - y0 < 10 or x1 - x0 < 4:
            continue
        reg = a[max(0, y0):y1, max(0, x0):x1]
        s = float(np.percentile(reg, 75)) * (0.6 + b.size.height)   # bright outfit, prefer full figures
        if s > score:
            best, score = (b.origin.x + b.size.width / 2) * w, s
    return best if best is not None else (default if default is not None else w / 2)

# ---- graphics -------------------------------------------------------------------------------------
def grain(h, w, amt): return (nd.gaussian_filter(rng.normal(0, 1, (h, w)), 0.8) * amt)[..., None]
def strip(text, font, fill, ink=INK, pad=(30, 14)):
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, t_, r_, b_ = d.textbbox((0, 0), text, font=font)
    w, h = r_ - l + 2 * pad[0], b_ - t_ + 2 * pad[1]
    pts = [(14 + x, 14 + rng.uniform(-2, 2)) for x in np.linspace(0, w, 30)]
    pts += [(14 + w + rng.uniform(-6, 6), 14 + y) for y in np.linspace(0, h, 10)]
    pts += [(14 + x, 14 + h + rng.uniform(-2, 2)) for x in np.linspace(w, 0, 30)]
    pts += [(14 + rng.uniform(-6, 6), 14 + y) for y in np.linspace(h, 0, 10)]
    size = (w + 28, h + 28)
    a = Image.new("L", size, 0); ImageDraw.Draw(a).polygon(pts, fill=255)
    base = np.clip(np.array(fill, np.float32) + grain(size[1], size[0], 6), 0, 255)
    img = Image.fromarray(np.dstack([base, np.array(a)]).astype(np.uint8), "RGBA")
    ImageDraw.Draw(img).text((14 + pad[0] - l, 14 + pad[1] - t_), text, font=font, fill=ink)
    if img.width > VW - 60:
        img = img.resize((VW - 60, int(img.height * (VW - 60) / img.width)), Image.LANCZOS)
    return img
def shadow(img, blur, alpha):
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(img.split()[-1].filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * alpha)))
    return sh
def ease(x): x = min(max(x, 0), 1); return 1 - (1 - x) ** 3
def place(canvas, s, x, y, ang, q, dx_dir=-1):
    r = s.rotate(ang, Image.BICUBIC, expand=True)
    r.putalpha(r.split()[-1].point(lambda v: int(v * q)))
    dx = int((1 - q) * 220) * dx_dir
    canvas.alpha_composite(shadow(r, 10, 0.45 * q), (x + dx + 8, y + 12)); canvas.alpha_composite(r, (x + dx, y))

FONTS = {"big": ImageFont.truetype(FUT, 130, index=4), "huge": ImageFont.truetype(FUT, 150, index=4),
         "mid": ImageFont.truetype(AVC, 72, index=0), "sm": ImageFont.truetype(AVC, 60, index=2)}
COL = {"y": YEL, "w": PAPER}
cap_font = ImageFont.truetype(AVC, 86, index=8)
def caption(text, maxw=940):
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    width = lambda s: d.textbbox((0, 0), s, font=cap_font, stroke_width=9)[2]
    lines = [text]
    if width(text) > maxw and len(text.split()) > 1:
        ws = text.split()
        k = min(range(1, len(ws)), key=lambda i: max(width(" ".join(ws[:i])), width(" ".join(ws[i:]))))
        lines = [" ".join(ws[:k]), " ".join(ws[k:])]
    lh = 104; wmax = max(width(s) for s in lines)
    img = Image.new("RGBA", (wmax + 20, lh * len(lines) + 30), (0, 0, 0, 0)); dr = ImageDraw.Draw(img)
    for j, s in enumerate(lines):
        l, t_, r_, b_ = d.textbbox((0, 0), s, font=cap_font, stroke_width=9)
        dr.text(((img.width - (r_ - l)) // 2 - l, 10 + j * lh - t_), s, font=cap_font, fill=(255, 255, 255), stroke_width=9, stroke_fill=(10, 10, 12))
    if img.width > maxw + 20:
        img = img.resize((maxw + 20, int(img.height * (maxw + 20) / img.width)), Image.LANCZOS)
    return img

# ---- builder --------------------------------------------------------------------------------------
def build(beats, out, workdir, end_card=None, cap_y=1400, progress=None, fx=None):
    prog = progress or (lambda f, m: None)
    fx = fx or {}
    R = os.path.join(workdir, "rk_" + os.path.splitext(os.path.basename(out))[0].replace(" ", "_"))
    os.makedirs(R, exist_ok=True)
    ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an"]
    # timeline
    t, parts, pcs, CAPS, TITLES, TRANS = 0.0, [], [], [], [], []
    for bi, b in enumerate(beats):
        prog(0.7 * bi / max(1, len(beats)), f"plan {bi + 1}/{len(beats)}")
        f, a, z = b["audio"]; dur = z - a
        # shots: fill the beat; a shot with dur=None takes the rest
        fixed = sum(s.get("dur") or 0 for s in b["shots"])
        o = 0.0
        for si, s in enumerate(b["shots"]):
            sd = s.get("dur") or (dur - fixed)
            r0, r1 = t + o, t + o + sd
            n = int(round(r1 * FPS)) - int(round(r0 * FPS))
            p = os.path.join(R, f"b{bi:02d}s{si}.mp4"); parts.append(p)
            kind = s["kind"]
            if kind == "paper":
                paper_frames(s["dir"], R, p, n, int(round(s.get("offset", 0.0) * FPS)), ENC)
                o += sd
                continue
            src = f if kind == "sync" else s["file"]
            st = (a + o) if kind == "sync" else s["t"]           # synced shots start on their own audio
            w, h, hdr = probe(src)
            pre = (TM + "," if hdr else "")
            look = color_filter(s.get("filter") or fx.get("filter"), fx.get("lut") if not s.get("filter") else s.get("lut"))
            post = ("," + look) if look else ""
            if s.get("layout") == "split":
                # top: projection close-up (16:9) ; bottom: the speaker
                sx, sy, sw_, sh_ = s["screen"]; px, py, pw, ph = s["person"]
                th = int(VW * 9 / 16) // 2 * 2; bh = VH - th
                vf = (pre + f"fps={FPS},split[a][b];[a]crop={sw_}:{sh_}:{sx}:{sy},scale={VW}:{th}:flags=lanczos[top];"
                      f"[b]crop={pw}:{ph}:{px}:{py},scale={VW}:{bh}:flags=lanczos,unsharp=5:5:0.3[bot];"
                      f"[top][bot]vstack=inputs=2" + post)
                run(["ffmpeg", "-v", "error", "-y", "-ss", f"{st:.3f}", "-i", src, "-frames:v", str(n), "-filter_complex", vf] + ENC + [p])
                o += sd
                continue
            if s.get("layout") == "fit" and w > h:
                # full landscape frame (slightly zoomed) in the middle, blurred copy behind it
                zoom = s.get("zoom", 1.15)
                cw, ch = int(w / zoom) // 2 * 2, int(h / zoom) // 2 * 2
                cx, cy = s.get("cx", w / 2), s.get("cy", h / 2)
                x0 = int(max(0, min(w - cw, cx - cw / 2))); y0 = int(max(0, min(h - ch, cy - ch / 2)))
                fh = int(VW * ch / cw) // 2 * 2
                vf = (pre + f"fps={FPS},split[a][b];[a]scale=-2:{VH // 8},crop={VW // 8}:{VH // 8},gblur=sigma=4,scale={VW}:{VH},"
                      f"eq=brightness=-0.08:saturation=0.8[bg];[b]crop={cw}:{ch}:{x0}:{y0},scale={VW}:{fh}:flags=lanczos[fg];"
                      f"[bg][fg]overlay=0:{s.get('fy', (VH - fh) // 2)}" + post)
                run(["ffmpeg", "-v", "error", "-y", "-ss", f"{st:.3f}", "-i", src, "-frames:v", str(n), "-filter_complex", vf] + ENC + [p])
                o += sd
                continue
            if kind == "native" or (w < h):
                vf = pre + f"fps={FPS},scale={VW}:{VH}:force_original_aspect_ratio=increase,crop={VW}:{VH},unsharp=5:5:0.4"
            else:
                cx = s.get("cx") or speaker_cx(src, st + sd / 2, hdr)
                zoom = s.get("zoom", 1.0)
                ch = int(h / zoom) // 2 * 2; cw = int(ch * 9 / 16) // 2 * 2
                cy = s.get("cy", h / 2)
                x0 = int(max(0, min(w - cw, cx - cw / 2))); y0 = int(max(0, min(h - ch, cy - ch / 2)))
                vf = pre + f"fps={FPS},crop={cw}:{ch}:{x0}:{y0},scale={VW}:{VH}:flags=lanczos" + (",unsharp=5:5:0.4" if cw < 1400 else "")
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{st:.3f}", "-i", src, "-frames:v", str(n), "-vf", vf + post] + ENC + [p])
            o += sd
        # audio
        raw = run_bytes(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", f, "-vn", "-ac", "2", "-ar", "48000", "-f", "s16le", "-"])
        x = np.frombuffer(raw, np.int16).reshape(-1, 2).astype(np.float32)
        want = int(round(dur * 48000)); x = np.pad(x, ((0, max(0, want - len(x))), (0, 0)))[:want]
        fd = int(0.012 * 48000); ramp = np.linspace(0, 1, fd)[:, None]; x[:fd] *= ramp; x[-fd:] *= ramp[::-1]
        x *= b.get("gain", 1.0); pcs.append(x)
        for text, s0, s1 in b.get("caps", []):
            CAPS.append((t + s0 - a, t + s1 - a, caption(text), b.get("cap_y", cap_y)))
        for (text, size, col, x_, y_, ang, d0, d1) in b.get("titles", []):
            TITLES.append((t + d0, t + (d1 if d1 is not None else dur) - 0.05, strip(text, FONTS[size], COL[col], pad=(34, 10) if size in ("big", "huge") else (30, 14)), x_, y_, ang, text))
        t += dur
        if b.get("transition") and bi < len(beats) - 1:
            TRANS.append((t, b["transition"]))
    total = t
    if end_card:   # silent hold on the last frame with the name strips
        tail = end_card.get("dur", 2.0)
        p = os.path.join(R, "end.mp4"); parts.append(p)
        last = parts[-2]
        run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.05", "-i", last, "-frames:v", "1", "-update", "1", os.path.join(R, "last.png")])
        run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-i", os.path.join(R, "last.png"), "-frames:v", str(int(round(tail * FPS))),
             "-vf", "eq=brightness=-0.12:saturation=0.6,format=yuv420p"] + ENC + [p])
        pcs.append(np.zeros((int(round(tail * 48000)), 2), np.float32))
        for (text, size, col, x_, y_, ang, d0) in end_card["titles"]:
            TITLES.append((total + d0, total + tail + 1, strip(text, FONTS[size], COL[col], pad=(34, 10) if size in ("big", "huge") else (30, 14)), x_, y_, ang, text))
        total += tail
    # merge identical consecutive title strips so they do not blink between beats
    TITLES.sort(key=lambda x: x[0]); merged = []
    for it in TITLES:
        prev = next((m for m in merged if m[6] == it[6] and m[3:6] == it[3:6] and it[0] - m[1] < 0.35), None) if len(it) > 6 else None
        if prev: prev[1] = max(prev[1], it[1])
        else: merged.append(list(it))
    TITLES = [tuple(m[:6]) for m in merged]
    nf = int(round(total * FPS))
    with open(os.path.join(R, "list.txt"), "w") as fl:
        for p in parts: fl.write(f"file '{p}'\n")
    base = os.path.join(R, "base.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(R, "list.txt"), "-c", "copy", base])
    if TRANS:
        prog(0.66, "geçişler")
        base = apply_transitions(base, TRANS, R, ENC)
    y = np.clip(np.concatenate(pcs), -32768, 32767).astype(np.int16)
    wr = os.path.join(R, "a_raw.wav")
    with wave.open(wr, "wb") as w_: w_.setnchannels(2); w_.setsampwidth(2); w_.setframerate(48000); w_.writeframes(y.tobytes())
    aud = os.path.join(R, "a.wav")
    mix_audio(wr, aud, total, fx.get("audio") or {}, fx.get("sfx") or [])
    # clean preview (video + sound, no captions/titles): the editor draws text live on top of it
    prev = os.path.join(workdir, "preview.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-i", base, "-i", aud, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
         "-movflags", "+faststart", "-shortest", prev + ".tmp.mp4"])
    os.replace(prev + ".tmp.mp4", prev)
    od = os.path.join(R, "ov"); os.makedirs(od, exist_ok=True)
    for i in range(nf):
        tt = i / FPS
        c = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
        for a_, b_, s, x_, y_, ang in TITLES:
            q = min(ease((tt - a_) / 0.3), ease((b_ - tt) / 0.25))
            if q > 0: place(c, s, x_, y_, ang, q)
        if i % 60 == 0: prog(0.7 + 0.25 * i / nf, "grafikler")
        for a_, b_, img, cyy in CAPS:
            if a_ <= tt < b_:
                pop = 1 + 0.08 * (1 - ease((tt - a_) / 0.12))
                im = img.resize((int(img.width * pop), int(img.height * pop)), Image.LANCZOS) if pop > 1.001 else img
                c.alpha_composite(im, ((VW - im.width) // 2, cyy - im.height // 2))
        c.save(os.path.join(od, f"o_{i:04d}.png"), compress_level=1)
    run(["ffmpeg", "-v", "error", "-y", "-i", base, "-framerate", str(FPS), "-i", os.path.join(od, "o_%04d.png"), "-i", aud,
         "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[v]", "-map", "[v]", "-map", "2:a",
         "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out])
    import shutil
    shutil.rmtree(od, ignore_errors=True); shutil.rmtree(os.path.join(R, "paper_cache"), ignore_errors=True)
    for f_ in os.listdir(R):
        if f_.endswith(".mp4") and f_ != "base.mp4": os.remove(os.path.join(R, f_))
    return total

def paper_frames(pdir, R, out, n, off, ENC):
    """Vertical paper-cutout name card from a portrait still (frame.jpg + mask_clean.png)."""
    cache = os.path.join(R, "paper_cache")
    if not os.path.isdir(cache):
        os.makedirs(cache)
        frame = Image.open(os.path.join(pdir, "frame.jpg")).convert("RGB").resize((VW, VH), Image.LANCZOS)
        mask = np.array(Image.open(os.path.join(pdir, "mask_clean.png")).convert("L").resize((VW, VH), Image.LANCZOS)).astype(np.float32) / 255
        F = np.array(frame).astype(np.float32)
        grey = F @ np.array([0.299, 0.587, 0.114], np.float32)
        BG = np.clip((F * 0.3 + grey[..., None] * 0.7) * 0.4 + grain(VH, VW, 8), 0, 255)
        ys, xs = np.nonzero(mask > 0.5)
        x0, x1, y0, y1 = xs.min() - 50, xs.max() + 50, ys.min() - 50, ys.max() + 50
        m = mask[y0:y1, x0:x1]
        dist = nd.distance_transform_edt(m < 0.5)
        border = np.maximum(np.clip((16 + nd.gaussian_filter(rng.normal(0, 1, m.shape), 4) * 30 - dist) / 1.5, 0, 1), m)
        paper = np.clip(np.array(PAPER, np.float32) + grain(*m.shape, 6), 0, 255)
        rgb = paper * (1 - m[..., None]) + F[y0:y1, x0:x1] * m[..., None]
        sticker = Image.fromarray(np.dstack([rgb, border * 255]).astype(np.uint8), "RGBA")
        CX, CY = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
        big = ImageFont.truetype(FUT, 170, index=4); mid = ImageFont.truetype(AVC, 74, index=0); sm = ImageFont.truetype(AVC, 62, index=2)
        S = [(strip("BIAR", big, PAPER, pad=(40, 10)), 300, 250, -3.0, 0.30), (strip("Founder of ArfDAO", mid, YEL), 260, 470, 2.0, 0.45),
             (strip("@justbiar", sm, PAPER), 300, 600, -1.5, 0.60), (strip("biar.dev", sm, PAPER), 340, 710, 1.0, 0.70)]
        back = lambda x, k=1.9: (lambda y: 1 + (k + 1) * y ** 3 + k * y ** 2)(min(max(x, 0), 1) - 1)
        for i in range(int(6 * FPS)):          # up to 6 s of card, cached for both halves of the intro
            u = i / FPS; k = ease(u / 0.25)
            img = Image.fromarray((F * (1 - k) + BG * k).astype(np.uint8)).convert("RGBA")
            q = back((u - 0.05) / 0.4)
            if u > 0.05:
                sc = 1 + 0.08 * q
                st = sticker.resize((int(sticker.width * sc), int(sticker.height * sc)), Image.LANCZOS).rotate(-2.5 * min(1, q), Image.BICUBIC, expand=True)
                px, py = int(CX - st.width / 2), int(CY - st.height / 2 + 60 - 30 * min(1, q))
                img.alpha_composite(shadow(st, 16, 0.55), (px + 12, py + 18)); img.alpha_composite(st, (px, py))
            for st_, x_, y_, ang, d in S:
                qq = ease((u - d) / 0.3)
                if qq > 0: place(img, st_, x_, y_, ang, qq)
            img.convert("RGB").save(os.path.join(cache, f"p_{i:04d}.jpg"), quality=94)
    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-start_number", str(off), "-i", os.path.join(cache, "p_%04d.jpg"),
         "-frames:v", str(n), "-vf", "format=yuv420p"] + ENC + [out])

# ---- looks, transitions, audio ---------------------------------------------------------------
FILTERS = {   # name -> ffmpeg video filter (applied after crop/scale, so it costs little)
    "none": "",
    "dogal": "eq=contrast=1.04:saturation=1.05",
    "canli": "eq=contrast=1.08:saturation=1.28,unsharp=5:5:0.3",
    "sicak": "colorbalance=rs=.06:gs=.01:bs=-.06:rm=.04:bm=-.04,eq=saturation=1.08",
    "soguk": "colorbalance=rs=-.05:bs=.07:rm=-.03:bm=.05,eq=saturation=0.98",
    "sinematik": "colorbalance=rs=-.06:gs=-.02:bs=.08:rh=.08:gh=.02:bh=-.06,eq=contrast=1.1:saturation=0.92,vignette=PI/5",
    "soluk": "curves=all='0/0.06 0.5/0.52 1/0.94',eq=saturation=0.82",
    "siyahbeyaz": "hue=s=0,eq=contrast=1.12",
    "gece": "eq=brightness=-0.04:contrast=1.12:saturation=0.85,colorbalance=bs=.08:bm=.04",
}
def color_filter(name, lut=None):
    parts = []
    if lut and os.path.exists(lut):
        parts.append("lut3d=file='" + lut.replace("'", r"\'") + "'")
    f = FILTERS.get(name or "none", "")
    if f: parts.append(f)
    return ",".join(parts)

BUILTIN_TRANSITIONS = ("flas", "karart", "zoom", "bulanik", "kaydir")
def apply_transitions(base, TRANS, R, ENC):
    """Effects centred on beat boundaries. They never move a cut, so lips stay in sync with audio."""
    inputs, chains, last, k = ["-i", base], [], "[0:v]", 1
    zoom_terms = []
    for i, (T, tr) in enumerate(TRANS):
        name, d = tr.get("name", "flas"), float(tr.get("dur", 0.4))
        a0, a1 = max(0, T - d / 2), T + d / 2
        if name in ("flas", "karart"):
            col = "white" if name == "flas" else "black"
            chains.append(f"color=c={col}:s={VW}x{VH}:r={FPS}:d={d:.3f},format=rgba,fade=t=in:st=0:d={d/2:.3f}:alpha=1,"
                          f"fade=t=out:st={d/2:.3f}:d={d/2:.3f}:alpha=1,setpts=PTS+{a0:.3f}/TB[c{i}]")
            chains.append(f"{last}[c{i}]overlay=eof_action=pass:format=auto[v{i}]"); last = f"[v{i}]"
        elif name == "bulanik":
            chains.append(f"{last}gblur=sigma=28:enable='between(t,{a0:.3f},{a1:.3f})'[v{i}]"); last = f"[v{i}]"
        elif name == "zoom":
            zoom_terms.append(f"0.18*max(0,1-abs(t-{T:.3f})/{d/2:.3f})")
        elif name == "kaydir":     # whip: strong sideways motion blur across the cut
            chains.append(f"{last}avgblur=sizeX=70:sizeY=1:enable='between(t,{a0:.3f},{a1:.3f})'[v{i}]"); last = f"[v{i}]"
        elif tr.get("asset") and os.path.exists(tr["asset"]):
            inputs += ["-i", tr["asset"]]
            alpha = "rgba" in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=pix_fmt", "-of", "csv=p=0", tr["asset"]],
                                             capture_output=True, text=True).stdout
            key = "" if alpha else ",colorkey=black:0.12:0.25"
            ad = float(probe_dur(tr["asset"]) or d); start = T - min(ad, d) / 2 if tr.get("dur") else T - ad / 2
            chains.append(f"[{k}:v]scale={VW}:{VH}:force_original_aspect_ratio=increase,crop={VW}:{VH},fps={FPS},format=rgba{key},setpts=PTS+{max(0, start):.3f}/TB[a{i}]")
            chains.append(f"{last}[a{i}]overlay=eof_action=pass:format=auto[v{i}]"); last = f"[v{i}]"; k += 1
    if zoom_terms:
        z = "+".join(zoom_terms)
        chains.append(f"{last}scale=w='trunc({VW}*(1+{z})/2)*2':h='trunc({VH}*(1+{z})/2)*2':eval=frame,crop={VW}:{VH}[vz]"); last = "[vz]"
    if not chains: return base
    out = os.path.join(R, "base_fx.mp4")
    run(["ffmpeg", "-v", "error", "-y"] + inputs + ["-filter_complex", ";".join(chains) + f";{last}format=yuv420p[vout]", "-map", "[vout]"] + ENC + [out])
    return out

def probe_dur(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout.strip()
    try: return float(r)
    except ValueError: return None

def mix_audio(voice, out, total, A, sfx):
    """voice clean-up, optional music bed that ducks under the voice, sound effects, loudness."""
    lufs = float(A.get("lufs", -14)); chain = "highpass=f=80"
    if A.get("denoise"): chain += ",afftdn=nf=-25"
    if A.get("eq") == "sicak": chain += ",equalizer=f=180:t=q:w=1:g=2,equalizer=f=6500:t=q:w=1:g=-1.5"
    elif A.get("eq") == "net": chain += ",equalizer=f=250:t=q:w=1:g=-2,equalizer=f=4500:t=q:w=1.2:g=2.5"
    chain += ",acompressor=threshold=-20dB:ratio=3:attack=5:release=120"
    ins, g, mixes = ["-i", voice], [f"[0:a]{chain},asplit=2[vo][sc]"], ["[vo]"]
    music = A.get("music") or {}
    n = 1
    if music.get("path") and os.path.exists(music["path"]):
        ins += ["-stream_loop", "-1", "-i", music["path"]]
        mg = float(music.get("gain", 0.18))
        g.append(f"[{n}:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,volume={mg:.3f},"
                 f"afade=t=in:d=0.8,afade=t=out:st={max(0, total - 1.5):.3f}:d=1.5[mu]")
        if music.get("duck", True):
            g.append("[mu][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[mud]"); mixes.append("[mud]")
        else:
            mixes.append("[mu]"); g.append("[sc]anullsink")
        n += 1
    else:
        g.append("[sc]anullsink")
    for j, e in enumerate(sfx):
        if not os.path.exists(e.get("path", "")): continue
        ins += ["-i", e["path"]]; ms = int(max(0, float(e.get("t", 0))) * 1000)
        g.append(f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={float(e.get('gain', 0.8)):.3f},adelay={ms}|{ms}[s{j}]"); mixes.append(f"[s{j}]"); n += 1
    g.append(f"{''.join(mixes)}amix=inputs={len(mixes)}:normalize=0:duration=first,loudnorm=I={lufs}:TP=-1.2:LRA=9[out]")
    run(["ffmpeg", "-v", "error", "-y"] + ins + ["-filter_complex", ";".join(g), "-map", "[out]", "-ar", "48000", "-t", f"{total:.3f}", out])

def run_bytes(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode:
        raise SystemExit(r.stderr.decode()[-800:])
    return r.stdout

def tallest_person(src, t, hdr):
    """Bounding box (x0, y0, x1, y1 in source pixels) of the tallest detected person."""
    import Quartz, Vision
    from Foundation import NSURL
    w, h, _ = probe(src)
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tp.jpg")
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf",
         (TM + "," if hdr else "") + "scale=1920:-2,format=yuvj420p", p])
    img = Quartz.CGImageSourceCreateImageAtIndex(Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(p), None), 0, None)
    req = Vision.VNDetectHumanRectanglesRequest.alloc().initWithCompletionHandler_(None)
    req.setUpperBodyOnly_(False)
    Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None).performRequests_error_([req], None)
    best = None
    for o in req.results() or []:
        b = o.boundingBox()
        if best is None or b.size.height > best.size.height:
            best = b
    if best is None:
        return None
    return (best.origin.x * w, (1 - best.origin.y - best.size.height) * h, (best.origin.x + best.size.width) * w, (1 - best.origin.y) * h)
