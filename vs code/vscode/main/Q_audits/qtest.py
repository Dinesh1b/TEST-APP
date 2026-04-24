"""
QR scanner automation (Playwright native keyboard — Angular/PrimeNG compatible)

Flow:
- Read scan codes from Excel
- Focus item code input on audit page
- Type each code via Playwright's real keyboard API (page.keyboard.type)
  → Angular NgZone sees these events → PrimeNG autocomplete fires
- Wait for dropdown panel to confirm autocomplete triggered
- Press Enter to submit each scan
- Let Continuous Count process quantity / new-row / reset

Why native keyboard instead of hid_wedge (JS evaluate):
- JS evaluate fires events INSIDE the page context but OUTSIDE Angular's zone patch.
  NgZone never sees them → no change detection → dropdown never appears.
- page.keyboard.type() goes through Playwright's CDP layer, which the browser
  treats as genuine hardware input. Angular's zone intercepts it properly.
"""

import os
import sys

import pandas as pd
from playwright.sync_api import sync_playwright

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login
from login.popup_handler import detect_feedback


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
class Config:
    DEFAULT_TIMEOUT   = 10_000
    WAIT_AFTER_ACTION = 400          # ms between scans
    TYPE_DELAY_MS     = 30           # ms between keystrokes (mimics scanner burst)

    email     = None
    password  = None
    email2    = "yoiffoweuroipre-7178@yopmail.com"
    password2 = "MeNx6G2S"

    browsername  = "chrome"
    environments = "PRODUCTION"
    Branch       = "nm"

    audit_name = "Audit_8L38ZF_2"
    AUDIT_URL  = "https://app.stockount.com/home/audit/16f32e1b-c0ed-43f8-9474-08de92d69397/stock"

    EXCEL_PATH     = r"C:\Users\HP\Documents\input\scan.xlsx"
    EXCEL_SHEET    = "Sheet1"
    EXCEL_CODE_COL = "code"

    run_Q_SA1 = True


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEL LOADER
# ═══════════════════════════════════════════════════════════════════════════════
def load_scan_codes(config) -> list:
    path = config.EXCEL_PATH
    if not os.path.exists(path):
        print(f"❌ Excel not found: {path}")
        sys.exit(1)

    df  = pd.read_excel(path, sheet_name=config.EXCEL_SHEET)
    col = config.EXCEL_CODE_COL

    if col not in df.columns:
        print(f"❌ Column '{col}' missing — found: {list(df.columns)}")
        sys.exit(1)

    codes = []
    for _, row in df.iterrows():
        code = str(row.get(col, "")).strip()
        if code and code != "nan":
            codes.append(code.upper())

    if not codes:
        print("⚠   No valid codes found.")
    return codes


# ═══════════════════════════════════════════════════════════════════════════════
# NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════════
def select_branch(page, branch_text: str) -> None:
    dropdown = page.locator(
        "xpath=/html/body/app-root/app-layout/div/app-header"
        "/div[1]/div[2]/div[2]//p-dropdown"
    )
    dropdown.wait_for(state="visible", timeout=30_000)
    dropdown.locator(".p-dropdown-label").click()
    panel = page.locator(".p-dropdown-panel").last
    panel.wait_for(state="visible", timeout=30_000)
    search = panel.locator("input.p-dropdown-filter")
    if search.count() > 0:
        search.fill("")
        search.fill(branch_text)
        page.wait_for_timeout(300)
    option = panel.locator("li.p-dropdown-item", has_text=branch_text)
    if option.count() == 0:
        raise Exception(f"❌ Branch not found: {branch_text}")
    option.first.click()
    panel.wait_for(state="hidden", timeout=30_000)


def enable_continuous_count(page) -> None:
    toggle_root  = page.locator("p-inputswitch").first
    hidden_input = toggle_root.locator("input[role='switch']").first
    if hidden_input.get_attribute("aria-checked") == "true":
        print("ℹ️  Continuous Count already ON")
        return
    toggle_root.locator("span.p-inputswitch-slider").click()
    page.wait_for_timeout(400)
    if hidden_input.get_attribute("aria-checked") != "true":
        hidden_input.evaluate("""el => {
            el.checked = true;
            el.dispatchEvent(new Event('input',  { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""")
        page.wait_for_timeout(300)
    print("✅ Continuous Count ON")


def navigate_to_audit(page, config) -> None:
    print("📂 Navigating to audit...")

    if config.AUDIT_URL:
        page.goto(config.AUDIT_URL, wait_until="networkidle")
        print("✅ Direct URL loaded")
    else:
        select_branch(page, config.Branch)
        page.wait_for_selector("a[href='/home/audit']", state="visible")
        page.click("a[href='/home/audit']")
        page.wait_for_load_state("networkidle")
        row = page.locator(
            f"table tbody tr:has(td span:has-text('{config.audit_name}'))"
        ).first
        row.locator("td span").first.click()
        page.wait_for_load_state("networkidle")
        print(f"✅ Audit opened: {config.audit_name}")

    enable_continuous_count(page)
    detect_feedback(page)


# ═══════════════════════════════════════════════════════════════════════════════
# PLAYWRIGHT NATIVE KEYBOARD  (replaces hid_wedge)
# ═══════════════════════════════════════════════════════════════════════════════
def native_type(page, text: str, delay_ms: int = 30) -> None:
    """
    Type text via Playwright's CDP keyboard layer.

    This is the correct approach for Angular + PrimeNG:
    - Playwright routes keystrokes through Chrome DevTools Protocol
    - The browser treats them as real hardware input
    - Angular's NgZone monkey-patches addEventListener at startup,
      so it intercepts these events and triggers change detection
    - PrimeNG's autocomplete completeMethod fires on each keyup
    - The dropdown panel appears as expected

    delay_ms=30 mimics a USB HID scanner burst (~33 chars/sec).
    If the dropdown still doesn't appear, raise to 50ms — some
    PrimeNG builds debounce on the keyup handler.
    """
    page.keyboard.type(text, delay=delay_ms)


# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH ITEM
# ═══════════════════════════════════════════════════════════════════════════════
def search_item(page, item_code: str, config) -> bool:
    """
    Full scan flow for one code:
      1. Locate and focus the Item Code autocomplete input
      2. Clear any existing value
      3. Type via Playwright native keyboard (triggers Angular zone + PrimeNG)
      4. Wait for dropdown panel to confirm autocomplete fired
      5. Press Enter to submit
    """
    try:
        ac = page.locator(
            "input.p-autocomplete-input[placeholder*='Item Code']"
        ).first
        ac.scroll_into_view_if_needed()
        ac.wait_for(state="visible", timeout=7_000)

        # Remove readonly attribute and focus (safe — JS eval here doesn't
        # trigger Angular, which is exactly what we want at this stage)
        ac.evaluate("""el => {
            el.removeAttribute('readonly');
            el.focus();
        }""")

        # Clear any existing text with Ctrl+A → Delete
        page.keyboard.press("Control+A")
        page.keyboard.press("Delete")

        # Type via real Playwright keyboard — Angular NgZone intercepts this
        native_type(page, item_code, delay_ms=config.TYPE_DELAY_MS)

        # Wait for PrimeNG dropdown panel to appear (proves autocomplete fired)
        # If this times out, the code isn't found in the system — we still
        # submit with Enter and let the app handle the error state.
        try:
            page.wait_for_selector(
                ".p-autocomplete-panel",
                state="visible",
                timeout=3_000,
            )
            print(f"  [dropdown] panel appeared for {item_code}")
        except Exception:
            print(f"  [warn] no dropdown for {item_code} — submitting anyway")

        # Submit — acts as the scanner's Enter terminator
        page.keyboard.press("Enter")

        page.wait_for_timeout(450)
        detect_feedback(page)
        return True

    except Exception as exc:
        print(f"  [scan-error] {item_code}: {exc}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# PROCESS SCAN
# ═══════════════════════════════════════════════════════════════════════════════
def process_scan(page, code: str, scan_dict: dict, config) -> bool:
    """
    Submit one scan code and track count for final report.
    No manual qty / add-count / clear-form steps — Continuous Count handles all.
    """
    if not search_item(page, code, config):
        print(f"  [skip] scanner submit failed for {code}")
        return False

    scan_dict[code] = scan_dict.get(code, 0) + 1
    print(f"  [ok] {code} submitted ({scan_dict[code]}x)")
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SCAN LOOP
# ═══════════════════════════════════════════════════════════════════════════════
def Q_SA1(page, config) -> None:
    navigate_to_audit(page, config)

    codes = load_scan_codes(config)
    total = len(codes)

    # Preview unique code counts
    preview: dict = {}
    for c in codes:
        preview[c] = preview.get(c, 0) + 1

    print(f"\n📋 {total} scan(s)  →  {len(preview)} unique code(s)\n{'─'*52}")
    for i, code in enumerate(codes, 1):
        print(f"   [{i:>2}] {code}")
    print()

    scan_dict: dict = {}
    ok_count   = 0
    fail_count = 0

    for idx, code in enumerate(codes, start=1):
        print(f"\n[{idx:>3}/{total}]  {code:<20}  (scan)")

        if process_scan(page, code, scan_dict, config):
            ok_count += 1
        else:
            fail_count += 1

        page.wait_for_timeout(config.WAIT_AFTER_ACTION)

    # Final report
    print(f"\n{'═'*52}")
    print("📊 Session Complete — final scan_dict:")
    print(f"   {'Code':<20}  {'Qty':>6}")
    print(f"   {'─'*20}  {'─'*6}")
    for code, qty in scan_dict.items():
        print(f"   {code:<20}  {qty:>6}")
    print(f"\n   ✅ {ok_count} succeeded  ❌ {fail_count} failed  📦 {total} total")
    print(f"{'═'*52}")


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    with sync_playwright() as p:

        browser, page = login(
            p,
            browser_name = Config.browsername,
            environment  = Config.environments,
            email        = Config.email,
            password     = Config.password,
        )
        page.set_default_timeout(30_000)

        
        if Config.run_Q_SA1:
            same_creds = ((Config.email or "") == (Config.email2 or "") and (Config.password or "") == (Config.password2 or ""))
            if not same_creds:
                browser.close()
                browser, page = login(
                    p,
                    browser_name=Config.browsername,
                    environment=Config.environments,
                    email=Config.email2,
                    password=Config.password2,
                )
                page.set_default_timeout(30_000)
        else:
            print("❌ Q_SA1 skipped")
