import sys
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError

# ======================================================
# PATH SETUP
# ======================================================
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login


# ======================================================
# VALIDATION RESULT CLASSES
# ======================================================
class ValidationStatus(Enum):
    PASSED = "✅ PASSED"
    FAILED = "❌ FAILED"
    WARNING = "⚠️  WARNING"
    SKIPPED = "⏭️  SKIPPED"


@dataclass
class FieldValidation:
    """Validation result for a single field"""
    field_name: str
    expected_value: str
    actual_value: str
    status: ValidationStatus
    error_message: Optional[str] = None
    
    @property
    def passed(self) -> bool:
        return self.status == ValidationStatus.PASSED
    
    def __str__(self) -> str:
        if self.passed:
            return f"  {self.status.value} {self.field_name}: {self.actual_value}"
        else:
            return (f"  {self.status.value} {self.field_name}: "
                   f"Expected='{self.expected_value}', Got='{self.actual_value}'")


@dataclass
class RowValidation:
    """Validation result for an entire row"""
    row_number: int
    item_code: str
    field_validations: List[FieldValidation]
    overall_status: ValidationStatus
    error_message: Optional[str] = None
    
    @property
    def passed(self) -> bool:
        return all(fv.passed for fv in self.field_validations)
    
    @property
    def failed_fields(self) -> List[FieldValidation]:
        return [fv for fv in self.field_validations if not fv.passed]
    
    def __str__(self) -> str:
        header = f"\nRow {self.row_number} ({self.item_code}): {self.overall_status.value}"
        if self.error_message:
            header += f" - {self.error_message}"
        
        field_results = "\n".join(str(fv) for fv in self.field_validations)
        return f"{header}\n{field_results}"


@dataclass
class ValidationReport:
    """Complete validation report"""
    total_rows_expected: int
    total_rows_actual: int
    row_validations: List[RowValidation]
    overall_status: ValidationStatus
    summary: Dict[str, int]
    
    @property
    def passed_rows(self) -> List[RowValidation]:
        return [rv for rv in self.row_validations if rv.passed]
    
    @property
    def failed_rows(self) -> List[RowValidation]:
        return [rv for rv in self.row_validations if not rv.passed]
    
    def print_report(self):
        """Print formatted validation report"""
        print("\n" + "=" * 80)
        print("📊 VALIDATION REPORT")
        print("=" * 80)
        
        # Summary section
        print("\n📈 SUMMARY")
        print("-" * 80)
        print(f"Expected Rows: {self.total_rows_expected}")
        print(f"Actual Rows:   {self.total_rows_actual}")
        print(f"Passed Rows:   {len(self.passed_rows)}")
        print(f"Failed Rows:   {len(self.failed_rows)}")
        print(f"\nOverall Status: {self.overall_status.value}")
        
        # Row count validation
        if self.total_rows_expected != self.total_rows_actual:
            print(f"\n⚠️  Row count mismatch!")
            print(f"   Expected {self.total_rows_expected} rows but found {self.total_rows_actual}")
        
        # Detailed results
        print("\n" + "=" * 80)
        print("📋 DETAILED RESULTS")
        print("=" * 80)
        
        for row_validation in self.row_validations:
            print(row_validation)
        
        # Failed rows summary
        if self.failed_rows:
            print("\n" + "=" * 80)
            print("❌ FAILED ROWS SUMMARY")
            print("=" * 80)
            for rv in self.failed_rows:
                print(f"\nRow {rv.row_number} ({rv.item_code}):")
                for fv in rv.failed_fields:
                    print(f"  • {fv.field_name}: Expected '{fv.expected_value}', Got '{fv.actual_value}'")
        
        # Statistics
        print("\n" + "=" * 80)
        print("📊 STATISTICS")
        print("=" * 80)
        
        total_fields = sum(len(rv.field_validations) for rv in self.row_validations)
        passed_fields = sum(sum(1 for fv in rv.field_validations if fv.passed) 
                          for rv in self.row_validations)
        failed_fields = total_fields - passed_fields
        
        print(f"Total Fields Validated: {total_fields}")
        print(f"Passed Fields:          {passed_fields}")
        print(f"Failed Fields:          {failed_fields}")
        
        if total_fields > 0:
            accuracy = (passed_fields / total_fields) * 100
            print(f"Accuracy:               {accuracy:.2f}%")
        
        print("\n" + "=" * 80)


# ======================================================
# CONFIGURATION
# ======================================================
class Config:
    EXPECTED_ROWS = [
        {'item_code': 'ITM0004', 'stock_qty': '0',  'audited_qty': '5',  'damaged_qty': '0'},
        {'item_code': 'ITM0002', 'stock_qty': '10', 'audited_qty': '10', 'damaged_qty': '5'},
        {'item_code': 'ITM0001', 'stock_qty': '30', 'audited_qty': '10', 'damaged_qty': '10'},
    ]
    
    TABLE_LOAD_TIMEOUT = 60000
    ROW_LOAD_TIMEOUT = 20000
    NETWORK_IDLE_TIMEOUT = 15000
    POLLING_INTERVAL = 1000
    MAX_POLL_ATTEMPTS = 60


# ======================================================
# UTILITY FUNCTIONS
# ======================================================
def normalize(text: str) -> str:
    """Normalize text for comparison"""
    if not text:
        return ""
    return text.replace(",", "").strip()


def compare_values(expected: str, actual: str, field_name: str) -> FieldValidation:
    """Compare expected and actual values"""
    expected_normalized = normalize(expected)
    actual_normalized = normalize(actual)
    
    if expected_normalized == actual_normalized:
        return FieldValidation(
            field_name=field_name,
            expected_value=expected,
            actual_value=actual,
            status=ValidationStatus.PASSED
        )
    else:
        return FieldValidation(
            field_name=field_name,
            expected_value=expected,
            actual_value=actual,
            status=ValidationStatus.FAILED,
            error_message=f"Value mismatch"
        )


# ======================================================
# TABLE LOCATION FUNCTIONS
# ======================================================
def try_multiple_table_selectors(page: Page) -> Optional[any]:
    """Try multiple selectors to find the table"""
    print("\n🎯 Trying multiple table selectors...")
    
    selectors = [
        ("xpath=//*[contains(text(),'Recently Audited')]/following::table[1]", "XPath - following table"),
        ("xpath=//div[contains(text(),'Recently Audited')]/following-sibling::*//table", "XPath - sibling table"),
        (".common-table table", "CSS - common-table class"),
        ("p-table table", "CSS - p-table element"),
        (".p-datatable-wrapper table", "CSS - datatable wrapper"),
        ("table >> nth=0", "First table on page"),
        ("table >> nth=1", "Second table on page"),
        ("table >> nth=2", "Third table on page"),
    ]
    
    for selector, description in selectors:
        try:
            print(f"  Trying: {description}")
            table = page.locator(selector)
            count = table.count()
            
            if count > 0:
                tbody = table.locator("tbody").first
                if tbody.count() > 0:
                    print(f"    ✅ Found table with tbody using: {description}")
                    return table.first
            else:
                print(f"    ❌ No match")
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
    
    print("  ❌ No suitable table found with any selector")
    return None


def wait_for_table_with_polling(page: Page) -> Optional[any]:
    """Poll continuously for table and rows"""
    print("\n⏳ Starting advanced polling for table and rows...")
    print(f"  Will poll every {Config.POLLING_INTERVAL}ms for up to {Config.MAX_POLL_ATTEMPTS} attempts")
    
    for attempt in range(Config.MAX_POLL_ATTEMPTS):
        try:
            if attempt % 5 == 0:
                print(f"  Attempt {attempt + 1}/{Config.MAX_POLL_ATTEMPTS}...")
            
            page.wait_for_load_state("domcontentloaded", timeout=2000)
            table = try_multiple_table_selectors(page)
            
            if table:
                rows = table.locator("tbody tr")
                row_count = rows.count()
                
                if row_count > 0:
                    print(f"\n  ✅ SUCCESS! Found table with {row_count} rows")
                    return table
                else:
                    if attempt % 10 == 0:
                        print(f"    ⏳ Table found but no rows yet (attempt {attempt + 1})")
            
            page.wait_for_timeout(Config.POLLING_INTERVAL)
            
            if attempt % 5 == 0:
                page.keyboard.press("PageDown")
                page.wait_for_timeout(500)
            
        except Exception as e:
            if attempt % 20 == 0:
                print(f"    ⚠️  Polling error at attempt {attempt + 1}: {str(e)[:100]}")
    
    print("  ❌ Polling timeout - table with rows not found")
    return None


def wait_for_table_to_load(page: Page) -> bool:
    """Comprehensive waiting strategy"""
    print("\n" + "=" * 70)
    print("⏳ WAITING FOR TABLE TO LOAD")
    print("=" * 70)
    
    try:
        # Wait for network idle
        print("\n  Step 1: Waiting for network idle...")
        try:
            page.wait_for_load_state("networkidle", timeout=Config.NETWORK_IDLE_TIMEOUT)
            print("    ✅ Network idle")
        except:
            print("    ⚠️  Network idle timeout (continuing anyway)")
        
        # Wait for DOM
        print("  Step 2: Waiting for DOM content loaded...")
        page.wait_for_load_state("domcontentloaded", timeout=5000)
        print("    ✅ DOM ready")
        
        # Extra wait for rendering
        print("  Step 3: Waiting for framework to render (5s)...")
        page.wait_for_timeout(5000)
        
        # Scroll to trigger lazy loading
        print("  Step 4: Scrolling to table area...")
        page.keyboard.press("PageDown")
        page.wait_for_timeout(2000)
        
        # Poll for table
        print("  Step 5: Starting advanced polling mechanism...")
        table = wait_for_table_with_polling(page)
        
        if table is None:
            print("\n❌ FAILED TO FIND TABLE WITH ROWS")
            
            return False
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR during table wait: {e}")
        return False


# ======================================================
# NAVIGATION
# ======================================================
def navigate_to_ongoing_audits(page: Page, audit_name: str = "Audit_PWDNZ5_1"):
    """Navigate to the audit page"""
    print("📂 Navigating to Ongoing Audits...")
    page.click("a[href='#/home/audit']")
    page.wait_for_load_state("networkidle")

    row = page.locator(
        f"table tbody tr:has(td span:has-text('{audit_name}'))"
        f":has(td:has-text('Complete Count'))"
    ).first

    row.locator("td span").first.click()
    page.locator("button.primary-button:has-text('Stock Audit')").click()
    page.wait_for_load_state("networkidle")

    print(f"✅ Opened audit: {audit_name}")


# ======================================================
# ROW EXTRACTION
# ======================================================
def extract_row_data(row, row_index: int) -> Dict[str, str]:
    """Extract data from a single row"""
    cells = row.locator("td")
    
    # Extract S.No
    try:
        s_no = cells.nth(0).inner_text(timeout=5000).strip()
    except:
        s_no = str(row_index + 1)
    
    # Extract Item Code
    try:
        item_code_cell = cells.nth(1)
        item_code = item_code_cell.locator("span").first.inner_text(timeout=5000).strip()
    except:
        try:
            item_code = cells.nth(1).inner_text(timeout=5000).strip().split('\n')[0]
        except:
            item_code = "N/A"
    
    # Extract quantities
    try:
        stock_qty = cells.nth(6).inner_text(timeout=5000).strip()
    except:
        stock_qty = "N/A"
    
    try:
        audited_qty = cells.nth(7).inner_text(timeout=5000).strip()
    except:
        audited_qty = "N/A"
    
    try:
        damaged_qty = cells.nth(8).inner_text(timeout=5000).strip()
    except:
        damaged_qty = "N/A"
    
    return {
        's_no': s_no,
        'item_code': item_code,
        'stock_qty': stock_qty,
        'audited_qty': audited_qty,
        'damaged_qty': damaged_qty
    }


# ======================================================
# VALIDATION ENGINE
# ======================================================
def validate_row_against_expected(
    actual_data: Dict[str, str],
    expected_data: Dict[str, str],
    row_number: int
) -> RowValidation:
    """Validate a single row against expected data"""
    
    field_validations = []
    
    # Validate Item Code
    field_validations.append(
        compare_values(expected_data['item_code'], actual_data['item_code'], 'Item Code')
    )
    
    # Validate Stock Qty
    field_validations.append(
        compare_values(expected_data['stock_qty'], actual_data['stock_qty'], 'Stock Qty')
    )
    
    # Validate Audited Qty
    field_validations.append(
        compare_values(expected_data['audited_qty'], actual_data['audited_qty'], 'Audited Qty')
    )
    
    # Validate Damaged Qty
    field_validations.append(
        compare_values(expected_data['damaged_qty'], actual_data['damaged_qty'], 'Damaged Qty')
    )
    
    # Determine overall row status
    all_passed = all(fv.passed for fv in field_validations)
    overall_status = ValidationStatus.PASSED if all_passed else ValidationStatus.FAILED
    
    return RowValidation(
        row_number=row_number,
        item_code=actual_data['item_code'],
        field_validations=field_validations,
        overall_status=overall_status
    )


def validate_table_comprehensive(
    page: Page,
    expected_rows: List[Dict[str, str]]
) -> ValidationReport:
    """
    Comprehensive table validation with detailed comparison
    """
    
    print("\n" + "=" * 80)
    print("🔍 COMPREHENSIVE TABLE VALIDATION")
    print("=" * 80)
    
    # Wait for table to load
    if not wait_for_table_to_load(page):
        print("❌ Failed to load table")
        return ValidationReport(
            total_rows_expected=len(expected_rows),
            total_rows_actual=0,
            row_validations=[],
            overall_status=ValidationStatus.FAILED,
            summary={'error': 'Table not found'}
        )
    
    # Locate table
    print("\n🔍 Locating table...")
    table = try_multiple_table_selectors(page)
    
    if not table:
        print("❌ Could not locate table")
        return ValidationReport(
            total_rows_expected=len(expected_rows),
            total_rows_actual=0,
            row_validations=[],
            overall_status=ValidationStatus.FAILED,
            summary={'error': 'Table selector failed'}
        )
    
    print("✅ Table located successfully")
    
    # Get all rows
    rows = table.locator("tbody tr")
    actual_row_count = rows.count()
    
    print(f"\n📊 Found {actual_row_count} rows in table")
    print(f"📊 Expected {len(expected_rows)} rows")
    
    # Extract and validate each row
    row_validations = []
    
    print("\n" + "=" * 80)
    print("📝 EXTRACTING AND VALIDATING ROWS")
    print("=" * 80)
    
    for i in range(actual_row_count):
        try:
            print(f"\nProcessing Row {i + 1}...")
            
            row = rows.nth(i)
            actual_data = extract_row_data(row, i)
            
            print(f"  Extracted: {actual_data['item_code']} | "
                  f"Stock={actual_data['stock_qty']} | "
                  f"Audited={actual_data['audited_qty']} | "
                  f"Damaged={actual_data['damaged_qty']}")
            
            # Validate against expected data if available
            if i < len(expected_rows):
                expected_data = expected_rows[i]
                print(f"  Expected:  {expected_data['item_code']} | "
                      f"Stock={expected_data['stock_qty']} | "
                      f"Audited={expected_data['audited_qty']} | "
                      f"Damaged={expected_data['damaged_qty']}")
                
                row_validation = validate_row_against_expected(
                    actual_data, expected_data, i + 1
                )
                row_validations.append(row_validation)
                
                if row_validation.passed:
                    print(f"  {ValidationStatus.PASSED.value}")
                else:
                    print(f"  {ValidationStatus.FAILED.value}")
                    for fv in row_validation.failed_fields:
                        print(f"    • {fv.field_name}: Expected '{fv.expected_value}', Got '{fv.actual_value}'")
            else:
                # Extra row not in expected data
                print(f"  {ValidationStatus.WARNING.value} Extra row (not in expected data)")
                row_validation = RowValidation(
                    row_number=i + 1,
                    item_code=actual_data['item_code'],
                    field_validations=[],
                    overall_status=ValidationStatus.WARNING,
                    error_message="Extra row not in expected data"
                )
                row_validations.append(row_validation)
            
        except Exception as e:
            print(f"  ❌ Error processing row {i + 1}: {e}")
            row_validation = RowValidation(
                row_number=i + 1,
                item_code="ERROR",
                field_validations=[],
                overall_status=ValidationStatus.FAILED,
                error_message=f"Exception: {str(e)}"
            )
            row_validations.append(row_validation)
    
    # Check for missing rows
    if actual_row_count < len(expected_rows):
        print(f"\n⚠️  Missing {len(expected_rows) - actual_row_count} expected rows")
    
    # Determine overall status
    all_passed = all(rv.passed for rv in row_validations)
    row_count_matches = actual_row_count == len(expected_rows)
    
    if all_passed and row_count_matches:
        overall_status = ValidationStatus.PASSED
    else:
        overall_status = ValidationStatus.FAILED
    
    # Create report
    report = ValidationReport(
        total_rows_expected=len(expected_rows),
        total_rows_actual=actual_row_count,
        row_validations=row_validations,
        overall_status=overall_status,
        summary={
            'passed': len([rv for rv in row_validations if rv.passed]),
            'failed': len([rv for rv in row_validations if not rv.passed]),
        }
    )
    
    return report


# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    
    print("\n" + "=" * 80)
    print("🚀 COMPREHENSIVE AUDIT TABLE VALIDATION")
    print("=" * 80 + "\n")
    
    with sync_playwright() as p:
        
        browser, page = login(
            p,
            browser_name="chrome",
            environment="QA"
        )
        
        try:
            # Navigate to audit page
            navigate_to_ongoing_audits(page)
            
            print("\n⏳ Waiting 10 seconds for page to stabilize...")
            page.wait_for_timeout(10000)
            
            
            
            # Run comprehensive validation
            validation_report = validate_table_comprehensive(
                page,
                expected_rows=Config.EXPECTED_ROWS
            )
            
            # Print detailed report
            validation_report.print_report()
            
           
            
            # Final summary
            print("\n" + "=" * 80)
            print("🎯 FINAL RESULT")
            print("=" * 80)
            print(f"Status: {validation_report.overall_status.value}")
            print(f"Passed Rows: {len(validation_report.passed_rows)}/{validation_report.total_rows_actual}")
            print(f"Failed Rows: {len(validation_report.failed_rows)}/{validation_report.total_rows_actual}")
            print("=" * 80 + "\n")
            
        except Exception as e:
            print(f"\n❌ CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            
           
        
        finally:
            input("\nPress ENTER to close browser...")
            browser.close()
    
    print("\n✅ VALIDATION COMPLETED\n")