"""Absolute camera position per frame, from the static top of the frame (ceiling, curtain, wall).

Reads 480x270 grey frames on stdin. Each frame is registered against a fixed reference frame
using only rows 0..95 (above the projection screen), so changing slides cannot fool it and
nothing accumulates.  Usage: ffmpeg ... | motion2.py REF_FRAME_INDEX out.npz
"""
import sys
import numpy as np

W, H, S = 480, 270, 3840 / 480
TOP = 95
win = np.outer(np.hanning(TOP), np.hanning(W)).astype(np.float32)

def prep(a):
    a = a[:TOP]
    gy, gx = np.gradient(a)
    g = np.hypot(gx, gy)
    return np.fft.rfft2((g - g.mean()) * win)

def peak(r):
    y, x = np.unravel_index(np.argmax(r), r.shape)
    def par(m1, c, p1):
        d = m1 - 2 * c + p1
        return 0.0 if d == 0 else 0.5 * (m1 - p1) / d
    fy = par(r[(y - 1) % TOP, x], r[y, x], r[(y + 1) % TOP, x])
    fx = par(r[y, (x - 1) % W], r[y, x], r[y, (x + 1) % W])
    y, x = y + fy, x + fx
    if y > TOP / 2: y -= TOP
    if x > W / 2: x -= W
    return x, y, float(r.max())

# Reference frame comes from a separate file; frames are processed one by one (constant memory).
buf, n = sys.stdin.buffer, W * H
R = prep(np.fromfile(sys.argv[1], np.uint8)[:n].reshape(H, W).astype(np.float32))
xs, ys, qs = [], [], []
while True:
    b = buf.read(n)
    if len(b) < n:
        break
    X = prep(np.frombuffer(b, np.uint8).reshape(H, W).astype(np.float32)) * np.conj(R)
    x, y, q = peak(np.fft.irfft2(X / (np.abs(X) + 1e-6), s=(TOP, W)))
    xs.append(x * S); ys.append(y * S); qs.append(q)
np.savez(sys.argv[2], px=np.array(xs), py=np.array(ys), q=np.array(qs))
q = np.array(qs)
print(f"frames {len(xs)}, match quality p5 {np.percentile(q,5):.3f} p50 {np.median(q):.3f}; x {min(xs):.0f}..{max(xs):.0f}, y {min(ys):.0f}..{max(ys):.0f}")
