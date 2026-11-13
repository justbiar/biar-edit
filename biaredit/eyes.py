"""Score frames by eye openness (Vision face landmarks) and sharpness.

Usage: eyes.py dir start_sec   (frames e_0001.png... at 59.94 fps starting at start_sec)
"""
import glob, os, sys
import numpy as np
import Quartz, Vision
from Foundation import NSURL
from PIL import Image

d, t0 = sys.argv[1], float(sys.argv[2])
FPS = 60000 / 1001

def eye_ratio(pts):
    a = np.array([(p.x, p.y) for p in pts])
    w = a[:, 0].max() - a[:, 0].min()
    h = a[:, 1].max() - a[:, 1].min()
    return h / w if w > 0 else 0

rows = []
for i, p in enumerate(sorted(glob.glob(os.path.join(d, "e_*.png")))):
    img = Quartz.CGImageSourceCreateImageAtIndex(Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(p), None), 0, None)
    req = Vision.VNDetectFaceLandmarksRequest.alloc().initWithCompletionHandler_(None)
    ok, err = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None).performRequests_error_([req], None)
    faces = req.results() or []
    if not ok or not faces:
        continue
    f = max(faces, key=lambda o: o.boundingBox().size.width)
    lm = f.landmarks()
    if lm is None or lm.leftEye() is None or lm.rightEye() is None:
        continue
    le = eye_ratio([lm.leftEye().normalizedPoints()[k] for k in range(lm.leftEye().pointCount())])
    re = eye_ratio([lm.rightEye().normalizedPoints()[k] for k in range(lm.rightEye().pointCount())])
    g = np.array(Image.open(p).convert("L")).astype(np.float32)
    lap = np.abs(4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]).var()
    bb = f.boundingBox()
    rows.append((t0 + i / FPS, min(le, re), lap, bb.size.width * 600))
rows = np.array(rows)
print("frames with a face:", len(rows))
eo = rows[:, 1]
print(f"eye openness: min {eo.min():.2f}  median {np.median(eo):.2f}  max {eo.max():.2f}")
# Good = eyes clearly open (top 30 %) ; among those, sharpest.
thr = np.percentile(eo, 70)
good = rows[eo >= thr]
best = good[np.argsort(-good[:, 2])][:8]
for t, e, l, fw in best:
    print(f"t={t:.3f}s eyes={e:.2f} sharp={l:.0f} face_w={fw:.0f}px")
np.save(os.path.join(d, "scores.npy"), rows)
