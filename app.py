import os
import json
from flask import Flask, request, jsonify
from yt_dlp import YoutubeDL

app = Flask(__name__)

# Read API key from env (Render Dashboard → Environment → API_KEY)
API_KEY = (os.getenv("API_KEY") or os.getenv("APIKEY") or os.getenv("SECRET_API_KEY") or "").strip()

def _get_client_key(req: request) -> str | None:
    """
    Try multiple places/casings and trim whitespace.
    Also allow ?key=... as a fallback for easier testing.
    """
    # Query param (for quick tests in tools)
    qk = req.args.get("key")
    if qk:
        return qk.strip()

    # Common header casings
    for name in [
        "x-api-key", "X-API-Key", "X-Api-Key", "x-apiKey", "X-APIKEY", "apikey", "Api-Key"
    ]:
        v = req.headers.get(name)
        if v:
            return v.strip()
    return None

@app.get("/health")
def health():
    return jsonify({"ok": True, "key_required": bool(API_KEY)}), 200

@app.post("/resolve")
def resolve():
    # Require a key if one is configured
    if API_KEY:
        client_key = _get_client_key(request)
        if not client_key:
            return jsonify({"error": "unauthorized", "why": "missing key"}), 401
        if client_key != API_KEY:
            return jsonify({"error": "unauthorized", "why": "key mismatch"}), 401

    try:
        body = request.get_json(silent=True) or {}
        url = (body.get("url") or "").strip()
        if not url:
            return jsonify({"error": "bad_request", "why": "missing url"}), 400

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
            "noplaylist": True,
            # Faster direct URL extraction
            "forcejson": True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Try to find a direct media URL
        direct_url = None

        # 1) formats list
        for f in (info.get("formats") or []):
            if f.get("url") and ("video" in (f.get("vcodec") or "") or f.get("acodec")):
                direct_url = f["url"]
                break

        # 2) top-level url (some sites put it here)
        if not direct_url and info.get("url"):
            direct_url = info["url"]

        if not direct_url:
            return jsonify({"error": "no_direct_link"}), 422

        return jsonify({
            "url": direct_url,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "ext": info.get("ext"),
            "http_headers": info.get("http_headers"),
        }), 200

    except Exception as e:
        return jsonify({"error": "resolver_failed", "detail": str(e)}), 500
