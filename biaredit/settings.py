"""Settings and secrets.

Plain settings (which provider is on, default model, Ollama address, client ids) live in
~/Library/Application Support/biar-edit/config.json.  Anything secret (API keys, client
secrets, OAuth tokens) goes to the macOS Keychain under the service "biar-edit" and never
into a file in the project, so a project folder can be shared or zipped safely.
"""
import json, os, secrets as _secrets, subprocess, threading

APP_DIR = os.path.expanduser("~/Library/Application Support/biar-edit")
CONFIG = os.path.join(APP_DIR, "config.json")
SERVICE = "biar-edit"
_lock = threading.Lock()

DEFAULTS = {
    "providers": {
        "anthropic": {"enabled": False, "default_model": "claude-sonnet-5-5"},
        "openrouter": {"enabled": False, "default_model": ""},
        "ollama": {"enabled": True, "base_url": "http://localhost:11434", "default_model": ""},
        "elevenlabs": {"enabled": False, "voice_id": "", "model_id": "eleven_multilingual_v2"},
    },
    "default_text_provider": "anthropic",
    "accounts": {
        "x": {"client_id": "", "connected": False, "handle": "", "auto_post": False},
        "linkedin": {"client_id": "", "connected": False, "handle": "", "auto_post": False},
        "instagram": {"client_id": "", "connected": False, "handle": "", "auto_post": False},
        "youtube": {"client_id": "", "connected": False, "handle": "", "auto_post": False, "privacy": "public", "shorts_tag": True, "category": "24", "language": "en"},
    },
    "voices": [],
    "export_dir": os.path.expanduser("~/Desktop/untitled folder/reels"),
    "automation": {"caption_prompt": "Bu reels için kısa, samimi bir Instagram açıklaması yaz. Türkçe, en fazla 3 cümle, sonunda 5-7 hashtag. Uzun çizgi (em dash) kullanma."},
}

def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out

def load():
    with _lock:
        try:
            return _merge(DEFAULTS, json.load(open(CONFIG)))
        except (FileNotFoundError, json.JSONDecodeError):
            return json.loads(json.dumps(DEFAULTS))

def save(cfg):
    with _lock:
        os.makedirs(APP_DIR, exist_ok=True)
        tmp = CONFIG + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        os.chmod(tmp, 0o600); os.replace(tmp, CONFIG)

def update(patch):
    cfg = _merge(load(), patch); save(cfg); return cfg

# ---- Keychain ---------------------------------------------------------------
def get_secret(name):
    r = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-a", name, "-w"], capture_output=True, text=True)
    return r.stdout.rstrip("\n") if r.returncode == 0 else None

def set_secret(name, value):
    if not value:
        return delete_secret(name)
    subprocess.run(["security", "add-generic-password", "-U", "-s", SERVICE, "-a", name, "-w", value],
                   capture_output=True, check=True)

def delete_secret(name):
    subprocess.run(["security", "delete-generic-password", "-s", SERVICE, "-a", name], capture_output=True)

def has_secret(name):
    return get_secret(name) is not None

def get_json_secret(name):
    v = get_secret(name)
    try:
        return json.loads(v) if v else None
    except json.JSONDecodeError:
        return None

def set_json_secret(name, obj):
    set_secret(name, json.dumps(obj) if obj else "")

# ---- local API token ----------------------------------------------------------
def api_token():
    """Token that every state-changing request must carry (header X-Biar-Token).
    Web pages from other sites cannot read it, so they cannot drive the editor or post for you."""
    t = get_secret("api_token")
    if not t:
        t = _secrets.token_urlsafe(24); set_secret("api_token", t)
    return t

SECRET_NAMES = {
    "anthropic": "anthropic_api_key", "openrouter": "openrouter_api_key", "elevenlabs": "elevenlabs_api_key",
    "x": "x_client_secret", "linkedin": "linkedin_client_secret", "instagram": "instagram_client_secret",
    "youtube": "youtube_client_secret",
}

def public_view():
    """Config for the UI: secrets replaced by a has-key flag."""
    cfg = load()
    for p in cfg["providers"]:
        if p in SECRET_NAMES:
            cfg["providers"][p]["has_key"] = has_secret(SECRET_NAMES[p])
    for a in cfg["accounts"]:
        cfg["accounts"][a]["has_secret"] = has_secret(SECRET_NAMES[a])
        cfg["accounts"][a]["connected"] = get_json_secret(f"{a}_token") is not None
    return cfg
