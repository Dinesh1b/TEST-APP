"""
ENTERPRISE AUDIT VALIDATION SYSTEM
====================================
Fields to validate = columns present in 'auditSummary' Excel sheet.

  Add a column    → that field gets validated
  Remove a column → that field is skipped
  No code changes needed.

FILTER MERGE LOGIC:
  Negative Variance badge  → shows rows from: Negative Variance + Line Items Not Found
  Positive Variance badge  → shows rows from: Positive Variance + Excess Line Item

BIZ RULES:
  Matched Line Item  → Stock Quantity == Audited Qty
  Location Conflict  → Stock Location != Audited Location
  Damaged Report     → Damaged Qty > 0
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Set, Optional
from dataclasses import dataclass
from enum import Enum
import pandas as pd
from playwright.sync_api import sync_playwright, Page


# ── filter enums ─────────────────────────────────────────────────────
class FilterType(Enum):
    ALL                  = "All"
    MATCHED_LINE_ITEM    = "Matched Line Item"
    LINE_ITEMS_NOT_FOUND = "Line Items Not Found"
    EXCESS_LINE_ITEM     = "Excess Line Item"
    NEGATIVE_VARIANCE    = "Negative Variance"
    POSITIVE_VARIANCE    = "Positive Variance"
    LOCATION_CONFLICT    = "Location Conflict"
    CROSS_CHECKED_AUDIT  = "Cross Checked Audit"
    DAMAGED_REPORT       = "Damaged Report"

class SubFilterType(Enum):
    NEGATIVE_LINE_ITEM = "Negative Line Item"
    POSITIVE_LINE_ITEM = "Positive Line Item"

UI_FILTERS   = [f.value for f in FilterType]
SKIP_FILTERS = {"Matched"}


# ── secondary filter columns (O, P in the Excel sheet) ───────────────
SECONDARY_FILTER_COLUMNS: List[str] = [
    "Damaged Filter",
    "Location Filter",
]

# ── filter merge map ─────────────────────────────────────────────────
FILTER_MERGE_MAP: Dict[str, List[str]] = {
    FilterType.NEGATIVE_VARIANCE.value: [
        FilterType.NEGATIVE_VARIANCE.value,
        FilterType.LINE_ITEMS_NOT_FOUND.value,
    ],
    FilterType.POSITIVE_VARIANCE.value: [
        FilterType.POSITIVE_VARIANCE.value,
        FilterType.EXCESS_LINE_ITEM.value,
    ],
}

# ── full UI column → td index map ────────────────────────────────────
ALL_UI_COLUMNS: Dict[str, int] = {
    "Item Code":        1,
    "Item Name":        2,
    "UOM":              3,
    "Stock Quantity":   4,
    "Audited Qty":      5,
    "Variance":         6,
    "Variance Value":   7,
    "Variance Type":    8,
    "Damaged Qty":      9,
    "Auditor Name":     10,
    "Audited DateTime": 11,
    "Audited Image":    12,
    "Stock Location":   13,
    "Audited Location": 14,
    "Reason":           15,
    "Geo Location":     16,
}

# ── config ───────────────────────────────────────────────────────────
@dataclass
class Config:
    DEFAULT_TIMEOUT:     int = 20_000
    SCROLL_WAIT_MS:      int = 600
    SCROLL_STEP_PX:      int = 400
    SCROLL_WRAPPER_CSS:  str = ".p-datatable-scrollable .p-datatable-wrapper"
    TABLE_ROW_SELECTOR:  str = "tbody.p-datatable-tbody > tr"
    TABLE_BODY_SELECTOR: str = "tbody.p-datatable-tbody"
    BADGE_CSS:           str = "span.badge-custom"
    FILTER_NAV_BTNS:     str = "button.filter-nav"
    BADGE_CONTAINER:     str = "div.filters-list"

# ── colours ──────────────────────────────────────────────────────────
R="\033[91m"; G="\033[92m"; Y="\033[93m"; C="\033[96m"
W="\033[97m"; B="\033[1m";  DIM="\033[2m"; RS="\033[0m"
def c(t,col): return f"{col}{t}{RS}"
def bar(ch="─",w=110,col=C): print(c(ch*w,col))
def dbl(): print(c("═"*110,B))
def section(t): dbl(); print(c(f"  ▶  {t}",B)); dbl()

# ── normaliser ───────────────────────────────────────────────────────
class N:
    _F = re.compile(r'^-?\d+\.\d+$')
    @classmethod
    def norm(cls, v) -> str:
        if v is None: return ""
        s = str(v).strip()
        if s.lower() in ("nan","none",""): return ""
        t = " ".join(s.replace(",","").lower().split())
        if cls._F.match(t):
            try:
                f = float(t)
                return str(int(f)) if f == int(f) else str(round(f,4))
            except ValueError: pass
        return t

def f2f(v) -> float:
    try: return float(str(v).replace(",","").strip())
    except: return 0.0

def _nh(h): return h.strip().lower().replace("_"," ").replace("-"," ")




# ======================================================
# EXCEL LOADER  ← CHANGED
# ======================================================
def load_excel(path, sheet, fcol):
    df = pd.read_excel(path, sheet_name=sheet)

    # normalised name → standard UI name
    norm_to_std = {_nh(k): k for k in ALL_UI_COLUMNS}

    # columns that must never be validated as UI fields
    skip_as_field: Set[str] = {_nh(s) for s in SECONDARY_FILTER_COLUMNS} | {_nh(fcol)}

    col_to_std: Dict[str, str] = {}
    for col in df.columns:
        n = _nh(col)
        if n in norm_to_std and n not in skip_as_field:
            col_to_std[col] = norm_to_std[n]

    active_fields = list(col_to_std.values())

    # find secondary filter columns that actually exist in the sheet
    sec_col_map: Dict[str, str] = {}   # excel_col_name → secondary filter value
    for col in df.columns:
        if _nh(col) in {_nh(s) for s in SECONDARY_FILTER_COLUMNS}:
            sec_col_map[col] = col     # keep actual column name for row.get()

    grouped: Dict[str, List[Dict]] = {}

    for _, row in df.iterrows():
        # ── primary filter (column Q) ────────────────────────────────
        fn = str(row.get(fcol, "")).strip()
        if not fn or fn in SKIP_FILTERS:
            continue

        rec = {std: N.norm(row[col]) for col, std in col_to_std.items()}

        # add to primary group
        grouped.setdefault(fn, []).append(rec)

        # ── secondary filters (columns O and P) ──────────────────────
        # If a secondary-filter cell is non-empty, the same row record
        # is ALSO added to that filter group.
        for sec_col in sec_col_map:
            raw_sec = row.get(sec_col, "")
            if pd.isna(raw_sec):
                continue
            sec_val = re.sub(r'[:\s]+$', '', str(raw_sec).strip())
            if sec_val and sec_val not in SKIP_FILTERS:
                if sec_val != fn:
                    grouped.setdefault(sec_val, []).append(rec)

    return grouped, active_fields


def print_load_summary(grouped, active_fields):
    print()
    for fn, rows in grouped.items():
        print(f"  {c('✓',G)} Excel  {fn:<30}  {len(rows):>3} rows")
    print()
    bar("─", 60, DIM)
    print(f"  {c('Validating these fields',B)}  ({len(active_fields)}):")
    bar("─", 60, DIM)
    for fld in active_fields:
        print(f"  {c('✅',G)}  {fld}")
    skipped = [f for f in ALL_UI_COLUMNS if f not in active_fields]
    if skipped:
        print()
        print(f"  {c('Skipped (not in Excel sheet)',Y)}  ({len(skipped)}):")
        for fld in skipped:
            print(f"  {c('⛔',Y)}  {fld}")
    bar("─", 60, DIM)
    print()

# ── UI row extraction ────────────────────────────────────────────────
def extract_row(row) -> Dict[str, str]:
    cells = row.locator("td")
    data  = {}
    for fn, idx in ALL_UI_COLUMNS.items():
        try:
            cell = cells.nth(idx)
            data[fn] = "yes" if fn == "Audited Image" and cell.locator("img").count() > 0 \
                             else N.norm(cell.inner_text())
        except:
            data[fn] = ""
    return data

def blank_row(r): return all(not v for v in r.values())

# ── badge count extraction ───────────────────────────────────────────
def _badge_label(badge) -> str:
    txt = " ".join(badge.inner_text().split()).strip()
    return re.sub(r"\s*\(\d+\)\s*$", "", txt).strip()

def _badge_count(badge) -> int:
    txt = " ".join(badge.inner_text().split()).strip()
    m   = re.search(r"\((\d+)\)\s*$", txt)
    return int(m.group(1)) if m else -1

# ── carousel navigation ──────────────────────────────────────────────
def _left_nav(page, cfg) -> None:
    while True:
        left = page.locator(cfg.FILTER_NAV_BTNS).first
        if left.is_disabled():
            break
        left.click()
        page.wait_for_timeout(300)

def _right_nav(page, cfg) -> bool:
    right = page.locator(cfg.FILTER_NAV_BTNS).last
    if right.is_disabled():
        return False
    right.click()
    page.wait_for_timeout(300)
    return True

def click_badge(page, cfg, filter_name: str) -> int:
    _left_nav(page, cfg)
    visited_positions: set = set()

    while True:
        badges = page.locator(cfg.BADGE_CSS)
        count  = badges.count()

        for i in range(count):
            badge = badges.nth(i)
            if _badge_label(badge) == filter_name:
                row_count = _badge_count(badge)
                badge.click()
                page.wait_for_timeout(1000)
                print(f"  {c('▶ Badge clicked',G)}  {filter_name!r}  "
                      f"(count={c(str(row_count), Y)})")
                return row_count

        visible = tuple(_badge_label(badges.nth(i)) for i in range(count))
        if visible in visited_positions:
            break
        visited_positions.add(visible)

        if not _right_nav(page, cfg):
            break

    raise ValueError(
        f"Badge not found in carousel: '{filter_name}'\n"
        f"  Badges seen: {sorted(visited_positions)}"
    )

# ── scroll + collect ─────────────────────────────────────────────────
def scroll_and_collect(page, cfg, seen):
    wrapper = page.locator(cfg.SCROLL_WRAPPER_CSS).first
    collected, prev_top = [], -1

    def _grab():
        for i in range(wrapper.locator(cfg.TABLE_ROW_SELECTOR).count()):
            data = extract_row(wrapper.locator(cfg.TABLE_ROW_SELECTOR).nth(i))
            if blank_row(data): continue
            code = data.get("Item Code","")
            if code and code not in seen:
                seen.add(code); collected.append(data)

    _grab()
    while True:
        cur = wrapper.evaluate("el => el.scrollTop")
        if cur == prev_top: break
        prev_top = cur
        wrapper.evaluate(f"el => el.scrollTop += {cfg.SCROLL_STEP_PX}")
        page.wait_for_timeout(cfg.SCROLL_WAIT_MS)
        _grab()
    wrapper.evaluate("el => el.scrollTop = el.scrollHeight")
    page.wait_for_timeout(cfg.SCROLL_WAIT_MS)
    _grab()
    return collected

def collect_all(page, cfg) -> List[Dict]:
    try:
        page.wait_for_selector(
            cfg.TABLE_BODY_SELECTOR,
            state="visible",
            timeout=5_000
        )
    except Exception:
        print(f"  {c('⚠ No table body visible — 0 rows for this filter',Y)}")
        return []

    seen, all_rows = set(), []
    while True:
        all_rows.extend(scroll_and_collect(page, cfg, seen))
        try:
            nxt = page.locator("button.p-paginator-next")
            if nxt.count()==0 or "p-disabled" in (nxt.get_attribute("class") or ""): break
            nxt.click()
            page.wait_for_load_state("networkidle", timeout=10_000)
            page.wait_for_timeout(1200)
            page.wait_for_selector(cfg.TABLE_BODY_SELECTOR, timeout=cfg.DEFAULT_TIMEOUT)
        except: break
    return all_rows

# ── business rules ───────────────────────────────────────────────────
class BizRules:
    @staticmethod
    def matched_line_item(r):
        return f2f(r.get("Stock Quantity", 0)) == f2f(r.get("Audited Qty", 0))

    @staticmethod
    def excess(r):
        return f2f(r["Stock Quantity"])==0 and f2f(r["Audited Qty"])>0 and f2f(r["Variance"])>0

    @staticmethod
    def pos_line(r):
        return f2f(r["Stock Quantity"])>0 and f2f(r["Audited Qty"])>0 and f2f(r["Variance"])>0

    @staticmethod
    def not_found(r):
        return f2f(r["Stock Quantity"])>0 and f2f(r["Audited Qty"])==0 and f2f(r["Variance"])<0

    @staticmethod
    def neg_line(r):
        return f2f(r["Stock Quantity"])>0 and f2f(r["Audited Qty"])>0 and f2f(r["Variance"])<0

    @staticmethod
    def pos_var(r):
        return f2f(r["Variance"]) > 0

    @staticmethod
    def neg_var(r):
        return f2f(r["Variance"]) < 0

    @staticmethod
    def location_conflict(r):
        stock   = N.norm(r.get("Stock Location",  ""))
        audited = N.norm(r.get("Audited Location", ""))
        return stock != audited

    @staticmethod
    def damaged_report(r):
        return f2f(r.get("Damaged Qty", 0)) > 0

    @staticmethod
    def resolve(fn, row):
        if fn == FilterType.POSITIVE_VARIANCE.value:
            return FilterType.EXCESS_LINE_ITEM.value if f2f(row["Stock Quantity"])==0 \
                   else SubFilterType.POSITIVE_LINE_ITEM.value
        if fn == FilterType.NEGATIVE_VARIANCE.value:
            return FilterType.LINE_ITEMS_NOT_FOUND.value if f2f(row["Audited Qty"])==0 \
                   else SubFilterType.NEGATIVE_LINE_ITEM.value
        return fn

    _MAP = None
    def validators(self):
        if self._MAP is None:
            BizRules._MAP = {
                FilterType.MATCHED_LINE_ITEM.value:     self.matched_line_item,
                FilterType.LINE_ITEMS_NOT_FOUND.value:  self.not_found,
                FilterType.EXCESS_LINE_ITEM.value:      self.excess,
                FilterType.NEGATIVE_VARIANCE.value:     self.neg_var,
                FilterType.POSITIVE_VARIANCE.value:     self.pos_var,
                SubFilterType.NEGATIVE_LINE_ITEM.value: self.neg_line,
                SubFilterType.POSITIVE_LINE_ITEM.value: self.pos_line,
                FilterType.LOCATION_CONFLICT.value:     self.location_conflict,
                FilterType.DAMAGED_REPORT.value:        self.damaged_report,
            }
        return self._MAP

    def check(self, fn, row):
        leaf = self.resolve(fn, row)
        vfn  = self.validators().get(leaf)
        if vfn is None: return None
        if not vfn(row):
            return (f"Rule=[{leaf}]  Stock={row.get('Stock Quantity')}  "
                    f"Audited={row.get('Audited Qty')}  Variance={row.get('Variance')}  "
                    f"DamagedQty={row.get('Damaged Qty')}  "
                    f"StockLoc={row.get('Stock Location')}  "
                    f"AuditedLoc={row.get('Audited Location')}")
        return None

# ── failure record ───────────────────────────────────────────────────
@dataclass
class Fail:
    filter_name: str; code: str; field: str
    expected: str;    actual: str; kind: str

# ── output ───────────────────────────────────────────────────────────
_WC=14; _WF=22; _WE=28; _WA=28

def _hdr():
    bar("─",100,DIM)
    print(f"  {'Status':<6}  {'Item Code':<{_WC}}  {'Field':<{_WF}}  "
          f"{c('Expected',C):<{_WE+10}}  {c('Actual',Y):<{_WA+10}}  Type")
    bar("─",100,DIM)

def pass_line(code): print(f"  {c('PASS',G)}  {code}")

def fail_line(code, fld, ev, av, kind):
    kc = R if kind in ("FIELD","BIZ") else Y
    print(f"  {c('FAIL',R)}  {code:<{_WC}}  {fld:<{_WF}}  "
          f"{c('exp',C)}={ev!r:<{_WE}}  {c('act',Y)}={av!r:<{_WA}}  [{c(kind,kc)}]")

# ── engine ───────────────────────────────────────────────────────────
class Engine:
    def __init__(self, active_fields):
        self.active_fields = active_fields
        self.failures: List[Fail]  = []
        self.passes:   List[tuple] = []
        self._biz = BizRules()

    def _addf(self, *a): self.failures.append(Fail(*a))

    def compare(self, actual, expected, filter_name):
        amap   = {r["Item Code"].lower(): r for r in actual}
        emap   = {r["Item Code"].lower(): r for r in expected}
        is_all = (filter_name == FilterType.ALL.value)
        _hdr()

        for code, exp_row in emap.items():
            if code not in amap:
                fail_line(code,"—","row present","MISSING","MISSING")
                self._addf(filter_name,code,"—","row present","MISSING","MISSING")
                continue

            act_row = amap[code]; ok = True

            for fld in self.active_fields:
                if fld == "Item Code": continue
                ev = exp_row.get(fld, "")
                av = act_row.get(fld, "")
                if av != ev:
                    fail_line(code, fld, ev, av, "FIELD")
                    self._addf(filter_name, code, fld, ev, av, "FIELD")
                    ok = False

            biz = self._biz.check(filter_name, act_row)
            if biz:
                fail_line(code,"[BIZ RULE]","invariant ok",biz,"BIZ")
                self._addf(filter_name,code,"[BIZ RULE]","invariant ok",biz,"BIZ")
                ok = False

            if ok:
                pass_line(code); self.passes.append((filter_name, code))

        if not is_all:
            for code in amap:
                if code not in emap:
                    fail_line(code,"—","not in Excel","PRESENT IN UI","EXTRA")
                    self._addf(filter_name,code,"—","not in Excel","PRESENT IN UI","EXTRA")
        bar()

    def summary(self) -> bool:
        dbl(); print(c("  FINAL VALIDATION SUMMARY",B)); dbl()
        tp, tf = len(self.passes), len(self.failures)

        print(c(f"\n  ✅  PASSED ITEMS  ({tp})",G)); bar("─",70,G)
        if self.passes:
            prev=None
            for fn, code in self.passes:
                if fn!=prev: print(f"\n  {c(fn,C)}"); prev=fn
                print(f"    {c('PASS',G)}  {code}")
        else: print(f"    {c('(none)',DIM)}")

        print(c(f"\n  ❌  FAILED ITEMS  ({tf})",R)); bar("─",110,R)
        if self.failures:
            print(f"  {'#':<5}  {'Filter':<28}  {'Item Code':<16}  "
                  f"{'Field':<24}  {'Expected':<30}  {'Actual':<30}  Type")
            bar("─",110,R)
            prev=None
            for i,f in enumerate(self.failures,1):
                if f.filter_name!=prev:
                    if prev: print()
                    print(f"  {c(f.filter_name,C)}"); prev=f.filter_name
                kc = R if f.kind in ("FIELD","BIZ") else Y
                print(c(f"  {i:<5}  {'':28}  {f.code:<16}  {f.field:<24}  "
                         f"{f.expected[:30]:<30}  {f.actual[:30]:<30}  {f.kind}", kc))

            print(); bar("─",70,R)
            counts: Dict[str,Dict[str,int]] = {}
            for f in self.failures:
                counts.setdefault(f.filter_name,{})
                counts[f.filter_name][f.kind] = counts[f.filter_name].get(f.kind,0)+1
            print(f"  {'Filter':<28}  {'FIELD':>6}  {'MISSING':>7}  {'EXTRA':>5}  {'BIZ':>4}  {'TOTAL':>6}")
            sep=f"  {'─'*28}  {'─'*6}  {'─'*7}  {'─'*5}  {'─'*4}  {'─'*6}"
            print(sep); grand=0
            for fn,kc in counts.items():
                t=sum(kc.values()); grand+=t
                print(f"  {fn:<28}  {kc.get('FIELD',0):>6}  {kc.get('MISSING',0):>7}  "
                      f"{kc.get('EXTRA',0):>5}  {kc.get('BIZ',0):>4}  {c(str(t),R):>6}")
            print(sep)
            print(f"  {'TOTAL':<28}  {'':>6}  {'':>7}  {'':>5}  {'':>4}  {c(str(grand),R):>6}")
        else: print(f"    {c('(none)',DIM)}")

        print(); dbl()
        if not self.failures:
            print(f"  {c('✅  ALL VALIDATIONS PASSED',G)}  ({tp} items checked)")
        else:
            print(f"  {c('❌  VALIDATION FAILED',R)}     PASS={c(str(tp),G)}    FAIL={c(str(tf),R)}")
        dbl()
        return not self.failures

# ── navigation ───────────────────────────────────────────────────────
def open_audit_summary(page):
    page.get_by_role("button", name="Audit Summary").click()
    page.wait_for_load_state("networkidle"); page.wait_for_timeout(800)

def select_branch(page, branch):
    dd = page.locator('xpath=//div[@data-tour-id="header-branch"]//p-dropdown').first
    dd.locator(".p-dropdown-label").click()
    panel = page.locator(".p-dropdown-panel").last
    panel.wait_for(state="visible")
    inp = panel.locator("input.p-dropdown-filter")
    if inp.count()>0: inp.fill(branch)
    panel.locator("li.p-dropdown-item", has_text=branch).first.click()
    panel.wait_for(state="hidden")

def navigate_to_audit(page, config):
    page.wait_for_selector("a[href='/home/audit']", state="visible")
    page.click("a[href='/home/audit']")
    page.wait_for_load_state("networkidle")
    select_branch(page, config.Branch)
    row = page.locator(f"table tbody tr:has(td span:has-text('{config.ap_audit_name}'))").first
    row.locator("td span").first.click()
    open_audit_summary(page)

def A_audit_Summary(page, config):
    cfg = Config()

    section("LOADING EXCEL DATA")
    grouped, active_fields = load_excel(config.EXCEL_PATH, config.EXCEL_SHEET_audit_Summary, config.FILTER_COLUMN)
    print_load_summary(grouped, active_fields)
    navigate_to_audit(page, config)
    engine = Engine(active_fields=active_fields)

    for filter_name in UI_FILTERS:
            section(f"FILTER  ▶  {filter_name}")

            badge_count = click_badge(page, cfg, filter_name)

            if badge_count == 0:
                print(f"  {c('⏭  Skipping — badge count is 0',DIM)}\n")
                continue

            actual = collect_all(page, cfg)

            merge_keys = FILTER_MERGE_MAP.get(filter_name, [filter_name])
            exp: List[Dict] = []
            for key in merge_keys:
                exp.extend(grouped.get(key, []))

            print(f"\n  {c('UI',C)} = {len(actual)} rows    {c('Excel',G)} = {len(exp)} rows", end="")
            if len(merge_keys) > 1:
                merged_info = " + ".join(f"{c(k,Y)}({len(grouped.get(k,[]))})" for k in merge_keys)
                print(f"   {c('← merged:',DIM)} {merged_info}", end="")
            print("\n")

            engine.compare(actual, exp, filter_name)

    

    sys.exit(0 if engine.summary() else 1)



