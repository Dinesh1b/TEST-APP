# FULL SCRIPT WITH FAST_MODE APPLIED
# --------------------------------------------------------------
# Paste this file into your project. Every time.sleep() now uses
# SLEEP_TIME which is controlled by FAST_MODE.
# --------------------------------------------------------------

import sys
import os
import time
import random
import string
import difflib
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --------------------------------------------------------------
# FAST MODE CONTROL
# --------------------------------------------------------------
FAST_MODE = False  # Set True for fast mode (0.15s sleeps), False for default (1s)
SLEEP_TIME = 0.10 if FAST_MODE else 1.0

# --------------------------------------------------------------
# Path setup
# --------------------------------------------------------------
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# Project imports
from login.login import login
from login.popup_handler import detect_feedback
from login.logger_setup import mirrored_print
from excel_logger import write_log

# --------------------------------------------------------------
# Utility Helpers
# --------------------------------------------------------------


def random_name():
    return "Audit_" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def click_and_wait(page, click_selector, wait_selector=None, timeout=15000):
    page.wait_for_selector(click_selector, timeout=timeout).click()
    if wait_selector:
        page.wait_for_selector(wait_selector, timeout=timeout)
    time.sleep(SLEEP_TIME)


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


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def read_dropdown_options_for_locator(page, dropdown_locator, timeout=2000):
    try:
        combobox = dropdown_locator.locator('span[role="combobox"]').first
        combobox.scroll_into_view_if_needed()
        js_click(page, combobox)
        time.sleep(SLEEP_TIME)

        try:
            page.wait_for_selector("div.p-dropdown-panel:visible", timeout=timeout)
        except PlaywrightTimeoutError:
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
                        """
                        panel => Array.from(panel.querySelectorAll('li.p-dropdown-item'))
                        .map(li => li.innerText ? li.innerText.trim() : (li.textContent || '').trim())
                        """
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
        time.sleep(SLEEP_TIME)
        return option_texts

    except Exception:
        page.mouse.click(0, 0)
        return []


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
def map_headers(page, mapping):
    row_container = page.locator("div.row-container")
    left_col = row_container.locator("div.col-md-6.col-lg-6.col-12").nth(0)
    right_col = row_container.locator("div.col-md-6.col-lg-6.col-12").nth(1)

    left_labels = left_col.locator("div.label > label")
    right_dropdowns = right_col.locator("p-dropdown")

    try:
        label_texts = left_col.evaluate(
            """
            col => Array.from(col.querySelectorAll('div.label > label'))
            .map(el => el.innerText ? el.innerText.trim() : (el.textContent || '').trim())
            """
        )
    except:
        label_texts = []
        for i in range(left_labels.count()):
            try:
                label_texts.append(left_labels.nth(i).inner_text().strip())
            except:
                label_texts.append("")

    mirrored_print(f"Found labels: {label_texts}")

    for required_label, excel_header in mapping.items():
        wait_for_overlay_to_disappear(page)

        try:
            idx = label_texts.index(required_label)
        except ValueError:
            mirrored_print(f"Label missing: {required_label}")
            continue

        dropdown_locator = right_dropdowns.nth(idx)
        options = read_dropdown_options_for_locator(page, dropdown_locator)
        mirrored_print(f"Options for '{required_label}': {len(options)}")

        ok, reason, pick = select_option_for_dropdown_locator(page, dropdown_locator, excel_header)

        if ok:
            mirrored_print(f"âœ” Mapped {required_label} â†’ '{excel_header}' ({reason})")

        else:
            mirrored_print(f"Failed to map {required_label} â†’ '{excel_header}' ({reason})")

    mirrored_print("Header mapping done.")


# --------------------------------------------------------------
# Main Audit Creation
# --------------------------------------------------------------

def q_audit(page):
    # Wait until element visible
    page.wait_for_selector("a[href='/home/audit']", state="visible")

    # Click
    page.click("a[href='/home/audit']")
    time.sleep(SLEEP_TIME)

    page.wait_for_selector("button.createAuditBtn").click()
    time.sleep(SLEEP_TIME)

    page.wait_for_selector("button:has-text('Quick Audit')").click()
    time.sleep(SLEEP_TIME)

    audit_name = random_name()
    page.wait_for_selector("input.underline-input").fill(audit_name)
    print(f"Creating Audit: {audit_name}")
    time.sleep(SLEEP_TIME)

    page.wait_for_selector("button.button.primary-button:has-text('Create Audit')").click()
    time.sleep(SLEEP_TIME)

    # Settings icon
    settings_icon = page.wait_for_selector("img[alt='seting icon']")
    js_click(page, settings_icon)
    time.sleep(SLEEP_TIME)

    # Checkboxes
    geo = page.wait_for_selector("input[formcontrolname='isGeoLocation']")
    if not geo.is_checked(): geo.check(force=False)

    photo = page.wait_for_selector("input[formcontrolname='isPhotoValidation']")
    if not photo.is_checked(): photo.check(force=False)

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
        "Item Name": "Item Name",
        "Stock Quantity": "Adjustmentqty",
        "Cost Price": "Cost Price",
        "Category": "Category",
        "Storage": "Location",
        "Barcode": "Barcode",
    }
    map_headers(page, mapping)

    # MAP and SAVE
    page.wait_for_selector("button:has-text('Map')").click()
    time.sleep(SLEEP_TIME)

    page.wait_for_selector("button:has-text('Save')").click()
    time.sleep(SLEEP_TIME)

    detect_feedback(page)
    write_log(audit_name, "Created successfully")




# --------------------------------------------------------------
# Main
# --------------------------------------------------------------
if __name__ == "__main__":
    with sync_playwright() as p:

        # â­ login.py returns (browser, page)
        browser, page = login(
            p,
            browser_name="chrome",      # edge / chrome / firefox
            environment="STAGING"            # PRODUCTION / STAGING / QA / DEV
        )

        # â­ Only continue if login succeeded
        q_audit(page)

