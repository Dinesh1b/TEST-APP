"""
ENTERPRISE AUDIT VALIDATION SYSTEM
Comprehensive validation with filters, row-wise comparison, and soft assertions
"""

import sys
import os
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
from playwright.sync_api import sync_playwright, Page, Browser


# ======================================================
# PATH SETUP
# ======================================================

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login


# ======================================================
# ENUMS
# ======================================================

class VarianceType(Enum):
    """Enumeration for variance types"""
    NEGATIVE = "negative"
    POSITIVE = "positive"


class FilterType(Enum):
    """Enumeration for filter types"""
    ALL = "All"
    LINE_ITEMS_NOT_FOUND = "Line Items Not Found"
    EXCESS_LINE_ITEM = "Excess Line Item"
    NEGATIVE_VARIANCE = "Negative Variance"
    POSITIVE_VARIANCE = "Positive Variance"


# ======================================================
# CONFIG
# ======================================================

@dataclass
class Config:
    """Configuration settings for the validation system"""
    DEFAULT_TIMEOUT: int = 20000
    SCROLL_WAIT_MS: int = 600
    SHOW_BROWSER_AFTER_TEST: bool = True
    TABLE_SCROLL_CONTAINER_XPATH: str = "/html/body/app-root/app-layout/div/app-audit-summary/div/div[4]/div[6]/div/div[2]"
    TABLE_BODY_SELECTOR: str = "tbody.p-datatable-tbody"
    TABLE_ROW_SELECTOR: str = "tbody.p-datatable-tbody > tr"


# ======================================================
# COLUMN MAPPING
# ======================================================

@dataclass
class ColumnMapping:
    """Mapping of column names to their indices in the table"""
    ITEM_CODE: int = 1
    ITEM_NAME: int = 2
    CATEGORY: int = 4
    STOCK_QUANTITY: int = 5
    AUDITED_QTY: int = 6
    VARIANCE: int = 7
    VARIANCE_VALUE: int = 8
    VARIANCE_TYPE: int = 9
    DAMAGED_QTY: int = 10
    CROSS_AUDITED_QTY: int = 14
    CROSS_DAMAGED_QTY: int = 15

    @classmethod
    def get_field_mapping(cls) -> Dict[str, int]:
        """Returns a dictionary mapping field names to column indices"""
        return {
            "Item Code": cls.ITEM_CODE,
            "Item Name": cls.ITEM_NAME,
            "Category": cls.CATEGORY,
            "Stock Quantity": cls.STOCK_QUANTITY,
            "Audited Qty": cls.AUDITED_QTY,
            "Variance": cls.VARIANCE,
            "Variance Value": cls.VARIANCE_VALUE,
            "Variance Type": cls.VARIANCE_TYPE,
            "Damaged Qty": cls.DAMAGED_QTY,
            "Cross AuditedQty": cls.CROSS_AUDITED_QTY,
            "Cross DamagedQty": cls.CROSS_DAMAGED_QTY,
        }


# ======================================================
# UTILITY FUNCTIONS
# ======================================================

def to_int(value: str) -> int:
    """
    Convert string to integer, handling commas and whitespace
    
    Args:
        value: String value to convert
        
    Returns:
        Integer value, or 0 if conversion fails
    """
    if not value:
        return 0
    try:
        return int(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0


# ======================================================
# DATA NORMALIZER
# ======================================================

class DataNormalizer:
    """Handles data normalization for consistent comparisons"""

    @staticmethod
    def normalize(value: str) -> str:
        """
        Normalize a value by removing commas, extra whitespace, and converting to lowercase
        
        Args:
            value: Value to normalize
            
        Returns:
            Normalized string
        """
        if value is None:
            return ""
        return " ".join(str(value).replace(",", "").strip().lower().split())


# ======================================================
# DATA EXTRACTION
# ======================================================

class DataExtractor:
    """Handles extraction of data from table rows"""

    def __init__(self, column_mapping: ColumnMapping):
        """
        Initialize the data extractor
        
        Args:
            column_mapping: Column mapping configuration
        """
        self.column_mapping = column_mapping
        self.field_indices = column_mapping.get_field_mapping()

    def extract_row(self, row) -> Dict[str, str]:
        """
        Extract data from a single table row
        
        Args:
            row: Playwright locator for the row
            
        Returns:
            Dictionary containing extracted field values
        """
        cells = row.locator("td")
        data = {}

        for field, idx in self.field_indices.items():
            try:
                cell_text = cells.nth(idx).inner_text()
                data[field] = DataNormalizer.normalize(cell_text)
            except Exception as e:
                print(f"⚠️  Warning: Failed to extract '{field}' at index {idx}: {e}")
                data[field] = ""

        return data

    def collect_rows(self, page: Page, config: Config) -> List[Dict[str, str]]:
        """
        Collect all rows from the scrollable table
        
        Args:
            page: Playwright page object
            config: Configuration settings
            
        Returns:
            List of dictionaries containing row data
        """
        all_rows = []
        seen_codes: Set[str] = set()
        previous_count = -1

        scroll_container = page.locator(f"xpath={config.TABLE_SCROLL_CONTAINER_XPATH}")

        print("📊 Collecting table rows...")

        while True:
            rows = scroll_container.locator(config.TABLE_ROW_SELECTOR)
            count = rows.count()

            # Check if we've reached the end
            if count == previous_count:
                break

            previous_count = count

            # Extract new rows
            for i in range(count):
                row = rows.nth(i)
                data = self.extract_row(row)
                code = data.get("Item Code")

                if code and code not in seen_codes:
                    seen_codes.add(code)
                    all_rows.append(data)

            # Scroll to bottom
            scroll_container.evaluate("el => el.scrollTop = el.scrollHeight")
            page.wait_for_timeout(config.SCROLL_WAIT_MS)

        print(f"✓ Collected {len(all_rows)} unique rows")
        return all_rows


# ======================================================
# BUSINESS RULES ENGINE
# ======================================================

class BusinessRulesEngine:
    """Validates business rules for different filter types"""

    @staticmethod
    def validate_line_items_not_found(row: Dict[str, str]) -> bool:
        """
        Validate: Stock > 0, Audited = 0, Variance < 0
        
        Args:
            row: Row data dictionary
            
        Returns:
            True if rule is satisfied, False otherwise
        """
        stock = to_int(row["Stock Quantity"])
        audited = to_int(row["Audited Qty"])
        variance = to_int(row["Variance"])
        return stock > 0 and audited == 0 and variance < 0

    @staticmethod
    def validate_excess_line_item(row: Dict[str, str]) -> bool:
        """
        Validate: Stock = 0, Audited > 0, Variance > 0
        
        Args:
            row: Row data dictionary
            
        Returns:
            True if rule is satisfied, False otherwise
        """
        stock = to_int(row["Stock Quantity"])
        audited = to_int(row["Audited Qty"])
        variance = to_int(row["Variance"])
        return stock == 0 and audited > 0 and variance > 0

    @staticmethod
    def validate_negative_variance(row: Dict[str, str]) -> bool:
        """
        Validate: Variance < 0
        
        Args:
            row: Row data dictionary
            
        Returns:
            True if rule is satisfied, False otherwise
        """
        variance = to_int(row["Variance"])
        return variance < 0

    @staticmethod
    def validate_positive_variance(row: Dict[str, str]) -> bool:
        """
        Validate: Variance > 0
        
        Args:
            row: Row data dictionary
            
        Returns:
            True if rule is satisfied, False otherwise
        """
        variance = to_int(row["Variance"])
        return variance > 0

    def apply_business_rule(self, filter_name: str, row: Dict[str, str]) -> Optional[str]:
        """
        Apply the appropriate business rule based on filter type
        
        Args:
            filter_name: Name of the filter
            row: Row data dictionary
            
        Returns:
            Error message if validation fails, None otherwise
        """
        validators = {
            FilterType.LINE_ITEMS_NOT_FOUND.value: self.validate_line_items_not_found,
            FilterType.EXCESS_LINE_ITEM.value: self.validate_excess_line_item,
            FilterType.NEGATIVE_VARIANCE.value: self.validate_negative_variance,
            FilterType.POSITIVE_VARIANCE.value: self.validate_positive_variance,
        }

        validator = validators.get(filter_name)
        if validator and not validator(row):
            return f"{filter_name}: Business rule failed (Item {row['Item Code']})"
        
        return None


# ======================================================
# VALIDATION ENGINE
# ======================================================

class ValidationEngine:
    """Main validation engine for audit data"""

    def __init__(self, config: Config):
        """
        Initialize the validation engine
        
        Args:
            config: Configuration settings
        """
        self.config = config
        self.failures: List[str] = []
        self.business_rules = BusinessRulesEngine()

    def add_failure(self, message: str) -> None:
        """
        Add a failure message to the list
        
        Args:
            message: Failure message
        """
        self.failures.append(message)
        print(f"  ❌ {message}")

    def validate_variance_type(
        self,
        row: Dict[str, str],
        expected_type: str,
        filter_name: str
    ) -> None:
        """
        Validate that the variance type matches expected value
        
        Args:
            row: Row data dictionary
            expected_type: Expected variance type
            filter_name: Name of the filter being validated
        """
        actual_type = row["Variance Type"].lower()
        expected_type_lower = expected_type.lower()
        
        if actual_type != expected_type_lower:
            self.add_failure(
                f"{filter_name}: Variance type mismatch "
                f"(Item {row['Item Code']}, Expected: {expected_type}, Actual: {row['Variance Type']})"
            )

    def validate_rows_against_expected(
        self,
        actual_rows: List[Dict[str, str]],
        expected_rows: List[Dict[str, str]],
        filter_name: str
    ) -> None:
        """
        Validate actual rows against expected rows
        
        Args:
            actual_rows: List of actual row data
            expected_rows: List of expected row data
            filter_name: Name of the filter being validated
        """
        # Create lookup maps
        actual_map = {
            DataNormalizer.normalize(r["Item Code"]): r
            for r in actual_rows
        }

        expected_map = {
            DataNormalizer.normalize(r["Item Code"]): r
            for r in expected_rows
        }

        # Check for missing and mismatched rows
        for exp_code, exp_row in expected_map.items():
            if exp_code not in actual_map:
                self.add_failure(
                    f"{filter_name}: Missing row {exp_row['Item Code']}"
                )
                continue

            act_row = actual_map[exp_code]

            # Compare each field
            for field, exp_value in exp_row.items():
                act_value = act_row.get(field, "")
                exp_normalized = DataNormalizer.normalize(exp_value)

                if exp_normalized != act_value:
                    self.add_failure(
                        f"{filter_name}: Mismatch - "
                        f"Item {exp_row['Item Code']}, "
                        f"Field '{field}', "
                        f"Expected='{exp_value}', "
                        f"Actual='{act_value}'"
                    )

        # Check for unexpected rows
        for act_code, act_row in actual_map.items():
            if act_code not in expected_map:
                self.add_failure(
                    f"{filter_name}: Unexpected row {act_row['Item Code']}"
                )

    def validate_filter(
        self,
        page: Page,
        filter_name: str,
        expected_type: Optional[str],
        expected_rows: Optional[List[Dict[str, str]]] = None
    ) -> None:
        """
        Validate a specific filter
        
        Args:
            page: Playwright page object
            filter_name: Name of the filter to validate
            expected_type: Expected variance type for this filter
            expected_rows: Expected row data for comparison
        """
        print(f"\n{'='*60}")
        print(f"🔍 Validating Filter: {filter_name}")
        print(f"{'='*60}")

        # Click on the filter badge
        badge = page.locator(f"span.badge:has-text('{filter_name}')")

        if badge.count() == 0:
            self.add_failure(f"Filter not found: {filter_name}")
            return

        badge.click()
        page.wait_for_timeout(1000)
        wait_for_table(page, self.config)

        # Extract data
        extractor = DataExtractor(ColumnMapping())
        actual_rows = extractor.collect_rows(page, self.config)

        # Validate each row
        for row in actual_rows:
            # Apply business rules (skip for "All" filter)
            if filter_name != FilterType.ALL.value:
                error = self.business_rules.apply_business_rule(filter_name, row)
                if error:
                    self.add_failure(error)

            # Validate variance type
            if expected_type:
                self.validate_variance_type(row, expected_type, filter_name)

        # Compare against expected rows
        if expected_rows is not None:
            print(f"\n📋 Comparing {len(actual_rows)} actual rows against {len(expected_rows)} expected rows...")
            self.validate_rows_against_expected(
                actual_rows,
                expected_rows,
                filter_name
            )

        print(f"\n✓ Filter '{filter_name}' validation complete")

    def print_summary(self) -> None:
        """Print validation summary and raise exception if failures exist"""
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)

        if self.failures:
            print(f"\n❌ VALIDATION FAILED - {len(self.failures)} issue(s) found:\n")
            for idx, failure in enumerate(self.failures, 1):
                print(f"{idx}. {failure}")
            print("\n" + "="*60)
            raise AssertionError(f"Validation failed with {len(self.failures)} issue(s)")
        else:
            print("\n✅ ALL VALIDATIONS PASSED")
            print(f"✓ All filters validated successfully")
            print("="*60)


# ======================================================
# PAGE HELPERS
# ======================================================

def wait_for_table(page: Page, config: Config) -> None:
    """
    Wait for the table to be visible
    
    Args:
        page: Playwright page object
        config: Configuration settings
    """
    page.wait_for_selector(
        config.TABLE_BODY_SELECTOR,
        timeout=config.DEFAULT_TIMEOUT
    )


def navigate_open_audit(page: Page, audit_name: str) -> None:
    """
    Navigate to and open a specific audit
    
    Args:
        page: Playwright page object
        audit_name: Name of the audit to open
    """
    print(f"\n🔍 Navigating to audit: {audit_name}")
    
    page.click("a[href='#/home/audit']")
    page.wait_for_load_state("networkidle")

    row = page.locator(
        f"table tbody tr:has(td span:has-text('{audit_name}'))"
        f":has(td:has-text('Complete Count'))"
    ).first

    row.locator("td span").first.click()
    print(f"✓ Opened audit: {audit_name}")


# ======================================================
# TEST DATA BUILDER
# ======================================================

class TestDataBuilder:
    """Builds expected test data sets"""

    @staticmethod
    def build_expected_all() -> List[Dict[str, str]]:
        """Build expected data for 'All' filter"""
        return [
            {
                "Item Code": "ITM0001",
                "Item Name": "Item 001",
                "Category": "GMA",
                "Stock Quantity": "30",
                "Audited Qty": "0",
                "Variance": "-30",
                "Variance Value": "-3,000.00",
                "Variance Type": "Negative",
                "Damaged Qty": "0",
                "Cross AuditedQty": "0",
                "Cross DamagedQty": "1"
            },
            {
                "Item Code": "ITM0002",
                "Item Name": "Item 002",
                "Category": "Gear",
                "Stock Quantity": "10",
                "Audited Qty": "0",
                "Variance": "-10",
                "Variance Value": "-1,000.00",
                "Variance Type": "Negative",
                "Damaged Qty": "0",
                "Cross AuditedQty": "0",
                "Cross DamagedQty": "0"
            },
            {
                "Item Code": "ITM0003",
                "Item Name": "Item 003",
                "Category": "Parts",
                "Stock Quantity": "10",
                "Audited Qty": "0",
                "Variance": "-10",
                "Variance Value": "-1,000.00",
                "Variance Type": "Negative",
                "Damaged Qty": "0",
                "Cross AuditedQty": "0",
                "Cross DamagedQty": "0"
            },
            {
                "Item Code": "item0011",
                "Item Name": "item0011",
                "Category": "Gear",
                "Stock Quantity": "0",
                "Audited Qty": "10",
                "Variance": "10",
                "Variance Value": "1,000.00",
                "Variance Type": "Positive",
                "Damaged Qty": "0",
                "Cross AuditedQty": "0",
                "Cross DamagedQty": "0"
            }
        ]

    @staticmethod
    def filter_line_items_not_found(data: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Filter data for 'Line Items Not Found'"""
        return [
            r for r in data
            if to_int(r["Stock Quantity"]) > 0 and to_int(r["Audited Qty"]) == 0
        ]

    @staticmethod
    def filter_excess_line_item(data: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Filter data for 'Excess Line Item'"""
        return [
            r for r in data
            if to_int(r["Stock Quantity"]) == 0 and to_int(r["Audited Qty"]) > 0
        ]

    @staticmethod
    def filter_negative_variance(data: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Filter data for 'Negative Variance'"""
        return [
            r for r in data
            if to_int(r["Variance"]) < 0
        ]

    @staticmethod
    def filter_positive_variance(data: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Filter data for 'Positive Variance'"""
        return [
            r for r in data
            if to_int(r["Variance"]) > 0
        ]


# ======================================================
# MAIN EXECUTION
# ======================================================

def main():
    """Main execution function"""
    
    print("\n" + "="*60)
    print("ENTERPRISE AUDIT VALIDATION SYSTEM")
    print("="*60)
    
    # Initialize configuration
    config = Config()

    # Build expected data
    print("\n📦 Building expected test data...")
    builder = TestDataBuilder()
    expected_all = builder.build_expected_all()
    
    expected_line_items_not_found = builder.filter_line_items_not_found(expected_all)
    expected_excess_line_item = builder.filter_excess_line_item(expected_all)
    expected_negative = builder.filter_negative_variance(expected_all)
    expected_positive = builder.filter_positive_variance(expected_all)

    print(f"✓ Expected 'All': {len(expected_all)} rows")
    print(f"✓ Expected 'Line Items Not Found': {len(expected_line_items_not_found)} rows")
    print(f"✓ Expected 'Excess Line Item': {len(expected_excess_line_item)} rows")
    print(f"✓ Expected 'Negative Variance': {len(expected_negative)} rows")
    print(f"✓ Expected 'Positive Variance': {len(expected_positive)} rows")

    # Define filters to validate
    filters: List[Tuple[str, Optional[str], List[Dict[str, str]]]] = [
        (FilterType.ALL.value, None, expected_all),
        (FilterType.LINE_ITEMS_NOT_FOUND.value, VarianceType.NEGATIVE.value, expected_line_items_not_found),
        (FilterType.EXCESS_LINE_ITEM.value, VarianceType.POSITIVE.value, expected_excess_line_item),
        (FilterType.POSITIVE_VARIANCE.value, VarianceType.POSITIVE.value, expected_positive),
        (FilterType.NEGATIVE_VARIANCE.value, VarianceType.NEGATIVE.value, expected_negative),
    ]

    # Execute validation
    with sync_playwright() as p:
        print("\n🌐 Launching browser...")
        
        browser, page = login(
            p,
            browser_name="chrome",
            environment="production"
        )

        page.wait_for_timeout(3000)

        # Navigate to audit
        navigate_open_audit(page, "bullet12222_2")

        # Initialize validation engine
        engine = ValidationEngine(config)

        # Validate each filter
        for filter_name, expected_type, expected_rows in filters:
            try:
                engine.validate_filter(
                    page,
                    filter_name,
                    expected_type,
                    expected_rows
                )
            except Exception as e:
                engine.add_failure(f"Exception during '{filter_name}' validation: {str(e)}")

        # Print summary
        engine.print_summary()

        # Keep browser open if configured
        if config.SHOW_BROWSER_AFTER_TEST:
            print("\n⏸️  Browser will remain open for inspection")
            input("Press ENTER to close browser...")

        browser.close()
        print("\n✓ Browser closed")


# ======================================================
# ENTRY POINT
# ======================================================

if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"\n💥 Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)