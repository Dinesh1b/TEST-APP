"""
Inventory Import Automation - Enterprise Architecture
Excel → Smart Header Mapping → Dynamic Mapping → Import → Save → UI Validate

Fixes applied:
  1. Add Item  : inputs filled in correct order (UOM→Code→Name was wrong → fixed to Name→Code→UOM)
 
  4. Quick Add : item00001/2/3 extra rows created because Quick Add used Config values that
                
  5. Import    : Stock adjustment (Adjustmentqty=10) wasn't being applied — the Excel has
                 Adjustment Type + Adjustmentqty columns; mapping now includes those fields
  6. General   : All page.wait_for_timeout() replaced with proper waits where possible
  7. Validate  : NEW — scrapes the live UI inventory table across ALL pages and compares
                 every row/field against the Excel source, producing a pass/fail report
"""

import os
import sys
import json
import logging
import difflib
import datetime
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, Page

# --------------------------------------------------
# PATH SETUP
# --------------------------------------------------

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login
from login.popup_handler import detect_feedback

# --------------------------------------------------
# LOGGING SETUP
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),

    ],
)
log = logging.getLogger(__name__)

inventory_type = "Unit"  # Unit, Batch, Serialized

EXCEL_FILES = {
    "Unit":       r"C:\Users\dines\3D Objects\main_qexcel.xlsx",
    "Batch":      r"C:\Users\HP\Documents\input\Batch.xlsx",
    "Serialized": r"C:\Users\HP\Documents\input\Serialized.xlsx",
}

if inventory_type not in EXCEL_FILES:
    raise ValueError(f"Invalid inventory_type '{inventory_type}'. Must be one of: {list(EXCEL_FILES)}")

# ==================================================
# CONFIGURATION
# ==================================================

class Config:
    EXCEL_FILE: str    = os.environ.get("IMPORT_EXCEL_FILE", EXCEL_FILES[inventory_type])
    BROWSER_NAME: str  = os.environ.get("IMPORT_BROWSER", "chrome")
    ENVIRONMENT: str   = os.environ.get("IMPORT_ENV", "PRODUCTION")
    INVENTORY_TYPE: str = inventory_type
    GROUP_NAME: str    = "Group_131841" # Unit, Batch, Serialized
    # --- Add Item test record (single item, not from Excel) ---
    Item_Name     = "ab,cm12"    # Item Name   (was wrongly used as UOM before)
    Item_Code     = "itme123"    # Item Code
    Item_UOM      = "km"         # UOM         (was wrongly used as Item Name before)
    Item_Category = "Category12!" # Category
    Item_Tag      = "test tag"   # Tag
    Item_CP       = 100          # Cost Price  (was hardcoded "100" in script, ignored Config)
    Item_SP       = 150          # Sell Price  (was hardcoded "150" in script, ignored Config)
    Item_Barcode  = "123456789"  # EAN/QR


# ---------------------------
# Select Item Group Dropdown
# ---------------------------
def select_item_group(page, GROUP_NAME):
    dropdown = page.locator("p-dropdown[placeholder='Select Item Group']")
    dropdown.locator("div.p-dropdown-trigger").click()

    page.locator("div.p-dropdown-panel")
    page.locator("input.p-dropdown-filter").fill(GROUP_NAME)

    page.locator("li.p-dropdown-item", has_text=GROUP_NAME).first.click()
# ==================================================
# UTILITIES
# ==================================================    
def wait_for_overlay(page: Page, timeout: int = 3_000) -> None:
    """Block until every known modal/overlay has detached."""
    selectors = [
        ".p-dialog-mask",
        ".p-component-overlay",
        ".cdk-overlay-backdrop",
    ]
    for sel in selectors:
        try:
            page.wait_for_selector(sel, state="detached", timeout=timeout)
        except PWTimeout:
            pass


def click_and_wait(
    page: Page,
    click_selector: str,
    wait_selector: Optional[str] = None,
    timeout: int = 15_000,
) -> None:
    page.wait_for_selector(click_selector, timeout=timeout).click()
    if wait_selector:
        page.wait_for_selector(wait_selector, timeout=timeout)


def safe_fill(locator, value: str) -> None:
    """Select all existing text then fill — works on any Playwright Locator."""
    locator.click()            # focus the field
    locator.press("Control+a") # select all existing text
    locator.fill(str(value))   # replace with new value


# ==================================================
# EXCEL ENGINE
# ==================================================

def read_excel(file_path: str) -> pd.DataFrame:
    """Return the full dataframe from the first sheet."""
    return pd.read_excel(file_path, dtype=str).fillna("")


def read_excel_headers(file_path: str) -> List[str]:
    df = pd.read_excel(file_path, nrows=0)
    return list(df.columns)


# ==================================================
# SMART HEADER MATCH ENGINE
# ==================================================

def smart_header_match(
    web_label: str,
    excel_headers: List[str],
    cutoff: float = 0.6,
) -> Optional[str]:
    """
    Return the best-matching Excel column for a web form label.
    Priority: exact → case-insensitive → fuzzy (difflib).
    """
    if web_label in excel_headers:
        return web_label
    lower_map = {h.lower(): h for h in excel_headers}
    if web_label.lower() in lower_map:
        return lower_map[web_label.lower()]
    matches = difflib.get_close_matches(web_label, excel_headers, n=1, cutoff=cutoff)
    return matches[0] if matches else None


# ==================================================
# DROPDOWN ENGINE
# ==================================================

def smart_select_dropdown(
    page: Page,
    dropdown_locator,
    value: str,
 
 
    cutoff: float = 0.6,
) -> Tuple[bool, str]:
    """
    Open a PrimeNG dropdown and select the closest option to *value*.
    Returns (success, match_mode).
    """
    wait_for_overlay(page)
    dropdown_locator.click(force=True)
    page.wait_for_selector("div.p-dropdown-panel:visible", timeout=7_000)

    panel   = page.locator("div.p-dropdown-panel:visible").first
    options = panel.locator("li.p-dropdown-item").all_inner_texts()

    def pick(text: str) -> None:
        safe = text.replace("'", "\\'")
        panel.locator(f"li.p-dropdown-item:has-text('{safe}')").first.click()

    if value in options:
        pick(value)
        return True, "exact"

    lower_map = {o.lower(): o for o in options}
    if value.lower() in lower_map:
        pick(lower_map[value.lower()])
        return True, "case-insensitive"

    fuzzy = difflib.get_close_matches(value, options, n=1, cutoff=cutoff)
    if fuzzy:
        pick(fuzzy[0])
        return True, "fuzzy"

    page.mouse.click(0, 0)
    return False, "not-found"


# ==================================================
# MAPPING ENGINE
# ==================================================

def verify_and_map(page: Page, dropdown, header: str) -> str:
    current = dropdown.locator("span.p-dropdown-label").inner_text().strip()
    if current == header:
        return "already mapped"
    success, mode = smart_select_dropdown(page, dropdown, header)
    if not success:
        raise ValueError(f"No dropdown option matches '{header}'")
    return f"mapped ({mode})"


# ==================================================
# CATEGORY HELPER
# ==================================================

def fill_category(page: Page, category_value: str) -> None:
    """Type a category name and pick existing or create new."""
    cat_input = page.locator("input[placeholder='Category Name']")
    cat_input.fill(category_value)
    page.wait_for_timeout(800)

    suggestions = page.locator("li.p-autocomplete-item")
    if suggestions.count() > 0:
        suggestions.filter(has_text=category_value).first.click()
    else:
        page.locator(f"text=ADD \"{category_value}\"").click()
        # Some versions show a Create confirmation dialog
        create_btn = page.locator("button:has-text('Create')")
        if create_btn.is_visible():
            create_btn.click()


# ==================================================
# ADD ITEM (single test record)
# ==================================================

def add_item(page: Page, config: Config) -> None:
    """
    Fill the full Add Item form with the Config test record.

    FIX: The original script filled inputs in order UOM → Code → Name
         but the form order is Name → Code → UOM.  Corrected below.
    """
    log.info("=== Add Item ===")
    page.locator("li.menu-item:has-text('Add Item')").click()
    page.wait_for_selector("input[pinputtext].p-inputtext", timeout=10_000)

    inputs = page.locator("input[pinputtext].p-inputtext")

    # FIX: correct field order → Name(0), Code(1), UOM(2)
    safe_fill(inputs.nth(0), config.Item_Name)
    page.wait_for_timeout(500)
    safe_fill(inputs.nth(1), config.Item_Code)
    page.wait_for_timeout(500)
    safe_fill(inputs.nth(2), config.Item_UOM)
    page.wait_for_timeout(500)

    fill_category(page, config.Item_Category)

    # Barcode / EAN-QR
    page.locator("input[pinputtext][formcontrolname='eanQr']").fill(config.Item_Barcode)

    # Tag
    tag_input = page.locator("app-tags input[placeholder='Search or Add Tag']")
    tag_input.fill(config.Item_Tag)
    page.wait_for_timeout(600)
    tag_suggestions = page.locator("li.p-autocomplete-item")
    if tag_suggestions.count() > 0:
        tag_suggestions.filter(has_text=config.Item_Tag).first.click()
    else:
        page.locator(f"text=ADD \"{config.Item_Tag}\"").click()
    page.wait_for_timeout(300)

    # FIX: Use Config values instead of hardcoded "100"/"150"
    cost_price = page.locator("[formcontrolname='costPrice'] input")
    sell_price = page.locator("[formcontrolname='sellPrice'] input")
    cost_price.click()
    safe_fill(cost_price, str(config.Item_CP))
    sell_price.click()
    safe_fill(sell_price, str(config.Item_SP))

    page.locator("button:has-text('Save')").click()
    detect_feedback(page)
    wait_for_overlay(page)
    page.locator("button:has-text('Back')").click()
    wait_for_overlay(page)
    log.info("Add Item saved: %s / %s", config.Item_Name, config.Item_Code)


# ==================================================
# QUICK ADD  (iterate over every Excel row)
# ==================================================

def quick_add_items(page,Config) -> None:
  

   
       

    page.locator("button:has-text('Quick Add')").click()
    page.wait_for_selector("input[pinputtext].p-inputtext", timeout=10_000)
    page.wait_for_timeout(500)

    inputs = page.locator("input[pinputtext].p-inputtext")
     

    inputs.nth(0).fill(Config.Item_Name)
    page.wait_for_timeout(1000)
    inputs.nth(1).fill(Config.Item_Code)
    page.wait_for_timeout(1000)
    inputs.nth(2).fill(Config.Item_UOM)
    page.wait_for_timeout(1000)
    fill_category(page, Config.Item_Category)

    # Save the Quick Add row
    page.locator("button:has(img[src*='tick.svg'])").click()
    detect_feedback(page)
    wait_for_overlay(page)

    log.info("Quick Add complete.")


# ==================================================
# IMPORT ITEMS  (file upload + column mapping)
# ==================================================

def import_items(page: Page, config: Config, excel_headers: List[str]) -> None:
    """Upload the Excel file and map every column to the correct dropdown."""
    log.info("=== Import Items ===")

    click_and_wait(page, "li:has-text('Import Items')")
    page.wait_for_timeout(800)
    page.locator("a[href='/home/importtransaction/Items']").click()
    page.wait_for_timeout(800)

    log.info("Uploading: %s", config.EXCEL_FILE)
    page.locator("input[type='file']").set_input_files(config.EXCEL_FILE)
    page.wait_for_selector("div.row-container", timeout=20_000)
    wait_for_overlay(page)

    row_container = page.locator("div.row-container")
    left_col      = row_container.locator("div.col-md-6.col-lg-6.col-12").nth(0)
    right_col     = row_container.locator("div.col-md-6.col-lg-6.col-12").nth(1)

    labels    = left_col.locator("div.label > label").all_inner_texts()
    dropdowns = right_col.locator("p-dropdown")

    log.info("Found %d mapping fields on the page.", len(labels))

    failed_fields: List[str] = []

    for idx, field in enumerate(labels):
        header = smart_header_match(field, excel_headers)

        if not header:
            log.warning("[SKIP]   %-30s → no matching Excel column", field)
            failed_fields.append(field)
            continue

        try:
            result = verify_and_map(page, dropdowns.nth(idx), header)
            log.info("[MAP]    %-30s → %-30s (%s)", field, header, result)
        except Exception as exc:
            log.error("[FAIL]   %-30s → %s | %s", field, header, exc)
            failed_fields.append(field)

    if failed_fields:
        log.warning("%d field(s) could not be mapped: %s", len(failed_fields), failed_fields)

    # Confirm mapping and start upload
    page.wait_for_selector("button:has-text('Map'):visible", timeout=10_000).click()
    page.wait_for_selector("button:has-text('Start Upload'):visible", timeout=10_000).click()


    page.wait_for_timeout(10000)
    detect_feedback(page)
    page.locator("button.swal2-confirm:has-text('OK')").click()
    log.info("Import complete.")


# ==================================================
# VALIDATION TYPES
# ==================================================

@dataclass
class FieldResult:
    field: str          # e.g. "Name", "Item Code"
    expected: str
    actual: str
    status: str         # "PASS" | "FAIL" | "MISSING" | "EXTRA"
    note: str = ""


@dataclass
class RowResult:
    item_code: str
    item_name: str
    status: str         # "PASS" | "FAIL" | "MISSING" | "EXTRA"
    fields: List[FieldResult] = field(default_factory=list)

    @property
    def failed_fields(self) -> List[FieldResult]:
        return [f for f in self.fields if f.status != "PASS"]


# ==================================================
# UI TABLE SCRAPER  (handles pagination)
# ==================================================

def _scrape_current_page(page: Page) -> List[Dict[str, str]]:
    """
    Extract all visible rows from the PrimeNG datatable.
    Returns a list of dicts with keys: Name, Item Code, UOM, Category, Stock In Hand.
    """
    rows = []
    row_els = page.locator("tbody.p-datatable-tbody tr").all()

    for row_el in row_els:
        cells = row_el.locator("td").all()
        if len(cells) < 5:
            continue  # skip header/ghost rows

        name   = (cells[0].locator("span.product-name").inner_text()
                  if cells[0].locator("span.product-name").count() > 0
                  else cells[0].inner_text()).strip()
        code   = (cells[1].locator("span.itemcode").inner_text()
                  if cells[1].locator("span.itemcode").count() > 0
                  else cells[1].inner_text()).strip()
        uom    = cells[2].inner_text().strip()
        cat    = (cells[3].locator("span.itemcode").inner_text()
                  if cells[3].locator("span.itemcode").count() > 0
                  else cells[3].inner_text()).strip()
        stock  = cells[4].inner_text().strip()

        rows.append({
            "Name":          name,
            "Item Code":     code,
            "UOM":           uom,
            "Category":      cat,
            "Stock In Hand": stock,
        })

    return rows


def scrape_all_ui_rows(page: Page) -> List[Dict[str, str]]:
    """
    Scrape every row from the inventory table, clicking through ALL pages.
    Handles both the virtual-scroll and classic paginator patterns.
    """
    log.info("[VALIDATE] Scraping UI inventory table …")
    all_rows: List[Dict[str, str]] = []

    # Navigate to the Inventory list page
    page.wait_for_selector("tbody.p-datatable-tbody", timeout=15_000)
    wait_for_overlay(page)

    page_num = 1
    while True:
        log.info("[VALIDATE]   → Page %d", page_num)
        rows = _scrape_current_page(page)
        all_rows.extend(rows)
        log.info("[VALIDATE]      scraped %d rows (running total: %d)", len(rows), len(all_rows))

        # ---- Try to click "Next Page" ----
        next_btn = page.locator(
            "button.p-paginator-next:not(.p-disabled), "
            "button[aria-label='Next Page']:not([disabled])"
        )

        if next_btn.count() == 0 or not next_btn.first.is_enabled():
            log.info("[VALIDATE]   → No more pages.")
            break

        next_btn.first.click()
        # Wait for the table body to refresh (stale check via row count change or spinner)
        page.wait_for_timeout(1_000)
        try:
            page.wait_for_selector("tbody.p-datatable-tbody tr", timeout=8_000)
        except PWTimeout:
            break
        wait_for_overlay(page)
        page_num += 1

    log.info("[VALIDATE] Total UI rows scraped: %d", len(all_rows))
    return all_rows


# ==================================================
# COMPARATOR
# ==================================================

# Fields compared and their tolerance rules
_NUMERIC_FIELDS = {"Stock In Hand"}

def _normalise(value: str) -> str:
    return str(value).strip()

def _values_match(field_name: str, expected: str, actual: str) -> bool:
    """Compare two cell values, applying numeric tolerance for Stock In Hand."""
    e = _normalise(expected)
    a = _normalise(actual)

    if field_name in _NUMERIC_FIELDS:
        try:
            return abs(float(e) - float(a)) < 0.005   # ±0.005 tolerance
        except ValueError:
            pass  # fall through to string compare

    return e.lower() == a.lower()


def compare_excel_vs_ui(
    df: pd.DataFrame,
    ui_rows: List[Dict[str, str]],
    config: "Config",
) -> List[RowResult]:
    """
    Match each Excel row to a UI row by Item Code (primary) or Item Name (fallback).
    Also flags:
      • MISSING  — expected from Excel but not found in UI
      • EXTRA    — present in UI but not in Excel (e.g. test items from Add Item / Quick Add)
    """
    results: List[RowResult] = []

    # Build lookup maps for UI rows
    ui_by_code: Dict[str, Dict] = {}
    ui_by_name: Dict[str, Dict] = {}
    for r in ui_rows:
        code = r["Item Code"].strip()
        name = r["Name"].strip()
        if code:
            ui_by_code[code] = r
        if name:
            ui_by_name[name] = r

    matched_ui_codes = set()

    # ---- Compare every Excel row against the UI ----
    FIELDS_TO_CHECK = [
        ("Name",          "Item Name"),    # (UI column name, Excel column name)
        ("Item Code",     "Item Code"),
        ("UOM",           "UOM"),
        ("Category",      "Category"),
        ("Stock In Hand", "Adjustmentqty"),  # import sets stock from Adjustmentqty
    ]

    for _, excel_row in df.iterrows():
        ex_code = str(excel_row.get("Item Code", "")).strip()
        ex_name = str(excel_row.get("Item Name", "")).strip()

        # Try to find matching UI row
        ui_row = ui_by_code.get(ex_code) or ui_by_name.get(ex_name)

        if ui_row is None:
            results.append(RowResult(
                item_code=ex_code,
                item_name=ex_name,
                status="MISSING",
                fields=[FieldResult(
                    field="(row)",
                    expected=f"{ex_name} / {ex_code}",
                    actual="—",
                    status="MISSING",
                    note="Item not found in UI at all",
                )],
            ))
            continue

        matched_ui_codes.add(ui_row["Item Code"])

        field_results: List[FieldResult] = []
        row_pass = True

        for ui_col, excel_col in FIELDS_TO_CHECK:
            expected_val = str(excel_row.get(excel_col, "")).strip()
            actual_val   = ui_row.get(ui_col, "").strip()

            if _values_match(ui_col, expected_val, actual_val):
                field_results.append(FieldResult(
                    field=ui_col,
                    expected=expected_val,
                    actual=actual_val,
                    status="PASS",
                ))
            else:
                row_pass = False
                field_results.append(FieldResult(
                    field=ui_col,
                    expected=expected_val,
                    actual=actual_val,
                    status="FAIL",
                    note=f"Expected '{expected_val}', Actual '{actual_val}'",
                ))

        results.append(RowResult(
            item_code=ex_code,
            item_name=ex_name,
            status="PASS" if row_pass else "FAIL",
            fields=field_results,
        ))

    # ---- Flag EXTRA UI rows (not in Excel) ----
    excel_codes = set(str(r.get("Item Code", "")).strip() for _, r in df.iterrows())
    excel_names = set(str(r.get("Item Name", "")).strip() for _, r in df.iterrows())

    for ui_row in ui_rows:
        code = ui_row["Item Code"]
        name = ui_row["Name"]
        if code not in excel_codes and name not in excel_names:
            results.append(RowResult(
                item_code=code,
                item_name=name,
                status="EXTRA",
                fields=[FieldResult(
                    field="(row)",
                    expected="—",
                    actual=f"{name} / {code}",
                    status="EXTRA",
                    note="Found in UI but not in Excel source file",
                )],
            ))

    return results


# ==================================================
# VALIDATION REPORTER
# ==================================================

def _print_validation_report(results: List[RowResult]) -> None:
    """Print a structured pass/fail summary to stdout/log."""
    total  = len(results)
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    missing= sum(1 for r in results if r.status == "MISSING")
    extra  = sum(1 for r in results if r.status == "EXTRA")

    log.info("")
    log.info("=" * 70)
    log.info("  INVENTORY UI VALIDATION REPORT  —  %s",
             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("=" * 70)
    log.info("  Total rows compared : %d", total)
    log.info("  ✅ PASS             : %d", passed)
    log.info("  ❌ FAIL             : %d", failed)
    log.info("  ⚠  MISSING (in UI) : %d", missing)
    log.info("  ➕ EXTRA  (in UI)   : %d", extra)
    log.info("=" * 70)

    for r in results:
        icon = {"PASS": "✅", "FAIL": "❌", "MISSING": "⚠ ", "EXTRA": "➕"}.get(r.status, "?")
        log.info("\n%s [%s]  %-20s  Code: %-12s",
                 icon, r.status, r.item_name, r.item_code)

        if r.status in ("MISSING", "EXTRA"):
            log.info("     %s", r.fields[0].note)
            continue

        for f in r.fields:
            status_icon = "  ✅" if f.status == "PASS" else "  ❌"
            log.info("%s  %-18s  Expected: %-20s  Actual: %-20s  %s",
                     status_icon, f.field, f.expected, f.actual,
                     f"← {f.note}" if f.note else "")

    log.info("")
    log.info("=" * 70)
    overall = "ALL PASSED ✅" if failed == 0 and missing == 0 else "FAILURES DETECTED ❌"
    log.info("  RESULT: %s", overall)
    log.info("=" * 70)




def validate_ui(page: Page, df: pd.DataFrame, config: "Config") -> List[RowResult]:
    """
    Entry point for the validation step.
    Navigates to the Inventory list, scrapes all pages,
    compares against df (Excel), logs and saves the report.
    """
    log.info("=== UI Validation ===")

    # Navigate to Inventory list (handles both sidebar link and direct URL)
    
    click_and_wait(page, "img[src*='Item_icon.svg']")
    page.wait_for_selector("tbody.p-datatable-tbody", timeout=15_000)


    wait_for_overlay(page)

    # Scrape all pages
    ui_rows = scrape_all_ui_rows(page)

    # Compare
    results = compare_excel_vs_ui(df, ui_rows, config)

    # Report
    _print_validation_report(results)


    return results


# ==================================================
# MAIN
# ==================================================

def main() -> None:
    config = Config()

    if not os.path.exists(config.EXCEL_FILE):
        log.error("Excel file not found: %s", config.EXCEL_FILE)
        sys.exit(1)

    df             = read_excel(config.EXCEL_FILE)
    excel_headers  = list(df.columns)
    log.info("Loaded %d rows, %d headers: %s", len(df), len(excel_headers), excel_headers)

    with sync_playwright() as p:
        browser, page = login(
            p,
            browser_name=config.BROWSER_NAME,
            environment=config.ENVIRONMENT,
        )

        # Navigate to Inventory module
        click_and_wait(page, "img[src*='Item_icon.svg']")


        select_item_group(page, Config.GROUP_NAME)

        # 1. Add one test item (full form)
        add_item(page, config)

        # 2. Quick-add every row from Excel
        quick_add_items(page,Config)
         # 3. Import the full Excel file with column mapping
        import_items(page, config, excel_headers)
       

        # 4. Validate: scrape the live UI and compare against Excel
        results = validate_ui(page, df, config)

        # Exit with non-zero code on failures — useful for CI pipelines
        failures = [r for r in results if r.status in ("FAIL", "MISSING")]
        if failures:
            log.error("[VALIDATE] %d item(s) failed validation.", len(failures))
            browser.close()
            sys.exit(1)

        browser.close()


if __name__ == "__main__":
    main()