"""Reel projects: projects/<name>/reel.json -> 1080x1920 reel.

Usage: reel_project.py PROJECT_DIR [--check]
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["PATH"] = "/opt/homebrew/opt/ffmpeg-full/bin:" + os.environ.get("PATH", "")

def validate(r):
    """Same rule as the long edit: a shot that shows the speaker talking must be in sync with its own audio."""
    out = []
    for bi, b in enumerate(r["beats"]):
        if b["audio"]["b"] <= b["audio"]["a"]:
            out.append({"level": "error", "beat": bi, "msg": f"Cümle {bi + 1}: ses bitişi başlangıçtan önce."})
        fixed = sum(s.get("dur") or 0 for s in b["shots"])
        if fixed > b["audio"]["b"] - b["audio"]["a"] + 0.01:
            out.append({"level": "error", "beat": bi, "msg": f"Cümle {bi + 1}: planların süresi sesten uzun."})
        for si, s in enumerate(b["shots"]):
            if s["kind"] in ("sync", "paper"):
                continue
            src = r["sources"].get(s.get("src"), {})
            if src.get("speaker") == "yes" and not s.get("synced"):
                out.append({"level": "error", "beat": bi, "shot": si,
                            "msg": f"Cümle {bi + 1}, plan {si + 1} ({s['src']}): yüzün görünüyor ama ses başka andan. Dudaklar kayar."})
            elif src.get("speaker") == "sometimes" and not s.get("synced"):
                out.append({"level": "warn", "beat": bi, "shot": si, "msg": f"Cümle {bi + 1}, plan {si + 1} ({s['src']}): bazen konuşmacı görünüyor, kontrol et."})
    return out

def to_beats(r, pdir):
    S = r["sources"]; beats = []
    for b in r["beats"]:
        a = b["audio"]
        shots = []
        for s in b["shots"]:
            d = {k: v for k, v in s.items() if k not in ("src",)}
            if s["kind"] == "paper":
                d["dir"] = os.path.join(pdir, s.get("dir", "paper")) if not os.path.isabs(s.get("dir", "")) else s["dir"]
            elif s["kind"] != "sync":
                d["file"] = S[s["src"]]["path"]
            if s.get("layout") == "crop":
                d.pop("layout")
            shots.append(d)
        beats.append(dict(audio=(S[a["src"]]["path"], a["a"], a["b"]), gain=b.get("gain", 1.0), shots=shots,
                          caps=[(c["text"], c["s"], c["e"]) for c in b.get("caps", [])],
                          titles=[(t["text"], t["size"], t["col"], t["x"], t["y"], t.get("ang", 0), t.get("d0", 0), t.get("d1")) for t in b.get("titles", [])],
                          **({"cap_y": b["cap_y"]} if b.get("cap_y") else {}),
                          **({"transition": b["transition"]} if b.get("transition") and b["transition"].get("name") not in (None, "", "none") else {})))
    return beats

def main(pdir, check=False):
    pdir = os.path.abspath(pdir)
    r = json.load(open(os.path.join(pdir, "reel.json")))
    work = os.path.join(pdir, "work"); os.makedirs(work, exist_ok=True)
    probs = validate(r)
    if check:
        print(json.dumps(probs, ensure_ascii=False, indent=1)); return
    def status(step, pct=None, **kw):
        tmp = os.path.join(work, "status.json.tmp")
        json.dump({"step": step, "pct": pct, "time": time.time(), **kw}, open(tmp, "w"), ensure_ascii=False)
        os.replace(tmp, os.path.join(work, "status.json"))
    if any(p["level"] == "error" for p in probs):
        status("error", msg="Önce kırmızı uyarıları düzelt."); sys.exit(1)
    from reelkit import build
    end = r.get("end_card")
    if end:
        end = dict(dur=end.get("dur", 2.4), titles=[(t["text"], t["size"], t["col"], t["x"], t["y"], t.get("ang", 0), t.get("d0", 0)) for t in end["titles"]])
    status("render", 0)
    out = r["output"]; os.makedirs(os.path.dirname(out), exist_ok=True); tmp = out + ".tmp.mp4"
    fx = {"filter": (r.get("look") or {}).get("filter"), "lut": (r.get("look") or {}).get("lut"),
          "audio": r.get("audio") or {}, "sfx": r.get("sfx") or []}
    total = build(to_beats(r, pdir), tmp, work, end_card=end, cap_y=r.get("cap_y", 1400),
                  progress=lambda f, m: status(m, round(100 * f)), fx=fx)
    os.replace(tmp, out)
    json.dump(r, open(os.path.join(work, "rendered.json"), "w"), ensure_ascii=False)   # what this render shows, for the editor's "needs render" badge
    status("bitti", 100, output=out, length=round(total, 2))
    print(f"done {out} ({total:.1f}s)")

if __name__ == "__main__":
    main(sys.argv[1], "--check" in sys.argv)
