#!/usr/bin/env python3
import sys
import os
import time
import random
import string
import difflib
from typing import List, Tuple
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError
import pandas as pd

# ======================================================
# CONFIG
# ======================================================
DRY_RUN = False
SEED = None

if SEED is not None:
    random.seed(SEED)

# ======================================================
# PATH SETUP
# Add parent folder to path so your login module can be imported
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login   # must exist and return (browser, page)
from login.popup_handler import detect_feedback
from login.logger_setup import mirrored_print   # must exist and return (browser, page)
from excel_logger import write_log

# --------------------------------------------------------------
# FAST MODE CONTROL
# --------------------------------------------------------------
FAST_MODE = False  # Set True for fast mode (0.15s sleeps), False for default (1s)
SLEEP_TIME = 0.10 if FAST_MODE else 1.0

def wait_for_overlay_to_disappear(page):
    overlays = [
        ".p-dialog-mask",
        ".p-component-overlay",
        ".cdk-overlay-backdrop"
    ]
    for selector in overlays:
        try:
            page.wait_for_selector(selector, state="detached", timeout=2000)
        except PlaywrightTimeoutError:
            pass
def js_click(page, locator):
    try:
        locator.click(force=True)
        return True
    except Exception:
        try:
            handle = locator.element_handle(timeout=2000)
            if handle:
                page.evaluate("(el) => el.click()", handle)
                return True
        except Exception:
            return False
    return False

def js_click(page, locator):
    try:
        locator.click(force=True)
        return True
    except Exception:
        try:
            handle = locator.element_handle(timeout=2000)
            if handle:
                page.evaluate("(el) => el.click()", handle)
                return True
        except Exception:
            return False
    return False

def select_item_group(page, group_name: str):
    """
    Select value from 'Select Item Group' PrimeNG dropdown
    """

    # Scope to Item Group dropdown container
    dropdown = page.locator(
        "p-dropdown[placeholder='Select Item Group']"
    )

    # Open dropdown
    dropdown.locator("div.p-dropdown-trigger").click()
    time.sleep(SLEEP_TIME)

    # Dropdown panel (opens globally)
    panel = page.locator("div.p-dropdown-panel")
    time.sleep(SLEEP_TIME)


    # Type in filter    
    panel.locator("input.p-dropdown-filter").fill(group_name)
    time.sleep(SLEEP_TIME)


    # Click matching option
    panel.locator(
        "li.p-dropdown-item", has_text=group_name
    ).first.click()


def js_click(page, locator):
    try:
        locator.click(force=True)
        return True
    except Exception:
        try:
            handle = locator.element_handle(timeout=2000)
            if handle:
                page.evaluate("(el) => el.click()", handle)
                return True
        except Exception:
            return False
    return False

def read_dropdown_options_for_locator(page, dropdown_locator, timeout=3000):
    """
    Open the given p-dropdown locator, find the visible appended panel that contains options,
    return the list of option strings found in that panel. Always closes the panel afterwards.
    (This helper returns the list — caller should avoid printing the whole list.)
    """
    try:
        combobox = dropdown_locator.locator('span[role="combobox"]').first
        combobox.scroll_into_view_if_needed()
        js_click(page, combobox)
        time.sleep(0.12)

        # Wait for any visible panel to appear
        try:
            page.wait_for_selector("div.p-dropdown-panel:visible", timeout=timeout)
        except TimeoutError:
            page.mouse.click(0, 0)
            return []

        panels = page.locator("div.p-dropdown-panel:visible")
        option_texts = []
        panel_count = panels.count()
        for i in range(panel_count):
            panel = panels.nth(i)
            try:
                item_count = panel.locator("li.p-dropdown-item").count()
            except Exception:
                item_count = 0
            if item_count > 0:
                try:
                    option_texts = panel.evaluate(
                        """panel => Array.from(panel.querySelectorAll('li.p-dropdown-item'))
                                           .map(li => li.innerText ? li.innerText.trim() : (li.textContent || '').trim())"""
                    )
                except Exception:
                    option_texts = []
                    for j in range(item_count):
                        try:
                            option_texts.append(panel.locator("li.p-dropdown-item").nth(j).inner_text().strip())
                        except Exception:
                            option_texts.append("")
                break

        page.mouse.click(0, 0)
        time.sleep(0.12)
        return option_texts

    except Exception as e:
        mirrored_print(f"✖ Failed to read dropdown options: {e}")
        try:
            page.mouse.click(0, 0)
        except Exception:
            pass
        return []

def _normalize(s: str) -> str:
    return (s or "").strip().lower()

def select_option_for_dropdown_locator(page, dropdown_locator, option_text, timeout=7000):
    start = time.time()
    option_text_norm = _normalize(option_text)
    mirrored_print(f"[select_option] selecting '{option_text}'")

    try:
        trigger = dropdown_locator
        try:
            inner = dropdown_locator.locator('span[role="combobox"]').first
            if inner.count() and inner.is_visible():
                trigger = inner
        except Exception:
            pass

        try:
            trigger.scroll_into_view_if_needed()
        except Exception:
            pass

        clicked = js_click(page, trigger)
        if not clicked:
            try:
                trigger.click(timeout=2000, force=True)
            except Exception:
                pass

        time.sleep(SLEEP_TIME)

        panel_selectors = [
            "div.p-dropdown-panel", "div.p-multiselect-panel", "ul.p-dropdown-items",
            "div.ui-dropdown-panel", "div[role='listbox']", "div[role='dialog']"
        ]

        panels = []
        for sel in panel_selectors:
            try:
                loc = page.locator(sel)
                cnt = loc.count()
                for i in range(cnt):
                    p = loc.nth(i)
                    if p.is_visible():
                        panels.append(p)
            except Exception:
                continue

        if not panels:
            panels = [page]

        # 1) exact match
        for panel in panels:
            try:
                opt = panel.locator(f"li:has-text('{option_text}')")
                if opt.count():
                    for j in range(opt.count()):
                        candidate = opt.nth(j)
                        if candidate.is_visible():
                            js_click(page, candidate)
                            return True, "exact_li", candidate
            except Exception:
                continue

        # 2) case-insensitive + fuzzy
        for panel in panels:
            try:
                items = panel.locator("li, div, span")
                cnt = items.count()
            except:
                cnt = 0

            seen = []
            for i in range(cnt):
                try:
                    it = items.nth(i)
                    if not it.is_visible():
                        continue
                    txt = it.inner_text().strip()
                    if not txt:
                        continue
                    seen.append((i, txt, it))
                    if _normalize(txt) == option_text_norm:
                        js_click(page, it)
                        return True, "case_insensitive_direct", it
                except:
                    continue

            if seen:
                texts = [t for (_, t, _) in seen]
                lower_texts = [t.lower() for t in texts]
                matches = difflib.get_close_matches(option_text_norm, lower_texts, n=1, cutoff=0.6)
                if matches:
                    best = matches[0]
                    idx = lower_texts.index(best)
                    chosen = seen[idx][2]
                    js_click(page, chosen)
                    return True, "fuzzy", chosen

        # 3) page-wide exact
        page_items = page.locator(f"text={option_text}")
        if page_items.count():
            for i in range(page_items.count()):
                candidate = page_items.nth(i)
                if candidate.is_visible():
                    js_click(page, candidate)
                    return True, "page_wide", candidate

        return False, "not_found", None

    except Exception as e:
        return False, f"exception:{e}", None
    
def click_and_wait(page, click_selector, wait_selector=None, timeout=15000):
    page.wait_for_selector(click_selector, timeout=timeout).click()
    if wait_selector:
        page.wait_for_selector(wait_selector, timeout=timeout)
    time.sleep(SLEEP_TIME)
# --------------------------------------------------------------
# ✅ CHECK IF HEADER ALREADY MAPPED
# --------------------------------------------------------------
def is_already_mapped(dropdown_locator) -> bool:
    """
    Returns True if dropdown already has selected value
    """
    try:
        label = dropdown_locator.locator(
            "span.p-dropdown-label:not(.p-placeholder)"
        )
        return label.count() > 0 and label.first.inner_text().strip() != ""
    except Exception:
        return False
    
# --------------------------------------------------------------
# Import Items
# --------------------------------------------------------------
def import_items(page, file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    click_and_wait(page, "li:has-text('Import Items')", "input[type='file']")

    page.locator("input[type='file']").set_input_files(file_path)
    mirrored_print("Excel file uploaded.")
    time.sleep(SLEEP_TIME)

    page.wait_for_selector("div.row-container")
    wait_for_overlay_to_disappear(page)
    time.sleep(SLEEP_TIME)
    return True

# --------------------------------------------------------------
# Map Headers
# --------------------------------------------------------------
# --------------------------------------------------------------
# HEADER MAPPING (SAFE)
# --------------------------------------------------------------
def map_headers(page, mapping):
    row_container = page.locator("div.row-container")
    left_col = row_container.locator("div.col-md-6").nth(0)
    right_col = row_container.locator("div.col-md-6").nth(1)

    labels = left_col.locator("div.label > label")
    dropdowns = right_col.locator("p-dropdown")

    label_texts = []
    for i in range(labels.count()):
        label_texts.append(labels.nth(i).inner_text().strip())

    mirrored_print(f"Found headers: {label_texts}")

    for required_label, excel_header in mapping.items():
        wait_for_overlay_to_disappear(page)

        if required_label not in label_texts:
            mirrored_print(f"⚠ Missing label: {required_label}")
            continue

        idx = label_texts.index(required_label)
        dropdown = dropdowns.nth(idx)

        # ✅ SKIP IF ALREADY MAPPED
        if is_already_mapped(dropdown):
            mirrored_print(f"⏭ Skipped '{required_label}' (already mapped)")
            continue

        ok = select_option_for_dropdown_locator(page, dropdown, excel_header)

        if ok:
            mirrored_print(f"✔ Mapped {required_label} → {excel_header}")
        else:
            mirrored_print(f"✖ Failed to map {required_label}")

    mirrored_print("✅ Header mapping completed safely.")


# ======================================================
# SAFE CLICK
# ======================================================
def safe_click(locator):
    locator.wait_for(state="attached", timeout=15000)
    locator.wait_for(state="visible", timeout=15000)

    locator.scroll_into_view_if_needed()

    # wait for stability
    locator.page.wait_for_load_state("networkidle")

    try:
        locator.click(timeout=10000)
    except:
        locator.click(force=True)

# ======================================================
# WAIT TIME (TIME2 = 2 seconds)
# ======================================================
def wait2(page):
    page.wait_for_timeout(2000)  # 2 seconds


# ======================================================
# RANDOM AUDIT NAME
# ======================================================
def random_name():
    return "Audit_" + "".join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )


# ======================================================
# CREATE AUDIT
# ======================================================
def create_audit(page):
    try:
        print("➡️ Open Audit page", flush=True)
        page.click("a[href='#/home/audit']")
        page.wait_for_load_state("networkidle")
        wait2(page)

        print("➡️ Click Create Audit", flush=True)
        safe_click(page.locator("button.createAuditBtn"))
        wait2(page)

        print("➡️ Select Audit Plan", flush=True)
        safe_click(page.locator("button[label='Audit Plan']"))
        wait2(page)
        safe_click(page.locator("button:has-text('Add Audit Plan')"))
        wait2(page)

        print("➡️ Select Role", flush=True)
        safe_click(page.locator("div#role .p-dropdown-trigger"))
        wait2(page)
        safe_click(page.locator("#role_0"))# Select first item group ,role_0, role_1, role_2, role_3, role_4
        wait2(page)
        
        audit_name = random_name()
        print(f"📝 Audit Name: {audit_name}", flush=True)
        page.fill("input#name", audit_name)
        wait2(page)

        print("➡️ Select Audit Type", flush=True)
        page.locator("p-radiobutton").first.click()
        wait2(page)

        print("➡️ Choose Frequency", flush=True)
        safe_click(page.get_by_role("combobox", name="Choose Frequency"))
        wait2(page)
        safe_click(page.locator("li.p-dropdown-item:has-text('Manual')"))
        wait2(page)

        safe_click(page.get_by_role("button", name="Next"))
        wait2(page)

        print("➡️ Select Auditor", flush=True)
        safe_click(page.locator("div.p-multiselect-trigger").first)
        wait2(page)
        page.locator("li.p-multiselect-item").first.click()
        wait2(page)
        safe_click(page.locator("button.p-multiselect-close"))
        wait2(page)

        print("➡️ Enable options", flush=True)
        page.check("[formcontrolname='isDamageQty']")
        page.check("[formcontrolname='isStockItems']")
        #page.check("[formcontrolname='isPhotoValidation']")
        page.check("[formcontrolname='isGeoTagging']")
        wait2(page)

        print("➡️ Cross-check config", flush=True)
        page.locator("span.p-radiobutton-icon").nth(1).click(force=True)
        wait2(page)
        page.fill("[formcontrolname='crossCheckSize']", "50")
        wait2(page)

        print("➡️ Choose Cross Auditor", flush=True)
        safe_click(page.locator("span.p-dropdown-label:has-text('Choose Cross Auditor')"))
        wait2(page)
        page.locator("li.p-dropdown-item").first.click()
        wait2(page)

        print("➡️ Click Next", flush=True)
        safe_click(page.get_by_role("button", name="Next"))

        wait2(page)

        if DRY_RUN:
            print("🟡 DRY_RUN enabled – skipping Save", flush=True)
            return audit_name

        print("➡️ Save Audit", flush=True)
        safe_click(page.locator("button.primary-button:has-text('Save')"))
        
        
    
        
        page.wait_for_load_state("networkidle")


        safe_click(page.locator("button:has-text('Back')"))
        page.wait_for_load_state("networkidle")
        wait2(page)

        return audit_name

    except Exception as e:
        print(f"❌ Error during audit creation: {str(e)}", flush=True)
        detect_feedback(page)
        raise


# ----------------------
# UI functions
# ----------------------
def test(page: Page):
    """Navigate to audit page and click the desired audit."""
    page.click("a[href='#/home/audit']")
    page.wait_for_load_state("networkidle")
    locator = page.locator(
    f"table tbody tr:has(td span:has-text('{audit_name}')):has(td:has-text('Complete Count')) td span"
).first

    locator.click()


 # Settings icon
    settings_icon = page.wait_for_selector("img[alt='seting icon']")
    js_click(page, settings_icon)
    time.sleep(SLEEP_TIME)

    # Checkboxes
    #geo = page.wait_for_selector("input[formcontrolname='isGeoLocation']")
    #if not geo.is_checked(): geo.check(force=False)

    #photo = page.wait_for_selector("input[formcontrolname='isPhotoValidation']")
    #if not photo.is_checked(): photo.check(force=False)

    time.sleep(SLEEP_TIME)

    # Responsible person
    dropdown_trigger = page.wait_for_selector("div.p-multiselect-trigger")
    dropdown_trigger.click()
    ok,_,_ = select_option_for_dropdown_locator(page, dropdown_trigger, "Dinesh B")
    dropdown_trigger.click()
    time.sleep(SLEEP_TIME)

    # Import
    page.wait_for_selector("button:has-text('Import Stock Sheet')").click()
    time.sleep(SLEEP_TIME)

    file_path = os.path.abspath(r"C:\Users\HP\Documents\input\QAudit.xlsx")
    page.wait_for_selector("input#formFileSm").set_input_files(file_path)
    time.sleep(SLEEP_TIME)

    # Mapping
    mapping = {
        "Item Code": "Item Code",
        
        "Stock Quantity": "Adjustmentqty",
        
    }
    map_headers(page, mapping)

    # MAP and SAVE
    page.wait_for_selector("button:has-text('Map')").click()
    time.sleep(SLEEP_TIME)

    page.wait_for_selector("button:has-text('Save')").click()
    time.sleep(SLEEP_TIME)

    detect_feedback(page)
    





# ----------------------
# Entry point (minimal validation, no try/except)
# ----------------------
if __name__ == "__main__":
    #
    # Start Playwright and run flow (no try/except)
    with sync_playwright() as p:
        browser, page = login(
            p,
            browser_name="chrome",  # chrome / edge / firefox
            environment="QA"        # PRODUCTION / STAGING / QA / DEV
        )
        # 2. Navigate to Inventory → Item Groups
        click_and_wait(page, "img[src*='Item_icon.svg']")

        time.sleep(3)

        click_and_wait(page, "a[href*='itemGroup']")
        time.sleep(3)

        # 3. Create a new Item Group
        group_name = f"Test Group Automation {random.randint(10000, 99999)}"
        mirrored_print(f"Generated Group Name: {group_name}")
        time.sleep(3)

        click_and_wait(page, "button:has-text('Add Item Group')", "input[formcontrolname='groupName']")
        time.sleep(3)
        page.fill("input[formcontrolname='groupName']", group_name)
        time.sleep(3)
        click_and_wait(page, "button:has-text('Save')", "button:has-text('Back')")
        time.sleep(3)
        click_and_wait(page, "button:has-text('Back')")
        select_item_group(page, group_name)
        time.sleep(3)
        

        

        # 4. Import Items
        click_and_wait(page, "li:has-text('Import Items')", "input[type='file']")

        # 5. Upload Excel file (defensive)
        file_path = os.path.abspath(r"C:\Users\HP\Documents\input\QAudit.xlsx")
        if not os.path.exists(file_path):
            mirrored_print(f"✖ File not found: {file_path}")
            raise FileNotFoundError(file_path)
        try:
            page.wait_for_selector("input[type='file']", timeout=15000)
            file_input = page.locator("input[type='file']")
            file_input.set_input_files(file_path)
            mirrored_print("Excel file uploaded.")
        except Exception as e:
            mirrored_print(f"✖ Failed to set input files: {e}")
            try:
                mirrored_print(f"page.is_closed(): {page.is_closed()}")
            except Exception as e2:
                mirrored_print(f"✖ couldn't check page.is_closed(): {e2}")
            raise

        # 6. Wait for mapping modal to appear and be stable
        page.wait_for_selector("div.row-container", timeout=20000)
        wait_for_overlay_to_disappear(page)
        time.sleep(0.5)

        # 7. HEADER MAPPING (with concise logging)
        mapping = {
            "Item Category": "Category",
            "Item Code":     "Item Code",
            "Item Name":     "Item Name",
            "Cost Price":    "Cost Price",
            "Sell Price":    "Sell Price"
        }

        # locate columns and find labels/dropdowns
        row_container = page.locator("div.row-container")
        left_col = row_container.locator("div.col-md-6.col-lg-6.col-12").nth(0)
        right_col = row_container.locator("div.col-md-6.col-lg-6.col-12").nth(1)
        left_labels = left_col.locator("div.label > label")
        right_dropdowns = right_col.locator("p-dropdown")

        # read all label texts in one evaluate to avoid many sync calls
        try:
            label_texts = left_col.evaluate(
                """col => Array.from(col.querySelectorAll('div.label > label'))
                               .map(el => el.innerText ? el.innerText.trim() : (el.textContent || '').trim())"""
            )
        except Exception as e:
            mirrored_print(f"Warning: evaluate failed: {e}. Falling back to incremental read.")
            label_texts = []
            try:
                count = left_labels.count()
            except Exception:
                count = 0
            for i in range(count):
                try:
                    label_texts.append(left_labels.nth(i).inner_text().strip())
                except Exception as e2:
                    mirrored_print(f"  ✖ failed to read label {i}: {e2}")
                    label_texts.append("")

        mirrored_print(f"Found left labels: {label_texts}")

        # iterate mapping with fuzzy fallback & concise logging
        for required_field, desired_header in mapping.items():
            wait_for_overlay_to_disappear(page)
            try:
                idx = label_texts.index(required_field)
            except ValueError:
                mirrored_print(f"✖ Label '{required_field}' not found. Available: {label_texts}")
                continue

            dropdown_locator = right_dropdowns.nth(idx)

            # read current options for this dropdown but do not print them
            options = read_dropdown_options_for_locator(page, dropdown_locator)
            # only log number of options, not the full list
            mirrored_print(f"Options count for '{required_field}': {len(options)}")

            # skip if already mapped
            if is_already_mapped(dropdown_locator):
                mirrored_print(f"⏭ Skipped '{required_field}' (already mapped)")
                continue    
        # 8. FINALIZE IMPORT: MAP then SAVE
        wait_for_overlay_to_disappear(page)
        try:
            page.wait_for_selector("button:has-text('Map'):visible", timeout=5000).click()
            mirrored_print("Clicked MAP button.")
        except TimeoutError:
            mirrored_print("✖ MAP button not found or not visible.")

        wait_for_overlay_to_disappear(page)
        try:
            page.wait_for_selector("button:has-text('Save'):visible", timeout=5000).click()
            mirrored_print("Clicked SAVE button.")
        except TimeoutError:
            mirrored_print("✖ SAVE button not found or not visible.")
            time.sleep(5)
        page.wait_for_selector("button:has-text('OK'):visible", timeout=5000).click()
        time.sleep(4)
        mirrored_print("Clicked OK button.")
        wait_for_overlay_to_disappear(page)
        time.sleep(4)
        mirrored_print("🎉 Import Completed (attempted).")

        # ----- OPTION C: Pause here for Playwright Inspector -----
        mirrored_print("🔎 Opening Playwright Inspector... script paused.")
         # <--- interactive browser pause point

        audit_name = create_audit(page)
        test(page)


        input("\nPress ENTER to close browser...")

        browser.close()
 