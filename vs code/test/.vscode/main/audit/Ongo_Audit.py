import sys
import time
import os
import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
from login.popup_handler import detect_feedback
from login.logger_setup import mirrored_print
import pyautogui
# --------------------------------------------------------------
# GLOBAL SPEED CONTROL
# --------------------------------------------------------------
SLEEP_TIME = 1

def Ongo_Audit(page, Config):
    # --------------------------------------------------------------
    # UTILITIES
    # --------------------------------------------------------------
    def wait_for_overlay_to_disappear(page):
        for selector in [
            ".p-dialog-mask",
            ".p-component-overlay",
            ".cdk-overlay-backdrop"
        ]:
            try:
                page.wait_for_selector(selector, state="detached", timeout=2000)
            except PlaywrightTimeoutError:
                pass

    def is_already_mapped(dropdown_locator) -> bool:
        try:
            label = dropdown_locator.locator(
                "span.p-dropdown-label:not(.p-placeholder)"
            )
            return label.count() > 0 and label.first.inner_text().strip() != ""
        except:
            return False

    # --------------------------------------------------------------
    # DROPDOWN OPTION SELECTOR
    # --------------------------------------------------------------
    def select_option_for_dropdown_locator(page, dropdown_locator, option_text):
        dropdown_locator.click()
        time.sleep(SLEEP_TIME)

        option_text_norm = option_text.strip().lower()
        items = page.locator("li.p-dropdown-item")

        for i in range(items.count()):
            item = items.nth(i)
            if not item.is_visible():
                continue

            text = item.inner_text().strip().lower()
            if text == option_text_norm:
                item.scroll_into_view_if_needed()
                item.click(force=True)
                time.sleep(SLEEP_TIME)
                return True

        return False

    # --------------------------------------------------------------
    # WAIT FOR MAPPING ROWS
    # --------------------------------------------------------------
    def wait_for_mapping_rows(page, required_labels, timeout_ms=45000):
        deadline = time.time() + (timeout_ms / 1000)
        last_seen_labels = []

        row_container = page.locator("div.row-container")
        left_col = row_container.locator("div.col-md-6").nth(0)
        labels = left_col.locator("div.label > label")

        while time.time() < deadline:
            wait_for_overlay_to_disappear(page)

            if row_container.count() > 0 and row_container.first.is_visible():
                current_labels = [
                    labels.nth(i).inner_text().strip()
                    for i in range(labels.count())
                    if labels.nth(i).inner_text().strip()
                ]

                if current_labels:
                    last_seen_labels = current_labels

                if all(label in current_labels for label in required_labels):
                    return current_labels

            page.wait_for_timeout(500)

        raise Exception(
            f"Header mapping rows did not load in time. "
            f"Required={required_labels}, seen={last_seen_labels}"
        )

    # --------------------------------------------------------------
    # SELECT SHEET (NEW)
    # --------------------------------------------------------------
    def select_sheet(page, preferred_sheet):
        selector = "p-dropdown[placeholder='Choose Sheet'], p-dropdown[ng-reflect-placeholder='Choose Sheet']"
        mirrored_print(f"[SHEET] Waiting for selection dropdown (preferred: {preferred_sheet})")
        
        try:
            # Wait a short time to see if the dropdown appears
            page.wait_for_selector(selector, timeout=8000)
            dropdown = page.locator(selector).first
            
            # Use existing helper to select the option
            ok = select_option_for_dropdown_locator(page, dropdown, preferred_sheet)
            if ok:
                mirrored_print(f"✅ Selected target sheet: {preferred_sheet}")
                time.sleep(SLEEP_TIME)
                return preferred_sheet
            else:
                mirrored_print(f"⚠ Preferred sheet '{preferred_sheet}' not found. Picking first available.")
                dropdown.click()
                time.sleep(SLEEP_TIME)
                first_opt = page.locator("li.p-dropdown-item").first
                if first_opt.count() > 0:
                    txt = first_opt.inner_text().strip()
                    first_opt.click()
                    mirrored_print(f"✅ Selected fallback sheet: {txt}")
                    time.sleep(SLEEP_TIME)
                    return txt
        except PlaywrightTimeoutError:
            mirrored_print("ℹ No sheet selection dropdown appeared (skipping step)")
            return None
        except Exception as e:
            mirrored_print(f"⚠ Sheet selection error: {str(e)}")
            return None
        return None

    # --------------------------------------------------------------
    # HEADER MAPPING + VERIFICATION
    # --------------------------------------------------------------
    def map_headers(page, mapping):
        row_container = page.locator("div.row-container")
        left_col = row_container.locator("div.col-md-6").nth(0)
        right_col = row_container.locator("div.col-md-6").nth(1)

        labels = left_col.locator("div.label > label")
        dropdowns = right_col.locator("p-dropdown")

        label_texts = [
            labels.nth(i).inner_text().strip()
            for i in range(labels.count())
        ]

        mirrored_print(f"Found headers in UI: {label_texts}")

        all_ok = True

        for required_label, excel_header in mapping.items():
            wait_for_overlay_to_disappear(page)

            if required_label not in label_texts:
                mirrored_print(f"❌ UI missing label: {required_label}")
                all_ok = False
                continue

            idx = label_texts.index(required_label)
            dropdown = dropdowns.nth(idx)

            if is_already_mapped(dropdown):
                mapped_value = dropdown.locator(
                    "span.p-dropdown-label"
                ).inner_text().strip()

                if mapped_value.lower() == excel_header.lower():
                    mirrored_print(f"✔ Verified: {required_label} → {mapped_value}")
                    continue
                else:
                    mirrored_print(
                        f"⚠ Mismatch: {required_label} → {mapped_value} "
                        f"(expected {excel_header})"
                    )

            ok = select_option_for_dropdown_locator(page, dropdown, excel_header)

            if not ok:
                mirrored_print(f"❌ Failed to map {required_label}")
                all_ok = False
            else:
                mirrored_print(f"✔ Mapped {required_label} → {excel_header}")

        if not all_ok:
            raise Exception("❌ Header mapping verification FAILED")

        mirrored_print("✅ Header mapping & verification completed successfully")

    # --------------------------------------------------------------
    # SET CHECKBOX
    # --------------------------------------------------------------
    def set_checkbox(page, selector, should_be_checked):
        checkbox = page.wait_for_selector(selector)
        if should_be_checked and not checkbox.is_checked():
            checkbox.check(force=True)
        elif not should_be_checked and checkbox.is_checked():
            checkbox.uncheck(force=True)

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
    # SELECT AUDITORS
    # --------------------------------------------------------------
    def select_auditors(page, auditor_list):
        auditors = [a for a in auditor_list if a]
        if not auditors:
            return

        dropdown = page.locator("p-multiselect#role")
        dropdown.wait_for(state="visible")
        dropdown.locator(".p-multiselect-label").click()

        panel = page.locator("div.p-multiselect-panel").last
        panel.wait_for(state="visible")

        for auditor in auditors:
            search = panel.locator("input.p-multiselect-filter")
            if search.count() > 0:
                search.fill("")
                search.fill(auditor)
                page.wait_for_timeout(300)

            option = panel.locator("li.p-multiselect-item", has_text=auditor)
            if option.count() == 0:
                print(f"⚠️ Auditor not found, skipping: {auditor}")
                continue

            if "p-highlight" not in (option.first.get_attribute("class") or ""):
                option.first.click()
                page.wait_for_timeout(300)

        page.keyboard.press("Escape")
        panel.wait_for(state="hidden")

    # --------------------------------------------------------------
    # LOAD AUDITOR MAPPING FROM EXCEL SHEET
    # --------------------------------------------------------------
    def load_auditor_mapping():
        df = pd.read_excel(
            Config.EXCEL_PATH,
            sheet_name=Config.EXCEL_SHEET_AUDITOR_MAPPING
        )

        result = {}
        seen = {}

        for _, row in df.iterrows():
            auditor = str(row[Config.EXCEL_auditor_col]).strip()
            if not auditor or auditor.lower() == "nan":
                continue

            if auditor not in result:
                result[auditor] = {"categories": [], "storages": []}
                seen[auditor] = {"categories": set(), "storages": set()}

            cat_val = str(row.get(Config.EXCEL_category_col, "")).strip()
            if cat_val and cat_val.lower() != "nan":
                for cat in cat_val.split(","):
                    cat = cat.strip()
                    if cat and cat.lower() not in seen[auditor]["categories"]:
                        result[auditor]["categories"].append(cat)
                        seen[auditor]["categories"].add(cat.lower())

            stor_val = str(row.get(Config.EXCEL_storage_col, "")).strip()
            if stor_val and stor_val.lower() != "nan":
                for stor in stor_val.split(","):
                    stor = stor.strip()
                    if stor and stor.lower() not in seen[auditor]["storages"]:
                        result[auditor]["storages"].append(stor)
                        seen[auditor]["storages"].add(stor.lower())

        return result

    # --------------------------------------------------------------
    # FIND EXACT AUDITOR ROW
    # --------------------------------------------------------------
    def find_auditor_row(page, auditor_name):
        rows = page.locator("tr")
        for i in range(rows.count()):
            row = rows.nth(i)
            tds = row.locator("td")
            for j in range(tds.count()):
                if tds.nth(j).inner_text().strip() == auditor_name:
                    return row
        return None

    # --------------------------------------------------------------
    # OPEN MULTISELECT PANEL FOR A ROW
    # --------------------------------------------------------------
    def open_multiselect_panel(page, row):
        row.locator("div.p-multiselect").click()
        panel = page.locator("div.p-multiselect-panel").filter(
            has=page.locator(":visible")
        )
        panel.wait_for(state="visible")
        return panel

    # --------------------------------------------------------------
    # SELECT ITEMS IN AN OPEN MULTISELECT PANEL (idempotent)
    # --------------------------------------------------------------
    def select_items_in_panel(page, panel, items, auditor_name, item_type):
        for item_text in items:
            option = panel.locator("li.p-multiselect-item", has_text=item_text)

            if option.count() == 0:
                mirrored_print(
                    f"⚠ {item_type} '{item_text}' not found for '{auditor_name}'"
                )
                continue

            cls = option.first.get_attribute("class") or ""
            if "p-highlight" not in cls:
                option.first.click()
                page.wait_for_timeout(300)
            else:
                mirrored_print(
                    f"✔ Already selected: '{item_text}' for '{auditor_name}'"
                )

        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

    # --------------------------------------------------------------
    # APPLY AUDITOR ASSIGNMENTS
    # --------------------------------------------------------------
    def apply_auditor_assignments(page, mapping_type):
        if mapping_type == "Random":
            mirrored_print("ℹ Mapping type is Random — no assignments needed")
            return

        auditor_map = load_auditor_mapping()
        mirrored_print(f"📋 Loaded auditor mapping: {auditor_map}")

        for auditor, data in auditor_map.items():

            if mapping_type == "By Category":
                categories = data["categories"]
                if not categories:
                    mirrored_print(f"⚠ No categories found for '{auditor}' in sheet")
                    continue
                mirrored_print(f"→ Assigning categories {categories} to '{auditor}'")
                row = find_auditor_row(page, auditor)
                if row is None:
                    mirrored_print(f"❌ Row not found for auditor: '{auditor}'")
                    continue
                panel = open_multiselect_panel(page, row)
                select_items_in_panel(page, panel, categories, auditor, "Category")

            elif mapping_type == "By Storage":
                storages = data["storages"]
                if not storages:
                    mirrored_print(f"⚠ No storages found for '{auditor}' in sheet")
                    continue
                mirrored_print(f"→ Assigning storages {storages} to '{auditor}'")
                row = find_auditor_row(page, auditor)
                if row is None:
                    mirrored_print(f"❌ Row not found for auditor: '{auditor}'")
                    continue
                panel = open_multiselect_panel(page, row)
                select_items_in_panel(page, panel, storages, auditor, "Storage")

            else:
                raise ValueError(
                    f"Unknown AUDITOR_MAPPING_TYPE: '{mapping_type}'. "
                    "Must be 'Random', 'By Category', or 'By Storage'."
                )

    # --------------------------------------------------------------
    # TEST MAPPING AND SAVING
    # --------------------------------------------------------------
    def test_mapping_and_saving(page):

        mirrored_print("📥 Uploading primary file")
        page.set_input_files("input#formFileSm", Config.oa_excel_path)
        
        # ── NEW: Sheet selection ──────────────────────────────────────────
        # Mandatory if the workbook has multiple sheets or the app requires it
        pref_sheet = getattr(Config, 'oa_sheet', 'Data')
        select_sheet(page, pref_sheet)
        # ──────────────────────────────────────────────────────────────────

        page.wait_for_selector("div.row-container")
    # -----------------------------
    # First mapping attempt
    # -----------------------------
        map_headers(page, Config.oa_mapping)

        page.click("button:has-text('Map')")
        time.sleep(SLEEP_TIME)

   
        page.click("button:has-text('Save')")
        detect_feedback(page)

        mirrored_print("🎉 Mapping & saving completed successfully")
        page.mouse.click(200, 300)




    # --------------------------------------------------------------
    # CLICK AUDIT ROW
    # --------------------------------------------------------------
    def click_audit(page, audit_name):
        page.wait_for_load_state("networkidle")

        # Find and click the specific audit using ap_audit_name
        row = page.locator(
            f"table tbody tr:has(td span:has-text('{Config.ap_audit_name}'))"
        ).first
        row.locator("td span").first.click()
        print(f"✅ Opened audit: {Config.ap_audit_name}")

    # --------------------------------------------------------------
    # MAIN FLOW
    # Ongoing Audit only uses: oa_group_name, ap_audit_name, oa_excel_path
    # Credentials (oa_email / oa_password) and Excel column config
    # have moved to Auditor 1 SA (A_SA.py) — see asa_* fields.
    # --------------------------------------------------------------
    def setup_Audit(page):
        page.wait_for_selector("a[href='/home/audit']", state="visible")
        page.click("a[href='/home/audit']")
        time.sleep(SLEEP_TIME)

        select_branch(page, Config.Branch)
        print(f"✅ Branch selected: {Config.Branch}")
        time.sleep(SLEEP_TIME)

        click_audit(page, Config.ap_audit_name)
        detect_feedback(page)

        page.click("img[alt='seting icon']")
        time.sleep(SLEEP_TIME)

        print("✅ Opened audit settings")
        oa_aud1 = getattr(Config, "oa_Auditor1", None) or Config.Auditor1
        oa_aud2 = getattr(Config, "oa_Auditor2", None) or Config.Auditor2
        print(f"✅ select_auditors= {oa_aud1}, {oa_aud2}")

        select_auditors(page, [oa_aud1, oa_aud2])

        set_checkbox(page, "input[formcontrolname='IsDamageQty']",       Config.oa_A_Checkboxes_Audit_Damaged)
        set_checkbox(page, "input[formcontrolname='isStockItems']",      Config.oa_A_Checkboxes_StockItems)
        set_checkbox(page, "input[formcontrolname='isGeoLocation']",     Config.oa_A_Checkboxes_geo)
        set_checkbox(page, "input[formcontrolname='isPhotoValidation']", Config.oa_A_Checkboxes_photo)
        time.sleep(SLEEP_TIME)

        page.click("button:has-text('Update')")
        time.sleep(SLEEP_TIME)

        page.click("button:has-text('Import Stock Sheet')")
        test_mapping_and_saving(page)
        time.sleep(SLEEP_TIME)

        mapping_type = Config.AUDITOR_MAPPING_TYPE
        page.locator("p-dropdown[formcontrolname='auditMappingType']").click()
        page.locator("li.p-dropdown-item", has_text=mapping_type).click()
        time.sleep(SLEEP_TIME)

        apply_auditor_assignments(page, mapping_type)
        time.sleep(SLEEP_TIME)

        page.click("button:has-text('Update')")
        time.sleep(SLEEP_TIME)

    # --------------------------------------------------------------
    # ENTRY POINT
    # --------------------------------------------------------------
    setup_Audit(page)