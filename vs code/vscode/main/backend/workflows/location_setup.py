from datetime import datetime
import pytz
import difflib
import random
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import Page
import os
import sys





class Config:

    zones  = ["SA"]
    aisles = ["A1", "A2", "A3"]
    bays   = ["B1","B2","B3","B4","B5"]
    levels = ["L1", "L2", "L3", "L4", "L5"]

# ---------------------------------------
# SAFE CLICK
# ---------------------------------------
def safe_click(locator):
    locator.wait_for(state="attached", timeout=15000)
    locator.wait_for(state="visible", timeout=15000)
    locator.scroll_into_view_if_needed()
    locator.page.wait_for_load_state("networkidle")
    try:
        locator.click(timeout=10000)
    except:
        locator.click(force=True)


# ---------------------------------------
# DROPDOWN FILTER + SELECT
# ---------------------------------------
def type_in_dropdown_filter_dynamic(page, filter_text):
    filter_input = page.locator("input.p-dropdown-filter").last
    filter_input.wait_for(state="visible", timeout=5000)
    filter_input.click()
    filter_input.clear()

    # Human typing simulation
    for char in filter_text:
        filter_input.type(char, delay=random.randint(60, 140))

    page.wait_for_timeout(600)

    aria_owns = filter_input.get_attribute("aria-owns")
    options_locator = page.locator(f"#{aria_owns} li.p-dropdown-item")
    options_locator.first.wait_for(state="visible", timeout=5000)

    all_options = options_locator.all_inner_texts()

    # Exact match
    if filter_text in all_options:
        matched = filter_text
    else:
        matches = difflib.get_close_matches(filter_text, all_options, n=1, cutoff=0.4)
        if matches:
            matched = matches[0]
            print(f"⚠ Fuzzy match: {filter_text} → {matched}")
        else:
            print("❌ No timezone match found")
            return

    option = page.locator(f"#{aria_owns} li.p-dropdown-item:has-text('{matched}')")
    safe_click(option)
    print(f"✅ Selected: {matched}")


# ---------------------------------------
# SETTINGS page LOGIC
# ---------------------------------------
def settings(page):
    try:
        page.locator("button:has(img[src*='white_logo.png'])").click()
        page.locator("#audit-settings-link").click()
        page.wait_for_timeout(1000)
        page.locator("a[href='/home/storage']").first.click()
        page.wait_for_timeout(1000)

        # ── STEP 1: Add Zones ──────────────────────────────────────
        for zone in Config.zones:
            safe_click(page.locator(".storage-header button"))
            page.wait_for_timeout(400)
            page.locator(".storage-panel input[placeholder='Short Code']").last.fill(zone)
            page.wait_for_timeout(300)

        # ── STEP 2: Add Aisles for every Zone ─────────────────────
        for zone in Config.zones:
            page.locator(".aisle-header select").select_option(label=zone)
            page.wait_for_timeout(400)
            for aisle in Config.aisles:
                safe_click(page.locator(".aisle-header button"))
                page.wait_for_timeout(400)
                page.locator(".aisle-panel input[placeholder='Short Code']").last.fill(aisle)
                page.wait_for_timeout(300)

        # ── STEP 3: Add Bays for every Zone→Aisle combo ───────────
    
                for bay in Config.bays:
                    safe_click(page.locator(".bay-header button"))
                    page.wait_for_timeout(400)
                    page.locator(".bay-panel input[placeholder='Short Code']").last.fill(bay)
                    page.wait_for_timeout(300)

        # ── STEP 4: Add Levels for every Zone→Aisle→Bay combo ─────

                    for level in Config.levels:
                        safe_click(page.locator(".level-header button"))
                        page.wait_for_timeout(400)
                        page.locator(".level-panel input[placeholder='Short Code']").last.fill(level)
                        page.wait_for_timeout(300)
        
    except PlaywrightTimeoutError:
        print("❌ Settings navigation failed")
    page.locator("button.primary-button:has-text('Save')").click()





