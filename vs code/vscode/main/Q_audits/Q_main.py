import sys
import os
from playwright.sync_api import sync_playwright

# --------------------------------------------------------------
# PATH SETUP
# --------------------------------------------------------------
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from login.login import login
from Q_audits.Q_setting import Q_setting
from Q_audits.Q_SA import Q_SA
from Q_audits.Q_SA1 import Q_SA1
from Q_audits.Q_as_table import Q_as_table
from Q_audits.Q_Recently_audit import Q_Recently_Audit
from Q_audits.Q_audit_Summary import Q_audit_Summary
# --------------------------------------------------------------
# CONFIG  Control Input then run specific test case
# --------------------------------------------------------------
class Config:

    # Timeout settings
    DEFAULT_TIMEOUT = 10000
    SHORT_TIMEOUT = 5000
    WAIT_AFTER_ACTION = 300 #page.wait_for_timeout(Config.WAIT_AFTER_ACTION)
    
# main configuration foe login and browser setup

    # â”€â”€ Conditional Login Control â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    USE_CUSTOM_LOGIN = False   # ðŸ” True / False

    if USE_CUSTOM_LOGIN:
        email = "rakeikoppanna-7429@yopmail.com"  # override ENV_CONFIG default
        password = "MeNx6G2S"
    else:
        email = None
        password = None          # Override ENV_CONFIG default    

    browsername = "chrome"
    environments = "PRODUCTION"  # DEV/QA/ STAGING /PRODUCTION

    Branch = "nm"  # branch to select during login, if applicable
#===========================================================
#Control Q_create
    audit_name = "Audit_TEST_3132"

    Auditor_name1 = "dine"
    Auditor_name2 = "egggg tttt"
    Auditor_name3 = None
# true/false to control checkboxes in Q_create page
    Checkboxes_Audit_Damaged = True 
    Checkboxes_StockItems = True
    Checkboxes_geo = False
    Checkboxes_photo = False
    # -------------------------------------------------------
    # AUDITOR_MAPPING_TYPE # "Random" | "By Category" | "By Storage" 
    # -------------------------------------------------------
    AUDITOR_MAPPING_TYPE = "Random"

    mapping = {
        "Item Code": "Item Code",
        "Item Name": "Item Name",
        "Stock Quantity": "Adjustmentqty",
        "UOM": "UOM",
        "Cost Price": "Cost Price",
        "Category": "Category",
        "Location": "Location",
        "Barcode": "Barcode",
    }
    
    run_q_setting = True   # ðŸ” True / False control Q_create to import sheet
#==================================================================================================
   #Upload Excel file path for Stock and Audit page
    EXCEL_PATH = r"C:\Users\HP\Documents\input\main_qexcel.xlsx"
#==================================================================================================
    #AUDITOR_MAPPING_TYPE = "By Storage" # "Random" | "By Category" | "By Storage" 
    EXCEL_SHEET_AUDITOR_MAPPING = "AUDITOR_MAPPING"

    EXCEL_auditor_col  = "Auditor"          # -------------------------------------------------------
    EXCEL_category_col = "Category"         # Single sheet that holds all auditor mapping data.
    EXCEL_storage_col  = "Storage"          # Must have columns: Auditor | Category | Storage
                                            # Category column is used for "By Category" mode.
                                            # Storage  column is used for "By Storage"  mode.
                                            # ------------------------------------------------------    



#==================================================================================================
        #  control  stock audit page
    location1 = "SA-A2-B3-L3"
    code1 = "ABC1123"
    aud_qty1 = 10
    dam_qty1 = 0
    
    EXCEL_SHEET_auditor_1 = "auditor_1"
    EXCEL_LOCATION_COL1 = "locations"
    EXCEL_CODE_COL1 = "code"
    EXCEL_AUDITED_COL1 = "audited"
    EXCEL_DAMAGED_COL1 = "damaged"

    run_Q_SA = True # # ðŸ” True / False control  stock audit page 

#===================================================================================================
#  control second   Auditor stock audit page
            #  control  stock audit page
    location2 = "SA-A2-B3-L3"
    code2 = "ABC11234"
    aud_qty2 = 10
    dam_qty2 = 0


    EXCEL_SHEET_auditor_2 = "auditor_2"
    EXCEL_LOCATION_COL2 = "locations"
    EXCEL_CODE_COL2 = "code"
    EXCEL_AUDITED_COL2 = "audited"
    EXCEL_DAMAGED_COL2 = "damaged"
    #Auditorlog in 2

    email2 = "yoiffoweuroipre-7178@yopmail.com"       # override ENV_CONFIG default
    password2 = "MeNx6G2S"             # override ENV_CONFIG default    

    # Auditorlog in 2
    run_Q_SA1 = False # # ðŸ” True / False control  stock audit page
#===================================================================================================
#control  audit summary table page 
   
    EXCEL_SHEET_as_table = "as_table"
    run_Q_as_table = False # # ðŸ” True / False control  audit summary table page 
#==================================================================================================
#control  recently audited page
    
    EXCEL_SHEET_Recently_Audit = "Recently_Audit"
    
    run_Q_Recently_Audit = False # # ðŸ” True / False 
#===================================================================================================
    EXCEL_SHEET_audit_Summary   = "auditSummary"
    FILTER_COLUMN = "filter"
    run_Q_audit_Summary  = False # # ðŸ” True / False
#===================================================================================================
if __name__ == "__main__":
    with sync_playwright() as p:

        # â”€â”€ Login as Auditor 1 â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        browser, page = login(
            p,
            browser_name=Config.browsername,
            environment=Config.environments,
            email=Config.email,
            password=Config.password
        )
        page.set_default_timeout(30000)

        if Config.run_q_setting:
            Q_setting(page, Config)
        else:
            print("âŒ Q_setting skipped")

        if Config.run_Q_SA:
            Q_SA(page, Config)
        else:
            print("âŒ Q_SA skipped")

        # ── Login as Auditor 2 ─────────────────────────────────────────
        if Config.run_Q_SA1:
            same_creds = (
                (Config.email or "") == (Config.email2 or "") and
                (Config.password or "") == (Config.password2 or "")
            )
            if not same_creds:
                browser.close()  # close Auditor 1 session only when credentials change
                browser, page = login(
                    p,
                    browser_name=Config.browsername,
                    environment=Config.environments,
                    email=Config.email2,
                    password=Config.password2
                )
                page.set_default_timeout(30000)
            Q_SA1(page, Config)
        else:
            print("❌ Q_SA1 skipped")

        if Config.run_Q_as_table:
            Q_as_table(page, Config)
        else:
            print("âŒ Q_as_table skipped")

        if Config.run_Q_Recently_Audit:
            Q_Recently_Audit(page, Config)
        else:
            print("âŒ Q_Recently_Audit skipped")

        if Config.run_Q_audit_Summary:
            Q_audit_Summary(page, Config)
        else:
            print("âŒ Q_audit_Summary skipped")

        input("Press ENTER to close browser...")
        browser.close()
