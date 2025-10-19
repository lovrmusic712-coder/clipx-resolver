# app.py
import os
import json
from flask import Flask, request, jsonify
from yt_dlp import YoutubeDL

app = Flask(__name__)

# Accept either API_KEY or APIKEY env var names
API_KEY = os.getenv("API_KEY") or os.getenv("APIKEY") or os.getenv("SECRET_API_KEY")

def _client_key(req):
    # Accept a few header casings
    return (
        req.headers.get("x-api-key")
        or req.headers.get("X-API-Key")
        or req.headers.get("X-Api-Key")
        or req.headers.get("x-apiKey")
    )

@app.get("/health")
def health():
    return "ok", 200

@app.post("/resolve")
def resolve():
    # If an API key is configured, require it
    if API_KEY:
        incoming = _client_key(request)
        if not incoming or incoming != API_KEY:
            return jsonify({"error": "unauthorized"}), 401

    try:
        body = request.get_json(force=True, silent=True) or {}
        url = body.get("url", "").strip()
        if not url:
            return jsonify({"error": "missing url"}), 400

        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
            "extract_flat": False,
            "geo_bypass": True,
            "nocheckcertificate": True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Prefer a direct file URL if present
        direct_url = None
        if "url" in info:
            direct_url = info["url"]
        elif "formats" in info and info["formats"]:
            # choose best video+audio
            best = max(info["formats"], key=lambda f: f.get("height", 0) or 0)
            direct_url = best.get("url")

        if not direct_url:
            return jsonify({"error": "no direct media link found"}), 422

        return jsonify({
            "url": direct_url,
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "webpage_url": info.get("webpage_url", url),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # For local dev only
    app.run(host="0.0.0.0", port=8080)

