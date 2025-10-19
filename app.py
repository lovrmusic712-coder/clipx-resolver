# app.py
import os
import json
from flask import Flask, request, jsonify
from yt_dlp import YoutubeDL

app = Flask(__name__)

# Optional auth: if API_KEY exists, we require the matching header.
API_KEY = os.getenv("API_KEY") or os.getenv("APIKEY") or os.getenv("SECRET_API_KEY")

def _client_key(req):
    # Accept a few header casings
    return (
        req.headers.get("x-api-key")
        or req.headers.get("X-API-Key")
        or req.headers.get("X-Api-Key")
        or req.headers.get("xApiKey")
    )

@app.get("/health")
def health():
    return jsonify({"ok": True, "key_required": bool(API_KEY)}), 200

@app.post("/resolve")
def resolve():
    # Enforce key only if configured
    if API_KEY:
        client = _client_key(request)
        if client != API_KEY:
            return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "missing url"}), 400

    # yt_dlp options chosen for reliability; no actual download, just info
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "extract_flat": False,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Try the canonical direct URL
        direct_url = info.get("url")

        # Fallback: pick a sane mp4 format if available
        if not direct_url:
            for f in (info.get("formats") or []):
                # prefer mp4 progressive
                if f.get("ext") == "mp4" and f.get("acodec") not in (None, "none") and f.get("vcodec") not in (None, "none"):
                    direct_url = f.get("url")
                    break
            # ultimate fallback: *any* url
            if not direct_url and info.get("formats"):
                direct_url = info["formats"][-1].get("url")

        if not direct_url:
            return jsonify({"error": "no_direct_link"}), 422

        result = {
            "url": direct_url,
            "title": info.get("title"),
            "duration": info.get("duration"),
            "ext": info.get("ext") or "mp4",
            "thumb": info.get("thumbnail"),
            # pass along a realistic UA—some CDNs check this
            "http_headers": {
                "Accept": "*/*",
                "User-Agent": "Mozilla/5.0",
            },
        }
        return jsonify(result), 200

    except Exception as e:
        # Don’t leak stack traces; return a short error string for the app to show
        return jsonify({"error": "resolve_failed", "detail": str(e)[:200]}), 500

# NOTE: On Render we run via Gunicorn (see Procfile). This block is only for local dev.
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)

