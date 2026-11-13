"""Social accounts (X, LinkedIn, Instagram, YouTube) and the post queue.

Each platform needs a developer app you create yourself (client id + secret).  Connecting runs
the platform's OAuth login in your browser and the tokens go to the Keychain.

Posting never happens behind your back: a post made by automation (API / MCP / a rule) waits
in the queue as "onay bekliyor" unless you switched "otomatik paylaş" on for that account.
"""
import base64, hashlib, json, mimetypes, os, secrets, threading, time, urllib.parse, urllib.request, urllib.error, uuid
import settings as S

REDIRECT = "http://localhost:{port}/oauth/callback"
QUEUE = os.path.join(S.APP_DIR, "posts.json")
_qlock = threading.Lock()
_pending = {}          # state -> {"platform", "verifier", "time"}
LINKEDIN_VERSION = "202609"
IG_API = "v23.0"

class SocialError(Exception):
    pass

PLATFORMS = {
    "x": {"name": "X", "scopes": "tweet.read tweet.write users.read media.write offline.access",
          "auth": "https://x.com/i/oauth2/authorize", "token": "https://api.x.com/2/oauth2/token",
          "help": "developer.x.com > Projects & Apps > User authentication: OAuth 2.0, Web App, callback adresi aşağıdaki."},
    "linkedin": {"name": "LinkedIn", "scopes": "openid profile w_member_social",
                 "auth": "https://www.linkedin.com/oauth/v2/authorization", "token": "https://www.linkedin.com/oauth/v2/accessToken",
                 "help": "linkedin.com/developers > uygulama > Products: 'Share on LinkedIn' ve 'Sign In with OpenID Connect' ekle, Auth sekmesine callback adresini yaz."},
    "instagram": {"name": "Instagram", "scopes": "instagram_business_basic,instagram_business_content_publish",
                  "auth": "https://www.instagram.com/oauth/authorize", "token": "https://api.instagram.com/oauth/access_token",
                  "help": "developers.facebook.com > uygulama > Instagram > API setup with Instagram login. Hesap Business veya Creator olmalı. Instagram yalnızca https callback kabul eder: giriş sonrası açılan sayfanın adresini kopyalayıp 'Kodu yapıştır' alanına ver."},
    "youtube": {"name": "YouTube", "scopes": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/youtube.force-ssl",
                "auth": "https://accounts.google.com/o/oauth2/v2/auth", "token": "https://oauth2.googleapis.com/token",
                "help": "console.cloud.google.com > yeni proje > 'YouTube Data API v3'ü etkinleştir > OAuth izin ekranı (External, kendini test kullanıcısı ekle, sonra 'Publish app') > Credentials > OAuth client ID > Web application, Authorized redirect URI: aşağıdaki callback adresi. Girişte Google kanal seçtirir: Ranked Legends'ı seç."},
}
YT_PRIVACY = ("public", "unlisted", "private")

# ---- http helpers --------------------------------------------------------------
def _http(url, data=None, headers=None, method=None, form=False, raw_body=None, want_headers=False, timeout=180):
    h = {"User-Agent": "biar-edit/1.0", **(headers or {})}
    body = raw_body
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode(); h.setdefault("Content-Type", "application/x-www-form-urlencoded")
        else:
            body = json.dumps(data).encode(); h.setdefault("Content-Type", "application/json")
    r = urllib.request.Request(url, data=body, headers=h, method=method or ("POST" if body is not None else "GET"))
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            out = resp.read(); js = json.loads(out) if out and out[:1] in (b"{", b"[") else {}
            return (js, dict(resp.headers)) if want_headers else js
    except urllib.error.HTTPError as e:
        raise SocialError(f"{e.code}: {e.read().decode(errors='replace')[:400]}") from None
    except urllib.error.URLError as e:
        raise SocialError(f"bağlanılamadı: {e.reason}") from None

def _multipart(fields, files):
    b = uuid.uuid4().hex; out = []
    for k, v in fields.items():
        out += [f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()]
    for k, (fn, data, ct) in files.items():
        out += [f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fn}\"\r\nContent-Type: {ct}\r\n\r\n".encode(), data, b"\r\n"]
    out.append(f"--{b}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={b}"

# ---- OAuth ---------------------------------------------------------------------------
def auth_url(platform, port):
    cfg = S.load()["accounts"][platform]; P = PLATFORMS[platform]
    if not cfg.get("client_id") or not S.has_secret(S.SECRET_NAMES[platform]):
        raise SocialError("Önce client id ve client secret gir.")
    state = secrets.token_urlsafe(16); verifier = secrets.token_urlsafe(48)
    _pending[state] = {"platform": platform, "verifier": verifier, "time": time.time()}
    q = {"response_type": "code", "client_id": cfg["client_id"], "redirect_uri": REDIRECT.format(port=port),
         "scope": P["scopes"], "state": state}
    if platform == "youtube":
        q.update(access_type="offline", prompt="consent select_account", include_granted_scopes="true")
    if platform in ("x", "youtube"):
        q["code_challenge"] = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        q["code_challenge_method"] = "S256"
    return P["auth"] + "?" + urllib.parse.urlencode(q)

def finish_oauth(code, state, port):
    st = _pending.pop(state, None)
    if not st or time.time() - st["time"] > 900:
        raise SocialError("Oturum süresi doldu ya da geçersiz. Bağlan'a tekrar bas.")
    p = st["platform"]; cfg = S.load()["accounts"][p]; secret = S.get_secret(S.SECRET_NAMES[p])
    redirect = REDIRECT.format(port=port)
    if p == "x":
        basic = base64.b64encode(f"{cfg['client_id']}:{secret}".encode()).decode()
        tok = _http(PLATFORMS[p]["token"], {"code": code, "grant_type": "authorization_code", "client_id": cfg["client_id"],
                                            "redirect_uri": redirect, "code_verifier": st["verifier"]}, {"Authorization": f"Basic {basic}"}, form=True)
    elif p == "youtube":
        tok = _http(PLATFORMS[p]["token"], {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect, "client_id": cfg["client_id"],
                                            "client_secret": secret, "code_verifier": st["verifier"]}, form=True)
        if not tok.get("refresh_token"):
            raise SocialError("Google yenileme anahtarı vermedi. myaccount.google.com/permissions'dan uygulamanın erişimini kaldırıp tekrar bağlan.")
    elif p == "linkedin":
        tok = _http(PLATFORMS[p]["token"], {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect,
                                            "client_id": cfg["client_id"], "client_secret": secret}, form=True)
    else:
        tok = _http(PLATFORMS[p]["token"], {"client_id": cfg["client_id"], "client_secret": secret, "grant_type": "authorization_code",
                                            "redirect_uri": redirect, "code": code}, form=True)
        long = _http("https://graph.instagram.com/access_token?" + urllib.parse.urlencode(
            {"grant_type": "ig_exchange_token", "client_secret": secret, "access_token": tok["access_token"]}))
        tok = {**tok, **long}
    tok["obtained"] = time.time()
    S.set_json_secret(f"{p}_token", tok)
    handle = whoami(p)
    S.update({"accounts": {p: {"handle": handle}}})
    return p, handle

def code_from_pasted_url(url):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url.strip()).query)
    if "code" not in q or "state" not in q:
        raise SocialError("Adreste code ve state yok. Girişten sonra açılan sayfanın tam adresini yapıştır.")
    return q["code"][0].rstrip("#_"), q["state"][0]

def disconnect(p):
    S.delete_secret(f"{p}_token"); S.update({"accounts": {p: {"handle": ""}}})

def _token(p):
    tok = S.get_json_secret(f"{p}_token")
    if not tok:
        raise SocialError(f"{PLATFORMS[p]['name']} bağlı değil.")
    age = time.time() - tok.get("obtained", 0)
    if p == "x" and tok.get("refresh_token") and age > tok.get("expires_in", 7200) - 120:
        cfg = S.load()["accounts"]["x"]; secret = S.get_secret(S.SECRET_NAMES["x"])
        basic = base64.b64encode(f"{cfg['client_id']}:{secret}".encode()).decode()
        new = _http(PLATFORMS["x"]["token"], {"grant_type": "refresh_token", "refresh_token": tok["refresh_token"], "client_id": cfg["client_id"]},
                    {"Authorization": f"Basic {basic}"}, form=True)
        tok = {**tok, **new, "obtained": time.time()}; S.set_json_secret("x_token", tok)
    if p == "youtube" and age > tok.get("expires_in", 3600) - 120:
        cfg = S.load()["accounts"]["youtube"]; secret = S.get_secret(S.SECRET_NAMES["youtube"])
        try:
            new = _http(PLATFORMS["youtube"]["token"], {"grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
                                                         "client_id": cfg["client_id"], "client_secret": secret}, form=True)
        except SocialError as e:
            if "invalid_grant" in str(e):
                raise SocialError("YouTube bağlantısının süresi doldu. Google projen 'Testing' modundaysa anahtarlar 7 günde biter: OAuth izin ekranında 'Publish app' yap ve tekrar bağlan.") from None
            raise
        tok = {**tok, **new, "obtained": time.time()}; S.set_json_secret("youtube_token", tok)
    if p == "instagram" and age > 30 * 86400:      # long-lived tokens last 60 days; refresh at 30
        new = _http("https://graph.instagram.com/refresh_access_token?" + urllib.parse.urlencode(
            {"grant_type": "ig_refresh_token", "access_token": tok["access_token"]}))
        tok = {**tok, **new, "obtained": time.time()}; S.set_json_secret("instagram_token", tok)
    return tok

def whoami(p):
    t = _token(p)["access_token"]
    if p == "x":
        return "@" + _http("https://api.x.com/2/users/me", headers={"Authorization": f"Bearer {t}"})["data"]["username"]
    if p == "linkedin":
        return _http("https://api.linkedin.com/v2/userinfo", headers={"Authorization": f"Bearer {t}"}).get("name", "")
    if p == "youtube":
        it = (_http("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true", headers={"Authorization": f"Bearer {t}"}).get("items") or [{}])[0]
        sn = it.get("snippet", {}); return sn.get("customUrl") or sn.get("title") or "kanal"
    return "@" + _http(f"https://graph.instagram.com/{IG_API}/me?fields=user_id,username&access_token={t}").get("username", "")

# ---- publishing ---------------------------------------------------------------------------
def post_x(video, text):
    t = _token("x")["access_token"]; H = {"Authorization": f"Bearer {t}"}
    media_ids = []
    if video:
        size = os.path.getsize(video)
        init = _http("https://api.x.com/2/media/upload/initialize", {"media_type": "video/mp4", "total_bytes": size, "media_category": "tweet_video"}, H)
        mid = init["data"]["id"]
        with open(video, "rb") as f:
            i = 0
            while chunk := f.read(4 << 20):
                body, ct = _multipart({"segment_index": str(i)}, {"media": ("chunk.mp4", chunk, "application/octet-stream")})
                _http(f"https://api.x.com/2/media/upload/{mid}/append", headers={**H, "Content-Type": ct}, raw_body=body); i += 1
        fin = _http(f"https://api.x.com/2/media/upload/{mid}/finalize", headers=H, method="POST", raw_body=b"")
        info = (fin.get("data") or {}).get("processing_info")
        while info and info.get("state") in ("pending", "in_progress"):
            time.sleep(info.get("check_after_secs", 3))
            info = (_http(f"https://api.x.com/2/media/upload?command=STATUS&media_id={mid}", headers=H).get("data") or {}).get("processing_info")
        if info and info.get("state") == "failed":
            raise SocialError(f"X video işleyemedi: {info}")
        media_ids = [mid]
    d = _http("https://api.x.com/2/tweets", {"text": text, **({"media": {"media_ids": media_ids}} if media_ids else {})}, H)
    handle = S.load()["accounts"]["x"].get("handle", "").lstrip("@") or "i"
    return f"https://x.com/{handle}/status/{d['data']['id']}"

def post_linkedin(video, text, title=""):
    t = _token("linkedin")["access_token"]
    me = _http("https://api.linkedin.com/v2/userinfo", headers={"Authorization": f"Bearer {t}"})["sub"]
    owner = f"urn:li:person:{me}"
    H = {"Authorization": f"Bearer {t}", "LinkedIn-Version": LINKEDIN_VERSION, "X-Restli-Protocol-Version": "2.0.0"}
    content = {}
    if video:
        size = os.path.getsize(video)
        init = _http("https://api.linkedin.com/rest/videos?action=initializeUpload",
                     {"initializeUploadRequest": {"owner": owner, "fileSizeBytes": size, "uploadCaptions": False, "uploadThumbnail": False}}, H)["value"]
        etags = []
        with open(video, "rb") as f:
            for ins in init["uploadInstructions"]:
                f.seek(ins["firstByte"]); part = f.read(ins["lastByte"] - ins["firstByte"] + 1)
                _, hd = _http(ins["uploadUrl"], headers={"Content-Type": "application/octet-stream"}, raw_body=part, method="PUT", want_headers=True)
                etags.append(hd.get("ETag") or hd.get("etag"))
        _http("https://api.linkedin.com/rest/videos?action=finalizeUpload",
              {"finalizeUploadRequest": {"video": init["video"], "uploadToken": init.get("uploadToken", ""), "uploadedPartIds": etags}}, H)
        content = {"content": {"media": {"title": title or "video", "id": init["video"]}}}
    _, hd = _http("https://api.linkedin.com/rest/posts", {"author": owner, "commentary": text, "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False, **content}, H, want_headers=True)
    urn = hd.get("x-restli-id") or hd.get("X-RestLi-Id") or ""
    return f"https://www.linkedin.com/feed/update/{urn}" if urn else "https://www.linkedin.com/feed/"

def post_instagram(video, text):
    if not video:
        raise SocialError("Instagram gönderisi için video gerekli.")
    tok = _token("instagram"); t = tok["access_token"]
    uid = tok.get("user_id") or _http(f"https://graph.instagram.com/{IG_API}/me?fields=user_id&access_token={t}")["user_id"]
    c = _http(f"https://graph.instagram.com/{IG_API}/{uid}/media", {"media_type": "REELS", "upload_type": "resumable", "caption": text, "access_token": t}, form=True)
    cid = c["id"]; size = os.path.getsize(video)
    with open(video, "rb") as f:
        _http(f"https://rupload.facebook.com/ig-api-upload/{IG_API}/{cid}", headers={"Authorization": f"OAuth {t}", "offset": "0", "file_size": str(size)},
              raw_body=f.read(), method="POST")
    for _ in range(120):
        st = _http(f"https://graph.instagram.com/{IG_API}/{cid}?fields=status_code,status&access_token={t}")
        if st.get("status_code") == "FINISHED": break
        if st.get("status_code") == "ERROR": raise SocialError(f"Instagram videoyu işleyemedi: {st.get('status')}")
        time.sleep(5)
    pub = _http(f"https://graph.instagram.com/{IG_API}/{uid}/media_publish", {"creation_id": cid, "access_token": t}, form=True)
    link = _http(f"https://graph.instagram.com/{IG_API}/{pub['id']}?fields=permalink&access_token={t}").get("permalink")
    return link or "https://www.instagram.com/"

def post_youtube(video, text, publish_at=None):
    """Resumable upload. First line of the caption is the title, the rest the description.
    Credits written next to a ranking render (... - krediler.txt) are appended automatically."""
    if not video: raise SocialError("YouTube için video gerekli.")
    t = _token("youtube")["access_token"]; cfg = S.load()["accounts"]["youtube"]
    lines = (text or "").strip().splitlines()
    title = (lines[0] if lines else os.path.splitext(os.path.basename(video))[0]).strip()
    desc = "\n".join(lines[1:]).strip()
    if cfg.get("shorts_tag", True) and "#shorts" not in (title + desc).lower():
        title = (title[:91] + " #Shorts") if len(title) <= 91 else title[:91] + " #Shorts"
    cred = os.path.splitext(video)[0] + " - krediler.txt"
    if os.path.exists(cred):
        c = open(cred, encoding="utf-8").read().strip()
        if c and c.splitlines()[0] not in desc: desc = (desc + "\n\n" + "Credits:\n" + c).strip()
    body = {"snippet": {"title": title[:100], "description": desc[:4900], "categoryId": str(cfg.get("category", "24")),
                        "defaultLanguage": cfg.get("language", "en")},
            "status": {"privacyStatus": cfg.get("privacy", "public") if cfg.get("privacy") in YT_PRIVACY else "public",
                       "selfDeclaredMadeForKids": False, "embeddable": True}}
    if publish_at and float(publish_at) > time.time() + 20 * 60:     # YouTube publishes it itself at that moment
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(publish_at)))
    size = os.path.getsize(video)
    _, hd = _http("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status", body,
                  {"Authorization": f"Bearer {t}", "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"}, want_headers=True)
    loc = hd.get("Location") or hd.get("location")
    if not loc: raise SocialError("YouTube yükleme adresi vermedi.")
    with open(video, "rb") as f:
        res = _http(loc, headers={"Authorization": f"Bearer {t}", "Content-Type": "video/mp4", "Content-Length": str(size)},
                    raw_body=f.read(), method="PUT", timeout=1800)
    vid = res.get("id")
    if not vid: raise SocialError(f"YouTube yanıtı beklenmedik: {str(res)[:300]}")
    return f"https://youtube.com/shorts/{vid}"

def youtube_update(video_id, privacy=None, title=None, description=None):
    """Change an uploaded video (needs the youtube.force-ssl permission: reconnect once if it was connected before)."""
    t = _token("youtube")["access_token"]; H = {"Authorization": f"Bearer {t}"}
    cur = (_http(f"https://www.googleapis.com/youtube/v3/videos?part=snippet,status&id={video_id}", headers=H).get("items") or [None])[0]
    if not cur: raise SocialError("Video bulunamadı.")
    parts, body = [], {"id": video_id}
    if privacy:
        if privacy not in YT_PRIVACY: raise SocialError("Görünürlük public, unlisted ya da private olmalı.")
        st = cur["status"]; body["status"] = {"privacyStatus": privacy, "selfDeclaredMadeForKids": st.get("selfDeclaredMadeForKids", False),
                                              "embeddable": st.get("embeddable", True), "license": st.get("license", "youtube")}; parts.append("status")
    if title or description is not None:
        sn = cur["snippet"]; body["snippet"] = {"title": (title or sn["title"])[:100], "description": sn.get("description", "") if description is None else description[:4900],
                                                "categoryId": sn.get("categoryId", "24"), "tags": sn.get("tags", [])}; parts.append("snippet")
    if not parts: return cur
    try:
        return _http(f"https://www.googleapis.com/youtube/v3/videos?part={','.join(parts)}", body, H, method="PUT")
    except SocialError as e:
        if "insufficient" in str(e).lower():
            raise SocialError("Bu işlem için yeni bir izin gerekiyor: Hesaplar > YouTube > Yeniden bağlan.") from None
        raise

def youtube_reschedule(video_id, ts):
    """Move a scheduled (private + publishAt) upload to a new publish time."""
    import datetime
    t = _token("youtube")["access_token"]; H = {"Authorization": f"Bearer {t}"}
    cur = (_http(f"https://www.googleapis.com/youtube/v3/videos?part=status&id={video_id}", headers=H).get("items") or [None])[0]
    if not cur: raise SocialError("Video bulunamadı.")
    st = cur["status"]
    if st.get("privacyStatus") != "private" or not st.get("publishAt"): raise SocialError("Video zaten yayında, saati değiştirilemez.")
    iso = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {"id": video_id, "status": {"privacyStatus": "private", "publishAt": iso, "selfDeclaredMadeForKids": st.get("selfDeclaredMadeForKids", False),
                                       "embeddable": st.get("embeddable", True), "license": st.get("license", "youtube")}}
    try: return _http("https://www.googleapis.com/youtube/v3/videos?part=status", body, H, method="PUT")
    except SocialError as e:
        if "insufficient" in str(e).lower():
            raise SocialError("Yayın saatini değiştirmek için yeni bir izin gerekiyor: Hesaplar > YouTube > Yeniden bağlan.") from None
        raise

def set_publish_at(pid, ts):
    """New YouTube publish time for a queued post; if it is already uploaded, YouTube is updated too."""
    p = next((x for x in list_posts() if x["id"] == pid), None)
    if not p: raise SocialError("gönderi yok")
    t = p["targets"].get("youtube") or {}
    if t.get("status") == "paylaşıldı" and t.get("url"):
        youtube_reschedule(t["url"].rstrip("/").split("/")[-1], ts)
    with _qlock:
        q = _load_q()
        for x in q:
            if x["id"] == pid: x.setdefault("options", {}).setdefault("youtube", {})["publish_at"] = ts
        _save_q(q)

POSTERS = {"x": post_x, "linkedin": post_linkedin, "instagram": post_instagram, "youtube": post_youtube}

# ---- queue ------------------------------------------------------------------------------------
def _load_q():
    try: return json.load(open(QUEUE))
    except (FileNotFoundError, json.JSONDecodeError): return []

def _save_q(q):
    os.makedirs(S.APP_DIR, exist_ok=True); tmp = QUEUE + ".tmp"
    json.dump(q, open(tmp, "w"), ensure_ascii=False, indent=1); os.replace(tmp, QUEUE)

def list_posts():
    with _qlock: return _load_q()

def create_post(video, captions, platforms, when=None, source="arayüz", approved=False, project=None, options=None):
    """captions: {"default": str, "x": str, ...}.  approved=False puts it in the approval list,
    unless the account has auto_post on and the request came from automation."""
    acc = S.load()["accounts"]
    if video and not os.path.isfile(video):
        raise SocialError("Video dosyası bulunamadı.")
    targets = {}
    for p in platforms:
        if p not in POSTERS: raise SocialError(f"bilinmeyen platform: {p}")
        ok = approved or (source != "arayüz" and acc[p].get("auto_post"))
        targets[p] = {"status": "bekliyor" if ok else "onay bekliyor", "url": None, "error": None}
    post = {"id": uuid.uuid4().hex[:10], "created": time.time(), "source": source, "project": project, "video": video,
            "captions": captions, "when": when or time.time(), "targets": targets, "options": options or {}}
    with _qlock:
        q = _load_q(); q.insert(0, post); _save_q(q)
    return post

def edit_post(pid, patch):
    with _qlock:
        q = _load_q()
        for p in q:
            if p["id"] == pid:
                for k in ("captions", "when"):
                    if k in patch: p[k] = patch[k]
                if patch.get("approve"):
                    for t in p["targets"].values():
                        if t["status"] in ("onay bekliyor", "hata"): t["status"] = "bekliyor"; t["error"] = None
                if patch.get("cancel"):
                    for t in p["targets"].values():
                        if t["status"] in ("onay bekliyor", "bekliyor"): t["status"] = "iptal"
                _save_q(q); return p
    raise SocialError("gönderi yok")

def delete_post(pid):
    with _qlock:
        q = [p for p in _load_q() if p["id"] != pid]; _save_q(q)

def _set_target(pid, plat, **kw):
    with _qlock:
        q = _load_q()
        for p in q:
            if p["id"] == pid: p["targets"][plat].update(kw)
        _save_q(q)

def run_due():
    now = time.time()
    for p in list_posts():
        if p["when"] > now: continue
        for plat, t in p["targets"].items():
            if t["status"] != "bekliyor": continue
            _set_target(p["id"], plat, status="paylaşılıyor")
            try:
                cap = p["captions"].get(plat) or p["captions"].get("default", "")
                url = POSTERS[plat](p["video"], cap, **((p.get("options") or {}).get(plat) or {}))
                _set_target(p["id"], plat, status="paylaşıldı", url=url, posted=time.time())
            except Exception as e:      # keep the queue alive, show the reason in the UI
                _set_target(p["id"], plat, status="hata", error=str(e)[:500])

def start_scheduler():
    # anything left "paylaşılıyor" by a crash goes back to the approval list instead of re-posting
    with _qlock:
        q = _load_q()
        for p in q:
            for t in p["targets"].values():
                if t["status"] == "paylaşılıyor": t["status"] = "onay bekliyor"; t["error"] = "Uygulama paylaşım sırasında kapandı, kontrol edip tekrar onayla."
        _save_q(q)
    def loop():
        while True:
            try: run_due()
            except Exception: pass
            time.sleep(15)
    threading.Thread(target=loop, daemon=True).start()
