"""Pick the sharpest frame near each moment and export a square crop + full 4K frame.

Usage: stills.py MAIN.MOV OUTDIR
"""
import os, subprocess, sys
import numpy as np

MAIN, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
TM = "zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0:peak=4,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
# name, time, square crop (x, y, size) in 4K pixels
M = [
    ("01_isim-karti", 51.0, (1270, 820, 1200)),
    ("02_isim-karti-yuruyus", 53.5, (1380, 820, 1200)),
    ("03_binary-anlatim", 370.0, (1350, 800, 1200)),
    ("04_low-level", 430.0, (1250, 780, 1200)),
    ("05_four-layers", 650.0, (1170, 750, 1200)),
    ("06_tesekkurler", 1446.0, (1050, 700, 1300)),
]
for name, t, (x, y, s) in M:
    t0 = max(0, t - 0.4)
    # Sharpness on a small grey version of the crop (variance of the Laplacian).
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0}", "-i", MAIN, "-t", "0.8",
                          "-vf", f"crop={s}:{s}:{x}:{y},scale=400:400,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, 400, 400).astype(np.float32)
    lap = [(np.abs(f[1:-1, 1:-1] * 4 - f[:-2, 1:-1] - f[2:, 1:-1] - f[1:-1, :-2] - f[1:-1, 2:])).var() for f in fr]
    k = int(np.argmax(lap)); tb = t0 + k * 1001 / 60000
    for tag, vf in (("kare", f"{TM},crop={s}:{s}:{x}:{y}"), ("genis", TM)):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{tb:.4f}", "-i", MAIN, "-frames:v", "1",
                        "-vf", vf, "-q:v", "1", os.path.join(OUT, f"{name}_{tag}.jpg")], check=True)
    print(f"{name}: best frame {k}/{len(fr)} at {tb:.2f}s (sharpness {lap[k]:.0f}, median {np.median(lap):.0f})")
