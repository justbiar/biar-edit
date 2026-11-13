"""Track global camera translation per second (phase correlation vs a reference frame).

Usage: track.py gray.raw first_sec ref_sec out.json   (gray.raw = 480x270 8-bit frames, 1 per second)
Output: {sec: [dx, dy]} in 4K pixels, smoothed.
"""
import json, sys
import numpy as np

raw, first, ref, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
W, H, S = 480, 270, 3840 / 480
fr = np.fromfile(raw, dtype=np.uint8).reshape(-1, H, W).astype(np.float32)
win = np.outer(np.hanning(H), np.hanning(W))

def prep(a):
    # Gradient magnitude: robust to the projected content and lighting changes.
    gy, gx = np.gradient(a)
    g = np.hypot(gx, gy)
    return (g - g.mean()) * win

def shift(a, b):
    F = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    r = np.fft.ifft2(F / (np.abs(F) + 1e-6)).real
    y, x = np.unravel_index(np.argmax(r), r.shape)
    if y > H // 2: y -= H
    if x > W // 2: x -= W
    return x, y, float(r.max())

R = prep(fr[ref - first])
pos = {}
for i in range(len(fr)):
    dx, dy, q = shift(prep(fr[i]), R)
    pos[first + i] = (dx * S, dy * S, q)
# Median filter (5 s) to reject outliers, then moving average (3 s).
secs = sorted(pos)
xs = np.array([pos[s][0] for s in secs]); ys = np.array([pos[s][1] for s in secs])
def med(a, k=2):
    return np.array([np.median(a[max(0, i - k): i + k + 1]) for i in range(len(a))])
def avg(a, k=1):
    return np.array([a[max(0, i - k): i + k + 1].mean() for i in range(len(a))])
xs, ys = avg(med(xs)), avg(med(ys))
json.dump({int(s): [round(float(x), 1), round(float(y), 1)] for s, x, y in zip(secs, xs, ys)}, open(out, "w"))
print("tracked", len(secs), "frames; dx range", xs.min().round(), xs.max().round(), "dy range", ys.min().round(), ys.max().round())
