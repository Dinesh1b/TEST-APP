import os
import sys
import time
import re
from playwright.sync_api import sync_playwright

# Ensure Python sees root directory of "main"
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# Correct imports
from login.login import login
from new_transaction import new_transaction
from login.popup_handler import detect_feedback
from login.logger_setup import mirrored_print
from excel_logger import write_log

# -----------------------
# Parsing / verification helpers
# -----------------------
def _parse_amount(text: str) -> float:
    """
    Parse human-friendly currency strings into a signed float.
    Accepts forms like:
      "12", "12.00", "-12", "(12.00)", "₹ 1,234.50", "1,234.50-"
    """
    if not text:
        raise ValueError("Empty amount text")

    s = text.strip()

    # handle parentheses for negative amounts: (12.00) -> -12.00
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1].strip()

    # allow trailing negative sign e.g. "12-"
    if s.endswith("-"):
        negative = True
        s = s[:-1].strip()

    # remove any non-digit, non-dot, non-comma, non-minus characters
    s = re.sub(r"[^\d\.,\-]", "", s)

    # remove thousands separators (commas)
    s = s.replace(",", "")

    if s == "" or s == ".":
        raise ValueError(f"Could not parse amount from '{text}'")

    val = float(s)
    if negative:
        val = -abs(val)
    return val


def verify_closing_balance(page, expected_amount, *, tolerance=0.0001):
    """
    Verify the Closing Balance displayed on the page equals expected_amount.
    expected_amount: numeric (int/float) or string (e.g. "-12" or "(12.00)").
    Raises AssertionError on mismatch.
    """
    # normalize expected_amount to float
    if isinstance(expected_amount, str):
        expected = _parse_amount(expected_amount)
    else:
        expected = float(expected_amount)

    # locate the closing-balance container by label text, then the span.ms-2
    container = page.locator("div.col-lg-3.lbl").filter(has_text="Closing Balance")
    container.wait_for(state="visible", timeout=7000)

    amount_span = container.locator("span.ms-2")
    text = amount_span.inner_text().strip()
    actual = _parse_amount(text)

    print(f"Closing Balance on page: {actual}  |  Expected: {expected}")

    if abs(actual - expected) <= tolerance:
        print("✅ Closing Balance matches expected amount.")
        return True
    else:
        msg = f"❌ Closing Balance mismatch: actual={actual}, expected={expected}"
        print(msg)
        raise AssertionError(msg)


# -----------------------
# Page helper functions
# -----------------------
def fill_first_row(page, payment_mode, account_text, amount, description):
    """Fill the first row in the transaction table."""
    pm = page.locator("tr.ng-star-inserted:first-of-type td:nth-child(1) span[role='combobox']")
    pm.wait_for(state="visible", timeout=7000)
    pm.click()
    page.locator(f"li[role='option'] >> text='{payment_mode}'").click()

    acc = page.locator("tr.ng-star-inserted:first-of-type td:nth-child(2) p-dropdown")
    acc.click()
    page.locator(".p-dropdown-panel input.p-dropdown-filter").fill(account_text)
    page.locator(f".p-dropdown-items li[role='option'] >> text='{account_text}'").click()

    page.locator("tr.ng-star-inserted:first-of-type td:nth-child(3) textarea").fill(description)
    page.locator("tr.ng-star-inserted:first-of-type td:nth-child(4) input").fill(str(amount))


def add_payment_line(page, payment_mode, account_text, amount, description):
    """Add and fill a new payment row."""
    page.locator("button:has-text('Add Line')").click()
    page.locator("tr:last-child td:nth-child(4) input").wait_for(state="visible", timeout=7000)

    pm = page.locator("tr:last-child td:nth-child(1) span[role='combobox']")
    pm.click()
    page.locator(f"li[role='option'] >> text='{payment_mode}'").click()

    acc = page.locator("tr:last-child td:nth-child(2) p-dropdown")
    acc.click()
    page.locator(".p-dropdown-panel input.p-dropdown-filter").fill(account_text)
    page.locator(f".p-dropdown-items li[role='option'] >> text='{account_text}'").click()

    page.locator("tr:last-child td:nth-child(3) textarea").fill(description)
    page.locator("tr:last-child td:nth-child(4) input").fill(str(amount))


# -----------------------
# Main flow — start Playwright (browser will NOT close)
# -----------------------
p = sync_playwright().start()   # keep browser open
print("🎬 Starting Playwright workflow...")

browser, page = login(p, browser_name="chrome", environment="QA")

# Navigate to new transaction
new_transaction(page)

# Click 'New Receipt'
page.locator("a.link:has-text('New Receipt')").click()
page.locator("a.link:has-text('New Receipt')").wait_for(state="hidden", timeout=3000)  # let navigation/render settle

# Select contact
contact_name = "Heather2234"
page.locator("input[placeholder='Search Contact']").wait_for(state="visible", timeout=7000)
page.locator("input[placeholder='Search Contact']").fill(contact_name)
page.locator("ul#Contact_list li").filter(has_text=contact_name).first.wait_for(state="visible", timeout=7000)
page.locator("ul#Contact_list li").filter(has_text=contact_name).first.click()
print("✅ Contact selected")

# Add line items
line_items = [
    {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1000},
    {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1030},
    {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1400},
    {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1500},
]

fill_first_row(page, **line_items[0], description="Auto Line 1 – payment entry")
print("✅ First row filled")

for i, item in enumerate(line_items[1:], start=2):
    add_payment_line(page, **item, description=f"Auto Line {i} – payment entry")
    print(f"✅ Row {i} filled")

# Header fields
page.fill("input[formcontrolname='Reference']", "REF-001")
page.fill("textarea[formcontrolname='Description']", "Transaction description here")

# Save as Draft
page.locator("button:has-text('Save As Draft')").click()
print("💾 Saved as draft")

# Detect feedback (kept inside)
detect_feedback(page)

# Navigate/menu
page.locator("a:has(img.sidenav-link-icon[src*='LederMenuIcon.svg'])").first.wait_for(state="visible", timeout=7000)
page.locator("a:has(img.sidenav-link-icon[src*='LederMenuIcon.svg'])").first.click()

# Autocomplete input box for contact selection (again)
inp = page.locator("input.p-autocomplete-input")
inp.wait_for(state="visible", timeout=7000)
inp.click()
inp.fill(contact_name)
page.locator("ul.p-autocomplete-items li").first.wait_for(state="visible", timeout=7000)
page.locator("ul.p-autocomplete-items li").first.click()

# Select "This Month" from FilterDate dropdown
option_text = "This Month"
combobox = page.locator("p-dropdown[formcontrolname='FilterDate'] span[role='combobox']")
combobox.wait_for(state="visible", timeout=7000)
panel_id = combobox.get_attribute("aria-controls")
combobox.click()
panel_selector = f"#{panel_id}" if panel_id else ".p-dropdown-panel:visible"
page.locator(panel_selector).wait_for(state="visible", timeout=7000)
page.locator(f"{panel_selector} li").filter(has_text=option_text).first.click()

# Click Retrieve
btn = page.locator("button.primary-button:has-text('Retrive')")
btn.wait_for(state="visible", timeout=7000)
btn.click()
print("🔍 Retrieved transactions for the selected contact and date range")

# Detect any feedback
detect_feedback(page)

# ---- verify the Closing Balance (expecting 12)
verify_closing_balance(page, 12)
print("✅ Closing Balance verified")


print("✅ Workflow completed (browser remains open)")

# keep browser open — change the sleep if you want shorter/longer
page.wait_for_timeout(99999999)
# NOTE: Close browser manually when you want: browser.close(); p.stop()
