from asyncio import timeout
import time
import os
import sys
from typing import List, Tuple
import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, Page, sync_playwright


from backend.shared.popup_handler import detect_feedback
from backend.shared.logger_setup import mirrored_print


        # ======================================================
        # UTILITY FUNCTIONS
        # ======================================================
def normalize(text: str) -> str:
            """Remove commas and extra spaces"""
            return text.replace(",", "").strip()
        # --------------------------------------------------------------
        # ENABLE CONTINUOUS COUNT
        # --------------------------------------------------------------
def enable_continuous_count(page: Page) -> None:
                toggle = page.locator("p-inputswitch")
                if toggle.get_attribute("aria-checked") != "true":
                    toggle.click()
                    page.wait_for_timeout(300)
                    print("✅ Continuous Count ENABLED")


def Q_SA(Page, Config):
    # Normalize parameter naming: the rest of this module expects `page`
    # to be the Playwright Page instance.
    page = Page
    # ----------------------
    # Helpers for binding inputs
    # ----------------------
    def human_type_input(page, selector: str, text: str, delay_seconds: float = 0.03) -> None:
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



    def js_set_number_with_events(page, selector: str, value: str) -> None:
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
            Page.wait_for_timeout(0.06)

    # --------------------------------------------------------------
    # SELECT LOCATION - PrimeNG p-dropdown (Single Select)
    # --------------------------------------------------------------

    def select_location(page, value: str, timeout: int = 5000):
            """
            Selects a value from PrimeNG p-dropdown inside p-dialog.
            Handles strict mode, overlay panel, and optional filter.
            """

            if not value:
                return

            try:
                # --------------------------------------------------
                # 1️⃣ Scope inside dialog (STRICT MODE SAFE)
                # --------------------------------------------------
                dialog = page.get_by_role("dialog")
                dialog.wait_for(state="visible", timeout=timeout)

                dropdown = dialog.locator("p-dropdown#role").first
                dropdown.wait_for(state="visible", timeout=timeout)

                # --------------------------------------------------
                # 2️⃣ Open dropdown
                # --------------------------------------------------
                dropdown.locator(".p-dropdown-trigger").click()

                # --------------------------------------------------
                # 3️⃣ Overlay panel (appendTo='body')
                # --------------------------------------------------
                panel = page.locator("div.p-dropdown-panel").last
                panel.wait_for(state="visible", timeout=timeout)

                # --------------------------------------------------
                # 4️⃣ Filter (if enabled)
                # --------------------------------------------------
                search = panel.locator("input.p-dropdown-filter")
                if search.count() > 0:
                    search.fill("")
                    search.fill(value)

                # --------------------------------------------------
                # 5️⃣ Select option
                # --------------------------------------------------
                option = panel.locator(
                    "li.p-dropdown-item",
                    has_text=value
                )

                if option.count() == 0:
                    raise Exception(f"❌ Location not found: {value}")

                option.first.click()

                # --------------------------------------------------
                # 6️⃣ Wait for dropdown to close
                # --------------------------------------------------
                panel.wait_for(state="hidden", timeout=timeout)

                print(f"✅ Location selected: {value}")

            except TimeoutError:
                raise Exception("❌ Timeout while selecting location")

            except Exception as e:
                raise Exception(f"❌ select_location failed: {e}")

    def click_add_item_button(page, timeout: int = 7000) -> None:
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



    def fill_item_details_bound(page, item_code: str, audited_qty: int, damaged_qty: int, location: str):

            """
            Bind/fill modal fields so Angular/PrimeNG picks up values reliably.
            """

            # --------------------------------------------------
            # Dialog wait
            # --------------------------------------------------
            page.wait_for_selector("div.p-dialog-mask", timeout=9000)
            page.wait_for_selector("div.p-dialog", timeout=9000)
            page.wait_for_selector("div.p-dialog-content div.dialog-content", timeout=9000)
            page.wait_for_timeout(120)

            # --------------------------------------------------
            # Item Code
            # --------------------------------------------------
            item_sel = "input[formcontrolname='itemCode']"
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

            # --------------------------------------------------
            # Damaged Qty (optional)
            # --------------------------------------------------
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
                    # damagedQty not present — ignore
                    pass

            # --------------------------------------------------
            # Location (PrimeNG dropdown)
            # --------------------------------------------------
            if location:
                select_location(page, location)




            
            # Click Save (button inside dialog)
            save_sel = "div.p-dialog-content div.dialog-content button.button.primary-button:has-text('Save')"
            page.wait_for_selector(save_sel, timeout=6000)
            page.locator(save_sel).first.click()

            # Wait for dialog to close (mask detached) and network settle
            page.wait_for_selector("div.p-dialog-mask", state="detached", timeout=8000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(200)


        # --------------------------------------------------------------
        # SELECT LOCATION — shared panel-click logic
        # --------------------------------------------------------------
    def _open_dropdown_and_pick(page, dropdown, value: str, timeout: int) -> None:
            """
            Open a PrimeNG p-dropdown (already located) and click the matching option.
            Works whether the dropdown is inside a dialog or an inline row.
            """
            dropdown.locator(".p-dropdown-trigger").click()

            panel = page.locator("div.p-dropdown-panel").last
            panel.wait_for(state="visible", timeout=timeout)

            # Optional filter input
            search = panel.locator("input.p-dropdown-filter")
            if search.count() > 0:
                search.fill("")
                search.fill(value)
                page.wait_for_timeout(300)          # let filter re-render

            option = panel.locator("li.p-dropdown-item", has_text=value)
            if option.count() == 0:
                raise Exception(f"Location not found in dropdown: '{value}'")

            option.first.click()
            panel.wait_for(state="hidden", timeout=timeout)
            print(f"✅ Location selected: {value}")


        # --------------------------------------------------------------
        # SELECT LOCATION — MODAL DIALOG (fill_item_details_bound)
        # --------------------------------------------------------------
    def select_location(page, value: str, timeout: int = 5_000) -> None:
            """
            Select a location from a PrimeNG p-dropdown INSIDE the active p-dialog.
            Tries formcontrolname='location', 'locationId', 'locationCode', then falls
            back to the first visible p-dropdown found in the dialog.
            """
            if not value:
                        return

            try:
                    dialog = page.get_by_role("dialog")
                    dialog.wait_for(state="visible", timeout=timeout)

                    dropdown = None
                    for candidate in [
                        dialog.locator("p-dropdown[formcontrolname='location']"),
                        dialog.locator("p-dropdown[formcontrolname='locationId']"),
                        dialog.locator("p-dropdown[formcontrolname='locationCode']"),
                        dialog.locator("p-dropdown"),           # last-resort fallback
                    ]:
                        try:
                            if candidate.count() > 0 and candidate.first.is_visible(timeout=500):
                                dropdown = candidate.first
                                break
                        except Exception:
                            continue

                    if dropdown is None:
                        raise Exception("Could not find a location dropdown inside the dialog")

                    _open_dropdown_and_pick(page, dropdown, value, timeout)

            except PlaywrightTimeoutError:
                    raise Exception("❌ Timeout while selecting location (modal)")
            except Exception as e:
                    raise Exception(f"❌ select_location (modal) failed: {e}")


        # --------------------------------------------------------------
        # SELECT LOCATION — INLINE CONTINUOUS COUNT ROW
        # --------------------------------------------------------------
    def select_location_inline(page, value: str, timeout: int = 5000) -> None:
            if not value:
                return
            try:
                    dropdown = None

                    # 1️⃣ id="role" is the actual DOM id from the app HTML — try it first
                    try:
                        candidate = page.locator("p-dropdown#role").first
                        if candidate.count() > 0 and candidate.is_visible(timeout=500):
                            dropdown = candidate
                    except Exception:
                        pass

                    # 2️⃣ formcontrolname candidates (outside any dialog)
                    if dropdown is None:
                        for fcn in ("location", "locationId", "locationCode"):
                            candidate = page.locator(
                                f"p-dropdown[formcontrolname='{fcn}']:not(p-dialog p-dropdown)"
                            )
                            try:
                                if candidate.count() > 0 and candidate.first.is_visible(timeout=500):
                                    dropdown = candidate.first
                                    break
                            except Exception:
                                continue

                    # 3️⃣ Fallback: first visible p-dropdown not inside a dialog
                    if dropdown is None:
                        all_dd = page.locator("p-dropdown")
                        for i in range(all_dd.count()):
                            dd = all_dd.nth(i)
                            try:
                                in_dialog = dd.evaluate("el => !!el.closest('[role=\"dialog\"]')")
                                if not in_dialog and dd.is_visible(timeout=300):
                                    dropdown = dd
                                    break
                            except Exception:
                                continue

                        if dropdown is None:
                            raise Exception("Could not find the inline location dropdown on the page")

                    _open_dropdown_and_pick(page, dropdown, value, timeout)
            except PlaywrightTimeoutError:
                    raise Exception("❌ Timeout while selecting location (inline)")
            except Exception as e:
                    raise Exception(f"❌ select_location_inline failed: {e}")




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
        """
        Fill the inline continuous-count row:
        autocomplete → location dropdown → quantities → 'Add Count'.
        """

        # ── Autocomplete item code ────────────────────────────────────────────
        ac = page.locator("input.p-autocomplete-input[placeholder*='Item Code']").first
        ac.scroll_into_view_if_needed()
        ac.click()
        ac.fill("")
        ac.type(item_query, delay=50)

        # Wait for UI to update (longer than before to let error label render too)
        page.wait_for_timeout(500)

        # 🔴 Check error label FIRST — item doesn't exist in the system
        not_found = page.locator("label.text-danger:has-text('Search term not found.')")
        if not_found.count() > 0 and not_found.is_visible():
            print(f"❌ Item NOT FOUND: {item_query}")
            return False  # ⛔ Stop flow — do not attempt location/qty/submit

        # ✅ Otherwise wait for and select from autocomplete dropdown
        results = page.locator("li.p-autocomplete-item")
        try:
            results.first.wait_for(state="visible", timeout=3000)
            results.first.click()
        except PlaywrightTimeoutError:
            print(f"⚠️ No dropdown result for: {item_query}")
            return False  # Safer than ArrowDown fallback

        page.wait_for_timeout(300)

        # ── Location ──────────────────────────────────────────────────────────
        select_location_inline(page, location)
        page.wait_for_timeout(200)

        # ── Quantities ────────────────────────────────────────────────────────
        page.fill('input[formcontrolname="auditedQty"]', str(audited_qty))
        page.fill('input[formcontrolname="damagedQty"]', str(damaged_qty))

        # ── Submit ────────────────────────────────────────────────────────────
        page.click("button:has-text('Add Count')")
        page.wait_for_timeout(300)

        return True


        # --------------------------------------------------------------
        # EXCEL LOADER (VALIDATED)
        # --------------------------------------------------------------
    def load_items_from_excel(
                path: str,
                sheet_name= Config.EXCEL_SHEET_auditor_1,
                location_col: str = "locations",
                code_col: str = "code",
                audited_col: str = "audited",
                damaged_col: str = "damaged",
            ) -> List[Tuple[str, str, float, float]]:

                if not os.path.exists(path):
                    print(f"❌ Excel file not found: {path}")
                    sys.exit(1)

                df = pd.read_excel(path, sheet_name= Config.EXCEL_SHEET_auditor_1)

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

            # Load and validate items (will sys.exit if file missing or irrecoverable)
                # ============================================
                # 1. Load test data from Excel
                # ============================================
    items_to_add = load_items_from_excel(
                        Config.EXCEL_PATH,
                        sheet_name=Config.EXCEL_SHEET_auditor_1,
                        code_col=Config.EXCEL_CODE_COL1,
                        audited_col=Config.EXCEL_AUDITED_COL1,
                        damaged_col=Config.EXCEL_DAMAGED_COL1,
                    )
    # --------------------------------------------------------------
    # SELECT BRANCH using XPATH (PrimeNG p-dropdown)
    # --------------------------------------------------------------
    def select_branch(page, branch_text: str):

        # 1️⃣ Branch dropdown container (XPath)
        dropdown = page.locator(
            'xpath=/html/body/app-root/app-layout/div/app-header/div[1]/div[2]/div[2]//p-dropdown'
        )
        dropdown.wait_for(state="visible", timeout=30000)

        # 2️⃣ Click dropdown label to open
        dropdown.locator(".p-dropdown-label").click()

        # 3️⃣ Wait for dropdown panel (overlay)
        panel = page.locator(".p-dropdown-panel").last
        panel.wait_for(state="visible", timeout=30000)

        # 4️⃣ Filter search (if exists)
        search = panel.locator("input.p-dropdown-filter")
        if search.count() > 0:
            search.fill("")
            search.fill(branch_text)
            page.wait_for_timeout(300)

        # 5️⃣ Select branch option
        option = panel.locator(
            "li.p-dropdown-item",
            has_text=branch_text
        )

        if option.count() == 0:
            raise Exception(f"❌ Branch not found: {branch_text}")

        option.first.click()

        # 6️⃣ Ensure panel closed
        panel.wait_for(state="hidden", timeout=30000)

        # 7️⃣ Final verification
        dropdown.locator(
            ".p-dropdown-label",
            has_text=branch_text
        ).wait_for(state="visible", timeout=30000)

        # ======================================================
        # NAVIGATION
        # ======================================================
    def navigate_to_ongoing_audits(Page, Config):
            """Navigate to the ongoing audits Page and open specified audit"""

            print("📂 Navigating to Ongoing Audits...")

           
            Page.wait_for_timeout(500)
    # Wait until element visible
            Page.wait_for_selector("a[href='/home/audit']", state="visible")

            # Click
            Page.click("a[href='/home/audit']")
            print("✅ Clicked on 'Audits' in sidebar")
            Page.wait_for_load_state("networkidle")
            select_branch(Page, Config.Branch)

            print(f"✅ Branch selected: {Config.Branch}")
            # Find and click the specific audit
            row = Page.locator(
                f"table tbody tr:has(td span:has-text('{Config.audit_name}'))"
                
            ).first
            
            row.locator("td span").first.click()
            print(f"✅ Opened audit: {Config.audit_name}")
    
        
            
                # open modal once
            click_add_item_button(Page)

            # fill item details
            fill_item_details_bound(
            Page,
            item_code=Config.code1,
            location=Config.location2,
            audited_qty=Config.aud_qty2,
            damaged_qty=Config.dam_qty2
        )
                    
            print(f"Processed {Config.code1} ({Config.aud_qty2}/{Config.dam_qty2}/{Config.location2})")
            detect_feedback(Page)
                    # wait a bit before closing
           
            Page.wait_for_timeout(500)
                            # ============================================
                            # 6. Add items from Excel using inline form
                            # ============================================
            print("\n" + "-"*70)
            print("🔷 ADDING ITEMS FROM EXCEL (Inline Form)")
            print("-"*70)
                            
#=============
    
    
        # ── Bulk loop ─────────────────────────────────────────────────────

            for idx, (location, code, audited, damaged) in enumerate(items_to_add, start=1):
                   print(f"\n[{idx}/{len(items_to_add)}] ➡️  {code} | A:{audited}  D:{damaged} | {location}")
                   success = add_item_count(Page, code, audited, damaged, location)

            success_count = 0
            fail_count = 0

            if success:
                    print(f"✅ [{idx}/{len(items_to_add)}] {code} "
                            f"(Audited: {audited}, Damaged: {damaged})")
                    detect_feedback(Page)
                    success_count   += 1
            else:
                            print(f"❌ [{idx}/{len(items_to_add)}] Failed: {code}")
                            fail_count    += 1
                        
                            Page.wait_for_timeout(Config.WAIT_AFTER_ACTION)
                    
                            print(f"\n📊 Summary: {success_count} succeeded, {fail_count} failed")
    navigate_to_ongoing_audits(Page, Config)



            
            
