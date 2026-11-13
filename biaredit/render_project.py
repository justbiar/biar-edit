"""Render a project.json to the final 4K film.

Usage: render_project.py PROJECT_DIR [--check]
Steps: validate -> work/edits.json -> plan segments -> chapter graphics -> paper intro -> segments -> mux.
Progress goes to PROJECT_DIR/work/status.json so the editor UI can show it.
"""
import json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
ENV = dict(os.environ, PATH="/opt/homebrew/opt/ffmpeg-full/bin:" + os.environ.get("PATH", ""))

def status(work, step, pct=None, **kw):
    d = {"step": step, "pct": pct, "time": time.time(), **kw}
    tmp = os.path.join(work, "status.json.tmp")
    json.dump(d, open(tmp, "w"), ensure_ascii=False); os.replace(tmp, os.path.join(work, "status.json"))

def validate(p):
    """Problems that would make the film look wrong. 'error' blocks rendering."""
    out = []
    for o in p["overlays"]:
        if not o.get("on", True):
            continue
        s = p["sources"].get(o["src"], {})
        if s.get("speaker") == "yes" and not o.get("synced"):
            out.append({"level": "error", "id": o["id"], "msg": f"#{o['id']} {o['src']}: konuşmacının yüzü görünüyor ama ses başka bir andan. Dudaklar kaymış görünür."})
        elif s.get("speaker") == "sometimes" and not o.get("synced"):
            out.append({"level": "warn", "id": o["id"], "msg": f"#{o['id']} {o['src']}: bu klipte bazen konuşmacı görünüyor, seçilen anı kontrol et."})
        if o["end"] - o["start"] <= 0:
            out.append({"level": "error", "id": o["id"], "msg": f"#{o['id']}: bitiş başlangıçtan önce."})
    cuts = sorted((c for c in p["cuts"] if c.get("on", True)), key=lambda c: c["start"])
    for a, b in zip(cuts, cuts[1:]):
        if 0 < b["start"] - a["end"] < 0.12:
            out.append({"level": "warn", "id": b["id"], "msg": f"Kesim #{a['id']} ve #{b['id']} arasında {1000*(b['start']-a['end']):.0f} ms kalıyor: kekeme gibi duyulabilir."})
    return out

def main(pdir, check_only=False):
    pdir = os.path.abspath(pdir)
    p = json.load(open(os.path.join(pdir, "project.json")))
    work = os.path.join(pdir, "work"); os.makedirs(work, exist_ok=True)
    problems = validate(p)
    json.dump(problems, open(os.path.join(work, "problems.json"), "w"), ensure_ascii=False)
    if check_only:
        print(json.dumps(problems, ensure_ascii=False, indent=1)); return
    if any(x["level"] == "error" for x in problems):
        status(work, "error", msg="Render durduruldu: önce kırmızı uyarıları düzelt.", problems=problems); sys.exit(1)

    status(work, "hazırlık", 0)
    # 1) the renderer's input format
    cuts = [{"start": c["start"], "end": c["end"], "reason": c["reason"]} for c in p["cuts"] if c.get("on", True)]
    broll = [{"id": o["id"], "start": o["start"], "end": o["end"], "clip": o["src"], "clipIn": o["in"],
              "reason": o.get("reason", ""), "secret": o.get("secret", False)} for o in p["overlays"] if o.get("on", True)]
    clips = {k: {} for k in p["sources"] if k != p["main"]}
    clips["SCREEN"] = {}; clips["PAPER"] = {}
    json.dump({"cuts": cuts, "broll": broll, "clips": clips}, open(os.path.join(work, "edits.json"), "w"), ensure_ascii=False)
    json.dump({"chapters": p.get("chapters", []), "outro": p.get("outro")}, open(os.path.join(work, "chapters.json"), "w"), ensure_ascii=False)
    for f in ("track.json", "motion2.npz"):
        src = os.path.join(pdir, "data", f)
        if os.path.exists(src) and not os.path.exists(os.path.join(work, f)):
            shutil.copy(src, os.path.join(work, f))
    srcdir = p["source_dir"]

    # 2) segment plan (also gives the output-frame mapping the graphics need)
    status(work, "plan", 2)
    subprocess.run([PY, "-I", os.path.join(HERE, "render.py"), work, srcdir, "--plan-only"], check=True, env=ENV, capture_output=True)
    # 3) chapter cards + outro
    status(work, "grafikler", 4)
    shutil.rmtree(os.path.join(work, "gfx"), ignore_errors=True)
    subprocess.run([PY, "-I", os.path.join(HERE, "graphics.py"), work], check=True, env=ENV, capture_output=True)
    # 4) paper intro frames
    if any(b["clip"] == "PAPER" for b in broll):
        status(work, "kağıt efekti", 8)
        pw = os.path.join(work, "paper2")
        if not os.path.isdir(os.path.join(pw, "seq")):
            shutil.copytree(os.path.join(pdir, "paper"), pw, dirs_exist_ok=True)
            os.makedirs(os.path.join(pw, "anim"), exist_ok=True)
            subprocess.run([PY, "-I", os.path.join(HERE, "paper2.py"), pw], check=True, env=ENV, capture_output=True)
            seq = os.path.join(pw, "seq"); os.makedirs(seq, exist_ok=True)
            frames = sorted(f for f in os.listdir(os.path.join(pw, "anim")) if f.startswith("a_")) + \
                     sorted(f for f in os.listdir(os.path.join(pw, "anim")) if f.startswith("f_"))
            for i, f in enumerate(frames):
                os.symlink(os.path.join(pw, "anim", f), os.path.join(seq, f"p_{i:05d}.jpg"))
    if "--dry" in sys.argv:
        status(work, "hazır (kuru çalıştırma)", 10); print("dry run ok"); return
    # 5) segments (reuses identical segments from the previous render)
    status(work, "render", 10)
    proc = subprocess.Popen([PY, "-I", os.path.join(HERE, "render.py"), work, srcdir], env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        if line.startswith("progress "):
            a, b = line.split()[1].split("/")
            status(work, "render", 10 + 85 * int(a) / int(b))
        elif "ERR" in line or "mismatch" in line:
            status(work, "error", msg=line.strip());
    if proc.wait() != 0:
        status(work, "error", msg="render başarısız, log: work/render/log.txt"); sys.exit(1)
    # 6) mux
    status(work, "birleştirme", 96)
    R = os.path.join(work, "render"); out = p["output"]
    tmp = out + ".tmp.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(R, "list.txt"), "-i", os.path.join(R, "audio.wav"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", tmp], check=True, env=ENV)
    os.replace(tmp, out)
    status(work, "bitti", 100, output=out)
    print("done", out)

if __name__ == "__main__":
    main(sys.argv[1], "--check" in sys.argv)
