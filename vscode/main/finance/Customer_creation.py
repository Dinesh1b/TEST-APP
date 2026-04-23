# customer_creation.py

import os
import re
import sys
import random
import string
from typing import List
from playwright.sync_api import sync_playwright, TimeoutError



# ------------------------------
# PATH SETUP
# ------------------------------
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login

# ------------------------------
# RANDOM DATA GENERATORS
# ------------------------------
def random_first_name():
    return ''.join(random.choices(string.ascii_letters, k=6)).capitalize()

def random_last_name():
    return ''.join(random.choices(string.ascii_letters, k=7)).capitalize()

def random_mobile_no():
    return random.choice("6789") + ''.join(random.choices("0123456789", k=9))

def wait_and_fill(locator, text, timeout=3000):
    locator.wait_for(state="visible", timeout=timeout)
    locator.fill(text)
# ------------------------------
# COMMON UTILS
# ------------------------------
def try_click_any(page, selector_exprs: List[str], timeout: int = 3000) -> bool:
    for sel in selector_exprs:
        try:
            loc = page.locator(sel)
            loc.wait_for(state="visible", timeout=timeout)
            loc.click()
            return True
        except Exception:
            continue
    return False



def select_pdropdown_by_label(page, label_text: str, option_text: str, timeout=7000):
    """
    Stable PrimeNG dropdown selector using label text (NO dynamic IDs)
    """
    dropdown = page.locator(
        f"label:has-text('{label_text}') >> xpath=../..//span[@role='combobox']"
    )
    dropdown.wait_for(state="visible", timeout=timeout)
    dropdown.click()

    option = page.locator(
        f"li.p-dropdown-item:has-text('{option_text}')"
    )
    option.wait_for(state="visible", timeout=timeout)
    option.click()

def select_pdropdown(page, dropdown_id, value):
    page.locator(f"span[aria-controls='{dropdown_id}_list']").click()
    page.get_by_role("option", name=value).click()

def select_pdropdown_by_label2(page, label_text, option_text):
    page.locator("label", has_text=label_text)\
        .locator("xpath=following-sibling::p-dropdown")\
        .get_by_role("combobox")\
        .click()

    page.get_by_role("option", name=option_text).click()



# ------------------------------
# CUSTOMER CREATION FLOW
# ------------------------------
def customer_creation(page):
    print("🚀 Customer creation started")

    # Dashboard
    page.locator("//img[contains(@src,'AppIcon.svg')]").wait_for()
    page.locator("//img[contains(@src,'AppIcon.svg')]").click()

    # Finance menu
    page.locator(
        "span.sidenav-link-text:has-text('Finance')"
    ).locator("xpath=..").wait_for()
    page.locator(
        "span.sidenav-link-text:has-text('Finance')"
    ).locator("xpath=..").click()

    # Customer menu
    page.locator("a:has(img[src*='customer.svg'])").first.wait_for()
    page.locator("a:has(img[src*='customer.svg'])").first.click()

    # Add Customer
    page.locator("button:has-text('Add Customer')").wait_for()
    page.locator("button:has-text('Add Customer')").click()

    # ---------------- FORM DATA ----------------
    first_name = random_first_name()
    last_name = random_last_name()
    mobile_no = random_mobile_no()

    print(f"🧑 First Name : {first_name}")
    print(f"🧑 Last Name  : {last_name}")
    print(f"📱 Mobile     : {mobile_no}")

    # ---------------- TEXT INPUTS ----------------

    page.locator("input[formcontrolname='FirstName']").fill(first_name)
    page.locator("input[formcontrolname='LastName']").fill(last_name)
    page.locator("input[formcontrolname='AddressLine1']").fill("Address Line 1")
    page.locator("input[formcontrolname='City']").fill("Chennai")
    page.locator("input[formcontrolname='State']").fill("Tamil Nadu")
    page.locator("input[formcontrolname='PinCode']").fill("600001")
    

    # ---------------- DROPDOWNS ----------------
    
    



    select_pdropdown_by_label2(page, "Customer Type", "Individual")
    select_pdropdown_by_label(page, "Source", "Event")
    select_pdropdown_by_label(page, "Country", "India")
    select_pdropdown_by_label(page, "Contact Type", "Mobile")
    page.wait_for_load_state("networkidle")

    page.locator("div") \
    .filter(has_text=re.compile(r"^Contact Value \*$")) \
    .get_by_role("textbox") \
    .fill(mobile_no)

    page.get_by_role("button", name="    Add Contact").click()

    page.wait_for_timeout(300)

    # ---------------- SAVE ----------------
    page.locator("button:has-text('Save')").wait_for()
    page.locator("button:has-text('Save')").click()

    # ---------------- VALIDATION ----------------


# ------------------------------
# SCRIPT ENTRY POINT
# ------------------------------
if __name__ == "__main__":
    with sync_playwright() as p:
        browser, page = login(
            p,
            browser_name="chrome",
            environment="QA"
        )

        customer_creation(page)

        input("\nPress ENTER to close browser...")
        browser.close()
