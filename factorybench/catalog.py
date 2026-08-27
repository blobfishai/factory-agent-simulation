"""Deterministic FactoryBench-100 task catalog.

The benchmark is synthetic, but the records and control flow mirror the data
shape of production manufacturing ERP work: orders, BOMs, lots, sourcing,
receiving, three-way match, quality, WIP, transfers, and maintenance.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import date, timedelta
from typing import Any

BENCHMARK_NAME = "FactoryBench-100"
BENCHMARK_VERSION = "1.0.0"
AS_OF_DATE = date(2026, 1, 12)

FAMILIES = (
    "order_release",
    "material_shortage",
    "supplier_selection",
    "inbound_receipt",
    "invoice_match",
    "production_issue",
    "quality_exception",
    "completion_costing",
    "transfer_reschedule",
    "maintenance_recovery",
)

_POLICIES = {
    "order_release": (
        "Order release control",
        "Release only when the customer is not on credit hold, an effective BOM exists, "
        "and every component has enough available stock. Reserve the exact BOM quantity.",
    ),
    "material_shortage": (
        "Shortage requisition control",
        "Net requirements against unreserved on-hand. Use an approved supplier quote that "
        "is valid through the need-by date. Requisitions over the requester's limit require "
        "the plant manager's approval.",
    ),
    "supplier_selection": (
        "Supplier award policy",
        "Choose an approved supplier. Minimize landed price while meeting the need-by date; "
        "break ties by higher quality score, then higher on-time rate. Purchase orders above "
        "the buyer's limit require plant-manager approval.",
    ),
    "inbound_receipt": (
        "Receiving and inspection policy",
        "Receive only against an approved purchase order. Put the lot in inspection status, "
        "record accepted and rejected quantities, and release only accepted quantity to stores.",
    ),
    "invoice_match": (
        "Three-way match policy",
        "Compare invoice, approved PO, and accepted receipt. Approve when quantity is covered "
        "and the amount variance is at most 2 percent; otherwise place a variance hold.",
    ),
    "production_issue": (
        "Material issue policy",
        "Issue only reserved, unrestricted stock. Use FEFO across eligible lots and start the "
        "operation only after the full required quantity has been issued.",
    ),
    "quality_exception": (
        "Nonconformance policy",
        "A failed inspection requires an immediate lot hold and an open nonconformance. "
        "Use REWORK when the defect is recoverable and assign it to the quality engineer.",
    ),
    "completion_costing": (
        "Work-order close policy",
        "Complete all operations before closing the work order. Record finished quantity and "
        "scrap, then post material, labor, and overhead variance for finance review.",
    ),
    "transfer_reschedule": (
        "Interplant recovery policy",
        "Use unrestricted surplus from the donor plant, complete the interplant transfer, and "
        "reschedule the receiving work order no earlier than the transfer arrival date.",
    ),
    "maintenance_recovery": (
        "Unplanned downtime policy",
        "Open a high-priority maintenance work order for the failed workcenter. Reroute production "
        "only to a qualified active alternate and reschedule within that center's capacity.",
    ),
}

_INTEGER_ANSWER_FIELDS = {
    "completed_quantity",
    "issued_quantity",
    "net_shortage",
    "released_quantity",
    "scrap_quantity",
}
_DECIMAL_ANSWER_FIELDS = {"total_amount", "variance_percent"}


def _answer_schema(answer: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, dict[str, Any]] = {}
    for field in answer:
        if field in _INTEGER_ANSWER_FIELDS:
            properties[field] = {"type": "integer"}
        elif field in _DECIMAL_ANSWER_FIELDS:
            properties[field] = {"type": "number", "multipleOf": 0.01}
        else:
            properties[field] = {"type": "string"}
    return {
        "type": "object",
        "properties": properties,
        "required": sorted(answer),
        "additionalProperties": False,
    }


def _typed_answer(answer: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    typed: dict[str, Any] = {}
    for field, value in answer.items():
        answer_type = schema["properties"][field]["type"]
        if answer_type == "integer":
            typed[field] = int(value)
        elif answer_type == "number":
            typed[field] = float(value)
        else:
            typed[field] = str(value)
    return typed


def _row(**values: Any) -> dict[str, Any]:
    return values


def _base_seed(task_id: str) -> dict[str, list[dict[str, Any]]]:
    seed: dict[str, list[dict[str, Any]]] = {
        "organizations": [
            _row(organization_id="M1", name="Northstar Controls Manufacturing", ledger_currency="USD")
        ],
        "plants": [
            _row(plant_id="SEA", organization_id="M1", name="Seattle Assembly", timezone="America/Los_Angeles"),
            _row(plant_id="PDX", organization_id="M1", name="Portland Components", timezone="America/Los_Angeles"),
        ],
        "users": [
            _row(user_id="U-PLANNER", display_name="Maya Chen", role="production_planner", plant_id="SEA", approval_limit=0),
            _row(user_id="U-BUYER", display_name="Diego Ruiz", role="buyer", plant_id="SEA", approval_limit=1_000),
            _row(user_id="U-MANAGER", display_name="Avery Morgan", role="plant_manager", plant_id="SEA", approval_limit=250_000),
            _row(user_id="U-INSPECTOR", display_name="Priya Shah", role="quality_inspector", plant_id="SEA", approval_limit=0),
            _row(user_id="U-QUALITY", display_name="Noah Williams", role="quality_engineer", plant_id="SEA", approval_limit=0),
        ],
        "items": [
            _row(item_id="FG-PANEL", organization_id="M1", description="Industrial control panel", item_type="finished_good", uom="EA", unit_cost=910, make_buy="MAKE", status="Active"),
            _row(item_id="RM-HOUSING", organization_id="M1", description="Powder-coated enclosure", item_type="component", uom="EA", unit_cost=210, make_buy="BUY", status="Active"),
            _row(item_id="RM-RELAY", organization_id="M1", description="Safety relay", item_type="component", uom="EA", unit_cost=48, make_buy="BUY", status="Active"),
            _row(item_id="RM-COPPER", organization_id="M1", description="Copper busbar set", item_type="component", uom="EA", unit_cost=72, make_buy="BUY", status="Active"),
        ],
        "bom_headers": [
            _row(bom_id="BOM-PANEL-C", assembly_item_id="FG-PANEL", revision="C", effective_on="2025-10-01", status="Active")
        ],
        "bom_components": [
            _row(bom_id="BOM-PANEL-C", component_item_id="RM-HOUSING", quantity_per=1, yield_factor=1, operation_sequence=10),
            _row(bom_id="BOM-PANEL-C", component_item_id="RM-RELAY", quantity_per=2, yield_factor=1, operation_sequence=20),
            _row(bom_id="BOM-PANEL-C", component_item_id="RM-COPPER", quantity_per=1, yield_factor=1, operation_sequence=20),
        ],
        "suppliers": [
            _row(supplier_id="SUP-A", name="Cascade Industrial", approved=1, quality_score=97.2, on_time_rate=0.94, payment_terms="NET30"),
            _row(supplier_id="SUP-B", name="Rainier Components", approved=1, quality_score=95.8, on_time_rate=0.98, payment_terms="NET45"),
            _row(supplier_id="SUP-C", name="Frontier Supply", approved=0, quality_score=99.1, on_time_rate=0.99, payment_terms="NET30"),
        ],
        "workcenters": [
            _row(workcenter_id="WC-ASM-1", plant_id="SEA", name="Assembly Cell 1", status="Active", capacity_hours=80, qualified_item_class="control_panel"),
            _row(workcenter_id="WC-ASM-2", plant_id="SEA", name="Assembly Cell 2", status="Active", capacity_hours=64, qualified_item_class="control_panel"),
            _row(workcenter_id="WC-PDX-1", plant_id="PDX", name="Portland Fabrication", status="Active", capacity_hours=72, qualified_item_class="control_panel"),
        ],
        "documents": [],
    }
    for index, (family, (title, body)) in enumerate(_POLICIES.items(), start=1):
        policy_bytes = f"# {title}\n\n{body}\n".encode()
        seed["documents"].append(
            _row(
                doc_id=f"POL-{index:02d}",
                task_id=task_id,
                title=title,
                category=family,
                body=body,
                sha256=hashlib.sha256(policy_bytes).hexdigest(),
            )
        )
    return seed


def _asset(family: str) -> dict[str, str]:
    index = FAMILIES.index(family) + 1
    title, _ = _POLICIES[family]
    return {
        "asset_id": f"POL-{index:02d}",
        "kind": "policy",
        "title": title,
        "source": "plant_docs",
    }


def _step(tool: str, arguments: dict[str, Any], *, control: bool = False) -> dict[str, Any]:
    return {"tool": tool, "arguments": arguments, "control": control}


def _assertion(
    assertion_id: str,
    description: str,
    table: str,
    where: dict[str, Any],
    values: dict[str, Any] | None = None,
    *,
    count: int | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": assertion_id,
        "description": description,
        "table": table,
        "where": where,
    }
    if values is not None:
        result["values"] = values
    if count is not None:
        result["count"] = count
    return result


def _task(
    number: int,
    variant: int,
    family: str,
    title: str,
    role: str,
    instruction: str,
    seed: dict[str, list[dict[str, Any]]],
    required_reads: list[str],
    allowed_write_tables: list[str],
    oracle_steps: list[dict[str, Any]],
    assertions: list[dict[str, Any]],
    answer: dict[str, Any],
    level: str,
) -> dict[str, Any]:
    task_id = f"factorybench-{number:03d}"
    answer_schema = _answer_schema(answer)
    typed_answer = _typed_answer(answer, answer_schema)
    for step in oracle_steps:
        if step["tool"] == "submit_answer":
            step["arguments"] = deepcopy(typed_answer)
    return {
        "benchmark": BENCHMARK_NAME,
        "benchmark_version": BENCHMARK_VERSION,
        "task_id": task_id,
        "family": family,
        "variant": variant,
        "level": level,
        "title": title,
        "role": role,
        "instruction": instruction,
        "as_of": AS_OF_DATE.isoformat(),
        "world": {
            "name": "Northstar Controls Oracle-shaped ERP",
            "organization_id": "M1",
            "primary_plant": "SEA",
            "database": "SQLite",
            "servers": ["oracle_erp", "plant_docs", "factory_harness"],
        },
        "assets": [_asset(family)],
        "seed_tables": seed,
        "required_reads": required_reads,
        "required_read_calls": [
            {"tool": step["tool"], "arguments": deepcopy(step["arguments"])}
            for step in oracle_steps
            if step.get("control")
        ],
        "answer_schema": answer_schema,
        "allowed_write_tables": allowed_write_tables + ["answers", "audit_log"],
        "oracle_steps": oracle_steps,
        "expected": {"assertions": assertions, "answer": typed_answer},
        "evaluation": {
            "metric": "FactoryScore",
            "definition": "100 × passed deterministic workflow checks / total checks",
            "checks": [
                "required read-before-write controls",
                "expected ERP state transitions",
                "exact submitted answer fields",
                "write-scope containment",
                "error-free tool execution",
            ],
        },
    }


def _new_seed(task_id: str) -> dict[str, list[dict[str, Any]]]:
    return deepcopy(_base_seed(task_id))


def _order_release(number: int, variant: int) -> dict[str, Any]:
    task_id = f"factorybench-{number:03d}"
    seed = _new_seed(task_id)
    qty = 4 + variant
    so_id = f"SO-{variant:04d}"
    wo_id = f"WO-{variant:04d}"
    start = AS_OF_DATE + timedelta(days=variant)
    completion = start + timedelta(days=3)
    seed["sales_orders"] = [_row(sales_order_id=so_id, task_id=task_id, customer_name=f"Atlas Systems {variant}", status="Booked", credit_hold=0, requested_date=completion.isoformat(), priority="High" if variant % 3 == 0 else "Standard")]
    seed["sales_order_lines"] = [_row(sales_order_id=so_id, line_no=1, item_id="FG-PANEL", ordered_qty=qty, shipped_qty=0)]
    seed["inventory_on_hand"] = [
        _row(plant_id="SEA", subinventory="STORES", item_id="RM-HOUSING", lot_number=f"H-{variant:03d}", quantity=qty + 3, reserved_qty=0, expiration_date=None, status="Unrestricted"),
        _row(plant_id="SEA", subinventory="STORES", item_id="RM-RELAY", lot_number=f"R-{variant:03d}", quantity=qty * 2 + 4, reserved_qty=0, expiration_date="2027-06-30", status="Unrestricted"),
        _row(plant_id="SEA", subinventory="STORES", item_id="RM-COPPER", lot_number=f"C-{variant:03d}", quantity=qty + 2, reserved_qty=0, expiration_date=None, status="Unrestricted"),
    ]
    steps = [
        _step("search_documents", {"category": "order_release"}, control=True),
        _step("get_sales_order", {"sales_order_id": so_id}, control=True),
        _step("get_bom", {"item_id": "FG-PANEL", "as_of": AS_OF_DATE.isoformat()}, control=True),
        _step("get_inventory", {"plant_id": "SEA", "item_ids": ["RM-HOUSING", "RM-RELAY", "RM-COPPER"]}, control=True),
        _step("create_work_order", {"work_order_id": wo_id, "sales_order_id": so_id, "item_id": "FG-PANEL", "quantity": qty, "scheduled_start": start.isoformat(), "scheduled_completion": completion.isoformat(), "workcenter_id": "WC-ASM-1"}),
        _step("reserve_material", {"reservation_id": f"RES-H-{variant:03d}", "work_order_id": wo_id, "item_id": "RM-HOUSING", "plant_id": "SEA", "subinventory": "STORES", "lot_number": f"H-{variant:03d}", "quantity": qty}),
        _step("reserve_material", {"reservation_id": f"RES-R-{variant:03d}", "work_order_id": wo_id, "item_id": "RM-RELAY", "plant_id": "SEA", "subinventory": "STORES", "lot_number": f"R-{variant:03d}", "quantity": qty * 2}),
        _step("reserve_material", {"reservation_id": f"RES-C-{variant:03d}", "work_order_id": wo_id, "item_id": "RM-COPPER", "plant_id": "SEA", "subinventory": "STORES", "lot_number": f"C-{variant:03d}", "quantity": qty}),
        _step("submit_answer", {"work_order_id": wo_id, "released_quantity": str(qty), "completion_date": completion.isoformat()}),
    ]
    assertions = [
        _assertion("work_order_released", "A released discrete work order links to the sales order.", "work_orders", {"work_order_id": wo_id}, {"sales_order_id": so_id, "quantity": qty, "status": "Released"}),
        _assertion("all_components_reserved", "All three BOM components are reserved.", "material_reservations", {"work_order_id": wo_id, "status": "Active"}, count=3),
        _assertion("relay_requirement_reserved", "The two-per-assembly relay requirement is fully reserved.", "material_requirements", {"work_order_id": wo_id, "item_id": "RM-RELAY"}, {"required_qty": qty * 2, "reserved_qty": qty * 2}),
    ]
    answer = {"work_order_id": wo_id, "released_quantity": str(qty), "completion_date": completion.isoformat()}
    instruction = f"Release sales order {so_id} for {qty} FG-PANEL units into production at SEA. Check the governing policy, credit status, effective BOM, and component availability; create and fully reserve the work order. Return the work-order ID, released quantity, and scheduled completion date."
    return _task(number, variant, "order_release", f"Release {so_id} to manufacturing", "production_planner", instruction, seed, ["search_documents", "get_sales_order", "get_bom", "get_inventory"], ["work_orders", "work_order_operations", "material_requirements", "material_reservations", "inventory_on_hand"], steps, assertions, answer, "L2")


def _material_shortage(number: int, variant: int) -> dict[str, Any]:
    task_id = f"factorybench-{number:03d}"
    seed = _new_seed(task_id)
    required = 18 + variant * 2
    on_hand = 3 + variant % 4
    shortage = required - on_hand
    wo_id = f"WO-S-{variant:03d}"
    req_id = f"REQ-{variant:04d}"
    need_by = AS_OF_DATE + timedelta(days=18 + variant)
    price_a = 70 + variant / 10
    price_b = 72 + variant / 10
    total = round(shortage * price_a, 2)
    seed["work_orders"] = [_row(work_order_id=wo_id, task_id=task_id, sales_order_id=None, item_id="FG-PANEL", quantity=required, completed_qty=0, scrap_qty=0, status="Released", scheduled_start=(need_by - timedelta(days=2)).isoformat(), scheduled_completion=need_by.isoformat(), parent_work_order_id=None, workcenter_id="WC-ASM-1")]
    seed["material_requirements"] = [_row(work_order_id=wo_id, item_id="RM-COPPER", required_qty=required, reserved_qty=0, issued_qty=0, need_by=(need_by - timedelta(days=3)).isoformat())]
    seed["inventory_on_hand"] = [_row(plant_id="SEA", subinventory="STORES", item_id="RM-COPPER", lot_number=f"CS-{variant:03d}", quantity=on_hand, reserved_qty=0, expiration_date=None, status="Unrestricted")]
    seed["supplier_quotes"] = [
        _row(quote_id=f"QA-{variant:03d}", task_id=task_id, supplier_id="SUP-A", item_id="RM-COPPER", unit_price=price_a, lead_days=5, minimum_qty=5, valid_until=(need_by + timedelta(days=5)).isoformat()),
        _row(quote_id=f"QB-{variant:03d}", task_id=task_id, supplier_id="SUP-B", item_id="RM-COPPER", unit_price=price_b, lead_days=3, minimum_qty=5, valid_until=(need_by + timedelta(days=5)).isoformat()),
    ]
    steps = [
        _step("search_documents", {"category": "material_shortage"}, control=True),
        _step("get_work_order", {"work_order_id": wo_id}, control=True),
        _step("get_inventory", {"plant_id": "SEA", "item_ids": ["RM-COPPER"]}, control=True),
        _step("get_supplier_quotes", {"task_id": task_id, "item_id": "RM-COPPER", "need_by": need_by.isoformat()}, control=True),
        _step("create_requisition", {"requisition_id": req_id, "requester_id": "U-BUYER", "work_order_id": wo_id, "supplier_id": "SUP-A", "item_id": "RM-COPPER", "quantity": shortage, "unit_price": price_a, "need_by": need_by.isoformat()}),
        _step("approve_requisition", {"requisition_id": req_id, "approver_id": "U-MANAGER"}),
        _step("submit_answer", {"requisition_id": req_id, "net_shortage": str(shortage), "supplier_id": "SUP-A"}),
    ]
    assertions = [
        _assertion("requisition_approved", "The shortage is covered by an approved requisition.", "purchase_requisitions", {"requisition_id": req_id}, {"status": "Approved", "supplier_id": "SUP-A", "total_amount": total, "approved_by": "U-MANAGER"}),
        _assertion("net_quantity_ordered", "The requisition line equals net requirement after available stock.", "requisition_lines", {"requisition_id": req_id, "line_no": 1}, {"item_id": "RM-COPPER", "quantity": shortage, "unit_price": price_a}),
    ]
    answer = {"requisition_id": req_id, "net_shortage": str(shortage), "supplier_id": "SUP-A"}
    instruction = f"Work order {wo_id} is short RM-COPPER. Net the {required} required units against available SEA stock, select a valid approved quote that meets the need-by date {need_by.isoformat()}, create the requisition, and obtain any required approval. Return the requisition ID, net shortage, and supplier."
    return _task(number, variant, "material_shortage", f"Cover material shortage for {wo_id}", "material_planner", instruction, seed, ["search_documents", "get_work_order", "get_inventory", "get_supplier_quotes"], ["purchase_requisitions", "requisition_lines"], steps, assertions, answer, "L3")


def _supplier_selection(number: int, variant: int) -> dict[str, Any]:
    task_id = f"factorybench-{number:03d}"
    seed = _new_seed(task_id)
    req_id = f"REQ-A-{variant:03d}"
    po_id = f"PO-{variant:04d}"
    qty = 30 + variant * 2
    need_by = AS_OF_DATE + timedelta(days=14 + variant)
    price_a = 49.5 + variant / 10
    price_b = 48.0 + variant / 10
    total = round(qty * price_b, 2)
    seed["purchase_requisitions"] = [_row(requisition_id=req_id, task_id=task_id, requester_id="U-PLANNER", work_order_id=None, status="Approved", supplier_id=None, total_amount=0, need_by=need_by.isoformat(), approved_by="U-MANAGER")]
    seed["requisition_lines"] = [_row(requisition_id=req_id, line_no=1, item_id="RM-RELAY", quantity=qty, unit_price=0)]
    seed["supplier_quotes"] = [
        _row(quote_id=f"SQA-{variant:03d}", task_id=task_id, supplier_id="SUP-A", item_id="RM-RELAY", unit_price=price_a, lead_days=6, minimum_qty=10, valid_until=(need_by + timedelta(days=1)).isoformat()),
        _row(quote_id=f"SQB-{variant:03d}", task_id=task_id, supplier_id="SUP-B", item_id="RM-RELAY", unit_price=price_b, lead_days=4, minimum_qty=10, valid_until=(need_by + timedelta(days=1)).isoformat()),
        _row(quote_id=f"SQC-{variant:03d}", task_id=task_id, supplier_id="SUP-C", item_id="RM-RELAY", unit_price=price_b - 4, lead_days=2, minimum_qty=10, valid_until=(need_by + timedelta(days=1)).isoformat()),
    ]
    steps = [
        _step("search_documents", {"category": "supplier_selection"}, control=True),
        _step("get_requisition", {"requisition_id": req_id}, control=True),
        _step("get_supplier_quotes", {"task_id": task_id, "item_id": "RM-RELAY", "need_by": need_by.isoformat()}, control=True),
        _step("create_purchase_order", {"purchase_order_id": po_id, "requisition_id": req_id, "supplier_id": "SUP-B", "buyer_id": "U-BUYER", "item_id": "RM-RELAY", "quantity": qty, "unit_price": price_b, "promised_date": (AS_OF_DATE + timedelta(days=4)).isoformat()}),
        _step("approve_purchase_order", {"purchase_order_id": po_id, "approver_id": "U-MANAGER"}),
        _step("submit_answer", {"purchase_order_id": po_id, "supplier_id": "SUP-B", "total_amount": f"{total:.2f}"}),
    ]
    assertions = [
        _assertion("po_approved", "The purchase order is awarded to the best eligible supplier, meets the need-by date, and is approved.", "purchase_orders", {"purchase_order_id": po_id}, {"requisition_id": req_id, "supplier_id": "SUP-B", "status": "Approved", "total_amount": total, "promised_date": (AS_OF_DATE + timedelta(days=4)).isoformat(), "approved_by": "U-MANAGER"}),
        _assertion("po_line_exact", "The PO line preserves the approved requisition quantity.", "purchase_order_lines", {"purchase_order_id": po_id, "line_no": 1}, {"item_id": "RM-RELAY", "ordered_qty": qty, "unit_price": price_b}),
    ]
    answer = {"purchase_order_id": po_id, "supplier_id": "SUP-B", "total_amount": f"{total:.2f}"}
    instruction = f"Source requisition {req_id} for {qty} RM-RELAY units by {need_by.isoformat()}. Compare current quotes, exclude ineligible suppliers, award the purchase order, and obtain the approval required by policy. Return the PO ID, chosen supplier, and total amount."
    return _task(number, variant, "supplier_selection", f"Award sourcing event {req_id}", "buyer", instruction, seed, ["search_documents", "get_requisition", "get_supplier_quotes"], ["purchase_orders", "purchase_order_lines"], steps, assertions, answer, "L3")


def _inbound_receipt(number: int, variant: int) -> dict[str, Any]:
    task_id = f"factorybench-{number:03d}"
    seed = _new_seed(task_id)
    po_id = f"PO-R-{variant:03d}"
    receipt_id = f"RCV-{variant:04d}"
    inspection_id = f"INSP-R-{variant:03d}"
    qty = 24 + variant
    lot = f"LOT-R-{variant:04d}"
    seed["purchase_orders"] = [_row(purchase_order_id=po_id, task_id=task_id, requisition_id=None, supplier_id="SUP-B", buyer_id="U-BUYER", status="Approved", total_amount=round(qty * 48.5, 2), promised_date=AS_OF_DATE.isoformat(), approved_by="U-MANAGER")]
    seed["purchase_order_lines"] = [_row(purchase_order_id=po_id, line_no=1, item_id="RM-RELAY", ordered_qty=qty, received_qty=0, unit_price=48.5)]
    steps = [
        _step("search_documents", {"category": "inbound_receipt"}, control=True),
        _step("get_purchase_order", {"purchase_order_id": po_id}, control=True),
        _step("receive_purchase_order", {"receipt_id": receipt_id, "purchase_order_id": po_id, "receiver_id": "U-PLANNER", "item_id": "RM-RELAY", "quantity": qty, "lot_number": lot, "received_at": AS_OF_DATE.isoformat()}),
        _step("record_inspection", {"inspection_id": inspection_id, "source_type": "receipt", "source_id": receipt_id, "item_id": "RM-RELAY", "lot_number": lot, "inspected_qty": qty, "accepted_qty": qty, "rejected_qty": 0, "result": "Pass", "inspector_id": "U-INSPECTOR"}),
        _step("submit_answer", {"receipt_id": receipt_id, "inspection_id": inspection_id, "released_quantity": str(qty), "lot_number": lot}),
    ]
    assertions = [
        _assertion("receipt_complete", "The approved PO quantity is received into a traceable lot.", "receipts", {"receipt_id": receipt_id}, {"purchase_order_id": po_id, "status": "Inspected"}),
        _assertion("inspection_passed", "The full receipt has a passing inspection.", "quality_inspections", {"inspection_id": inspection_id}, {"accepted_qty": qty, "rejected_qty": 0, "result": "Pass"}),
        _assertion("accepted_stock_released", "Accepted stock is released to stores.", "inventory_on_hand", {"plant_id": "SEA", "subinventory": "STORES", "item_id": "RM-RELAY", "lot_number": lot}, {"quantity": qty, "status": "Unrestricted"}),
    ]
    answer = {"receipt_id": receipt_id, "inspection_id": inspection_id, "released_quantity": str(qty), "lot_number": lot}
    instruction = f"Receive the full {qty}-unit RM-RELAY shipment for approved PO {po_id}, lot {lot}. Record the required inspection, release only accepted quantity, and return the receipt, inspection, released quantity, and lot identifiers."
    return _task(number, variant, "inbound_receipt", f"Receive and inspect {po_id}", "receiving_agent", instruction, seed, ["search_documents", "get_purchase_order"], ["purchase_orders", "purchase_order_lines", "receipts", "receipt_lines", "quality_inspections", "inventory_on_hand"], steps, assertions, answer, "L2")


def _invoice_match(number: int, variant: int) -> dict[str, Any]:
    task_id = f"factorybench-{number:03d}"
    seed = _new_seed(task_id)
    po_id = f"PO-I-{variant:03d}"
    receipt_id = f"RCV-I-{variant:03d}"
    invoice_id = f"INV-{variant:04d}"
    qty = 20 + variant
    po_total = round(qty * 72, 2)
    should_hold = variant % 2 == 0
    invoice_total = round(po_total * (1.035 if should_hold else 1.01), 2)
    expected_status = "Hold" if should_hold else "Approved"
    hold_reason = "AMOUNT_VARIANCE" if should_hold else None
    seed["purchase_orders"] = [_row(purchase_order_id=po_id, task_id=task_id, requisition_id=None, supplier_id="SUP-A", buyer_id="U-BUYER", status="Approved", total_amount=po_total, promised_date=AS_OF_DATE.isoformat(), approved_by="U-MANAGER")]
    seed["purchase_order_lines"] = [_row(purchase_order_id=po_id, line_no=1, item_id="RM-COPPER", ordered_qty=qty, received_qty=qty, unit_price=72)]
    seed["receipts"] = [_row(receipt_id=receipt_id, task_id=task_id, purchase_order_id=po_id, status="Inspected", received_at=AS_OF_DATE.isoformat(), receiver_id="U-PLANNER")]
    seed["receipt_lines"] = [_row(receipt_id=receipt_id, line_no=1, item_id="RM-COPPER", quantity=qty, accepted_qty=qty, rejected_qty=0, lot_number=f"LOT-I-{variant:03d}")]
    seed["ap_invoices"] = [_row(invoice_id=invoice_id, task_id=task_id, purchase_order_id=po_id, receipt_id=receipt_id, supplier_id="SUP-A", invoice_amount=invoice_total, status="Pending", hold_reason=None)]
    action = "hold_invoice" if should_hold else "approve_invoice"
    action_args = {"invoice_id": invoice_id, "reason": "AMOUNT_VARIANCE"} if should_hold else {"invoice_id": invoice_id}
    steps = [
        _step("search_documents", {"category": "invoice_match"}, control=True),
        _step("get_purchase_order", {"purchase_order_id": po_id}, control=True),
        _step("get_receipt", {"receipt_id": receipt_id}, control=True),
        _step("get_invoice_match", {"invoice_id": invoice_id}, control=True),
        _step(action, action_args),
        _step("submit_answer", {"invoice_id": invoice_id, "decision": expected_status, "variance_percent": f"{((invoice_total - po_total) / po_total * 100):.2f}"}),
    ]
    assertions = [_assertion("invoice_decision", "The invoice receives the policy-correct three-way-match decision.", "ap_invoices", {"invoice_id": invoice_id}, {"status": expected_status, "hold_reason": hold_reason})]
    answer = {"invoice_id": invoice_id, "decision": expected_status, "variance_percent": f"{((invoice_total - po_total) / po_total * 100):.2f}"}
    instruction = f"Perform three-way match for invoice {invoice_id} against PO {po_id} and receipt {receipt_id}. The invoice is ${invoice_total:.2f}; apply the variance policy, update the invoice, and return the decision and variance percentage."
    return _task(number, variant, "invoice_match", f"Resolve three-way match for {invoice_id}", "accounts_payable_specialist", instruction, seed, ["search_documents", "get_purchase_order", "get_receipt", "get_invoice_match"], ["ap_invoices"], steps, assertions, answer, "L2")


def _production_issue(number: int, variant: int) -> dict[str, Any]:
    task_id = f"factorybench-{number:03d}"
    seed = _new_seed(task_id)
    wo_id = f"WO-I-{variant:03d}"
    qty = 10 + variant
    required = qty * 2
    early_lot = f"R-EARLY-{variant:03d}"
    late_lot = f"R-LATE-{variant:03d}"
    seed["work_orders"] = [_row(work_order_id=wo_id, task_id=task_id, sales_order_id=None, item_id="FG-PANEL", quantity=qty, completed_qty=0, scrap_qty=0, status="Released", scheduled_start=AS_OF_DATE.isoformat(), scheduled_completion=(AS_OF_DATE + timedelta(days=2)).isoformat(), parent_work_order_id=None, workcenter_id="WC-ASM-1")]
    seed["work_order_operations"] = [_row(work_order_id=wo_id, sequence=10, workcenter_id="WC-ASM-1", status="Ready", planned_hours=qty * 0.5, actual_hours=0)]
    seed["material_requirements"] = [_row(work_order_id=wo_id, item_id="RM-RELAY", required_qty=required, reserved_qty=required, issued_qty=0, need_by=AS_OF_DATE.isoformat())]
    seed["inventory_on_hand"] = [
        _row(plant_id="SEA", subinventory="STORES", item_id="RM-RELAY", lot_number=early_lot, quantity=required, reserved_qty=required, expiration_date="2026-06-30", status="Unrestricted"),
        _row(plant_id="SEA", subinventory="STORES", item_id="RM-RELAY", lot_number=late_lot, quantity=required + 10, reserved_qty=0, expiration_date="2027-06-30", status="Unrestricted"),
    ]
    seed["material_reservations"] = [_row(reservation_id=f"RES-I-{variant:03d}", task_id=task_id, work_order_id=wo_id, item_id="RM-RELAY", plant_id="SEA", subinventory="STORES", lot_number=early_lot, quantity=required, status="Active")]
    tx_id = f"TX-ISSUE-{variant:03d}"
    steps = [
        _step("search_documents", {"category": "production_issue"}, control=True),
        _step("get_work_order", {"work_order_id": wo_id}, control=True),
        _step("get_inventory", {"plant_id": "SEA", "item_ids": ["RM-RELAY"]}, control=True),
        _step("issue_material", {"transaction_id": tx_id, "work_order_id": wo_id, "item_id": "RM-RELAY", "plant_id": "SEA", "subinventory": "STORES", "lot_number": early_lot, "quantity": required, "occurred_at": AS_OF_DATE.isoformat()}),
        _step("start_operation", {"work_order_id": wo_id, "sequence": 10}),
        _step("submit_answer", {"work_order_id": wo_id, "issued_lot": early_lot, "issued_quantity": str(required), "operation_status": "In Process"}),
    ]
    assertions = [
        _assertion("fefo_issue", "The full requirement is issued from the reserved earliest-expiry lot.", "material_transactions", {"transaction_id": tx_id}, {"transaction_type": "WIP_ISSUE", "lot_number": early_lot, "quantity": required}),
        _assertion("requirement_issued", "The material requirement reflects the full issue.", "material_requirements", {"work_order_id": wo_id, "item_id": "RM-RELAY"}, {"issued_qty": required}),
        _assertion("operation_started", "The first operation starts after material issue.", "work_order_operations", {"work_order_id": wo_id, "sequence": 10}, {"status": "In Process"}),
    ]
    answer = {"work_order_id": wo_id, "issued_lot": early_lot, "issued_quantity": str(required), "operation_status": "In Process"}
    instruction = f"Stage and issue {required} RM-RELAY units to work order {wo_id}, honoring reservation and FEFO controls, then start operation 10. Return the work order, lot, issued quantity, and operation status."
    return _task(number, variant, "production_issue", f"Issue FEFO material to {wo_id}", "shop_floor_controller", instruction, seed, ["search_documents", "get_work_order", "get_inventory"], ["inventory_on_hand", "material_reservations", "material_requirements", "material_transactions", "work_order_operations", "work_orders"], steps, assertions, answer, "L3")


def _quality_exception(number: int, variant: int) -> dict[str, Any]:
    task_id = f"factorybench-{number:03d}"
    seed = _new_seed(task_id)
    inspection_id = f"INSP-Q-{variant:03d}"
    hold_id = f"HOLD-{variant:04d}"
    nc_id = f"NC-{variant:04d}"
    lot = f"FG-LOT-{variant:03d}"
    inspected = 8 + variant
    rejected = 1 + variant % 3
    seed["quality_inspections"] = [_row(inspection_id=inspection_id, task_id=task_id, source_type="work_order", source_id=f"WO-Q-{variant:03d}", item_id="FG-PANEL", lot_number=lot, inspected_qty=inspected, accepted_qty=inspected - rejected, rejected_qty=rejected, result="Fail", inspector_id="U-INSPECTOR")]
    seed["inventory_on_hand"] = [_row(plant_id="SEA", subinventory="FG", item_id="FG-PANEL", lot_number=lot, quantity=inspected, reserved_qty=0, expiration_date=None, status="Inspection")]
    steps = [
        _step("search_documents", {"category": "quality_exception"}, control=True),
        _step("get_quality_context", {"inspection_id": inspection_id}, control=True),
        _step("place_quality_hold", {"hold_id": hold_id, "inspection_id": inspection_id, "item_id": "FG-PANEL", "lot_number": lot, "reason_code": "FUNCTIONAL_TEST_FAIL"}),
        _step("create_nonconformance", {"nonconformance_id": nc_id, "inspection_id": inspection_id, "disposition": "REWORK", "owner_id": "U-QUALITY"}),
        _step("submit_answer", {"inspection_id": inspection_id, "hold_id": hold_id, "nonconformance_id": nc_id, "disposition": "REWORK"}),
    ]
    assertions = [
        _assertion("lot_held", "The failed lot is on an active quality hold.", "quality_holds", {"hold_id": hold_id}, {"lot_number": lot, "reason_code": "FUNCTIONAL_TEST_FAIL", "status": "Active"}),
        _assertion("nonconformance_opened", "A recoverable nonconformance is assigned for rework.", "nonconformances", {"nonconformance_id": nc_id}, {"inspection_id": inspection_id, "disposition": "REWORK", "status": "Open", "owner_id": "U-QUALITY"}),
        _assertion("inventory_quarantined", "The affected inventory remains quarantined.", "inventory_on_hand", {"plant_id": "SEA", "subinventory": "FG", "item_id": "FG-PANEL", "lot_number": lot}, {"status": "Quality Hold"}),
    ]
    answer = {"inspection_id": inspection_id, "hold_id": hold_id, "nonconformance_id": nc_id, "disposition": "REWORK"}
    instruction = f"Inspection {inspection_id} failed for lot {lot}, with {rejected} of {inspected} units rejected. Contain the lot and open the policy-correct quality record. Return the inspection, hold, nonconformance, and disposition."
    return _task(number, variant, "quality_exception", f"Contain failed lot {lot}", "quality_engineer", instruction, seed, ["search_documents", "get_quality_context"], ["quality_holds", "nonconformances", "inventory_on_hand"], steps, assertions, answer, "L2")


def _completion_costing(number: int, variant: int) -> dict[str, Any]:
    task_id = f"factorybench-{number:03d}"
    seed = _new_seed(task_id)
    wo_id = f"WO-C-{variant:03d}"
    qty = 12 + variant
    scrap = variant % 3
    completed = qty - scrap
    mat_var = round((variant - 5) * 12.5, 2)
    labor_var = round((variant % 4 - 2) * 18.0, 2)
    overhead_var = round((variant % 3 - 1) * 7.5, 2)
    variance_id = f"VAR-{variant:04d}"
    seed["work_orders"] = [_row(work_order_id=wo_id, task_id=task_id, sales_order_id=None, item_id="FG-PANEL", quantity=qty, completed_qty=0, scrap_qty=0, status="In Process", scheduled_start=(AS_OF_DATE - timedelta(days=2)).isoformat(), scheduled_completion=AS_OF_DATE.isoformat(), parent_work_order_id=None, workcenter_id="WC-ASM-1")]
    seed["work_order_operations"] = [
        _row(work_order_id=wo_id, sequence=10, workcenter_id="WC-ASM-1", status="Complete", planned_hours=qty * 0.5, actual_hours=qty * 0.55),
        _row(work_order_id=wo_id, sequence=20, workcenter_id="WC-ASM-1", status="In Process", planned_hours=qty * 0.75, actual_hours=qty * 0.8),
    ]
    steps = [
        _step("search_documents", {"category": "completion_costing"}, control=True),
        _step("get_work_order", {"work_order_id": wo_id}, control=True),
        _step("complete_operation", {"work_order_id": wo_id, "sequence": 20, "actual_hours": round(qty * 0.8, 2)}),
        _step("complete_work_order", {"work_order_id": wo_id, "completed_qty": completed, "scrap_qty": scrap}),
        _step("record_wip_variance", {"variance_id": variance_id, "work_order_id": wo_id, "material_variance": mat_var, "labor_variance": labor_var, "overhead_variance": overhead_var}),
        _step("submit_answer", {"work_order_id": wo_id, "completed_quantity": str(completed), "scrap_quantity": str(scrap), "variance_id": variance_id}),
    ]
    assertions = [
        _assertion("operation_completed", "All work-order operations are complete.", "work_order_operations", {"work_order_id": wo_id, "status": "Complete"}, count=2),
        _assertion("work_order_completed", "Finished and scrap quantities reconcile to the order quantity.", "work_orders", {"work_order_id": wo_id}, {"status": "Completed", "completed_qty": completed, "scrap_qty": scrap}),
        _assertion("variance_posted", "WIP variance is posted for finance review.", "wip_variances", {"variance_id": variance_id}, {"material_variance": mat_var, "labor_variance": labor_var, "overhead_variance": overhead_var, "status": "Posted"}),
    ]
    answer = {"work_order_id": wo_id, "completed_quantity": str(completed), "scrap_quantity": str(scrap), "variance_id": variance_id}
    instruction = f"Close work order {wo_id} after completing its remaining operation. Record {completed} finished units and {scrap} scrap, post the supplied WIP variance amounts from the costing packet, and return the closure summary."
    return _task(number, variant, "completion_costing", f"Complete and cost {wo_id}", "production_cost_accountant", instruction, seed, ["search_documents", "get_work_order"], ["work_order_operations", "work_orders", "wip_variances", "inventory_on_hand"], steps, assertions, answer, "L3")


def _transfer_reschedule(number: int, variant: int) -> dict[str, Any]:
    task_id = f"factorybench-{number:03d}"
    seed = _new_seed(task_id)
    wo_id = f"WO-T-{variant:03d}"
    transfer_id = f"TRF-{variant:04d}"
    lot = f"PDX-C-{variant:03d}"
    qty = 7 + variant
    arrival = AS_OF_DATE + timedelta(days=2)
    new_completion = arrival + timedelta(days=3)
    seed["work_orders"] = [_row(work_order_id=wo_id, task_id=task_id, sales_order_id=None, item_id="FG-PANEL", quantity=qty, completed_qty=0, scrap_qty=0, status="Released", scheduled_start=AS_OF_DATE.isoformat(), scheduled_completion=(AS_OF_DATE + timedelta(days=1)).isoformat(), parent_work_order_id=None, workcenter_id="WC-ASM-1")]
    seed["material_requirements"] = [_row(work_order_id=wo_id, item_id="RM-COPPER", required_qty=qty, reserved_qty=0, issued_qty=0, need_by=AS_OF_DATE.isoformat())]
    seed["inventory_on_hand"] = [
        _row(plant_id="SEA", subinventory="STORES", item_id="RM-COPPER", lot_number=f"SEA-C-{variant:03d}", quantity=1, reserved_qty=1, expiration_date=None, status="Unrestricted"),
        _row(plant_id="PDX", subinventory="STORES", item_id="RM-COPPER", lot_number=lot, quantity=qty + 12, reserved_qty=0, expiration_date=None, status="Unrestricted"),
    ]
    steps = [
        _step("search_documents", {"category": "transfer_reschedule"}, control=True),
        _step("get_work_order", {"work_order_id": wo_id}, control=True),
        _step("get_inventory", {"plant_id": "PDX", "item_ids": ["RM-COPPER"]}, control=True),
        _step("get_schedule", {"plant_id": "SEA", "work_order_id": wo_id}, control=True),
        _step("create_transfer", {"transfer_id": transfer_id, "item_id": "RM-COPPER", "lot_number": lot, "from_plant": "PDX", "from_subinventory": "STORES", "to_plant": "SEA", "to_subinventory": "STORES", "quantity": qty, "transferred_at": AS_OF_DATE.isoformat()}),
        _step("complete_transfer", {"transfer_id": transfer_id, "arrival_date": arrival.isoformat()}),
        _step("reschedule_work_order", {"work_order_id": wo_id, "scheduled_start": arrival.isoformat(), "scheduled_completion": new_completion.isoformat(), "workcenter_id": "WC-ASM-1"}),
        _step("submit_answer", {"transfer_id": transfer_id, "work_order_id": wo_id, "new_start": arrival.isoformat(), "new_completion": new_completion.isoformat()}),
    ]
    assertions = [
        _assertion("transfer_completed", "The donor-plant transfer is completed for the shortage quantity.", "inventory_transfers", {"transfer_id": transfer_id}, {"quantity": qty, "status": "Completed"}),
        _assertion("receiving_inventory_created", "Transferred stock is available at the receiving plant.", "inventory_on_hand", {"plant_id": "SEA", "subinventory": "STORES", "item_id": "RM-COPPER", "lot_number": lot}, {"quantity": qty, "status": "Unrestricted"}),
        _assertion("work_order_rescheduled", "The work order starts on arrival and has a feasible completion date.", "work_orders", {"work_order_id": wo_id}, {"scheduled_start": arrival.isoformat(), "scheduled_completion": new_completion.isoformat()}),
    ]
    answer = {"transfer_id": transfer_id, "work_order_id": wo_id, "new_start": arrival.isoformat(), "new_completion": new_completion.isoformat()}
    instruction = f"Recover the RM-COPPER shortage on work order {wo_id} using unrestricted surplus at PDX. Transfer {qty} units from lot {lot}, then reschedule the SEA work order no earlier than arrival on {arrival.isoformat()}. Return the transfer and revised dates."
    return _task(number, variant, "transfer_reschedule", f"Transfer material and recover {wo_id}", "supply_chain_planner", instruction, seed, ["search_documents", "get_work_order", "get_inventory", "get_schedule"], ["inventory_transfers", "inventory_on_hand", "work_orders"], steps, assertions, answer, "L3")


def _maintenance_recovery(number: int, variant: int) -> dict[str, Any]:
    task_id = f"factorybench-{number:03d}"
    seed = _new_seed(task_id)
    wo_id = f"WO-M-{variant:03d}"
    maintenance_id = f"MWO-{variant:04d}"
    start = AS_OF_DATE + timedelta(days=1)
    completion = start + timedelta(days=2)
    seed["work_orders"] = [_row(work_order_id=wo_id, task_id=task_id, sales_order_id=None, item_id="FG-PANEL", quantity=6 + variant, completed_qty=0, scrap_qty=0, status="Released", scheduled_start=AS_OF_DATE.isoformat(), scheduled_completion=(AS_OF_DATE + timedelta(days=2)).isoformat(), parent_work_order_id=None, workcenter_id="WC-ASM-1")]
    seed["work_order_operations"] = [_row(work_order_id=wo_id, sequence=10, workcenter_id="WC-ASM-1", status="Ready", planned_hours=10 + variant, actual_hours=0)]
    seed["workcenters"][0]["status"] = "Down"
    steps = [
        _step("search_documents", {"category": "maintenance_recovery"}, control=True),
        _step("get_schedule", {"plant_id": "SEA", "work_order_id": wo_id}, control=True),
        _step("get_maintenance_context", {"workcenter_id": "WC-ASM-1"}, control=True),
        _step("create_maintenance_work_order", {"maintenance_id": maintenance_id, "workcenter_id": "WC-ASM-1", "priority": "High", "scheduled_start": AS_OF_DATE.isoformat(), "expected_finish": start.isoformat(), "failure_code": "UNPLANNED_DOWNTIME"}),
        _step("reroute_operation", {"work_order_id": wo_id, "sequence": 10, "workcenter_id": "WC-ASM-2"}),
        _step("reschedule_work_order", {"work_order_id": wo_id, "scheduled_start": start.isoformat(), "scheduled_completion": completion.isoformat(), "workcenter_id": "WC-ASM-2"}),
        _step("submit_answer", {"maintenance_id": maintenance_id, "work_order_id": wo_id, "alternate_workcenter": "WC-ASM-2", "new_completion": completion.isoformat()}),
    ]
    assertions = [
        _assertion("maintenance_opened", "High-priority maintenance is opened for the failed center.", "maintenance_work_orders", {"maintenance_id": maintenance_id}, {"workcenter_id": "WC-ASM-1", "priority": "High", "status": "Open"}),
        _assertion("operation_rerouted", "The operation moves to an active qualified alternate.", "work_order_operations", {"work_order_id": wo_id, "sequence": 10}, {"workcenter_id": "WC-ASM-2"}),
        _assertion("schedule_recovered", "The work-order dates and primary center reflect the recovery plan.", "work_orders", {"work_order_id": wo_id}, {"workcenter_id": "WC-ASM-2", "scheduled_start": start.isoformat(), "scheduled_completion": completion.isoformat()}),
    ]
    answer = {"maintenance_id": maintenance_id, "work_order_id": wo_id, "alternate_workcenter": "WC-ASM-2", "new_completion": completion.isoformat()}
    instruction = f"Assembly Cell 1 failed before work order {wo_id}. Open the required maintenance order, choose a qualified active alternate with capacity, reroute operation 10, and reschedule production. Return the maintenance ID, alternate workcenter, and revised completion."
    return _task(number, variant, "maintenance_recovery", f"Recover production after WC-ASM-1 failure", "maintenance_planner", instruction, seed, ["search_documents", "get_schedule", "get_maintenance_context"], ["maintenance_work_orders", "work_order_operations", "work_orders"], steps, assertions, answer, "L3")


_BUILDERS = (
    _order_release,
    _material_shortage,
    _supplier_selection,
    _inbound_receipt,
    _invoice_match,
    _production_issue,
    _quality_exception,
    _completion_costing,
    _transfer_reschedule,
    _maintenance_recovery,
)


def build_catalog() -> list[dict[str, Any]]:
    """Return all 100 deterministic benchmark tasks."""

    tasks: list[dict[str, Any]] = []
    number = 1
    for builder in _BUILDERS:
        for variant in range(1, 11):
            tasks.append(builder(number, variant))
            number += 1
    return tasks


def get_task(task_id: str) -> dict[str, Any]:
    for task in build_catalog():
        if task["task_id"] == task_id:
            return task
    raise KeyError(f"Unknown task: {task_id}")
