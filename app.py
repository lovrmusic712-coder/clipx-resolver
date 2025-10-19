# app.py
import os
import json
from urllib.parse import urlparse

from flask import Flask, request, jsonify
from yt_dlp import YoutubeDL

app = Flask(__name__)

# ── API key handling ───────────────────────────────────────────────────────────
# If you set API_KEY in Render → Environment, clients MUST send that same key
# in header:  x-api-key: <your-key>
# If API_KEY is not set, we accept the fallback "dev-key".
API_KEY = os.getenv("API_KEY") or os.getenv("APIKEY") or os.getenv("SECRET_API_KEY")

def _client_key(req):
    # accept common casings
    return (
        req.headers.get("x-api-key")
        or req.headers.get("X-API-Key")
        or req.headers.get("X-Api-Key")
        or req.headers.get("xApiKey")
    )

# ── health check ───────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "key_required": bool(API_KEY)
    }), 200

# ── main resolver ─────────────────────────────────────────────────────────────
@app.post("/resolve")
def resolve():
    # 1) Auth (only if API_KEY configured)
    if API_KEY:
        client = _client_key(request)
        if not client or client != API_KEY:
            return jsonify({"error": "unauthorized"}), 401
    else:
        # no API key configured → allow "dev-key" as default to avoid surprises
        client = _client_key(request)
        if client and client != "dev-key":
            # If they send a wrong key when no key is required, just ignore it.
            pass

    # 2) Parse body
    try:
        body = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"error": "invalid_json"}), 400

    url = (body or {}).get("url", "").strip()
    if not url:
        return jsonify({"error": "missing url"}), 400
    # quick sanity check
    try:
        p = urlparse(url)
        if not p.scheme or not p.netloc:
            raise ValueError()
    except Exception:
        return jsonify({"error": "bad url"}), 400

    # 3) Use yt_dlp to extract a direct media URL
    # Disable downloads; just get info
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "geo_bypass": True,
        "http_headers": {
            # helps for some sources
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
        },
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return jsonify({"error": "extract_failed", "detail": str(e)}), 422

    # 4) Choose a downloadable URL
    direct_url = None
    title = info.get("title")
    thumbnail = info.get("thumbnail")

    # Most sites provide 'url' at the top level
    if isinstance(info, dict) and info.get("url"):
        direct_url = info["url"]

    # Otherwise pick the first reasonable mp4 video format
    if not direct_url:
        for f in (info.get("formats") or []):
            u = f.get("url")
            if not u:
                continue
            mime = f.get("ext") or ""
            if "mp4" in mime or f.get("vcodec"):
                direct_url = u
                break

    if not direct_url:
        return jsonify({"error": "no_direct_url"}), 404

    # 5) Return clean JSON for the app
    return jsonify({
        "url": direct_url,
        "title": title,
        "thumbnail": thumbnail,
        "webpage_url": info.get("webpage_url") or url,
        "duration": info.get("duration"),
        "ext": info.get("ext") or "mp4",
        "http_headers": {
            # send back headers some CDNs require when you download
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*"
        }
    }), 200

if __name__ == "__main__":
    # local run:  python app.py
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
