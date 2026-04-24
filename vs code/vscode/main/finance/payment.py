import os
import sys
import time
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


# ------------------------------------------------------
# Fill first row
# ------------------------------------------------------
def fill_first_row(page, payment_mode, account_text, amount, description):
    pm = page.locator("tr.ng-star-inserted:first-of-type td:nth-child(1) span[role='combobox']")
    pm.wait_for(state="visible")
    pm.click()
    page.locator(f"li[role='option'] >> text='{payment_mode}'").click()

    acc = page.locator("tr.ng-star-inserted:first-of-type td:nth-child(2) p-dropdown")
    acc.click()
    page.locator(".p-dropdown-panel input.p-dropdown-filter").fill(account_text)
    page.locator(f".p-dropdown-items li[role='option'] >> text='{account_text}'").click()

    page.locator("tr.ng-star-inserted:first-of-type td:nth-child(3) textarea").fill(description)
    page.locator("tr.ng-star-inserted:first-of-type td:nth-child(4) input").fill(str(amount))


# ------------------------------------------------------
# Add additional rows
# ------------------------------------------------------
def add_payment_line(page, payment_mode, account_text, amount, description):
    page.locator("button:has-text('Add Line')").click()
    time.sleep(1)

    print("➡️ Add Line clicked")

    pm = page.locator("tr:last-child td:nth-child(1) span[role='combobox']")
    pm.click()
    page.locator(f"li[role='option'] >> text='{payment_mode}'").click()

    acc = page.locator("tr:last-child td:nth-child(2) p-dropdown")
    acc.click()
    page.locator(".p-dropdown-panel input.p-dropdown-filter").fill(account_text)
    page.locator(f".p-dropdown-items li[role='option'] >> text='{account_text}'").click()

    page.locator("tr:last-child td:nth-child(3) textarea").fill(description)
    page.locator("tr:last-child td:nth-child(4) input").fill(str(amount))


# ------------------------------------------------------
# MAIN WORKFLOW
# ------------------------------------------------------
with sync_playwright() as p:

    # 1️⃣ LOGIN
    browser, page = login(p, browser_name="chrome", environment="QA")

    # 2️⃣ NAVIGATE → New Transaction
    new_transaction(page)

    # 3️⃣ CLICK NEW PAYMENT
    page.locator("a.link:has-text('New payment')").click()
    time.sleep(1)
    print("➡️ New payment clicked")

    # 4️⃣ SELECT CONTACT
    page.locator("input[placeholder='Search Contact']").fill("Heather2234")
    page.locator("ul#Contact_list li").filter(has_text="Heather2234").first.click()
    print("➡️ Contact selected")

    # 5️⃣ MULTIPLE LINE ITEMS
    line_items = [
        {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1000},
        {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1030},
        {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1400},
        {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1500},
    ]

    print("➡️ Line items prepared")

    # FIRST ROW
    first = line_items[0]
    fill_first_row(page, first["payment_mode"], first["account_text"], first["amount"], "Auto Line 1")
    print("➡️ First row added")

    # EXTRA ROWS
    for i, item in enumerate(line_items[1:], start=2):
        add_payment_line(page, item["payment_mode"], item["account_text"], item["amount"], f"Auto Line {i}")
        print(f"➡️ Row {i} added")

    # 6️⃣ HEADER DETAILS
    page.fill("input[formcontrolname='Reference']", "REF-001")
    page.fill("textarea[formcontrolname='Description']", "Automated payment entry")
    print("➡️ Header filled")

    # 7️⃣ SAVE
    page.locator("button:has-text('Save As Draft')").click()
    time.sleep(1)
    print("➡️ Save As Draft clicked")

    # 8️⃣ POST
    page.locator("button:has-text('Save & Post')").click()
    time.sleep(2)
    print("➡️ Save & Post clicked")

    # 9️⃣ DETECT FEEDBACK
    detect_feedback(page)

    print("✅ Workflow completed")

    page.wait_for_timeout(3000)
