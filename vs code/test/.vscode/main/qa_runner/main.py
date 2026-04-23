import os
import sys

from playwright.sync_api import sync_playwright, Error as PlaywrightError

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.pages.auth.login_page import login

# Group: Q Audit
from src.workflows.Q_audit.Q_setting import Q_setting
from src.workflows.Q_audit.Q_SA import Q_SA
from src.workflows.Q_audit.Q_SA1 import Q_SA1
from src.workflows.Q_audit.Q_as_table import Q_as_table
from src.workflows.Q_audit.Q_Recently_audit import Q_Recently_Audit
from src.workflows.Q_audit.Q_audit_Summary import Q_audit_Summary

# Utilities
from src.utils.timezone_helper import timezone

# Group: Audit Plan (Core Setup & Reports)
from src.workflows.audit.Audit_plan import create_audit
from src.workflows.audit.Ad_hoc_Audit import Ad_hoc_Audit
from src.workflows.audit.Ongo_Audit import Ongo_Audit
from src.workflows.audit.Auditor_1 import A_SA

from src.workflows.Audit_plan.A_SA2 import A_SA2
from src.workflows.Audit_plan.A_audit_Summary import A_audit_Summary
from src.workflows.Audit_plan.A_as_table import A_as_table
from src.workflows.Audit_plan.A_Recently_Audit import A_Recently_Audit

# Group: Inventory
from src.workflows.inventory.create_group import create_group
from src.workflows.inventory.location import settings
from src.workflows.inventory.import_app import import_app

from Config import Config

FLAG_TO_IDX = {
    "run_q_setting":          0,
    "run_Q_SA":               1,
    "run_Q_SA1":              2,
    "run_Q_as_table":         3,
    "run_Q_Recently_Audit":   4,
    "run_Q_audit_Summary":    5,
    "run_create_audit":       6,
    "run_create_Ad_hoc_Audit": 6,
    "run_setup_Audit":        7,
    "run_A_SA":               8,
    "run_A_SA2":              9,
    "run_A_as_table":         10,
    "run_A_audit_Summary":    11,
    "run_A_Recently_Audit":   12,
    "run_create_group":       13,
    "run_locatio_setup":      14,
    "run_import_app":         15,
}

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
                try: idx = int(item)
                except ValueError: idx = None
        else:
            idx = None
        if idx is not None and idx not in order:
            order.append(idx)
    if not order:
        order = DEFAULT_ORDER[:]
    return [idx for idx in order if _is_enabled(idx)]

def _is_enabled(idx):
    if idx == 0:  return bool(Config.run_q_setting)
    if idx == 1:  return bool(Config.run_Q_SA)
    if idx == 2:  return bool(Config.run_Q_SA1)
    if idx == 3:  return bool(Config.run_Q_as_table)
    if idx == 4:  return bool(Config.run_Q_Recently_Audit)
    if idx == 5:  return bool(Config.run_Q_audit_Summary)
    if idx == 6:  return bool(Config.run_create_audit or Config.run_create_Ad_hoc_Audit)
    if idx == 7:  return bool(Config.run_setup_Audit)
    if idx == 8:  return bool(Config.run_A_SA)
    if idx == 9:  return bool(Config.run_A_SA2)
    if idx == 10: return bool(Config.run_A_as_table)
    if idx == 11: return bool(Config.run_A_audit_Summary)
    if idx == 12: return bool(Config.run_A_Recently_Audit)
    if idx == 13: return bool(Config.run_create_group)
    if idx == 14: return bool(Config.run_locatio_setup)
    if idx == 15: return bool(Config.run_import_app)
    return False

def main():
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
            cred_pass  = Config.password if session_type == "auditor1" else Config.password2

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
                Ad_hoc_Audit(page, Config)
                return
            if Config.A_Type == "Audit_plan":
                if Config.run_timezone and Config.frequency.lower() != "manual":
                    timezone(page)
                create_audit(page, Config)
                return

        tasks = {
            0:  lambda: (ensure_session("auditor1"), Q_setting(page, Config)),
            1:  lambda: (ensure_session("auditor1"), Q_SA(page, Config)),
            2:  lambda: (ensure_session("auditor2"), Q_SA1(page, Config)),
            3:  lambda: (ensure_session("auditor1"), Q_as_table(page, Config)),
            4:  lambda: (ensure_session("auditor1"), Q_Recently_Audit(page, Config)),
            5:  lambda: (ensure_session("auditor1"), Q_audit_Summary(page, Config)),
            6:  lambda: (ensure_session("auditor1"), run_audit_plan_or_adhoc()),
            7:  lambda: (ensure_session("auditor1"), Ongo_Audit(page, Config)),
            8:  lambda: (ensure_session("auditor1"), A_SA(page, Config)),
            9:  lambda: (ensure_session("auditor2"), A_SA2(page, Config)),
            10: lambda: (ensure_session("auditor2"), A_as_table(page, Config)),
            11: lambda: (ensure_session("auditor2"), A_audit_Summary(page, Config)),
            12: lambda: (ensure_session("auditor2"), A_Recently_Audit(page, Config)),
            13: lambda: (ensure_session("auditor1"), create_group(page, Config)),
            14: lambda: (ensure_session("auditor1"), settings(page)),
            15: lambda: (ensure_session("auditor1"), import_app(page, Config)),
        }

        try:
            order = _enabled_order()
            for idx in order:
                task = tasks.get(idx)
                if task:
                    print(f"Running module index: {idx}")
                    task()
            print("Automation completed successfully.")
        finally:
            if browser:
                browser.close()

if __name__ == "__main__":
    main()
