"""SQLite-backed Oracle-shaped manufacturing ERP simulation."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

READ_TOOLS = {
    "search_documents",
    "get_sales_order",
    "get_bom",
    "get_inventory",
    "get_work_order",
    "get_requisition",
    "get_supplier_quotes",
    "get_purchase_order",
    "get_receipt",
    "get_invoice_match",
    "get_quality_context",
    "get_schedule",
    "get_maintenance_context",
}

WRITE_TOOLS = {
    "create_work_order",
    "reserve_material",
    "create_requisition",
    "approve_requisition",
    "create_purchase_order",
    "approve_purchase_order",
    "receive_purchase_order",
    "record_inspection",
    "approve_invoice",
    "hold_invoice",
    "issue_material",
    "start_operation",
    "place_quality_hold",
    "create_nonconformance",
    "complete_operation",
    "complete_work_order",
    "record_wip_variance",
    "create_transfer",
    "complete_transfer",
    "reschedule_work_order",
    "create_maintenance_work_order",
    "reroute_operation",
    "submit_answer",
}

TOOL_CONTRACTS = {
    "oracle_erp": {
        "description": "Query and mutate the synthetic manufacturing ERP.",
        "tools": sorted((READ_TOOLS | WRITE_TOOLS) - {"search_documents", "submit_answer"}),
    },
    "plant_docs": {
        "description": "Search versioned operating policies and task assets.",
        "tools": ["search_documents"],
    },
    "factory_harness": {
        "description": "Submit exact answer fields for deterministic verification.",
        "tools": ["submit_answer"],
    },
}

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _canonical_argument(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _canonical_argument(item)) for key, item in value.items()))
    if isinstance(value, list):
        normalized = [_canonical_argument(item) for item in value]
        return tuple(sorted(normalized, key=repr))
    return value


def missing_required_read_calls(
    task: dict[str, Any],
    trace: list[dict[str, Any]],
    *,
    before_index: int | None = None,
) -> list[dict[str, Any]]:
    """Return task-bound read calls absent from the successful trace prefix."""

    requirements = task.get("required_read_calls")
    if requirements is None:
        requirements = [{"tool": tool} for tool in task.get("required_reads", [])]
    successful = [
        entry
        for entry in trace
        if entry.get("success") and (before_index is None or entry["index"] < before_index)
    ]
    missing = []
    for requirement in requirements:
        expected_arguments = requirement.get("arguments")
        matched = any(
            entry["tool"] == requirement["tool"]
            and (
                expected_arguments is None
                or _canonical_argument(entry.get("arguments", {}))
                == _canonical_argument(expected_arguments)
            )
            for entry in successful
        )
        if not matched:
            missing.append(requirement)
    return missing


def normalize_answer_fields(task: dict[str, Any], fields: dict[str, Any]) -> dict[str, str]:
    """Validate task-specific answer fields and return canonical text values."""

    schema = task["answer_schema"]
    properties = schema["properties"]
    expected_fields = set(properties)
    submitted_fields = set(fields)
    if submitted_fields != expected_fields:
        missing = sorted(expected_fields - submitted_fields)
        unexpected = sorted(submitted_fields - expected_fields)
        raise ValueError(f"answer fields do not match schema; missing={missing}, unexpected={unexpected}")

    normalized: dict[str, str] = {}
    for field, field_schema in properties.items():
        value = fields[field]
        answer_type = field_schema["type"]
        if answer_type == "string":
            if not isinstance(value, str):
                raise ValueError(f"answer field {field} must be a string")
            normalized[field] = value
            continue
        if isinstance(value, bool):
            raise ValueError(f"answer field {field} must be numeric")
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"answer field {field} must be numeric") from exc
        if not decimal_value.is_finite():
            raise ValueError(f"answer field {field} must be finite")
        if answer_type == "integer":
            if decimal_value != decimal_value.to_integral_value():
                raise ValueError(f"answer field {field} must be an integer")
            normalized[field] = str(int(decimal_value))
            continue
        if answer_type == "number":
            quantum = Decimal(str(field_schema.get("multipleOf", 0.01)))
            quantized = decimal_value.quantize(quantum)
            if quantized != decimal_value:
                raise ValueError(f"answer field {field} exceeds the allowed precision")
            places = max(0, -quantum.as_tuple().exponent)
            normalized[field] = f"{quantized:.{places}f}"
            continue
        raise ValueError(f"unsupported answer type for {field}: {answer_type}")
    return normalized


def seed_database(task: dict[str, Any], path: str | Path) -> Path:
    """Create a fresh deterministic SQLite world for one task."""

    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if database_path.exists():
        database_path.unlink()
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.execute("PRAGMA foreign_keys = OFF")
        for table, rows in task["seed_tables"].items():
            for row in rows:
                columns = list(row)
                placeholders = ", ".join("?" for _ in columns)
                names = ", ".join(columns)
                connection.execute(
                    f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
                    [row[column] for column in columns],
                )
        connection.commit()
        connection.execute("PRAGMA foreign_keys = ON")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ValueError(f"seed data violates foreign keys: {violations}")
    finally:
        connection.close()
    return database_path


class FactoryWorld:
    """An isolated task world with auditable tool calls and transactional writes."""

    def __init__(self, task: dict[str, Any], database_path: str | Path):
        self.task = task
        self.database_path = Path(database_path)
        self.connection = sqlite3.connect(self.database_path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.row_factory = sqlite3.Row
        self.trace: list[dict[str, Any]] = []

    @classmethod
    def fresh(cls, task: dict[str, Any], database_path: str | Path) -> "FactoryWorld":
        seed_database(task, database_path)
        return cls(task, database_path)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "FactoryWorld":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def call_tool(self, tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        arguments = arguments or {}
        if tool not in READ_TOOLS | WRITE_TOOLS:
            result = {"error": f"unknown tool: {tool}"}
            self.trace.append({"index": len(self.trace), "tool": tool, "arguments": arguments, "success": False, "result": result})
            return result
        try:
            if tool in WRITE_TOOLS:
                self._require_preflight()
            handler = getattr(self, f"_tool_{tool}")
            result = handler(**arguments)
            self.connection.commit()
            success = True
        except (KeyError, TypeError, ValueError, sqlite3.Error) as exc:
            self.connection.rollback()
            result = {"error": str(exc)}
            success = False
        self.trace.append(
            {
                "index": len(self.trace),
                "tool": tool,
                "arguments": arguments,
                "success": success,
                "result": result,
            }
        )
        return result

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        tables = [
            row["name"]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        snapshot: dict[str, list[dict[str, Any]]] = {}
        for table in tables:
            order = ", ".join(row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})"))
            rows = self.connection.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
            snapshot[table] = [dict(row) for row in rows]
        return snapshot

    def _successful_tools(self) -> set[str]:
        return {entry["tool"] for entry in self.trace if entry["success"]}

    def _require_preflight(self) -> None:
        missing = missing_required_read_calls(self.task, self.trace)
        if missing:
            rendered = ", ".join(
                f"{requirement['tool']}({json.dumps(requirement.get('arguments', {}), sort_keys=True)})"
                for requirement in missing
            )
            raise ValueError(f"read-before-write control failed; missing: {rendered}")

    def _one(self, query: str, params: Iterable[Any] = ()) -> dict[str, Any]:
        row = self.connection.execute(query, tuple(params)).fetchone()
        if row is None:
            raise ValueError("record not found")
        return dict(row)

    def _all(self, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(query, tuple(params)).fetchall()]

    def _audit(self, tool: str, table: str, record_id: str, action: str, payload: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO audit_log (task_id, tool, table_name, record_id, action, payload) VALUES (?, ?, ?, ?, ?, ?)",
            (self.task["task_id"], tool, table, record_id, action, json.dumps(payload, sort_keys=True)),
        )

    def _tool_search_documents(self, category: str) -> dict[str, Any]:
        rows = self._all(
            "SELECT doc_id, title, category, body, sha256 FROM documents WHERE task_id = ? AND category = ? ORDER BY doc_id",
            (self.task["task_id"], category),
        )
        if not rows:
            raise ValueError(f"no documents found for category {category}")
        return {"documents": rows}

    def _tool_get_sales_order(self, sales_order_id: str) -> dict[str, Any]:
        header = self._one("SELECT * FROM sales_orders WHERE sales_order_id = ?", (sales_order_id,))
        lines = self._all("SELECT * FROM sales_order_lines WHERE sales_order_id = ? ORDER BY line_no", (sales_order_id,))
        return {"header": header, "lines": lines}

    def _tool_get_bom(self, item_id: str, as_of: str) -> dict[str, Any]:
        header = self._one(
            "SELECT * FROM bom_headers WHERE assembly_item_id = ? AND status = 'Active' AND effective_on <= ? ORDER BY effective_on DESC LIMIT 1",
            (item_id, as_of),
        )
        components = self._all("SELECT * FROM bom_components WHERE bom_id = ? ORDER BY operation_sequence, component_item_id", (header["bom_id"],))
        return {"header": header, "components": components}

    def _tool_get_inventory(self, plant_id: str, item_ids: list[str]) -> dict[str, Any]:
        if not item_ids:
            raise ValueError("item_ids must not be empty")
        placeholders = ", ".join("?" for _ in item_ids)
        rows = self._all(
            f"SELECT *, quantity - reserved_qty AS available_qty FROM inventory_on_hand WHERE plant_id = ? AND item_id IN ({placeholders}) ORDER BY item_id, expiration_date, lot_number",
            (plant_id, *item_ids),
        )
        return {"lots": rows}

    def _tool_get_work_order(self, work_order_id: str) -> dict[str, Any]:
        header = self._one("SELECT * FROM work_orders WHERE work_order_id = ?", (work_order_id,))
        operations = self._all("SELECT * FROM work_order_operations WHERE work_order_id = ? ORDER BY sequence", (work_order_id,))
        requirements = self._all("SELECT * FROM material_requirements WHERE work_order_id = ? ORDER BY item_id", (work_order_id,))
        reservations = self._all("SELECT * FROM material_reservations WHERE work_order_id = ? ORDER BY reservation_id", (work_order_id,))
        return {"header": header, "operations": operations, "requirements": requirements, "reservations": reservations}

    def _tool_get_requisition(self, requisition_id: str) -> dict[str, Any]:
        header = self._one("SELECT * FROM purchase_requisitions WHERE requisition_id = ?", (requisition_id,))
        lines = self._all("SELECT * FROM requisition_lines WHERE requisition_id = ? ORDER BY line_no", (requisition_id,))
        return {"header": header, "lines": lines}

    def _tool_get_supplier_quotes(self, task_id: str, item_id: str, need_by: str) -> dict[str, Any]:
        rows = self._all(
            "SELECT q.*, s.name, s.approved, s.quality_score, s.on_time_rate FROM supplier_quotes q JOIN suppliers s ON s.supplier_id = q.supplier_id WHERE q.task_id = ? AND q.item_id = ? AND q.valid_until >= ? ORDER BY q.unit_price, s.quality_score DESC, s.on_time_rate DESC",
            (task_id, item_id, need_by),
        )
        return {"quotes": rows}

    def _tool_get_purchase_order(self, purchase_order_id: str) -> dict[str, Any]:
        header = self._one("SELECT * FROM purchase_orders WHERE purchase_order_id = ?", (purchase_order_id,))
        lines = self._all("SELECT * FROM purchase_order_lines WHERE purchase_order_id = ? ORDER BY line_no", (purchase_order_id,))
        return {"header": header, "lines": lines}

    def _tool_get_receipt(self, receipt_id: str) -> dict[str, Any]:
        header = self._one("SELECT * FROM receipts WHERE receipt_id = ?", (receipt_id,))
        lines = self._all("SELECT * FROM receipt_lines WHERE receipt_id = ? ORDER BY line_no", (receipt_id,))
        return {"header": header, "lines": lines}

    def _tool_get_invoice_match(self, invoice_id: str) -> dict[str, Any]:
        invoice = self._one("SELECT * FROM ap_invoices WHERE invoice_id = ?", (invoice_id,))
        po = self._one("SELECT * FROM purchase_orders WHERE purchase_order_id = ?", (invoice["purchase_order_id"],))
        received = self._one(
            "SELECT COALESCE(SUM(accepted_qty), 0) AS accepted_qty FROM receipt_lines WHERE receipt_id = ?",
            (invoice["receipt_id"],),
        )
        ordered = self._one(
            "SELECT COALESCE(SUM(ordered_qty), 0) AS ordered_qty FROM purchase_order_lines WHERE purchase_order_id = ?",
            (invoice["purchase_order_id"],),
        )
        variance = (invoice["invoice_amount"] - po["total_amount"]) / po["total_amount"] * 100
        return {"invoice": invoice, "po": po, "ordered_qty": ordered["ordered_qty"], "accepted_qty": received["accepted_qty"], "variance_percent": round(variance, 4)}

    def _tool_get_quality_context(self, inspection_id: str) -> dict[str, Any]:
        inspection = self._one("SELECT * FROM quality_inspections WHERE inspection_id = ?", (inspection_id,))
        inventory = self._all("SELECT * FROM inventory_on_hand WHERE item_id = ? AND lot_number = ?", (inspection["item_id"], inspection["lot_number"]))
        return {"inspection": inspection, "inventory": inventory}

    def _tool_get_schedule(self, plant_id: str, work_order_id: str) -> dict[str, Any]:
        work_order = self._one("SELECT * FROM work_orders WHERE work_order_id = ?", (work_order_id,))
        centers = self._all("SELECT * FROM workcenters WHERE plant_id = ? ORDER BY workcenter_id", (plant_id,))
        operations = self._all("SELECT * FROM work_order_operations WHERE work_order_id = ? ORDER BY sequence", (work_order_id,))
        return {"work_order": work_order, "operations": operations, "workcenters": centers}

    def _tool_get_maintenance_context(self, workcenter_id: str) -> dict[str, Any]:
        center = self._one("SELECT * FROM workcenters WHERE workcenter_id = ?", (workcenter_id,))
        alternates = self._all(
            "SELECT * FROM workcenters WHERE plant_id = ? AND workcenter_id != ? AND status = 'Active' AND qualified_item_class = ? ORDER BY capacity_hours DESC",
            (center["plant_id"], workcenter_id, center["qualified_item_class"]),
        )
        return {"failed_workcenter": center, "qualified_alternates": alternates}

    def _tool_create_work_order(
        self,
        work_order_id: str,
        sales_order_id: str,
        item_id: str,
        quantity: float,
        scheduled_start: str,
        scheduled_completion: str,
        workcenter_id: str,
    ) -> dict[str, Any]:
        order = self._one("SELECT * FROM sales_orders WHERE sales_order_id = ?", (sales_order_id,))
        if order["credit_hold"] or order["status"] != "Booked":
            raise ValueError("sales order is not eligible for release")
        bom = self._one("SELECT * FROM bom_headers WHERE assembly_item_id = ? AND status = 'Active' ORDER BY effective_on DESC LIMIT 1", (item_id,))
        center = self._one("SELECT * FROM workcenters WHERE workcenter_id = ?", (workcenter_id,))
        if center["status"] != "Active":
            raise ValueError("workcenter is not active")
        payload = {
            "work_order_id": work_order_id,
            "task_id": self.task["task_id"],
            "sales_order_id": sales_order_id,
            "item_id": item_id,
            "quantity": quantity,
            "completed_qty": 0,
            "scrap_qty": 0,
            "status": "Released",
            "scheduled_start": scheduled_start,
            "scheduled_completion": scheduled_completion,
            "parent_work_order_id": None,
            "workcenter_id": workcenter_id,
        }
        self.connection.execute(
            "INSERT INTO work_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(payload.values()),
        )
        self._audit("create_work_order", "work_orders", work_order_id, "insert", payload)
        operation = {"work_order_id": work_order_id, "sequence": 10, "workcenter_id": workcenter_id, "status": "Ready", "planned_hours": round(quantity * 1.25, 2), "actual_hours": 0}
        self.connection.execute("INSERT INTO work_order_operations VALUES (?, ?, ?, ?, ?, ?)", tuple(operation.values()))
        self._audit("create_work_order", "work_order_operations", f"{work_order_id}:10", "insert", operation)
        components = self._all("SELECT * FROM bom_components WHERE bom_id = ?", (bom["bom_id"],))
        for component in components:
            required = round(quantity * component["quantity_per"] / component["yield_factor"], 6)
            requirement = {"work_order_id": work_order_id, "item_id": component["component_item_id"], "required_qty": required, "reserved_qty": 0, "issued_qty": 0, "need_by": scheduled_start}
            self.connection.execute("INSERT INTO material_requirements VALUES (?, ?, ?, ?, ?, ?)", tuple(requirement.values()))
            self._audit("create_work_order", "material_requirements", f"{work_order_id}:{component['component_item_id']}", "insert", requirement)
        return {"work_order_id": work_order_id, "status": "Released", "requirements_created": len(components)}

    def _tool_reserve_material(self, reservation_id: str, work_order_id: str, item_id: str, plant_id: str, subinventory: str, lot_number: str, quantity: float) -> dict[str, Any]:
        requirement = self._one("SELECT * FROM material_requirements WHERE work_order_id = ? AND item_id = ?", (work_order_id, item_id))
        remaining = requirement["required_qty"] - requirement["reserved_qty"]
        if abs(quantity - remaining) > 1e-6:
            raise ValueError(f"reservation must equal remaining requirement {remaining}")
        lot = self._one("SELECT * FROM inventory_on_hand WHERE plant_id = ? AND subinventory = ? AND item_id = ? AND lot_number = ?", (plant_id, subinventory, item_id, lot_number))
        if lot["status"] != "Unrestricted" or lot["quantity"] - lot["reserved_qty"] < quantity:
            raise ValueError("insufficient eligible on-hand quantity")
        payload = {"reservation_id": reservation_id, "task_id": self.task["task_id"], "work_order_id": work_order_id, "item_id": item_id, "plant_id": plant_id, "subinventory": subinventory, "lot_number": lot_number, "quantity": quantity, "status": "Active"}
        self.connection.execute("INSERT INTO material_reservations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(payload.values()))
        self.connection.execute("UPDATE inventory_on_hand SET reserved_qty = reserved_qty + ? WHERE plant_id = ? AND subinventory = ? AND item_id = ? AND lot_number = ?", (quantity, plant_id, subinventory, item_id, lot_number))
        self.connection.execute("UPDATE material_requirements SET reserved_qty = reserved_qty + ? WHERE work_order_id = ? AND item_id = ?", (quantity, work_order_id, item_id))
        self._audit("reserve_material", "material_reservations", reservation_id, "insert", payload)
        self._audit("reserve_material", "inventory_on_hand", f"{plant_id}:{subinventory}:{item_id}:{lot_number}", "update", {"reserved_delta": quantity})
        self._audit("reserve_material", "material_requirements", f"{work_order_id}:{item_id}", "update", {"reserved_delta": quantity})
        return {"reservation_id": reservation_id, "status": "Active"}

    def _tool_create_requisition(self, requisition_id: str, requester_id: str, work_order_id: str, supplier_id: str, item_id: str, quantity: float, unit_price: float, need_by: str) -> dict[str, Any]:
        supplier = self._one("SELECT * FROM suppliers WHERE supplier_id = ?", (supplier_id,))
        if not supplier["approved"]:
            raise ValueError("supplier is not approved")
        total = round(quantity * unit_price, 2)
        payload = {"requisition_id": requisition_id, "task_id": self.task["task_id"], "requester_id": requester_id, "work_order_id": work_order_id, "status": "Pending Approval", "supplier_id": supplier_id, "total_amount": total, "need_by": need_by, "approved_by": None}
        self.connection.execute("INSERT INTO purchase_requisitions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(payload.values()))
        line = {"requisition_id": requisition_id, "line_no": 1, "item_id": item_id, "quantity": quantity, "unit_price": unit_price}
        self.connection.execute("INSERT INTO requisition_lines VALUES (?, ?, ?, ?, ?)", tuple(line.values()))
        self._audit("create_requisition", "purchase_requisitions", requisition_id, "insert", payload)
        self._audit("create_requisition", "requisition_lines", f"{requisition_id}:1", "insert", line)
        return {"requisition_id": requisition_id, "status": "Pending Approval", "total_amount": total}

    def _tool_approve_requisition(self, requisition_id: str, approver_id: str) -> dict[str, Any]:
        requisition = self._one("SELECT * FROM purchase_requisitions WHERE requisition_id = ?", (requisition_id,))
        approver = self._one("SELECT * FROM users WHERE user_id = ?", (approver_id,))
        if approver["approval_limit"] < requisition["total_amount"]:
            raise ValueError("approver limit is insufficient")
        self.connection.execute("UPDATE purchase_requisitions SET status = 'Approved', approved_by = ? WHERE requisition_id = ?", (approver_id, requisition_id))
        self._audit("approve_requisition", "purchase_requisitions", requisition_id, "update", {"status": "Approved", "approved_by": approver_id})
        return {"requisition_id": requisition_id, "status": "Approved"}

    def _tool_create_purchase_order(self, purchase_order_id: str, requisition_id: str, supplier_id: str, buyer_id: str, item_id: str, quantity: float, unit_price: float, promised_date: str) -> dict[str, Any]:
        requisition = self._one("SELECT * FROM purchase_requisitions WHERE requisition_id = ?", (requisition_id,))
        line = self._one("SELECT * FROM requisition_lines WHERE requisition_id = ? AND item_id = ?", (requisition_id, item_id))
        supplier = self._one("SELECT * FROM suppliers WHERE supplier_id = ?", (supplier_id,))
        if requisition["status"] != "Approved" or not supplier["approved"]:
            raise ValueError("requisition or supplier is not eligible")
        quote = self._one("SELECT * FROM supplier_quotes WHERE task_id = ? AND supplier_id = ? AND item_id = ?", (self.task["task_id"], supplier_id, item_id))
        if abs(float(quote["unit_price"]) - unit_price) > 1e-6:
            raise ValueError("selected price does not match a current task quote")
        if abs(float(line["quantity"]) - quantity) > 1e-6 or quantity < quote["minimum_qty"]:
            raise ValueError("purchase order quantity must match the requisition and quote minimum")
        need_by = date.fromisoformat(requisition["need_by"])
        if date.fromisoformat(quote["valid_until"]) < need_by:
            raise ValueError("selected quote is not valid through the requisition need-by date")
        promised = date.fromisoformat(promised_date)
        earliest_delivery = date.fromisoformat(self.task["as_of"]) + timedelta(days=int(quote["lead_days"]))
        if promised < earliest_delivery or promised > need_by:
            raise ValueError("promised date does not satisfy quoted lead time and requisition need-by")
        total = round(quantity * unit_price, 2)
        payload = {"purchase_order_id": purchase_order_id, "task_id": self.task["task_id"], "requisition_id": requisition_id, "supplier_id": supplier_id, "buyer_id": buyer_id, "status": "Pending Approval", "total_amount": total, "promised_date": promised_date, "approved_by": None}
        self.connection.execute("INSERT INTO purchase_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(payload.values()))
        line = {"purchase_order_id": purchase_order_id, "line_no": 1, "item_id": item_id, "ordered_qty": quantity, "received_qty": 0, "unit_price": unit_price}
        self.connection.execute("INSERT INTO purchase_order_lines VALUES (?, ?, ?, ?, ?, ?)", tuple(line.values()))
        self._audit("create_purchase_order", "purchase_orders", purchase_order_id, "insert", payload)
        self._audit("create_purchase_order", "purchase_order_lines", f"{purchase_order_id}:1", "insert", line)
        return {"purchase_order_id": purchase_order_id, "status": "Pending Approval", "total_amount": total}

    def _tool_approve_purchase_order(self, purchase_order_id: str, approver_id: str) -> dict[str, Any]:
        order = self._one("SELECT * FROM purchase_orders WHERE purchase_order_id = ?", (purchase_order_id,))
        approver = self._one("SELECT * FROM users WHERE user_id = ?", (approver_id,))
        if approver["approval_limit"] < order["total_amount"]:
            raise ValueError("approver limit is insufficient")
        self.connection.execute("UPDATE purchase_orders SET status = 'Approved', approved_by = ? WHERE purchase_order_id = ?", (approver_id, purchase_order_id))
        self._audit("approve_purchase_order", "purchase_orders", purchase_order_id, "update", {"status": "Approved", "approved_by": approver_id})
        return {"purchase_order_id": purchase_order_id, "status": "Approved"}

    def _tool_receive_purchase_order(self, receipt_id: str, purchase_order_id: str, receiver_id: str, item_id: str, quantity: float, lot_number: str, received_at: str) -> dict[str, Any]:
        order = self._one("SELECT * FROM purchase_orders WHERE purchase_order_id = ?", (purchase_order_id,))
        line = self._one("SELECT * FROM purchase_order_lines WHERE purchase_order_id = ? AND item_id = ?", (purchase_order_id, item_id))
        if order["status"] != "Approved" or line["received_qty"] + quantity > line["ordered_qty"]:
            raise ValueError("receipt exceeds an eligible approved PO quantity")
        receipt = {"receipt_id": receipt_id, "task_id": self.task["task_id"], "purchase_order_id": purchase_order_id, "status": "Pending Inspection", "received_at": received_at, "receiver_id": receiver_id}
        self.connection.execute("INSERT INTO receipts VALUES (?, ?, ?, ?, ?, ?)", tuple(receipt.values()))
        receipt_line = {"receipt_id": receipt_id, "line_no": 1, "item_id": item_id, "quantity": quantity, "accepted_qty": 0, "rejected_qty": 0, "lot_number": lot_number}
        self.connection.execute("INSERT INTO receipt_lines VALUES (?, ?, ?, ?, ?, ?, ?)", tuple(receipt_line.values()))
        self.connection.execute("UPDATE purchase_order_lines SET received_qty = received_qty + ? WHERE purchase_order_id = ? AND item_id = ?", (quantity, purchase_order_id, item_id))
        self.connection.execute("INSERT INTO inventory_on_hand VALUES ('SEA', 'RECEIVING', ?, ?, ?, 0, NULL, 'Inspection')", (item_id, lot_number, quantity))
        self._audit("receive_purchase_order", "receipts", receipt_id, "insert", receipt)
        self._audit("receive_purchase_order", "receipt_lines", f"{receipt_id}:1", "insert", receipt_line)
        self._audit("receive_purchase_order", "purchase_order_lines", f"{purchase_order_id}:1", "update", {"received_delta": quantity})
        self._audit("receive_purchase_order", "inventory_on_hand", f"SEA:RECEIVING:{item_id}:{lot_number}", "insert", {"quantity": quantity, "status": "Inspection"})
        return {"receipt_id": receipt_id, "status": "Pending Inspection"}

    def _tool_record_inspection(self, inspection_id: str, source_type: str, source_id: str, item_id: str, lot_number: str, inspected_qty: float, accepted_qty: float, rejected_qty: float, result: str, inspector_id: str) -> dict[str, Any]:
        if abs(accepted_qty + rejected_qty - inspected_qty) > 1e-6:
            raise ValueError("inspection quantities do not reconcile")
        receipt = self._one("SELECT * FROM receipts WHERE receipt_id = ?", (source_id,))
        line = self._one("SELECT * FROM receipt_lines WHERE receipt_id = ? AND item_id = ?", (source_id, item_id))
        if line["quantity"] != inspected_qty or receipt["status"] != "Pending Inspection":
            raise ValueError("inspection does not match the pending receipt")
        payload = {"inspection_id": inspection_id, "task_id": self.task["task_id"], "source_type": source_type, "source_id": source_id, "item_id": item_id, "lot_number": lot_number, "inspected_qty": inspected_qty, "accepted_qty": accepted_qty, "rejected_qty": rejected_qty, "result": result, "inspector_id": inspector_id}
        self.connection.execute("INSERT INTO quality_inspections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(payload.values()))
        self.connection.execute("UPDATE receipt_lines SET accepted_qty = ?, rejected_qty = ? WHERE receipt_id = ? AND item_id = ?", (accepted_qty, rejected_qty, source_id, item_id))
        self.connection.execute("UPDATE receipts SET status = 'Inspected' WHERE receipt_id = ?", (source_id,))
        self.connection.execute("DELETE FROM inventory_on_hand WHERE plant_id = 'SEA' AND subinventory = 'RECEIVING' AND item_id = ? AND lot_number = ?", (item_id, lot_number))
        if accepted_qty:
            self.connection.execute("INSERT INTO inventory_on_hand VALUES ('SEA', 'STORES', ?, ?, ?, 0, NULL, 'Unrestricted')", (item_id, lot_number, accepted_qty))
        if rejected_qty:
            self.connection.execute("INSERT INTO inventory_on_hand VALUES ('SEA', 'QUARANTINE', ?, ?, ?, 0, NULL, 'Quality Hold')", (item_id, lot_number, rejected_qty))
        self._audit("record_inspection", "quality_inspections", inspection_id, "insert", payload)
        self._audit("record_inspection", "receipt_lines", f"{source_id}:1", "update", {"accepted_qty": accepted_qty, "rejected_qty": rejected_qty})
        self._audit("record_inspection", "receipts", source_id, "update", {"status": "Inspected"})
        self._audit("record_inspection", "inventory_on_hand", f"SEA:{item_id}:{lot_number}", "move", {"accepted_qty": accepted_qty, "rejected_qty": rejected_qty})
        return {"inspection_id": inspection_id, "result": result, "released_quantity": accepted_qty}

    def _invoice_eligible(self, invoice_id: str) -> tuple[dict[str, Any], float, bool]:
        match = self._tool_get_invoice_match(invoice_id)
        variance = abs(match["variance_percent"])
        quantity_ok = match["accepted_qty"] >= match["ordered_qty"]
        return match["invoice"], variance, quantity_ok

    def _tool_approve_invoice(self, invoice_id: str) -> dict[str, Any]:
        _, variance, quantity_ok = self._invoice_eligible(invoice_id)
        if variance > 2.0 or not quantity_ok:
            raise ValueError("invoice exceeds three-way-match tolerance")
        self.connection.execute("UPDATE ap_invoices SET status = 'Approved', hold_reason = NULL WHERE invoice_id = ?", (invoice_id,))
        self._audit("approve_invoice", "ap_invoices", invoice_id, "update", {"status": "Approved", "hold_reason": None})
        return {"invoice_id": invoice_id, "status": "Approved"}

    def _tool_hold_invoice(self, invoice_id: str, reason: str) -> dict[str, Any]:
        _, variance, quantity_ok = self._invoice_eligible(invoice_id)
        if variance <= 2.0 and quantity_ok:
            raise ValueError("invoice is within tolerance and should not be held")
        self.connection.execute("UPDATE ap_invoices SET status = 'Hold', hold_reason = ? WHERE invoice_id = ?", (reason, invoice_id))
        self._audit("hold_invoice", "ap_invoices", invoice_id, "update", {"status": "Hold", "hold_reason": reason})
        return {"invoice_id": invoice_id, "status": "Hold", "hold_reason": reason}

    def _tool_issue_material(self, transaction_id: str, work_order_id: str, item_id: str, plant_id: str, subinventory: str, lot_number: str, quantity: float, occurred_at: str) -> dict[str, Any]:
        reservation = self._one("SELECT * FROM material_reservations WHERE work_order_id = ? AND item_id = ? AND lot_number = ? AND status = 'Active'", (work_order_id, item_id, lot_number))
        lot = self._one("SELECT * FROM inventory_on_hand WHERE plant_id = ? AND subinventory = ? AND item_id = ? AND lot_number = ?", (plant_id, subinventory, item_id, lot_number))
        earliest = self._one("SELECT lot_number FROM inventory_on_hand WHERE plant_id = ? AND subinventory = ? AND item_id = ? AND status = 'Unrestricted' AND reserved_qty > 0 ORDER BY expiration_date, lot_number LIMIT 1", (plant_id, subinventory, item_id))
        if earliest["lot_number"] != lot_number or reservation["quantity"] != quantity or lot["reserved_qty"] < quantity:
            raise ValueError("issue violates reservation or FEFO control")
        payload = {"transaction_id": transaction_id, "task_id": self.task["task_id"], "transaction_type": "WIP_ISSUE", "work_order_id": work_order_id, "item_id": item_id, "plant_id": plant_id, "subinventory": subinventory, "lot_number": lot_number, "quantity": quantity, "occurred_at": occurred_at, "reference": reservation["reservation_id"]}
        self.connection.execute("INSERT INTO material_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(payload.values()))
        self.connection.execute("UPDATE inventory_on_hand SET quantity = quantity - ?, reserved_qty = reserved_qty - ? WHERE plant_id = ? AND subinventory = ? AND item_id = ? AND lot_number = ?", (quantity, quantity, plant_id, subinventory, item_id, lot_number))
        self.connection.execute("UPDATE material_reservations SET status = 'Consumed' WHERE reservation_id = ?", (reservation["reservation_id"],))
        self.connection.execute("UPDATE material_requirements SET issued_qty = issued_qty + ? WHERE work_order_id = ? AND item_id = ?", (quantity, work_order_id, item_id))
        self._audit("issue_material", "material_transactions", transaction_id, "insert", payload)
        self._audit("issue_material", "inventory_on_hand", f"{plant_id}:{subinventory}:{item_id}:{lot_number}", "update", {"quantity_delta": -quantity, "reserved_delta": -quantity})
        self._audit("issue_material", "material_reservations", reservation["reservation_id"], "update", {"status": "Consumed"})
        self._audit("issue_material", "material_requirements", f"{work_order_id}:{item_id}", "update", {"issued_delta": quantity})
        return {"transaction_id": transaction_id, "lot_number": lot_number, "quantity": quantity}

    def _tool_start_operation(self, work_order_id: str, sequence: int) -> dict[str, Any]:
        remaining = self._one("SELECT COUNT(*) AS count FROM material_requirements WHERE work_order_id = ? AND issued_qty < required_qty", (work_order_id,))
        if remaining["count"]:
            raise ValueError("materials are not fully issued")
        self.connection.execute("UPDATE work_order_operations SET status = 'In Process' WHERE work_order_id = ? AND sequence = ?", (work_order_id, sequence))
        self.connection.execute("UPDATE work_orders SET status = 'In Process' WHERE work_order_id = ?", (work_order_id,))
        self._audit("start_operation", "work_order_operations", f"{work_order_id}:{sequence}", "update", {"status": "In Process"})
        self._audit("start_operation", "work_orders", work_order_id, "update", {"status": "In Process"})
        return {"work_order_id": work_order_id, "sequence": sequence, "status": "In Process"}

    def _tool_place_quality_hold(self, hold_id: str, inspection_id: str, item_id: str, lot_number: str, reason_code: str) -> dict[str, Any]:
        inspection = self._one("SELECT * FROM quality_inspections WHERE inspection_id = ?", (inspection_id,))
        if inspection["result"] != "Fail" or inspection["lot_number"] != lot_number:
            raise ValueError("inspection does not support a quality hold")
        payload = {"hold_id": hold_id, "task_id": self.task["task_id"], "item_id": item_id, "lot_number": lot_number, "reason_code": reason_code, "status": "Active", "source_id": inspection_id}
        self.connection.execute("INSERT INTO quality_holds VALUES (?, ?, ?, ?, ?, ?, ?)", tuple(payload.values()))
        self.connection.execute("UPDATE inventory_on_hand SET status = 'Quality Hold' WHERE item_id = ? AND lot_number = ?", (item_id, lot_number))
        self._audit("place_quality_hold", "quality_holds", hold_id, "insert", payload)
        self._audit("place_quality_hold", "inventory_on_hand", f"{item_id}:{lot_number}", "update", {"status": "Quality Hold"})
        return {"hold_id": hold_id, "status": "Active"}

    def _tool_create_nonconformance(self, nonconformance_id: str, inspection_id: str, disposition: str, owner_id: str) -> dict[str, Any]:
        inspection = self._one("SELECT * FROM quality_inspections WHERE inspection_id = ?", (inspection_id,))
        if inspection["result"] != "Fail" or disposition not in {"REWORK", "SCRAP", "RETURN"}:
            raise ValueError("invalid nonconformance disposition")
        payload = {"nonconformance_id": nonconformance_id, "task_id": self.task["task_id"], "inspection_id": inspection_id, "disposition": disposition, "status": "Open", "owner_id": owner_id}
        self.connection.execute("INSERT INTO nonconformances VALUES (?, ?, ?, ?, ?, ?)", tuple(payload.values()))
        self._audit("create_nonconformance", "nonconformances", nonconformance_id, "insert", payload)
        return {"nonconformance_id": nonconformance_id, "status": "Open", "disposition": disposition}

    def _tool_complete_operation(self, work_order_id: str, sequence: int, actual_hours: float) -> dict[str, Any]:
        operation = self._one("SELECT * FROM work_order_operations WHERE work_order_id = ? AND sequence = ?", (work_order_id, sequence))
        if operation["status"] not in {"Ready", "In Process"}:
            raise ValueError("operation cannot be completed from its current status")
        self.connection.execute("UPDATE work_order_operations SET status = 'Complete', actual_hours = ? WHERE work_order_id = ? AND sequence = ?", (actual_hours, work_order_id, sequence))
        self._audit("complete_operation", "work_order_operations", f"{work_order_id}:{sequence}", "update", {"status": "Complete", "actual_hours": actual_hours})
        return {"work_order_id": work_order_id, "sequence": sequence, "status": "Complete"}

    def _tool_complete_work_order(self, work_order_id: str, completed_qty: float, scrap_qty: float) -> dict[str, Any]:
        order = self._one("SELECT * FROM work_orders WHERE work_order_id = ?", (work_order_id,))
        open_operations = self._one("SELECT COUNT(*) AS count FROM work_order_operations WHERE work_order_id = ? AND status != 'Complete'", (work_order_id,))
        if open_operations["count"] or abs(completed_qty + scrap_qty - order["quantity"]) > 1e-6:
            raise ValueError("operations or completion quantities do not reconcile")
        self.connection.execute("UPDATE work_orders SET status = 'Completed', completed_qty = ?, scrap_qty = ? WHERE work_order_id = ?", (completed_qty, scrap_qty, work_order_id))
        lot_number = f"COMP-{work_order_id}"
        self.connection.execute("INSERT INTO inventory_on_hand VALUES ('SEA', 'FG', ?, ?, ?, 0, NULL, 'Unrestricted')", (order["item_id"], lot_number, completed_qty))
        self._audit("complete_work_order", "work_orders", work_order_id, "update", {"status": "Completed", "completed_qty": completed_qty, "scrap_qty": scrap_qty})
        self._audit("complete_work_order", "inventory_on_hand", f"SEA:FG:{order['item_id']}:{lot_number}", "insert", {"quantity": completed_qty})
        return {"work_order_id": work_order_id, "status": "Completed", "completed_qty": completed_qty, "scrap_qty": scrap_qty}

    def _tool_record_wip_variance(self, variance_id: str, work_order_id: str, material_variance: float, labor_variance: float, overhead_variance: float) -> dict[str, Any]:
        order = self._one("SELECT * FROM work_orders WHERE work_order_id = ?", (work_order_id,))
        if order["status"] != "Completed":
            raise ValueError("work order must be completed before variance posting")
        payload = {"variance_id": variance_id, "task_id": self.task["task_id"], "work_order_id": work_order_id, "material_variance": material_variance, "labor_variance": labor_variance, "overhead_variance": overhead_variance, "status": "Posted"}
        self.connection.execute("INSERT INTO wip_variances VALUES (?, ?, ?, ?, ?, ?, ?)", tuple(payload.values()))
        self._audit("record_wip_variance", "wip_variances", variance_id, "insert", payload)
        return {"variance_id": variance_id, "status": "Posted"}

    def _tool_create_transfer(self, transfer_id: str, item_id: str, lot_number: str, from_plant: str, from_subinventory: str, to_plant: str, to_subinventory: str, quantity: float, transferred_at: str) -> dict[str, Any]:
        lot = self._one("SELECT * FROM inventory_on_hand WHERE plant_id = ? AND subinventory = ? AND item_id = ? AND lot_number = ?", (from_plant, from_subinventory, item_id, lot_number))
        if lot["status"] != "Unrestricted" or lot["quantity"] - lot["reserved_qty"] < quantity:
            raise ValueError("donor plant lacks unrestricted surplus")
        payload = {"transfer_id": transfer_id, "task_id": self.task["task_id"], "item_id": item_id, "lot_number": lot_number, "from_plant": from_plant, "from_subinventory": from_subinventory, "to_plant": to_plant, "to_subinventory": to_subinventory, "quantity": quantity, "status": "In Transit", "transferred_at": transferred_at}
        self.connection.execute("INSERT INTO inventory_transfers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(payload.values()))
        self.connection.execute("UPDATE inventory_on_hand SET quantity = quantity - ? WHERE plant_id = ? AND subinventory = ? AND item_id = ? AND lot_number = ?", (quantity, from_plant, from_subinventory, item_id, lot_number))
        self._audit("create_transfer", "inventory_transfers", transfer_id, "insert", payload)
        self._audit("create_transfer", "inventory_on_hand", f"{from_plant}:{from_subinventory}:{item_id}:{lot_number}", "update", {"quantity_delta": -quantity})
        return {"transfer_id": transfer_id, "status": "In Transit"}

    def _tool_complete_transfer(self, transfer_id: str, arrival_date: str) -> dict[str, Any]:
        transfer = self._one("SELECT * FROM inventory_transfers WHERE transfer_id = ?", (transfer_id,))
        if transfer["status"] != "In Transit":
            raise ValueError("transfer is not in transit")
        self.connection.execute("UPDATE inventory_transfers SET status = 'Completed', transferred_at = ? WHERE transfer_id = ?", (arrival_date, transfer_id))
        self.connection.execute(
            "INSERT INTO inventory_on_hand (plant_id, subinventory, item_id, lot_number, quantity, reserved_qty, expiration_date, status) VALUES (?, ?, ?, ?, ?, 0, NULL, 'Unrestricted') ON CONFLICT(plant_id, subinventory, item_id, lot_number) DO UPDATE SET quantity = quantity + excluded.quantity",
            (transfer["to_plant"], transfer["to_subinventory"], transfer["item_id"], transfer["lot_number"], transfer["quantity"]),
        )
        self._audit("complete_transfer", "inventory_transfers", transfer_id, "update", {"status": "Completed", "arrival_date": arrival_date})
        self._audit("complete_transfer", "inventory_on_hand", f"{transfer['to_plant']}:{transfer['to_subinventory']}:{transfer['item_id']}:{transfer['lot_number']}", "upsert", {"quantity_delta": transfer["quantity"]})
        return {"transfer_id": transfer_id, "status": "Completed", "arrival_date": arrival_date}

    def _tool_reschedule_work_order(self, work_order_id: str, scheduled_start: str, scheduled_completion: str, workcenter_id: str) -> dict[str, Any]:
        center = self._one("SELECT * FROM workcenters WHERE workcenter_id = ?", (workcenter_id,))
        if center["status"] != "Active" or scheduled_completion < scheduled_start:
            raise ValueError("schedule or workcenter is infeasible")
        self.connection.execute("UPDATE work_orders SET scheduled_start = ?, scheduled_completion = ?, workcenter_id = ? WHERE work_order_id = ?", (scheduled_start, scheduled_completion, workcenter_id, work_order_id))
        self._audit("reschedule_work_order", "work_orders", work_order_id, "update", {"scheduled_start": scheduled_start, "scheduled_completion": scheduled_completion, "workcenter_id": workcenter_id})
        return {"work_order_id": work_order_id, "scheduled_start": scheduled_start, "scheduled_completion": scheduled_completion, "workcenter_id": workcenter_id}

    def _tool_create_maintenance_work_order(self, maintenance_id: str, workcenter_id: str, priority: str, scheduled_start: str, expected_finish: str, failure_code: str) -> dict[str, Any]:
        center = self._one("SELECT * FROM workcenters WHERE workcenter_id = ?", (workcenter_id,))
        if center["status"] != "Down":
            raise ValueError("maintenance requires a down workcenter")
        payload = {"maintenance_id": maintenance_id, "task_id": self.task["task_id"], "workcenter_id": workcenter_id, "priority": priority, "status": "Open", "scheduled_start": scheduled_start, "expected_finish": expected_finish, "failure_code": failure_code}
        self.connection.execute("INSERT INTO maintenance_work_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)", tuple(payload.values()))
        self._audit("create_maintenance_work_order", "maintenance_work_orders", maintenance_id, "insert", payload)
        return {"maintenance_id": maintenance_id, "status": "Open"}

    def _tool_reroute_operation(self, work_order_id: str, sequence: int, workcenter_id: str) -> dict[str, Any]:
        center = self._one("SELECT * FROM workcenters WHERE workcenter_id = ?", (workcenter_id,))
        if center["status"] != "Active" or center["qualified_item_class"] != "control_panel" or center["capacity_hours"] <= 0:
            raise ValueError("alternate workcenter is not qualified and available")
        self.connection.execute("UPDATE work_order_operations SET workcenter_id = ? WHERE work_order_id = ? AND sequence = ?", (workcenter_id, work_order_id, sequence))
        self._audit("reroute_operation", "work_order_operations", f"{work_order_id}:{sequence}", "update", {"workcenter_id": workcenter_id})
        return {"work_order_id": work_order_id, "sequence": sequence, "workcenter_id": workcenter_id}

    def _tool_submit_answer(self, **fields: Any) -> dict[str, Any]:
        normalized_fields = normalize_answer_fields(self.task, fields)
        for field, normalized in normalized_fields.items():
            self.connection.execute(
                "INSERT INTO answers (task_id, field, value) VALUES (?, ?, ?) ON CONFLICT(task_id, field) DO UPDATE SET value = excluded.value",
                (self.task["task_id"], field, normalized),
            )
            self._audit("submit_answer", "answers", f"{self.task['task_id']}:{field}", "upsert", {"value": normalized})
        return {"task_id": self.task["task_id"], "submitted": normalized_fields}
