"""Verbatim re-transcription in short chunks so the disfluency prompt applies to every window.

Usage: fillers.py main.wav gaps.json out.json START END
Chunks are cut at existing word gaps (~20 s each) so no word is split.
"""
import json, sys, wave
import numpy as np
import mlx_whisper

wav, gaps_path, out, T0, T1 = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
PROMPT = ("Umm, so, uh, I was like, uh, thinking about it. Uh, hmm, er, you know, um, "
          "we, uh, we are going to, um, start. Ah, uhm, okay, so, uh.")

w = wave.open(wav); sr = w.getframerate()
audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
words = json.load(open(gaps_path))["words"]

# Choose chunk borders at the middle of word gaps, aiming for ~20 s chunks.
borders, t = [T0], T0
while t + 20 < T1:
    cands = [(words[i - 1]["e"] + words[i]["s"]) / 2 for i in range(1, len(words))
             if t + 15 <= words[i]["s"] <= t + 25 and words[i]["s"] - words[i - 1]["e"] > 0.15]
    t = t + 20 if not cands else min(cands, key=lambda c: abs(c - (t + 20)))
    borders.append(t)
borders.append(T1)

res = []
for a, b in zip(borders, borders[1:]):
    chunk = audio[int(a * sr): int(b * sr)]
    r = mlx_whisper.transcribe(chunk, path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
                               language="en", word_timestamps=True, initial_prompt=PROMPT,
                               condition_on_previous_text=False, temperature=0.0)
    for s in r["segments"]:
        for x in s.get("words", []):
            res.append({"w": x["word"].strip(), "s": round(x["start"] + a, 2), "e": round(x["end"] + a, 2),
                        "p": round(x.get("probability", 0), 2)})
    print(f"{a:7.1f}-{b:7.1f}", " ".join(x["w"] for x in res if a <= x["s"] < b)[:160], flush=True)
json.dump(res, open(out, "w"), ensure_ascii=False)
