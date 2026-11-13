"""List words with timing, gaps between words and the audio energy inside each gap.

Usage: gaps.py transcript.json main.wav out.json
A gap with speech-level energy is likely a filler ("uh", "umm") that Whisper dropped;
a gap with low energy is a silent pause.
"""
import json, sys, wave
import numpy as np

tr, wav, out = sys.argv[1:4]
w = wave.open(wav)
sr = w.getframerate()
a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
hop = sr // 100  # 10 ms frames
n = len(a) // hop
rms = np.sqrt((a[: n * hop].reshape(n, hop) ** 2).mean(1))
db = 20 * np.log10(rms + 1e-9)

words = []
for s in json.load(open(tr))["segments"]:
    for x in s.get("words", []):
        words.append({"w": x["word"].strip(), "s": round(x["start"], 2), "e": round(x["end"], 2)})

# Speech reference level: median energy inside words.
inside = np.concatenate([db[int(x["s"] * 100): int(x["e"] * 100)] for x in words if x["e"] > x["s"]])
speech = float(np.median(inside))
floor = float(np.percentile(db, 10))

gaps = []
for i in range(1, len(words)):
    s, e = words[i - 1]["e"], words[i]["s"]
    if e - s < 0.35:
        continue
    seg = db[int(s * 100): int(e * 100)]
    voiced = float((seg > speech - 12).mean()) if len(seg) else 0
    gaps.append({"i": i, "s": s, "e": e, "len": round(e - s, 2), "voiced": round(voiced, 2),
                 "before": " ".join(x["w"] for x in words[max(0, i - 4): i]),
                 "after": " ".join(x["w"] for x in words[i: i + 4])})

json.dump({"speech_db": speech, "floor_db": floor, "words": words, "gaps": gaps}, open(out, "w"), ensure_ascii=False)
print(f"speech {speech:.1f} dB, floor {floor:.1f} dB, words {len(words)}, gaps {len(gaps)}")
tot = sum(g["len"] for g in gaps if g["s"] > 68 and g["e"] < 1454)
print(f"total gap time inside talk: {tot:.0f}s")
