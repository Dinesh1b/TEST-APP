"""
runner.py — Automation Entry Point.

Replaces the old main.py. Uses module_registry for dynamic workflow loading
instead of 17 hardcoded imports.
"""

import os
import sys
import importlib

# Ensure project root is on sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from playwright.sync_api import sync_playwright

from backend.pages.login_page import login
from backend.shared.timezone_helper import timezone
from backend.models.module_registry import get_all_modules, get_flag_to_idx_map
from backend.Config import Config


def _load_workflow(workflow_ref: str):
    """
    Dynamically import a workflow function from modules.json 'workflow' field.
    E.g. 'q_setting.Q_setting' → import backend.workflows.q_setting, getattr(mod, 'Q_setting')
    """
    mod_path, func_name = workflow_ref.rsplit(".", 1)
    mod = importlib.import_module(f"backend.workflows.{mod_path}")
    return getattr(mod, func_name)


FLAG_TO_IDX = get_flag_to_idx_map()
DEFAULT_ORDER = list(range(16))


def _enabled_order():
    raw_order = getattr(Config, "MODULE_RUN_ORDER", []) or []
    order = []
    for item in raw_order:
        if isinstance(item, int):
            idx = item
        elif isinstance(item, str):
            idx = FLAG_TO_IDX.get(item)
            if idx is None:
                try:
                    idx = int(item)
                except ValueError:
                    idx = None
        else:
            idx = None
        if idx is not None and idx not in order:
            order.append(idx)
    if not order:
        order = DEFAULT_ORDER[:]
    return [idx for idx in order if _is_enabled(idx)]


def _is_enabled(idx):
    """Check if module at given index is enabled in Config."""
    all_modules = get_all_modules()
    for m in all_modules:
        if m["idx"] == idx:
            flag = m["flag"]
            enabled = bool(getattr(Config, flag, False))
            # Special case: idx 6 can be either audit_plan or ad_hoc
            if m.get("alt_flag"):
                enabled = enabled or bool(getattr(Config, m["alt_flag"], False))
            return enabled
    return False


def main():
    all_modules = get_all_modules()
    # Build module index → definition lookup
    idx_to_module = {m["idx"]: m for m in all_modules}

    with sync_playwright() as p:
        print("Logging in (Auditor 1)...")
        browser, page = login(
            p,
            browser_name=Config.browsername,
            environment=Config.environments,
            email=Config.email,
            password=Config.password,
        )

        current_session = "auditor1"

        def ensure_session(session_type):
            nonlocal browser, page, current_session
            if current_session == session_type:
                return

            print(f"Switching session to: {session_type}")
            browser.close()

            cred_email = Config.email if session_type == "auditor1" else Config.email2
            cred_pass = Config.password if session_type == "auditor1" else Config.password2

            browser, page = login(
                p,
                browser_name=Config.browsername,
                environment=Config.environments,
                email=cred_email,
                password=cred_pass,
            )
            page.set_default_timeout(45000)
            current_session = session_type

        def run_audit_plan_or_adhoc():
            if Config.A_Type == "Ad_hoc":
                wf = _load_workflow("ad_hoc_audit.Ad_hoc_Audit")
                wf(page, Config)
                return
            if Config.A_Type == "Audit_plan":
                if Config.run_timezone and Config.frequency.lower() != "manual":
                    timezone(page)
                wf = _load_workflow("audit_plan.create_audit")
                wf(page, Config)
                return

        try:
            order = _enabled_order()
            for idx in order:
                mod_def = idx_to_module.get(idx)
                if not mod_def:
                    continue

                print(f"Running module index: {idx} ({mod_def['display']})")

                # Determine session
                session_type = mod_def.get("session", "auditor1")
                ensure_session(session_type)

                # Special case: idx 6 has Audit Plan / Ad-hoc branching
                if idx == 6:
                    run_audit_plan_or_adhoc()
                else:
                    wf_func = _load_workflow(mod_def["workflow"])
                    # Some workflows take (page, Config), some take just (page)
                    # Location setup (idx 14) only takes page
                    if idx == 14:
                        wf_func(page)
                    else:
                        wf_func(page, Config)

            print("Automation completed successfully.")
        finally:
            if browser:
                browser.close()


if __name__ == "__main__":
    main()
