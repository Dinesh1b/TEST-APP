import sys
import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login
from login.popup_handler import detect_feedback
from excel_logger import write_log, set_excel_path
from inventory.create_group import create_group as create_group
from inventory.Item_import_add import import_app
from inventory.location import settings
class Config:

        # ── Conditional Login Control ─────────────────────────────
    USE_CUSTOM_LOGIN = False

    if USE_CUSTOM_LOGIN:
        email = "rakeikoppanna-7429@yopmail.com"
        password = "MeNx6G2S"
    else:
        email = None
        password = None

    browsername = "chrome"
    environments = "production" # production, staging, development

    Branch = "nm"

    run_locatio_setup = False
    zones  = ["SA"]
    aisles = ["A1", "A2", "A3"]
    bays   = ["B1","B2","B3","B4","B5"]
    levels = ["L1", "L2", "L3", "L4", "L5"]


    run_create_group = False


    group_name = "Group@1"
    inventory_type = "Unit" # Unit, Batch , Serialized
    sheet_name = "Data"
    # input add Fields   
    fields = [
        "Item Code",
        "Item Name",
    ]

    # input add IDs (used only if Serialized)
    ids = [
        "Serial Number",
        "IMEI",
        "Barcode"
    ]

#itme itme imports
    run_import_app = True

    EXCEL_FILE: str = os.environ.get(
        "IMPORT_EXCEL_FILE",
        r"C:\Users\HP\Documents\input\main_qexcel.xlsx"
    )
    run_add_item = False
    run_quick_add_items = False
    run_import_items = False
    #group_name = "Group_131841" if
    # --- Add Item test record (single item, not from Excel) ---
    Item_Name     = "ab,cm12"    # Item Name   (was wrongly used as UOM before)
    Item_Code     = "itme173"    # Item Code
    Item_UOM      = "km"         # UOM         (was wrongly used as Item Name before)
    Item_Category = "Category132!" # Category
    Item_Tag      = "test tag1"   # Tag
    Item_CP       = 100          # Cost Price  (was hardcoded "100" in script, ignored Config)
    Item_SP       = 150          # Sell Price  (was hardcoded "150" in script, ignored Config)
    Item_Barcode  = "1234u56789"  # EAN/QR



    

# ======================================================
# MAIN EXECUTION
# ======================================================

if __name__ == "__main__":

    with sync_playwright() as p:

        browser, page = login(
            p,
            browser_name=Config.browsername,
            environment=Config.environments,
            email=Config.email,
            password=Config.password
        )
        if Config.run_locatio_setup:
             settings(page)
        else:
            print("x create_group")
        if Config.run_create_group:
             create_group(page,  Config)
        else:
            print("x create_group")
        if Config.run_import_app:
             import_app(page,  Config)
        else:
            print("x Itme_imports")
        browser.close()