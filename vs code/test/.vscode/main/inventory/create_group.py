import sys
import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# ---------------------------
# Select Inventory Type
# ---------------------------
def select_inventory_type(page, Config, inventory_type):
    card = page.locator("button.inventory-type-card", has_text=inventory_type)
    card.wait_for(state="visible")
    card.click()


# ---------------------------
# Select Item Group Dropdown
# ---------------------------
def select_item_group(page, group_name):
    dropdown = page.locator("p-dropdown[placeholder='Select Item Group']")
    dropdown.locator("div.p-dropdown-trigger").click()

    panel = page.locator("div.p-dropdown-panel")
    panel.locator("input.p-dropdown-filter").fill(group_name)

    panel.locator("li.p-dropdown-item", has_text=group_name).first.click()


# ---------------------------
# Add Field
# ---------------------------
def add_field(page, field_index, field_type):

    print(f"➕ Adding Field {field_index}: {field_type}")

    combos = page.locator("span[role='combobox'][aria-label='Select']")
    count_before = combos.count()

    page.get_by_role("button", name="Add Field").click()

    page.wait_for_function(
        f"document.querySelectorAll(\"span[role='combobox'][aria-label='Select']\").length > {count_before}"
    )

    dropdown = page.locator("span[role='combobox'][aria-label='Select']").last
    dropdown.scroll_into_view_if_needed()
    dropdown.click()

    panel = page.locator("div.p-dropdown-panel").last
    panel.wait_for(state="visible")

    panel.locator("li[role='option']", has_text=field_type).click()

    print(f"✅ Field {field_index} set")


# ---------------------------
# Add Serialized IDs
# ---------------------------
def add_ids(page, Config):

    for index, id_name in enumerate(Config.ids, start=1):

        field = page.locator(f"input[formcontrolname='id{index}Name']")
        field.wait_for(state="visible")
        field.fill(id_name)

        print(f"✅ ID {index} added → {id_name}")

        if index < len(Config.ids):

            add_btn = page.locator("button", has_text="Add ID")
            add_btn.click()

            page.wait_for_selector(
                f"input[formcontrolname='id{index+1}Name']"
            )

def add_field_types(page,field_types):

    for index, field_type in enumerate(field_types, start=2):
        add_field(page, index, field_type)

# ---------------------------
# Automation Logic
# ---------------------------
def create_group(page, Config):
    page.click("img[src*='Item_icon.svg']")
    page.wait_for_timeout(500)

    page.click("a[href*='itemGroup']")
    page.wait_for_timeout(500)

    page.click("button:has-text('Add Item Group')")
    page.wait_for_timeout(500)
    print("Add Item Group")

    page.fill("input[formcontrolname='groupName']", Config.group_name)

    # ✅ Fixed: pass both Config and inventory_type
    select_inventory_type(page, Config, Config.inventory_type)

    # ✅ Fixed: pass Config
    if Config.inventory_type == "Serialized":
        add_ids(page, Config)

    page.locator("input[placeholder='Barcode']").click()
    print("Click Barcode Config")

    # ✅ Fixed: pass field_types
    add_field_types(page, Config.fields)

    ok_btn = page.get_by_role("button", name="Ok")
    ok_btn.wait_for(state="visible")
    ok_btn.click()
    print("click OK")
    page.wait_for_timeout(500)

    page.click("button:has-text('Save')")
    page.click("button:has-text('Back')")

    # Verify Dropdown
    #select_item_group(page, Config.group_name)

