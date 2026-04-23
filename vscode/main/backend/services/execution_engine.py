"""
execution_engine.py — Module orchestration.

Manages the execution of automation modules in a background thread.
Uses module_registry instead of hardcoded MODULE_KEYS.
"""

import os
import sys
import json
import time
import threading
import subprocess

from backend.models.module_registry import (
    get_module_keys,
    get_idx_to_flag_map,
    get_flag_to_idx_map,
)

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_true(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "on")
    return bool(v)


def execute_run(cfg, rid, logger, state_lock, get_active_proc, set_active_proc, set_running):
    """
    Prepare and launch the automation run in a background thread.
    Returns (total_modules, active_modules_list).
    """
    MODULE_KEYS = get_module_keys()
    idx_to_flag = get_idx_to_flag_map()
    flag_to_idx = get_flag_to_idx_map()
    name_to_flag = {name: key for key, name in MODULE_KEYS}
    flag_to_name = {key: name for key, name in MODULE_KEYS}

    # Coerce all module flags to real booleans early.
    for key, _ in MODULE_KEYS:
        if key in cfg:
            cfg[key] = _is_true(cfg.get(key))

    # Handle legacy key: run_locatio_setup → run_location_setup
    if "run_locatio_setup" in cfg and "run_location_setup" not in cfg:
        cfg["run_location_setup"] = cfg.pop("run_locatio_setup")

    # Normalise cfg.modules → boolean flags (backward compat)
    modules_list = cfg.get("modules")
    if modules_list and isinstance(modules_list, list):
        for item in modules_list:
            if isinstance(item, str) and item in name_to_flag:
                cfg[name_to_flag[item]] = True

    # Special case: idx 6 can be either Audit_Plan OR Ad_hoc
    def _resolve_idx6_flag(cfg: dict) -> str:
        if cfg.get("run_create_Ad_hoc_Audit"):
            return "run_create_Ad_hoc_Audit"
        return "run_create_audit"

    # Build active_modules in drag priority order
    order = cfg.get("MODULE_RUN_ORDER")
    active_modules: list[tuple[str, str]] = []

    if order and isinstance(order, list):
        seen: set[str] = set()
        for item in order:
            flag = None
            if isinstance(item, int):
                if item == 6:
                    flag = _resolve_idx6_flag(cfg)
                else:
                    flag = idx_to_flag.get(item)
            elif isinstance(item, str):
                flag = item if item.startswith("run_") else name_to_flag.get(item)

            if not flag or flag in seen:
                continue
            seen.add(flag)

            if cfg.get(flag):
                active_modules.append((flag, flag_to_name.get(flag, flag)))

        if not active_modules:
            active_modules = [(k, n) for k, n in MODULE_KEYS if cfg.get(k)]
    else:
        active_modules = [(k, n) for k, n in MODULE_KEYS if cfg.get(k)]

    total = max(len(active_modules), 1)

    def execute():
        from backend.services.db import db_insert_step, db_finish_run
        from backend.services.config_builder import build_config_py

        try:
            logger.log(json.dumps({
                "type": "init",
                "run_id": rid,
                "total": total,
                "modules": [n for _, n in active_modules],
            }))

            single_process = os.getenv("QA_RUNNER_SINGLE_PROCESS", "1").strip().lower() in ("1", "true", "yes", "on")

            if single_process:
                cfg["MODULE_RUN_ORDER"] = [flag for flag, n in active_modules]
                config_path = os.path.join(_BASE, "backend", "Config.py")
                with open(config_path, "w", encoding="utf-8") as fp:
                    fp.write(build_config_py(cfg))

                logger.log("\n[INFO] ▶ Launching: Full flow (single process)")
                logger.log("─" * 52)

                runner_path = os.path.join(_BASE, "backend", "runner.py")
                launch_cmd = [sys.executable, "-u", runner_path]

                env = dict(os.environ)
                env["PYTHONUNBUFFERED"] = "1"

                proc = subprocess.Popen(
                    launch_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=_BASE,
                    env=env,
                    bufsize=1,
                )

                with state_lock:
                    set_active_proc(proc)

                for line in iter(proc.stdout.readline, ""):
                    stripped = line.rstrip()
                    logger.log(stripped)

                proc.wait()

                if proc.returncode != 0:
                    logger.log(f"❌ Aborted: flow failed (exit {proc.returncode})")
                    db_finish_run(rid, "error")
                    return

                db_insert_step(rid, "Full flow", "done", 100)
            else:
                done_count = 0
                for flag, mname in active_modules:
                    module_cfg = dict(cfg)
                    for k, _ in MODULE_KEYS:
                        if module_cfg.get(k):
                            module_cfg[k] = False
                    module_cfg[flag] = True

                    target_idx = flag_to_idx.get(flag)
                    module_cfg["MODULE_RUN_ORDER"] = [target_idx] if target_idx is not None else []

                    config_path = os.path.join(_BASE, "backend", "Config.py")
                    with open(config_path, "w", encoding="utf-8") as fp:
                        fp.write(build_config_py(module_cfg))

                    logger.log(f"\n[INFO] ▶ Launching: {mname}")
                    logger.log("─" * 52)

                    runner_path = os.path.join(_BASE, "backend", "runner.py")
                    launch_cmd = [sys.executable, "-u", runner_path]

                    env = dict(os.environ)
                    env["PYTHONUNBUFFERED"] = "1"

                    proc = subprocess.Popen(
                        launch_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        cwd=_BASE,
                        env=env,
                        bufsize=1,
                    )

                    with state_lock:
                        set_active_proc(proc)

                    module_failed = False
                    for line in iter(proc.stdout.readline, ""):
                        stripped = line.rstrip()
                        logger.log(stripped)
                        sl = stripped.lower()
                        if ("playwright error" in sl
                                or "unexpected error" in sl
                                or ("error" in sl and "audit name already exists" in sl)):
                            module_failed = True

                    proc.wait()

                    if proc.returncode != 0 or module_failed:
                        logger.log(f"❌ Aborted: {mname} failed (exit {proc.returncode})")
                        db_finish_run(rid, "error")
                        return

                    done_count = min(done_count + 1, total)
                    pct = int(done_count / total * 100)

                    logger.log(json.dumps({
                        "type": "progress",
                        "step": mname,
                        "progress": pct,
                        "done": done_count,
                        "total": total,
                    }))

                    db_insert_step(rid, mname, "done", pct)

            logger.log("─" * 52)
            logger.log("[OK] Run completed successfully.")
            logger.log(json.dumps({
                "type": "progress",
                "progress": 100,
                "done": total,
                "total": total,
            }))
            db_finish_run(rid, "done")

        except Exception as e:
            logger.log(f"[ERROR] {e}")
            from backend.services.db import db_finish_run
            db_finish_run(rid, "error")
        finally:
            set_running(False)
            logger.log("__DONE__")

    threading.Thread(target=execute, daemon=True).start()
    return total, active_modules
