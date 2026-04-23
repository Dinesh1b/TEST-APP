from asyncio import timeout
import time
import os
import sys
from typing import List, Tuple
import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from login.popup_handler import detect_feedback
from login.logger_setup import mirrored_print


# ======================================================
# UTILITY FUNCTIONS
# ======================================================
def normalize(text: str) -> str:
    """Remove commas and extra spaces"""
    return text.replace(",", "").strip()


# --------------------------------------------------------------
# ENABLE CONTINUOUS COUNT
# --------------------------------------------------------------
def enable_continuous_count(page) -> None:
    toggle = page.locator("p-inputswitch")
    if toggle.get_attribute("aria-checked") != "true":
        toggle.click()
        page.wait_for_timeout(300)
        print("✅ Continuous Count ENABLED")


def A_SA(page, Config):

    # ----------------------
    # Helpers for binding inputs
    # ----------------------
    def human_type_input(page, selector: str, text: str, delay_seconds: float = 0.03) -> None:
        el = page.locator(selector).first
        el.wait_for(state="visible", timeout=7000)
        el.focus()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.type(str(text), delay=int(delay_seconds * 1000))
        el.evaluate("el => el.blur()")
        page.wait_for_timeout(0.08)

    def js_set_number_with_events(page, selector: str, value: str) -> None:
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

    # --------------------------------------------------------------
    # SELECT LOCATION - PrimeNG TreeSelect (Dialog scope)
    # --------------------------------------------------------------
    def select_location_tree(page, value: str, timeout: int = 5000, retry: int = 2):
        if not value:
            print("⚠️ Empty location value, skipping...")
            return

        for attempt in range(retry + 1):
            try:
                dialog = page.get_by_role("dialog")
                dialog.wait_for(state="visible", timeout=timeout)

                treeselect = dialog.locator("p-treeselect").first
                treeselect.wait_for(state="visible", timeout=timeout)
                treeselect.click()

                panel = page.locator(".p-treeselect-panel").last
                panel.wait_for(state="visible", timeout=timeout)
                time.sleep(0.3)

                search = panel.locator("input.location-search-input")
                if search.count() > 0:
                    search.fill("")
                    search.fill(value)
                    time.sleep(0.5)

                parts = value.split("-")

                for i, part in enumerate(parts):
                    node = panel.locator(".p-treenode-content", has_text=part).first
                    node.wait_for(state="visible", timeout=timeout)

                    if i < len(parts) - 1:
                        toggler = node.locator(".p-tree-toggler")
                        if toggler.count() > 0:
                            try:
                                toggler.click()
                            except:
                                node.click()
                        time.sleep(0.3)
                    else:
                        checkbox = node.locator(".p-checkbox")
                        if checkbox.count() > 0:
                            checkbox.click()
                        else:
                            node.click()

                panel.wait_for(state="hidden", timeout=timeout)
                print(f"✅ Location selected: {value}")
                return

            except TimeoutError:
                print(f"⏳ Attempt {attempt+1}: Timeout, retrying...")
            except Exception as e:
                print(f"⚠️ Attempt {attempt+1} failed: {e}")

            try:
                page.keyboard.press("Escape")
            except:
                pass
            time.sleep(1)

        raise Exception(f"❌ Failed to select location after retries: {value}")

    # --------------------------------------------------------------
    # SELECT LOCATION — INLINE CONTINUOUS COUNT ROW
    # --------------------------------------------------------------
    def select_location_inline(page, value: str, timeout: int = 7000):
        if not value:
            return

        try:
            treeselect = page.locator("app-location-tree-select p-treeselect").first
            treeselect.wait_for(state="visible", timeout=timeout)

            trigger = treeselect.locator(".p-treeselect-trigger")
            trigger.click()

            panel = page.locator("div.p-treeselect-panel").last
            panel.wait_for(state="visible", timeout=timeout)
            time.sleep(0.5)

            search = panel.locator("input.location-search-input")
            if search.count() > 0:
                search.fill(value)
                time.sleep(1)

            final_node = panel.locator(
                ".p-treenode-content:has(.node-label:text-is('{}'))".format(value.split("-")[-1])
            ).first

            if final_node.count() == 0:
                raise Exception(f"❌ Node not found: {value}")

            checkbox = final_node.locator(".p-checkbox")
            if checkbox.count() > 0:
                checkbox.click()
            else:
                final_node.click()

            page.keyboard.press("Escape")
            print(f"✅ Location selected: {value}")

        except PlaywrightTimeoutError:
            raise Exception("❌ Timeout while selecting location (inline treeselect)")
        except Exception as e:
            raise Exception(f"❌ select_location_inline failed: {e}")

    # --------------------------------------------------------------
    # CLICK ADD ITEM BUTTON
    # --------------------------------------------------------------
    def click_add_item_button(page, timeout: int = 7000) -> None:
        try:
            page.click("button.button.primary-button.me-3:has-text('Add Item')", timeout=timeout)
        except Exception:
            page.click("button:has-text('Add Item')", timeout=timeout)

        page.wait_for_selector("div.p-dialog-mask", timeout=8000)
        page.wait_for_selector("div.p-dialog", timeout=8000)
        page.wait_for_selector("div.p-dialog-content div.dialog-content", timeout=8000)
        page.wait_for_timeout(200)

    # --------------------------------------------------------------
    # FILL ITEM DETAILS — BOUND (dialog form fields)
    # --------------------------------------------------------------
    def fill_item_details_bound(
        page,
        ITEM_CODE1: str,
        ITEM_NAME1: str = "",
        CATEGORY1: str = "",
        COST_PRICE1: str = "",
        SELL_PRICE1: str = "",
        LOCATION1: str = "",
        BARCODE1: str = "",
        UOM1: str = "",
    ):
        page.wait_for_selector("div.p-dialog-mask", timeout=9000)
        page.wait_for_selector("div.p-dialog", timeout=9000)
        page.wait_for_selector("div.p-dialog-content div.dialog-content", timeout=9000)

        dialog = page.locator("div.p-dialog-content div.dialog-content")

        if CATEGORY1:
            dialog.locator("p-dropdown[formcontrolname='itemCategoryId']").click()
            page.wait_for_selector("div.p-dropdown-panel li.p-dropdown-item")
            page.locator(f"div.p-dropdown-panel li:has-text('{CATEGORY1}')").click()

        dialog.locator("input[formcontrolname='itemCode']").fill(ITEM_CODE1)
        page.wait_for_timeout(500)

        if ITEM_NAME1:
            dialog.locator("input[formcontrolname='itemName']").fill(ITEM_NAME1)
            page.wait_for_timeout(500)

        if COST_PRICE1:
            dialog.locator("input[formcontrolname='costPrice']").fill(COST_PRICE1)
            page.wait_for_timeout(500)

        if SELL_PRICE1:
            dialog.locator("input[formcontrolname='sellPrice']").fill(SELL_PRICE1)
            page.wait_for_timeout(500)

        if LOCATION1:
            select_location_tree(page, LOCATION1)

        if BARCODE1:
            dialog.locator("input[formcontrolname='eanQr']").fill(BARCODE1)
            page.wait_for_timeout(500)

        if UOM1:
            dialog.locator("input[formcontrolname='uom']").fill(UOM1)
            page.wait_for_timeout(500)

        dialog.locator("button[type='submit']").click()
        page.wait_for_timeout(500)

    # --------------------------------------------------------------
    # FILL ITEM DETAILS — UNBOUND (inline row after dialog closes)
    # --------------------------------------------------------------
    def fill_item_details_unbound(
        page,
        LOCATION1: str,
        ITEM_CODE1: str,
        audited_qty1: float,
        damaged_qty1: float
    ):
        save_sel = "div.p-dialog-content div.dialog-content button.button.primary-button:has-text('Save')"
        page.wait_for_selector(save_sel, timeout=6000)
        page.locator(save_sel).first.click()

        page.wait_for_selector("div.p-dialog-mask", state="detached", timeout=8000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(200)

        ac = page.locator("input.p-autocomplete-input[placeholder*='Item Code']").first
        ac.scroll_into_view_if_needed()
        ac.click()
        ac.fill("")
        ac.type(ITEM_CODE1, delay=50)

        try:
            page.wait_for_selector("li.p-autocomplete-item:visible", timeout=5000)
            page.locator("li.p-autocomplete-item").first.click()
        except PlaywrightTimeoutError:
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")

        page.wait_for_timeout(300)

        select_location_tree(page, LOCATION1)
        page.wait_for_timeout(200)

        page.fill('input[formcontrolname="auditedQty"]', str(audited_qty1))
        page.fill('input[formcontrolname="damagedQty"]', str(damaged_qty1))

        page.click("button:has-text('Add Count')")
        page.wait_for_timeout(300)

    # --------------------------------------------------------------
    # ADD ITEM COUNT (INLINE — CONTINUOUS COUNT MODE)
    # --------------------------------------------------------------
    def add_item_count(
        page,
        item_query: str,
        audited_qty: int,
        damaged_qty: int,
        location: str,
    ) -> bool:
        ac = page.locator("input.p-autocomplete-input[placeholder*='Item Code']").first
        ac.scroll_into_view_if_needed()
        ac.click()
        ac.fill("")
        ac.type(item_query, delay=50)

        try:
            page.wait_for_selector("li.p-autocomplete-item:visible", timeout=5000)
            page.locator("li.p-autocomplete-item").first.click()
        except PlaywrightTimeoutError:
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")

        page.wait_for_timeout(300)

        select_location_inline(page, location)
        page.wait_for_timeout(200)

        page.fill('input[formcontrolname="auditedQty"]', str(audited_qty))
        page.fill('input[formcontrolname="damagedQty"]', str(damaged_qty))

        page.click("button:has-text('Add Count')")
        page.wait_for_timeout(300)

        return True

    # --------------------------------------------------------------
    # NEW ADD ITEM (optional pre-audit item creation)
    # --------------------------------------------------------------
    def new_add_item(page):
        click_add_item_button(page)

        fill_item_details_bound(
            page,
            Config.ITEM_CODE1,
            Config.ITEM_NAME1,
            Config.CATEGORY1,
            Config.COST_PRICE1,
            Config.SELL_PRICE1,
            Config.LOCATION1,
            Config.BARCODE1,
            Config.UOM1,
        )

        fill_item_details_unbound(
            page,
            Config.LOCATION1,
            Config.ITEM_CODE1,
            Config.audited_qty1,
            Config.damaged_qty1,
        )

    # --------------------------------------------------------------
    # EXCEL LOADER
    # Now reads from Config.asa_* fields (moved from Ongoing Audit).
    # Config keys used:
    #   oa_excel_path    — file path (shared with Ongoing Audit)
    #   asa_sheet        — sheet name        (was oa_sheet)
    #   asa_loc_col      — location column   (was oa_loc_col)
    #   asa_code_col     — code column       (was oa_code_col)
    #   asa_aud_col      — audited column    (was oa_aud_col)
    #   asa_dam_col      — damaged column    (was oa_dam_col)
    # --------------------------------------------------------------
    def load_items_from_excel() -> List[Tuple[str, str, float, float]]:
        path        = Config.oa_excel_path
        sheet_name  = Config.EXCEL_SHEET_auditor_1
        location_col = Config.EXCEL_LOCATION_COL1
        code_col     = Config.EXCEL_CODE_COL1
        audited_col  = Config.EXCEL_AUDITED_COL1
        damaged_col  = Config.EXCEL_DAMAGED_COL1

        if not os.path.exists(path):
            print(f"❌ Excel file not found: {path}")
            sys.exit(1)

        df = pd.read_excel(path, sheet_name=sheet_name)

        for col in (location_col, code_col):
            if col not in df.columns:
                print(f"❌ Missing column in Excel: '{col}'  (found: {list(df.columns)})")
                sys.exit(1)

        items: List[Tuple[str, str, float, float]] = []

        for _, row in df.iterrows():
            location = str(row.get(location_col, "")).strip()
            code     = str(row.get(code_col,     "")).strip()

            if not location or not code or location == "nan" or code == "nan":
                continue

            audited_val = pd.to_numeric(row.get(audited_col), errors="coerce")
            audited     = float(audited_val) if not pd.isna(audited_val) else 0

            damaged_val = pd.to_numeric(row.get(damaged_col), errors="coerce")
            damaged     = float(damaged_val) if not pd.isna(damaged_val) else 0

            items.append((location, code, audited, damaged))

        if not items:
            print("⚠ No valid rows found in Excel — check column names and data.")

        return items

    # --------------------------------------------------------------
    # SELECT BRANCH
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
    # NAVIGATE TO ONGOING AUDITS
    # Uses Config.asa_email / asa_password for auditor login,
    # and Config.ap_audit_name to find the correct audit row.
    # --------------------------------------------------------------
    def navigate_to_ongoing_audits(page, Config):
        print("📂 Navigating to Ongoing Audits...")
        print(f"👤 Auditor: {Config.email}")

        page.wait_for_timeout(500)
        page.wait_for_selector("a[href='/home/audit']", state="visible")
        page.click("a[href='/home/audit']")
        print("✅ Clicked on 'Audits' in sidebar")
        page.wait_for_load_state("networkidle")

        select_branch(page, Config.Branch)
        print(f"✅ Branch selected: {Config.Branch}")

        # Find and click the specific audit using ap_audit_name
        row = page.locator(
            f"table tbody tr:has(td span:has-text('{Config.ap_audit_name}'))"
        ).first
        row.locator("td span").first.click()
        print(f"✅ Opened audit: {Config.ap_audit_name}")

        page.locator("button.button.primary-button:has-text('Stock Audit')").click()

        # Optional: add new item before bulk Excel import
        if Config.run_new_add_item:
            new_add_item(page)
        else:
            print("❌ New add item skipped")

        print(f"Processed {Config.ITEM_CODE1} ({Config.audited_qty1}/{Config.damaged_qty1}/{Config.LOCATION1})")
        detect_feedback(page)
        page.wait_for_timeout(500)

        # ============================================
        # Load items from Excel (asa_* config)
        # ============================================
        print("\n" + "-" * 70)
        print("🔷 ADDING ITEMS FROM EXCEL (Inline Form)")
        print(f"   Sheet   : {Config.EXCEL_SHEET_auditor_1}")
        print(f"   Loc col : {Config.EXCEL_LOCATION_COL1}")
        print(f"   Code col: {Config.EXCEL_CODE_COL1}")
        print(f"   Aud col : {Config.EXCEL_AUDITED_COL1}")
        print(f"   Dam col : {Config.EXCEL_DAMAGED_COL1}")
        print("-" * 70)

        items_to_add = load_items_from_excel()

        # ── Bulk loop ──────────────────────────────────────────────
        success_count = 0
        fail_count    = 0

        for idx, (location, code, audited, damaged) in enumerate(items_to_add, start=1):
            print(f"\n[{idx}/{len(items_to_add)}] ➡️  {code} | A:{audited}  D:{damaged} | {location}")
            success = add_item_count(page, code, audited, damaged, location)

            if success:
                print(f"✅ [{idx}/{len(items_to_add)}] {code} "
                      f"(Audited: {audited}, Damaged: {damaged})")
                detect_feedback(page)
                success_count += 1
            else:
                print(f"❌ [{idx}/{len(items_to_add)}] Failed: {code}")
                fail_count += 1

            page.wait_for_timeout(Config.WAIT_AFTER_ACTION)

        print(f"\n📊 Summary: {success_count} succeeded, {fail_count} failed")

    # --------------------------------------------------------------
    # ENTRY POINT
    # --------------------------------------------------------------
    navigate_to_ongoing_audits(page, Config)