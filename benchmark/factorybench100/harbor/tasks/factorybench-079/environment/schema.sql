PRAGMA foreign_keys = ON;

CREATE TABLE organizations (
    organization_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    ledger_currency TEXT NOT NULL
);

CREATE TABLE plants (
    plant_id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(organization_id),
    name TEXT NOT NULL,
    timezone TEXT NOT NULL
);

CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    plant_id TEXT NOT NULL REFERENCES plants(plant_id),
    approval_limit REAL NOT NULL DEFAULT 0
);

CREATE TABLE items (
    item_id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(organization_id),
    description TEXT NOT NULL,
    item_type TEXT NOT NULL,
    uom TEXT NOT NULL,
    unit_cost REAL NOT NULL,
    make_buy TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE bom_headers (
    bom_id TEXT PRIMARY KEY,
    assembly_item_id TEXT NOT NULL REFERENCES items(item_id),
    revision TEXT NOT NULL,
    effective_on TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE bom_components (
    bom_id TEXT NOT NULL REFERENCES bom_headers(bom_id),
    component_item_id TEXT NOT NULL REFERENCES items(item_id),
    quantity_per REAL NOT NULL,
    yield_factor REAL NOT NULL DEFAULT 1,
    operation_sequence INTEGER NOT NULL,
    PRIMARY KEY (bom_id, component_item_id)
);

CREATE TABLE suppliers (
    supplier_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    approved INTEGER NOT NULL,
    quality_score REAL NOT NULL,
    on_time_rate REAL NOT NULL,
    payment_terms TEXT NOT NULL
);

CREATE TABLE supplier_quotes (
    quote_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    supplier_id TEXT NOT NULL REFERENCES suppliers(supplier_id),
    item_id TEXT NOT NULL REFERENCES items(item_id),
    unit_price REAL NOT NULL,
    lead_days INTEGER NOT NULL,
    minimum_qty REAL NOT NULL,
    valid_until TEXT NOT NULL
);

CREATE TABLE sales_orders (
    sales_order_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    status TEXT NOT NULL,
    credit_hold INTEGER NOT NULL,
    requested_date TEXT NOT NULL,
    priority TEXT NOT NULL
);

CREATE TABLE sales_order_lines (
    sales_order_id TEXT NOT NULL REFERENCES sales_orders(sales_order_id),
    line_no INTEGER NOT NULL,
    item_id TEXT NOT NULL REFERENCES items(item_id),
    ordered_qty REAL NOT NULL,
    shipped_qty REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (sales_order_id, line_no)
);

CREATE TABLE workcenters (
    workcenter_id TEXT PRIMARY KEY,
    plant_id TEXT NOT NULL REFERENCES plants(plant_id),
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    capacity_hours REAL NOT NULL,
    qualified_item_class TEXT NOT NULL
);

CREATE TABLE work_orders (
    work_order_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    sales_order_id TEXT,
    item_id TEXT NOT NULL REFERENCES items(item_id),
    quantity REAL NOT NULL,
    completed_qty REAL NOT NULL DEFAULT 0,
    scrap_qty REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    scheduled_start TEXT NOT NULL,
    scheduled_completion TEXT NOT NULL,
    parent_work_order_id TEXT,
    workcenter_id TEXT REFERENCES workcenters(workcenter_id)
);

CREATE TABLE work_order_operations (
    work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
    sequence INTEGER NOT NULL,
    workcenter_id TEXT NOT NULL REFERENCES workcenters(workcenter_id),
    status TEXT NOT NULL,
    planned_hours REAL NOT NULL,
    actual_hours REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (work_order_id, sequence)
);

CREATE TABLE material_requirements (
    work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
    item_id TEXT NOT NULL REFERENCES items(item_id),
    required_qty REAL NOT NULL,
    reserved_qty REAL NOT NULL DEFAULT 0,
    issued_qty REAL NOT NULL DEFAULT 0,
    need_by TEXT NOT NULL,
    PRIMARY KEY (work_order_id, item_id)
);

CREATE TABLE inventory_on_hand (
    plant_id TEXT NOT NULL REFERENCES plants(plant_id),
    subinventory TEXT NOT NULL,
    item_id TEXT NOT NULL REFERENCES items(item_id),
    lot_number TEXT NOT NULL,
    quantity REAL NOT NULL,
    reserved_qty REAL NOT NULL DEFAULT 0,
    expiration_date TEXT,
    status TEXT NOT NULL,
    PRIMARY KEY (plant_id, subinventory, item_id, lot_number)
);

CREATE TABLE material_reservations (
    reservation_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
    item_id TEXT NOT NULL REFERENCES items(item_id),
    plant_id TEXT NOT NULL REFERENCES plants(plant_id),
    subinventory TEXT NOT NULL,
    lot_number TEXT NOT NULL,
    quantity REAL NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE material_transactions (
    transaction_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    work_order_id TEXT,
    item_id TEXT NOT NULL REFERENCES items(item_id),
    plant_id TEXT NOT NULL REFERENCES plants(plant_id),
    subinventory TEXT NOT NULL,
    lot_number TEXT NOT NULL,
    quantity REAL NOT NULL,
    occurred_at TEXT NOT NULL,
    reference TEXT NOT NULL
);

CREATE TABLE purchase_requisitions (
    requisition_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    requester_id TEXT NOT NULL REFERENCES users(user_id),
    work_order_id TEXT,
    status TEXT NOT NULL,
    supplier_id TEXT REFERENCES suppliers(supplier_id),
    total_amount REAL NOT NULL,
    need_by TEXT NOT NULL,
    approved_by TEXT
);

CREATE TABLE requisition_lines (
    requisition_id TEXT NOT NULL REFERENCES purchase_requisitions(requisition_id),
    line_no INTEGER NOT NULL,
    item_id TEXT NOT NULL REFERENCES items(item_id),
    quantity REAL NOT NULL,
    unit_price REAL NOT NULL,
    PRIMARY KEY (requisition_id, line_no)
);

CREATE TABLE purchase_orders (
    purchase_order_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    requisition_id TEXT,
    supplier_id TEXT NOT NULL REFERENCES suppliers(supplier_id),
    buyer_id TEXT NOT NULL REFERENCES users(user_id),
    status TEXT NOT NULL,
    total_amount REAL NOT NULL,
    promised_date TEXT NOT NULL,
    approved_by TEXT
);

CREATE TABLE purchase_order_lines (
    purchase_order_id TEXT NOT NULL REFERENCES purchase_orders(purchase_order_id),
    line_no INTEGER NOT NULL,
    item_id TEXT NOT NULL REFERENCES items(item_id),
    ordered_qty REAL NOT NULL,
    received_qty REAL NOT NULL DEFAULT 0,
    unit_price REAL NOT NULL,
    PRIMARY KEY (purchase_order_id, line_no)
);

CREATE TABLE receipts (
    receipt_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    purchase_order_id TEXT NOT NULL REFERENCES purchase_orders(purchase_order_id),
    status TEXT NOT NULL,
    received_at TEXT NOT NULL,
    receiver_id TEXT NOT NULL REFERENCES users(user_id)
);

CREATE TABLE receipt_lines (
    receipt_id TEXT NOT NULL REFERENCES receipts(receipt_id),
    line_no INTEGER NOT NULL,
    item_id TEXT NOT NULL REFERENCES items(item_id),
    quantity REAL NOT NULL,
    accepted_qty REAL NOT NULL DEFAULT 0,
    rejected_qty REAL NOT NULL DEFAULT 0,
    lot_number TEXT NOT NULL,
    PRIMARY KEY (receipt_id, line_no)
);

CREATE TABLE ap_invoices (
    invoice_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    purchase_order_id TEXT NOT NULL REFERENCES purchase_orders(purchase_order_id),
    receipt_id TEXT REFERENCES receipts(receipt_id),
    supplier_id TEXT NOT NULL REFERENCES suppliers(supplier_id),
    invoice_amount REAL NOT NULL,
    status TEXT NOT NULL,
    hold_reason TEXT
);

CREATE TABLE quality_inspections (
    inspection_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    item_id TEXT NOT NULL REFERENCES items(item_id),
    lot_number TEXT NOT NULL,
    inspected_qty REAL NOT NULL,
    accepted_qty REAL NOT NULL,
    rejected_qty REAL NOT NULL,
    result TEXT NOT NULL,
    inspector_id TEXT NOT NULL REFERENCES users(user_id)
);

CREATE TABLE quality_holds (
    hold_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    item_id TEXT NOT NULL REFERENCES items(item_id),
    lot_number TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    status TEXT NOT NULL,
    source_id TEXT NOT NULL
);

CREATE TABLE nonconformances (
    nonconformance_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    inspection_id TEXT NOT NULL REFERENCES quality_inspections(inspection_id),
    disposition TEXT NOT NULL,
    status TEXT NOT NULL,
    owner_id TEXT NOT NULL REFERENCES users(user_id)
);

CREATE TABLE inventory_transfers (
    transfer_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    item_id TEXT NOT NULL REFERENCES items(item_id),
    lot_number TEXT NOT NULL,
    from_plant TEXT NOT NULL REFERENCES plants(plant_id),
    from_subinventory TEXT NOT NULL,
    to_plant TEXT NOT NULL REFERENCES plants(plant_id),
    to_subinventory TEXT NOT NULL,
    quantity REAL NOT NULL,
    status TEXT NOT NULL,
    transferred_at TEXT NOT NULL
);

CREATE TABLE maintenance_work_orders (
    maintenance_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    workcenter_id TEXT NOT NULL REFERENCES workcenters(workcenter_id),
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    scheduled_start TEXT NOT NULL,
    expected_finish TEXT NOT NULL,
    failure_code TEXT NOT NULL
);

CREATE TABLE wip_variances (
    variance_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
    material_variance REAL NOT NULL,
    labor_variance REAL NOT NULL,
    overhead_variance REAL NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE documents (
    doc_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    body TEXT NOT NULL,
    sha256 TEXT NOT NULL
);

CREATE TABLE answers (
    task_id TEXT NOT NULL,
    field TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (task_id, field)
);

CREATE TABLE audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    table_name TEXT NOT NULL,
    record_id TEXT NOT NULL,
    action TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX idx_sales_orders_task ON sales_orders(task_id);
CREATE INDEX idx_work_orders_task ON work_orders(task_id);
CREATE INDEX idx_quotes_task ON supplier_quotes(task_id);
CREATE INDEX idx_purchase_orders_task ON purchase_orders(task_id);
CREATE INDEX idx_receipts_task ON receipts(task_id);
CREATE INDEX idx_invoices_task ON ap_invoices(task_id);
CREATE INDEX idx_inspections_task ON quality_inspections(task_id);
CREATE INDEX idx_documents_task ON documents(task_id);
CREATE INDEX idx_audit_task ON audit_log(task_id);
