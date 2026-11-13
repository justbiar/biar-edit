"""MCP server (stdio) so Claude and other agents can drive biar-edit.

  claude mcp add biar-edit -- <repo>/.venv/bin/python -I <repo>/biaredit/mcp_server.py

It is a thin client of the running app (http://localhost:8790), so a person in the UI and an
agent always see the same projects, renders and queue.  Posts an agent creates wait for your
approval in the queue unless you switched auto-post on for that account.
"""
import json, os, sys, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings as S

BASE = os.environ.get("BIAR_EDIT_URL", "http://localhost:8790")
PROTOCOL = "2025-06-18"

def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", "X-Biar-Token": S.api_token()})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read())
        except Exception: return {"ok": False, "msg": f"HTTP {e.code}"}
    except urllib.error.URLError:
        return {"ok": False, "msg": "biar-edit çalışmıyor. baslat.command ile aç."}

def obj(props, req=()):
    return {"type": "object", "properties": props, "required": list(req)}

STR, NUM = {"type": "string"}, {"type": "number"}
TOOLS = {
    "list_projects": ("Projeleri listeler (reel ve uzun video).", obj({}),
                      lambda a: call("GET", "/api/projects")),
    "get_reel": ("Bir projenin (reel ya da sıralama) tam yapısını ve uyarılarını döner. beats[]: audio{src,a,b}, shots[], caps[], titles[].",
                 obj({"project": STR}, ["project"]), lambda a: call("GET", f"/api/p/{a['project']}")),
    "save_reel": ("Reeli kaydeder. 'reel' alanı get_reel'den gelen reel nesnesinin düzenlenmiş hali olmalı. Önceki sürüm yedeklenir.",
                  obj({"project": STR, "reel": {"type": "object"}}, ["project", "reel"]),
                  lambda a: call("POST", f"/api/p/{a['project']}", a["reel"])),
    "render": ("Render başlatır. Kırmızı uyarı (senkron olmayan konuşmacı planı gibi) varsa reddeder.",
               obj({"project": STR}, ["project"]), lambda a: call("POST", f"/api/p/{a['project']}/render", {})),
    "render_status": ("Render ilerlemesi.", obj({"project": STR}, ["project"]), lambda a: call("GET", f"/api/p/{a['project']}/status")),
    "write_caption": ("Reelin altyazılarından paylaşım metni üretir (varsayılan model).",
                      obj({"project": STR, "platform": {"type": "string", "enum": ["instagram", "x", "linkedin", "youtube"]}}, ["project"]),
                      lambda a: call("POST", "/api/ai/caption", a)),
    "ask_model": ("Ayarlı modellerden birine soru sorar. provider boşsa varsayılan.",
                  obj({"prompt": STR, "provider": {"type": "string", "enum": ["anthropic", "openrouter", "ollama"]}, "model": STR, "system": STR}, ["prompt"]),
                  lambda a: call("POST", "/api/ai/chat", {"provider": a.get("provider"), "model": a.get("model"), "system": a.get("system"),
                                                          "messages": [{"role": "user", "content": a["prompt"]}]})),
    "queue_post": ("Paylaşım kuyruğuna gönderi ekler. Kullanıcı onaylayana kadar yayınlanmaz (hesapta otomatik paylaş açık değilse).",
                   obj({"project": STR, "text": STR, "platforms": {"type": "array", "items": {"type": "string", "enum": ["instagram", "x", "linkedin", "youtube"]}},
                        "when": {"type": "number", "description": "unix zamanı, boşsa onay anında"}}, ["project", "text", "platforms"]),
                   lambda a: call("POST", "/api/posts", {"project": a["project"], "captions": {"default": a["text"]}, "platforms": a["platforms"],
                                                         "when": a.get("when"), "source": "mcp", "approved": False})),
    "download_video": ("yt-dlp ile video indirir (TikTok, YouTube, Instagram, X...). Bağlantı tek video, profil ya da hashtag olabilir. "
                       "İndirilenler Kaynaklar'a eklenir. purpose='referans' başkasının içeriği içindir ve paylaşılamaz; 'kaynak' kullanıcının kendi içeriği.",
                       obj({"url": STR, "purpose": {"type": "string", "enum": ["kaynak", "referans"]}, "limit": NUM, "max_dur": NUM, "min_dur": NUM, "min_views": NUM}, ["url"]),
                       lambda a: call("POST", "/api/dl", a)),
    "download_status": ("İndirme işlerinin durumu. job_id verilirse tek iş.", obj({"job_id": STR}),
                        lambda a: call("GET", f"/api/dl/{a['job_id']}" if a.get("job_id") else "/api/dl")),
    "new_reel_from_media": ("Kaynaklar'daki bir videodan yeni reel projesi açar.", obj({"media_id": STR, "title": STR}, ["media_id"]),
                            lambda a: call("POST", "/api/projects/new", a)),
    "search_youtube": ("YouTube'da arar (indirmeden). Sıralama videosu için klip bulmakta kullan.", obj({"q": STR, "n": NUM}, ["q"]),
                       lambda a: call("GET", "/api/dl/search?" + __import__("urllib.parse").parse.urlencode({"q": a["q"], "n": int(a.get("n", 6))}))),
    "find_moment": ("Bir videonun altyazısında ifade arar, zaman damgalarını döner (kesit başlangıcı bulmak için).", obj({"url": STR, "find": STR, "lang": STR}, ["url"]),
                    lambda a: call("GET", "/api/dl/cues?" + __import__("urllib.parse").parse.urlencode({k: a[k] for k in ("url", "find", "lang") if a.get(k)}))),
    "new_ranking": ("Yeni sıralama (5'ten 1'e) projesi açar. Sonra get_reel ile okuyup save_reel ile items[] doldur: {rank,label,sub,comment,credit,url,parts:[[a,b]]}. "
                    "Alıntıları kısa tut (6-15 sn), her sıraya kendi yorumunu yaz, kaynağı belirt.", obj({"title": STR}, ["title"]),
                    lambda a: call("POST", "/api/projects/new", {"title": a["title"], "kind": "ranking"})),
    "youtube_update": ("Yüklenmiş bir YouTube videosunun görünürlüğünü, başlığını ya da açıklamasını değiştirir. Herkese açık yapmak yayınlamaktır: kullanıcı onayı olmadan çağırma.",
                       obj({"video_id": STR, "privacy": {"type": "string", "enum": ["public", "unlisted", "private"]}, "title": STR, "description": STR}, ["video_id"]),
                       lambda a: call("POST", f"/api/youtube/{a['video_id']}", {k: a[k] for k in ("privacy", "title", "description") if k in a})),
    "list_posts": ("Paylaşım kuyruğu ve durumları.", obj({}), lambda a: call("GET", "/api/posts")),
}

def reply(id_, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": id_}
    msg["error" if error else "result"] = error or result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n"); sys.stdout.flush()

def main():
    for line in sys.stdin:
        try: m = json.loads(line)
        except json.JSONDecodeError: continue
        mid, meth, prm = m.get("id"), m.get("method"), m.get("params") or {}
        if mid is None: continue                       # notifications
        if meth == "initialize":
            reply(mid, {"protocolVersion": prm.get("protocolVersion", PROTOCOL), "capabilities": {"tools": {}},
                        "serverInfo": {"name": "biar-edit", "version": "1.0"}})
        elif meth == "tools/list":
            reply(mid, {"tools": [{"name": n, "description": d, "inputSchema": s} for n, (d, s, _) in TOOLS.items()]})
        elif meth == "tools/call":
            n = prm.get("name")
            if n not in TOOLS: reply(mid, error={"code": -32602, "message": f"bilinmeyen araç {n}"}); continue
            out = TOOLS[n][2](prm.get("arguments") or {})
            bad = isinstance(out, dict) and out.get("ok") is False
            reply(mid, {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)[:60000]}], "isError": bad})
        elif meth == "ping":
            reply(mid, {})
        else:
            reply(mid, error={"code": -32601, "message": f"desteklenmiyor: {meth}"})

if __name__ == "__main__":
    main()
