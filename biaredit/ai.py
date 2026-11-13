"""One interface for every model provider.

  models(provider)                       -> [{"id", "name", "ctx"}]
  chat(provider, model, messages, system) -> text
  voices() / tts(text, voice_id)         -> ElevenLabs

Providers: anthropic (Claude), openrouter (hundreds of hosted models), ollama (local open
models), elevenlabs (voice).  OpenRouter and Ollama both speak the OpenAI chat format, so
adding another OpenAI-compatible host is one entry in OPENAI_COMPAT.
"""
import json, os, urllib.error, urllib.request
import settings as S

TIMEOUT = 120

class AIError(Exception):
    pass

def _req(url, data=None, headers=None, method=None, raw=False, timeout=TIMEOUT):
    body = json.dumps(data).encode() if data is not None and not isinstance(data, bytes) else data
    h = {"Content-Type": "application/json", "User-Agent": "biar-edit/1.0", **(headers or {})}
    r = urllib.request.Request(url, data=body, headers=h, method=method or ("POST" if body is not None else "GET"))
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            out = resp.read()
            return out if raw else json.loads(out or b"{}")
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")[:400]
        raise AIError(f"{e.code}: {msg}") from None
    except urllib.error.URLError as e:
        raise AIError(f"bağlanılamadı: {e.reason}") from None

def _key(provider):
    k = S.get_secret(S.SECRET_NAMES[provider])
    if not k:
        raise AIError(f"{provider} için API anahtarı yok. Ayarlar > Modeller'den ekle.")
    return k

def _ollama_url():
    return S.load()["providers"]["ollama"]["base_url"].rstrip("/")

OPENAI_COMPAT = {
    "openrouter": lambda: ("https://openrouter.ai/api/v1", {"Authorization": f"Bearer {_key('openrouter')}",
                                                            "HTTP-Referer": "http://localhost", "X-Title": "biar-edit"}),
    "ollama": lambda: (_ollama_url() + "/v1", {}),
}

def models(provider):
    if provider == "anthropic":
        d = _req("https://api.anthropic.com/v1/models?limit=100", headers={"x-api-key": _key("anthropic"), "anthropic-version": "2023-06-01"})
        return [{"id": m["id"], "name": m.get("display_name", m["id"])} for m in d.get("data", [])]
    if provider == "openrouter":
        d = _req("https://openrouter.ai/api/v1/models")          # public list, no key needed
        return sorted(({"id": m["id"], "name": m.get("name", m["id"]), "ctx": m.get("context_length")} for m in d.get("data", [])),
                      key=lambda m: m["name"].lower())
    if provider == "ollama":
        try:
            d = _req(_ollama_url() + "/api/tags", timeout=5)
        except AIError as e:
            if "bağlanılamadı" in str(e):
                raise AIError("Ollama çalışmıyor. Ollama uygulamasını aç ya da terminalde 'ollama serve' çalıştır.") from None
            raise
        return [{"id": m["name"], "name": m["name"], "size": m.get("size")} for m in d.get("models", [])]
    if provider == "elevenlabs":
        return [{"id": v["voice_id"], "name": v["name"]} for v in voices()]
    raise AIError(f"bilinmeyen sağlayıcı: {provider}")

def chat(provider, model, messages, system=None, max_tokens=1024, temperature=0.7):
    """messages: [{"role": "user"|"assistant", "content": str}]"""
    cfg = S.load()["providers"]
    model = model or cfg.get(provider, {}).get("default_model")
    if not model:
        raise AIError(f"{provider} için model seçilmedi.")
    if provider == "anthropic":
        body = {"model": model, "max_tokens": max_tokens, "messages": messages, "temperature": temperature}
        if system:
            body["system"] = system
        d = _req("https://api.anthropic.com/v1/messages", body,
                 {"x-api-key": _key("anthropic"), "anthropic-version": "2023-06-01"})
        return "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    if provider in OPENAI_COMPAT:
        base, h = OPENAI_COMPAT[provider]()
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        d = _req(base + "/chat/completions", {"model": model, "messages": msgs, "max_tokens": max_tokens,
                                              "temperature": temperature, "stream": False}, h)
        try:
            return d["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError):
            raise AIError(f"beklenmeyen yanıt: {json.dumps(d)[:300]}") from None
    raise AIError(f"{provider} metin modeli değil.")

def test(provider):
    """Cheap connectivity check used by the settings page."""
    if provider == "elevenlabs":
        return {"ok": True, "detail": f"{len(voices())} ses bulundu"}
    ms = models(provider)
    return {"ok": True, "detail": f"{len(ms)} model bulundu"}

# ---- ElevenLabs ---------------------------------------------------------------
def voices():
    d = _req("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": _key("elevenlabs")})
    return d.get("voices", [])

def voice_profile(pid=None):
    cfg = S.load(); vs = cfg.get("voices") or []
    if pid: return next((v for v in vs if v["id"] == pid), None)
    return next((v for v in vs if v.get("default")), vs[0] if vs else None)

def tts(text, voice_id=None, model_id=None, profile=None):
    """profile: a saved voice profile id (Ses > Ses modelleri) with its own voice settings."""
    c = S.load()["providers"]["elevenlabs"]; pr = voice_profile(profile) if profile or not voice_id else None
    voice_id = voice_id or (pr or {}).get("voice_id") or c.get("voice_id")
    if not voice_id:
        raise AIError("Ses seçilmedi. Ses > Ses modelleri'nden bir ses ekle.")
    body = {"text": text, "model_id": model_id or (pr or {}).get("model_id") or c.get("model_id") or "eleven_multilingual_v2"}
    if pr:
        body["voice_settings"] = {"stability": pr.get("stability", 0.5), "similarity_boost": pr.get("similarity", 0.75),
                                  "style": pr.get("style", 0.0), "use_speaker_boost": True, "speed": pr.get("speed", 1.0)}
    return _req(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128", body,
                {"xi-api-key": _key("elevenlabs"), "Accept": "audio/mpeg"}, raw=True)

def clone_voice(name, files, description=""):
    """ElevenLabs instant voice clone from your own recordings. Returns the new voice id."""
    import uuid as _u, mimetypes
    b = _u.uuid4().hex; parts = []
    for k, v in (("name", name), ("description", description)):
        parts.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for f in files:
        ct = mimetypes.guess_type(f)[0] or "audio/mpeg"
        parts += [f"--{b}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{os.path.basename(f)}\"\r\nContent-Type: {ct}\r\n\r\n".encode(),
                  open(f, "rb").read(), b"\r\n"]
    parts.append(f"--{b}--\r\n".encode())
    d = _req("https://api.elevenlabs.io/v1/voices/add", b"".join(parts),
             {"xi-api-key": _key("elevenlabs"), "Content-Type": f"multipart/form-data; boundary={b}"})
    return d["voice_id"]

def pick_text_provider():
    cfg = S.load()
    order = [cfg.get("default_text_provider")] + ["anthropic", "openrouter", "ollama"]
    for p in order:
        pc = cfg["providers"].get(p)
        if pc and pc.get("enabled") and pc.get("default_model"):
            return p, pc["default_model"]
    raise AIError("Açık ve varsayılan modeli seçilmiş bir metin sağlayıcısı yok. Ayarlar > Modeller.")
