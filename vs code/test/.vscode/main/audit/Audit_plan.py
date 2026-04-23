
"""
Complete Playwright Automation Script with Enhanced Reporting
- Fixed all duplicate function definitions
- Completed header mapping logic
- Configured file paths properly
- Improved error handling
- Better variable scoping
- Fixed file upload redundancy
- Fixed audit flow issues
- Full reporting integration with HTML/PDF generation
"""

import sys
import os
import time
import random
import string
import difflib
import pandas as pd
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError,expect
import pandas as pd
import logging
import sys

    
# ======================================================
# CONFIG
# ======================================================
DRY_RUN = False
SEED = None
FAST_MODE = False  # Set True for fast mode (0.10s sleeps), False for default (1s)
ENABLE_REPORTING = True  # Set True to generate HTML/PDF reports

# File paths configuration
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

                   
if SEED is not None:
            random.seed(SEED)

# ======================================================
# PATH SETUP
# ======================================================
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# ======================================================
# CONSTANTS
# ======================================================
SLEEP_TIME = 0.10 if FAST_MODE else 1.0


logging.basicConfig(
    level=logging.INFO,
    format="  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),   # console output
          # file output
    ]
)
log = logging.getLogger(__name__)

def select_prime_dropdown(page, value_text=None, aria_controls=None, xpath=None):
    # âœ… Open dropdown â€” XPath > aria_controls > generic fallback
    if xpath:
        dropdown = page.locator(f"xpath={xpath}")
    elif aria_controls:
        dropdown = page.locator(f"[aria-controls='{aria_controls}']").locator("..")
    else:
        dropdown = page.locator(".p-dropdown")

    safe_click(dropdown)

    # âœ… No value_text = just open, don't select anything
    if not value_text:
        log.info("â„¹ï¸  No value_text provided â€” dropdown opened only.")
        return

    # âœ… Scope options list
    if aria_controls:
        options_locator = page.locator(f"#{aria_controls} li.p-dropdown-item")
    else:
        options_locator = page.locator("li.p-dropdown-item")

    options_locator.first.wait_for(state="visible", timeout=5000)
    all_options = options_locator.all_inner_texts()

    # âœ… Tier 1: Exact match
    if value_text in all_options:
        matched = value_text

    # âœ… Tier 2: Substring match
    elif any(value_text.lower() in o.lower() for o in all_options):
        matched = next(o for o in all_options if value_text.lower() in o.lower())
        log.info(f"âš ï¸  Partial match: '{value_text}' â†’ '{matched}'")

    # âœ… Tier 3: Fuzzy match
    else:
        matches = difflib.get_close_matches(value_text, all_options, n=1, cutoff=0.4)
        if matches:
            matched = matches[0]
            log.info(f"âš ï¸  Fuzzy match: '{value_text}' â†’ '{matched}'")
        else:
            log.info(f"âŒ No match found for '{value_text}'. Available: {all_options}")
            return

    option = page.locator(f"li.p-dropdown-item:has-text('{matched}')")
    safe_click(option)


def choose_frequency(page, frequency_type, reporter=None):
    """
    frequency_type:
    'Manual'
    'One-Time'
    'Daily'
    'Weekly'
    'Monthly'
    """

    try:
        if reporter:
            step_start = time.time()

        log.info(f"âž¡ï¸ Choose Frequency: {frequency_type}")

        safe_click(page.get_by_role("combobox", name="Choose Frequency"))
        wait2(page)

        safe_click(
            page.locator(
                f"li.p-dropdown-item:has-text('{frequency_type}')"
            )
        )

        wait2(page)

        if reporter:
            reporter.add_test_step(
                "Choose Frequency",
                "passed",
                round(time.time() - step_start, 2)
            )

        # ðŸ”¥ Call specific logic
        handle_frequency_logic(page, frequency_type, reporter)

    except Exception as e:
        if reporter:
            reporter.add_test_step(
                "Choose Frequency",
                "failed",
                round(time.time() - step_start, 2),
                error=str(e)
            )
        raise
def handle_frequency_logic(page, frequency_type, reporter=None):

    if frequency_type.lower() == "Manual":
        # No date required
        return

    if frequency_type.lower() in ["one-time"]:
        select_start_date(page, reporter)
    
    elif frequency_type.lower() == "daily":
        select_start_end_date(page, reporter)

    elif frequency_type.lower() == "weekly":
        select_weekly_options(page, reporter)
        select_start_end_date(page, reporter)

    elif frequency_type.lower() == "monthly":
        select_frequency_date(page, reporter)
        select_start_end_date(page, reporter)

        

def select_weekly_options(page, Config):

    log.info("âž¡ï¸ Choose Weekly Day")

    safe_click(page.get_by_role("combobox", name="Choose day"))
    wait2(page)

    safe_click(
    page.locator(f"li.p-dropdown-item:has-text('{Config.Target__Day}')")
)
    wait2(page)

def select_frequency_date(page, Config):

    log.info("âž¡ï¸ Select Frequency Date")

    frequency_date = datetime.strptime(
    Config.Target_Date,   # dd/mm/yyyy
    "%d/%m/%Y"
).strftime("%m/%d/%Y")   
    #frequency_date = (datetime + timedelta(days=9)).strftime("%d/%m/%Y")

    freq_input = page.locator(
        "p-calendar[formcontrolname='frequencyDate'] input"
    )

    freq_input.wait_for(state="visible")
    freq_input.click()
    freq_input.press("Control+A")
    freq_input.press("Backspace")
    freq_input.type(frequency_date, delay=50)
    freq_input.press("Enter")

    wait2(page)
def select_start_date(page, reporter=None):


        log.info("âž¡ï¸ Select Start Date")

        today = datetime.today()
        #end_day = today + timedelta(days=10)

        start_day = today.day
       

        # Start Date
        safe_click(page.locator("button[aria-label='Choose Date']").nth(0))
        popup = page.locator("div.p-datepicker[role='dialog']")
        popup.wait_for(state="visible")

        safe_click(popup.locator(f"td[aria-label='{start_day}']:not(.p-disabled) span").first)

        wait2(page)


       
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#          IMPROVED DATE SELECTION FUNCTIONS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def select_prime_date(
    page: Page,
    formcontrolname: str,
    target_date: datetime,
    use_direct_input: bool = True,          # prefer typing if possible
    reporter=None
) -> None:
    """
    Select date in PrimeNG p-calendar.
    Tries direct input first (most stable), falls back to popup navigation.
    """
    if reporter:
        step_start = time.time()

    log.info(f"âž¡ï¸ Setting date for {formcontrolname}: {target_date.strftime('%d/%m/%Y')}")

    calendar = page.locator(f"p-calendar[formcontrolname='{formcontrolname}']")
    calendar.wait_for(state="visible", timeout=10000)

    input_field = calendar.locator("input")

    if use_direct_input:
        try:
            input_field.click(force=True)
            input_field.fill("")  # clear existing value
            formatted_date = target_date.strftime("%d/%m/%Y")  # adjust format if app uses %m/%d/%Y
            input_field.type(formatted_date, delay=40)
            input_field.press("Enter")
            time.sleep(0.6)

            # Verify
            expect(input_field).to_have_value(formatted_date, timeout=5000)
            log.info(f"âœ” Direct input successful: {formatted_date}")
            
            if reporter:
                reporter.add_test_step(
                    f"Set {formcontrolname} (direct)",
                    "passed",
                    round(time.time() - step_start, 2)
                )
            return

        except Exception as e:
            log.info(f"Direct input failed ({e}), falling back to calendar popup")

    # â”€â”€â”€ Popup fallback â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        date_button = calendar.locator("button[aria-label='Choose Date']")
        safe_click(date_button)

        popup = page.locator("div.p-datepicker[role='dialog']:visible").last
        expect(popup).to_be_visible(timeout=8000)

        # Navigate to correct month/year
        header = popup.locator(".p-datepicker-title")
        expected_header = target_date.strftime("%B %Y")  # "March 2026"

        attempts = 0
        max_attempts = 12  # roughly one year
        while header.inner_text().strip() != expected_header and attempts < max_attempts:
            next_btn = popup.locator(".p-datepicker-next")
            prev_btn = popup.locator(".p-datepicker-prev")

            if next_btn.is_visible():
                safe_click(next_btn)
            elif prev_btn.is_visible():
                safe_click(prev_btn)
            else:
                raise RuntimeError("Cannot navigate calendar - no prev/next buttons found")

            time.sleep(0.5)
            attempts += 1

        if attempts >= max_attempts:
            raise RuntimeError(f"Failed to reach {expected_header} after {max_attempts} attempts")

        # Select the day
        day_locator = popup.locator(
            f"td[aria-label='{target_date.day}'] span:not(.p-disabled)"
        ).first

        day_locator.wait_for(state="visible", timeout=6000)
        safe_click(day_locator)

        # Wait for popup to close & value to appear
        expect(popup).to_be_hidden(timeout=5000)
        expect(input_field).to_have_value(target_date.strftime("%d/%m/%Y"), timeout=6000)

        log.info(f"âœ” Popup selection successful: {target_date.day} {target_date.strftime('%B %Y')}")

        if reporter:
            reporter.add_test_step(
                f"Set {formcontrolname} (popup)",
                "passed",
                round(time.time() - step_start, 2)
            )

    except Exception as e:
        log.info(f"âŒ Date selection failed for {formcontrolname}: {str(e)}")
        if reporter:
            reporter.add_test_step(
                f"Set {formcontrolname}",
                "failed",
                round(time.time() - step_start, 2),
                error=str(e)
            )
        page.screenshot(path=f"error-date-{formcontrolname}-{int(time.time())}.png")
        raise
def select_start_end_date(page, Config):

      

        log.info("âž¡ï¸ Select Start & End Date")

        today = datetime.today()
        start_date = today  # or today + timedelta(days=1) if must be future
        end_date = today + timedelta(days=Config.Day_s)

        start_str = start_date.strftime("%m/%d/%Y")   # 02/03/2026
        end_str   = end_date.strftime("%m/%d/%Y")     # e.g. 01/04/2026

        log.info(f"Planned â†’ Start: {start_str}   End: {end_str}")

        def set_date(formcontrolname: str, date_str: str, target_date: datetime):
            calendar = page.locator(f"p-calendar[formcontrolname='{formcontrolname}']")
            calendar.wait_for(state="visible", timeout=10000)
            input_el = calendar.locator("input")

            # Try direct typing first (most apps accept DD/MM/YYYY)
            try:
                input_el.click(force=True)
                input_el.fill("")           # clear
                input_el.type(date_str, delay=40)
                input_el.press("Enter")
                time.sleep(0.8)

                # Quick verify
                current_val = input_el.input_value()
                if date_str in current_val or date_str.replace('/', '') in current_val:
                    log.info(f"âœ” Typing worked for {formcontrolname}: {date_str}")
                    return
                else:
                    log.info(f"Typing partial/ignored â†’ fallback to popup")
            except Exception as e:
                log.info(f"Typing failed ({e}) â†’ fallback to popup")

            # Popup fallback (robust navigation)
            try:
                safe_click(calendar.locator("button[aria-label='Choose Date']"))
                popup = page.locator("div.p-datepicker[role='dialog']:visible").last
                expect(popup).to_be_visible(timeout=8000)

                header = popup.locator(".p-datepicker-title")
                expected = target_date.strftime("%B %Y")   # "March 2026"

                attempts = 0
                while header.inner_text().strip() != expected and attempts < 24:
                    if popup.locator(".p-datepicker-next").is_visible():
                        safe_click(popup.locator(".p-datepicker-next"))
                    elif popup.locator(".p-datepicker-prev").is_visible():
                        safe_click(popup.locator(".p-datepicker-prev"))
                    else:
                        raise RuntimeError("No navigation buttons")
                    time.sleep(0.4)
                    attempts += 1

                if attempts >= 24:
                    raise RuntimeError(f"Couldn't reach {expected}")

                day_sel = popup.locator(
                    f"td[aria-label='{target_date.day}'] span:not(.p-disabled)"
                ).first
                day_sel.wait_for(state="visible")
                safe_click(day_sel)

                expect(popup).to_be_hidden(timeout=6000)
                expect(input_el).to_have_value(lambda v: date_str in v or str(target_date.day) in v, timeout=5000)

                log.info(f"âœ” Popup success for {formcontrolname}: {date_str}")

            except Exception as e:
                page.screenshot(path=f"date-fail-{formcontrolname}-{int(time.time())}.png")
                raise RuntimeError(f"Date set failed for {formcontrolname}: {e}")

        # Apply to both
        set_date("startDateTime", start_str, start_date)
        set_date("endDateTime", end_str, end_date)

        # Final debug read
        try:
            s_val = page.locator("[formcontrolname='startDateTime'] input").input_value()
            e_val = page.locator("[formcontrolname='endDateTime'] input").input_value()
            log.info(f"FINAL VALUES â†’ Start: {s_val} | End: {e_val}")
        except:
            pass


# ======================================================
# UTILITY FUNCTIONS
# ======================================================

def execute_step(reporter, step_name, func, *args, **kwargs):
    """
    Execute a step with timing and reporting.
    Only used when ENABLE_REPORTING is True.
    """
    start = time.time()
    try:
        result = func(*args, **kwargs)
        duration = round(time.time() - start, 2)
        if reporter:
            reporter.add_test_step(step_name, "passed", duration=duration)
        return result
    except Exception as e:
        duration = round(time.time() - start, 2)
        if reporter:
            reporter.add_test_step(step_name, "failed", duration=duration, error=str(e))
        raise


def wait_for_overlay_to_disappear(page: Page) -> None:
    """Wait for common overlay elements to disappear."""
    overlays = [
        ".p-dialog-mask",
        ".p-component-overlay",
        ".cdk-overlay-backdrop"
    ]
    for selector in overlays:
        try:
            page.wait_for_selector(selector, state="detached", timeout=2000)
        except PlaywrightTimeoutError:
            pass


def js_click(page: Page, locator) -> bool:
    """
    Attempt to click an element, first normally then via JavaScript if needed.
    Returns True if successful, False otherwise.
    """
    try:
        locator.click(force=True)
        return True
    except Exception:
        try:
            handle = locator.element_handle(timeout=2000)
            if handle:
                page.evaluate("(el) => el.click()", handle)
                return True
        except Exception:
            return False
    return False


def safe_click(locator) -> None:
    """Click with multiple safety checks."""
    locator.wait_for(state="attached", timeout=15000)
    locator.wait_for(state="visible", timeout=15000)
    locator.scroll_into_view_if_needed()
    locator.page.wait_for_load_state("networkidle")
    
    try:
        locator.click(timeout=10000)
    except:
        locator.click(force=True)


def wait2(page: Page) -> None:
    """Wait for 2 seconds."""
    page.wait_for_timeout(2000)


def click_and_wait(page: Page, click_selector: str, wait_selector: Optional[str] = None, 
                   timeout: int = 15000) -> None:
    """Click an element and optionally wait for another element to appear."""
    page.wait_for_selector(click_selector, timeout=timeout).click()
    if wait_selector:
        page.wait_for_selector(wait_selector, timeout=timeout)
    time.sleep(SLEEP_TIME)


def random_name() -> str:
    """Generate a random audit name."""
    return "Audit_" + "".join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )


def _normalize(s: str) -> str:
    """Normalize string for comparison."""
    return (s or "").strip().lower()
# =====================================
# Configure Cross Audit Section
# =====================================

def configure_cross_audit(page, cross_type: str, cross_auditor: str = None, cross_size: str = None, reporter=None):

    if reporter:
        step_start = time.time()

    log.info(f"âž¡ï¸ Configure Cross Audit: {cross_type}")

    # Step 1: Select Cross Audit Type
    click_cross_audit_type(page, cross_type, reporter)

    wait2(page)

    # Step 2: If Random Recheck â†’ fill percentage
    if cross_type == "Random Recheck":
        if not cross_size:
            raise Exception("âŒ Random Recheck requires cross_size value")

        size_input = page.locator("[formcontrolname='crossCheckSize']")
        size_input.wait_for(state="visible")
        size_input.fill(str(cross_size))

    # Step 3: Select Cross Auditor (if required)
    if cross_type in ["Random Recheck", "Discrepancy Recheck"]:

        if not cross_auditor:
            raise Exception(f"âŒ {cross_type} requires Cross Auditor")

        log.info("âž¡ï¸ Choose Cross Auditor")

        # Open dropdown
        safe_click(page.get_by_role("combobox", name="Choose Cross Auditor"))

        panel = page.locator("div.p-dropdown-panel")
        panel.wait_for(state="visible")

        # Select auditor by text
        option = panel.locator("li.p-dropdown-item", has_text=cross_auditor)

        if option.count() == 0:
            raise Exception(f"âŒ Cross Auditor '{cross_auditor}' not found")

        option.first.scroll_into_view_if_needed()
        option.first.click()

    wait2(page)

    if reporter:
        reporter.add_test_step(
            f"Configure Cross Audit - {cross_type}",
            "passed",
            round(time.time() - step_start, 2)
        )




# =====================================
# Select Multiple Auditors (PrimeNG Safe)
# =====================================

def select_auditors(page, auditor_input):


    # Convert to list
    if isinstance(auditor_input, str):
        auditor_names = [name.strip() for name in auditor_input.split(",") if name.strip()]
    else:
        auditor_names = auditor_input

    log.info(f"âž¡ï¸ Select Auditors: {', '.join(auditor_names)}")

    # Open dropdown
    safe_click(page.locator("div.p-multiselect-trigger").first)

    # Wait for overlay panel to appear
    panel = page.locator("div.p-multiselect-panel")
    panel.wait_for(state="visible")

    for auditor_name in auditor_names:

        # Use text-based locator inside panel (VERY IMPORTANT)
        option = panel.locator("li.p-multiselect-item", has_text=auditor_name)

        if option.count() == 0:
            raise Exception(f"âŒ Auditor '{auditor_name}' not found in dropdown")

        option.first.scroll_into_view_if_needed()
        option.first.click()

    # Close dropdown safely
    page.keyboard.press("Escape")

# ======================================================
# DROPDOWN FUNCTIONS
# ======================================================

def read_dropdown_options_for_locator(page: Page, dropdown_locator, 
                                     timeout: int = 3000) -> List[str]:
    """
    Open a p-dropdown, read all options, close it, and return the option list.
    """
    try:
        combobox = dropdown_locator.locator('span[role="combobox"]').first
        combobox.scroll_into_view_if_needed()
        js_click(page, combobox)
        time.sleep(0.12)

        try:
            page.wait_for_selector("div.p-dropdown-panel:visible", timeout=timeout)
        except PlaywrightTimeoutError:
            page.mouse.click(0, 0)
            return []

        panels = page.locator("div.p-dropdown-panel:visible")
        option_texts = []
        panel_count = panels.count()
        
        for i in range(panel_count):
            panel = panels.nth(i)
            try:
                item_count = panel.locator("li.p-dropdown-item").count()
            except Exception:
                item_count = 0
                
            if item_count > 0:
                try:
                    option_texts = panel.evaluate(
                        """panel => Array.from(panel.querySelectorAll('li.p-dropdown-item'))
                                           .map(li => li.innerText ? li.innerText.trim() : 
                                                     (li.textContent || '').trim())"""
                    )
                except Exception:
                    option_texts = []
                    for j in range(item_count):
                        try:
                            text = panel.locator("li.p-dropdown-item").nth(j).inner_text().strip()
                            option_texts.append(text)
                        except Exception:
                            option_texts.append("")
                break

        page.mouse.click(0, 0)
        time.sleep(0.12)
        return option_texts

    except Exception as e:
        log.info(f"âœ– Failed to read dropdown options: {e}")
        try:
            page.mouse.click(0, 0)
        except Exception:
            pass
        return []

def click_audit_type(page,audit_type: str):
    locator = page.locator(
        f"p-radiobutton[value='{audit_type}'] .p-radiobutton-box"
    )

    locator.wait_for(state="visible")
    locator.scroll_into_view_if_needed()
    locator.click()   # important for PrimeNG



# =====================================
# Select Cross Audit Type (PrimeNG - Final Stable Version)
# =====================================

def click_cross_audit_type(page,cross_audit_type: str, reporter=None):

    if reporter:
        step_start = time.time()

    log.info(f"âž¡ï¸ Select Cross Audit Type: {cross_audit_type}")

    # Map UI label to actual value attribute
    value_map = {
        "None": "",
        "Random Recheck": "Random",
        "Discrepancy Recheck": "Discrepancy"
    }

    if cross_audit_type not in value_map:
        raise Exception(
            f"âŒ Invalid Cross Audit Type: {cross_audit_type}. "
            f"Valid options: {list(value_map.keys())}"
        )

    radio_value = value_map[cross_audit_type]

    # Locate correct p-radiobutton using value attribute
    radio_component = page.locator(
        f"p-radiobutton[value='{radio_value}']"
    )

    radio_component.wait_for(state="attached")

    if radio_component.count() == 0:
        raise Exception(f"âŒ Cross Audit Type '{cross_audit_type}' not found in UI")

    # Locate visible clickable box
    radio_box = radio_component.locator(".p-radiobutton-box")

    # Check if already selected
    if not radio_box.get_attribute("class") or "p-highlight" not in radio_box.get_attribute("class"):
        radio_box.scroll_into_view_if_needed()
        radio_box.click()

    wait2(page)

    if reporter:
        reporter.add_test_step(
            f"Select Cross Audit Type - {cross_audit_type}",
            "passed",
            round(time.time() - step_start, 2)
        )

# ======================================================
# DROPDOWN OPTION SELECTION WITH FUZZY MATCHING 
def select_option_for_dropdown_locator(page: Page, dropdown_locator, option_text: str, 
                                       timeout: int = 7000) -> Tuple[bool, str, Optional[any]]:
    """
    Select an option from a dropdown with fuzzy matching fallback.
    Returns (success: bool, method: str, element: Locator or None)
    """
    option_text_norm = _normalize(option_text)
    log.info(f"[select_option] selecting '{option_text}'")

    try:
        trigger = dropdown_locator
        try:
            inner = dropdown_locator.locator('span[role="combobox"]').first
            if inner.count() and inner.is_visible():
                trigger = inner
        except Exception:
            pass

        try:
            trigger.scroll_into_view_if_needed()
        except Exception:
            pass

        clicked = js_click(page, trigger)
        if not clicked:
            try:
                trigger.click(timeout=2000, force=True)
            except Exception:
                pass

        time.sleep(SLEEP_TIME)

        panel_selectors = [
            "div.p-dropdown-panel", "div.p-multiselect-panel", "ul.p-dropdown-items",
            "div.ui-dropdown-panel", "div[role='listbox']", "div[role='dialog']"
        ]

        panels = []
        for sel in panel_selectors:
            try:
                loc = page.locator(sel)
                cnt = loc.count()
                for i in range(cnt):
                    p = loc.nth(i)
                    if p.is_visible():
                        panels.append(p)
            except Exception:
                continue

        if not panels:
            panels = [page]

        # 1) Exact match
        for panel in panels:
            try:
                opt = panel.locator(f"li:has-text('{option_text}')")
                if opt.count():
                    for j in range(opt.count()):
                        candidate = opt.nth(j)
                        if candidate.is_visible():
                            js_click(page, candidate)
                            return True, "exact_li", candidate
            except Exception:
                continue

        # 2) Case-insensitive + fuzzy match
        for panel in panels:
            try:
                items = panel.locator("li, div, span")
                cnt = items.count()
            except:
                cnt = 0

            seen = []
            for i in range(cnt):
                try:
                    it = items.nth(i)
                    if not it.is_visible():
                        continue
                    txt = it.inner_text().strip()
                    if not txt:
                        continue
                    seen.append((i, txt, it))
                    if _normalize(txt) == option_text_norm:
                        js_click(page, it)
                        return True, "case_insensitive_direct", it
                except:
                    continue

            if seen:
                texts = [t for (_, t, _) in seen]
                lower_texts = [t.lower() for t in texts]
                matches = difflib.get_close_matches(option_text_norm, lower_texts, n=1, cutoff=0.6)
                if matches:
                    best = matches[0]
                    idx = lower_texts.index(best)
                    chosen = seen[idx][2]
                    js_click(page, chosen)
                    return True, "fuzzy", chosen

        # 3) Page-wide exact match
        page_items = page.locator(f"text={option_text}")
        if page_items.count():
            for i in range(page_items.count()):
                candidate = page_items.nth(i)
                if candidate.is_visible():
                    js_click(page, candidate)
                    return True, "page_wide", candidate

        return False, "not_found", None

    except Exception as e:
        return False, f"exception:{e}", None


def is_already_mapped(dropdown_locator) -> bool:
    """Check if dropdown already has a selected value."""
    try:
        label = dropdown_locator.locator("span.p-dropdown-label:not(.p-placeholder)")
        return label.count() > 0 and label.first.inner_text().strip() != ""
    except Exception:
        return False


def select_item_group(page: Page, group_name: str) -> None:
    """Select value from 'Select Item Group' PrimeNG dropdown."""
    dropdown = page.locator("p-dropdown[placeholder='Select Item Group']")
    dropdown.locator("div.p-dropdown-trigger").click()
    time.sleep(SLEEP_TIME)

    panel = page.locator("div.p-dropdown-panel")
    time.sleep(SLEEP_TIME)

    panel.locator("input.p-dropdown-filter").fill(group_name)
    time.sleep(SLEEP_TIME)

    panel.locator("li.p-dropdown-item", has_text=group_name).first.click()
    # --------------------------------------------------------------
    # LOAD AUDITOR MAPPING FROM SINGLE SHEET
    # Returns: { auditor_name: { "categories": [...], "storages": [...] } }
    # Reads EXCEL_SHEET_AUDITOR_MAPPING with columns: Auditor | Category | Storage
    # --------------------------------------------------------------
def load_auditor_mapping(Config):
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
    # APPLY AUDITOR ASSIGNMENTS
    #   "Random"      â†’ nothing to assign
    #   "By Category" â†’ assign Category column values per auditor
    #   "By Storage"  â†’ assign Storage  column values per auditor
    # --------------------------------------------------------------
def apply_auditor_assignments(page, mapping_type):
        if mapping_type == "Random":
            log.info("â„¹ Mapping type is Random â€” no assignments needed")
            return

        auditor_map = load_auditor_mapping()
        log.info(f"ðŸ“‹ Loaded auditor mapping: {auditor_map}")

        for auditor, data in auditor_map.items():

            if mapping_type == "By Category":
                categories = data["categories"]
                if not categories:
                    log.info(f"âš  No categories found for '{auditor}' in sheet")
                    continue
                log.info(f"â†’ Assigning categories {categories} to '{auditor}'")
                row = find_auditor_row(page, auditor)
                if row is None:
                    log.info(f"âŒ Row not found for auditor: '{auditor}'")
                    continue
                panel = open_multiselect_panel(page, row)
                select_items_in_panel(page, panel, categories, auditor, "Category")

            elif mapping_type == "By Storage":
                storages = data["storages"]
                if not storages:
                    log.info(f"âš  No storages found for '{auditor}' in sheet")
                    continue
                log.info(f"â†’ Assigning storages {storages} to '{auditor}'")
                row = find_auditor_row(page, auditor)
                if row is None:
                    log.info(f"âŒ Row not found for auditor: '{auditor}'")
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
def test_mapping_and_saving(page, Config):

        log.info("ðŸ“¥ Uploading primary file")
        page.set_input_files("input#formFileSm", Config.EXCEL_PATH)
        page.wait_for_selector("div.row-container")

        
# ======================================================
# HEADER MAPPING
# ======================================================

def map_headers(page: Page, mapping: dict, reporter=None) -> None:
    """
    Map Excel headers to application fields with safety checks.
    """
    row_container = page.locator("div.row-container")
    left_col = row_container.locator("div.col-md-6").nth(0)
    right_col = row_container.locator("div.col-md-6").nth(1)

    labels = left_col.locator("div.label > label")
    dropdowns = right_col.locator("p-dropdown")

    # Read all label texts
    try:
        label_texts = left_col.evaluate(
            """col => Array.from(col.querySelectorAll('div.label > label'))
                           .map(el => el.innerText ? el.innerText.trim() : 
                                     (el.textContent || '').trim())"""
        )
    except Exception as e:
        log.info(f"Warning: evaluate failed: {e}. Falling back to incremental read.")
        label_texts = []
        count = labels.count()
        for i in range(count):
            try:
                label_texts.append(labels.nth(i).inner_text().strip())
            except Exception:
                label_texts.append("")

    log.info(f"Found headers: {label_texts}")

    for required_label, excel_header in mapping.items():
        wait_for_overlay_to_disappear(page)

        if required_label not in label_texts:
            log.info(f"âš  Missing label: {required_label}")
            if reporter:
                reporter.add_test_step(
                    f"Map {required_label}",
                    "skipped",
                    error=f"Label '{required_label}' not found on page"
                )
            continue

        idx = label_texts.index(required_label)
        dropdown = dropdowns.nth(idx)

        # Skip if already mapped
        if is_already_mapped(dropdown):
            log.info(f"â­ Skipped '{required_label}' (already mapped)")
            if reporter:
                reporter.add_test_step(
                    f"Map {required_label}",
                    "skipped",
                    error="Already mapped"
                )
            continue

        # Select the option
        step_start = time.time()
        ok, method, _ = select_option_for_dropdown_locator(page, dropdown, excel_header)
        duration = round(time.time() - step_start, 2)

        if ok:
            log.info(f"âœ” Mapped {required_label} â†’ {excel_header} via {method}")
            if reporter:
                reporter.add_test_step(
                    f"Map {required_label} â†’ {excel_header}",
                    "passed",
                    duration=duration
                )
        else:
            log.info(f"âœ– Failed to map {required_label}")
            if reporter:
                reporter.add_test_step(
                    f"Map {required_label}",
                    "failed",
                    duration=duration,
                    error=f"Could not find option '{excel_header}' in dropdown"
                )

    log.info("âœ… Header mapping completed.")
    





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
    # SELECT ITEMS IN AN OPEN MULTISELECT PANEL  (idempotent)
    # --------------------------------------------------------------
def select_items_in_panel(page, panel, items, auditor_name, item_type):
        for item_text in items:
            option = panel.locator("li.p-multiselect-item", has_text=item_text)

            if option.count() == 0:
                log.info(
                    f"âš  {item_type} '{item_text}' not found for '{auditor_name}'"
                )
                continue

            cls = option.first.get_attribute("class") or ""
            if "p-highlight" not in cls:
                option.first.click()
                page.wait_for_timeout(300)
            else:
                log.info(
                    f"âœ” Already selected: '{item_text}' for '{auditor_name}'"
                )

        page.keyboard.press("Escape")
        page.wait_for_timeout(300)


# =====================================
# Enable / Disable Audit Options (Dynamic)
# =====================================

def enable_audit_options(page, audit_options: dict, reporter=None):


    log.info("âž¡ï¸ Configure Audit Options")

    for field_name, value in audit_options.items():

        checkbox = page.locator(f"[formcontrolname='{field_name}']")

        # Wait for checkbox to be attached
        checkbox.wait_for(state="attached")

        should_check = str(value).strip().lower() in ["true", "yes", "1"]

        if should_check:
            if not checkbox.is_checked():
                checkbox.check()
        else:
            if checkbox.is_checked():
                checkbox.uncheck()

    wait2(page)

    # --------------------------------------------------------------
    # SELECT BRANCH using XPATH (PrimeNG p-dropdown)
    # --------------------------------------------------------------
def select_branch(page, branch_text: str):

        # 1ï¸âƒ£ Branch dropdown container (XPath)
        dropdown = page.locator(
            'xpath=/html/body/app-root/app-layout/div/app-header/div[1]/div[2]/div[2]//p-dropdown'
        )
        dropdown.wait_for(state="visible", timeout=30000)

        # 2ï¸âƒ£ Click dropdown label to open
        dropdown.locator(".p-dropdown-label").click()

        # 3ï¸âƒ£ Wait for dropdown panel (overlay)
        panel = page.locator(".p-dropdown-panel").last
        panel.wait_for(state="visible", timeout=30000)

        # 4ï¸âƒ£ Filter search (if exists)
        search = panel.locator("input.p-dropdown-filter")
        if search.count() > 0:
            search.fill("")
            search.fill(branch_text)
            page.wait_for_timeout(300)

        # 5ï¸âƒ£ Select branch option
        option = panel.locator(
            "li.p-dropdown-item",
            has_text=branch_text
        )

        if option.count() == 0:
            raise Exception(f"âŒ Branch not found: {branch_text}")

        option.first.click()

        # 6ï¸âƒ£ Ensure panel closed
        panel.wait_for(state="hidden", timeout=30000)

        # 7ï¸âƒ£ Final verification
        dropdown.locator(
            ".p-dropdown-label",
            has_text=branch_text
        ).wait_for(state="visible", timeout=30000)

def set_checkbox(page, selector, should_be_checked):
        checkbox = page.wait_for_selector(selector)
        if should_be_checked and not checkbox.is_checked():
            checkbox.check(force=True)
        elif not should_be_checked and checkbox.is_checked():
            checkbox.uncheck(force=True)  
# ======================================================
# AUDIT CREATION
# ======================================================

def create_audit(page, Config) -> str:
    """Create a new audit and return its name."""
    
     
    log.info("âž¡ï¸ Open Audit page")
    page.wait_for_timeout(1000)
    # Wait until element visible
    page.wait_for_selector("a[href='/home/audit']", state="visible")

    # Click
    page.click("a[href='/home/audit']")
    page.wait_for_load_state("networkidle")
    wait2(page)

    log.info("âž¡ï¸ Click Create Audit")
    safe_click(page.locator("button.createAuditBtn"))
    wait2(page)


    log.info("âž¡ï¸ Select Audit Plan")
    safe_click(page.locator("button[label='Audit Plan']"))
    wait2(page)
    safe_click(page.locator("button:has-text('Add Audit Plan')"))
    wait2(page)

      
#==========================================================================================        
#------------------------------------------------------------------------------------------
        # Open Audit Owner dropdown 

    log.info("âž¡ï¸ Choose Audit Owner")
    select_prime_dropdown(page,
    xpath="/html/body/app-root/app-layout/div/app-audit-plan/app-add-audit-plan/div/div[2]/form/div[1]/div/div[1]/div[2]/p-dropdown/div")
        
    wait2(page)
    safe_click(
    page.locator(f"li.p-dropdown-item:has-text('{Config.Audit_Owner}')")
)# Select fff dd as audit owner
    wait2(page)
        
       
#------------------------------------------------------------------------------------------
    # Select Group
     
    log.info("âž¡ï¸ Select Role")
    safe_click(page.locator("div#role .p-dropdown-trigger"))
    wait2(page)
    panel = page.locator("div.p-dropdown-panel")
    panel.wait_for(state="visible")
    panel.locator(
    "li.p-dropdown-item",
    has_text=Config.Group_Name
).first.click()
    wait2(page)
#------------------------------------------------------------------------------------------
# Fill Audit Name
        
    log.info(f"ðŸ“ Audit Name: {Config.ap_audit_name}") #audit name

    page.fill("input#name", Config.ap_audit_name)
    wait2(page)

#------------------------------------------------------------------------------------------
 
 # Select Audit Type as Cycle Count or Complete Count       

    log.info("âž¡ï¸ Select Audit Type")
    click_audit_type(page, Config.Audit_Type)   #Cycle Count or Complete Count     
    wait2(page)
#------------------------------------------------------------------------------------------
    #Choose Frequency - Manual, one-time, Daily , Weekly, Monthly
    choose_frequency(page, Config.frequency)
#dynamic selection based on requirement           
        
 #------------------------------------------------------------------------------------------     
# Click Next
    
    safe_click(page.get_by_role("button", name="Next"))
    wait2(page)

#---------------------------------------------------------------------------------------------------------
        # Select Auditors
    select_auditors(page, [Config.Auditor1, Config.Auditor2, Config.Audit_Owner])
#---------------------------------------------------------------------------------------------------------
 # Enable Audit Options  isDamageQty, isStockItems, isGeoTagging(true/false)
 # Enable Audit Options  isDamageQty, isStockItems, isGeoTagging(true/false)
# Audit Damaged Inventory
    set_checkbox(page, "input[formcontrolname='isDamageQty']", Config.A_Checkboxes_Audit_Damaged)

        # Show Stock Count to Auditor
    set_checkbox(page, "input[formcontrolname='isStockItems']", Config.A_Checkboxes_StockItems)

        # Geo Tagging
    set_checkbox(page, "input[formcontrolname='isGeoTagging']", Config.A_Checkboxes_geo)

        # Photo Validation
    set_checkbox(page, "input[formcontrolname='isPhotoValidation']", Config.A_Checkboxes_photo)

    time.sleep(SLEEP_TIME)
                
        
#---------------------------------------------------------------------------------------------------------
        #Sample Size, Cross Auditor
        #CROSS_AUDIT_TYPE = "Random Recheck", "Discrepancy Recheck", "None"

    if Config.CROSS_AUDIT_TYPE == "Random Recheck":
            configure_cross_audit(page, cross_type="Random Recheck", cross_size="50", cross_auditor=Config.CROSS_Auditor_name)
    elif Config.CROSS_AUDIT_TYPE  == "Discrepancy Recheck":
            configure_cross_audit(page, cross_type="Discrepancy Recheck", cross_auditor=Config.CROSS_Auditor_name)
    else:
            configure_cross_audit(page, cross_type="None")
#---------------------------------------------------------------------------------------------------------
 # Click Next
        
    log.info("âž¡ï¸ Click Next")
    safe_click(page.get_by_role("button", name="Next"))
    wait2(page)
#------------------------------------------------

#    mapping_type = Config.AUDIT_MAPPING_TYPE
    mapping_type = Config.AUDIT_MAPPING_TYPE
    page.locator("p-dropdown[formcontrolname='periodicalType']").click()
    page.locator("li.p-dropdown-item", has_text= mapping_type).click()
    time.sleep(SLEEP_TIME)
            # "Random" â†’ nothing extra; "By Category"/"By Storage" â†’ assign from sheet
    apply_auditor_assignments(page, mapping_type)   
#---------------------------------------------------------------------------------------------------------
 # Save Audit

    log.info("âž¡ï¸ Save Audit")
    safe_click(page.locator("button.primary-button:has-text('Save')"))
    page.wait_for_load_state("networkidle")
    safe_click(page.locator("button:has-text('Back')"))
    page.wait_for_load_state("networkidle")
    wait2(page)
   






    

