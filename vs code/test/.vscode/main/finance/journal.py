#journal_ro
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
# Fill any journal row by index (1-based)
# ------------------------------------------------------
def fill_journal_row(page, row_index, account, description, debit, credit):
    row = f"tr.ng-star-inserted:nth-of-type({row_index})"


    # Account/Contact (search + select)
    acc_input = page.locator(f"{row} td:nth-child(1) input")
    acc_input.fill(account[:3])  # type a few chars to trigger suggestions
    time.sleep(1)
    page.wait_for_selector("ul li", state="visible", timeout=5000)
    page.locator(f"ul li:has-text('{account}')").first.click()
    time.sleep(1)


    # Description
    page.locator(f"{row} td:nth-child(2) textarea").fill(description)
    time.sleep(1)


    # Debit / Credit
    if debit:
        page.locator(f"{row} td:nth-child(3) input").fill(str(debit))
    if credit:
        page.locator(f"{row} td:nth-child(4) input").fill(str(credit))
    time.sleep(1)




# ------------------------------------------------------
# Add new journal row
# ------------------------------------------------------
def add_journal_line(page):
    add_line_btn = page.locator("button:has-text('Add Line')")
    add_line_btn.wait_for(state="visible")
    add_line_btn.click()
    time.sleep(1)  # ✅ wait after adding line




# ------------------------------------------------------
# MAIN SCRIPT
# ------------------------------------------------------
with sync_playwright() as p:
    print("🎬 Starting Playwright workflow...")

    # Step 1: Login
    browser, page = login(p, browser_name="chrome", environment="QA")

    # Step 2: Navigate to new transaction
    new_transaction(page)


    # NAVIGATE to Journal Voucher

    page.locator("a.link:has-text('New Journal')").click()
    time.sleep(2)
    page.wait_for_selector("input[formcontrolname='Reference']", timeout=10000)


    # HEADER INFO
    page.fill("input[formcontrolname='Reference']", "JV-002")
    time.sleep(1)
    page.fill("textarea[formcontrolname='Description']", "Automated Journal Voucher - 2 default rows")
    time.sleep(1)


    # JOURNAL LINES DATA
    journal_lines = [
        {"account": "Cash", "description": "Cash received", "debit": 1000, "credit": 0},
        {"account": "Sales", "description": "Sales revenue", "debit": 0, "credit": 1000},
        {"account": "Bank", "description": "Deposit to bank", "debit": 2000, "credit": 0},
        {"account": "Cash", "description": "Service revenue", "debit": 0, "credit": 2000},
    ]


    # Fill first two rows (default rows)
    print("🧾 Filling default rows...")
    fill_journal_row(page, 1, **journal_lines[0])
    fill_journal_row(page, 2, **journal_lines[1])


    # Add & fill additional rows
    print("➕ Adding and filling new rows...")
    for i, line in enumerate(journal_lines[2:], start=3):
        add_journal_line(page)
        time.sleep(1)  # ✅ wait after line creation
        fill_journal_row(page, i, **line)


    # SAVE ACTIONS
    page.locator("button:has-text('Save As Draft')").click()
    time.sleep(1)
    page.locator("button:has-text('Save & Post')").click()
    time.sleep(1)


    print("✅ Journal voucher created successfully with first 2 rows filled by default.")
    input("Press Enter to close the browser...")