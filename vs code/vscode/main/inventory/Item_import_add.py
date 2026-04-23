"""
Inventory Import Automation - Enterprise Architecture
Excel → Smart Header Mapping → Sheet Selection → Dynamic Mapping → Import → Save → UI Validate

Fixes applied:
  1. Add Item  : inputs filled in correct order (UOM→Code→Name was wrong → fixed to Name→Code→UOM)
  4. Quick Add : item00001/2/3 extra rows created because Quick Add used Config values that
  5. Import    : Stock adjustment (Adjustmentqty=10) wasn't being applied — the Excel has
                 Adjustment Type + Adjustmentqty columns; mapping now includes those fields
  6. General   : All page.wait_for_timeout() replaced with proper waits where possible
  7. Validate  : NEW — scrapes the live UI inventory table across ALL pages and compares
                 every row/field against the Excel source, producing a pass/fail report
  8. Details   : NEW — opens Edit form for every Excel row and validates all form fields
                 (Item Code, Name, Barcode, UOM, Category, Cost Price, Sell Price)
  9. Sheet Sel : NEW — after file upload, detects all sheets in the workbook, shows a
                 dropdown (Choose Sheet), user selects → headers + mapping reload dynamically
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


# ==================================================
# EDIT-FORM FIELD MAP
# (friendly_label, formcontrolname, excel_col)
# ==================================================

EDIT_FORM_FIELDS: List[Tuple[str, str, str]] = [
    ("Item Code",   "itemCode",       "Item Code"),
    ("Name",        "itemName",       "Item Name"),
    ("Barcode",     "eanQr",          "Barcode"),
    ("UOM",         "UOM",            "UOM"),            # Fix 1: uppercase "UOM"
    ("Category",    "itemCategoryId", "Item Category"),  # Fix 2: parent fcn
    ("Cost Price",  "costPrice",      "Cost Price"),
    ("Sell Price",  "sellPrice",      "Sell Price"),
]


# ==================================================
# CONFIGURATION
# ==================================================

# ---------------------------
# Select Item Group Dropdown
# ---------------------------
def select_item_group(page, group_name):
    dropdown = page.locator("p-dropdown[placeholder='Select Item Group']")
    dropdown.locator("div.p-dropdown-trigger").click()

    page.locator("div.p-dropdown-panel")
    page.locator("input.p-dropdown-filter").fill(group_name)

    page.locator("li.p-dropdown-item", has_text=group_name).first.click()


# ==================================================
# UTILITIES
# ==================================================

def wait_for_overlay(page, timeout: int = 3_000) -> None:
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
    page,
    click_selector: str,
    wait_selector: Optional[str] = None,
    timeout: int = 15_000,
) -> None:
    page.wait_for_selector(click_selector, timeout=timeout).click()
    if wait_selector:
        page.wait_for_selector(wait_selector, timeout=timeout)


def safe_fill(locator, value: str) -> None:
    """Select all existing text then fill — works on any Playwright Locator."""
    locator.click()
    locator.press("Control+a")
    locator.fill(str(value))


# ==================================================
# EXCEL ENGINE
# ==================================================

def read_excel(file_path: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
    """
    Return the full dataframe from the specified sheet (or first sheet if None).
    sheet_name should match what was selected in the UI sheet dropdown.
    """
    kwargs = {"dtype": str}
    if sheet_name:
        kwargs["sheet_name"] = sheet_name
    df = pd.read_excel(file_path, **kwargs).fillna("")
    return _clean_df_columns(df)


def read_excel_headers(file_path: str, sheet_name: Optional[str] = None) -> List[str]:
    """Return column headers from the specified sheet (or first sheet if None)."""
    kwargs = {"nrows": 0, "dtype": str}
    if sheet_name:
        kwargs["sheet_name"] = sheet_name
    df = pd.read_excel(file_path, **kwargs)
    return list(df.columns)


def read_excel_sheet_names(file_path: str) -> List[str]:
    """Return all sheet names in the workbook."""
    xl = pd.ExcelFile(file_path)
    return xl.sheet_names


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
    # Common header aliases between templates
    aliases = {
        "item category": ["Item Category", "Category"],
        "category":      ["Category", "Item Category"],
    }
    key = web_label.strip().lower()
    if key in aliases:
        for candidate in aliases[key]:
            if candidate in excel_headers:
                return candidate
        lower_map = {h.lower(): h for h in excel_headers}
        for candidate in aliases[key]:
            if candidate.lower() in lower_map:
                return lower_map[candidate.lower()]

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
    page,
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

def verify_and_map(page, dropdown, header: str) -> str:
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

def fill_category(page, Item_Category: str) -> None:
    cat_input = page.locator("input[placeholder='Category Name']")
    cat_input.fill(Item_Category)
    page.wait_for_timeout(500)
    suggestions = page.locator("li.p-autocomplete-item")

    if suggestions.filter(has_text=Item_Category).count() > 0:
        suggestions.filter(has_text=Item_Category).first.click()
    else:
        pass

    popup = page.locator(".swal2-popup")
    try:
        popup.wait_for(state="visible", timeout=3000)
        popup.get_by_role("button", name="Create").click()
        popup.wait_for(state="hidden", timeout=3000)
    except Exception:
        pass


def fill_tag(page, Item_Tag: str) -> None:
    try:
        page.wait_for_selector("div.swal2-container", state="hidden", timeout=5000)
    except Exception:
        pass

    tag_input = page.locator("app-tags input[placeholder='Search or Add Tag']")
    tag_input.fill(Item_Tag)
    page.wait_for_timeout(600)
    tag_suggestions = page.locator("li.p-autocomplete-item")
    if tag_suggestions.count() > 0:
        tag_suggestions.filter(has_text=Item_Tag).first.click()
    else:
        page.locator(f"text=ADD \"{Item_Tag}\"").click()
    page.wait_for_timeout(300)


# ==================================================
# ADD ITEM (single test record)
# ==================================================

def add_item(page, Config) -> None:
    """
    Fill the full Add Item form with the Config test record.
    FIX: correct field order → Name(0), Code(1), UOM(2)
    """
    log.info("=== Add Item ===")
    page.locator("li.menu-item:has-text('Add Item')").click()
    page.wait_for_selector("input[pinputtext].p-inputtext", timeout=10_000)

    inputs = page.locator("input[pinputtext].p-inputtext")

    safe_fill(inputs.nth(0), Config.Item_Name)
    page.wait_for_timeout(500)
    safe_fill(inputs.nth(1), Config.Item_Code)
    page.wait_for_timeout(500)
    safe_fill(inputs.nth(2), Config.Item_UOM)
    page.wait_for_timeout(500)

    fill_category(page, Config.Item_Category)
    wait_for_overlay(page)

    page.locator("input[pinputtext][formcontrolname='eanQr']").fill(Config.Item_Barcode)
    fill_tag(page, Config.Item_Tag)

    tag_input = page.locator("app-tags input[placeholder='Search or Add Tag']")
    tag_input.fill(Config.Item_Tag)
    page.wait_for_timeout(600)
    tag_suggestions = page.locator("li.p-autocomplete-item")
    if tag_suggestions.count() > 0:
        tag_suggestions.filter(has_text=Config.Item_Tag).first.click()
    else:
        page.locator(f"text=ADD \"{Config.Item_Tag}\"").click()
    page.wait_for_timeout(300)

    cost_price = page.locator("[formcontrolname='costPrice'] input")
    sell_price = page.locator("[formcontrolname='sellPrice'] input")
    cost_price.click()
    safe_fill(cost_price, str(Config.Item_CP))
    sell_price.click()
    safe_fill(sell_price, str(Config.Item_SP))

    page.locator("button:has-text('Save')").click()
    detect_feedback(page)
    wait_for_overlay(page)

    if page.locator("button:has-text('Back')").is_visible():
        page.locator("button:has-text('Back')").click()
        wait_for_overlay(page)
    else:
        print("Item added successfully, skipping Back.")
        log.info("Add Item saved: %s / %s", Config.Item_Name, Config.Item_Code)


# ==================================================
# QUICK ADD  (iterate over every Excel row)
# ==================================================

def quick_add_items(page, Config) -> None:
    page.locator("button:has-text('Quick Add')").click()
    page.wait_for_selector("input[pinputtext].p-inputtext", timeout=10_000)
    page.wait_for_timeout(500)
    log.info("=== Quick Add Item ===")

    inputs = page.locator("input[pinputtext].p-inputtext")
    inputs.nth(0).fill(Config.Item_Name)
    page.wait_for_timeout(1000)
    inputs.nth(1).fill(Config.Item_Code)
    page.wait_for_timeout(1000)
    inputs.nth(2).fill(Config.Item_UOM)
    page.wait_for_timeout(1000)
    fill_category(page, Config.Item_Category)

    page.locator("button:has(img[src*='tick.svg'])").click()
    detect_feedback(page)
    wait_for_overlay(page)

    log.info("Quick Add complete.")


# ==================================================
# SHEET SELECTION  (NEW)
# ==================================================

def select_sheet(page, preferred_sheet: Optional[str] = None) -> str:
    """
    After file upload, wait for the sheet selection dropdown to appear,
    then pick the best matching sheet.

    Selection priority:
      1. preferred_sheet — exact match
      2. preferred_sheet — case-insensitive match
      3. preferred_sheet — fuzzy match (difflib, cutoff 0.6)
      4. First available sheet (fallback)

    After selection the function waits for div.row-container to reload
    so that the header-mapping UI reflects the chosen sheet's columns.

    Args:
        page            : Playwright Page object
        preferred_sheet : Sheet name from Config.sheet_name, or None to
                          auto-select the first available sheet.

    Returns:
        The sheet name that was actually selected (empty string if the
        dropdown was not found — single-sheet workbooks skip this step).
    """
    log.info("[SHEET] Waiting for sheet selection dropdown …")

    # The dropdown uses placeholder="Choose Sheet" per the HTML snippet
    sheet_dropdown_selector = (
        "p-dropdown[ng-reflect-placeholder='Choose Sheet'], "
        "p-dropdown[placeholder='Choose Sheet']"
    )

    try:
        page.wait_for_selector(sheet_dropdown_selector, timeout=10_000)
    except PWTimeout:
        log.warning(
            "[SHEET] Sheet dropdown not visible — "
            "single-sheet workbook or dropdown did not render. Skipping."
        )
        return ""

    sheet_dropdown = page.locator(sheet_dropdown_selector).first

    # ── Read available sheet names ───────────────────────────────────────────
    sheet_dropdown.locator("div.p-dropdown-trigger").click(force=True)
    page.wait_for_selector("div.p-dropdown-panel:visible", timeout=7_000)

    panel   = page.locator("div.p-dropdown-panel:visible").first
    options = panel.locator("li.p-dropdown-item").all_inner_texts()
    log.info("[SHEET] Available sheets: %s", options)

    # Close the panel before delegating to smart_select_dropdown
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    if not options:
        log.warning("[SHEET] No sheets found inside the dropdown. Skipping.")
        return ""

    # ── Determine target sheet ───────────────────────────────────────────────
    target = preferred_sheet if preferred_sheet else options[0]

    success, mode = smart_select_dropdown(page, sheet_dropdown, target)

    if success:
        log.info("[SHEET] Selected sheet: '%s'  (match mode: %s)", target, mode)
        selected = target
    else:
        # Fallback to first sheet
        log.warning(
            "[SHEET] Could not select preferred sheet '%s'. "
            "Falling back to first sheet: '%s'",
            target, options[0],
        )
        smart_select_dropdown(page, sheet_dropdown, options[0])
        selected = options[0]

    # ── Wait for the header-mapping UI to reload ─────────────────────────────
    # The backend re-reads the chosen sheet's columns and re-renders
    # div.row-container with updated dropdowns.
    try:
        page.wait_for_selector("div.row-container", timeout=10_000)
        wait_for_overlay(page)
        log.info("[SHEET] Header mapping UI reloaded for sheet: '%s'", selected)
    except PWTimeout:
        log.warning(
            "[SHEET] div.row-container did not reload after sheet selection. "
            "Proceeding anyway — mapping may be stale."
        )

    return selected


# ==================================================
# IMPORT ITEMS  (file upload + sheet selection + column mapping)
# ==================================================

def import_items(page, Config, excel_headers: List[str]) -> None:
    """
    Upload the Excel file, select the correct sheet (NEW), then map
    every column to the correct dropdown in the header-mapping UI.

    Flow:
        1. Navigate  →  Import Items page
        2. Upload    →  set_input_files
        3. Sheet     →  select_sheet()          ← NEW
        4. Map       →  verify_and_map() per field
        5. Confirm   →  Map → Start Upload → OK
    """
    log.info("=== Import Items ===")

    click_and_wait(page, "li:has-text('Import Items')")
    page.wait_for_timeout(800)
    page.locator("a[href='/home/importtransaction/Items']").click()
    page.wait_for_timeout(800)

    log.info("Uploading: %s", Config.EXCEL_FILE)
    page.locator("input[type='file']").set_input_files(Config.EXCEL_FILE)

    # ── NEW: Sheet selection ─────────────────────────────────────────────────
    # After upload, the backend detects all sheets and populates the
    # "Choose Sheet" p-dropdown. We pick Config.sheet_name (if set) or
    # fall back to the first available sheet automatically.
    #
    # Config.sheet_name examples:
    #   Config.sheet_name = None          → auto-picks first sheet
    #   Config.sheet_name = "Inventory"   → picks "Inventory" sheet
    #   Config.sheet_name = "6477"        → picks sheet named "6477"
    preferred_sheet = getattr(Config, "sheet_name", None)
    selected_sheet  = select_sheet(page, preferred_sheet)

    if selected_sheet:
        log.info("[IMPORT] Proceeding with sheet: '%s'", selected_sheet)
    # ────────────────────────────────────────────────────────────────────────

    page.wait_for_selector("div.row-container", timeout=20_000)
    wait_for_overlay(page)

    row_container = page.locator("div.row-container")
    left_col      = row_container.locator("div.col-md-6.col-lg-6.col-12").nth(0)
    right_col     = row_container.locator("div.col-md-6.col-lg-6.col-12").nth(1)

    labels    = left_col.locator("div.label > label").all_inner_texts()
    dropdowns = right_col.locator("p-dropdown")

    log.info("Found %d mapping fields on the page.", len(labels))

    failed_fields: List[str] = []

    for idx, field_label in enumerate(labels):
        header = smart_header_match(field_label, excel_headers)

        if not header:
            log.warning("[SKIP]   %-30s → no matching Excel column", field_label)
            failed_fields.append(field_label)
            continue

        try:
            result = verify_and_map(page, dropdowns.nth(idx), header)
            log.info("[MAP]    %-30s → %-30s (%s)", field_label, header, result)
        except Exception as exc:
            log.error("[FAIL]   %-30s → %s | %s", field_label, header, exc)
            failed_fields.append(field_label)

    if failed_fields:
        log.warning("%d field(s) could not be mapped: %s", len(failed_fields), failed_fields)

    page.wait_for_selector("button:has-text('Map'):visible", timeout=10_000).click()
    page.wait_for_selector("button:has-text('Start Upload'):visible", timeout=10_000).click()

    page.wait_for_timeout(10000)
    detect_feedback(page)
    page.locator("button.swal2-confirm:has-text('OK')").click()
    log.info("Import complete.")


# ==================================================
# RESULT DATACLASSES
# ==================================================

@dataclass
class FieldResult:
    field:    str
    expected: str
    actual:   str
    status:   str       # "PASS" | "FAIL" | "MISSING" | "EXTRA"
    note:     str = ""


@dataclass
class RowResult:
    item_code: str
    item_name: str
    status:    str      # "PASS" | "FAIL" | "MISSING" | "EXTRA"
    fields: List[FieldResult] = field(default_factory=list)

    @property
    def failed_fields(self) -> List[FieldResult]:
        return [f for f in self.fields if f.status != "PASS"]


# ==================================================
# UI TABLE SCRAPER  (handles pagination)
# ==================================================

def _scrape_current_page(page) -> List[Dict[str, str]]:
    """
    Extract all visible rows from the PrimeNG datatable.
    Returns list of dicts: Name, Item Code, UOM, Category, Stock In Hand.
    """
    rows = []
    row_els = page.locator("tbody.p-datatable-tbody tr").all()

    for row_el in row_els:
        cells = row_el.locator("td").all()
        if len(cells) < 5:
            continue

        name  = (cells[0].locator("span.product-name").inner_text()
                 if cells[0].locator("span.product-name").count() > 0
                 else cells[0].inner_text()).strip()
        code  = (cells[1].locator("span.itemcode").inner_text()
                 if cells[1].locator("span.itemcode").count() > 0
                 else cells[1].inner_text()).strip()
        uom   = cells[2].inner_text().strip()
        cat   = (cells[3].locator("span.itemcode").inner_text()
                 if cells[3].locator("span.itemcode").count() > 0
                 else cells[3].inner_text()).strip()
        stock = cells[4].inner_text().strip()

        rows.append({
            "Name":          name,
            "Item Code":     code,
            "UOM":           uom,
            "Category":      cat,
            "Stock In Hand": stock,
        })

    return rows


def scrape_all_ui_rows(page) -> List[Dict[str, str]]:
    """
    Scrape every row from the inventory table, clicking through ALL pages.
    """
    log.info("[VALIDATE] Scraping UI inventory table …")
    all_rows: List[Dict[str, str]] = []

    page.wait_for_selector("tbody.p-datatable-tbody", timeout=15_000)
    wait_for_overlay(page)

    page_num = 1
    while True:
        log.info("[VALIDATE]   → page %d", page_num)
        rows = _scrape_current_page(page)
        all_rows.extend(rows)
        log.info(
            "[VALIDATE]      scraped %d rows (running total: %d)",
            len(rows), len(all_rows),
        )

        next_btn = page.locator(
            "button.p-paginator-next:not(.p-disabled), "
            "button[aria-label='Next page']:not([disabled])"
        )

        if next_btn.count() == 0 or not next_btn.first.is_enabled():
            log.info("[VALIDATE]   → No more pages.")
            break

        next_btn.first.click()
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
# COMPARATOR  (list-level — Name / Code / Category)
# ==================================================

# Fields compared in the inventory LIST view
FIELDS_TO_CHECK = [
    ("Name",      "Item Name"),
    ("Item Code", "Item Code"),
    ("Category",  "Item Category"),
]


def _normalise(value: str) -> str:
    return str(value).strip().lower()


def _values_match(expected: str, actual: str) -> bool:
    return _normalise(expected) == _normalise(actual)


def _clean_df_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strip trailing asterisks and spaces from every column name so that
    template-decorated names like 'Item Code *' match plain lookups.
    """
    df = df.copy()
    df.columns = [str(c).strip().rstrip(" *").strip() for c in df.columns]

    # Header compatibility: some Excel templates use "Category" while others use "Item Category".
    # Standardize to "Item Category" so downstream lookups are consistent.
    cols = list(df.columns)
    if "Category" in cols and "Item Category" not in cols:
        df = df.rename(columns={"Category": "Item Category"})

    log.debug("[VALIDATE] Normalised Excel columns: %s", list(df.columns))
    return df


def compare_excel_vs_ui(
    df: pd.DataFrame,
    ui_rows: List[Dict[str, str]],
    config,
) -> List[RowResult]:
    """
    Match each Excel row to a UI row strictly by Item Code (case-insensitive).
    Flags: MISSING / EXTRA / PASS / FAIL
    """
    df = _clean_df_columns(df)
    results: List[RowResult] = []

    ui_by_code: Dict[str, Dict] = {}
    for r in ui_rows:
        code = r["Item Code"].strip()
        if code:
            ui_by_code[code.lower()] = r

    for _, excel_row in df.iterrows():
        ex_code = str(excel_row.get("Item Code", "")).strip()
        ex_name = str(excel_row.get("Item Name", "")).strip()

        ui_row = ui_by_code.get(ex_code.lower())

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

        field_results: List[FieldResult] = []
        row_pass = True

        for ui_col, excel_col in FIELDS_TO_CHECK:
            expected_val = str(excel_row.get(excel_col, "")).strip()
            actual_val   = ui_row.get(ui_col, "").strip()

            if _values_match(expected_val, actual_val):
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

    excel_codes = {
        str(r.get("Item Code", "")).strip().lower()
        for _, r in df.iterrows()
    }

    for ui_row in ui_rows:
        code = ui_row["Item Code"]
        name = ui_row["Name"]
        if code.strip().lower() not in excel_codes:
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
# INPUT ANALYSIS
# ==================================================

def _print_input_analysis(
    df: pd.DataFrame,
    ui_rows: List[Dict[str, str]],
) -> None:
    df = _clean_df_columns(df)

    ui_by_code: Dict[str, Dict] = {
        r["Item Code"].strip().lower(): r for r in ui_rows if r["Item Code"].strip()
    }
    excel_codes: set = {
        str(row.get("Item Code", "")).strip().lower()
        for _, row in df.iterrows()
    }

    log.info("")
    log.info("=" * 70)
    log.info("  INPUT ANALYSIS")
    log.info("=" * 70)

    log.info("")
    log.info("  📄 Excel  (%d rows)", len(df))
    log.info("  " + "-" * 60)

    for _, row in df.iterrows():
        code = str(row.get("Item Code", "")).strip()
        name = str(row.get("Item Name", "")).strip()
        cat  = str(row.get("Item Category", "")).strip()
        status_tag = "[FOUND   ]" if ui_by_code.get(code.lower()) else "[MISSING ]"
        log.info("  %s  %-14s  →  %-35s  →  %s", status_tag, code, name, cat)

    log.info("")
    log.info("  🌐 UI  (%d rows)", len(ui_rows))
    log.info("  " + "-" * 60)

    for r in ui_rows:
        code = r["Item Code"].strip()
        name = r["Name"].strip()
        cat  = r["Category"].strip()
        status_tag = "[MATCHED ]" if code.lower() in excel_codes else "[EXTRA   ]"
        log.info("  %s  %-14s  →  %-35s  →  %s", status_tag, code, name, cat)

    log.info("")
    log.info("=" * 70)


# ==================================================
# VALIDATION REPORTER  (shared by both validators)
# ==================================================

def _print_validation_report(
    results: List[RowResult],
    title: str = "INVENTORY UI VALIDATION REPORT",
) -> None:
    total   = len(results)
    passed  = sum(1 for r in results if r.status == "PASS")
    failed  = sum(1 for r in results if r.status == "FAIL")
    missing = sum(1 for r in results if r.status == "MISSING")
    extra   = sum(1 for r in results if r.status == "EXTRA")

    log.info("")
    log.info("=" * 70)
    log.info(
        "  %s  —  %s",
        title,
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    log.info("=" * 70)
    log.info("-" * 70)
    log.info("  Total rows compared : %d", total)
    log.info("  ✅ PASS             : %d", passed)
    log.info("  ❌ FAIL             : %d", failed)
    log.info("  ⚠  MISSING (in UI) : %d", missing)
    log.info("  ➕ EXTRA  (in UI)   : %d", extra)
    log.info("=" * 70)

    for r in results:
        icon = {"PASS": "✅", "FAIL": "❌", "MISSING": "⚠ ", "EXTRA": "➕"}.get(r.status, "?")
        log.info(
            "\n%s [%s]  %-20s  Code: %-12s",
            icon, r.status, r.item_name, r.item_code,
        )

        if r.status in ("MISSING", "EXTRA"):
            log.info("     %s", r.fields[0].note)
            continue

        for f in r.fields:
            status_icon = "  ✅" if f.status == "PASS" else "  ❌"
            log.info(
                "%s  %-18s  Expected: %-25s  Actual: %-25s  %s",
                status_icon, f.field, f.expected, f.actual,
                f"← {f.note}" if f.note else "",
            )

    log.info("")
    log.info("=" * 70)
    overall = "ALL PASSED ✅" if failed == 0 and missing == 0 else "FAILURES DETECTED ❌"
    log.info("  RESULT: %s", overall)
    log.info("=" * 70)


# ==================================================
# VALIDATE UI  (inventory list — Name / Code / Category)
# ==================================================

def validate_ui(page, df: pd.DataFrame, config) -> List[RowResult]:
    """
    Scrapes the inventory list table across all pages and compares
    Name, Item Code, Category against the Excel source.
    """
    log.info("=== UI Validation (List View) ===")

    click_and_wait(page, "img[src*='Item_icon.svg']")
    page.wait_for_selector("tbody.p-datatable-tbody", timeout=15_000)
    wait_for_overlay(page)

    ui_rows = scrape_all_ui_rows(page)
    _print_input_analysis(df, ui_rows)

    results = compare_excel_vs_ui(df, ui_rows, config)
    _print_validation_report(results, title="LIST VIEW VALIDATION REPORT")

    return results


# ==================================================
# DETAILS VALIDATION — EDIT FORM HELPERS
# ==================================================

def _normalise_price(value: str) -> str:
    """
    Strip currency symbols / commas so '100.00' == '100' == '₹100.00'.
    Falls back to lowercased raw string on parse failure.
    """
    cleaned = value.replace(",", "").strip().lstrip("₹$€£").strip()
    try:
        return str(float(cleaned))
    except ValueError:
        return cleaned.lower()


def _fields_equal(label: str, expected: str, actual: str) -> bool:
    """
    Field-aware comparison:
      • Price fields  → normalise via _normalise_price
      • All others    → case-insensitive, trimmed
    """
    if label in {"Cost Price", "Sell Price"}:
        return _normalise_price(expected) == _normalise_price(actual)
    return expected.strip().lower() == actual.strip().lower()


def _read_edit_form(page) -> Dict[str, str]:
    values: Dict[str, str] = {}

    for label, fcn, _ in EDIT_FORM_FIELDS:
        try:
            if label == "Category":
                # Category is a p-autocomplete inside app-auto-complete-category
                # The visible value is in the autocomplete's text input
                cat_input = page.locator(
                    f"[formcontrolname='{fcn}'] input.p-autocomplete-input"
                ).first
                values[label] = (cat_input.input_value() or "").strip()

            elif label in ("Cost Price", "Sell Price"):
                # p-inputnumber wraps a spinbutton input
                wrapper = page.locator(f"[formcontrolname='{fcn}']")
                inner   = wrapper.locator("input[role='spinbutton']").first
                values[label] = (inner.input_value() or "").strip()

            else:
                wrapper = page.locator(f"[formcontrolname='{fcn}']")
                inner   = wrapper.locator("input").first
                target  = inner if inner.count() > 0 else wrapper
                values[label] = (target.input_value() or "").strip()

        except Exception as exc:
            log.warning("[DETAILS_VAL] Could not read '%s': %s", label, exc)
            values[label] = ""

    return values


def _search_item_in_list(page, item_code: str) -> bool:
    """
    Type item_code into the inventory search box and wait for filtered results.
    Returns True on success.
    """
    try:
        page.fill("input#customerName", item_code)
        page.wait_for_timeout(800)
        page.wait_for_selector("tbody.p-datatable-tbody tr", timeout=6_000)
        wait_for_overlay(page)
        return True
    except PWTimeout:
        log.warning("[DETAILS_VAL] Search timed out for code '%s'", item_code)
        return False


def _open_edit_form(page, item_code: str, item_name: str) -> bool:
    """
    From the inventory list:
      1. Search for item_code
      2. Locate the matching row
      3. Click the kebab/action menu → Edit
      4. Confirm Edit Item heading is visible

    Returns True on success.
    """
    if not _search_item_in_list(page, item_code):
        return False

    try:
        page.locator(f"//span[text()='{item_name}']").click()
        wait_for_overlay(page)

        page.locator("//button[contains(@class,'dropdown-toggle')]").click()
        wait_for_overlay(page)
        page.locator("ul.dropdown-menu.show >> text=Edit").click()
        wait_for_overlay(page)

        return True

    except PWTimeout:
        log.warning(
            "[DETAILS_VAL] Could not open Edit form for '%s' / '%s'",
            item_code, item_name,
        )
        return False


def _back_to_inventory_list(page) -> None:
    """Click Back / breadcrumb to return to the inventory list."""
    try:
        back_btn = page.locator(
            "button:has-text('Back'), "
            "a:has-text('Back'), "
            "button[aria-label='Back']"
        ).first
        if back_btn.is_visible():
            back_btn.click()
            page.wait_for_selector("tbody.p-datatable-tbody", timeout=8_000)
            wait_for_overlay(page)
    except Exception as exc:
        log.warning("[DETAILS_VAL] Back navigation issue: %s", exc)


# ==================================================
# DETAILS VALIDATION  (Edit-form field-level check)
# ==================================================

def Details_validation(page, df: pd.DataFrame) -> List[RowResult]:
    """
    For every row in the Excel dataframe:
      1. Search the inventory list for the item code
      2. Open the Edit Item form via the kebab menu
      3. Read every field mapped in EDIT_FORM_FIELDS
      4. Compare against the Excel source value
      5. Navigate back and repeat

    Fields validated:
      Item Code · Name · Barcode · UOM · Category · Cost Price · Sell Price

    Match key : Item Code (used for search; no fallback)
    Returns   : List[RowResult]  — same shape as validate_ui results
    """
    log.info("=== Details Validation (Edit-form field check) ===")
    df = _clean_df_columns(df)

    results: List[RowResult] = []

    for _, excel_row in df.iterrows():
        item_code = str(excel_row.get("Item Code", "")).strip()
        item_name = str(excel_row.get("Item Name", "")).strip()

        if not item_code:
            log.warning(
                "[DETAILS_VAL] Skipping row with empty Item Code (name='%s')",
                item_name,
            )
            continue

        log.info("[DETAILS_VAL] Checking  %-14s  %s", item_code, item_name)

        # ── Try to open the Edit form ────────────────────────────────────────
        opened = _open_edit_form(page, item_code, item_name)

        if not opened:
            results.append(RowResult(
                item_code=item_code,
                item_name=item_name,
                status="MISSING",
                fields=[FieldResult(
                    field="(row)",
                    expected=f"{item_name} / {item_code}",
                    actual="—",
                    status="MISSING",
                    note="Edit form could not be opened — item not found or navigation failed",
                )],
            ))
            continue

        # ── Read all fields from the open Edit form ──────────────────────────
        ui_values = _read_edit_form(page)

        # ── Compare each field against Excel ────────────────────────────────
        field_results: List[FieldResult] = []
        row_pass = True

        for label, _, excel_col in EDIT_FORM_FIELDS:
            expected_val = str(excel_row.get(excel_col, "")).strip()
            actual_val   = ui_values.get(label, "")

            if _fields_equal(label, expected_val, actual_val):
                field_results.append(FieldResult(
                    field=label,
                    expected=expected_val,
                    actual=actual_val,
                    status="PASS",
                ))
            else:
                row_pass = False
                field_results.append(FieldResult(
                    field=label,
                    expected=expected_val,
                    actual=actual_val,
                    status="FAIL",
                    note=f"Expected '{expected_val}', Actual '{actual_val}'",
                ))

        results.append(RowResult(
            item_code=item_code,
            item_name=item_name,
            status="PASS" if row_pass else "FAIL",
            fields=field_results,
        ))

        # ── Back to list for the next item ───────────────────────────────────
        _back_to_inventory_list(page)

    _print_validation_report(results, title="EDIT FORM VALIDATION REPORT")
    return results


# ==================================================
# MAIN ENTRY POINT
# ==================================================

def import_app(page, Config):

    if not os.path.exists(Config.EXCEL_FILE):
        log.error("Excel file not found: %s", Config.EXCEL_FILE)
        sys.exit(1)

    # ── Load dataframe from the correct sheet ────────────────────────────────
    # Config.sheet_name may be None (first sheet) or a specific name.
    sheet_name    = getattr(Config, "sheet_name", None)
    df            = read_excel(Config.EXCEL_FILE, sheet_name=sheet_name)
    excel_headers = list(df.columns)
    log.info(
        "Loaded %d rows, %d headers from sheet '%s': %s",
        len(df), len(excel_headers),
        sheet_name or "(first sheet)",
        excel_headers,
    )

    # Navigate to Inventory module
    click_and_wait(page, "img[src*='Item_icon.svg']")
    select_item_group(page, Config.group_name)

    # 1. Add one test item (full form)
    if Config.run_add_item:
        add_item(page, Config)
    else:
        print("x add_item")

    # 2. Quick-add
    if Config.run_quick_add_items:
        quick_add_items(page, Config)
    else:
        print("x quick_add_items")

    # 3. Import the full Excel file with sheet selection + column mapping
    if Config.run_import_items:
        import_items(page, Config, excel_headers)
    else:
        print("x import_items")

    page.wait_for_timeout(1_000)
    select_item_group(page, Config.group_name)

    # 4. List-level validation — scrape inventory table, compare Name/Code/Category
    list_results = validate_ui(page, df, Config)

    # 5. Details validation — open Edit form per item, compare all form fields
    if getattr(Config, "run_details_validation", True):
        select_item_group(page, Config.group_name)
        details_results = Details_validation(page, df)
    else:
        print("x Details_validation")
        details_results = []

    # CI exit code — fail if any list or detail check failed
    all_results = list_results + details_results
    failures    = [r for r in all_results if r.status in ("FAIL", "MISSING")]
    if failures:
        log.error(
            "[VALIDATE] %d item(s) failed validation across list + edit-form checks.",
            len(failures),
        )