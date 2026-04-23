# w_transaction.py
import os
import sys
from playwright.sync_api import sync_playwright
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# Now import login() correctly
from login.login import login
from time import sleep


def new_transaction(page):

    print("\n🔐 Navigation Started")

    # Dashboard
    page.locator("xpath=//img[contains(@src,'AppIcon.svg')]").click()
    sleep(1)

    # Finance Menu
    page.locator("span.sidenav-link-text:has-text('Finance')").locator("xpath=..").click()
    sleep(0.7)

    # Transaction Menu Icon
    page.locator("a:has(img[src*='Transaction_Icon.svg'])").first.click()
    sleep(0.7)

    # New Transaction
    page.locator("p.ms-1:has-text('New transaction')").click()
    sleep(1.5)

    print("➡️ Opened: Finance → Transaction → New Transaction")


# ============================================
# RUN SCRIPT (This must be EXACTLY like this)
# ============================================
if __name__ == "__main__":
    with sync_playwright() as p:

        # ⭐ login.py returns (browser, page)
        browser, page = login(
            p,
            browser_name="chrome",      # edge / chrome / firefox
            environment="QA"            # PRODUCTION / STAGING / QA / DEV
        )

        # ⭐ Only continue if login succeeded
        new_transaction(page)

        input("\nPress ENTER to close browser...")
        browser.close()
# test/.vscode/new_transaction.py