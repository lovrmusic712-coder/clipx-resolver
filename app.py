# app.py
import os, json
from flask import Flask, request, jsonify
from yt_dlp import YoutubeDL

app = Flask(__name__)

# --- Config ---
# Required API key (set this in Render "Environment" as API_KEY)
API_KEY = os.getenv("API_KEY") or os.getenv("APIKEY") or os.getenv("SECRET_API_KEY") or ""
# Optional: allow a dev key ("dev-key") for quick testing: set ALLOW_DEV_KEY=1 in Render to enable
ALLOW_DEV_KEY = os.getenv("ALLOW_DEV_KEY", "0") in ("1", "true", "TRUE", "yes", "YES")

def _client_key(req):
    """Accept common header casings."""
    return (
        req.headers.get("x-api-key")
        or req.headers.get("X-API-Key")
        or req.headers.get("X-Api-Key")
        or req.headers.get("x-apiKey")
    )

@app.get("/health")
def health():
    # Do NOT leak your key. Just show whether it's set.
    return jsonify(ok=True, key_status=("set" if bool(API_KEY) else "empty")), 200

@app.post("/resolve")
def resolve():
    # 1) API key gate
    client_key = _client_key(request)
    if API_KEY:  # gate only if a key is configured
        if not client_key:
            return jsonify(error="unauthorized", reason="missing x-api-key header"), 401
        if client_key != API_KEY:
            # Allow dev key only if enabled (handy on free Render cold-starts)
            if not (ALLOW_DEV_KEY and client_key == "dev-key"):
                return jsonify(error="unauthorized", reason="x-api-key does not match"), 401
    # If API_KEY is empty, endpoint is open (not recommended for production)

    # 2) Parse JSON body
    try:
        body = request.get_json(silent=True) or {}
    except Exception:
        return jsonify(error="bad_request", reason="invalid json"), 400

    url = (body.get("url") or "").strip()
    if not url:
        return jsonify(error="bad_request", reason="missing url"), 400

    # 3) Resolve with yt-dlp
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "noprogress": True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            best = info.get("url")
            title = info.get("title")
            thumb = info.get("thumbnail")
            if not best:
                return jsonify(error="no_media", reason="no direct url in extractor output"), 422

            return jsonify(
                url=best,
                title=title,
                thumbnail=thumb,
                duration=info.get("duration"),
                ext=info.get("ext"),
                http_headers=info.get("http_headers"),
            ), 200
    except Exception as e:
        return jsonify(error="resolver_failed", detail=str(e)), 500
