"""
runner_bp.py — /run, /stop, /stream, /history routes.

The heavy execution logic lives in services/execution_engine.py.
"""

import json
import time
import uuid
import threading

from flask import Blueprint, request, jsonify, Response, stream_with_context

from backend import logger as _logger
from backend.logger import log_buffer, log_lock
from backend.services.execution_engine import execute_run
from backend.models.module_registry import get_module_keys

runner_bp = Blueprint("runner", __name__)

# ---------------------------------------------------------------------------
# Runtime state (thread-safe)
# ---------------------------------------------------------------------------
running: bool = False
current_run_id: str | None = None
_state_lock = threading.Lock()
_active_proc = None


@runner_bp.route("/run", methods=["POST"])
def run_route():
    global running, current_run_id, _active_proc

    with _state_lock:
        if running:
            return jsonify({"error": "A run is already in progress"}), 409
        running = True

    cfg = request.get_json()
    _logger.reset()

    rid = str(uuid.uuid4())[:8]
    current_run_id = rid

    # Delegate to execution engine
    total, active_modules = execute_run(
        cfg, rid, _logger,
        state_lock=_state_lock,
        get_active_proc=lambda: _active_proc,
        set_active_proc=lambda p: _set_proc(p),
        set_running=lambda v: _set_running(v),
    )

    return jsonify({"status": "started", "run_id": rid, "total": total})


def _set_proc(p):
    global _active_proc
    _active_proc = p


def _set_running(v):
    global running, _active_proc
    with _state_lock:
        running = v
        if not v:
            _active_proc = None


@runner_bp.route("/stop", methods=["POST"])
def stop():
    global running, _active_proc
    import subprocess

    with _state_lock:
        proc = _active_proc

    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception:
            pass

    with _state_lock:
        running = False

    _logger.log("[WARN] Run stopped by user.")
    _logger.log("__ERROR__")
    return jsonify({"status": "stopped"})


@runner_bp.route("/stream")
def stream():
    def generate():
        sent = 0
        while True:
            with log_lock:
                chunk = log_buffer[sent:]
            for line in chunk:
                sent += 1
                yield f"data: {line}\n\n"
                if line in ("__DONE__", "__ERROR__"):
                    return
            time.sleep(0.01)

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@runner_bp.route("/history")
def history():
    from backend.services.db import get_history
    return jsonify(get_history())


@runner_bp.route("/api/modules")
def api_modules():
    """Serve modules.json to the frontend for dynamic registry building."""
    import os
    _PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    modules_path = os.path.join(_PROJECT_ROOT, "modules.json")
    with open(modules_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)
