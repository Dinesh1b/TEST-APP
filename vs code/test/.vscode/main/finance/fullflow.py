#!/usr/bin/env python3
"""
Automated Playwright flows for customer -> receipt -> payment -> journal.

Notes:
- DEBUG prints removed per request; only INFO/WARN/ERROR/SUCCESS prints remain.
- Prints are forced to flush so output appears immediately.
- Risky blocks still wrapped to surface exceptions to stdout.
- Defaults: DRY_RUN=False, SEED=None (change at top if needed).
"""
import os
import sys
import random
import string
import time
import json
import traceback
import builtins
from typing import Optional, Callable, Any, List
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from time import sleep
from functools import wraps

# Force prints to flush to avoid buffering
_builtin_print = builtins.print
def _print_flush(*args, **kwargs):
    kwargs.setdefault("flush", True)
    return _builtin_print(*args, **kwargs)
print = _print_flush

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login
from login.popup_handler import detect_feedback
from login.logger_setup import mirrored_print
from excel_logger import write_log as _orig_write_log  # original excel writer

# ------------------------------
# Config / Defaults
# ------------------------------
MAX_JOURNAL_LINES = 4
DRY_RUN = False
SEED = None

# ------------------------------
# Helpers
# ------------------------------
def _safe_to_string(x: Any) -> str:
    try:
        return str(x)
    except Exception:
        pass
    try:
        return repr(x)
    except Exception:
        return "<unserializable-result>"

def try_click_any(page, selector_exprs: List[str], timeout: int = 2000, force_on_failure: bool = True) -> bool:
    """
    Try clicking the first selector that becomes visible from selector_exprs.
    Return True on success, False otherwise.
    """
    for sel in selector_exprs:
        try:
            loc = page.locator(sel)
            loc.wait_for(state="visible", timeout=timeout)
            try:
                loc.click(timeout=timeout)
            except Exception:
                if force_on_failure:
                    try:
                        loc.click(force=True, timeout=timeout)
                    except Exception:
                        continue
                else:
                    continue
            return True
        except Exception:
            continue
    return False

def write_log(*args, **kwargs) -> Optional[str]:
    """
    Call original excel writer but catch exceptions so it doesn't stop the flow.
    """
    parts = []
    if args:
        parts.append(" ".join(map(str, args)))
    if kwargs:
        kv = ", ".join(f"{k}={v!s}" for k, v in kwargs.items())
        parts.append(kv)
    msg = " | ".join(parts) if parts else "<no args>"

    print(f"INFO: write_log called: {msg}")
    try:
        excel_result = _orig_write_log(*args, **kwargs)
    except Exception as e:
        print(f"WARN: excel write failed: {_safe_to_string(e)}")
        return None

    excel_str = _safe_to_string(excel_result)
    if isinstance(excel_result, str):
        print(f"INFO: LOG: {msg} | excel_path={excel_result}")
    else:
        print(f"INFO: LOG: {msg} | excel_result={excel_str}")
    return excel_result

def _rng(seed: Optional[int] = None) -> random.Random:
    r = random.Random()
    if seed is not None:
        r.seed(seed)
    return r

def random_first_name(seed: Optional[int] = None):
    r = _rng(seed)
    return ''.join(r.choices(string.ascii_lowercase, k=6)).capitalize()

def random_last_name(seed: Optional[int] = None):
    r = _rng(seed)
    return ''.join(r.choices(string.ascii_lowercase, k=7)).capitalize()

def random_mobile(seed: Optional[int] = None):
    r = _rng(seed)
    first_digit = r.choice("6789")
    remaining = ''.join(r.choices("0123456789", k=9))
    return first_digit + remaining

def wait_and_click(locator, timeout=7000, force=False):
    try:
        locator.wait_for(state="visible", timeout=timeout)
        try:
            locator.click(timeout=timeout)
        except Exception:
            if force:
                locator.click(force=True, timeout=timeout)
            else:
                raise
    except PWTimeout as te:
        print(f"ERROR: wait_and_click -> timeout waiting for locator: {_safe_to_string(te)}")
        raise

def wait_and_fill(locator, text, timeout=3000):
    locator.wait_for(state="visible", timeout=timeout)
    locator.fill(text)

def retry(max_attempts: int = 3, delay: float = 0.5, backoff: float = 1.5):
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*a, **kw):
            last_ex = None
            _delay = delay
            for i in range(1, max_attempts + 1):
                try:
                    return fn(*a, **kw)
                except Exception as e:
                    last_ex = e
                    time.sleep(_delay)
                    _delay *= backoff
            raise last_ex
        return wrapper
    return decorator

def safe_locator_count(locator):
    try:
        return locator.count()
    except Exception:
        return 0

# ------------------------------
# Autocomplete helpers
# ------------------------------
def type_and_select(page, input_selector: str, text: str, dropdown_item_selector: str = "ul li", min_chars: int = 2, timeout=7000) -> bool:
    input_el = page.locator(input_selector)
    input_el.wait_for(state="visible", timeout=timeout)
    input_el.fill("")
    to_type = text if len(text) >= min_chars else text + (" " * (min_chars - len(text)))
    input_el.type(to_type, delay=50)
    page.wait_for_timeout(300)

    items = page.locator(dropdown_item_selector, has_text=text)
    if safe_locator_count(items) > 0:
        items.first.click()
        return True

    items_any = page.locator(dropdown_item_selector, has_text=text[:min_chars])
    if safe_locator_count(items_any) > 0:
        items_any.first.click()
        return True

    return False

def select_pdropdown(page, list_id: str, option_text: str, timeout=7000):
    opener_selector = f"span[role='combobox'][aria-controls='{list_id}']"
    clicked = try_click_any(page, [opener_selector])
    if not clicked:
        raise Exception(f"Combobox opener not clickable for list_id='{list_id}'")
    option_selector = f"ul#{list_id} li.p-dropdown-item:has-text('{option_text}')"
    page.locator(option_selector).wait_for(state="visible", timeout=timeout)
    page.locator(option_selector).click()
    return True

# ------------------------------
# Payment helpers
# ------------------------------
def fill_first_row(page, payment_mode, account_text, amount, description):
    pm = page.locator("tr.ng-star-inserted:first-of-type td:nth-child(1) span[role='combobox']").first
    wait_and_click(pm)
    page.locator(f"li[role='option'] >> text='{payment_mode}'").first.click()

    acc = page.locator("tr.ng-star-inserted:first-of-type td:nth-child(2) p-dropdown").first
    wait_and_click(acc)
    filter_input = page.locator(".p-dropdown-panel input.p-dropdown-filter")
    if safe_locator_count(filter_input) > 0:
        filter_input.fill(account_text)
        page.locator(f".p-dropdown-items li[role='option'] >> text='{account_text}'").first.click()
    else:
        page.locator(f".p-dropdown-items li[role='option'] >> text='{account_text}'").first.click()

    page.locator("tr.ng-star-inserted:first-of-type td:nth-child(3) textarea").first.fill(description)
    page.locator("tr.ng-star-inserted:first-of-type td:nth-child(4) input").first.fill(str(amount))

def add_payment_line(page, payment_mode, account_text, amount, description):
    try:
        page.locator("button:has-text('Add Line')").first.click()
        page.wait_for_timeout(500)
    except Exception as e:
        print(f"WARN: add_payment_line -> failed to click Add Line: {_safe_to_string(e)}")
        return

    pm = page.locator("tr:last-child td:nth-child(1) span[role='combobox']").last
    wait_and_click(pm)
    page.locator(f"li[role='option'] >> text='{payment_mode}'").last.click()

    acc = page.locator("tr:last-child td:nth-child(2) p-dropdown").last
    wait_and_click(acc)
    filter_input = page.locator(".p-dropdown-panel input.p-dropdown-filter")
    if safe_locator_count(filter_input) > 0:
        filter_input.fill(account_text)
        page.locator(f".p-dropdown-items li[role='option'] >> text='{account_text}'").last.click()
    else:
        page.locator(f".p-dropdown-items li[role='option'] >> text='{account_text}'").last.click()

    page.locator("tr:last-child td:nth-child(3) textarea").last.fill(description)
    page.locator("tr:last-child td:nth-child(4) input").last.fill(str(amount))

# ------------------------------
# Journal helpers
# ------------------------------
def fill_selector_field(page, row: str, col: int, value: Optional[str], is_textarea: bool = False):
    if not value:
        return
    selector = f"{row} td:nth-child({col}) {'textarea' if is_textarea else 'input'}"
    el = page.locator(selector)
    el.wait_for(state="visible", timeout=3000)
    el.fill(value)
    page.wait_for_timeout(120)

def select_contact_in_row(page, row_index: int, contact_name: str, col: int = 1):
    row = f"tr.ng-star-inserted:nth-of-type({row_index})"
    selector = f"{row} td:nth-child({col}) input"
    ok = type_and_select(page, selector, contact_name, min_chars=2, dropdown_item_selector="ul li")
    if not ok:
        page.locator(selector).fill(contact_name)

def fill_journal_row(page, row_index, account=None, description=None, debit=None, credit=None, contact=None):
    """
    Fill the given row. Supports 'account' or 'contact'.
    Reduced prints: only WARN/ERROR/SUCCESS messages.
    """
    row = f"tr.ng-star-inserted:nth-of-type({row_index})"

    if contact:
        sel = f"{row} td:nth-child(1) input"
        ok = type_and_select(page, sel, contact, dropdown_item_selector="ul li")
        if not ok:
            page.locator(sel).fill(contact)
        time.sleep(0.5)

    elif account:
        try:
            acc_input = page.locator(f"{row} td:nth-child(1) input")
            acc_input.wait_for(state="visible", timeout=5000)
            acc_input.fill(account[:3])
            page.wait_for_timeout(300)

            options = page.locator("ul li").filter(has_text=account)
            try:
                count = options.count()
            except Exception:
                count = 0

            if count == 0:
                options = page.locator("ul li").filter(has_text=account[:3])
                try:
                    count = options.count()
                except Exception:
                    count = 0

            if count > 0:
                options.nth(0).click()
            else:
                print(f"WARN: No matching account option found for '{account}'")
        except Exception as e:
            print(f"ERROR: fill_journal_row -> exception during account selection: {_safe_to_string(e)}")
            traceback.print_exc()

    # Description
    if description:
        try:
            desc_sel_textarea = f"{row} td:nth-child(2) textarea"
            desc_sel_input = f"{row} td:nth-child(2) input"
            if try_click_any(page, [desc_sel_textarea], timeout=300, force_on_failure=False):
                page.locator(desc_sel_textarea).fill(description)
            else:
                page.locator(desc_sel_input).fill(description)
        except Exception as e:
            print(f"ERROR: fill_journal_row -> exception during description fill: {_safe_to_string(e)}")
            traceback.print_exc()
    page.wait_for_timeout(250)

    # Debit / Credit
    try:
        if debit:
            page.locator(f"{row} td:nth-child(3) input").fill(str(debit))
        if credit:
            page.locator(f"{row} td:nth-child(4) input").fill(str(credit))
    except Exception as e:
        print(f"ERROR: fill_journal_row -> exception setting debit/credit: {_safe_to_string(e)}")
        traceback.print_exc()

def add_journal_line(page):
    try:
        add_line_btn = page.locator("button:has-text('Add Line')")
        add_line_btn.wait_for(state="visible")
        add_line_btn.click()
        time.sleep(0.6)
    except Exception as e:
        print(f"ERROR: add_journal_line -> failed: {_safe_to_string(e)}")
        traceback.print_exc()

def save_journal(page, dry_run: bool = False):
    try:
        page.locator("button:has-text('Save As Draft')").first.click()
        page.wait_for_timeout(350)
    except Exception as e:
        print(f"WARN: save_journal -> Save As Draft click failed: {_safe_to_string(e)}")
        traceback.print_exc()
        return

    if dry_run:
        print("INFO: Dry run enabled — skipping 'Save & Post'.")
        return

    try:
        page.locator("button:has-text('Save & Post')").first.click()
        page.wait_for_timeout(800)
    except Exception as e:
        print(f"WARN: save_journal -> Save & Post click failed: {_safe_to_string(e)}")
        traceback.print_exc()

# ------------------------------
# Customer flow
# ------------------------------
def customer_creation(page, seed: Optional[int] = None) -> str:
    print("\n============================")
    print("STEP 1: CUSTOMER CREATION")
    print("============================\n")
    print("INFO: Navigating to Finance module...")

    page.locator("xpath=//img[contains(@src,'AppIcon.svg')]").first.wait_for(state="visible", timeout=7000)
    page.locator("xpath=//img[contains(@src,'AppIcon.svg')]").first.click()
    page.wait_for_timeout(600)

    print("INFO: Opening Customer module...")
    finance = page.locator("span.sidenav-link-text:has-text('Finance')").first
    finance.locator("xpath=..").click()
    page.wait_for_timeout(600)
    page.locator("a:has(img[src*='customer.svg'])").first.click()
    page.wait_for_timeout(600)

    page.locator("button:has-text('Add Customer')").click()
    page.wait_for_timeout(800)

    first_name = random_first_name(seed)
    last_name = random_last_name(seed)
    mobile_no = random_mobile(seed)
    print(f"INFO: Generated -> {first_name} {last_name}, Mobile: {mobile_no}")

    wait_and_fill(page.locator("input[formcontrolname='FirstName']"), first_name)
    wait_and_fill(page.locator("input[formcontrolname='LastName']"), last_name)
    page.locator("input[formcontrolname='AddressLine1']").fill("Address Line 1")
    page.locator("input[formcontrolname='City']").fill("Chennai")
    page.locator("input[formcontrolname='State']").fill("Tamil Nadu")
    page.locator("input[formcontrolname='PinCode']").fill("600001")

    select_pdropdown(page, "pn_id_44_list", "India")
    page.wait_for_timeout(300)
    select_pdropdown(page, "pn_id_46_list", "Mobile")
    page.wait_for_timeout(200)
    wait_and_fill(page.locator("input[placeholder='Contact Value']"), mobile_no)
    page.wait_for_timeout(200)
    select_pdropdown(page, "pn_id_40_list", "Individual")
    page.wait_for_timeout(300)

    page.locator("button:has-text('Add Contact')").click()
    page.wait_for_timeout(300)

    page.locator("button:has-text('Save')").click()
    page.wait_for_timeout(1200)
    print("SUCCESS: Customer created ✔")

    write_log("customer_created", first_name=first_name, last_name=last_name, mobile=mobile_no)
    return first_name

# ------------------------------
# Receipt flow (robust selector)
# ------------------------------
def create_receipt_and_select_contact(page, contact_name: str):
    print("\n============================")
    print("STEP 2: CREATE RECEIPT")
    print("============================\n")
    print(f"INFO: Starting receipt creation for contact: {contact_name}")

    back_btn = page.locator("button:has-text('Back')")
    if safe_locator_count(back_btn) > 0:
        back_btn.first.wait_for(state="visible", timeout=3000)
        back_btn.first.click()
        page.wait_for_timeout(400)

    page.locator("a:has(img[src*='Transaction_Icon.svg'])").first.wait_for(state="visible", timeout=7000)
    page.locator("a:has(img[src*='Transaction_Icon.svg'])").first.click()
    page.wait_for_timeout(600)
    page.locator("p.ms-1:has-text('New transaction')").first.click()
    page.wait_for_timeout(800)
    page.locator("a.link:has-text('New Receipt')").first.click()
    page.wait_for_timeout(800)

    search_input = page.locator("input[placeholder='Search Contact']")
    search_input.wait_for(state="visible", timeout=7000)
    search_input.fill(contact_name)
    page.wait_for_timeout(800)   # give UI time to render dropdown

    try:
        options = page.locator("li[role='option']").filter(has_text=contact_name)
        if safe_locator_count(options) > 0:
            options.first.click()
        else:
            panel_options = page.locator(".p-autocomplete-panel li").filter(has_text=contact_name)
            if safe_locator_count(panel_options) > 0:
                panel_options.first.click()
            else:
                contact_list_items = page.locator("ul#Contact_list li").filter(has_text=contact_name)
                if safe_locator_count(contact_list_items) > 0:
                    contact_list_items.first.click()
                else:
                    generic_items = page.locator("li").filter(has_text=contact_name)
                    if safe_locator_count(generic_items) > 0:
                        generic_items.first.click()
                    else:
                        print("WARN: No dropdown appeared. Typing contact name directly as fallback.")
                        search_input.fill(contact_name)
    except Exception as e:
        print(f"ERROR: create_receipt_and_select_contact -> selection exception: {_safe_to_string(e)}")
        traceback.print_exc()

    print(f"INFO: Contact selection step complete for Receipt (contact={contact_name}).")

    try:
        page.fill("input[formcontrolname='Reference']", "REC-001")
    except Exception:
        pass
    if safe_locator_count(page.locator("input[formcontrolname='PaymentDate']")) > 0:
        try:
            page.fill("input[formcontrolname='PaymentDate']", time.strftime("%Y-%m-%d"))
        except Exception:
            pass

    line_items = [
        {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1000},
        {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1030},
        {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1000},
        {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1030},
    ]
    fill_first_row(page, **line_items[0], description="Receipt Line 1")
    for i, item in enumerate(line_items[1:], start=2):
        add_payment_line(page, **item, description=f"Receipt Line {i}")

    try:
        page.fill("textarea[formcontrolname='Description']", "Auto-created receipt")
    except Exception:
        pass

    try:
        page.locator("button:has-text('Save As Draft')").first.click()
        detect_feedback(page)
        print("SUCCESS: Receipt saved as draft")
        write_log("receipt_saved_draft", contact=contact_name, ref="REC-001")
    except Exception as e:
        print(f"WARN: Could not save receipt as draft: {_safe_to_string(e)}")
        traceback.print_exc()

# ------------------------------
# Payment flow
# ------------------------------
def create_payment_and_select_contact(page, contact_name: str):
    print("\n============================")
    print("STEP 3: CREATE PAYMENT")
    print("============================\n")
    print(f"INFO: Starting payment creation for contact: {contact_name}")

    back_btn = page.locator("button:has-text('Back')")
    if safe_locator_count(back_btn) > 0:
        back_btn.first.wait_for(state="visible", timeout=3000)
        back_btn.first.click()
        page.wait_for_timeout(400)

    page.locator("a:has(img[src*='Transaction_Icon.svg'])").first.wait_for(state="visible", timeout=7000)
    page.locator("a:has(img[src*='Transaction_Icon.svg'])").first.click()
    page.wait_for_timeout(600)
    page.locator("p.ms-1:has-text('New transaction')").first.click()
    page.wait_for_timeout(800)
    page.locator("a.link:has-text('New Payment')").first.click()
    page.wait_for_timeout(800)

    search_input = page.locator("input[placeholder='Search Contact']")
    search_input.wait_for(state="visible", timeout=7000)
    search_input.fill(contact_name)
    page.wait_for_timeout(600)

    results = page.locator("ul#Contact_list li", has_text=contact_name)
    if safe_locator_count(results) > 0:
        results.first.click()
    else:
        try:
            generic = page.locator("li", has_text=contact_name)
            generic.first.wait_for(state="visible", timeout=4000)
            generic.first.click()
        except Exception as e:
            print(f"WARN: payment contact selection failed: {_safe_to_string(e)}")
            traceback.print_exc()

    try:
        page.fill("input[formcontrolname='Reference']", "PAY-001")
    except Exception:
        pass
    if safe_locator_count(page.locator("p-dropdown[formcontrolname='PaymentAccount']")) > 0:
        try:
            page.locator("p-dropdown[formcontrolname='PaymentAccount']").first.click()
            page.locator(".p-dropdown-items li[role='option']").first.click()
        except Exception:
            pass

    line_items = [
        {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1000},
        {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1030},
        {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1000},
        {"payment_mode": "Cash Payment", "account_text": "Cash", "amount": 1030},
    ]
    fill_first_row(page, **line_items[0], description="Payment Line 1")
    for i, item in enumerate(line_items[1:], start=2):
        add_payment_line(page, **item, description=f"Payment Line {i}")

    try:
        page.fill("textarea[formcontrolname='Description']", "Auto-created payment")
    except Exception:
        pass

    try:
        page.locator("button:has-text('Save As Draft')").first.click()
        detect_feedback(page)
        print("SUCCESS: Payment saved as draft")
        write_log("payment_saved_draft", contact=contact_name, ref="PAY-001")
    except Exception as e:
        print(f"WARN: Could not save payment as draft: {_safe_to_string(e)}")
        traceback.print_exc()

# ------------------------------
# Journal flow
# ------------------------------
def create_journal_with_contact(page, generated_first_name, max_lines: int = MAX_JOURNAL_LINES, dry_run: bool = DRY_RUN):
    print("\n============================")
    print("STEP 4: CREATE JOURNAL")
    print("============================\n")
    print(f"INFO: Starting Journal creation using contact: {generated_first_name}")

    page.locator("a:has(img[src*='Transaction_Icon.svg'])").first.wait_for(state="visible", timeout=7000)
    page.locator("a:has(img[src*='Transaction_Icon.svg'])").first.click()
    page.wait_for_timeout(600)
    page.locator("p.ms-1:has-text('New transaction')").first.click()
    page.wait_for_timeout(800)
    page.locator("a.link:has-text('New Journal')").first.click()
    page.wait_for_selector("input[formcontrolname='Reference']", timeout=10000)

    try:
        page.fill("input[formcontrolname='Reference']", "JV-002")
        page.fill("textarea[formcontrolname='Description']", "Automated Journal Voucher with generated contact")
    except Exception:
        pass

    journal_lines: List[dict] = [
        {"account": "Cash",  "description": "Cash received",      "debit": 1000, "credit": 0},
        {"contact": generated_first_name, "description": "Sales revenue",      "debit": 0,    "credit": 1000},
        {"account": "Cash",  "description": "Deposit to bank",    "debit": 2000, "credit": 0},
        {"contact": generated_first_name,  "description": "Service revenue",    "debit": 0,    "credit": 2000},
    ]

    fill_journal_row(page, 1, **journal_lines[0])
    fill_journal_row(page, 2, **journal_lines[1])

    for i, line in enumerate(journal_lines[2:], start=3):
        if i > max_lines:
            break
        add_journal_line(page)
        time.sleep(0.6)
        fill_journal_row(page, i, **line)

    save_journal(page, dry_run=dry_run)
    detect_feedback(page)
    print("SUCCESS: Journal created")
    write_log("journal_created", contact=generated_first_name, ref="JV-002")

# ------------------------------
# Main 
# ------------------------------
if __name__ == "__main__":
    print("INFO: Script started")
    if SEED is not None:
        print(f"INFO: Using seed={SEED} for deterministic names")

    with sync_playwright() as p:
        print("INFO: Launching browser and logging in...")
        browser, page = login(
            p,
            browser_name="chrome",
            environment="QA"
        )
        print("INFO: Logged in — starting automation flows\n")

        # create customer and get generated first name
        generated_first_name = customer_creation(page, seed=SEED)

        # use that generated name to select contact in New Receipt
        create_receipt_and_select_contact(page, generated_first_name)

        # use that generated name to select contact in New Payment
        create_payment_and_select_contact(page, generated_first_name)

        # use that generated name to select contact in New journal
        create_journal_with_contact(page, generated_first_name, max_lines=MAX_JOURNAL_LINES, dry_run=DRY_RUN)

        print("INFO: Flows finished — cleaning up")
        try:
            input("\nPress ENTER to close browser...")
        except Exception:
            print("DEBUG: Input blocked or not available; proceeding to close browser")
        browser.close()
        print("INFO: Browser closed. Script complete.")
