# app.py
import os
import json
from flask import Flask, request, jsonify
from yt_dlp import YoutubeDL

app = Flask(__name__)

# --- Auth ---
# If API_KEY env var is empty, auth is DISABLED (handy for testing).
API_KEY = (os.getenv("API_KEY") or "").strip()

def _client_key(req) -> str:
    """Read client API key from common header spellings."""
    for k in ("x-api-key", "X-API-Key", "X-Api-Key", "x-apiKey", "x_api_key"):
        v = req.headers.get(k)
        if v:
            return v.strip()
    return ""

# --- Health ---
@app.get("/health")
def health():
    return "ok", 200

@app.get("/")
def root():
    return jsonify({"status": "ok", "service": "clipx-resolver"}), 200

# --- Resolve ---
@app.post("/resolve")
def resolve():
    # 1) Optional auth
    if API_KEY:
        if _client_key(request) != API_KEY:
            return jsonify({"error": "unauthorized"}), 401

    # 2) Parse JSON body { "url": "https://..." }
    try:
        data = request.get_json(force=True, silent=False)  # raise if invalid
    except Exception:
        return jsonify({"error": "invalid-json"}), 400

    url = (data or {}).get("url", "").strip()
    if not url:
        return jsonify({"error": "missing-url"}), 400

    # 3) Use yt-dlp to extract direct media URL (no download)
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "bv*+ba/bestaudio/best",
        "http_headers": {
            # Safer headers for some CDNs
            "Accept": "*/*",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
        },
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Pick a good playable URL
        direct = None
        if "url" in info:
            direct = info["url"]
        elif "entries" in info and info["entries"]:
            # playlists / multi-entries
            for entry in info["entries"]:
                if entry and entry.get("url"):
                    direct = entry["url"]
                    info = entry
                    break

        if not direct:
            # Fallback to picking the best format URL
            fmts = info.get("formats") or []
            for f in reversed(fmts):
                if f.get("url"):
                    direct = f["url"]
                    break

        if not direct:
            return jsonify({"error": "no-direct-url-found"}), 422

        resp = {
            "url": direct,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "ext": info.get("ext"),
            "webpage_url": info.get("webpage_url") or url,
        }
        return jsonify(resp), 200

    except Exception as e:
        # Surface a friendly error and a compact message
        msg = str(e)
        if len(msg) > 400:
            msg = msg[:400] + "…"
        return jsonify({"error": "extract-failed", "message": msg}), 500

if __name__ == "__main__":
    # Local dev: python app.py
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))


