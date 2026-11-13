"""Build the edit decision list (cuts + overlays) into edits.json.

Usage: plan.py gaps.json edits.json
"""
import json, sys

gaps_path, out = sys.argv[1:3]
G = json.load(open(gaps_path))
words = G["words"]
TALK_START, TALK_END, DUR = 68.0, 1453.5, 1474.96

def ctx(a, b, pad=3):
    before = " ".join(w["w"] for w in words if a - pad <= w["s"] < a)
    inside = " ".join(w["w"] for w in words if a <= w["s"] < b)
    after = " ".join(w["w"] for w in words if b <= w["s"] < b + pad)
    return (before[-40:] + " [" + inside + "] " + after[:40]).strip()

cuts = []
def cut(s, e, reason):
    cuts.append({"start": round(s, 2), "end": round(e, 2), "reason": reason, "text": ctx(s, e)})

# 1. Walk-on between the host's intro and the first words.
# Keep the walk-on while the screen shows the speaker's name card (47.5-56 s), cut the rest.
cut(56.3, 67.6, "Sahneye yürüme ve hazırlık")
# 2. Audience hand-raising waits (Whisper hallucinated "zero zero" here).
cut(262.0, 271.6, "Seyircinin el kaldırmasını bekleme")
cut(281.6, 284.8, "Seyircinin el kaldırmasını bekleme")
# 3. False starts, repeats, filler words.
# (Checked against the verbatim pass: the first pass misheard several of these as repeats.)
cut(198.5, 202.35, "Yarım kalan cümle: \"you can use the, uh, faucet, uh\"")
cut(1076.6, 1079.7, "Dolgu: \"Thanks. Okay.\"")
cut(1042.6, 1043.55, "Dolgu: \"Okay\"")
cut(968.5, 971.45, "Dolgu: \"Okay\"")
cut(1150.5, 1153.8, "Dolgu: \"Okay\"")
cut(950.2, 959.7, "Konu dışı araya girme (kontrol et)")
# 4. End: next speaker's announcement.
cut(1455.5, DUR, "Sonraki konuşmanın anonsu")

# 5. Pauses (silence or "uh/umm" that Whisper does not write out): shorten to ~0.4 s.
def covered(s, e):
    return any(c["start"] <= s + 0.05 and e - 0.05 <= c["end"] for c in cuts) or (260 < s < 287)
for g in G["gaps"]:
    if g["len"] >= 1.0 and TALK_START < g["s"] and g["e"] < TALK_END and not covered(g["s"], g["e"]):
        # Leave a natural pause: longer after a sentence end, a breath elsewhere.
        pad = 0.35 if words[g["i"] - 1]["w"].rstrip().endswith((".", "?", "!")) else 0.25
        s, e = g["s"] + pad, g["e"] - pad
        # Merge with an overlapping hand-made cut instead of duplicating.
        clash = [c for c in cuts if c["start"] < e and s < c["end"]]
        if clash:
            c = clash[0]; c["start"] = round(min(c["start"], s), 2); c["end"] = round(max(c["end"], e), 2)
            continue
        cut(s, e, "Duraklama / ııı" if g["len"] < 3 else "Uzun bekleme (demo sırasında)")

# 6. Fillers ("uh", "um") from the verbatim chunked pass. Each is cut from the end of the
#    previous real word to the start of the next one, leaving a short natural breath.
import re, os
FILL = re.compile(r"(?i)^\W*(uh+|um+|uhm+|umm+|er+|ah+|eh+)\W*$")
vpath = os.path.join(os.path.dirname(out), "verbatim.json")
V = json.load(open(vpath)) if os.path.exists(vpath) else []
# Drop hallucination loops: 4+ identical tokens in a row.
loop = set()
for i in range(len(V)):
    j = i
    while j + 1 < len(V) and V[j + 1]["w"].lower() == V[i]["w"].lower():
        j += 1
    if j - i >= 3:
        loop.update(range(i, j + 1))
real = [i for i, x in enumerate(V) if not FILL.match(x["w"]) and "hmm" not in x["w"].lower() and i not in loop]
unresolved = 0
for i, x in enumerate(V):
    if i in loop or not FILL.match(x["w"]) or not (TALK_START < x["s"] < TALK_END):
        continue
    prev = max((k for k in real if k < i), default=None)
    nxt = min((k for k in real if k > i), default=None)
    a = V[prev]["e"] if prev is not None else x["s"]
    b = V[nxt]["s"] if nxt is not None else x["e"]
    if b - a < 0.12:  # filler swallowed by neighbour timestamps: use its own span
        a, b = x["s"], x["e"]
    if b - a < 0.12:
        unresolved += 1
        continue
    # Keep ~0.3 s of air where the filler was, so the joined words do not collide.
    s, e = a + 0.15, b - 0.15
    if e - s < 0.15:
        continue
    if any(c["start"] <= s and e <= c["end"] for c in cuts):
        continue
    clash = [c for c in cuts if c["start"] < e and s < c["end"]]
    if clash:
        c = clash[0]; c["start"] = round(min(c["start"], s), 2); c["end"] = round(max(c["end"], e), 2)
        if "ııı" not in c["reason"]:
            c["reason"] += " + ııı"
        continue
    cut(s, e, "ııı (\"" + x["w"].strip(",.") + "\")")
print("fillers unresolved:", unresolved)

# 7. Second-pass fillers found in the already-edited audio (mapped back to source time).
p2 = os.path.join(os.path.dirname(out), "fillers_pass2.json")
for s, e, wtxt in (json.load(open(p2)) if os.path.exists(p2) else []):
    if not any(c["start"] <= s and e <= c["end"] for c in cuts):
        cut(s, e, "ııı (2. tarama)")

# 8. Safety: never cut into a real word. Hand-made cuts are trusted (they target words on purpose).
MANUAL = ("Dolgu", "Tekrar", "Yarım", "Konu dışı", "Sahneye", "Seyircinin", "Sonraki")
# Verbatim timings separate fillers from words, so they are the reference (first-pass words
# often stretch over an "uh" and would block the cut).
realset = set(real)
spans = [(x["s"], x["e"]) for i, x in enumerate(V) if i in realset]
safe = []
for c in cuts:
    if c["reason"].startswith(MANUAL):
        safe.append(c); continue
    s, e = c["start"], c["end"]
    pieces = [(s, e)]
    for ws, we in spans:
        nxt = []
        for a, b in pieces:
            ws2, we2 = ws - 0.08, we + 0.08
            if we2 <= a or b <= ws2:
                nxt.append((a, b)); continue
            if a < ws2: nxt.append((a, ws2))
            if we2 < b: nxt.append((we2, b))
        pieces = nxt
    for a, b in pieces:
        if b - a >= 0.12:
            safe.append({**c, "start": round(a, 2), "end": round(b, 2)})
cuts = safe

# Merge overlapping or touching cuts.
cuts.sort(key=lambda c: c["start"])
merged = []
for c in cuts:
    if merged and c["start"] <= merged[-1]["end"] + 0.05:
        m = merged[-1]; m["end"] = max(m["end"], c["end"])
        if c["reason"] not in m["reason"]:
            m["reason"] += " + " + c["reason"]
    else:
        merged.append(c)
cuts = merged
for i, c in enumerate(cuts, 1):
    c["id"] = i

# Overlays over the "looking at the laptop" moments. clip SCREEN = close-up of the projection.
S1, S2, S3 = "DJI_20261007064514_0020_D", "DJI_20261007080351_0030_D", "DJI_20261007123632_0074_D"
S4, S5, S6, PH = "DJI_20261007125658_0089_D", "DJI_20261007125837_0090_D", "IMG_4257", "PHOTO"

def kept_until(s, out_len):
    """Source time reached after playing out_len seconds of output starting at source s."""
    t, left = s, out_len
    for c in sorted(cuts, key=lambda c: c["start"]):
        if c["end"] <= t:
            continue
        if c["start"] > t:
            seg = c["start"] - t
            if seg >= left:
                return t + left
            left -= seg
        t = max(t, c["end"])
    return t + left

def out_len(s, e):
    return (e - s) - sum(max(0, min(e, c["end"]) - max(s, c["start"])) for c in cuts)

N1, N2, N3 = "20261008_103056", "DJI_20261008153106_0165_D", "IMG_4258"
L1, L2, L3, L4 = ("DJI_20261008055834_0111_D", "DJI_20261008055958_0112_D",
                  "DJI_20261008060601_0113_D", "DJI_20261008061432_0118_D")

# Usable ranges per source, checked frame by frame (no self-filming, no hands, no tilts,
# no shots of the speaker looking at the laptop, no readable keys).
POOL = {
    "audience": [(L3, 0, 14), (L3, 60, 125), (L3, 130, 157), (L3, 150, 178),
                 (L4, 0, 58), (L4, 100, 147), (L4, 150, 170), (L4, 240, 273)],
    "stage":    [(L3, 190, 205), (L4, 175, 228), (N3, 0, 5.5), (N3, 16, 27.5),
                 (S6, 0, 9.5), (S6, 14, 27.5), (S2, 30, 38.5), (L1, 16, 27)],
    "venue":    [(S1, 0, 6.5), (S1, 9.5, 20), (S1, 20, 26), (S2, 9, 29), (S2, 40, 43.5), (S3, 0, 10.5),
                 (S3, 13.5, 26.5), (S4, 0, 28), (S4, 30, 46), (S5, 0, 7), (S5, 10, 30), (L1, 0, 5),
                 (L2, 0, 5.5), (L2, 6, 16.5), (N2, 0, 5.5), (N2, 11, 14.5)],
}
SHOT = 6.0  # max seconds per shot

def chunks(lst):
    out = []
    for clip, a, b in lst:
        t = a
        while b - t >= 2.5:
            n = min(SHOT, b - t)
            if b - (t + n) < 2.5:
                n = b - t if b - t <= SHOT + 2.5 else n
            out.append((clip, t, t + n, b)); t += n
    return out

# Round-robin by clip so consecutive shots come from different sources.
import itertools
queues = {}
for cat, lst in POOL.items():
    by = {}
    for c in chunks(lst):
        by.setdefault(c[0], []).append(c)
    order = []
    for grp in itertools.zip_longest(*by.values()):
        order += [g for g in grp if g]
    queues[cat] = order

def take(cats):
    """Next unused shot, rotating through the given categories, never repeating the last clip."""
    def pop(q):
        for i, c in enumerate(q):
            if c[0] != take.last:
                take.last = c[0]; return q.pop(i)
        return None
    for _ in range(len(cats)):
        cat = cats[take.k % len(cats)]; take.k += 1
        r = pop(queues[cat])
        if r: return r
    for cat in queues:
        r = pop(queues[cat])
        if r: return r
    return None
take.k = 0
take.last = None
MIN = 2.5  # no shot shorter than this

broll = []
def fill(s, e, cats, reason, secret, first=None):
    need, t = out_len(s, e), s
    shots = [first] if first else []
    while need > 0.05:
        sh = shots.pop(0) if shots else take(cats)
        if sh is None:
            if secret:
                raise SystemExit(f"secret window {s}-{e} not covered")
            broll.append({"start": round(t, 2), "end": e, "clip": "SCREEN", "clipIn": 0, "reason": reason, "secret": False})
            return
        clip, ci, co, pmax = sh
        n = min(co - ci, need)
        rem = need - n
        if 0.05 < rem < MIN:  # avoid a sliver at the end of the window
            n = need if pmax - ci >= need else max(MIN, need - MIN)
        te = min(e, kept_until(t, n))
        broll.append({"start": round(t, 2), "end": round(te, 2), "clip": clip, "clipIn": ci, "reason": reason, "secret": secret})
        need -= n; t = te

def screen_with_cutaways(s, e, reason, every=20.0, cut=5.0):
    """Projection close-up, broken up by short audience shots so long demos do not drag."""
    total, t, o = out_len(s, e), s, 0.0
    while o < total - 0.05:
        seg = min(every, total - o)
        if 0 < total - o - seg < MIN:
            seg = total - o
        te = min(e, kept_until(t, seg))
        broll.append({"start": round(t, 2), "end": round(te, 2), "clip": "SCREEN", "clipIn": 0, "reason": reason, "secret": False})
        t, o = te, o + seg
        if total - o > cut + 8:
            sh = take(["audience"])
            if sh:
                n = min(cut, sh[3] - sh[1]); te = min(e, kept_until(t, n))
                broll.append({"start": round(t, 2), "end": round(te, 2), "clip": sh[0], "clipIn": sh[1],
                              "reason": "Ara plan: seyirci", "secret": False})
                t, o = te, o + n

# Secret windows first, so they always get footage.
SECRET = [(856.0, 866.0, "GİZLİ: OpenRouter API key ekranda"),
          (923.5, 1044.5, "GİZLİ: cüzdan private key terminalde"),
          (1190.5, 1199.5, "GİZLİ: Walrus delegate private key"),
          (1209.0, 1228.5, "GİZLİ: Walrus SDK credentials")]
for s, e, r in SECRET:
    fill(s, e, ["audience", "audience", "venue", "stage"], r, True)

LAPTOP = [
    (115, 138, "screen", "Bilgisayara bakıyor, QR kod anlatımı: perde yakın plan"),
    (247, 259, ["audience"], "Bilgisayara bakıyor, seyirciye soru: seyirci"),
    (276, 285, ["venue"], "Bilgisayara bakıyor: etkinlik"),
    (715, 725, ["venue"], "Bilgisayara bakıyor, bölüm 2 başlangıcı"),
    (776, 796, ["stage", "venue"], "Bilgisayara bakıyor: sahne ve etkinlik"),
    (806, 846, "screen", "Demo, laptop başında: perde yakın plan"),
    (866.0, 887, "screen", "Demo, laptop başında: perde yakın plan"),
    (905, 914, ["venue"], "Bilgisayara bakıyor: etkinlik"),
    (1126, 1135, ["stage"], "Bilgisayara bakıyor: sahne"),
    (1145, 1156, "screen", "Bilgisayara bakıyor: perde yakın plan"),
    (1186, 1190.5, "screen", "Walrus hafıza kurulumu: perde yakın plan"),
    (1199.5, 1209.0, "screen", "Walrus hafıza kurulumu: perde yakın plan"),
    (1228.5, 1247, "screen", "Walrus hafıza kurulumu: perde yakın plan"),
    (1256, 1327, "screen", "Agent remember/recall demo: perde yakın plan"),
    (1365, 1387, "screen", "Agent kaydı: perde yakın plan"),
    (1395, 1405, ["venue", "stage"], "Bilgisayara bakıyor: etkinlik"),
]
for s, e, mode, r in LAPTOP:
    if mode == "screen":
        screen_with_cutaways(s, e, r)
    else:
        fill(s, e, mode, r, False, first=(S3, 0.0, 10.5, 10.5) if s == 715 else None)

# Intro: paper-cutout freeze from the audience phone angle while he says hello (229 frames).
broll.append({"start": 68.2, "end": round(kept_until(68.2, 229 / (60000 / 1001)), 3), "clip": "PAPER", "clipIn": 0,
              "reason": "Giris: kagit efekti (isim, X, site)", "secret": False})
broll.sort(key=lambda b: b["start"])
for i, b in enumerate(broll, 1):
    b["id"] = i
from collections import Counter
used = Counter(b["clip"] for b in broll)
print("secret windows covered; shots per clip:", dict(used))

d = json.load(open(out))
d["cuts"], d["broll"] = cuts, broll
d["clips"]["SCREEN"] = {"src": "main_proxy.mp4", "screen": True}
d["clips"]["PHOTO"] = {"src": "frames/heic.jpg", "image": True}
for c in (N1, N2, N3, L1, L2, L3, L4):
    d["clips"][c] = {"src": "side/" + c + ".mp4"}
json.dump(d, open(out, "w"), ensure_ascii=False, indent=1)
tot = sum(c["end"] - c["start"] for c in cuts)
print(len(cuts), "cuts,", round(tot), "s removed; final", round((DUR - tot) / 60, 1), "min;", len(broll), "overlays")
