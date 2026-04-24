import time
from turtle import pd
import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from backend.shared.popup_handler import detect_feedback
from backend.shared.logger_setup import mirrored_print

# --------------------------------------------------------------
# GLOBAL SPEED CONTROL
# --------------------------------------------------------------
SLEEP_TIME = 1

def Q_setting(page, Config):
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
    # DROPDOWN OPTION SELECTOR (FIXED)
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
    # HEADER MAPPING + VERIFICATION (NO DUPLICATE)
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

            # -----------------------------
            # VERIFY EXISTING MAPPING
            # -----------------------------
            if is_already_mapped(dropdown):
                mapped_value = dropdown.locator(
                    "span.p-dropdown-label"
                ).inner_text().strip()

                if mapped_value.lower() == excel_header.lower():
                    mirrored_print(f"✔ Verified: {required_label} → {mapped_value}")
                    continue
                else:
                    mirrored_print(
                        f"⚠ Mismatch: {required_label} → {mapped_value} (expected {excel_header})"
                    )

            # -----------------------------
            # MAP IF NOT MATCHED
            # -----------------------------
            ok = select_option_for_dropdown_locator(
                page, dropdown, excel_header
            )

            if not ok:
                mirrored_print(f"❌ Failed to map {required_label}")
                all_ok = False
            else:
                mirrored_print(f"✔ Mapped {required_label} → {excel_header}")

        if not all_ok:
            raise Exception("❌ Header mapping verification FAILED")

        mirrored_print("✅ Header mapping & verification completed successfully")


    def set_checkbox(page, selector, should_be_checked):
        checkbox = page.wait_for_selector(selector)
        if should_be_checked and not checkbox.is_checked():
            checkbox.check(force=True)
        elif not should_be_checked and checkbox.is_checked():
            checkbox.uncheck(force=True)
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
                raise Exception(f"Auditor not found: {auditor}")

            if "p-highlight" not in (option.first.get_attribute("class") or ""):
                option.first.click()
                page.wait_for_timeout(300)

        page.keyboard.press("Escape")
        panel.wait_for(state="hidden")


    # --------------------------------------------------------------
    # LOAD AUDITOR MAPPING FROM SINGLE SHEET
    # Returns: { auditor_name: { "categories": [...], "storages": [...] } }
    # Reads EXCEL_SHEET_AUDITOR_MAPPING with columns: Auditor | Category | Storage
    # --------------------------------------------------------------
    def load_auditor_mapping():
        df = pd.read_excel(
            Config.EXCEL_PATH,
            sheet_name=Config.EXCEL_SHEET_AUDITOR_MAPPING
        )

        result = {}   # { auditor: { "categories": [], "storages": [] } }
        seen   = {}   # { auditor: { "categories": set, "storages": set } }

        for _, row in df.iterrows():
            auditor = str(row[Config.EXCEL_auditor_col]).strip()
            if not auditor or auditor.lower() == "nan":
                continue

            if auditor not in result:
                result[auditor] = {"categories": [], "storages": []}
                seen[auditor]   = {"categories": set(), "storages": set()}

            # --- Category column ---
            cat_val = str(row.get(Config.EXCEL_category_col, "")).strip()
            if cat_val and cat_val.lower() != "nan":
                for cat in cat_val.split(","):
                    cat = cat.strip()
                    if cat and cat.lower() not in seen[auditor]["categories"]:
                        result[auditor]["categories"].append(cat)
                        seen[auditor]["categories"].add(cat.lower())

            # --- Storage column ---
            stor_val = str(row.get(Config.EXCEL_storage_col, "")).strip()
            if stor_val and stor_val.lower() != "nan":
                for stor in stor_val.split(","):
                    stor = stor.strip()
                    if stor and stor.lower() not in seen[auditor]["storages"]:
                        result[auditor]["storages"].append(stor)
                        seen[auditor]["storages"].add(stor.lower())

        return result


        # --------------------------------------------------------------
        # FIND EXACT AUDITOR ROW  (exact <td> match, not substring)
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
    # SELECT ITEMS IN AN OPEN MULTISELECT PANEL  (idempotent)
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
    #   "Random"      → nothing to assign
    #   "By Category" → assign Category column values per auditor
    #   "By Storage"  → assign Storage  column values per auditor
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
        page.set_input_files("input#formFileSm", Config.EXCEL_PATH)
        page.wait_for_selector("div.row-container")

        
    # -----------------------------
    # First mapping attempt
    # -----------------------------
        map_headers(page, Config.mapping)

        page.click("button:has-text('Map')")
        time.sleep(SLEEP_TIME)

   
        page.click("button:has-text('Save')")
        detect_feedback(page)

        mirrored_print("🎉 Mapping & saving completed successfully")
        page.mouse.click(200, 300)


    def create_name(page, Config):
        audit_name = Config.audit_name
        input_selector = "input.underline-input"
        button_selector = "button:has-text('Create Audit')"

        try:
            # get current value
            current_value = page.input_value(input_selector)

            # if empty, fill audit name
            if not current_value.strip():
                    page.fill(input_selector, audit_name)

                    page.click(button_selector)

        except Exception as e:
            mirrored_print(f"❌ Failed to create audit with name {audit_name}: {e}")
            raise
    # --------------------------------------------------------------
    # MAIN FLOW
    # --------------------------------------------------------------
    def create_and_setup_audit(page):
                # Wait until element visible
        page.wait_for_selector("a[href='/home/audit']", state="visible")

        # Click
        page.click("a[href='/home/audit']")
        time.sleep(SLEEP_TIME)
        #branch selection moved before clicking create audit to avoid branch related issues during audit creation
        select_branch(page, Config.Branch)
        print(f"✅ Branch selected: {Config.Branch}")

        time.sleep(SLEEP_TIME)   
        page.click("button.createAuditBtn")
        time.sleep(SLEEP_TIME)

        page.click("button:has-text('Quick Audit')")
        time.sleep(SLEEP_TIME)

        create_name(page, Config)

        time.sleep(SLEEP_TIME)
        detect_feedback(page)

        page.click("img[alt='seting icon']")
        time.sleep(SLEEP_TIME)

        select_auditors(page,[Config.Auditor_name1, Config.Auditor_name2, Config.Auditor_name3])
      

        # Audit Damaged Inventory
        set_checkbox(page, "input[formcontrolname='IsDamageQty']", Config.Checkboxes_Audit_Damaged)

        # Show Stock Count to Auditor
        set_checkbox(page, "input[formcontrolname='isStockItems']", Config.Checkboxes_StockItems)

        # Geo Tagging
        set_checkbox(page, "input[formcontrolname='isGeoLocation']", Config.Checkboxes_geo)

        # Photo Validation
        set_checkbox(page, "input[formcontrolname='isPhotoValidation']", Config.Checkboxes_photo)
        time.sleep(SLEEP_TIME)


        page.click("button:has-text('Update')")
        time.sleep(SLEEP_TIME)

        page.click("button:has-text('Import Stock Sheet')")
        test_mapping_and_saving(page)

        # --- Settings pass 2: mapping type + category/storage assignments ---
        page.click("img[alt='seting icon']")
        time.sleep(SLEEP_TIME)

        time.sleep(SLEEP_TIME)
        #    mapping_type = Config.AUDITOR_MAPPING_TYPE
        mapping_type = Config.AUDITOR_MAPPING_TYPE
        page.locator("p-dropdown[formcontrolname='auditMappingType']").click()
        page.locator("li.p-dropdown-item", has_text= mapping_type).click()
        time.sleep(SLEEP_TIME)
            # "Random" → nothing extra; "By Category"/"By Storage" → assign from sheet
        apply_auditor_assignments(page, mapping_type)
        time.sleep(SLEEP_TIME)
        page.click("button:has-text('Update')")
        time.sleep(SLEEP_TIME)



    # --------------------------------------------------------------
    # Execute main flow
    create_and_setup_audit(page)