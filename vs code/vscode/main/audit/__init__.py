# ============================================================================
# config/settings.py
# ============================================================================
"""
Centralized configuration management.
Single source of truth for all settings.
"""

from dataclasses import dataclass
from typing import Optional
from pathlib import Path


@dataclass
class BrowserConfig:
    """Browser configuration."""
    name: str = "chrome"
    headless: bool = False
    timeout: int = 15000  # milliseconds
    slow_mo: int = 0  # milliseconds
    proxy: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class TestConfig:
    """Test execution configuration."""
    dry_run: bool = False
    seed: Optional[int] = None
    fast_mode: bool = False
    enable_reporting: bool = True
    screenshot_on_failure: bool = True
    
    @property
    def sleep_time(self) -> float:
        """Get sleep time based on mode."""
        return 0.10 if self.fast_mode else 1.0


@dataclass
class PathConfig:
    """Path configuration."""
    excel_file: str = r"C:\Users\HP\Documents\input\QAudit.xlsx"
    reports_dir: str = "reports"
    logs_dir: str = "logs"
    screenshots_dir: str = "screenshots"
    
    def __post_init__(self):
        """Create directories if they don't exist."""
        Path(self.reports_dir).mkdir(exist_ok=True)
        Path(self.logs_dir).mkdir(exist_ok=True)
        Path(self.screenshots_dir).mkdir(exist_ok=True)


class Settings:
    """Global settings singleton."""
    
    # Configuration instances
    browser = BrowserConfig()
    test = TestConfig()
    paths = PathConfig()
    
    # Login credentials (use environment variables in production)
    LOGIN_USER = "test_user"
    LOGIN_PASSWORD = "test_password"
    LOGIN_ENVIRONMENT = "QA"
    LOGIN_URL = "https://app.example.com/login"
    
    # Default timeouts (milliseconds)
    TIMEOUT_ELEMENT = 15000
    TIMEOUT_NETWORK = 30000
    TIMEOUT_PAGE_LOAD = 30000
    
    # Feature flags
    USE_HEADLESS = False
    ENABLE_VIDEO_RECORDING = False
    ENABLE_TRACE = False
    
    @classmethod
    def configure_for_ci(cls):
        """Configure settings for CI/CD environment."""
        cls.browser.headless = True
        cls.test.fast_mode = True
        cls.test.enable_reporting = True
    
    @classmethod
    def configure_for_debug(cls):
        """Configure settings for debugging."""
        cls.browser.headless = False
        cls.test.fast_mode = False
        cls.test.screenshot_on_failure = True


# ============================================================================
# selectors/common_selectors.py
# ============================================================================
"""
Common selectors used across all pages.
Centralized to avoid hardcoding in tests.
"""


class CommonSelectors:
    """Common selectors used throughout the application."""
    
    # Navigation
    HOME = "a[href='#/home']"
    LOGOUT = "button:has-text('Logout')"
    SIDEBAR_MENU = "nav.sidebar"
    
    # Overlays & Dialogs
    DIALOG_MASK = ".p-dialog-mask"
    OVERLAY_BACKDROP = ".cdk-overlay-backdrop"
    LOADING_SPINNER = ".p-progress-spinner"
    
    # Common buttons
    OK_BTN = "button:has-text('OK')"
    CANCEL_BTN = "button:has-text('Cancel')"
    SAVE_BTN = "button:has-text('Save')"
    NEXT_BTN = "button:has-text('Next')"
    BACK_BTN = "button:has-text('Back')"
    CLOSE_BTN = "button[aria-label='Close']"
    
    # Common inputs
    TEXT_INPUT = "input[type='text']"
    PASSWORD_INPUT = "input[type='password']"
    EMAIL_INPUT = "input[type='email']"
    NUMBER_INPUT = "input[type='number']"
    
    # Notifications
    SUCCESS_TOAST = ".p-toast-message.p-toast-message-success"
    ERROR_TOAST = ".p-toast-message.p-toast-message-error"
    WARNING_TOAST = ".p-toast-message.p-toast-message-warn"
    
    # Tables
    DATA_TABLE = "p-table"
    TABLE_ROW = "tr"
    TABLE_CELL = "td"
    
    # Dropdowns (PrimeNG)
    DROPDOWN_PANEL = "div.p-dropdown-panel"
    DROPDOWN_ITEM = "li.p-dropdown-item"
    DROPDOWN_FILTER = "input.p-dropdown-filter"
    
    # MultiSelect (PrimeNG)
    MULTISELECT_PANEL = "div.p-multiselect-panel"
    MULTISELECT_ITEM = "li.p-multiselect-item"
    MULTISELECT_TRIGGER = "div.p-multiselect-trigger"
    
    # Calendar (PrimeNG)
    CALENDAR_PANEL = "div.p-datepicker"
    CALENDAR_DATE = "td[role='gridcell']"
    
    # Forms
    FORM_ERROR = ".ng-invalid.ng-touched"
    REQUIRED_FIELD = ".p-error"
    
    @staticmethod
    def get_by_text(text: str) -> str:
        """Get selector for element containing text."""
        return f"text={text}"
    
    @staticmethod
    def get_by_placeholder(placeholder: str) -> str:
        """Get selector for input with placeholder."""
        return f"input[placeholder='{placeholder}']"
    
    @staticmethod
    def get_by_aria_label(label: str) -> str:
        """Get selector for element with aria-label."""
        return f"[aria-label='{label}']"


# ============================================================================
# selectors/audit_selectors.py
# ============================================================================
"""
Audit-specific selectors.
Organized by functional area.
"""


class AuditSelectors:
    """All audit-related CSS selectors."""
    
    # ========== NAVIGATION ==========
    AUDIT_PAGE = "a[href='#/home/audit']"
    CREATE_AUDIT_BTN = "button.createAuditBtn"
    AUDIT_PLAN_BTN = "button[label='Audit Plan']"
    ADD_AUDIT_PLAN_BTN = "button:has-text('Add Audit Plan')"
    
    # ========== BASIC INFO SECTION ==========
    AUDIT_OWNER_DROPDOWN = "p-dropdown[formcontrolname='auditOwner']"
    AUDIT_OWNER_TRIGGER = "p-dropdown[formcontrolname='auditOwner'] div.p-dropdown-trigger"
    
    ROLE_DROPDOWN_CONTAINER = "div#role"
    ROLE_DROPDOWN_TRIGGER = "div#role .p-dropdown-trigger"
    ROLE_OPTION_TEMPLATE = "div#role_list li.p-dropdown-item"
    
    AUDIT_NAME_INPUT = "input#name"
    AUDIT_NAME_LABEL = "label[for='name']"
    
    # ========== AUDIT TYPE SECTION ==========
    AUDIT_TYPE_RADIO_TEMPLATE = "p-radiobutton[value='{value}'] .p-radiobutton-box"
    AUDIT_TYPE_COMPLETE_COUNT = "p-radiobutton[value='Complete Count'] .p-radiobutton-box"
    AUDIT_TYPE_CYCLE_COUNT = "p-radiobutton[value='Cycle Count'] .p-radiobutton-box"
    
    # ========== FREQUENCY SECTION ==========
    FREQUENCY_DROPDOWN = "p-dropdown[formcontrolname='frequency']"
    FREQUENCY_DROPDOWN_TRIGGER = "p-dropdown[formcontrolname='frequency'] div.p-dropdown-trigger"
    FREQUENCY_DROPDOWN_PANEL = "div.p-dropdown-panel:visible"
    FREQUENCY_DROPDOWN_ITEM_TEMPLATE = "li.p-dropdown-item:has-text('{frequency}')"
    
    # Date fields for frequency
    FREQUENCY_DATE_PICKER = "p-calendar[formcontrolname='frequencyDate']"
    FREQUENCY_DATE_INPUT = "p-calendar[formcontrolname='frequencyDate'] input"
    
    START_DATE_PICKER = "p-calendar[formcontrolname='startDateTime']"
    START_DATE_BTN = "p-calendar[formcontrolname='startDateTime'] button[aria-label='Choose Date']"
    END_DATE_PICKER = "p-calendar[formcontrolname='endDateTime']"
    END_DATE_BTN = "p-calendar[formcontrolname='endDateTime'] button[aria-label='Choose Date']"
    
    CALENDAR_POPUP = "div.p-datepicker[role='dialog']"
    CALENDAR_DATE_TEMPLATE = "td[aria-label='{day}']:not(.p-disabled) span"
    
    # ========== AUDITOR SELECTION ==========
    AUDITOR_MULTISELECT = "div.p-multiselect-trigger"
    AUDITOR_PANEL = "div.p-multiselect-panel"
    AUDITOR_ITEM_TEMPLATE = "li.p-multiselect-item:has-text('{name}')"
    
    # ========== AUDIT OPTIONS ==========
    DAMAGE_QTY_CHECKBOX = "[formcontrolname='isDamageQty']"
    STOCK_ITEMS_CHECKBOX = "[formcontrolname='isStockItems']"
    PHOTO_VALIDATION_CHECKBOX = "[formcontrolname='isPhotoValidation']"
    GEO_TAGGING_CHECKBOX = "[formcontrolname='isGeoTagging']"
    
    DAMAGE_QTY_LABEL = "label:has-text('Damage Quantity')"
    STOCK_ITEMS_LABEL = "label:has-text('Stock Items')"
    PHOTO_VALIDATION_LABEL = "label:has-text('Photo Validation')"
    GEO_TAGGING_LABEL = "label:has-text('Geo Tagging')"
    
    # ========== CROSS AUDIT SECTION ==========
    CROSS_AUDIT_RADIO_TEMPLATE = "p-radiobutton[value='{value}'] .p-radiobutton-box"
    CROSS_AUDIT_NONE = "p-radiobutton[value=''] .p-radiobutton-box"
    CROSS_AUDIT_RANDOM = "p-radiobutton[value='Random'] .p-radiobutton-box"
    CROSS_AUDIT_DISCREPANCY = "p-radiobutton[value='Discrepancy'] .p-radiobutton-box"
    
    CROSS_CHECK_SIZE_INPUT = "[formcontrolname='crossCheckSize']"
    CROSS_AUDITOR_DROPDOWN = "p-dropdown[formcontrolname='crossAuditor']"
    CROSS_AUDITOR_TRIGGER = "p-dropdown[formcontrolname='crossAuditor'] div.p-dropdown-trigger"
    
    # ========== FORM BUTTONS ==========
    NEXT_BTN = "button:has-text('Next')"
    SAVE_BTN = "button.primary-button:has-text('Save')"
    BACK_BTN = "button:has-text('Back')"
    
    # ========== HELPER METHODS ==========
    @staticmethod
    def get_audit_type_radio(audit_type: str) -> str:
        """Get selector for audit type radio button."""
        return f"p-radiobutton[value='{audit_type}'] .p-radiobutton-box"
    
    @staticmethod
    def get_cross_audit_radio(cross_type: str) -> str:
        """Get selector for cross audit type radio button."""
        value_map = {
            "None": "",
            "Random Recheck": "Random",
            "Discrepancy Recheck": "Discrepancy"
        }
        value = value_map.get(cross_type, cross_type)
        return f"p-radiobutton[value='{value}'] .p-radiobutton-box"


# ============================================================================
# actions/dropdown_actions.py
# ============================================================================
"""
Smart dropdown selection with fallback strategies.
Handles PrimeNG dropdowns robustly.
"""

import difflib
from typing import Tuple, List, Optional
from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError
import time


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    return (text or "").strip().lower()


def smart_select_dropdown(page: Page, dropdown_locator: Locator, 
                          value: str, timeout: int = 7000) -> Tuple[bool, str]:
    """
    Intelligently select from dropdown with multiple fallback strategies.
    
    Strategies (in order):
    1. Exact match
    2. Case-insensitive match
    3. Fuzzy match (>60% similarity)
    4. Page-wide search
    
    Args:
        page: Playwright page
        dropdown_locator: Locator for dropdown element
        value: Value to select
        timeout: Max wait time in ms
    
    Returns:
        (success: bool, method: str)
        method values: "exact", "case_insensitive", "fuzzy", "not_found", "error"
    """
    
    try:
        # Wait for overlay to disappear
        _wait_for_overlay_gone(page)
        
        # Open dropdown
        dropdown_locator.click(force=True)
        time.sleep(0.1)
        
        # Wait for panel
        try:
            page.wait_for_selector("div.p-dropdown-panel:visible", timeout=timeout)
        except PlaywrightTimeoutError:
            return False, "panel_not_found"
        
        panel = page.locator("div.p-dropdown-panel:visible").first
        
        # Get all options
        try:
            options = panel.locator("li.p-dropdown-item").all_inner_texts()
        except:
            return False, "no_options_found"
        
        if not options:
            return False, "empty_list"
        
        # Strategy 1: Exact match
        if value in options:
            panel.locator(f"li.p-dropdown-item:has-text('{value}')").first.click()
            return True, "exact"
        
        # Strategy 2: Case-insensitive
        lower_map = {opt.lower(): opt for opt in options}
        if value.lower() in lower_map:
            match = lower_map[value.lower()]
            panel.locator(f"li.p-dropdown-item:has-text('{match}')").first.click()
            return True, "case_insensitive"
        
        # Strategy 3: Fuzzy matching
        fuzzy_matches = difflib.get_close_matches(value, options, n=1, cutoff=0.6)
        if fuzzy_matches:
            match = fuzzy_matches[0]
            panel.locator(f"li.p-dropdown-item:has-text('{match}')").first.click()
            return True, "fuzzy"
        
        # Close dropdown
        page.mouse.click(0, 0)
        time.sleep(0.1)
        
        return False, "not_found"
    
    except Exception as e:
        try:
            page.mouse.click(0, 0)
        except:
            pass
        return False, f"exception: {str(e)}"


def select_radio_button(page: Page, value: str) -> bool:
    """
    Select radio button by value attribute.
    
    Args:
        page: Playwright page
        value: Value attribute of radio button
    
    Returns:
        bool: True if successful
    """
    try:
        radio = page.locator(f"p-radiobutton[value='{value}']")
        
        if radio.count() == 0:
            return False
        
        radio_box = radio.locator(".p-radiobutton-box")
        radio_box.scroll_into_view_if_needed()
        time.sleep(0.2)
        
        # Check if already selected
        class_attr = radio_box.get_attribute("class") or ""
        if "p-highlight" not in class_attr:
            radio_box.click()
            time.sleep(0.3)
        
        return True
    
    except Exception:
        return False


def select_multiselect(page: Page, panel_selector: str, 
                       options: List[str]) -> bool:
    """
    Select multiple options from multiselect dropdown.
    
    Args:
        page: Playwright page
        panel_selector: Selector for multiselect panel
        options: List of option names to select
    
    Returns:
        bool: True if all options selected successfully
    """
    
    try:
        # Open dropdown
        trigger = page.locator("div.p-multiselect-trigger").first
        trigger.click()
        time.sleep(0.2)
        
        panel = page.locator(panel_selector)
        panel.wait_for(state="visible")
        time.sleep(0.2)
        
        # Select each option
        for option_name in options:
            option = panel.locator("li.p-multiselect-item", has_text=option_name)
            
            if option.count() == 0:
                return False
            
            option.first.scroll_into_view_if_needed()
            option.first.click()
            time.sleep(0.2)
        
        # Close dropdown
        page.keyboard.press("Escape")
        time.sleep(0.2)
        
        return True
    
    except Exception:
        return False


def _wait_for_overlay_gone(page: Page) -> None:
    """Wait for overlay/dialog to disappear."""
    overlays = [
        ".p-dialog-mask",
        ".p-component-overlay",
        ".cdk-overlay-backdrop",
        ".modal-backdrop"
    ]
    
    for selector in overlays:
        try:
            page.wait_for_selector(selector, state="detached", timeout=2000)
        except PlaywrightTimeoutError:
            pass