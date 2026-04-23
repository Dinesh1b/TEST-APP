import os


class BaseConfig:
    DEFAULT_TIMEOUT = 10000
    SHORT_TIMEOUT = 5000
    WAIT_AFTER_ACTION = 300

    USE_CUSTOM_LOGIN = False

    email = None
    password = None
    email2 = None
    password2 = None

    browsername = "chrome"
    environments = "PRODUCTION"
    base_urls = {
        "PRODUCTION": "https://app.stockount.com",
        "STAGING": "https://yellow-river-0ebeae800.2.azurestaticapps.net",
        "QA": "https://kind-mushroom-018e57a00.1.azurestaticapps.net",
        "DEV": "https://nice-water-001254c00.1.azurestaticapps.net",
    }

    Branch = "nm"
    audit_name = ""

    Auditor_name1 = None
    Auditor_name2 = None
    Auditor_name3 = None

    Checkboxes_Audit_Damaged = False
    Checkboxes_StockItems = False
    Checkboxes_geo = False
    Checkboxes_photo = False

    mapping = {}

    run_Q_audit = False
    run_Audit_plan = False
    run_inventory = False

    run_q_setting = False
    run_Q_SA = False
    run_Q_SA1 = False
    run_Q_as_table = False
    run_Q_Recently_Audit = False
    run_create_audit = False
    run_timezone = False
    run_create_group = False

    EXCEL_PATH = "C:/Users/HP/Documents/input/main_qexcel.xlsx"

    AUDITOR_MAPPING_TYPE = "Random"
    EXCEL_SHEET_AUDITOR_MAPPING = None
    EXCEL_auditor_col = "Auditor"
    EXCEL_category_col = "Category"
    EXCEL_storage_col = "Storage"

    location1 = "SA-A2-B3-L3"
    code1 = "ABC1123"
    aud_qty1 = 0
    dam_qty1 = 0

    EXCEL_SHEET_auditor_1 = "auditor_1"
    EXCEL_LOCATION_COL1 = "locations"
    EXCEL_CODE_COL1 = "code"
    EXCEL_AUDITED_COL1 = "audited"
    EXCEL_DAMAGED_COL1 = "damaged"

    location2 = "SA-A2-B3-L3"
    code2 = "ABC11234"
    aud_qty2 = 0
    dam_qty2 = 0

    EXCEL_SHEET_auditor_2 = "auditor_2"
    EXCEL_LOCATION_COL2 = "locations"
    EXCEL_CODE_COL2 = "code"
    EXCEL_AUDITED_COL2 = "audited"
    EXCEL_DAMAGED_COL2 = "damaged"

    EXCEL_SHEET_as_table = "as_table"
    EXCEL_SHEET_Recently_Audit = "Recently_Audit"

    Audit_Owner = ""
    Auditor1 = ""
    Auditor2 = ""
    Group_Name = ""
    Audit_Type = "Complete Count"
    frequency = "one-time"
    Day_s = 30
    Target__Day = "Thursday"
    Target_Date = ""

    A_Checkboxes_Audit_Damaged = False
    A_Checkboxes_StockItems = False
    A_Checkboxes_geo = False
    A_Checkboxes_photo = False

    CROSS_AUDIT_TYPE = "Random Recheck"
    CROSS_Auditor_name = ""
    AUDIT_MAPPING_TYPE = "Random"

    group_name = "Group_34"
    inventory_type = "Serialized"
    fields = ["Item Code", "Item Name"]
    ids = ["Id1Name", "Id2Name", "Id3Name"]

    @classmethod
    def get_base_url(cls):
        return cls.base_urls.get(str(cls.environments).upper(), cls.base_urls["PRODUCTION"])


try:
    from backend.Config import Config as RuntimeConfig
except Exception:
    RuntimeConfig = None


class Config(BaseConfig):
    pass


if RuntimeConfig is not None:
    for _name in dir(RuntimeConfig):
        if _name.startswith("__"):
            continue
        setattr(Config, _name, getattr(RuntimeConfig, _name))

    if not hasattr(Config, "base_urls"):
        Config.base_urls = BaseConfig.base_urls


def get_settings():
    return Config


__all__ = ["BaseConfig", "Config", "get_settings"]
