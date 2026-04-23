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

# Add parent folder to path so your login module can be imported
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login
from login.popup_handler import detect_feedback
from login.logger_setup import mirrored_print   # must exist and return (browser, page)
from excel_logger import write_log

# --------------------------------------------------------------
# FAST MODE CONTROL
# --------------------------------------------------------------
FAST_MODE = False  # Set True for fast mode (0.15s sleeps), False for default (1s)
SLEEP_TIME = 0.10 if FAST_MODE else 1.0

# --------------------------------------------------------------
# Utility Helpers
# --------------------------------------------------------------


def random_name():
    return "Audit_" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

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


# --------------------------------------------------------------
# âœ… CHECK IF HEADER ALREADY MAPPED
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
            mirrored_print(f"âš  Missing label: {required_label}")
            continue

        idx = label_texts.index(required_label)
        dropdown = dropdowns.nth(idx)

        # âœ… SKIP IF ALREADY MAPPED
        if is_already_mapped(dropdown):
            mirrored_print(f"â­ Skipped '{required_label}' (already mapped)")
            continue

        ok = select_option_for_dropdown_locator(page, dropdown, excel_header)

        if ok:
            mirrored_print(f"âœ” Mapped {required_label} â†’ {excel_header}")
        else:
            mirrored_print(f"âœ– Failed to map {required_label}")

    mirrored_print("âœ… Header mapping completed safely.")

# --------------------------------------------------------------
# Main Audit Creation
# --------------------------------------------------------------

def qtest(page):
    page.wait_for_selector("a[href='/home/audit']", state="visible")
    page.click("a[href='/home/audit']")
    time.sleep(SLEEP_TIME)

    page.wait_for_selector("button.createAuditBtn").click()
    time.sleep(SLEEP_TIME)

    page.wait_for_selector("button:has-text('Quick Audit')").click()
    time.sleep(SLEEP_TIME)

    audit_name = random_name()
    page.wait_for_selector("input.underline-input").fill(audit_name)
    print(f"Creating Audit: {audit_name}")

    

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
        "Location": "Location",
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



# ----------------------
# Helpers for binding inputs
# ----------------------
def human_type_input(page: Page, selector: str, text: str, delay_seconds: float = 0.03) -> None:
    """
    Focus the input and type text like a user to trigger keyboard listeners.
    Uses Ctrl+A then Backspace to clear existing content first.
    """
    el = page.locator(selector).first
    el.wait_for(state="visible", timeout=7000)
    el.focus()
    # Clear (Ctrl+A + Backspace). On mac replace with Meta+A if needed.
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.keyboard.type(str(text), delay=int(delay_seconds * 1000))
    # Blur to trigger validation/blur handlers
    el.evaluate("el => el.blur()")
    page.wait_for_timeout(0.08)


def js_set_number_with_events(page: Page, selector: str, value: str) -> None:
    """
    JS assignment for number inputs: set valueAsNumber and dispatch input+change+blur.
    Use after typing if typing didn't bind.
    """
    locator = page.locator(selector).first
    locator.wait_for(state="attached", timeout=7000)
    locator.evaluate(
        """(el, val) => {
            try {
                if (el.type === 'number') {
                    const n = Number(val);
                    el.valueAsNumber = isNaN(n) ? 0 : n;
                } else {
                    el.value = val;
                }
            } catch (e) {
                el.value = val;
            }
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            if (typeof el.blur === 'function') el.blur();
        }""",
        value,
    )
    page.wait_for_timeout(0.06)


# ----------------------
# UI functions (PrimeNG dialog-aware)
# ----------------------
def Ongoing_Audits(page: Page, audit_title: str) -> None:
    page.wait_for_selector("a[href='/home/audit']", state="visible")

    # Prefer class + text locator
    sel = f"span.link-name:has-text('{audit_title}')"

    try:
        page.wait_for_selector(sel, timeout=8000)
        locator = page.locator(sel).first
        locator.scroll_into_view_if_needed()
        locator.click()

    except Exception:
        # Fallback 1
        try:
            page.get_by_text(audit_title, exact=True).first.click()
        except Exception:
            # Fallback 2 (XPath)
            page.locator(
                f"//span[contains(normalize-space(.), '{audit_title}')]"
            ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(200)

    # Debug: print all audit names
    all_audits = page.locator("span.link-name").all_inner_texts()
    print("Available audits:", all_audits)

    print(f"Opened audit: {audit_title}")
    page.screenshot(path="debug_audits.png")


def click_add_item_button(page: Page, timeout: int = 7000) -> None:
    """
    Click the 'Add Item' button and wait for PrimeNG dialog to appear.
    """
    try:
        page.click("button.button.primary-button.me-3:has-text('Add Item')", timeout=timeout)
    except Exception:
        page.click("button:has-text('Add Item')", timeout=timeout)

    # Wait for PrimeNG dialog mask / dialog
    page.wait_for_selector("div.p-dialog-mask", timeout=8000)
    page.wait_for_selector("div.p-dialog", timeout=8000)
    page.wait_for_selector("div.p-dialog-content div.dialog-content", timeout=8000)
    page.wait_for_timeout(200)


def fill_item_details_bound(page: Page, item_code: str, audited_qty: int, damaged_qty: int) -> None:
    """
    Bind/fill modal fields so Angular/PrimeNG picks up values reliably:
      - type item code & numbers (human-like)
      - fallback JS assignment for number inputs if typing didn't bind
    """
    # Ensure dialog present
    page.wait_for_selector("div.p-dialog-mask", timeout=9000)
    page.wait_for_selector("div.p-dialog", timeout=9000)
    page.wait_for_selector("div.p-dialog-content div.dialog-content", timeout=9000)
    page.wait_for_timeout(120)

    # Item Code: human-like typing (best for autocomplete and keyboard listeners)
    item_sel = "div.p-dialog-content div.dialog-content input[formcontrolname='itemCode']"
    page.wait_for_selector(item_sel, timeout=7000)
    human_type_input(page, item_sel, item_code, delay_seconds=0.03)

    # Audited Qty: first type, then verify form binding; if not bound, use JS fallback
    aud_sel = "div.p-dialog-content div.dialog-content input[formcontrolname='auditedQty']"
    page.wait_for_selector(aud_sel, timeout=7000)
    # human-typing (fires keyboard events)
    human_type_input(page, aud_sel, str(audited_qty), delay_seconds=0.02)
    # small tick for Angular to process
    page.wait_for_timeout(120)

    # Optional: verify the value is set in DOM; if not, enforce via JS
    try:
        current_val = page.locator(aud_sel).first.get_attribute("value")
        # Sometimes the attribute may remain empty while valueAsNumber is set; check both
        if current_val is None or current_val.strip() == "":
            js_set_number_with_events(page, aud_sel, str(audited_qty))
    except Exception:
        # fallback enforcement
        js_set_number_with_events(page, aud_sel, str(audited_qty))

    # Damaged Qty: similar approach (optional field)
    dam_sel = "div.p-dialog-content div.dialog-content input[formcontrolname='damagedQty']"
    try:
        page.wait_for_selector(dam_sel, timeout=2000)
        human_type_input(page, dam_sel, str(damaged_qty), delay_seconds=0.02)
        page.wait_for_timeout(80)
        try:
            cur = page.locator(dam_sel).first.get_attribute("value")
            if cur is None or cur.strip() == "":
                js_set_number_with_events(page, dam_sel, str(damaged_qty))
        except Exception:
            js_set_number_with_events(page, dam_sel, str(damaged_qty))
    except PlaywrightTimeoutError:
        # damagedQty not present â€” ignore
        pass

    # Click Save (button inside dialog)
    save_sel = "div.p-dialog-content div.dialog-content button.button.primary-button:has-text('Save')"
    page.wait_for_selector(save_sel, timeout=6000)
    page.locator(save_sel).first.click()

    # Wait for dialog to close (mask detached) and network settle
    page.wait_for_selector("div.p-dialog-mask", state="detached", timeout=8000)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(200)


def add_item_count(page: Page, item_query: str, audited_qty: int = 0, damaged_qty: int = 0) -> bool:
    """
    Fill the autocomplete item, select the first suggestion, fill quantities, and click Add Count.
    Returns True on success (no try/except used).
    """
    ac_selector = "input.p-autocomplete-input[placeholder='Select Item Code / Name / Ean']"
    ac = page.locator(ac_selector).first
    ac.scroll_into_view_if_needed()
    ac.click()
    ac.fill(item_query)

    # Wait for suggestion list and select the first suggestion (common structures)
    try:
        page.wait_for_selector("#autoComplete_list li, #autoComplete_list .p-autocomplete-item", timeout=4000)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
    except PlaywrightTimeoutError:
        page.keyboard.press("Enter")

    page.wait_for_timeout(300)

    page.fill('input[formcontrolname="auditedQty"]', str(audited_qty))
    page.fill('input[formcontrolname="damagedQty"]', str(damaged_qty))

    # Click Add Count (button or link)
    try:
        page.click("button:has-text('Add Count')", timeout=3000)
    except Exception:
        page.click(":text('Add Count')", timeout=3000)

    page.wait_for_timeout(300)
    return True

# ----------------------
# Excel loader with validation (no try/except)
# ----------------------
def load_items_from_excel_validated(
    path: str,
    sheet_name=0,
    code_col: str = "code",
    audited_col: str = "audited",
    damaged_col: str = "damaged",
) -> List[Tuple[str, int, int]]:
    # 1) File exists
    if not os.path.exists(path):
        print(f"ERROR: Excel file not found: {path}")
        sys.exit(1)

    # 2) Read Excel (pandas will raise if it can't; we intentionally don't catch exceptions)
    df = pd.read_excel(path, sheet_name=sheet_name)

    # 3) Determine code column
    if code_col in df.columns:
        chosen_code_col = code_col
    else:
        # fallback to the first column name
        chosen_code_col = df.columns[0] if len(df.columns) >= 1 else None
        if chosen_code_col is None:
            print("ERROR: Excel has no columns to use as item code.")
            sys.exit(1)
        print(f"WARNING: '{code_col}' not found. Using first column '{chosen_code_col}' as code.")

    # 4) Determine audited column (fallback to second column)
    if audited_col in df.columns:
        chosen_audited_col = audited_col
    else:
        chosen_audited_col = df.columns[1] if len(df.columns) >= 2 else None
        if chosen_audited_col is None:
            print(f"WARNING: '{audited_col}' not found and no second column available; defaulting audited values to 0.")
        else:
            print(f"WARNING: '{audited_col}' not found. Using column '{chosen_audited_col}' as audited.")

    # 5) Determine damaged column (fallback to third column)
    if damaged_col in df.columns:
        chosen_damaged_col = damaged_col
    else:
        chosen_damaged_col = df.columns[2] if len(df.columns) >= 3 else None
        if chosen_damaged_col is None:
            print(f"WARNING: '{damaged_col}' not found and no third column available; defaulting damaged values to 0.")
        else:
            print(f"WARNING: '{damaged_col}' not found. Using column '{chosen_damaged_col}' as damaged.")

    # 6) Build items list, coercing numeric columns
    items = []
    for idx, row in df.iterrows():
        raw_code = row.get(chosen_code_col, "") if chosen_code_col is not None else ""
        code = str(raw_code).strip()
        if not code:
            # skip rows with empty code
            continue

        # audited value: if we have a chosen column else default 0
        if chosen_audited_col is not None:
            audited_raw = row.get(chosen_audited_col, 0)
            audited_num = pd.to_numeric([audited_raw], errors="coerce")[0]
            audited = int(audited_num) if not pd.isna(audited_num) else 0
        else:
            audited = 0

        # damaged value
        if chosen_damaged_col is not None:
            damaged_raw = row.get(chosen_damaged_col, 0)
            damaged_num = pd.to_numeric([damaged_raw], errors="coerce")[0]
            damaged = int(damaged_num) if not pd.isna(damaged_num) else 0
        else:
            damaged = 0

        items.append((code, audited, damaged))

    # 7) Final check: at least one item
    if not items:
        print("WARNING: No valid items found in Excel. The run will proceed with an empty list.")
    return items

# ----------------------
# Config: only Excel
# ----------------------
EXCEL_PATH = "C:\\Users\\HP\\Documents\\input\\data_items.xlsx"   # update path
EXCEL_SHEET = 0
EXCEL_CODE_COL = "code"
EXCEL_AUDITED_COL = "audited"
EXCEL_DAMAGED_COL = "damaged"

def normalize(text: str) -> str:
    """Remove commas and extra spaces"""
    return text.replace(",", "").strip()

def open_audit_summary(page: Page):
    page.get_by_role("button", name="Audit Summary").click()
    page.wait_for_load_state("networkidle")


# --------------------------------------------------
# TOTAL ROW VALIDATION (PRINT ALL + FAIL AT END)
# --------------------------------------------------
def verify_total_values(page: Page):
    total = page.locator("tfoot tr")

    # Column indexes based on table
    COL = {
        "Stock Value": 1,
        "Audited Value": 2,
        "Damaged Value": 3,
        "StockLoss Value": 4,
        "Stock Excess Value": 6,
        "Completed Inventory": 7
    }

    # Expected values
    EXPECTED = {
        "Stock Value": "5000",
        "Audited Value": "2000",
        "Damaged Value": "3000",
        "StockLoss Value": "2000",
        "Stock Excess Value": "2000",
        "Completed Inventory": "50"
    }

    errors = []  # ðŸ”¥ collect all mismatches

    print("\nðŸ“Š TOTAL ROW VALUES (Actual vs Expected)")
    print("-" * 65)

    for label, index in COL.items():
        actual = normalize(total.locator("td").nth(index).inner_text())
        expected = EXPECTED[label]

        if actual == expected:
            print(f"âœ… {label:25} | Actual: {actual:>8} | Expected: {expected}")
        else:
            print(f"âŒ {label:25} | Actual: {actual:>8} | Expected: {expected}")
            errors.append(
                f"{label} mismatch (Expected={expected}, Actual={actual})"
            )

    print("-" * 65)

    # ðŸ”¥ Fail ONLY after printing everything
    if errors:
        raise AssertionError(
            "\nâŒ TOTAL ROW VALIDATION FAILED:\n - " + "\n - ".join(errors)
        )

    print("âœ… TOTAL ROW VALIDATION PASSED\n")

# ----------------------
# Entry point (minimal validation, no try/except)
# ----------------------
if __name__ == "__main__":

     # ðŸ”¥ One item only
    code = "ABC1123"
    aud_qty = 10
    dam_qty = 0

    # Load and validate items (will sys.exit if file missing or irrecoverable)
    items_to_add = load_items_from_excel_validated(
        EXCEL_PATH,
        sheet_name=EXCEL_SHEET,
        code_col=EXCEL_CODE_COL,
        audited_col=EXCEL_AUDITED_COL,
        damaged_col=EXCEL_DAMAGED_COL,
    )

    # Start Playwright and run flow (no try/except)
    with sync_playwright() as p:
        browser, page = login(
            p,
            browser_name="chrome",  # chrome / edge / firefox
            environment="QA"        # PRODUCTION / STAGING / QA / DEV
        )
        qtest(page)
        
         # open modal once
        click_add_item_button(page)

            # fill item details
        fill_item_details_bound(page, code, aud_qty, dam_qty)
        print(f"Processed {code} ({aud_qty}/{dam_qty})")
        detect_feedback(page)
    

            # wait a bit before closing
        page.wait_for_timeout(500)

        for code, audited, damaged in items_to_add:
            add_item_count(page, code, audited_qty=audited, damaged_qty=damaged)
            print(f"Processed {code} ({audited}/{damaged})")
            detect_feedback(page)
        
        open_audit_summary(page)
        # ðŸ”¥ Print all columns + validate
        verify_total_values(page)






