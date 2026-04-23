import sys
import os
import time
from datetime import datetime
from typing import Dict
from playwright.sync_api import sync_playwright, Page

# ======================================================
# CONFIG
# ======================================================
DRY_RUN = False
ENABLE_REPORTING = True
CI_MODE = os.getenv("CI") is not None

# ======================================================
# PATH SETUP
# ======================================================
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login
from login.popup_handler import detect_feedback

if ENABLE_REPORTING:
    try:
        from utils.enhanced_report_generator import AutomationReporter
    except ImportError:
        print("⚠ AutomationReporter not found. Reporting disabled.")
        ENABLE_REPORTING = False


# ======================================================
# EXPECTED DATA
# ======================================================
EXPECTED_ROW = {
    "Audit Name": "Audit_PWDNZ5_1",
    "Type": "Complete Count",
    "Audited / Total Line Item": "0 / 10",
    "Audited / Total Qty": "0 / 100",
    "Matched LineItem": "0",
    "Shortfall LineItem": "0",
    "Excess LineItem": "0",
    "Status": "Not Started"
}


# ======================================================
# NAVIGATION
# ======================================================
def navigate_to_ongoing_audits(page: Page):
    page.click("a[href='#/home/audit']")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("tbody tr", timeout=10000)


# ======================================================
# HEADER MAPPING
# ======================================================
def get_column_index_map(page: Page) -> Dict[str, int]:
    headers = page.locator("thead th")
    header_map = {}
    for i in range(headers.count()):
        header_text = headers.nth(i).inner_text().strip()
        header_map[header_text] = i
    return header_map


# ======================================================
# FETCH ROW DATA
# ======================================================
def get_audit_row_data(page: Page, audit_name: str) -> Dict[str, str]:

    page.wait_for_selector("tbody tr", timeout=10000)
    header_map = get_column_index_map(page)

    row = page.locator(
        f"tbody tr:has(td:has-text('{audit_name}'))"
    )

    if row.count() == 0:
        raise Exception(f"Audit row '{audit_name}' not found")

    row = row.first
    cells = row.locator("td")

    actual_data = {}

    for column_name in EXPECTED_ROW.keys():
        if column_name in header_map:
            index = header_map[column_name]
            actual_data[column_name] = cells.nth(index).inner_text().strip()
        else:
            actual_data[column_name] = "COLUMN NOT FOUND"

    return actual_data


# ======================================================
# VALIDATION
# ======================================================
def normalize(value: str) -> str:
    if not value:
        return ""
    return value.strip().lower()


def validate_audit_row(page: Page,
                       actual: Dict[str, str],
                       expected: Dict[str, str],
                       reporter=None) -> bool:

    errors = []
    matched = []

    for column, expected_value in expected.items():

        actual_value = actual.get(column, "")

        if normalize(actual_value) == normalize(expected_value):
            matched.append(f"{column} ✔")
        else:
            error_msg = (
                f"{column} ❌ | Expected: {expected_value} | Actual: {actual_value}"
            )
            errors.append(error_msg)

    report_message = (
        "Matched Columns:\n" + "\n".join(matched) +
        "\n\nFailed Columns:\n" + ("\n".join(errors) if errors else "None")
    )

    if errors:

        screenshot_path = f"screenshot_{int(time.time())}.png"
        page.screenshot(path=screenshot_path)

        if reporter:
            reporter.add_log("Validation failed.")
            reporter.add_log(report_message)
            reporter.add_test_step(
                "Audit Row Validation",
                "failed",
                duration=0,
                error=report_message,
                screenshot=screenshot_path
            )

        return False

    else:
        if reporter:
            reporter.add_log("All columns matched successfully.")
            reporter.add_log(report_message)
            reporter.add_test_step(
                "Audit Row Validation",
                "passed",
                duration=0,
                error=report_message
            )

        return True


# ======================================================
# MAIN
# ======================================================
def main():

    reporter = AutomationReporter("Inventory Audit Report") if ENABLE_REPORTING else None

    start_time = time.time()
    validation_status = False

    print("\n🚀 STARTING AUDIT AUTOMATION\n")

    if reporter:
        reporter.add_log("Automation execution started.")

    try:

        with sync_playwright() as p:

            step = time.time()
            browser, page = login(
                p,
                browser_name="chrome",
                environment="QA"
            )

            if reporter:
                reporter.add_log("Login successful.")
                reporter.add_test_step("Login to Application", "passed", time.time() - step)

            detect_feedback(page)

            step = time.time()
            navigate_to_ongoing_audits(page)

            if reporter:
                reporter.add_log("Navigated to Ongoing Audits page.")
                reporter.add_test_step("Navigate to Ongoing Audits", "passed", time.time() - step)

            step = time.time()
            actual_row = get_audit_row_data(
                page,
                EXPECTED_ROW["Audit Name"]
            )

            if reporter:
                reporter.add_log(f"Fetched row data for: {EXPECTED_ROW['Audit Name']}")
                reporter.add_test_step("Fetch Audit Row Data", "passed", time.time() - step)

            step = time.time()
            validation_status = validate_audit_row(
                page,
                actual_row,
                EXPECTED_ROW,
                reporter
            )

            if reporter:
                reporter.add_log("Validation step completed.")
                reporter.add_test_step(
                    "Validation Completed",
                    "passed" if validation_status else "failed",
                    time.time() - step
                )

            if not CI_MODE and not DRY_RUN:
                page.wait_for_timeout(2000)

            browser.close()

    except Exception as e:

        if reporter:
            reporter.add_log(f"Critical error occurred: {str(e)}")
            reporter.add_test_step("Execution Error", "failed", duration=0, error=str(e))

        validation_status = False

    finally:

        duration = round(time.time() - start_time, 2)

        if reporter:

            reporter.add_log(f"Total execution time: {duration}s")

            reporter.add_test_step(
                "Total Execution",
                "passed" if validation_status else "failed",
                duration
            )

            final_status = "PASSED" if validation_status else "FAILED"

            reporter.finalize(final_status, duration)

            report_dir = os.path.join(
                "reports",
                datetime.now().strftime("%Y%m%d_%H%M%S")
            )

            html, pdf = reporter.generate_reports(report_dir)

            print("\n📊 REPORTS GENERATED")
            print("HTML:", html)
            print("PDF :", pdf)

            if not CI_MODE:
                try:
                    os.startfile(html)
                except:
                    import webbrowser
                    webbrowser.open(f"file://{html}")

        print("\n✅ Automation execution completed\n")


if __name__ == "__main__":
    main()
