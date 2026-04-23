import re
import pandas as pd
from collections import defaultdict
from playwright.sync_api import Page


DIALOG_WRAPPER_XPATH = (
    "//div[contains(@class,'auditor-summary-dialog')]"
    "//div[contains(@class,'p-datatable-wrapper')]"
)


def normalize(text: str) -> str:
    return str(text).replace(",", "").replace("%", "").strip()


def clean_name(text: str) -> str:
    return re.sub(r'\s+', ' ', str(text)).strip()


def to_int_safe(value: str, field: str, auditor: str):
    try:
        normalized = normalize(value)
        if normalized in ("", "--"):
            return normalized
        if "." not in normalized:
            return int(normalized)
        return float(normalized)
    except ValueError:
        raise AssertionError(
            f"Non-numeric value in '{field}' for auditor '{auditor}': '{value}'"
        )


def Q_as_table(Page, Config):

    def open_audit_summary(page):
        page.get_by_role("button", name="Audit Summary").click()
        page.wait_for_load_state("networkidle")
        page.locator("button:has-text('Realtime Auditor Insights')").click()
        page.locator(f"xpath={DIALOG_WRAPPER_XPATH}").first.wait_for(state="visible", timeout=15000)
        page.wait_for_timeout(800)

    def detect_columns(page) -> dict:
        headers = page.locator(f"xpath={DIALOG_WRAPPER_XPATH}//thead//th")
        header_texts = [
            re.sub(r"\s+", " ", headers.nth(i).inner_text()).strip()
            for i in range(headers.count())
        ]

        col = {}
        found = []
        for i, raw in enumerate(header_texts):
            norm = raw.lower().replace("\xa0", " ")
            found.append(f"[{i}] '{norm}'")

            if "auditor" in norm:
                col["auditor"] = i
            elif "completed inventory" in norm:
                col["completed"] = i
            elif "audited value" in norm:
                col["audited"] = i
            elif "damaged value" in norm:
                col["damaged"] = i
            elif "elapsed timing" in norm:
                col["elapsed"] = i
            elif "progress" in norm:
                col["progress"] = i
            elif "status" in norm:
                col["status"] = i

        print("\nHeaders detected inside Auditor Summary dialog:")
        for h in found:
            print(f"   {h}")
        print(f"\n   -> Column map: {col}\n")

        required = ["auditor", "completed", "audited", "damaged", "elapsed", "progress", "status"]
        missing = [k for k in required if k not in col]
        if missing:
            raise AssertionError(f"Missing column mappings: {missing}\nFound: {found}")

        return col

    def read_all_rows_via_js(page, col: dict) -> dict:
        prog_idx = col["progress"]

        raw_rows = page.evaluate(
            """([xpath, progIdx]) => {
                const result = document.evaluate(
                    xpath,
                    document,
                    null,
                    XPathResult.FIRST_ORDERED_NODE_TYPE,
                    null
                );
                const wrapper = result.singleNodeValue;
                if (!wrapper) return [];

                wrapper.scrollTop = 0;
                const rows = Array.from(wrapper.querySelectorAll('tbody tr'));

                return rows.map((row) => {
                    const tds = Array.from(row.querySelectorAll('td'));
                    return tds.map((td, idx) => {
                        if (idx === progIdx) {
                            const progressText =
                                td.querySelector("div[style*='font-weight: bold']") ||
                                td.querySelector("div[style*='text-align: center']");
                            return progressText ? progressText.innerText.trim() : td.innerText.trim();
                        }
                        return td.innerText.trim();
                    });
                });
            }""",
            [DIALOG_WRAPPER_XPATH, prog_idx]
        )

        actual = {}
        print(f"   JS found {len(raw_rows)} tbody row(s)\n")

        for i, cells in enumerate(raw_rows):
            if not cells:
                continue

            auditor = clean_name(cells[col["auditor"]]) if col["auditor"] < len(cells) else ""
            if not auditor or auditor.lower() == "total":
                print(f"   [row {i}] skip -> '{auditor}'")
                continue

            print(f"   [row {i}] reading -> '{auditor}'")

            def g(key):
                v = cells[col[key]] if col[key] < len(cells) else ""
                return to_int_safe(v, key, auditor)

            actual[auditor] = {
                "completed": g("completed"),
                "audited": g("audited"),
                "damaged": g("damaged"),
                "elapsed": clean_name(cells[col["elapsed"]]) if col["elapsed"] < len(cells) else "",
                "progress": normalize(cells[col["progress"]]) if col["progress"] < len(cells) else "",
                "status": clean_name(cells[col["status"]]) if col["status"] < len(cells) else "",
            }

        return actual

    def read_ui_total_via_js(page, col: dict) -> dict:
        cells = page.evaluate(
            """(xpath) => {
                const result = document.evaluate(
                    xpath,
                    document,
                    null,
                    XPathResult.FIRST_ORDERED_NODE_TYPE,
                    null
                );
                const wrapper = result.singleNodeValue;
                if (!wrapper) return [];

                return Array.from(wrapper.querySelectorAll('tfoot tr td'))
                            .map(td => td.innerText.trim());
            }""",
            DIALOG_WRAPPER_XPATH
        )

        result = {}
        for k in ["completed", "audited", "damaged"]:
            v = cells[col[k]] if col[k] < len(cells) else ""
            result[k] = to_int_safe(v, k, "TOTAL")
        return result

    def load_excel(path: str) -> dict:
        df = pd.read_excel(path, sheet_name=Config.EXCEL_SHEET_as_table)
        expected = defaultdict(lambda: {
            "completed": 0,
            "audited": 0,
            "damaged": 0,
            "elapsed": None,
            "progress": None,
            "status": None,
        })

        for _, row in df.iterrows():
            auditor = clean_name(str(row["auditor"]))
            expected[auditor]["completed"] += float(row["completed"])
            expected[auditor]["audited"] += float(row["audited"])
            expected[auditor]["damaged"] += float(row["damaged"])

            if "elapsed" in row and pd.notna(row["elapsed"]):
                expected[auditor]["elapsed"] = clean_name(str(row["elapsed"]))

            if pd.notna(row["progress"]):
                p = float(row["progress"])
                expected[auditor]["progress"] = str(int(p * 100) if p <= 1 else int(p))

            if "status" in row and pd.notna(row["status"]):
                expected[auditor]["status"] = clean_name(str(row["status"]))

        print(f"Excel loaded -> {len(expected)} auditor(s)")
        for name, data in expected.items():
            print(f"   {name}: {data}")
        return expected

    def normalize_for_comparison(val):
        if isinstance(val, (int, float)):
            if isinstance(val, float) and val.is_integer():
                return int(val)
            return val
        return str(val)

    FIELDS = ["completed", "audited", "damaged", "elapsed", "progress", "status"]

    def print_comparison(exp: dict, act: dict):
        W = 18
        print(f"  {'FIELD':<16} {'EXPECTED':>{W}} {'ACTUAL':>{W}}  RESULT")
        print(f"  {'-' * 16} {'-' * W} {'-' * W}  ------")
        for key in FIELDS:
            e = str(exp.get(key, "-"))
            a = str(act.get(key, "-"))
            e_val = normalize_for_comparison(exp.get(key))
            a_val = normalize_for_comparison(act.get(key))
            mark = "PASS" if e_val == a_val else "FAIL"
            print(f"  {key:<16} {e:>{W}} {a:>{W}}  {mark}")

    def validate_auditors(expected: dict, actual: dict) -> list:
        errors = []
        sep = "=" * 72
        print(f"\n{sep}")
        print("  AUDITOR-WISE VALIDATION  (Expected vs Actual)")
        print(sep)

        for auditor, exp in expected.items():
            print(f"\n  Auditor: {auditor}")
            if auditor not in actual:
                msg = f"Auditor '{auditor}' NOT FOUND in UI"
                errors.append(msg)
                print(f"  {msg}")
                print(f"     UI has: {list(actual.keys())}")
                continue
            act = actual[auditor]
            print_comparison(exp, act)
            for key in FIELDS:
                e_val = normalize_for_comparison(exp.get(key))
                a_val = normalize_for_comparison(act.get(key, "-"))
                if e_val != a_val:
                    errors.append(f"{auditor} | {key} | Expected={e_val} Actual={a_val}")
        return errors

    def calculate_total(expected: dict) -> dict:
        total = defaultdict(float)
        for data in expected.values():
            for key in ["completed", "audited", "damaged"]:
                total[key] += data[key]

        result = {}
        for key, value in total.items():
            result[key] = int(value) if float(value).is_integer() else value
        return result

    def validate_total(exp_total: dict, ui_total: dict) -> list:
        errors = []
        W = 18
        sep = "=" * 72
        print(f"\n{sep}")
        print("  TOTAL ROW VALIDATION  (Expected vs Actual)")
        print(sep)
        print(f"  {'FIELD':<16} {'EXPECTED':>{W}} {'ACTUAL':>{W}}  RESULT")
        print(f"  {'-' * 16} {'-' * W} {'-' * W}  ------")

        for key in ["completed", "audited", "damaged"]:
            e = str(exp_total.get(key, "-"))
            a = str(ui_total.get(key, "-"))
            e_val = normalize_for_comparison(exp_total.get(key))
            a_val = normalize_for_comparison(ui_total.get(key))
            mark = "PASS" if e_val == a_val else "FAIL"
            print(f"  {key:<16} {e:>{W}} {a:>{W}}  {mark}")
            if e_val != a_val:
                errors.append(f"TOTAL {key} | Expected={e_val} Actual={a_val}")

        return errors

    def select_branch(page, branch_text: str):
        dropdown = page.locator(
            'xpath=/html/body/app-root/app-layout/div/app-header/div[1]/div[2]/div[2]//p-dropdown'
        )
        dropdown.wait_for(state="visible", timeout=30000)
        dropdown.locator(".p-dropdown-label").click()

        panel = page.locator(".p-dropdown-panel").last
        panel.wait_for(state="visible", timeout=30000)

        search = panel.locator("input.p-dropdown-filter")
        if search.count() > 0:
            search.fill("")
            search.fill(branch_text)
            page.wait_for_timeout(300)

        option = panel.locator("li.p-dropdown-item", has_text=branch_text)
        if option.count() == 0:
            raise Exception(f"Branch not found: {branch_text}")

        option.first.click()
        panel.wait_for(state="hidden", timeout=30000)
        dropdown.locator(".p-dropdown-label", has_text=branch_text).wait_for(state="visible", timeout=30000)

    def navigate_to_as(page, Config):
        page.wait_for_selector("a[href='/home/audit']", state="visible")
        page.click("a[href='/home/audit']")
        page.wait_for_load_state("networkidle")
        select_branch(page, Config.Branch)

        print(f"Branch selected: {Config.Branch}")

        row = page.locator(
            f"table tbody tr:has(td span:has-text('{Config.audit_name}'))"
        ).first
        row.locator("td span").first.click()
        open_audit_summary(page)

        expected = load_excel(Config.EXCEL_PATH)
        col = detect_columns(page)
        actual = read_all_rows_via_js(page, col)

        errors = []
        errors += validate_auditors(expected, actual)

        exp_total = calculate_total(expected)
        ui_total = read_ui_total_via_js(page, col)
        errors += validate_total(exp_total, ui_total)

        sep = "=" * 72
        print(f"\n{sep}")
        if errors:
            print(f"  FAILED - {len(errors)} error(s):")
            for err in errors:
                print(f"      - {err}")
        else:
            print("  ALL ROWS VALIDATED - AUDIT SUMMARY PASSED")
        print(sep)

    navigate_to_as(Page, Config)
