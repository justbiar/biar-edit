"""Find fillers left in the edited audio and map them back to source time.

Usage: pass2.py main.wav edits.json out.json
Writes [[src_start, src_end, word], ...].
"""
import json, re, sys, wave
import numpy as np
import mlx_whisper

wav, ed, out = sys.argv[1:4]
T0, T1 = 66.0, 1456.0
w = wave.open(wav); sr = w.getframerate()
a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
cuts = sorted((c for c in json.load(open(ed))["cuts"] if c["end"] > T0 and c["start"] < T1), key=lambda c: c["start"])
keep, t = [], T0
for c in cuts:
    if c["start"] > t:
        keep.append((t, c["start"]))
    t = max(t, c["end"])
keep.append((t, T1))
segs, pos = [], 0.0  # (edited_start, src_start, length)
parts = []
for s, e in keep:
    parts.append(a[int(s * sr): int(e * sr)]); segs.append((pos, s, e - s)); pos += e - s
y = np.concatenate(parts)

def to_src(te):
    for es, ss, ln in segs:
        if es <= te < es + ln:
            return ss + (te - es)
    return None

FILL = re.compile(r"(?i)^\W*(uh+|um+|uhm+|umm+|er+|ah+|eh+)\W*$")
P = "Umm, so, uh, I was like, uh, thinking about it. Uh, er, you know, um, we, uh, we are going to, um, start."
found = []
step = 20 * sr
for k in range(0, len(y), step - 2 * sr):  # 2 s overlap so chunk borders do not hide fillers
    r = mlx_whisper.transcribe(y[k:k + step], path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
                               language="en", initial_prompt=P, condition_on_previous_text=False,
                               word_timestamps=True)
    ws = [x for s in r["segments"] for x in s.get("words", [])]
    for i, x in enumerate(ws):
        if not FILL.match(x["word"].strip()):
            continue
        # Bound by neighbouring real words in edited time.
        lo = ws[i - 1]["end"] if i > 0 else x["start"]
        hi = ws[i + 1]["start"] if i + 1 < len(ws) else x["end"]
        if hi - lo < 0.12:
            lo, hi = x["start"], x["end"]
        if hi - lo < 0.12:
            continue
        s_src, e_src = to_src(k / sr + lo + 0.05), to_src(k / sr + hi - 0.05)
        # Only keep spans that stay inside one kept piece (no cut in between).
        if s_src is not None and e_src is not None and 0 < e_src - s_src < 1.5:
            found.append([round(s_src, 2), round(e_src, 2), x["word"].strip()])
found = sorted({(f[0], f[1]): f for f in found}.values())
json.dump(found, open(out, "w"))
print("pass2 fillers:", len(found))
