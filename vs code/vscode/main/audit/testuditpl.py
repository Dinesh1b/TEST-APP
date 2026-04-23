import re
import sys
import os
import random
import string
import pandas as pd
from typing import List, Tuple, Optional
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError

# ======================================================
# PATH SETUP
# ======================================================
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login
from login.popup_handler import detect_feedback


# ======================================================
# CONFIGURATION
# ======================================================
class Config:
    """Centralized configuration"""
    EXCEL_PATH = r"C:\Users\HP\Documents\input\data_items.xlsx"
    EXCEL_SHEET = 0
    EXCEL_CODE_COL = "code"
    EXCEL_AUDITED_COL = "audited"
    EXCEL_DAMAGED_COL = "damaged"
    
    # Expected totals for validation
    EXPECTED_TOTALS = {
        "Stock Value": "5000",
        "Audited Value": "2000",
        "Damaged Value": "3000",
        "StockLoss Value": "2000",
        "Stock Excess Value": "2000",
        "Completed Inventory": "50"
    }
    
    # Column indices in the totals table
    TOTAL_COLUMNS = {
        "Stock Value": 1,
        "Audited Value": 2,
        "Damaged Value": 3,
        "StockLoss Value": 4,
        "Stock Excess Value": 6,
        "Completed Inventory": 7
    }
    
    # Timeout settings
    DEFAULT_TIMEOUT = 10000
    SHORT_TIMEOUT = 5000
    WAIT_AFTER_ACTION = 300


# ======================================================
# UTILITY FUNCTIONS
# ======================================================
def normalize(text: str) -> str:
    """Remove commas and extra spaces from text"""
    if not text:
        return ""
    return text.replace(",", "").strip()


def js_set_number_with_events(page: Page, selector: str, value: str) -> None:
    """
    Set number input value via JavaScript and trigger all necessary events.
    This ensures Angular/PrimeNG change detection is triggered.
    """
    try:
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
        page.wait_for_timeout(100)
    except Exception as e:
        print(f"⚠️  Warning: Could not set value via JS for {selector}: {e}")


def random_name() -> str:
    """Generate a random item code"""
    return "itemCode" + "".join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )


# ======================================================
# EXCEL DATA LOADING
# ======================================================
def load_items_from_excel(
    path: str,
    sheet_name: int = 0,
    code_col: str = "code",
    audited_col: str = "audited",
    damaged_col: str = "damaged",
) -> List[Tuple[str, int, int]]:
    """
    Load item data from Excel with intelligent column fallback.
    
    Returns:
        List of tuples: (item_code, audited_qty, damaged_qty)
    
    Exits:
        Exits with error if file not found or Excel is invalid
    """
    # Validate file exists
    if not os.path.exists(path):
        print(f"❌ ERROR: Excel file not found: {path}")
        sys.exit(1)

    # Read Excel
    try:
        df = pd.read_excel(path, sheet_name=sheet_name)
    except Exception as e:
        print(f"❌ ERROR: Failed to read Excel file: {e}")
        sys.exit(1)

    # Validate DataFrame is not empty
    if df.empty:
        print("❌ ERROR: Excel file is empty.")
        sys.exit(1)

    # Determine code column (required)
    if code_col in df.columns:
        chosen_code_col = code_col
    else:
        chosen_code_col = df.columns[0] if len(df.columns) >= 1 else None
        if chosen_code_col is None:
            print("❌ ERROR: Excel has no columns.")
            sys.exit(1)
        print(f"⚠️  WARNING: '{code_col}' not found. Using first column '{chosen_code_col}' as code.")

    # Determine audited column (fallback to second column)
    if audited_col in df.columns:
        chosen_audited_col = audited_col
    else:
        chosen_audited_col = df.columns[1] if len(df.columns) >= 2 else None
        if chosen_audited_col is None:
            print(f"⚠️  WARNING: '{audited_col}' not found. Defaulting audited values to 0.")
        else:
            print(f"⚠️  WARNING: '{audited_col}' not found. Using column '{chosen_audited_col}' as audited.")

    # Determine damaged column (fallback to third column)
    if damaged_col in df.columns:
        chosen_damaged_col = damaged_col
    else:
        chosen_damaged_col = df.columns[2] if len(df.columns) >= 3 else None
        if chosen_damaged_col is None:
            print(f"⚠️  WARNING: '{damaged_col}' not found. Defaulting damaged values to 0.")
        else:
            print(f"⚠️  WARNING: '{damaged_col}' not found. Using column '{chosen_damaged_col}' as damaged.")

    # Build items list
    items = []
    for idx, row in df.iterrows():
        # Get item code
        raw_code = row.get(chosen_code_col, "") if chosen_code_col is not None else ""
        code = str(raw_code).strip()
        if not code or code.lower() == 'nan':  # FIX: Skip NaN values
            continue

        # Get audited quantity
        if chosen_audited_col is not None:
            audited_raw = row.get(chosen_audited_col, 0)
            audited_num = pd.to_numeric([audited_raw], errors="coerce")[0]
            audited = int(audited_num) if not pd.isna(audited_num) else 0
        else:
            audited = 0

        # Get damaged quantity
        if chosen_damaged_col is not None:
            damaged_raw = row.get(chosen_damaged_col, 0)
            damaged_num = pd.to_numeric([damaged_raw], errors="coerce")[0]
            damaged = int(damaged_num) if not pd.isna(damaged_num) else 0
        else:
            damaged = 0

        items.append((code, audited, damaged))

    # Validate we have items
    if not items:
        print("⚠️  WARNING: No valid items found in Excel.")
        return []
    
    print(f"✅ Loaded {len(items)} items from Excel")
    return items


# ======================================================
# NAVIGATION
# ======================================================
def navigate_to_ongoing_audits(page: Page, audit_name: str = "Audit_PWDNZ5_1"):
    """Navigate to the ongoing audits page and open specified audit"""
    print("📂 Navigating to Ongoing Audits...")
    page.click("a[href='#/home/audit']")
    page.wait_for_load_state("networkidle")

    # Find and click the specific audit
    row = page.locator(
        f"table tbody tr:has(td span:has-text('{audit_name}'))"
        f":has(td:has-text('Complete Count'))"
    ).first

    row.locator("td span").first.click()
    page.locator("button.primary-button:has-text('Stock Audit')").click()
    page.wait_for_load_state("networkidle")
    print(f"✅ Opened audit: {audit_name}")


# ======================================================
# FORM FILLING
# ======================================================
def fill_inventory_form_robust(page: Page, item_code_new: str) -> bool:
    """
    Fill out the inventory form with robust error handling
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Wait for the form to be visible
        print("Waiting for form...")
        page.wait_for_selector('form', timeout=Config.DEFAULT_TIMEOUT)
        
        # 1. Select Category - "Parts"
        print("Selecting category...")
        try:
            # Method 1: Using formcontrolname attribute
            category_dropdown = page.locator('p-dropdown[formcontrolname="itemCategoryId"]')
            category_dropdown.click(timeout=Config.SHORT_TIMEOUT)
            
            # Wait for dropdown to open
            page.wait_for_timeout(500)
            
            # Click on "Parts" option
            try:
                page.locator('[role="option"]:has-text("Parts")').click(timeout=3000)
            except:
                # Alternative: use text content
                page.get_by_text("Parts", exact=False).first.click()
                
        except Exception as e:
            print(f"⚠️  Warning selecting category: {e}")
            # Try alternative selector
            try:
                page.locator('.p-dropdown').first.click()
                page.wait_for_timeout(500)
                page.locator('li:has-text("Parts")').first.click()
            except Exception as e2:
                print(f"❌ ERROR: Could not select category: {e2}")
                return False
        
        print("✓ Category selected")
        
        
        # 2. Fill Item Code
        print(f"Filling Item Code: {item_code_new}")
        item_code_input = page.locator('input[formcontrolname="itemCode"]')
        item_code_input.clear()  # FIX: Clear before filling
        item_code_input.fill(item_code_new)
        print("✓ Item Code filled")
                
        # 3. Fill Item Name
        print("Filling Item Name...")
        item_name_input = page.locator('input[formcontrolname="itemName"]')
        item_name_input.clear()
        item_name_input.fill('abcd1234')
        print("✓ Item Name filled")
        
        # 4. Fill Cost Price
        print("Filling Cost Price...")
        cost_price_input = page.locator('input[formcontrolname="costPrice"]')
        cost_price_input.clear()
        cost_price_input.fill('100')
        print("✓ Cost Price filled")
        
        # Small delay to ensure all fields are processed
        page.wait_for_timeout(500)
        
        # 5. Click Save button
        print("Clicking Save button...")
        try:
            # Method 1: Using text and class
            save_button = page.locator('button.primary-button:has-text("Save")')
            save_button.click(timeout=Config.SHORT_TIMEOUT)
            detect_feedback(page)
        except Exception as e:
            print(f"⚠️  Trying alternative save method: {e}")
            # Method 2: Using type
            save_button = page.locator('button[type="submit"]')
            save_button.click(timeout=Config.SHORT_TIMEOUT)
            detect_feedback(page)
        
        page.wait_for_timeout(800)
        print("✅ Form filled and saved successfully!")

        

         # Locate input
        autocomplete_input = page.locator(
            'input[placeholder*="Search Item Code / Name / Barcode"]'
        )

        # Wait for visible
        autocomplete_input.wait_for(state="visible", timeout=10000)

        # Click to focus
        autocomplete_input.click()

        # Clear existing value (if any)
        autocomplete_input.press("Control+A")
        autocomplete_input.press("Backspace")

        # Human-like typing
        for char in item_code_new:
            autocomplete_input.type(char, delay=120)

        # Wait for dropdown items
        page.wait_for_selector("li.p-autocomplete-item", timeout=5000)

        # Select first suggestion
        first_option = page.locator("li.p-autocomplete-item").first
        first_option.click()

        print("✅ Item selected successfully")\
        

       
        page.wait_for_timeout(500)

        
        # Fill in quantities using formcontrolname attribute
        page.locator('input[formcontrolname="auditedQty"]').fill("12")
        print("✓ Audited Quantity filled")
        page.locator('input[formcontrolname="damagedQty"]').fill("13")
        print("✓ Damaged Quantity filled")

        page.get_by_role("button", name="Add Count").click()
        page.wait_for_timeout(800)
        print("✓ Add Count clicked")
        return True
    
    except Exception as e:
        print(f"❌ ERROR in fill_inventory_form_robust: {e}")
        return False


# ======================================================
# ITEM ENTRY - INLINE FORM (Method 1)
# ======================================================
def add_item_inline(
    page: Page, 
    item_code: str, 
    audited_qty: int = 0, 
    damaged_qty: int = 0
) -> bool:
    """
    Add item using the inline form (autocomplete on main page).
    
    This method:
    1. Fills autocomplete with item code
    2. Selects first suggestion
    3. Fills quantities
    4. Clicks "Add Count"
    
    Returns:
        True if successful
    """
    try:
        # Fill autocomplete
        ac_selector = "input.p-autocomplete-input[placeholder*='Item Code']"
        ac = page.locator(ac_selector).first
        
        # FIX: Check if element exists before interacting
        if ac.count() == 0:
            print(f"❌ ERROR: Autocomplete input not found")
            return False
        
        ac.scroll_into_view_if_needed()
        ac.click()
        ac.fill("")  # Clear first
        ac.type(item_code, delay=50)  # FIX: Use type with delay for better reliability
        
        # Wait for and select suggestion
        try:
            page.wait_for_selector("li.p-autocomplete-item:visible", timeout=Config.SHORT_TIMEOUT)
            page.locator("li.p-autocomplete-item").first.click()
        except PlaywrightTimeoutError:
            print("⚠️  Autocomplete timeout, trying keyboard navigation...")
            # Fallback: keyboard navigation
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(200)
            page.keyboard.press("Enter")
        
        page.wait_for_timeout(Config.WAIT_AFTER_ACTION)
        
        # Fill quantities
        audited_selector = 'input[formcontrolname="auditedQty"]'
        damaged_selector = 'input[formcontrolname="damagedQty"]'
        
        # FIX: Check if fields exist
        if page.locator(audited_selector).count() == 0:
            print(f"❌ ERROR: Audited quantity field not found")
            return False
        
        page.fill(audited_selector, str(audited_qty))

        page.fill(damaged_selector, str(damaged_qty))
        
        # Trigger change events for Angular
        js_set_number_with_events(page, audited_selector, str(audited_qty))
        js_set_number_with_events(page, damaged_selector, str(damaged_qty))
        
        # Click Add Count
        add_count_btn = page.locator("button:has-text('Add Count')")
        if add_count_btn.count() == 0:
            print(f"❌ ERROR: Add Count button not found")
            return False
            
        add_count_btn.click()
        page.wait_for_timeout(Config.WAIT_AFTER_ACTION)
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR in add_item_inline: {e}")
        return False


# ======================================================
# ITEM ENTRY - DIALOG MODAL (Method 2)
# ======================================================
def click_add_item_button(page: Page):
    """Click the 'Add Item' button to open the dialog modal"""
    add_btn_selector = "button:has-text('Add Item')"
    page.click(add_btn_selector)
    page.wait_for_timeout(800)




# ======================================================
# VALIDATION
# ======================================================
def verify_total_values(
    page: Page, 
    expected: Optional[dict] = None, 
    columns: Optional[dict] = None
) -> bool:
    """
    Verify the total row values in the audit summary table.
    
    Args:
        page: Playwright Page object
        expected: Dictionary of expected values (uses Config.EXPECTED_TOTALS if None)
        columns: Dictionary of column indices (uses Config.TOTAL_COLUMNS if None)
    
    Returns:
        True if all validations pass, False otherwise
    """
    if expected is None:
        expected = Config.EXPECTED_TOTALS
    if columns is None:
        columns = Config.TOTAL_COLUMNS
    
    try:
        # FIX: Check if total row exists
        total_row = page.locator("tfoot tr")
        if total_row.count() == 0:
            print("❌ ERROR: Total row not found in table")
            return False
        
        errors = []
        
        print("\n" + "="*70)
        print("📊 TOTAL ROW VALIDATION (Actual vs Expected)")
        print("="*70)
        
        for label, index in columns.items():
            try:
                cell = total_row.locator("td").nth(index)
                if cell.count() == 0:
                    print(f"❌ {label:25} | Cell not found at index {index}")
                    errors.append(f"{label} cell not found")
                    continue
                
                actual = normalize(cell.inner_text())
                expected_val = expected[label]
                
                if actual == expected_val:
                    print(f"✅ {label:25} | Actual: {actual:>8} | Expected: {expected_val}")
                else:
                    print(f"❌ {label:25} | Actual: {actual:>8} | Expected: {expected_val}")
                    errors.append(f"{label} mismatch (Expected={expected_val}, Actual={actual})")
            except Exception as e:
                print(f"❌ {label:25} | Error reading value: {e}")
                errors.append(f"{label} error: {e}")
        
        print("="*70)
        
        if errors:
            print(f"\n❌ TOTAL ROW VALIDATION FAILED:\n   - " + "\n   - ".join(errors))
            return False
        
        print("✅ ALL VALIDATIONS PASSED\n")
        return True
        
    except Exception as e:
        print(f"❌ ERROR in verify_total_values: {e}")
        return False


# ======================================================
# MAIN EXECUTION
# ======================================================
if __name__ == "__main__":
    """Main execution flow"""
    print("\n" + "="*70)
    print("🚀 STARTING AUDIT AUTOMATION")
    print("="*70 + "\n")
    
    browser = None
    
    try:
        # ============================================
        # 1. Load test data from Excel
        # ============================================
        items_from_excel = load_items_from_excel(
            Config.EXCEL_PATH,
            sheet_name=Config.EXCEL_SHEET,
            code_col=Config.EXCEL_CODE_COL,
            audited_col=Config.EXCEL_AUDITED_COL,
            damaged_col=Config.EXCEL_DAMAGED_COL,
        )
        
       
        # ============================================
        # 2. Start browser and login
        # ============================================
        print("\n🌐 Starting browser...")
        with sync_playwright() as p:
            browser, page = login(
                p,
                browser_name="chrome",
                environment="QA"
            )
            
            # ============================================
            # 3. Navigate to audit
            # ============================================
            navigate_to_ongoing_audits(page)
            
            
            # ============================================
            # 4. Create new test item via dialog
            # ============================================
            print("\n" + "-"*70)
            print("🔷 CREATING NEW TEST ITEM VIA DIALOG")
            print("-"*70)
            
            click_add_item_button(page)
                
            page.wait_for_timeout(600)
            
            
            item_code_new = random_name()
            fill_inventory_form_robust(page, item_code_new)
               
            
            
            
            # ============================================
            # 6. Add items from Excel using inline form
            # ============================================
            print("\n" + "-"*70)
            print("🔷 ADDING ITEMS FROM EXCEL (Inline Form)")
            print("-"*70)
            
            success_count = 0
            fail_count = 0
            
            for idx, (code, audited, damaged) in enumerate(items_from_excel, 1):
                success = add_item_inline(page, code, audited, damaged)
                
                if success:
                    print(f"✅ [{idx}/{len(items_from_excel)}] {code} "
                          f"(Audited: {audited}, Damaged: {damaged})")
                    detect_feedback(page)
                    success_count += 1
                else:
                    print(f"❌ [{idx}/{len(items_from_excel)}] Failed: {code}")
                    fail_count += 1
                
                page.wait_for_timeout(Config.WAIT_AFTER_ACTION)
            
            print(f"\n📊 Summary: {success_count} succeeded, {fail_count} failed")
            
            # ============================================
            # 7. Navigate back and validate totals
            # ============================================
            print("\n" + "-"*70)
            print("🔍 VALIDATING TOTALS")
            print("-"*70)

            back_button = page.locator("button.primary-button:has-text('Back')").first
            if back_button.count() > 0:
                back_button.click()
                page.wait_for_timeout(1000)
            else:
                print("⚠️  Warning: Back button not found, skipping navigation")
            
            validation_passed = verify_total_values(page)
            
            # ============================================
            # 8. Complete
            # ============================================
            print("\n" + "="*70)
            if validation_passed and fail_count == 0:
                print("✅ AUDIT AUTOMATION COMPLETED SUCCESSFULLY")
            else:
                print("⚠️  AUDIT AUTOMATION COMPLETED WITH WARNINGS/ERRORS")
            print("="*70 + "\n")
            
            input("Press ENTER to close browser...")
            browser.close()
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Script interrupted by user")
        if browser:
            browser.close()
    except Exception as e:
        print(f"\n\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        if browser:
            browser.close()
        sys.exit(1)


