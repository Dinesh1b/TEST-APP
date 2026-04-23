/*
   Q-ARunner — config.js
   Supports 16 modules (0-15) and Auditor 2 logic.
*/

window.fv = id => document.getElementById(id)?.value ?? '';
window.ftaLines = id => (window.fv(id) || '').split('\n').map(x => x.trim()).filter(Boolean);

const v = id => document.getElementById(id)?.value ?? '';
const bv = id => document.getElementById(id)?.checked ?? false;

const getConfig = () => {

  const grp = Array.isArray(window.grpEnabled) ? window.grpEnabled : [false, false, false, false];
  const mod = Array.isArray(window.modEnabled) ? window.modEnabled : new Array(16).fill(false);
  const up = window._uploadedPaths || {};

  /* Audit type */
  const aType = v('A_Type') || 'Audit_plan';
  const apOn = !!grp[1];
  const tzOn = apOn && aType === 'Audit_plan' && bv('cb-tz');
  const caOn = apOn && aType === 'Audit_plan' && bv('cb-ca');
  const ahOn = apOn && aType === 'Ad_hoc' && bv('cb-adhoc-run');

  /* Inventory type */
  const invTypeCard = document.querySelector('.inv-type-card.selected');
  const invType = invTypeCard ? invTypeCard.id.replace('invcard_', '') : 'Serialized';

  /* ----------------------------------------------------------
     MODULE INDEX → FLAG NAME MAP
  ---------------------------------------------------------- */
  const IDX_TO_NAME = {
    0: 'Q_Setting',
    1: 'Q_SA',
    2: 'Q_SA1',
    3: 'Q_as_table',
    4: 'Q_Recently_Audit',
    5: 'Q_audit_Summary',
    6: caOn ? 'Audit_Plan' : ahOn ? 'Ad_hoc_Audit' : 'Audit_Plan',
    7: 'Ongoing_Audit',
    8: 'A_SA',
    9: 'A_SA2',
    10: 'A_as_table',
    11: 'A_audit_Summary',
    12: 'A_Recently_Audit',
    13: 'Create_Group',
    14: 'Location_Setup',
    15: 'Import_App',
  };

  /* Get drag-ordered enabled indices from queue.js */
  const _order = (typeof window.getQueueOrder === 'function')
    ? window.getQueueOrder()
    : (() => {
      const out = [];
      if (grp[0]) [0, 1, 2, 3, 4, 5].forEach(i => { if (mod[i]) out.push(i); });
      if (grp[1]) [6, 7, 8, 9, 10, 11, 12].forEach(i => { if (mod[i]) out.push(i); });
      if (grp[2]) [13, 14, 15].forEach(i => { if (mod[i]) out.push(i); });
      return out;
    })();

  const modules = _order.map(i => IDX_TO_NAME[i]).filter(Boolean);

  /* ----------------------------------------------------------
     INDIVIDUAL BOOLEAN RUN FLAGS
  ---------------------------------------------------------- */
  const run_q_setting = !!(grp[0] && mod[0]);
  const run_Q_SA = !!(grp[0] && mod[1]);
  const run_Q_SA1 = !!(grp[0] && mod[2]);
  const run_Q_as_table = !!(grp[0] && mod[3]);
  const run_Q_Recently_Audit = !!(grp[0] && mod[4]);
  const run_Q_audit_Summary = !!(grp[0] && mod[5]);

  const run_timezone = !!tzOn;
  const run_create_audit = !!caOn;
  const run_create_Ad_hoc_Audit = !!ahOn;
  const run_setup_Audit = !!(grp[1] && mod[7]);
  const run_A_SA = !!(grp[1] && mod[8]);
  const run_A_SA2 = !!(grp[1] && mod[9]);
  const run_A_as_table = !!(grp[1] && mod[10]);
  const run_A_audit_Summary = !!(grp[1] && mod[11]);
  const run_A_Recently_Audit = !!(grp[1] && mod[12]);

  const run_create_group = !!(grp[2] && mod[13]);
  const run_locatio_setup = !!(grp[2] && mod[14]);
  const run_import_app = !!(grp[2] && mod[15]);

  /* Sub-action of run_A_SA2: only fires when SA2 page is running */
  const run_new_add_item2 = run_A_SA2 && bv('cb-nai2');

  return {
    DEFAULT_TIMEOUT: parseInt(v('DEFAULT_TIMEOUT')) || 10000,
    SHORT_TIMEOUT: parseInt(v('SHORT_TIMEOUT')) || 5000,
    WAIT_AFTER_ACTION: parseInt(v('WAIT_AFTER_ACTION')) || 300,

    browsername: v('browsername') || 'chrome',
    environments: v('environments') || 'QA',
    Branch: v('branch') || 'nm',

    USE_CUSTOM_LOGIN: bv('use_custom_login'),
    email: v('email') || null,
    password: v('password') || null,

    run_Q_audit: grp[0],
    run_Audit_plan: grp[1],
    run_inventory: grp[2],

    MODULE_RUN_ORDER: _order,
    modules,

    run_q_setting,
    run_Q_SA,
    run_Q_SA1,
    run_Q_as_table,
    run_Q_Recently_Audit,
    run_Q_audit_Summary,
    run_timezone,
    run_create_audit,
    run_create_Ad_hoc_Audit,
    run_setup_Audit,
    run_A_SA,
    run_new_add_item2,
    run_A_SA2,
    run_A_audit_Summary,
    run_A_as_table,
    run_A_Recently_Audit,
    run_create_group,
    run_locatio_setup,
    run_import_app,

    A_Type: aType,

    /* -- Q_Setting -- */
    audit_name: v('qs-audit-name') || 'Audit_TEST',
    Auditor_name1: v('qs-a1') || null,
    Auditor_name2: v('qs-a2') || null,
    Auditor_name3: v('qs-a3') || null,
    Checkboxes_Audit_Damaged: bv('cb-damaged'),
    Checkboxes_StockItems: bv('cb-stock'),
    Checkboxes_geo: bv('cb-geo'),
    Checkboxes_photo: bv('cb-photo'),
    qs_sheet: v('qs-sheet'),

    /* -- Global Excel / Mapping -- */
    EXCEL_PATH: up['OA_EXCEL'] || up['EXCEL_PATH'] || '',
    AUDITOR_MAPPING_TYPE: v('AUDITOR_MAPPING_TYPE') || 'Random',
    EXCEL_SHEET_AUDITOR_MAPPING: v('EXCEL_SHEET_AUDITOR_MAPPING') || '',
    EXCEL_auditor_col: v('EXCEL_auditor_col') || 'Auditor',
    EXCEL_category_col: v('EXCEL_category_col') || 'Category',
    EXCEL_storage_col: v('EXCEL_storage_col') || 'Storage',

    /* -- Stock Audit A1 (Auditor 1) -- */
    location1: v('location1') || 'SA-A1',
    code1: v('code1') || 'ABC1123',
    aud_qty1: parseInt(v('aud_qty1')) || 0,
    dam_qty1: parseInt(v('dam_qty1')) || 0,

    ITEM_CODE1: v('asa-item-code') || 'ABC1123',
    ITEM_NAME1: v('asa-item-name') || 'Test Item',
    CATEGORY1: v('asa-category') || 'Gear',
    COST_PRICE1: v('asa-cp') || '100',
    SELL_PRICE1: v('asa-sp') || '100',
    LOCATION1: v('asa-location') || 'SA-A1',
    BARCODE1: v('asa-barcode') || '123456789',
    UOM1: v('asa-uom') || 'PCS',
    audited_qty1: parseInt(v('asa-aud-qty')) || 10,
    damaged_qty1: parseInt(v('asa-dam-qty')) || 0,

    EXCEL_SHEET_auditor_1: v('asa-sheet') || 'auditor_1',
    EXCEL_LOCATION_COL1: v('asa-loc-col') || 'locations',
    EXCEL_CODE_COL1: v('asa-code-col') || 'code',
    EXCEL_AUDITED_COL1: v('asa-aud-col') || 'audited',
    EXCEL_DAMAGED_COL1: v('asa-dam-col') || 'damaged',

    /* -- Stock Audit A2 (Auditor 2) -- */
    location2: v('location2') || 'SA-A1',
    code2: v('code2') || 'ABC1123',
    aud_qty2: parseInt(v('aud_qty2')) || 0,
    dam_qty2: parseInt(v('dam_qty2')) || 0,

    ITEM_CODE2: v('asa2-item-code') || 'ABC1123',
    ITEM_NAME2: v('asa2-item-name') || 'Test Item',
    CATEGORY2: v('asa2-category') || 'Gear',
    COST_PRICE2: v('asa2-cp') || '100',
    SELL_PRICE2: v('asa2-sp') || '100',
    LOCATION2: v('asa2-location') || 'SA-A1',
    BARCODE2: v('asa2-barcode') || '123456789',
    UOM2: v('asa2-uom') || 'PCS',
    audited_qty2: parseInt(v('asa2-aud-qty')) || 10,
    damaged_qty2: parseInt(v('asa2-dam-qty')) || 0,

    EXCEL_SHEET_auditor_2: v('asa2-sheet') || 'auditor_2',
    EXCEL_LOCATION_COL2: v('asa2-loc-col') || 'locations',
    EXCEL_CODE_COL2: v('asa2-code-col') || 'code',
    EXCEL_AUDITED_COL2: v('asa2-aud-col') || 'audited',
    EXCEL_DAMAGED_COL2: v('asa2-dam-col') || 'damaged',

    email2: v('asa2-email') || v('email2') || null,
    password2: v('asa2-password') || v('password2') || null,

    /* -- Reports / Summary -- */
    EXCEL_SHEET_audit_Summary: v('EXCEL_SHEET_audit_Summary') || 'auditSummary',
    FILTER_COLUMN: v('FILTER_COLUMN') || 'filter',
    EXCEL_SHEET_as_table: v('EXCEL_SHEET_as_table') || 'as_table',
    EXCEL_SHEET_Recently_Audit: v('EXCEL_SHEET_Recently_Audit') || 'Recently_Audit',

    /* -- Audit Plan details -- */
    Audit_Owner: v('ap-owner') || 'Dinesh B',
    Auditor1: v('ap-auditor1') || '',
    Auditor2: v('ap-auditor2') || '',
    Group_Name: v('ap-group') || '',
    ap_audit_name: v('ap-audit-name') || '',
    Audit_Type: v('ap-audit-type') || 'Complete Count',
    frequency: v('ap-frequency') || 'one-time',
    Day_s: parseInt(v('ap-days')) || 30,
    Target__Day: v('ap-target-day') || 'Thursday',
    Target_Date: v('ap-target-date') || '05/03/2026',
    A_Checkboxes_Audit_Damaged: bv('ap-cb-damaged'),
    A_Checkboxes_StockItems: bv('ap-cb-stock'),
    A_Checkboxes_geo: bv('ap-cb-geo'),
    A_Checkboxes_photo: bv('ap-cb-photo'),

    CROSS_AUDIT_TYPE: v('ap-cross-type') || 'Random Recheck',
    CROSS_Auditor_name: v('ap-cross-auditor') || 'Dinesh',
    AUDIT_MAPPING_TYPE: v('AUDIT_MAPPING_TYPE') || 'Random',

    Auditor1_adhoc: v('ah-auditor1') || '',
    Auditor2_adhoc: v('ah-auditor2') || '',
    Group_Name_adhoc: v('ah-group') || '',
    ap_audit_name_adhoc: v('ah-audit-name') || '',

    /* -- Ongoing Audit -- */
    oa_group_name: v('oa-group-name') || '',
    ap_audit_name: v('oa-audit-name') || '',
    oa_email: v('oa-email') || null,
    oa_password: v('oa-password') || null,
    oa_excel_path: up['OA_EXCEL'] || up['EXCEL_PATH'] || '',
    oa_sheet: v('oa-sheet') || 'Data',

    /* -- Ongoing Audit: auditors, checkboxes, mapping -- */
    oa_Auditor1: v('oa-auditor1') || '',
    oa_Auditor2: v('oa-auditor2') || '',
    oa_A_Checkboxes_Audit_Damaged: bv('oa-cb-damaged'),
    oa_A_Checkboxes_StockItems:    bv('oa-cb-stock'),
    oa_A_Checkboxes_geo:           bv('oa-cb-geo'),
    oa_A_Checkboxes_photo:         bv('oa-cb-photo'),

    oa_mapping: (() => {
      try {
        return JSON.parse(v('oa-mapping') || '{}');
      } catch (e) {
        return {};
      }
    })(),

    /* -- Global Mapping (Shared with Ongoing Audit UI) -- */
    AUDITOR_MAPPING_TYPE:        v('oa-mapping-type')  || v('AUDITOR_MAPPING_TYPE') || 'Random',
    EXCEL_SHEET_AUDITOR_MAPPING: v('oa-mapping-sheet') || v('EXCEL_SHEET_AUDITOR_MAPPING') || '',
    EXCEL_auditor_col:           v('oa-auditor-col')   || v('EXCEL_auditor_col')   || 'Auditor',
    EXCEL_category_col:          v('oa-category-col')  || v('EXCEL_category_col')  || 'Category',
    EXCEL_storage_col:           v('oa-storage-col')   || v('EXCEL_storage_col')   || 'Storage',

    /* -- Inventory -- */
    inv_group_name: v('inv-group-name') || 'Group_34',
    inventory_type: invType,
    inv_fields: window.ftaLines ? window.ftaLines('inv-fields') : [],
    inv_ids: window.ftaLines ? window.ftaLines('inv-ids') : [],

    /* -- Location Setup -- */
    ls_zones: v('ls-zones') || 'SA',
    ls_aisles: v('ls-aisles') || 'A1',
    ls_bays: v('ls-bays') || 'B1',
    ls_levels: v('ls-levels') || 'L1',

    /* -- Import Items -- */
    EXCEL_FILE: up['IMPORT_EXCEL'] || '',
    sheet_name: v('ii-sheet-name') || 'Data',
    run_add_item: bv('cb-run-add-item'),
    run_quick_add_items: bv('cb-quick-add'),
    run_import_items: bv('cb-import-excel'),
    Item_Name: v('ii-item-name') || '',
    Item_Code: v('ii-item-code') || '',
    Item_UOM: v('ii-item-uom') || 'PCS',
    Item_Category: v('ii-category') || '',
    Item_Tag: v('ii-tag') || '',
    Item_CP: parseFloat(v('ii-cp')) || 0,
    Item_SP: parseFloat(v('ii-sp')) || 0,
    Item_Barcode: v('ii-barcode') || '',

    /* -- Re-mapping for legacy keys if needed -- */
    asa_sheet: v('asa-sheet') || 'auditor_1',
    asa_loc_col: v('asa-loc-col') || 'locations',
    asa_code_col: v('asa-code-col') || 'code',
    asa_aud_col: v('asa-aud-col') || 'audited',
    asa_dam_col: v('asa-dam-col') || 'damaged',
  };
};

window.buildCfg = () => {
  if (document.activeElement && typeof document.activeElement.blur === 'function') {
    document.activeElement.blur();
  }
  return getConfig();
};

console.info('[QA] config.js updated to v9 ✓');
