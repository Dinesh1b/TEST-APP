import sys
import time
import os
import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
from login.popup_handler import detect_feedback
from login.logger_setup import mirrored_print
# --------------------------------------------------------------
# GLOBAL SPEED CONTROL
# --------------------------------------------------------------
SLEEP_TIME = 1

def Ad_hoc_Audit(page, Config):


    # ---------------------------
    # Select Item Group Dropdown
    # ---------------------------
    def select_item_group(page, Group_Name):
        dropdown = page.locator("p-dropdown[placeholder='Select Item Group']")
        dropdown.locator("div.p-dropdown-trigger").click()

        page.locator("div.p-dropdown-panel")
        page.locator("input.p-dropdown-filter").fill(Group_Name)

        page.locator("li.p-dropdown-item", has_text=Group_Name).first.click()




    # --------------------------------------------------------------
    # SELECT BRANCH (PrimeNG p-dropdown via XPath)
    # --------------------------------------------------------------
    def select_branch(page, branch_text: str):
        dropdown = page.locator(
            'xpath=/html/body/app-root/app-layout/div/app-header/div[1]/div[2]/div[2]//p-dropdown'
        )
        dropdown.wait_for(state="visible", timeout=30000)
        dropdown.locator(".p-dropdown-label").click()

        panel = page.locator(".p-dropdown-panel").last
        panel.wait_for(state="visible", timeout=30000)

        search = panel.locator("input.p-dropdown-filter")
        if search.count() > 0:
            search.fill("")
            search.fill(branch_text)
            page.wait_for_timeout(300)

        option = panel.locator("li.p-dropdown-item", has_text=branch_text)
        if option.count() == 0:
            raise Exception(f"❌ Branch not found: {branch_text}")

        option.first.click()
        panel.wait_for(state="hidden", timeout=30000)

        dropdown.locator(
            ".p-dropdown-label", has_text=branch_text
        ).wait_for(state="visible", timeout=30000)




    # --------------------------------------------------------------
    # CREATE AUDIT NAME
    # --------------------------------------------------------------
    def create_name(page, Config):
        audit_name = Config.ap_audit_name
        input_selector = "input.underline-input"
        button_selector = "button:has-text('Create Audit')"

        try:
            current_value = page.input_value(input_selector)

            if not current_value.strip():
                page.fill(input_selector, audit_name)
                page.click(button_selector)

        except Exception as e:
            mirrored_print(f"❌ Failed to create audit with name {audit_name}: {e}")
            raise

    # --------------------------------------------------------------
    # MAIN FLOW
    # --------------------------------------------------------------
    def create_Ad_hoc_Audit(page):
        page.wait_for_selector("a[href='/home/audit']", state="visible")
        page.click("a[href='/home/audit']")
        time.sleep(SLEEP_TIME)

        # Branch selection before creating audit to avoid branch-related issues
        select_branch(page, Config.Branch)
        print(f"✅ Branch selected: {Config.Branch}")
        time.sleep(SLEEP_TIME)

        page.click("button.createAuditBtn")
        time.sleep(SLEEP_TIME)

        page.click("button:has-text('Ad-hoc Audit')")
        time.sleep(SLEEP_TIME)

        select_item_group(page, Config.Group_Name)
        create_name(page, Config)
        time.sleep(SLEEP_TIME)

    # --------------------------------------------------------------
    # ENTRY POINT
    # --------------------------------------------------------------
    create_Ad_hoc_Audit(page)