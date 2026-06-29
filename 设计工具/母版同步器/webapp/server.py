"""Flask app · server · 本地网页 GUI 入口。薄壳。"""
import os, json
from flask import Flask, render_template, request, jsonify
from webapp.service import (
    scan_general, scan_lessons_up, scan_lessons_down,
    apply_general, apply_lessons_up, apply_lessons_down,
)
from app.bootstrap import create_project as bootstrap_create


def create_app(hub_dir: str | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    if hub_dir is None:
        hub_dir = os.environ.get("HUB_DIR", os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..", "设计工具"))

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/scan")
    def api_scan():
        mode = request.args.get("mode", "general")
        fn = {"general": scan_general, "up": scan_lessons_up, "down": scan_lessons_down}.get(mode)
        if fn is None:
            return jsonify({"error": f"未知模式: {mode}"}), 400
        return jsonify(fn(hub_dir))

    @app.route("/api/apply", methods=["POST"])
    def api_apply():
        body = request.get_json(force=True)
        mode = body.get("mode", "")
        items = body.get("items", [])
        fn = {"general": apply_general, "up": apply_lessons_up, "down": apply_lessons_down}.get(mode)
        if fn is None:
            return jsonify({"error": f"未知模式: {mode}"}), 400
        return jsonify(fn(hub_dir, items))

    @app.route("/api/create-project", methods=["POST"])
    def api_create_project():
        body = request.get_json(force=True)
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"success": False, "error": "项目名不能为空"}), 200
        root = os.path.dirname(os.path.abspath(hub_dir))
        result = bootstrap_create(root, name)
        return jsonify({
            "success": result.success,
            "error": result.error,
            "project_dir": result.project_dir,
            "created_files": result.created_files,
        })

    return app


if __name__ == "__main__":
    hub = os.environ.get("HUB_DIR", None)
    app = create_app(hub)
    app.run(host="127.0.0.1", port=8080, debug=True)
