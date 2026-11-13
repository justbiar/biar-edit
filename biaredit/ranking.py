"""Ranking shorts ("5'ten 1'e"): short quoted clips, our ranking board and commentary on top.

  python -I biaredit/ranking.py projects/rank01        renders projects/rank01/ranking.json

ranking.json
  {"type": "ranking", "name": ..., "kicker": "TARİHİN EN EFSANE", "title": "SAHNE DEMOLARI",
   "intro": "5'ten 1'e", "outro": ["Sence 1 numara hangisi olmalıydı?", "Yorumlara yaz"],
   "output": "/path/out.mp4",
   "items": [ {"rank": 5, "label": ..., "sub": ..., "comment": ..., "credit": ..., "url": ...,
               "parts": [[a, b], ...]}, ... ]}        items in the order they are shown (5 -> 1)

Clips stay short and every frame carries our own board, ranking and comment, which is what makes
this commentary rather than a re-upload. Sources are cached, so re-renders do not download again.
"""
import json, math, os, re, shutil, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.environ["PATH"] = "/opt/homebrew/opt/ffmpeg-full/bin:/opt/homebrew/bin:" + os.environ.get("PATH", "")
import settings as S, style as STY


W, H, FPS = 1080, 1920, 30
BOX = (40, 400, 1000, 600)              # x, y, w, h of the clip window
FUT = "/System/Library/Fonts/Supplemental/Futura.ttc"
AVC = "/System/Library/Fonts/Avenir Next Condensed.ttc"
F = lambda path, size, idx: ImageFont.truetype(path, size, index=idx)
# Short-form caption convention: white type, heavy black outline, one yellow accent.
F_KICK, F_TITLE = F(FUT, 54, 4), F(FUT, 132, 4)
F_NUM, F_LABEL, F_SUB, F_COMM = F(FUT, 270, 4), F(FUT, 84, 4), F(AVC, 44, 0), F(AVC, 50, 0)
F_BOARD_N, F_BOARD_T, F_SMALL = F(FUT, 50, 4), F(AVC, 46, 0), F(AVC, 30, 2)
YELLOW, WHITE, BLACK = (255, 214, 10), (255, 255, 255), (0, 0, 0)
DIM = (255, 255, 255, 110)
SFX = os.path.join(ROOT, "media", "sfx")
STROKE = 7
ST = STY.merge(STY.DEFAULT, {})           # edit style in use (set per render by use_style)

def use_style(st):
    global ST, YELLOW
    ST = st; YELLOW = tuple(STY.ACCENTS[st["text"]["accent"]]["rgb"])

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise RuntimeError((r.stderr or r.stdout)[-1500:])
    return r.stdout

STATUS = None
def log(step, pct):
    print(json.dumps({"step": step, "pct": pct}, ensure_ascii=False), flush=True)
    if STATUS: json.dump({"step": step, "pct": pct}, open(STATUS, "w"), ensure_ascii=False)

def validate(spec):
    """Problems shown in the editor. error = blocks the render."""
    out, items = [], spec.get("items") or []
    if not items: out.append({"level": "error", "msg": "En az bir sıra ekle."})
    for it in items:
        tag = f"#{it.get('rank', '?')}"
        if not (it.get("url") or it.get("file")): out.append({"level": "error", "msg": f"{tag}: bağlantı yok."})
        parts = it.get("parts") or []
        if not parts: out.append({"level": "error", "msg": f"{tag}: kesit yok (ör. 12.5-20)."})
        for a, b in parts:
            if b <= a: out.append({"level": "error", "msg": f"{tag}: kesit bitişi başlangıçtan önce ({a}-{b})."})
        tot = sum(b - a for a, b in parts)
        if tot > 20: out.append({"level": "warn", "msg": f"{tag}: {tot:.0f} sn alıntı uzun. Alıntıyı kısa tutmak (6-15 sn) hem tempoyu hem alıntı hakkını korur."})
        if not it.get("comment"): out.append({"level": "warn", "msg": f"{tag}: yorum yok. Yorum, videoyu yeniden yükleme değil yorum içeriği yapan şey."})
        if not it.get("credit"): out.append({"level": "warn", "msg": f"{tag}: kaynak belirtilmemiş."})
    ranks = [it.get("rank") for it in items]
    if len(set(ranks)) != len(ranks): out.append({"level": "error", "msg": "Aynı sıra numarası iki kez kullanılmış."})
    return out

# ---------- sources ----------
def cache_dir():
    d = os.path.join(S.load().get("download_dir") or os.path.expanduser("~/Movies/biar-edit indirilenler"), "_siralama")
    os.makedirs(d, exist_ok=True); return d

def vid_id(url):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|video/)([\w-]{6,})", url)
    return m.group(1) if m else re.sub(r"\W+", "_", url)[-40:]

def source(item):
    """Returns (path, offset): parts are in original-video seconds; offset is where the file starts."""
    if item.get("file"): return item["file"], 0.0
    vid, d = vid_id(item["url"]), cache_dir()
    full = os.path.join(d, vid + ".mp4")
    if os.path.exists(full): return full, 0.0
    a = max(0, math.floor(min(p[0] for p in item["parts"])) - 2); b = math.ceil(max(p[1] for p in item["parts"])) + 2
    sec = os.path.join(d, f"{vid}_{a}-{b}.mp4")
    if os.path.exists(sec): return sec, float(a)
    fmt = "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080]+ba/b"
    dur = float(run(["yt-dlp", "--no-warnings", "--print", "duration", item["url"]]).strip().splitlines()[-1] or 0)
    if dur and dur <= 600:
        run(["yt-dlp", "-q", "--no-warnings", "-f", fmt, "--merge-output-format", "mp4", "-o", full, item["url"]]); return full, 0.0
    run(["yt-dlp", "-q", "--no-warnings", "-f", fmt, "--download-sections", f"*{a}-{b}", "--force-keyframes-at-cuts",
         "--merge-output-format", "mp4", "-o", sec, item["url"]])
    return sec, float(a)


# ---------- graphics ----------
def text_w(d, s, f, stroke=0): l, t, r, b = d.textbbox((0, 0), s, font=f, stroke_width=stroke); return r - l

def fit(d, s, f_path, size, idx, maxw, stroke=0):
    while size > 20:
        f = F(f_path, size, idx)
        if text_w(d, s, f, stroke) <= maxw: return f
        size -= 4
    return F(f_path, 20, idx)

LANG = "tr"
TEXT = {"tr": {"source": "Kaynak", "intro": "5'ten 1'e", "outro": ["Sence 1 numara hangisi olmalıydı?", "Yorumlara yaz"]},
        "en": {"source": "Source", "intro": "5 to 1", "outro": ["Which one deserved #1?", "Tell us in the comments"]}}
def T(key): return TEXT.get(LANG, TEXT["tr"])[key]
def tr_upper(s): return s.replace("i", "İ").replace("ı", "I").upper() if LANG == "tr" else s.upper()

def say(d, xy, s, f, fill=WHITE, stroke=STROKE):
    d.text(xy, s, font=f, fill=fill, stroke_width=stroke, stroke_fill=BLACK)

def shadow(img, radius=16, alpha=170, off=(0, 6), color=(0, 0, 0)):
    a = img.split()[3].filter(ImageFilter.GaussianBlur(radius))
    sh = Image.new("RGBA", img.size, (*color, 0)); sh.putalpha(a.point(lambda v: v * alpha // 255))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0)); out.paste(sh, off, sh)
    return Image.alpha_composite(out, img)

def spans(s):
    """'*vurgu*' marks the accent words: [(word, accent?), ...]."""
    out, on = [], False
    for k, part in enumerate(s.split("*")):
        on = k % 2 == 1
        for w in part.split():
            if out and not any(ch.isalnum() for ch in w): out[-1] = (out[-1][0] + w, out[-1][1])   # "wood*." keeps the dot attached
            else: out.append((w, on))
    return out

def wrap_spans(d, toks, f, maxw):
    lines, cur = [], []
    for w, on in toks:
        t = " ".join(x for x, _ in cur + [(w, on)])
        if cur and text_w(d, t, f, STROKE) > maxw: lines.append(cur); cur = [(w, on)]
        else: cur.append((w, on))
    return lines + ([cur] if cur else [])

def say_spans(d, x, y, line, f):
    sp = text_w(d, " ", f)
    for w, on in line:
        say(d, (x, y), w, f, YELLOW if on else WHITE, 6); x += text_w(d, w, f) + sp

def header(d, spec):
    kick = spec.get("kicker", "")
    say(d, ((W - text_w(d, kick, F_KICK, 5)) // 2, 106), kick, F_KICK, YELLOW, 5)
    f = fit(d, spec["title"], FUT, 132, 4, W - 70, STROKE)
    say(d, ((W - text_w(d, spec["title"], f, STROKE)) // 2, 166), spec["title"], f)

def board(d, items, upto, y0=1492):
    """Ranking board: rows 1..N top-down, revealed rows filled, the current one on a yellow bar."""
    by_rank = {it["rank"]: it for it in items}; shown = {it["rank"] for it in items[:upto + 1]}
    cur = items[upto]["rank"] if upto < len(items) else None
    rh = 66
    for i, r in enumerate(sorted(by_rank)):
        y = y0 + i * rh
        if r == cur:
            d.rounded_rectangle((36, y - 6, W - 36, y + rh - 10), 14, fill=(*YELLOW, 255))
            d.text((62, y), f"{r}", font=F_BOARD_N, fill=BLACK)
            d.text((130, y + 5), by_rank[r]["label"], font=F_BOARD_T, fill=BLACK)
        elif r in shown:
            say(d, (62, y), f"{r}", F_BOARD_N, YELLOW if r == 1 else WHITE, 5)
            say(d, (130, y + 5), by_rank[r]["label"], F_BOARD_T, WHITE, 5)
        else:
            say(d, (62, y), f"{r}", F_BOARD_N, DIM, 4); say(d, (130, y + 5), "?", F_BOARD_T, DIM, 4)

def dim_layer(alpha=105):
    """Darkens the blurred background so text stays readable on bright clips (clip window left clear)."""
    m = Image.new("RGBA", (W, H), (0, 0, 0, alpha)); x, y, w, h = BOX
    ImageDraw.Draw(m).rounded_rectangle((x, y, x + w - 1, y + h - 1), 34, fill=(0, 0, 0, 0)); return m

def card(spec, i):
    """Returns (base, number, comment) overlays for item i; number and comment animate separately."""
    items = spec["items"]; it = items[i]; x, y, w, h = BOX
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(base)
    header(d, spec)
    d.rounded_rectangle((x - 5, y - 5, x + w + 4, y + h + 4), 38, outline=(*YELLOW, 255) if it["rank"] == 1 else (255, 255, 255, 200), width=5)
    if it.get("credit"):
        c = T("source") + ": " + it["credit"]; say(d, (x + w - text_w(d, c, F_SMALL, 3), y + h + 14), c, F_SMALL, (255, 255, 255, 200), 3)
    num = f"#{it['rank']}"; nw = text_w(d, num, F_NUM, 10)
    nx = 40 + nw + 26; maxw = W - 40 - nx
    fl = fit(d, it["label"], FUT, 84, 4, maxw, STROKE)
    say(d, (nx, 1086), it["label"], fl)
    if it.get("sub"): say(d, (nx, 1192), it["sub"], F_SUB, (255, 255, 255, 230), 5)
    board(d, items, i)
    # number as its own layer so it can pop in
    nimg = Image.new("RGBA", (nw + 80, 340), (0, 0, 0, 0)); nd = ImageDraw.Draw(nimg)
    nd.text((40, 20), num, font=F_NUM, fill=YELLOW, stroke_width=10, stroke_fill=BLACK)
    # comment as its own layer so it can slide in
    cimg = Image.new("RGBA", (W, 200), (0, 0, 0, 0)); cd = ImageDraw.Draw(cimg)
    for k, ln in enumerate(wrap_spans(cd, spans(it.get("comment", "")), F_COMM, W - 80)[:3]):
        say_spans(cd, 40, 6 + k * 62, ln, F_COMM)
    nl = shadow(nimg, 10, 160, (0, 5))
    if ST["text"]["glow"]: nl = shadow(shadow(nl, 34, 255, (0, 0), YELLOW), 12, 255, (0, 0), YELLOW)
    return Image.alpha_composite(dim_layer(), shadow(base)), nl, shadow(cimg, 10, 160, (0, 4))

NUM_XY, COMM_XY = (0, 1010), (0, 1290)      # where the number / comment layers sit (top-left)

def intro_card(spec):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    kick = spec.get("kicker", ""); fk = fit(d, kick, FUT, 78, 4, W - 80, 6)
    say(d, ((W - text_w(d, kick, fk, 6)) // 2, 630), kick, fk, YELLOW, 6)
    f = fit(d, spec["title"], FUT, 170, 4, W - 60, 9)
    say(d, ((W - text_w(d, spec["title"], f, 9)) // 2, 724), spec["title"], f, WHITE, 9)
    s = tr_upper(spec.get("intro") or (ST["cta"]["intro"] if spec.get("style_version") else T("intro"))); fi = F(FUT, 64, 4)
    tw = text_w(d, s, fi); d.rounded_rectangle(((W - tw) // 2 - 36, 960, (W + tw) // 2 + 36, 1056), 22, fill=(*YELLOW, 255))
    d.text(((W - tw) // 2, 966), s, font=fi, fill=BLACK)
    return shadow(im)

def outro_card(spec):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    header(d, spec); board(d, spec["items"], len(spec["items"]), y0=520)
    q = spec.get("outro") or ([ST["cta"]["question"], ST["cta"]["button"]] if spec.get("style_version") else T("outro"))
    qq = tr_upper(q[0]); fq = fit(d, qq, FUT, 80, 4, W - 70, STROKE)
    say(d, ((W - text_w(d, qq, fq, STROKE)) // 2, 1080), qq, fq)
    if len(q) > 1:
        t = tr_upper(q[1]); fb = F(FUT, 56, 4); tw = text_w(d, t, fb)
        d.rounded_rectangle(((W - tw) // 2 - 34, 1210, (W + tw) // 2 + 34, 1296), 22, fill=(*YELLOW, 255))
        d.text(((W - tw) // 2, 1218), t, font=fb, fill=BLACK)
    return Image.alpha_composite(dim_layer(80), shadow(im))

def mask(path):
    x, y, w, h = BOX; m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), 34, fill=255); m.save(path)

# ---------- video ----------
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]

def cut(src, off, parts, out, focus_y=None):
    """Concatenate the parts of one source into a clean 30 fps clip.
    focus_y (0 top .. 1 bottom): which band of a tall (phone) video stays in the 16:9 window; default 0.3 for vertical sources."""
    ins, fc = [], []
    if focus_y is None:
        wh = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", src]).strip().split(",")
        focus_y = 0.3 if len(wh) == 2 and int(wh[1]) > int(wh[0]) else 0.5
    for k, (a, b) in enumerate(parts):
        ins += ["-ss", f"{a - off:.3f}", "-t", f"{b - a:.3f}", "-i", src]
        fc.append(f"[{k}:v]fps={FPS},scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080:(iw-ow)/2:(ih-oh)*{focus_y},setsar=1,"
                  f"fade=t=in:st=0:d=0.08,fade=t=out:st={b - a - 0.08:.3f}:d=0.08[v{k}];"
                  f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.04,afade=t=out:st={b - a - 0.06:.3f}:d=0.06[a{k}]")
    n = len(parts)
    fc.append("".join(f"[v{k}][a{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=1[v][a]")
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", *ENC, out])

def dur(p): return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).strip())


def sfx_mix(base_label, cues, first_input):
    """cues: [(name, at_seconds, volume)] -> (extra -i args, filter text ending in [a])."""
    ins, fc, labs = [], [], []
    for k, (name, at, vol) in enumerate(cues):
        ins += ["-i", os.path.join(SFX, name + ".wav")]; j = first_input + k
        fc.append(f"[{j}:a]aresample=48000,aformat=channel_layouts=stereo,volume={vol},adelay={int(at * 1000)}|{int(at * 1000)}[s{k}]"); labs.append(f"[s{k}]")
    if not cues: return ins, f"[{base_label}]anull[a]"
    fc.append(f"[{base_label}]{''.join(labs)}amix=inputs={len(cues) + 1}:duration=first:normalize=0[a]")
    return ins, ";".join(fc)

POP = "if(lt(t,0.1),0.01,if(lt(t,0.24),0.3+(t-0.1)/0.14*0.92,if(lt(t,0.36),1.22-(t-0.24)/0.12*0.22,1)))"

def look(): f = STY.FILTERS[ST["filter"]]["ff"]; return f + "," if f else ""

def motion(w, h, hits):
    """Camera shake / zoom punch on the clip window, driven by the hit times (seconds into the segment)."""
    e = ST["effects"]; sh = STY.SHAKE[e["shake"]]; punch = 0.08 if e["zoom_punch"] else 0
    if not sh["amp"] and not punch: return ""
    env = "+".join(f"between(it,{t:.2f},{t + 0.45:.2f})*exp(-(it-{t:.2f})*9)" for t in hits) or "0"
    z0 = 1 + 2.2 * (sh["amp"] + sh["base"]) / w
    dx = f"({sh['amp']}*({env})*sin(it*83)+{sh['base']}*sin(it*5.3))"
    dy = f"({sh['amp']}*({env})*cos(it*71)+{sh['base']}*sin(it*4.1+1))"
    cl = lambda c, d: f"max(0,min({c}-{c}/zoom,({c}-{c}/zoom)/2+{d}))"
    return f",zoompan=z='{z0:.4f}+{punch}*({env})':x='{cl('iw', dx)}':y='{cl('ih', dy)}':d=1:s={w}x{h}:fps={FPS}"

def compose(clip, layers, mk, out, cues=(), hits=(0.1,)):
    d = dur(clip); x, y, w, h = BOX; base, num, comm = layers
    nwid, nhei = Image.open(num).size; cx, cy = NUM_XY[0] + nwid / 2, NUM_XY[1] + nhei / 2
    fl = ST["transition"]["flash"]; e = ST["effects"]
    flash = {"white": ",fade=t=in:st=0:d=0.16:color=white", "black": ",fade=t=in:st=0:d=0.12:color=black"}.get(fl, "")
    fc = (f"[0:v]{look()}split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=28:3,eq=brightness=-0.32:saturation=0.75[bg];"
          f"[b]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}{motion(w, h, hits)}{',vignette=PI/4' if e['vignette'] else ''},format=rgba[c];[2:v]format=gray[m];[c][m]alphamerge[cr];"
          f"[bg][cr]overlay={x}:{y}[v1];[1:v]format=rgba,fade=t=in:st=0:d=0.2:alpha=1[ov];[v1][ov]overlay=0:0[v2];"
          f"[3:v]format=rgba,scale=w='max(2,iw*{POP})':h='max(2,ih*{POP})':eval=frame[n];"
          f"[v2][n]overlay=x='{cx}-overlay_w/2':y='{cy}-overlay_h/2':eval=frame[v3];"
          f"[4:v]format=rgba,fade=t=in:st=0.42:d=0.25:alpha=1[cm];"
          f"[v3][cm]overlay=x={COMM_XY[0]}:y='{COMM_XY[1]}+max(0,36*(1-(t-0.42)/0.25))':eval=frame"
          + (",noise=alls=9:allf=t" if e["grain"] else "") + flash + ",format=yuv420p[v];"
          "[0:a]loudnorm=I=-15:TP=-1.5:LRA=9[ca]")
    loop = lambda p: ["-loop", "1", "-t", f"{d:.3f}", "-i", p]
    ins = ["-i", clip, *loop(base), *loop(mk), *loop(num), *loop(comm)]
    sins, sfc = sfx_mix("ca", list(cues), 5)
    run(["ffmpeg", "-v", "error", "-y", *ins, *sins, "-filter_complex", fc + ";" + sfc, "-map", "[v]", "-map", "[a]", "-t", f"{d:.3f}", *ENC, out])

def still(bg_clip, at, overlay, secs, out, cues):
    """Intro/outro: frozen, blurred frame from a clip with a card on top (no speech, so the music leads)."""
    fc = (f"[0:v]{look()}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=34:3,eq=brightness=-0.42:saturation=0.7,"
          f"loop=loop=-1:size=1,trim=duration={secs},setpts=N/{FPS}/TB[bg];[1:v]format=rgba,"
          f"scale=w='iw*min(1,0.86+t*0.6)':h='ih*min(1,0.86+t*0.6)':eval=frame,fade=t=in:st=0:d=0.25:alpha=1[ov];"
          f"[bg][ov]overlay=x='(main_w-overlay_w)/2':y='(main_h-overlay_h)/2':eval=frame,fade=t=out:st={secs - 0.15}:d=0.15,format=yuv420p[v];"
          f"anullsrc=r=48000:cl=stereo,atrim=duration={secs}[sil]")
    sins, sfc = sfx_mix("sil", list(cues), 2)
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", bg_clip, "-loop", "1", "-t", f"{secs}", "-i", overlay, *sins,
         "-filter_complex", fc + ";" + sfc, "-map", "[v]", "-map", "[a]", "-frames:v", str(int(secs * FPS)), *ENC, out])

def find_drop(path, after=20.0):
    """Where the beat comes back after a breakdown (first loud moment after >= 4 s of quiet), or None."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "4000", "-f", "f32le", "-"], capture_output=True).stdout
    a = np.frombuffer(raw, np.float32); n = 1000                       # 0.25 s windows
    e = np.array([np.sqrt(np.mean(a[i:i + n] ** 2)) for i in range(0, len(a) - n, n)])
    if len(e) < 80: return None
    sm = np.convolve(e, np.ones(8) / 8, "same"); top = np.percentile(sm, 90)
    quiet = 0
    for i in range(len(sm)):
        if sm[i] < 0.45 * top: quiet += 1; continue
        if quiet >= 16 and i / 4 >= after and sm[i] > 0.7 * top:
            j = i - 4
            while j < i + 8 and e[j] < 0.7 * top: j += 1                 # first loud hit near the rise
            return float(j / 4)
        if sm[i] > 0.7 * top: quiet = 0
    return None

def music_bed(video, music, start, total, out, gain_db=-17, intro=0.0, outro_at=None):
    """Music under the whole short: ducked under speech, a bit louder in intro and outro, faded at both ends."""
    up = f"if(lt(t,{intro}),1.8,if(gt(t,{outro_at or total}),1.8,1))"
    fc = (f"[1:a]atrim=start={start}:duration={total},asetpts=N/SR/TB,aresample=48000,aformat=channel_layouts=stereo,"
          f"volume={gain_db}dB,volume='{up}':eval=frame,afade=t=in:d=0.4,afade=t=out:st={total - 1.2}:d=1.2[m];"
          f"[0:a]asplit[sp][sc];[m][sc]sidechaincompress=threshold=0.04:ratio=6:attack=15:release=450:makeup=1[md];"
          f"[sp][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=10,alimiter=limit=0.84:level=false[a]")
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", music, "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])

def sfx_scale(spec, cues):
    if spec.get("sfx_on") is False: return []
    g = float(spec.get("sfx_gain", ST["sfx_gain"])); return [(n, at, round(v * g, 3)) for n, at, v in cues]

def events(clip):
    """Where things happen in a clip: [(t, strength)] from audio onsets + big picture changes (0..1)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", clip, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
    a = np.frombuffer(raw, np.float32); n = 320                         # 20 ms frames
    if len(a) < n * 10: return []
    fr = a[: len(a) // n * n].reshape(-1, n)
    sp = np.abs(np.fft.rfft(fr * np.hanning(n), axis=1))
    flux = np.r_[0, np.maximum(0, np.diff(np.log1p(sp * 50), axis=0)).sum(1)]
    loud = np.sqrt((fr ** 2).mean(1)); loud = loud / (loud.max() + 1e-9)
    au = flux / (flux.max() + 1e-9) * (0.4 + 0.6 * loud)
    vraw = subprocess.run(["ffmpeg", "-v", "error", "-i", clip, "-vf", "fps=50,scale=64:36,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    v = np.frombuffer(vraw, np.uint8).reshape(-1, 36, 64).astype(np.float32)
    vd = np.r_[0, np.abs(np.diff(v, axis=0)).mean((1, 2))] if len(v) > 1 else np.zeros(1)
    m = min(len(au), len(vd)); sc = au[:m] + 0.6 * vd[:m] / (vd[:m].max() + 1e-9)
    sc = np.convolve(sc, np.ones(3) / 3, "same"); out = []
    for i in np.argsort(-sc):
        t = i * 0.02
        if sc[i] < 0.25 * sc.max(): break
        if all(abs(t - u) > 0.6 for u, _ in out): out.append((round(t, 2), float(sc[i] / sc.max())))
        if len(out) >= 12: break
    return sorted(out)

def rank_cues(it, dd, before_one, ev=None):
    """Sounds for one rank from the style, plus the hit times that drive shake / zoom punch.
    ev: events(clip); moment sounds snap to the real hit, and with moment.auto the strongest one gets a sound."""
    tr, hi = ST["transition"], ST["hit"]
    cm = ST["comment"]; mo = ST["moment"]; ev = ev or []
    cues = [(tr["sound"], 0.0, tr["vol"]), (hi["sound"], 0.1, hi["vol"]), (cm["slide"], 0.42, 0.5), (cm["tick"], 0.75, 0.6)]
    if it["rank"] == 1: cues += [(s, 0.1 + 0.02 * k, 0.75) for k, s in enumerate(ST["number1"]["sounds"])]
    hits = [0.1]; used = []
    snap = lambda t: max(((e, s) for e, s in ev if abs(e - t) <= 0.8), key=lambda x: x[1], default=(t, 0))[0]
    for m in it.get("sfx") or []:                                      # moment effects: [name, seconds into this rank, volume]
        name, at = m[0], float(m[1]); vol = float(m[2]) if len(m) > 2 else 0.8
        if mo["snap"]: at = snap(at)
        if os.path.exists(os.path.join(SFX, name + ".wav")) and at < dd:
            cues.append((name, at, vol)); used.append(at)
            if STY.is_hit(name): hits.append(at)
    if mo["auto"] and not used:                                       # nothing picked: put a hit on the clip's biggest moment
        big = [(e, s) for e, s in ev if 1.2 <= e <= dd - 0.8]
        if big:
            e = max(big, key=lambda x: x[1])[0]; cues.append((mo["sound"], e, mo["vol"])); hits.append(e)
    if before_one and ST["number1"]["buildup"]:
        for k, s in enumerate(ST["number1"]["buildup_sounds"]):
            sd = sfx_len(s); cues.append((s, max(0, dd - min(sd, 3.0) - 0.05), 0.55 if k == 0 else 0.45))
    return [c for c in cues if c[0]], hits

def sfx_len(name):
    try: return dur(os.path.join(SFX, name + ".wav"))
    except Exception: return 1.6

def cleanup_sources(items):
    """Setting "cleanup_sources": after a finished render, delete the downloaded source videos of this ranking.
    Only files inside the download cache (_siralama) are touched; a rank's own "file" is never deleted.
    Re-rendering later simply downloads them again."""
    d = os.path.realpath(cache_dir()); gone = []
    for it in items:
        if it.get("file") or not it.get("url"): continue
        vid = vid_id(it["url"])
        for f in [os.path.join(d, vid + ".mp4")] + [os.path.join(d, x) for x in os.listdir(d) if x.startswith(vid + "_") and x.endswith(".mp4")]:
            f = os.path.realpath(f)
            if os.path.dirname(f) == d and os.path.isfile(f):
                gone.append({"file": os.path.basename(f), "mb": round(os.path.getsize(f) / 1e6, 1)}); os.remove(f)
    return gone

def preview(d, st, out, i=None, secs=4.5):
    """A few seconds of one rank of project d rendered with style st (for the Stil screen)."""
    global LANG
    spec = json.load(open(os.path.join(d, "ranking.json"))); LANG = spec.get("lang", "tr"); use_style(st)
    spec = {**spec, "style_version": spec.get("style_version") or 1}
    work = os.path.join(d, "work"); items = spec["items"]
    i = len(items) - 1 if i is None else i
    clip = os.path.join(work, f"clip{i}.mp4")
    if not os.path.exists(clip): raise RuntimeError("Önizleme için önce bu projeyi bir kez render et.")
    tmp = os.path.join(work, "_pv"); os.makedirs(tmp, exist_ok=True)
    short = os.path.join(tmp, "clip.mp4"); run(["ffmpeg", "-v", "error", "-y", "-i", clip, "-t", str(secs), *ENC, short])
    paths = [os.path.join(tmp, f"card{s}.png") for s in ("", "_num", "_comm")]
    for im, p in zip(card(spec, i), paths): im.save(p)
    mk = os.path.join(tmp, "mask.png"); mask(mk)
    cues, hits = rank_cues(items[i], secs, False, events(short) if ST["moment"]["auto"] or ST["moment"]["snap"] else [])
    compose(short, paths, mk, out, sfx_scale(spec, cues), hits + [1.6, 3.0] if ST["effects"]["shake"] != "off" or ST["effects"]["zoom_punch"] else hits)
    return out

def render(d):
    global STATUS, LANG
    spec = json.load(open(os.path.join(d, "ranking.json"))); LANG = spec.get("lang", "tr")
    use_style(STY.merge(STY.get(spec.get("style_version")), spec.get("style")))
    work = os.path.join(d, "work"); os.makedirs(work, exist_ok=True); STATUS = os.path.join(work, "status.json")
    items = spec["items"]; n = len(items); segs = []
    mk = os.path.join(work, "mask.png"); mask(mk)
    for i, it in enumerate(items):
        log(f"#{it['rank']} kaynak indiriliyor", 5 + 65 * i // n)
        src, off = source(it)
        clip = os.path.join(work, f"clip{i}.mp4"); cut(src, off, it["parts"], clip, it.get("focus_y"))
        paths = [os.path.join(work, f"card{i}{s}.png") for s in ("", "_num", "_comm")]
        for im, p in zip(card(spec, i), paths): im.save(p)
        log(f"#{it['rank']} kurgulanıyor", 5 + 65 * i // n + 30 // n)
        dd = dur(clip)
        ev = events(clip) if ST["moment"]["auto"] or ST["moment"]["snap"] else []
        cues, hits = rank_cues(it, dd, i + 1 < n and items[i + 1]["rank"] == 1, ev)
        seg = os.path.join(work, f"seg{i}.mp4"); compose(clip, paths, mk, seg, sfx_scale(spec, cues), hits); segs.append(seg)
    log("giriş ve kapanış", 75)
    intro_card(spec).save(os.path.join(work, "intro.png")); outro_card(spec).save(os.path.join(work, "outro.png"))
    intro, outro = os.path.join(work, "intro.mp4"), os.path.join(work, "outro.mp4")
    isec, osec = float(spec.get("intro_secs", 1.8)), float(spec.get("outro_secs", 3.0))
    still(os.path.join(work, "clip0.mp4"), 0.5, os.path.join(work, "intro.png"), isec, intro, sfx_scale(spec, [(s, 0.03 * k, 0.6) for k, s in enumerate(ST["intro_outro"]["intro"])]))
    still(os.path.join(work, f"clip{n - 1}.mp4"), 1.0, os.path.join(work, "outro.png"), osec, outro, sfx_scale(spec, [(s, 0.35 * k, 0.6 + 0.2 * k) for k, s in enumerate(ST["intro_outro"]["outro"])]))
    log("birleştiriliyor", 85)
    lst = os.path.join(work, "concat.txt"); joined = os.path.join(work, "joined.mp4")
    open(lst, "w").write("".join(f"file '{p}'\n" for p in [intro, *segs, outro]))
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    out = spec.get("output") or os.path.join(S.load().get("export_dir") or os.path.expanduser("~/Desktop"), f"{spec.get('name', 'siralama')}.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    total = dur(joined); mu = spec.get("music") or {}
    mpath = mu.get("path") and (mu["path"] if os.path.isabs(mu["path"]) else os.path.join(ROOT, mu["path"]))
    if mpath and os.path.exists(mpath):
        log("müzik ekleniyor", 92)
        # put the track's drop on the moment #1 appears
        t1 = isec + sum(dur(s) for s, it in zip(segs, items) if it["rank"] != 1 and items.index(it) < next((k for k, x in enumerate(items) if x["rank"] == 1), n))
        drop = mu.get("drop")
        if drop is None and mu.get("sync_drop", ST["music"]["sync_drop"]): drop = find_drop(mpath)
        start = max(0.0, float(drop) - t1) if drop is not None else float(mu.get("start", 0))
        music_bed(joined, mpath, start, total, out, float(mu.get("gain_db", ST["music"]["gain_db"])), isec, total - osec)
    else:
        run(["ffmpeg", "-v", "error", "-y", "-i", joined, "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=10,alimiter=limit=0.84:level=false", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    shutil.copyfile(out, os.path.join(work, "preview.mp4"))
    credit = "\n".join(filter(None, [mu.get("credit")] + [f"#{it['rank']} {it['label']}: {it.get('credit', '')} {it.get('url', '')}".strip() for it in items]))
    open(os.path.splitext(out)[0] + " - krediler.txt", "w").write(credit + "\n")
    cleaned = cleanup_sources(items) if S.load().get("cleanup_sources") else []
    if cleaned: log(f"kaynak videolar silindi ({sum(c['mb'] for c in cleaned):.0f} MB)", 99)
    json.dump({"output": out, "duration": dur(out), "credits": credit, "style_version": ST.get("version"), "cleaned_sources": cleaned}, open(os.path.join(work, "rendered.json"), "w"), ensure_ascii=False)
    log("bitti", 100)
    return out

if __name__ == "__main__":
    try: print(render(os.path.abspath(sys.argv[1])))
    except Exception as e:
        log("hata: " + str(e)[-300:], None); raise
