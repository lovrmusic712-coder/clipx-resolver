import os, shlex, json, time
from flask import Flask, request, jsonify
from subprocess import Popen, PIPE

API_KEY = os.environ.get("CLIPX_API_KEY", "dev-key")
CACHE_TTL = int(os.environ.get("CLIPX_CACHE_TTL", "300"))

app = Flask(__name__)
_cache = {}

def run(cmd, timeout=20):
    p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE, text=True)
    try:
        out, err = p.communicate(timeout=timeout)
    except Exception:
        try: p.kill()
        except: pass
        raise RuntimeError("yt-dlp timeout")
    if p.returncode != 0:
        raise RuntimeError(err[:400] or "yt-dlp failed")
    return out

def pick_best_direct(info):
    if isinstance(info, dict) and info.get("url"):
        return info["url"]
    formats = info.get("formats", []) if isinstance(info, dict) else []
    if not formats:
        return None
    def has_av(f): return f.get("vcodec") != "none" and f.get("acodec") != "none"
    def is_mp4(f): return f.get("ext") == "mp4"
    def looks_nowm(f):
        u = (f.get("url") or "").lower()
        return ("nwm" in u) or ("watermark" not in u)
    candidates = [f for f in formats if f.get("url")]
    candidates.sort(key=lambda f: (
        0 if looks_nowm(f) else 1,
        0 if is_mp4(f) else 1,
        0 if has_av(f) else 1,
        -(f.get("tbr") or 0)
    ))
    return candidates[0].get("url") if candidates else None

@app.post("/resolve")
def resolve():
    if request.headers.get("x-api-key") != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    url = (request.json or {}).get("url", "").strip()
    if not url:
        return jsonify({"error": "missing url"}), 400
    key = f"u:{url}"
    now = time.time()
    if key in _cache and now - _cache[key]["t"] < CACHE_TTL:
        return jsonify(_cache[key]["data"])
    cmd = f'yt-dlp -J --no-warnings --skip-download {shlex.quote(url)}'
    try:
        raw = run(cmd, timeout=25)
        info = json.loads(raw)
    except Exception as e:
        return jsonify({"error": "resolver_failed", "details": str(e)[:200]}), 502
    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]
    direct = pick_best_direct(info)
    if not direct:
        return jsonify({"error": "no_playable_format"}), 404
    payload = {
        "url": direct,
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url"),
        "ext": info.get("ext"),
        "http_headers": info.get("http_headers", {})
    }
    _cache[key] = {"t": now, "data": payload}
    return jsonify(payload)

@app.get("/healthz")
def healthz():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
