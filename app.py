"""EcoScan — Intelligent Plastic Waste Detection and Environmental Action System.

Detect → Understand → Act → Track
"""

import logging
import os
import re

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, render_template, request

from services import ai, knowledge
from services.store import make_store, summarize

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ecoscan")

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "image/gif"}
CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def create_app(store=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB uploads
    app.store = store or make_store(app.instance_path)
    log.info("Storage backend: %s", app.store.kind)

    def client_id():
        cid = request.headers.get("X-Client-Id", "")
        return cid if CLIENT_ID_RE.match(cid) else None

    def demo_mode():
        return not os.getenv("OPENROUTER_API_KEY")

    @app.context_processor
    def inject_globals():
        return {"demo_mode": demo_mode()}

    # ---------- pages ----------
    @app.get("/")
    def index():
        return render_template("index.html", page="home")

    @app.get("/scan")
    def scan_page():
        return render_template("scan.html", page="scan")

    @app.get("/dashboard")
    def dashboard_page():
        return render_template("dashboard.html", page="dashboard")

    @app.get("/guide")
    def guide_page():
        return render_template("guide.html", page="guide",
                               resins=knowledge.RESINS, categories=knowledge.CATEGORIES,
                               bins=knowledge.BINS)

    @app.get("/scan/<scan_id>")
    def scan_detail(scan_id):
        try:
            scan = app.store.get(scan_id)
        except Exception:
            log.exception("Store read failed")
            abort(503)
        if not scan:
            abort(404)
        return render_template("scan_detail.html", page="dashboard", scan=scan)

    # ---------- API ----------
    @app.get("/api/health")
    def health():
        return jsonify(ok=True, storage=app.store.kind, demo=demo_mode())

    @app.post("/api/scan")
    def api_scan():
        upload = request.files.get("image")
        if not upload or not upload.filename:
            return jsonify(error="Please choose or capture a photo first."), 400
        if upload.mimetype not in ALLOWED_TYPES:
            return jsonify(error="Unsupported file type. Use a JPG, PNG or WEBP photo."), 400

        try:
            jpeg, thumb = ai.prepare_image(upload.read())
        except ai.AIError as exc:
            return jsonify(error=str(exc)), 400

        demo = demo_mode()
        if demo:
            detection, model = ai.DEMO_DETECTION, "demo"
        else:
            try:
                detection, model = ai.detect(jpeg)
            except ai.AIError as exc:
                log.warning("Detection failed: %s", exc)
                return jsonify(error=str(exc)), 502

        analysis = knowledge.enrich(detection)
        scan = {"id": None, "demo": demo, "model": model, "thumbnail": thumb, "analysis": analysis}
        try:
            saved = app.store.save(client_id(), analysis, thumb, model, demo)
            scan["id"] = saved["id"]
            scan["created_at"] = saved["created_at"]
        except Exception:
            # Detection still succeeded — show it even if history couldn't be saved.
            log.exception("Saving scan failed")
            scan["save_error"] = "Result could not be saved to history."
        return jsonify(scan)

    @app.get("/api/history")
    def api_history():
        cid = client_id()
        if not cid:
            return jsonify(scans=[])
        try:
            rows = app.store.list(cid, limit=50)
        except Exception:
            log.exception("Store read failed")
            return jsonify(error="History is temporarily unavailable."), 503
        return jsonify(scans=[{k: r[k] for k in ("id", "created_at", "thumbnail", "total_items",
                                                  "co2_saved_kg", "points", "level", "demo")}
                              | {"summary": r["analysis"].get("summary", "")} for r in rows])

    @app.get("/api/stats")
    def api_stats():
        cid = client_id()
        try:
            mine = summarize(app.store.list(cid, limit=500)) if cid else summarize([])
            community = summarize(app.store.list(None, limit=1000))
        except Exception:
            log.exception("Store read failed")
            return jsonify(error="Stats are temporarily unavailable."), 503
        labels = {k: v["label"] for k, v in knowledge.CATEGORIES.items()}
        return jsonify(mine=mine, community=community, category_labels=labels)

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error="Photo is too large (max 10 MB)."), 413

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_DEBUG") == "1")
