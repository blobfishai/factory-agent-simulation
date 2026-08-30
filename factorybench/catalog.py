"""FactoryBench-100 v3 employee-decision workflow catalog.

The catalog is deliberately data-driven, but not variant-driven: each of the
100 scenarios is independently authored in :mod:`factorybench.scenarios`.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from copy import deepcopy
from datetime import date, timedelta
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

from .contracts import READ_TOOLS, TOOL_BY_NAME, WRITE_TOOLS
from .evidence import build_evidence
from .realism import FAMILY_PROFILES, build_decision_case, fact_for_oracle_tool, source_fact_text
from .scenarios import FAMILIES, FAMILY_DESCRIPTIONS, SCENARIOS, Scenario


BENCHMARK_NAME = "FactoryBench-100"
BENCHMARK_VERSION = "3.3.4"
MINIMUM_PROVIDER_READ_CALLS = 26
AS_OF_DATE = date(2026, 1, 12)
WORLD_ID = "northstar-enterprise-fusion-v3"


# Provider fields that carry human-authored wording rather than the business
# identity, quantity, date, accounting, or routing state of a transaction.
# These fields are still checked for scoped business meaning, but natural
# employee wording must not fail merely because it differs from a gold string.
_SEMANTIC_PROVIDER_FIELDS = frozenset(
    {
        "WorkOrderDescription",
        "MaintenanceProgramName",
        "Description",
        "ItemDescription",
        "OperationName",
        "Comments",
        "HoldReason",
        "ReleaseReason",
        "acknowledgementNote",
        "closeReason",
        "cancellationReason",
        "DocumentName",
        "DocumentNumber",
    }
)


EVIDENCE_PATTERNS: tuple[dict[str, tuple[str, ...]], ...] = (
    {
        "reads": ("gmail.messages.list", "gmail.messages.get", "google_drive.files.list", "google_drive.files.download", "google_sheets.spreadsheets.values.batchGet", "slack.conversations_replies"),
        "writes": ("google_sheets.spreadsheets.values.update", "gmail.drafts.create"),
    },
    {
        "reads": ("slack.search_messages", "slack.conversations_replies", "google_drive.files.list", "google_sheets.spreadsheets.values.get", "gmail.threads.get"),
        "writes": ("google_drive.comments.create", "slack.chat_postMessage"),
    },
    {
        "reads": ("google_drive.files.list", "google_drive.files.export", "google_sheets.spreadsheets.get", "slack.conversations_history", "gmail.messages.list", "gmail.messages.attachments.get"),
        "writes": ("google_sheets.spreadsheets.values.append", "slack.reactions_add"),
    },
    {
        "reads": ("gmail.messages.list", "gmail.threads.get", "slack.conversations_history", "google_sheets.spreadsheets.get", "google_drive.files.list"),
        "writes": ("gmail.drafts.create", "google_drive.comments.create"),
    },
    {
        "reads": ("google_sheets.spreadsheets.values.get", "google_drive.files.list", "google_drive.files.export", "slack.files_info", "gmail.messages.list", "gmail.messages.get"),
        "writes": ("gmail.messages.send", "google_sheets.spreadsheets.values.update"),
    },
    {
        "reads": ("slack.conversations_history", "gmail.messages.list", "gmail.messages.get", "google_drive.files.get", "google_sheets.spreadsheets.values.batchGet", "google_drive.files.list"),
        "writes": ("slack.chat_postMessage", "gmail.drafts.create"),
    },
    {
        "reads": ("google_drive.files.list", "google_drive.files.download", "slack.search_messages", "gmail.messages.list", "gmail.threads.get", "google_sheets.spreadsheets.get"),
        "writes": ("google_drive.comments.create", "google_sheets.spreadsheets.values.append"),
    },
    {
        "reads": ("gmail.messages.list", "gmail.messages.attachments.get", "google_drive.files.download", "slack.conversations_replies", "google_sheets.spreadsheets.get", "google_drive.files.list"),
        "writes": ("google_drive.comments.create", "gmail.messages.send"),
    },
    {
        "reads": ("google_sheets.spreadsheets.values.batchGet", "gmail.messages.list", "gmail.messages.get", "slack.files_info", "google_drive.files.list"),
        "writes": ("google_sheets.spreadsheets.values.update", "slack.chat_postMessage"),
    },
    {
        "reads": ("google_drive.files.list", "google_drive.files.get", "gmail.messages.list", "gmail.messages.attachments.get", "slack.conversations_history", "google_sheets.spreadsheets.values.get"),
        "writes": ("gmail.drafts.create", "slack.reactions_add"),
    },
)

def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _answer_schema(
    answer: dict[str, Any],
    descriptions: dict[str, str] | None = None,
) -> dict[str, Any]:
    properties: dict[str, dict[str, Any]] = {}
    for field, value in answer.items():
        if isinstance(value, int):
            properties[field] = {"type": "integer"}
        elif isinstance(value, float):
            properties[field] = {"type": "number", "multipleOf": 0.01}
        else:
            properties[field] = {"type": "string"}
        if descriptions and field in descriptions:
            properties[field]["description"] = descriptions[field]
    return {
        "type": "object",
        "properties": properties,
        "required": sorted(answer),
        "additionalProperties": False,
    }


def _field_value(field: str, ordinal: int, scenario: Scenario) -> Any:
    effective = AS_OF_DATE + timedelta(days=(ordinal % 19) + 1)
    lowered = field.lower()
    if "quantity" in lowered:
        return 8 + ordinal % 37
    if "amount" in lowered or "value" in lowered:
        return round((8 + ordinal % 37) * (42.5 + ordinal * 1.17), 2)
    if "date" in lowered or "finish" in lowered or "completion" in lowered or "horizon" in lowered:
        return effective.isoformat()
    if "timestamp" in lowered:
        return f"{effective.isoformat()}T16:00:00-08:00"
    if "period" in lowered:
        return "2026-01"
    if any(token in lowered for token in ("action", "decision", "outcome", "result", "disposition")):
        return scenario.result_status
    prefixes = {
        "invoice": "INV",
        "maintenance": "MWO",
        "program": "PM",
        "purchase": "PO",
        "supplier": "SUP",
        "order": "ORD",
        "work_order": "WO",
        "transaction": "TX",
        "inspection": "INSP",
        "project": "PRJ",
        "case": "CASE",
        "change": "ECO",
        "supply": "SUPPLY",
        "receipt": "RCV",
        "record": "NS",
        "reference": "REF",
    }
    for token, prefix in prefixes.items():
        if token in lowered:
            return f"{prefix}-{ordinal:04d}"
    if "route" in lowered or "location" in lowered or "destination" in lowered:
        return f"SEA-{1 + ordinal % 4}"
    return f"FB-{ordinal:03d}"


def _answer(scenario: Scenario, ordinal: int) -> dict[str, Any]:
    return deepcopy(build_decision_case(scenario, ordinal)["answer"])


def _base64_message(scenario: Scenario, ordinal: int, *, sent: bool) -> str:
    decision = build_decision_case(scenario, ordinal)
    case = decision["case_reference"]
    kind = "Completed" if sent else "Draft"
    message = (
        f"From: {scenario.role.replace('_', '.')}@northstar.example\r\n"
        f"To: {decision['stakeholder'].replace(' ', '.')}@northstar.example\r\n"
        f"Subject: {case} — {kind} operating decision\r\n"
        "Content-Type: text/plain; charset=UTF-8\r\n\r\n"
        f"Decision: {decision['selected_option']}. Completion: {decision['selected_completion']}.\r\n"
        f"Binding constraint: {decision['binding_constraint']}.\r\n"
        f"Alternatives: {decision['alternative_impact']}.\r\n"
        f"Oracle record: {decision['record']}. Approval: AP-{ordinal:04d}. Case: {case}.\r\n"
    )
    return base64.urlsafe_b64encode(message.encode()).decode().rstrip("=")


def _path_value(name: str, ordinal: int) -> Any:
    if name == "OrderKey":
        # Oracle Order Management accepts HeaderId as an OrderKey string.
        return str(12_000_000 + ordinal)
    if name == "InspectionEventId":
        return f"IE-{1_100_000 + ordinal}"
    if name in {
        "WorkOrderId",
        "WorkOrderOperationId",
        "WorkOrderOperationId2",
        "WorkOrderOperationMaterialId",
        "WorkOrderOperationResourceId",
        "WoOperationId",
        "WoOperationMaterialId",
        "WoOperationResourceId",
        "MaintenanceProgramId",
        "SupplierId",
        "HeaderInterfaceId",
        "InterfaceTransactionId",
        "InvoiceId",
        "HoldId",
    }:
        offsets = {
            "WorkOrderId": 100_000,
            "WorkOrderOperationId": 200_000,
            "WorkOrderOperationId2": 200_000,
            "WorkOrderOperationMaterialId": 300_000,
            "WorkOrderOperationResourceId": 400_000,
            "WoOperationId": 200_000,
            "WoOperationMaterialId": 300_000,
            "WoOperationResourceId": 400_000,
            "MaintenanceProgramId": 500_000,
            "SupplierId": 600_000,
            "HeaderInterfaceId": 700_000,
            "InterfaceTransactionId": 800_000,
            "InvoiceId": 900_000,
            "HoldId": 1_000_000,
        }
        return offsets[name] + ordinal
    return f"{name}-{ordinal:04d}"


def _provider_critical_value(value: Any) -> Any:
    """Remove only free-form provider prose from an otherwise exact payload."""

    if isinstance(value, dict):
        return {
            key: _provider_critical_value(item)
            for key, item in value.items()
            if key not in _SEMANTIC_PROVIDER_FIELDS
        }
    if isinstance(value, list):
        return [_provider_critical_value(item) for item in value]
    return deepcopy(value)


def _provider_critical_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return the provider-critical subset graded by exact field and value."""

    return _provider_critical_value(arguments)


def _has_semantic_provider_fields(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key in _SEMANTIC_PROVIDER_FIELDS
            or _has_semantic_provider_fields(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_has_semantic_provider_fields(item) for item in value)
    return False


def _provider_argument_paths(value: Any, path: str = "") -> list[str]:
    """List provider argument leaf paths authorized for one mutation."""

    if isinstance(value, dict):
        return [
            leaf
            for key, item in value.items()
            for leaf in _provider_argument_paths(
                item,
                f"{path}.{key}" if path else key,
            )
        ]
    if isinstance(value, list):
        return [
            leaf
            for index, item in enumerate(value)
            for leaf in _provider_argument_paths(item, f"{path}[{index}]")
        ]
    return [path]


def _oracle_body(tool: str, ordinal: int, scenario: Scenario) -> dict[str, Any]:
    decision = build_decision_case(scenario, ordinal)
    effective = date.fromisoformat(decision["selected_start"])
    completion = date.fromisoformat(decision["selected_completion"])
    quantity = decision["transaction_measure"]
    transaction_unit = decision["transaction_unit"]
    item = decision["item"]
    case = decision["case_reference"]
    state_summary = (
        f"{scenario.result_status}: {decision['selected_option']}; completion {decision['selected_completion']}; "
        f"constraint {decision['binding_constraint']}; approval AP-{ordinal:04d}"
    )
    common: dict[str, dict[str, Any]] = {
        "oracle_fusion.work_orders.create": {"OrganizationCode": "SEA", "WorkOrderNumber": f"WO-{ordinal:04d}", "ItemNumber": item, "WorkOrderQuantity": quantity, "WorkOrderStatusCode": "ORA_RELEASED", "PlannedStartDate": effective.isoformat(), "PlannedCompletionDate": completion.isoformat()},
        "oracle_fusion.work_orders.update": {"WorkOrderStatusCode": "ORA_RELEASED", "PlannedStartDate": effective.isoformat(), "PlannedCompletionDate": completion.isoformat()},
        "oracle_fusion.maintenance_work_orders.create": {"OrganizationCode": "SEA", "WorkOrderNumber": f"MWO-{ordinal:04d}", "AssetNumber": f"ASSET-{ordinal:03d}", "WorkOrderDescription": state_summary, "WorkOrderTypeCode": "CORRECTIVE", "WorkOrderStatusCode": "ORA_RELEASED", "PlannedStartDate": effective.isoformat(), "PlannedCompletionDate": completion.isoformat()},
        "oracle_fusion.maintenance_work_orders.update": {"WorkOrderDescription": state_summary, "WorkOrderStatusCode": "ORA_RELEASED", "PlannedCompletionDate": completion.isoformat()},
        "oracle_fusion.maintenance_programs.create": {"MaintenanceProgramCode": f"PM-{ordinal:04d}", "MaintenanceProgramName": scenario.title, "OrganizationCode": "SEA", "StatusCode": "ACTIVE", "ForecastStartDate": effective.isoformat(), "ForecastEndDate": (effective + timedelta(days=90)).isoformat()},
        "oracle_fusion.maintenance_programs.update": {"StatusCode": "ACTIVE", "ForecastStartDate": effective.isoformat(), "ForecastEndDate": (effective + timedelta(days=90)).isoformat()},
        "oracle_fusion.invoices.create": {"BusinessUnit": "Northstar Manufacturing BU", "Supplier": "Cascade Industrial", "SupplierSite": "SEA", "InvoiceNumber": f"INV-{ordinal:04d}", "InvoiceDate": effective.isoformat(), "InvoiceAmount": decision["supported_value"], "InvoiceCurrency": "USD", "PaymentTerms": "Net 30"},
        "oracle_fusion.invoices.update": {"PaymentTerms": "Net 45"},
        "oracle_fusion.draft_purchase_orders.create": {"SupplierId": 600_000 + ordinal, "SupplierSiteId": 610_000 + ordinal, "ProcurementBUId": 204, "RequisitioningBUId": 204, "BuyerId": 9100 + ordinal, "DocumentStyleId": 1, "CurrencyCode": "USD", "Description": state_summary, "RequiredAcknowledgment": "Document and Schedule", "lines": [{"LineNumber": 1, "LineType": "Goods", "Item": item, "ItemDescription": scenario.title, "Quantity": 1, "UOM": "LOT", "Price": decision["supported_value"]}]},
        "oracle_fusion.quality_inspection_results.create": {"OrganizationCode": "SEA", "InspectionPlanName": f"PLAN-{1 + ordinal % 12:02d}", "InspectionPlanId": 1_200_000 + ordinal, "DocumentType": "RECEIVING", "DocumentNumber": f"RCV-{ordinal:04d}", "ItemNumber": item, "Quantity": quantity, "LotNumber": f"LOT-{ordinal:04d}", "InspectionStatus": "IN_PROGRESS", "samples": [{"SampleNumber": 1, "Result": "PASS"}]},
        "oracle_fusion.quality_inspection_results.update": {"InspectionStatus": "COMPLETE", "InspectionResult": "ACCEPT", "QuantityAccepted": quantity, "QuantityRejected": 0, "samples": [{"SampleNumber": 1, "Result": "PASS"}]},
        "oracle_fusion.work_order_operations.create": {"OperationSequenceNumber": 30 + ordinal % 10, "OperationName": f"Approved rework {case}", "WorkCenterCode": "WC-REWORK", "PlannedStartDate": effective.isoformat(), "PlannedCompletionDate": completion.isoformat()},
        "oracle_fusion.work_order_operations.update": {"WorkCenterCode": f"WC-ALT-{1 + ordinal % 3}", "PlannedStartDate": effective.isoformat(), "PlannedCompletionDate": completion.isoformat(), "OperationName": f"Controlled operation {case}"},
        "oracle_fusion.work_order_materials.update": {"QuantityPERProduct": decision["per_unit"], "SupplySubinventory": "STORES"},
        "oracle_fusion.work_order_resources.create": {"ResourceCode": f"RES-CERT-{ordinal:03d}", "UsageRate": 1.0, "AssignedUnits": 1, "BasisType": "VARIABLE"},
        "oracle_fusion.work_order_resources.update": {"UsageRate": 1.0, "AssignedUnits": 1},
        "oracle_fusion.maintenance_operations.update": {"WorkCenterCode": f"MAINT-{1 + ordinal % 3}", "OperationName": f"Corrective action {case}", "PlannedStartDate": effective.isoformat()},
        "oracle_fusion.receiving_receipt_transactions.update": {"TransactionType": "CORRECT", "Quantity": quantity, "InspectionQualityCode": "ACCEPT", "Comments": case},
        "oracle_fusion.work_order_materials.replace_with_substitute": {"substituteItemNumber": f"NS-SUB-{ordinal:03d}"},
        "oracle_fusion.material_transactions.create": {"SourceSystemCode": "FUSION_MOBILE", "SourceSystemType": "EXTERNAL", "MaterialTransactionDetail": [{"OrganizationCode": "SEA", "WorkOrderNumber": f"WO-{ordinal:04d}", "InventoryItemNumber": item, "TransactionTypeCode": "MATERIAL_ISSUE", "TransactionQuantity": quantity, "TransactionUnitOfMeasure": transaction_unit, "SubinventoryCode": "STORES", "LotNumber": f"LOT-{ordinal:04d}"}]},
        "oracle_fusion.operation_transactions.create": {"SourceSystemCode": "FUSION_MOBILE", "SourceSystemType": "EXTERNAL", "OperationTransactionDetail": [{"OrganizationCode": "SEA", "WorkOrderNumber": f"WO-{ordinal:04d}", "WoOperationSequenceNumber": 10, "FromDispatchState": "READY", "ToDispatchState": "COMPLETE", "TransactionQuantity": quantity, "TransactionUnitOfMeasure": transaction_unit}]},
        "oracle_fusion.resource_transactions.create": {"SourceSystemCode": "FUSION_MOBILE", "ResourceTransactionDetail": [{"OrganizationCode": "SEA", "WorkOrderNumber": f"WO-{ordinal:04d}", "WoOperationSequenceNumber": 10, "ResourceCode": f"RES-{ordinal:03d}", "TransactionQuantity": quantity, "TransactionUnitOfMeasure": transaction_unit}]},
        "oracle_fusion.inventory_transactions.create": {"SourceSystemCode": "EXTERNAL", "TransactionMode": "ONLINE", "TransactionLines": [{"OrganizationCode": "SEA", "Item": item, "Subinventory": "STORES", "TransactionType": "Subinventory Transfer", "TransactionQuantity": quantity, "TransactionUnitOfMeasure": transaction_unit, "LotNumber": f"LOT-{ordinal:04d}", "TransferSubinventory": "CONTROLLED"}]},
        "oracle_fusion.supply_requests.create": {"SupplyOrderReferenceNumber": f"SUPPLY-{ordinal:04d}", "SupplyRequestSystem": "EXT", "SupplyRequestDate": effective.isoformat(), "supplyRequestLines": [{"SupplyOrderSource": "EXT", "SupplyType": "BUY", "ItemNumber": item, "Quantity": quantity, "NeedByDate": completion.isoformat(), "DestinationOrganizationCode": "SEA"}]},
        "oracle_fusion.receiving_receipt_requests.create": {"ReceiptSourceCode": "VENDOR", "OrganizationCode": "SEA", "VendorName": "Cascade Industrial", "EmployeeId": 7100 + ordinal, "lines": [{"SourceDocumentCode": "PO", "POHeaderId": 2_000_000 + ordinal, "POLineId": 2_100_000 + ordinal, "ItemNumber": item, "Quantity": quantity, "UnitOfMeasure": transaction_unit, "LotNumber": f"LOT-{ordinal:04d}"}]},
        "oracle_fusion.receiving_receipt_transactions.create": {"TransactionType": "RECEIVE", "Quantity": quantity, "ItemNumber": item, "InspectionQualityCode": "ACCEPT", "lotItemLots": [{"LotNumber": f"LOT-{ordinal:04d}", "PrimaryQuantity": quantity}]},
        "oracle_fusion.maintenance_documents.create": {"DocumentName": f"{case}-technical-evidence", "DocumentNumber": f"DOC-{ordinal:04d}", "DocumentType": "URL", "Description": state_summary},
        "oracle_fusion.invoices.validate": {"ProcessAction": "Validate", "BusinessUnit": "Northstar Manufacturing BU", "Supplier": "Cascade Industrial", "InvoiceNumber": f"INV-{ordinal:04d}"},
        "oracle_fusion.invoice_holds.create": {"InvoiceId": 900_000 + ordinal, "HoldName": "CONTROL REVIEW", "HoldReason": state_summary},
        "oracle_fusion.invoice_holds.update": {"ReleaseName": "APPROVED EVIDENCE", "ReleaseReason": state_summary},
        "oracle_fusion.purchase_orders.acknowledge": {"supplierOrder": f"SUP-ACK-{ordinal:04d}", "acknowledgementNote": state_summary},
        "oracle_fusion.purchase_orders.close": {"closeAction": "finallyClose", "closeReason": state_summary},
        "oracle_fusion.purchase_orders.cancel": {"cancellationReason": state_summary, "cancelUnfulfilledDemandFlag": True, "initiatingParty": "buyer"},
        "oracle_fusion.maintenance_programs.generate_forecasts": {"MaintenanceProgramCode": f"PM-{ordinal:04d}", "ForecastStartDate": effective.isoformat(), "ForecastEndDate": (effective + timedelta(days=90)).isoformat()},
        "oracle_fusion.maintenance_programs.generate_work_orders": {"MaintenanceProgramCode": f"PM-{ordinal:04d}", "WorkOrderStartDate": effective.isoformat(), "WorkOrderEndDate": (effective + timedelta(days=30)).isoformat()},
    }
    body = deepcopy(common.get(tool, {}))
    if tool == "oracle_fusion.quality_inspection_results.update" and scenario.title == "Record failed dielectric-test samples":
        body.update(
            {
                "InspectionStatus": "COMPLETE",
                "InspectionResult": "REJECT",
                "QuantityAccepted": decision["usable_quantity"],
                "QuantityRejected": quantity,
                "samples": [{"SampleNumber": 1, "Result": "FAIL"}],
            }
        )
    if tool == "oracle_fusion.work_order_resources.create" and scenario.title in {
        "Recover output after a certified welder absence",
        "Move outsourced coating around a supplier outage",
    }:
        body["ResourceCode"] = f"RES-ALT-{ordinal:03d}"
    if tool == "oracle_fusion.material_transactions.create" and scenario.title in {
        "Return unused copper from a canceled operation",
        "Reverse a duplicated copper issue",
        "Return unused project material from WIP",
    }:
        detail = body["MaterialTransactionDetail"][0]
        detail["TransactionTypeCode"] = "MATERIAL_RETURN"
    if tool == "oracle_fusion.operation_transactions.create" and scenario.title in {
        "Record scrap discovered during final count",
        "Record yield loss from rejected processed parts",
    }:
        detail = body["OperationTransactionDetail"][0]
        detail["ToDispatchState"] = "REJECT"
    if tool == "oracle_fusion.inventory_transactions.create" and scenario.title == "Post a blind cycle-count adjustment":
        line = body["TransactionLines"][0]
        line["TransactionType"] = "Cycle Count Adjustment"
        line.pop("TransferSubinventory", None)
    if (
        tool == "oracle_fusion.material_transactions.create"
        and scenario.title == "Issue a reserved spare to an emergency repair"
    ):
        detail = body["MaterialTransactionDetail"][0]
        detail["WorkOrderNumber"] = decision["identifiers"]["maintenance_order"]
        detail["SubinventoryCode"] = "SERVICE-STORES"
    if (
        tool == "oracle_fusion.resource_transactions.create"
        and scenario.title == "Post an omitted maintenance labor charge"
    ):
        detail = body["ResourceTransactionDetail"][0]
        detail["WorkOrderNumber"] = decision["identifiers"]["maintenance_order"]
        detail["ResourceCode"] = f"MAINT-RES-CERT-{ordinal:03d}"
    if tool == "oracle_fusion.receiving_receipt_transactions.create" and scenario.title in {
        "Reject water-damaged enclosures at inspection",
        "Return mislabeled relays to the supplier",
    }:
        body["TransactionType"] = "RETURN TO VENDOR"
        body["InspectionQualityCode"] = "REJECT"
    return body


def _oracle_list_query(
    tool: str,
    ordinal: int,
    decision: dict[str, Any],
) -> str | None:
    """Use a queryable field from the concrete Fusion collection."""

    resource = _oracle_resource(tool)
    queries = {
        "work_orders": f"WorkOrderNumber='WO-{ordinal:04d}'",
        "maintenance_work_orders": (
            f"WorkOrderNumber='{decision['identifiers']['maintenance_order']}'"
        ),
        "maintenance_programs": f"MaintenanceProgramCode='PM-{ordinal:04d}'",
        "inventory_onhand_balances": (
            f"ItemNumber='{decision['item']}' and OrganizationCode='SEA'"
        ),
        "cycle_count_definitions": f"CycleCountName='SEA-BLIND-{ordinal:04d}'",
        "cycle_count_sequence_details": f"CycleCountEntryId={1_610_000 + ordinal}",
        "supply_requests": f"SupplyOrderReferenceNumber='SUPPLY-{ordinal:04d}'",
        "receiving_receipt_requests": (
            f"HeaderInterfaceId={_path_value('HeaderInterfaceId', ordinal)}"
        ),
        "quality_inspection_results": f"DocumentNumber='RCV-{ordinal:04d}'",
        "inspection_plans": f"InspectionPlanName='PLAN-{1 + ordinal % 12:02d}'",
        "purchase_orders": (
            f"OrderNumber='{decision['identifiers']['purchase_document']}'"
        ),
        "draft_purchase_orders": f"OrderNumber='DRAFT-PO-{ordinal:04d}'",
        "invoices": f"InvoiceNumber='INV-{ordinal:04d}'",
        "suppliers": f"SupplierNumber='SUP-{ordinal:05d}'",
        "sales_orders": (
            f"OrderNumber='{decision['identifiers']['order_number']}'"
        ),
    }
    return queries.get(resource)


def _post_write_read_tool(
    primary_write: str,
    scenario: Scenario | None = None,
) -> str:
    """Return the documented Fusion resource that exposes the committed effect."""

    if (
        scenario is not None
        and primary_write == "oracle_fusion.material_transactions.create"
        and scenario.title == "Issue a reserved spare to an emergency repair"
    ):
        return "oracle_fusion.maintenance_materials.list"
    if (
        scenario is not None
        and primary_write == "oracle_fusion.resource_transactions.create"
        and scenario.title == "Post an omitted maintenance labor charge"
    ):
        return "oracle_fusion.maintenance_resources.list"

    exact = {
        "oracle_fusion.work_orders.create": "oracle_fusion.work_orders.list",
        "oracle_fusion.work_orders.update": "oracle_fusion.work_orders.get",
        "oracle_fusion.maintenance_work_orders.create": "oracle_fusion.maintenance_work_orders.list",
        "oracle_fusion.maintenance_work_orders.update": "oracle_fusion.maintenance_work_orders.get",
        "oracle_fusion.maintenance_programs.create": "oracle_fusion.maintenance_programs.list",
        "oracle_fusion.maintenance_programs.update": "oracle_fusion.maintenance_programs.get",
        "oracle_fusion.maintenance_programs.generate_forecasts": "oracle_fusion.maintenance_programs.get",
        "oracle_fusion.maintenance_programs.generate_work_orders": "oracle_fusion.maintenance_work_orders.list",
        "oracle_fusion.invoices.create": "oracle_fusion.invoices.list",
        "oracle_fusion.invoices.update": "oracle_fusion.invoices.get",
        "oracle_fusion.invoices.validate": "oracle_fusion.invoices.get",
        "oracle_fusion.invoice_holds.create": "oracle_fusion.invoices.get",
        "oracle_fusion.invoice_holds.update": "oracle_fusion.invoices.get",
        "oracle_fusion.draft_purchase_orders.create": "oracle_fusion.draft_purchase_orders.list",
        "oracle_fusion.purchase_orders.acknowledge": "oracle_fusion.purchase_orders.get",
        "oracle_fusion.purchase_orders.close": "oracle_fusion.purchase_orders.get",
        "oracle_fusion.purchase_orders.cancel": "oracle_fusion.purchase_orders.get",
        "oracle_fusion.quality_inspection_results.create": "oracle_fusion.quality_inspection_results.list",
        "oracle_fusion.quality_inspection_results.update": "oracle_fusion.quality_inspection_results.list",
        "oracle_fusion.work_order_operations.create": "oracle_fusion.work_order_operations.list",
        "oracle_fusion.work_order_operations.update": "oracle_fusion.work_order_operations.list",
        "oracle_fusion.work_order_materials.update": "oracle_fusion.work_order_materials.list",
        "oracle_fusion.work_order_materials.replace_with_substitute": "oracle_fusion.work_order_materials.list",
        "oracle_fusion.work_order_resources.create": "oracle_fusion.work_order_resources.list",
        "oracle_fusion.work_order_resources.update": "oracle_fusion.work_order_resources.list",
        "oracle_fusion.maintenance_operations.update": "oracle_fusion.maintenance_operations.list",
        "oracle_fusion.receiving_receipt_transactions.update": "oracle_fusion.receiving_receipt_transactions.list",
        "oracle_fusion.material_transactions.create": "oracle_fusion.work_order_materials.list",
        "oracle_fusion.operation_transactions.create": "oracle_fusion.work_order_operations.list",
        "oracle_fusion.resource_transactions.create": "oracle_fusion.work_order_resources.list",
        "oracle_fusion.inventory_transactions.create": "oracle_fusion.inventory_onhand_balances.list",
        "oracle_fusion.supply_requests.create": "oracle_fusion.supply_requests.list",
        "oracle_fusion.receiving_receipt_requests.create": "oracle_fusion.receiving_receipt_requests.list",
        "oracle_fusion.receiving_receipt_transactions.create": "oracle_fusion.receiving_receipt_transactions.list",
        "oracle_fusion.maintenance_documents.create": "oracle_fusion.maintenance_documents.list",
    }
    try:
        return exact[primary_write]
    except KeyError as exc:
        raise ValueError(f"no provider readback resource for {primary_write}") from exc


def _post_write_state_patch(
    primary_write: str,
    post_read: str,
    ordinal: int,
    scenario: Scenario,
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Describe the provider fields whose changed value proves the mutation."""

    body = _provider_critical_value(
        _oracle_body(primary_write, ordinal, scenario)
    )
    quantity = decision["transaction_measure"]
    target = _oracle_record(post_read, ordinal, scenario, decision, quantity)
    patch: dict[str, Any] = {
        key: value
        for key, value in body.items()
        if key in target and not isinstance(value, (dict, list))
    }
    patch["LastUpdateDate"] = (
        f"{decision['selected_completion']}T16:00:00-08:00"
    )

    if primary_write == "oracle_fusion.work_order_materials.replace_with_substitute":
        patch.update(
            {
                "ItemNumber": body["substituteItemNumber"],
            }
        )
    elif primary_write == "oracle_fusion.material_transactions.create":
        detail = body["MaterialTransactionDetail"][0]
        signed_quantity = detail["TransactionQuantity"]
        if detail["TransactionTypeCode"] == "MATERIAL_RETURN":
            signed_quantity = -abs(signed_quantity)
        patch["IssuedQuantity"] = signed_quantity
        patch["SupplySubinventory"] = detail["SubinventoryCode"]
    elif primary_write == "oracle_fusion.operation_transactions.create":
        detail = body["OperationTransactionDetail"][0]
        patch["DispatchStatus"] = detail["ToDispatchState"]
        outcome_field = (
            "RejectedQuantity"
            if detail["ToDispatchState"] == "REJECT"
            else "CompletedQuantity"
        )
        patch[outcome_field] = abs(detail["TransactionQuantity"])
    elif primary_write == "oracle_fusion.resource_transactions.create":
        detail = body["ResourceTransactionDetail"][0]
        patch.update(
            {
                "ResourceCode": detail["ResourceCode"],
                "ChargedQuantity": detail["TransactionQuantity"],
            }
        )
    elif primary_write == "oracle_fusion.inventory_transactions.create":
        line = body["TransactionLines"][0]
        destination = line.get("TransferSubinventory", line["Subinventory"])
        quarantined = destination in {"CONTROLLED", "QUARANTINE", "HOLD"}
        resulting_quantity = (
            decision["raw_decision_values"]["eligible"]
            if line["TransactionType"] == "Cycle Count Adjustment"
            else abs(line["TransactionQuantity"])
        )
        patch.update(
            {
                "SubinventoryCode": destination,
                "LotNumber": line.get("LotNumber", target["LotNumber"]),
                "PrimaryQuantity": resulting_quantity,
                "AvailableToTransact": 0 if quarantined else resulting_quantity,
            }
        )
    elif primary_write == "oracle_fusion.supply_requests.create":
        line = body["supplyRequestLines"][0]
        patch.update(
            {
                "SupplyOrderReferenceNumber": body["SupplyOrderReferenceNumber"],
                "SupplyRequestStatus": "NEW",
                "ItemNumber": line["ItemNumber"],
                "Quantity": line["Quantity"],
                "NeedByDate": line["NeedByDate"],
                "DestinationOrganizationCode": line["DestinationOrganizationCode"],
            }
        )
    elif primary_write == "oracle_fusion.receiving_receipt_requests.create":
        patch["ProcessingStatusCode"] = "PENDING"
    elif primary_write in {
        "oracle_fusion.receiving_receipt_transactions.create",
        "oracle_fusion.receiving_receipt_transactions.update",
    }:
        patch["ProcessingStatusCode"] = "PENDING"
    elif primary_write == "oracle_fusion.invoices.validate":
        patch["ValidationStatus"] = "VALIDATED"
    elif primary_write == "oracle_fusion.invoice_holds.create":
        patch["invoiceHolds"] = [
            {
                "HoldId": _path_value("HoldId", ordinal),
                "HoldName": body["HoldName"],
                "HoldReason": body.get("HoldReason"),
                "HoldStatus": "ACTIVE",
            }
        ]
    elif primary_write == "oracle_fusion.invoice_holds.update":
        patch["invoiceHolds"] = [
            {
                "HoldId": _path_value("HoldId", ordinal),
                "ReleaseName": body["ReleaseName"],
                "ReleaseReason": body.get("ReleaseReason"),
                "HoldStatus": "RELEASED",
            }
        ]
    elif primary_write == "oracle_fusion.purchase_orders.acknowledge":
        patch["AcknowledgmentStatus"] = "ACCEPTED"
        patch["SupplierOrderNumber"] = body.get("supplierOrder")
    elif primary_write == "oracle_fusion.purchase_orders.close":
        patch["DocumentStatus"] = "FINALLY CLOSED"
    elif primary_write == "oracle_fusion.purchase_orders.cancel":
        patch["DocumentStatus"] = "CANCELED"
        patch["CanceledFlag"] = True
    elif primary_write == "oracle_fusion.maintenance_programs.generate_forecasts":
        patch.update(
            {
                "ForecastStartDate": body["ForecastStartDate"],
                "ForecastEndDate": body["ForecastEndDate"],
            }
        )
    elif primary_write == "oracle_fusion.maintenance_programs.generate_work_orders":
        patch.update(
            {
                "WorkOrderStatusCode": "ORA_UNRELEASED",
                "WorkOrderDescription": (
                    f"Generated from {body['MaintenanceProgramCode']} for "
                    f"{decision['case_reference']}"
                ),
                "PlannedStartDate": body["WorkOrderStartDate"],
                "PlannedCompletionDate": body["WorkOrderEndDate"],
            }
        )

    if set(patch) == {"LastUpdateDate"}:
        raise ValueError(f"provider readback for {primary_write} has no business field")
    return patch


def _materializes_new_provider_record(primary_write: str) -> bool:
    return primary_write in {
        "oracle_fusion.work_orders.create",
        "oracle_fusion.maintenance_work_orders.create",
        "oracle_fusion.maintenance_programs.create",
        "oracle_fusion.invoices.create",
        "oracle_fusion.draft_purchase_orders.create",
        "oracle_fusion.quality_inspection_results.create",
        "oracle_fusion.work_order_operations.create",
        "oracle_fusion.work_order_resources.create",
        "oracle_fusion.supply_requests.create",
        "oracle_fusion.receiving_receipt_requests.create",
        "oracle_fusion.receiving_receipt_transactions.create",
        "oracle_fusion.maintenance_documents.create",
    }


def _arguments(tool: str, ordinal: int, scenario: Scenario) -> dict[str, Any]:
    decision = build_decision_case(scenario, ordinal)
    case = decision["case_reference"]
    message_id = f"msg-{ordinal:03d}"
    file_id = f"drive-{ordinal:03d}"
    sheet_id = f"sheet-{ordinal:03d}"
    channel = ("C-PRODUCTION", "C-PROCUREMENT", "C-QUALITY", "C-FINANCE")[ordinal % 4]
    thread_ts = f"1768{ordinal:06d}.000100"
    explicit: dict[str, dict[str, Any]] = {
        "factorybench.context.get": {},
        "gmail.messages.list": {"userId": "me", "q": f'"{case}"', "maxResults": 20},
        "gmail.messages.get": {"userId": "me", "id": message_id, "format": "full"},
        "gmail.messages.attachments.get": {"userId": "me", "messageId": f"{message_id}-1", "id": f"att-{ordinal:03d}"},
        "gmail.threads.get": {"userId": "me", "id": f"thread-{ordinal:03d}", "format": "full"},
        "gmail.drafts.get": {"userId": "me", "id": f"draft-{ordinal:03d}", "format": "full"},
        "gmail.drafts.create": {"userId": "me", "message": {"raw": _base64_message(scenario, ordinal, sent=False), "threadId": f"thread-{ordinal:03d}"}},
        "gmail.messages.send": {"userId": "me", "raw": _base64_message(scenario, ordinal, sent=True), "threadId": f"thread-{ordinal:03d}"},
        "google_drive.files.list": {"q": f"name contains '{case}' and trashed = false", "pageSize": 50, "fields": "files(id,name,mimeType,modifiedTime,md5Checksum)"},
        "google_drive.files.get": {"fileId": file_id, "fields": "id,name,mimeType,modifiedTime,md5Checksum,description"},
        "google_drive.files.download": {"fileId": file_id},
        "google_drive.files.export": {"fileId": file_id, "mimeType": "text/plain"},
        "google_drive.comments.list": {"fileId": file_id, "pageSize": 100, "fields": "comments(id,content,resolved,createdTime)"},
        "google_drive.comments.get": {"fileId": file_id, "commentId": f"comment-{ordinal:03d}", "fields": "id,content,resolved,createdTime"},
        "google_drive.comments.create": {"fileId": file_id, "requestBody": {"content": f"{case}: {decision['selected_option']} recorded on Oracle record {decision['record']}; completion {decision['selected_completion']}; constraint {decision['binding_constraint']}; approval AP-{ordinal:04d}."}},
        "google_sheets.spreadsheets.get": {"spreadsheetId": sheet_id, "ranges": ["Control!A1:I50"], "includeGridData": False},
        "google_sheets.spreadsheets.values.get": {"spreadsheetId": sheet_id, "range": "Control!A1:I50", "majorDimension": "ROWS", "valueRenderOption": "UNFORMATTED_VALUE"},
        "google_sheets.spreadsheets.values.batchGet": {"spreadsheetId": sheet_id, "ranges": ["Control!A1:I50", "Approvals!A1:G20"], "majorDimension": "ROWS", "valueRenderOption": "UNFORMATTED_VALUE"},
        "google_sheets.spreadsheets.values.update": {"spreadsheetId": sheet_id, "range": f"Control!H{2 + ordinal % 40}", "valueInputOption": "RAW", "includeValuesInResponse": True, "requestBody": {"majorDimension": "ROWS", "values": [[f"{case} | {decision['selected_option']} | {decision['selected_completion']} | {decision['record']} | {decision['binding_constraint']} | AP-{ordinal:04d}"]]}},
        "google_sheets.spreadsheets.values.append": {"spreadsheetId": sheet_id, "range": "Audit!A:G", "valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS", "requestBody": {"majorDimension": "ROWS", "values": [[AS_OF_DATE.isoformat(), case, scenario.role, decision["selected_option"], decision["selected_completion"], decision["record"], f"AP-{ordinal:04d}"]]}},
        "slack.search_messages": {"query": f'"{case}"', "count": 50, "sort": "timestamp", "sort_dir": "asc"},
        "slack.conversations_history": {"channel": channel, "oldest": "1768000000.000000", "inclusive": True, "limit": 100},
        "slack.conversations_replies": {"channel": channel, "ts": thread_ts, "limit": 100},
        "slack.files_info": {"file": f"F-{ordinal:06d}"},
        "slack.chat_postMessage": {"channel": channel, "thread_ts": thread_ts, "text": f"{case}: Oracle record {decision['record']} now reflects {decision['selected_option']} with completion {decision['selected_completion']}. Binding constraint: {decision['binding_constraint']}. Alternatives: {decision['alternative_impact']}. Approval AP-{ordinal:04d}."},
        "slack.reactions_add": {"channel": channel, "timestamp": thread_ts, "name": "white_check_mark"},
    }
    if tool in explicit:
        return deepcopy(explicit[tool])
    definition = TOOL_BY_NAME[tool]
    schema = definition["inputSchema"]
    arguments: dict[str, Any] = {}
    for name in schema.get("required", []):
        if name == "requestBody":
            arguments[name] = _oracle_body(tool, ordinal, scenario)
        else:
            arguments[name] = _path_value(name, ordinal)
    if tool.startswith("oracle_fusion.") and tool.endswith(".list"):
        arguments.update({"limit": 50, "onlyData": True})
        query = _oracle_list_query(tool, ordinal, decision)
        if query:
            arguments["q"] = query
    if "requestBody" in schema.get("properties", {}) and "requestBody" not in arguments:
        arguments["requestBody"] = _oracle_body(tool, ordinal, scenario)
    return arguments


def _required_asset_read_calls(
    ordinal: int,
    scenario: Scenario,
    decision: dict[str, Any],
) -> list[dict[str, Any]]:
    """Require a mode-specific causal chain across 14 independent documents."""

    get = "google_drive.files.get"
    download = "google_drive.files.download"
    export = "google_drive.files.export"
    mode_layouts: dict[str, tuple[tuple[str, int], ...]] = {
        "plan": (
            (get, 2), (get, 1), (get, 12), (download, 13), (export, 21),
            (export, 4), (export, 20), (export, 10), (export, 18),
            (export, 11), (export, 16), (get, 9), (get, 8), (get, 26),
        ),
        "quantity": (
            (get, 2), (get, 1), (get, 12), (download, 13), (download, 14),
            (export, 4), (export, 20), (export, 22), (export, 10),
            (get, 9), (get, 8), (get, 26), (export, 11), (export, 21),
        ),
        "schedule": (
            (get, 2), (get, 1), (get, 12), (download, 13), (get, 23),
            (export, 17), (export, 16), (export, 11), (export, 4),
            (export, 10), (get, 9), (export, 19), (get, 8), (get, 26),
        ),
        "financial": (
            (get, 2), (get, 1), (get, 12), (export, 4), (download, 15),
            (export, 18), (export, 19), (get, 8), (export, 10),
            (export, 22), (get, 9), (export, 11), (get, 26), (get, 27),
        ),
        "identity": (
            (get, 2), (get, 1), (get, 12), (download, 13), (download, 14),
            (get, 28), (get, 26), (export, 4), (export, 10),
            (get, 9), (get, 8), (export, 19), (get, 27), (export, 11),
        ),
        "forecast": (
            (get, 2), (get, 1), (get, 12), (download, 13), (export, 21),
            (export, 4), (export, 16), (export, 17), (get, 23),
            (export, 11), (get, 9), (get, 8), (get, 28), (get, 26),
        ),
    }
    # Different operating teams enter the evidence graph at different control
    # points: planners begin with demand or schedule, maintenance begins with
    # outage and qualification, service begins with ownership, and close teams
    # begin with authority and reconciliation.  Rotate the mode-specific chain
    # by family/case and reverse it for teams whose control review runs outward
    # from the transaction.  The verifier still permits any causally valid read
    # order; this is the human reference path for that scenario.
    layout = list(mode_layouts[decision["decision_mode"]])
    family_index = FAMILIES.index(scenario.family)
    pivot = (family_index * 5 + ordinal) % len(layout)
    layout = layout[pivot:] + layout[:pivot]
    if family_index % 2:
        layout.reverse()
    calls: list[dict[str, Any]] = []
    for tool, asset_index in layout:
        arguments = _arguments(tool, ordinal, scenario)
        arguments["fileId"] = (
            f"drive-{ordinal:03d}"
            if asset_index == 2
            else f"drive-approval-{ordinal:03d}"
            if asset_index == 8
            else f"drive-{ordinal:03d}-{asset_index:02d}"
        )
        if tool == "google_drive.files.get":
            arguments.pop("fields", None)
            arguments["alt"] = "media"
        calls.append({"tool": tool, "arguments": arguments})
    return calls


def _partition_response_measure(value: float | int, count: int) -> list[float | int]:
    scale = 100 if isinstance(value, float) and not float(value).is_integer() else 1
    scaled = int(round(float(value) * scale))
    base, remainder = divmod(abs(scaled), count)
    sign = -1 if scaled < 0 else 1
    parts = [sign * (base + (1 if index < remainder else 0)) for index in range(count)]
    if scale == 1:
        return parts
    return [round(part / scale, 2) for part in parts]


_ORACLE_IDENTITY_FIELDS = (
    "WorkOrderId",
    "WorkOrderOperationId",
    "WorkOrderOperationMaterialId",
    "WorkOrderOperationResourceId",
    "WoOperationId",
    "WoOperationMaterialId",
    "WoOperationResourceId",
    "MaintenanceProgramId",
    "POHeaderId",
    "POLineId",
    "InvoiceId",
    "SupplierId",
    "InspectionEventId",
    "InspectionPlanId",
    "InventoryItemId",
    "HeaderInterfaceId",
    "InterfaceTransactionId",
    "OrderKey",
    "HeaderId",
    "SupplyRequestId",
    "DocumentId",
    "EntryHistoryId",
    "CycleCountEntryId",
    "CycleCountHeaderId",
)


def _oracle_resource(tool: str) -> str:
    return tool.removeprefix("oracle_fusion.").rsplit(".", 1)[0]


def _oracle_identity(record: dict[str, Any]) -> dict[str, Any]:
    for field in _ORACLE_IDENTITY_FIELDS:
        if field in record:
            return {field: record[field]}
    for field in (
        "OrderNumber",
        "WorkOrderNumber",
        "MaintenanceProgramCode",
        "InvoiceNumber",
        "SupplierNumber",
        "SupplyOrderReferenceNumber",
        "DocumentNumber",
        "InspectionPlanName",
    ):
        if field in record:
            return {field: record[field]}
    raise ValueError("Oracle fixture record has no provider identity")


def _oracle_status_field(resource: str) -> str | None:
    return {
        "work_orders": "WorkOrderStatusCode",
        "maintenance_work_orders": "WorkOrderStatusCode",
        "maintenance_programs": "StatusCode",
        "sales_orders": "StatusCode",
        "suppliers": "Status",
        "purchase_orders": "DocumentStatus",
        "purchase_order_lines": "LineStatus",
        "draft_purchase_orders": "DocumentStatus",
        "invoices": "ValidationStatus",
        "quality_inspection_results": "InspectionStatus",
        "inspection_plans": "StatusCode",
        "supply_requests": "SupplyRequestStatus",
        "receiving_receipt_requests": "ProcessingStatusCode",
        "receiving_receipt_transactions": "ProcessingStatusCode",
        "work_order_operations": "DispatchStatus",
        "maintenance_operations": "DispatchStatus",
        "maintenance_documents": "DocumentStatus",
        "cycle_count_sequence_details": "CountSequenceStatus",
    }.get(resource)


def _oracle_record(
    tool: str,
    ordinal: int,
    scenario: Scenario,
    decision: dict[str, Any],
    quantity: float | int,
) -> dict[str, Any]:
    """Build one response item using only fields from that Fusion resource."""

    resource = _oracle_resource(tool)
    case = decision["case_reference"]
    raw_values = decision["raw_decision_values"]
    updated = f"{AS_OF_DATE.isoformat()}T08:00:00-08:00"
    common = {"LastUpdateDate": updated, "LastUpdatedBy": "FACTORY.PLANNER"}

    records: dict[str, dict[str, Any]] = {
        "work_orders": {
            "OrganizationCode": "SEA",
            "WorkOrderId": _path_value("WorkOrderId", ordinal),
            "WorkOrderNumber": f"WO-{ordinal:04d}",
            "WorkOrderDescription": f"{case}: {scenario.title}",
            "SourceHeaderReference": case,
            "ItemNumber": decision["item"],
            "ItemRevision": decision["revision"],
            "PlannedStartQuantity": quantity,
            "WorkOrderStatusCode": "ORA_RELEASED",
            "PlannedStartDate": AS_OF_DATE.isoformat(),
            "PlannedCompletionDate": (AS_OF_DATE + timedelta(days=1)).isoformat(),
        },
        "sales_orders": {
            "OrderKey": _path_value("OrderKey", ordinal),
            "HeaderId": 12_000_000 + ordinal,
            "OrderNumber": decision["identifiers"]["order_number"],
            "SourceTransactionNumber": case,
            "SourceTransactionSystem": "NORTHSTAR_OMS",
            "BusinessUnitName": "Northstar Manufacturing BU",
            "StatusCode": "OPEN",
            "OrderedQuantity": decision["requested_quantity"],
            "RequestedShipDate": decision["requested_by"],
            "DemandStatusCode": "SCHEDULED",
        },
        "work_order_operations": {
            "WorkOrderId": _path_value("WorkOrderId", ordinal),
            "WorkOrderOperationId": _path_value("WorkOrderOperationId", ordinal),
            "OperationSequenceNumber": 10,
            "OperationName": f"Controlled operation for {case}",
            "WorkCenterCode": f"WC-{1 + ordinal % 4}",
            "DispatchStatus": "READY",
            "PlannedStartDate": AS_OF_DATE.isoformat(),
            "PlannedCompletionDate": (AS_OF_DATE + timedelta(days=1)).isoformat(),
            "CompletedQuantity": 0,
            "RejectedQuantity": 0,
        },
        "work_order_materials": {
            "WorkOrderId": _path_value("WorkOrderId", ordinal),
            "WorkOrderOperationId": _path_value("WorkOrderOperationId", ordinal),
            "WorkOrderOperationMaterialId": _path_value("WorkOrderOperationMaterialId", ordinal),
            "OperationSequenceNumber": 10,
            "MaterialSequenceNumber": 10,
            "ItemNumber": decision["item"],
            "ItemRevision": decision["revision"],
            "QuantityPerAssembly": decision["per_unit"],
            "RequiredQuantity": quantity,
            "IssuedQuantity": 0,
            "SupplySubinventory": "STORES",
        },
        "work_order_resources": {
            "WorkOrderId": _path_value("WorkOrderId", ordinal),
            "WorkOrderOperationId": _path_value("WorkOrderOperationId", ordinal),
            "WorkOrderOperationResourceId": _path_value("WorkOrderOperationResourceId", ordinal),
            "OperationSequenceNumber": 10,
            "ResourceCode": f"RES-CERT-{ordinal:03d}",
            "UsageRate": 1.0,
            "AssignedUnits": 1,
            "ChargedQuantity": 0,
        },
        "maintenance_resources": {
            "WorkOrderId": _path_value("WorkOrderId", ordinal),
            "WoOperationId": _path_value("WoOperationId", ordinal),
            "WoOperationResourceId": _path_value("WoOperationResourceId", ordinal),
            "OperationSequenceNumber": 10,
            "ResourceCode": f"MAINT-RES-CERT-{ordinal:03d}",
            "UsageRate": 1.0,
            "AssignedUnits": 1,
            "ChargedQuantity": 0,
        },
        "maintenance_materials": {
            "WorkOrderId": _path_value("WorkOrderId", ordinal),
            "WoOperationId": _path_value("WoOperationId", ordinal),
            "WoOperationMaterialId": _path_value("WoOperationMaterialId", ordinal),
            "OperationSequenceNumber": 10,
            "MaterialSequenceNumber": 10,
            "ItemNumber": decision["item"],
            "ItemRevision": decision["revision"],
            "QuantityPerAssembly": decision["per_unit"],
            "RequiredQuantity": quantity,
            "IssuedQuantity": 0,
            "SupplySubinventory": "SERVICE-STORES",
        },
        "maintenance_work_orders": {
            "OrganizationCode": "SEA",
            "WorkOrderId": _path_value("WorkOrderId", ordinal),
            "WorkOrderNumber": decision["identifiers"]["maintenance_order"],
            "WorkOrderDescription": f"{case}: {scenario.title}",
            "AssetNumber": decision["identifiers"]["asset_or_resource"],
            "WorkOrderStatusCode": "ORA_RELEASED",
            "PlannedStartDate": AS_OF_DATE.isoformat(),
            "PlannedCompletionDate": (AS_OF_DATE + timedelta(days=1)).isoformat(),
        },
        "maintenance_operations": {
            "WorkOrderId": _path_value("WorkOrderId", ordinal),
            "WoOperationId": _path_value("WoOperationId", ordinal),
            "OperationSequenceNumber": 10,
            "OperationName": f"Maintenance operation for {case}",
            "WorkCenterCode": f"MAINT-{1 + ordinal % 3}",
            "DispatchStatus": "READY",
            "PlannedStartDate": AS_OF_DATE.isoformat(),
            "PlannedCompletionDate": (AS_OF_DATE + timedelta(days=1)).isoformat(),
        },
        "maintenance_documents": {
            "WorkOrderId": _path_value("WorkOrderId", ordinal),
            "DocumentId": 1_300_000 + ordinal,
            "DocumentNumber": f"DOC-{ordinal:04d}",
            "DocumentName": f"{case}-source-reference",
            "DocumentType": "URL",
            "Description": f"Effective source reference for {case}",
            "DocumentStatus": "ACTIVE",
        },
        "maintenance_programs": {
            "MaintenanceProgramId": _path_value("MaintenanceProgramId", ordinal),
            "MaintenanceProgramCode": f"PM-{ordinal:04d}",
            "MaintenanceProgramName": f"{case}: {scenario.title}",
            "OrganizationCode": "SEA",
            "StatusCode": "ACTIVE",
            "ForecastStartDate": (AS_OF_DATE + timedelta(days=30)).isoformat(),
            "ForecastEndDate": (AS_OF_DATE + timedelta(days=120)).isoformat(),
        },
        "inventory_onhand_balances": {
            "OrganizationCode": "SEA",
            "InventoryItemId": 1_400_000 + ordinal,
            "ItemNumber": decision["item"],
            "ItemRevision": decision["revision"],
            "SubinventoryCode": "STORES",
            "Locator": f"SEA.STORES.{1 + ordinal % 8:02d}",
            "LotNumber": f"LOT-{ordinal:04d}",
            "PrimaryQuantity": raw_values["observed"],
            "ReservedQuantity": raw_values["excluded"],
            "AvailableToTransact": raw_values["eligible"],
            "PrimaryUnitOfMeasure": decision["unit"],
        },
        "cycle_count_definitions": {
            "CycleCountHeaderId": 1_600_000 + ordinal,
            "CycleCountName": f"SEA-BLIND-{ordinal:04d}",
            "Description": f"Blind controlled count for {case}",
            "OrganizationId": 204,
            "OrganizationCode": "SEA",
            "ApprovalRequired": "Yes",
            "ApprovalRequiredCode": 1,
            "ApprovalType": "Manual",
            "ApprovalTypeCode": "2",
            "DisplaySuggestedQuantity": "No",
            "MaximumRecounts": 2,
            "NegativeTolerancePercentage": 5,
            "PositiveTolerancePercentage": 5,
        },
        "cycle_count_sequence_details": {
            "CycleCountEntryId": 1_610_000 + ordinal,
            "CycleCountHeaderId": 1_600_000 + ordinal,
            "CycleCountName": f"SEA-BLIND-{ordinal:04d}",
            "OrganizationId": 204,
            "OrganizationCode": "SEA",
            "CountSequence": 1000 + ordinal,
            "CountSequenceStatus": "Pending approval",
            "CountSequenceStatusCode": "2",
            "ApprovalType": "Manual",
            "ItemNumber": decision["item"],
            "Revision": decision["revision"],
            "Subinventory": "STORES",
            "Locator": f"SEA.STORES.{1 + ordinal % 8:02d}",
            "LotNumber": f"LOT-{ordinal:04d}",
            "PrimarySuggestedQuantity": raw_values["scope"],
            "CountQuantity": raw_values["eligible"],
            "PrimaryAdjustmentQuantity": -raw_values["gap"],
            "Recounts": 2,
            "CountedBy": "Morgan, Casey",
            "CountDate": AS_OF_DATE.isoformat(),
        },
        "cycle_count_history": {
            "CycleCountEntryId": 1_610_000 + ordinal,
            "EntryHistoryId": 1_620_000 + ordinal,
            "CountQuantity": raw_values["eligible"],
            "CountUOM": decision["unit"],
            "CountedBy": "Morgan, Casey",
            "CountedByEmployeeId": 71_002,
            "CountDate": AS_OF_DATE.isoformat(),
            "PrimarySuggestedQuantity": raw_values["scope"],
            "Reason": "Independent recount",
        },
        "supply_requests": {
            "SupplyRequestId": 1_500_000 + ordinal,
            "SupplyOrderReferenceNumber": f"SUPPLY-{ordinal:04d}",
            "SupplyRequestSystem": "EXT",
            "SupplyRequestDate": AS_OF_DATE.isoformat(),
            "SupplyRequestStatus": "NEW",
            "ItemNumber": decision["item"],
            "Quantity": quantity,
            "NeedByDate": decision["requested_by"],
            "DestinationOrganizationCode": "SEA",
            "Description": case,
        },
        "receiving_receipt_requests": {
            "HeaderInterfaceId": _path_value("HeaderInterfaceId", ordinal),
            "ReceiptSourceCode": "VENDOR",
            "OrganizationCode": "SEA",
            "VendorName": decision["supplier"],
            "ProcessingStatusCode": "PENDING",
            "TransactionDate": AS_OF_DATE.isoformat(),
            "Comments": case,
        },
        "receiving_receipt_transactions": {
            "HeaderInterfaceId": _path_value("HeaderInterfaceId", ordinal),
            "InterfaceTransactionId": _path_value("InterfaceTransactionId", ordinal),
            "TransactionType": "RECEIVE",
            "ProcessingStatusCode": "PENDING",
            "Quantity": quantity,
            "ItemNumber": decision["item"],
            "UnitOfMeasure": decision["transaction_unit"],
            "InspectionQualityCode": "PENDING",
            "Comments": case,
        },
        "quality_inspection_results": {
            "InspectionEventId": _path_value("InspectionEventId", ordinal),
            "OrganizationCode": "SEA",
            "InspectionPlanId": 1_200_000 + ordinal,
            "InspectionPlanName": f"PLAN-{1 + ordinal % 12:02d}",
            "DocumentType": "RECEIVING",
            "DocumentNumber": f"RCV-{ordinal:04d}",
            "ItemNumber": decision["item"],
            "LotNumber": f"LOT-{ordinal:04d}",
            "Quantity": raw_values["observed"],
            "InspectionStatus": "COMPLETE",
            "InspectionResult": "ACCEPT",
            "QuantityAccepted": raw_values["eligible"],
            "QuantityRejected": raw_values["excluded"],
        },
        "inspection_plans": {
            "InspectionPlanId": 1_200_000 + ordinal,
            "InspectionPlanName": f"PLAN-{1 + ordinal % 12:02d}",
            "OrganizationCode": "SEA",
            "ItemNumber": decision["item"],
            "StatusCode": "APPROVED",
            "EffectiveFromDate": "2025-10-01",
            "EffectiveToDate": "2026-12-31",
            "Description": f"Effective inspection plan for {case}",
        },
        "suppliers": {
            "SupplierId": _path_value("SupplierId", ordinal),
            "Supplier": decision["supplier"],
            "SupplierNumber": f"SUP-{ordinal:05d}",
            "Status": "ACTIVE",
            "BusinessRelationship": "SPEND_AUTHORIZED",
            "TaxOrganizationType": "CORPORATION",
        },
        "purchase_orders": {
            "POHeaderId": 2_000_000 + ordinal,
            "OrderNumber": decision["identifiers"]["purchase_document"],
            "ProcurementBU": "Northstar Manufacturing BU",
            "Supplier": decision["supplier"],
            "SupplierId": _path_value("SupplierId", ordinal),
            "DocumentStatus": "OPEN",
            "CurrencyCode": "USD",
            "OrderedAmount": decision["approved_value"],
            "Description": case,
            "ScheduleDate": decision["standard_arrival"],
        },
        "purchase_order_lines": {
            "POHeaderId": 2_000_000 + ordinal,
            "POLineId": 2_100_000 + ordinal,
            "LineNumber": 1,
            "Item": decision["item"],
            "ItemDescription": f"{case}: {scenario.title}",
            "Quantity": quantity,
            "UOM": decision["transaction_unit"],
            "Price": decision["supported_value"],
            "LineStatus": "OPEN",
            "ScheduleDate": decision["standard_arrival"],
        },
        "draft_purchase_orders": {
            "POHeaderId": 2_200_000 + ordinal,
            "OrderNumber": f"DRAFT-PO-{ordinal:04d}",
            "SupplierId": _path_value("SupplierId", ordinal),
            "Supplier": decision["supplier"],
            "DocumentStatus": "INCOMPLETE",
            "CurrencyCode": "USD",
            "Total": decision["supported_value"],
            "Description": case,
        },
        "invoices": {
            "InvoiceId": _path_value("InvoiceId", ordinal),
            "InvoiceNumber": f"INV-{ordinal:04d}",
            "BusinessUnit": "Northstar Manufacturing BU",
            "Supplier": decision["supplier"],
            "SupplierSite": "SEA",
            "InvoiceDate": AS_OF_DATE.isoformat(),
            "InvoiceAmount": decision["approved_value"],
            "InvoiceCurrency": "USD",
            "PaymentTerms": "Net 30",
            "ValidationStatus": "NEVER VALIDATED",
            "AccountingDate": AS_OF_DATE.isoformat(),
        },
        "material_transactions": {
            "MaterialTransactionHeaderId": 3_000_000 + ordinal,
            "SourceSystemCode": "FUSION_MOBILE",
            "SourceSystemType": "EXTERNAL",
            "RequestStatus": "PENDING",
        },
        "operation_transactions": {
            "OperationTransactionHeaderId": 3_100_000 + ordinal,
            "SourceSystemCode": "FUSION_MOBILE",
            "SourceSystemType": "EXTERNAL",
            "RequestStatus": "PENDING",
        },
        "resource_transactions": {
            "ResourceTransactionHeaderId": 3_200_000 + ordinal,
            "SourceSystemCode": "FUSION_MOBILE",
            "RequestStatus": "PENDING",
        },
        "inventory_transactions": {
            "TransactionHeaderId": 3_300_000 + ordinal,
            "SourceSystemCode": "EXTERNAL",
            "TransactionMode": "ONLINE",
            "ReturnStatus": "SUCCESS",
        },
        "invoice_holds": {
            "HoldId": _path_value("HoldId", ordinal),
            "InvoiceId": _path_value("InvoiceId", ordinal),
            "HoldName": "CONTROL REVIEW",
            "HoldStatus": "ACTIVE",
        },
    }
    try:
        return {**records[resource], **common}
    except KeyError as exc:
        raise ValueError(f"no provider response profile for Oracle resource {resource}") from exc


def _oracle_candidate_rows(
    tool: str,
    record: dict[str, Any],
    ordinal: int,
    decision: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return realistic related rows while keeping one immutable effective match."""

    resource = _oracle_resource(tool)
    identity = _oracle_identity(record)
    identity_field, identity_value = next(iter(identity.items()))
    status_field = _oracle_status_field(resource)

    def change_identity(candidate: dict[str, Any], offset: int) -> None:
        if isinstance(identity_value, int):
            candidate[identity_field] = identity_value + offset
        else:
            candidate[identity_field] = f"{identity_value}-{offset // 100_000}"

    target = deepcopy(record)
    stale = deepcopy(record)
    change_identity(stale, 700_000)
    stale["LastUpdateDate"] = "2025-12-18T16:20:00-08:00"
    if status_field:
        stale[status_field] = "SUPERSEDED"
    if "ItemRevision" in stale:
        stale["ItemRevision"] = f"R{8 + ordinal % 3}"
    other_plant = deepcopy(record)
    change_identity(other_plant, 800_000)
    if "OrganizationCode" in other_plant:
        other_plant["OrganizationCode"] = "PDX"
    elif "DestinationOrganizationCode" in other_plant:
        other_plant["DestinationOrganizationCode"] = "PDX"
    elif "BusinessUnit" in other_plant:
        other_plant["BusinessUnit"] = "Northstar Portland BU"
    if "ItemNumber" in other_plant:
        other_plant["ItemNumber"] = f"{decision['item']}-PDX"
    draft = deepcopy(record)
    change_identity(draft, 900_000)
    if status_field:
        draft[status_field] = "DRAFT"
    if "ItemNumber" in draft:
        draft["ItemNumber"] = f"{decision['item']}-ALT"
    if "Description" in draft:
        draft["Description"] = f"Unapproved nearby record; not {decision['case_reference']}"
    rows = [stale, other_plant, draft]
    rows.insert(ordinal % 4, target)
    return rows


def _candidate_provider_arguments(
    critical_arguments: dict[str, Any],
    *,
    candidate_index: int,
    applicable: bool,
    ordinal: int,
) -> dict[str, Any]:
    """Build one provider setup row, including realistic inapplicable decoys."""

    candidate = deepcopy(critical_arguments)
    if applicable:
        return candidate

    def rewrite(value: Any, key: str = "") -> Any:
        if isinstance(value, dict):
            return {name: rewrite(item, name) for name, item in value.items()}
        if isinstance(value, list):
            return [rewrite(item, key) for item in value]
        if isinstance(value, int) and key.endswith("Id"):
            return value + (candidate_index + 1) * 700_000
        if isinstance(value, str):
            code_prefixes = {
                "WorkCenterCode": "WC",
                "ResourceCode": "RES",
                "substituteItemNumber": "NS-SUB",
                "Supplier": "SUPPLIER",
                "SupplierSite": "SITE",
                "InspectionPlanName": "PLAN",
                "HoldName": "HOLD",
                "ReleaseName": "RELEASE",
                "supplierOrder": "SUP-ACK",
            }
            if key in code_prefixes:
                return f"{code_prefixes[key]}-CAND-{ordinal:03d}-{candidate_index + 1}"
        return value

    return rewrite(candidate)


def _task_evidence(
    task_id: str,
    scenario: Scenario,
    ordinal: int,
    *,
    collaboration_writes: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Return source assets plus the discoverable provider setup crosswalk."""

    decision = build_decision_case(scenario, ordinal)
    primary_arguments = _arguments(scenario.primary_write, ordinal, scenario)
    critical_arguments = _provider_critical_arguments(primary_arguments)
    candidates = [
        {
            "candidateReference": f"SETUP-{ordinal:04d}-CURRENT",
            "immutableRecord": decision["record"],
            "sourceRevision": decision["revision"],
            "organizationCode": "SEA",
            "controlStatus": "ACTIVE_APPLICABLE",
            "targetAndProviderValues": _candidate_provider_arguments(
                critical_arguments,
                candidate_index=0,
                applicable=True,
                ordinal=ordinal,
            ),
        },
        {
            "candidateReference": f"SETUP-{ordinal:04d}-ARCHIVE",
            "immutableRecord": decision["record"],
            "sourceRevision": f"R{8 + ordinal % 3}",
            "organizationCode": "SEA",
            "controlStatus": "SUPERSEDED",
            "targetAndProviderValues": _candidate_provider_arguments(
                critical_arguments,
                candidate_index=1,
                applicable=False,
                ordinal=ordinal,
            ),
        },
        {
            "candidateReference": f"SETUP-{ordinal:04d}-PDX",
            "immutableRecord": f"NS-{ordinal + 1:06d}",
            "sourceRevision": decision["revision"],
            "organizationCode": "PDX",
            "controlStatus": "OTHER_ORGANIZATION",
            "targetAndProviderValues": _candidate_provider_arguments(
                critical_arguments,
                candidate_index=2,
                applicable=False,
                ordinal=ordinal,
            ),
        },
    ]
    rotation = ordinal % len(candidates)
    candidates = candidates[rotation:] + candidates[:rotation]
    assets = build_evidence(
        task_id,
        scenario,
        ordinal,
        collaboration_writes=collaboration_writes,
    )
    erp_asset = next(asset for asset in assets if asset["kind"] == "erp_export")
    erp_export = json.loads(erp_asset["content"])
    erp_export["providerSetupCrosswalk"] = {
        "source": "Oracle setup and transaction-control export",
        "providerOperation": scenario.primary_write,
        "instruction": (
            "Correlate immutable record, effective revision, organization, and "
            "control status before using provider identifiers or controlled "
            "values. This setup export does not determine the business decision, "
            "and row order does not indicate applicability."
        ),
        "candidates": candidates,
        "narrativeControl": (
            "Free-text names, descriptions, notes, and reasons may use natural "
            "wording but must remain scoped to this case or immutable record."
        ),
    }
    erp_asset["content"] = json.dumps(erp_export, indent=2, sort_keys=True) + "\n"
    erp_asset["preview"] = (
        f"Oracle starting record {decision['record']} at {decision['revision']} "
        "with option-to-provider setup controls."
    )
    return assets


def _drive_file_id(asset: dict[str, Any], ordinal: int, index: int) -> str:
    if asset["path"] == "business-request-and-control.md":
        return f"drive-{ordinal:03d}"
    if asset["path"] == "drive-approval-record.json":
        return f"drive-approval-{ordinal:03d}"
    return f"drive-{ordinal:03d}-{index:02d}"


def _drive_asset(
    assets: list[dict[str, Any]],
    ordinal: int,
    file_id: str,
) -> tuple[dict[str, Any], str]:
    for index, asset in enumerate(assets, start=1):
        candidate_id = _drive_file_id(asset, ordinal, index)
        if candidate_id == file_id:
            return asset, candidate_id
    raise ValueError(f"unknown task-scoped Drive file id {file_id}")


def _response(
    tool: str,
    ordinal: int,
    scenario: Scenario,
    arguments: dict[str, Any],
    *,
    collaboration_writes: tuple[str, ...] = (),
) -> dict[str, Any]:
    decision = build_decision_case(scenario, ordinal)
    case = decision["case_reference"]
    raw_values = decision["raw_decision_values"]
    quantity: float | int = (
        decision["transaction_measure"]
        if decision["decision_mode"] == "financial"
        and decision["transaction_unit"] != "USD"
        else (1 if decision["decision_mode"] == "financial" else raw_values["scope"])
    )
    task_id = f"factorybench-{ordinal:03d}"
    record = (
        _oracle_record(tool, ordinal, scenario, decision, quantity)
        if tool.startswith("oracle_fusion.")
        else {}
    )
    if tool == "factorybench.context.get":
        return {}
    if tool == "gmail.messages.list":
        return {
            "messages": [
                {"id": f"msg-{ordinal:03d}", "threadId": f"thread-{ordinal:03d}"},
                {"id": f"msg-{ordinal:03d}-1", "threadId": f"thread-{ordinal:03d}"},
                {"id": f"msg-{ordinal:03d}-2", "threadId": f"thread-{ordinal:03d}"},
                {"id": f"msg-{ordinal:03d}-3", "threadId": f"thread-{ordinal:03d}"},
            ],
            "resultSizeEstimate": 4,
        }
    if tool == "gmail.messages.get":
        assets = _task_evidence(
            task_id,
            scenario,
            ordinal,
            collaboration_writes=collaboration_writes,
        )
        text = next(asset["content"] for asset in assets if asset["kind"] == "email")
        encoded = base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")
        attachment_name = next(
            asset["path"]
            for asset in assets
            if asset["kind"] == "external_pdf"
        )
        return {"id": f"msg-{ordinal:03d}", "threadId": f"thread-{ordinal:03d}", "labelIds": ["INBOX"], "snippet": decision["request"][:140], "payload": {"headers": [{"name": "Subject", "value": f"{case} — operating question and external reply"}], "body": {"data": encoded, "size": len(text)}, "parts": [{"filename": attachment_name, "body": {"attachmentId": f"att-{ordinal:03d}", "size": 1024}}]}}
    if tool == "gmail.threads.get":
        assets = _task_evidence(
            task_id,
            scenario,
            ordinal,
            collaboration_writes=collaboration_writes,
        )
        text = next(
            asset["content"]
            for asset in assets
            if asset["kind"] == "email"
        )
        attachment_name = next(
            asset["path"] for asset in assets if asset["kind"] == "external_pdf"
        )
        sections = text.split("--- Earlier message:")
        messages = []
        for index, section in enumerate(sections):
            encoded = base64.urlsafe_b64encode(section.encode()).decode().rstrip("=")
            message = {
                "id": f"msg-{ordinal:03d}" if index == 0 else f"msg-{ordinal:03d}-{index}",
                "threadId": f"thread-{ordinal:03d}",
                "labelIds": ["INBOX"],
                "snippet": section[:140],
                "payload": {
                    "headers": [{"name": "Subject", "value": f"{case} — operating request and source reply"}],
                    "body": {"data": encoded, "size": len(section)},
                },
            }
            if index == 1:
                message["payload"]["parts"] = [
                    {
                        "filename": attachment_name,
                        "body": {
                            "attachmentId": f"att-{ordinal:03d}",
                            "size": 1024,
                        },
                    }
                ]
            messages.append(message)
        return {"id": f"thread-{ordinal:03d}", "historyId": str(900_000 + ordinal), "messages": messages}
    if tool == "gmail.messages.attachments.get":
        content = next(
            asset["content"]
            for asset in _task_evidence(
                task_id,
                scenario,
                ordinal,
                collaboration_writes=collaboration_writes,
            )
            if asset["kind"] == "external_pdf"
        ).encode()
        return {"size": len(content), "data": base64.urlsafe_b64encode(content).decode().rstrip("=")}
    if tool == "gmail.drafts.get":
        return {"id": f"draft-{ordinal:03d}", "message": {"id": f"draft-msg-{ordinal:03d}", "threadId": f"thread-{ordinal:03d}", "labelIds": ["DRAFT"]}}
    if tool == "gmail.drafts.create":
        return {"id": f"draft-{ordinal:03d}", "message": {"id": f"draft-msg-{ordinal:03d}", "threadId": f"thread-{ordinal:03d}", "labelIds": ["DRAFT"]}}
    if tool == "gmail.messages.send":
        return {"id": f"sent-{ordinal:03d}", "threadId": f"thread-{ordinal:03d}", "labelIds": ["SENT"]}
    if tool.startswith("google_drive.files.list"):
        files = []
        for index, asset in enumerate(
            _task_evidence(
                task_id,
                scenario,
                ordinal,
                collaboration_writes=collaboration_writes,
            ),
            start=1,
        ):
            file_id = _drive_file_id(asset, ordinal, index)
            files.append(
                {
                    "id": file_id,
                    "name": asset["path"],
                    "mimeType": asset["media_type"],
                    "modifiedTime": f"{AS_OF_DATE.isoformat()}T09:00:00Z",
                    "description": f"{case}: {asset['title']}",
                }
            )
        return {"kind": "drive#fileList", "files": files, "nextPageToken": None}
    if tool in {"google_drive.files.get", "google_drive.files.download", "google_drive.files.export"}:
        assets = _task_evidence(
            task_id,
            scenario,
            ordinal,
            collaboration_writes=collaboration_writes,
        )
        asset, file_id = _drive_asset(
            assets,
            ordinal,
            str(arguments.get("fileId", f"drive-{ordinal:03d}")),
        )
        return {
            "kind": "drive#file",
            "id": file_id,
            "name": asset["path"],
            "mimeType": asset["media_type"],
            "description": f"{case}: {asset['title']}",
            "content": asset["content"],
            "modifiedTime": f"{AS_OF_DATE.isoformat()}T09:00:00Z",
        }
    if tool == "google_drive.comments.list":
        return {"kind": "drive#commentList", "comments": [], "nextPageToken": None}
    if tool == "google_drive.comments.get":
        return {"id": f"comment-{ordinal:03d}", "content": "", "resolved": False}
    if tool == "google_drive.comments.create":
        return {"id": f"comment-{ordinal:03d}", "content": arguments["requestBody"]["content"], "resolved": False}
    if tool == "google_sheets.spreadsheets.get":
        return {
            "spreadsheetId": f"sheet-{ordinal:03d}",
            "properties": {"title": f"{case} finite-capacity and coverage workbook"},
            "namedRanges": [
                {"namedRangeId": f"control-{ordinal:03d}", "name": "EligibleCoverage"},
                {"namedRangeId": f"approval-{ordinal:03d}", "name": "DecisionApprovals"},
                {"namedRangeId": f"audit-{ordinal:03d}", "name": "DecisionAudit"},
            ],
            "developerMetadata": [
                {"metadataKey": "case", "metadataValue": case},
                {"metadataKey": "sourceRevision", "metadataValue": decision["revision"]},
            ],
            "sheets": [
                {"properties": {"sheetId": 0, "title": "Control"}},
                {"properties": {"sheetId": 1, "title": "Approvals"}},
                {"properties": {"sheetId": 2, "title": "Audit"}},
            ],
        }
    if tool in {"google_sheets.spreadsheets.values.get", "google_sheets.spreadsheets.values.batchGet"}:
        observed_parts = _partition_response_measure(raw_values["observed"], 4)
        excluded_parts = _partition_response_measure(raw_values["excluded"], 2)
        control_values = [
            ["case", "source_row", "observed", "excluded", "unit", "source_revision", "organization", "control_status", "control_note"],
            *[
                [case, f"OBS-{ordinal:04d}-{index}", part, "", decision["unit"], decision["revision"], "SEA", "OBSERVED_NOT_NETTED", decision["decision_spec"].eligible_label]
                for index, part in enumerate(observed_parts, start=1)
            ],
            *[
                [case, f"EXCL-{ordinal:04d}-{index}", "", part, decision["unit"], decision["revision"], "SEA", "EXCLUDE", decision["decision_spec"].excluded_label]
                for index, part in enumerate(excluded_parts, start=1)
            ],
            [f"CASE-{(ordinal % 100) + 1:03d}", "DISTRACTOR-CASE", max(1, int(float(raw_values["scope"]) // 3)), "", decision["unit"], decision["revision"], "SEA", "OTHER_CASE", "do not include"],
            [case, "DISTRACTOR-REVISION", max(1, int(float(raw_values["scope"]) // 4)), "", decision["unit"], f"R{8 + ordinal % 3}", "SEA", "SUPERSEDED", "do not include"],
            [case, "DISTRACTOR-PLANT", max(1, int(float(raw_values["scope"]) // 5)), "", decision["unit"], decision["revision"], "PDX", "OTHER_PLANT", "do not include"],
        ]
        approved_option = next(
            option for option in decision["options"] if option["recommended"]
        )
        approval_values = [
            ["case", "approval_id", "decision_option", "approval_status", "authorized_measure", "outcome_date", "source_revision"],
            [
                case,
                f"AP-{ordinal:04d}",
                approved_option["id"],
                "APPROVED",
                decision["transaction_measure"],
                approved_option["completion"],
                decision["revision"],
            ],
            [
                case,
                f"AP-{ordinal:04d}-EXCEPTION",
                "broader_or_exception_scope",
                "NOT_GRANTED",
                "",
                "",
                decision["revision"],
            ],
            [
                f"CASE-{(ordinal % 100) + 1:03d}",
                f"AP-{ordinal + 1:04d}",
                "unrelated_case_option",
                "APPROVED",
                raw_values["scope"],
                decision["requested_by"],
                decision["revision"],
            ],
        ]
        audit_values = [
            ["event_date", "case", "role", "decision_option", "outcome_date", "record", "approval_id"],
            [
                (AS_OF_DATE - timedelta(days=2)).isoformat(),
                f"CASE-{(ordinal % 100) + 1:03d}",
                "operations_planner",
                "unrelated_completed_decision",
                (AS_OF_DATE - timedelta(days=1)).isoformat(),
                f"NS-{ordinal + 1:06d}",
                f"AP-{ordinal + 1:04d}",
            ],
        ]

        def values_for(requested_range: str) -> list[list[Any]]:
            tab = requested_range.split("!", 1)[0].strip("'")
            return {
                "Control": control_values,
                "Approvals": approval_values,
                "Audit": audit_values,
            }.get(tab, [])

        if tool.endswith("batchGet"):
            requested_ranges = arguments.get("ranges", ["Control!A1:I50"])
            return {
                "spreadsheetId": f"sheet-{ordinal:03d}",
                "valueRanges": [
                    {
                        "range": requested_range,
                        "majorDimension": "ROWS",
                        "values": values_for(requested_range),
                    }
                    for requested_range in requested_ranges
                ],
            }
        requested_range = str(arguments.get("range", "Control!A1:I50"))
        return {
            "range": requested_range,
            "majorDimension": "ROWS",
            "values": values_for(requested_range),
        }
    if tool == "google_sheets.spreadsheets.values.update":
        return {"spreadsheetId": f"sheet-{ordinal:03d}", "updatedRange": arguments["range"], "updatedRows": 1, "updatedColumns": 1, "updatedCells": 1}
    if tool == "google_sheets.spreadsheets.values.append":
        return {"spreadsheetId": f"sheet-{ordinal:03d}", "tableRange": "Audit!A1:G20", "updates": {"updatedRange": "Audit!A21:G21", "updatedRows": 1, "updatedCells": 7}}
    if tool == "slack.search_messages":
        channel = _arguments("slack.conversations_history", ordinal, scenario)["channel"]
        thread = json.loads(
            next(
                asset["content"]
                for asset in _task_evidence(
                    task_id,
                    scenario,
                    ordinal,
                    collaboration_writes=collaboration_writes,
                )
                if asset["kind"] == "chat_thread"
            )
        )
        messages = deepcopy(thread["messages"])
        messages[2]["files"] = [
            {
                "id": f"F-{ordinal:06d}",
                "name": "approval-and-impact-note.pdf",
                "mimetype": "application/pdf",
                "title": f"{case} approval and impact note",
            }
        ]
        matches = [
            {"channel": {"id": channel}, **message}
            for message in messages
        ]
        return {"ok": True, "query": arguments["query"], "messages": {"total": len(matches), "matches": matches}}
    if tool in {"slack.conversations_history", "slack.conversations_replies"}:
        thread = json.loads(
            next(
                asset["content"]
                for asset in _task_evidence(
                    task_id,
                    scenario,
                    ordinal,
                    collaboration_writes=collaboration_writes,
                )
                if asset["kind"] == "chat_thread"
            )
        )
        messages = deepcopy(thread["messages"])
        messages[2]["files"] = [
            {
                "id": f"F-{ordinal:06d}",
                "name": "approval-and-impact-note.pdf",
                "mimetype": "application/pdf",
                "title": f"{case} approval and impact note",
            }
        ]
        return {"ok": True, "messages": messages, "has_more": False, "response_metadata": {"next_cursor": ""}}
    if tool == "slack.files_info":
        return {"ok": True, "file": {"id": f"F-{ordinal:06d}", "name": "approval-and-impact-note.pdf", "mimetype": "application/pdf", "title": f"{case} approval and impact note", "preview": source_fact_text(decision, "slack")}}
    if tool == "slack.chat_postMessage":
        return {"ok": True, "channel": arguments["channel"], "ts": f"1768{ordinal:06d}.000900", "message": {"text": arguments["text"], "thread_ts": arguments.get("thread_ts")}}
    if tool == "slack.reactions_add":
        return {"ok": True}
    if tool == "oracle_fusion.invoices.validate":
        return {"result": "The current action Validate Invoice has completed successfully."}
    if tool == "oracle_fusion.cycle_count_history.list":
        first_count = deepcopy(record)
        first_count["EntryHistoryId"] = record["EntryHistoryId"] - 1
        first_count["CountedBy"] = "Lee, Jordan"
        first_count["CountedByEmployeeId"] = 71_001
        first_count["CountDate"] = (AS_OF_DATE - timedelta(days=1)).isoformat()
        first_count["Reason"] = "Initial blind count"
        return {
            "items": [first_count, record],
            "count": 2,
            "hasMore": False,
            "limit": arguments.get("limit", 25),
            "offset": arguments.get("offset", 0),
            "links": [],
        }
    if tool.startswith("oracle_fusion.") and tool.endswith(".list"):
        candidates = _oracle_candidate_rows(tool, record, ordinal, decision)
        return {"items": candidates, "count": len(candidates), "hasMore": False, "limit": arguments.get("limit", 25), "offset": arguments.get("offset", 0), "links": []}
    if tool.startswith("oracle_fusion.") and tool in READ_TOOLS:
        return record
    if tool.startswith("oracle_fusion."):
        body = arguments.get("requestBody", {})
        response = deepcopy(record)
        for key, value in body.items():
            if not isinstance(value, (dict, list)):
                response[key] = value
        response["links"] = []
        return response
    raise ValueError(f"no response builder for {tool}")


def _systems_for(tools: list[str]) -> list[str]:
    return sorted({TOOL_BY_NAME[tool]["_meta"]["factorybench"]["server"] for tool in tools})


def _communication_requirement(writes: tuple[str, ...]) -> str:
    labels = []
    for tool in writes:
        if tool.startswith("gmail.drafts"):
            labels.append("create the requested email draft without sending it")
        elif tool.startswith("gmail.messages.send"):
            labels.append("send the scoped completion email")
        elif tool.startswith("slack.chat"):
            labels.append("reply in the existing Slack thread")
        elif tool.startswith("slack.reactions"):
            labels.append("mark the approved Slack thread complete")
        elif tool.startswith("google_sheets") and tool.endswith("update"):
            labels.append("write the outcome into the existing control-workbook cell")
        elif tool.startswith("google_sheets") and tool.endswith("append"):
            labels.append("append an audit row to the control workbook")
        elif tool.startswith("google_drive.comments"):
            labels.append("add the Oracle result as a Drive comment")
    return "; and ".join(labels)


def _investigation_description(
    tool: str,
    decision: dict[str, Any],
    arguments: dict[str, Any] | None = None,
) -> str:
    facts = {fact["id"]: fact for fact in decision["facts"]}
    if tool == "factorybench.context.get":
        return (
            f"Established the isolated {decision['case_reference']} scope, immutable handles, mounted systems, and evidence index before investigating {decision['record']}."
        )
    if tool.startswith("oracle_fusion."):
        resource = tool.removeprefix("oracle_fusion.").rsplit(".", 1)[0].replace("_", " ")
        return f"Correlated the Oracle {resource} record: {fact_for_oracle_tool(decision, tool)['rubric']}"
    if tool == "gmail.messages.list":
        return (
            f"Located the task-scoped correspondence for {decision['case_reference']} before opening any message; did not rely on a filename or a guessed sender."
        )
    if tool == "gmail.messages.attachments.get":
        return (
            f"Opened the external attachment from the matched email and {facts['conditional_external_recovery']['rubric']}"
        )
    if tool in {"gmail.messages.get", "gmail.threads.get"}:
        return facts["conditional_external_recovery"]["rubric"]
    if tool == "google_drive.files.list":
        return (
            f"Enumerated the case-scoped Drive records for {decision['case_reference']} and used their immutable file IDs to distinguish the effective specification, approval, and option workbook."
        )
    if tool.startswith("google_drive."):
        file_id = str((arguments or {}).get("fileId", ""))
        if file_id.startswith("drive-approval-"):
            return (
                f"Opened the task-scoped signed approval record and {facts['approval_scope']['rubric']}"
            )
        if file_id.endswith("-03"):
            return f"Opened the task-scoped external source document and {facts['conditional_external_recovery']['rubric']}"
        if file_id.endswith("-04"):
            return f"Opened the task-scoped source-input workbook and {facts['effective_requirement']['rubric']}"
        if file_id.endswith("-09"):
            return (
                "Opened the Oracle starting-record and setup crosswalk, matched "
                f"the independently supported option to its provider identifiers, and preserved {decision['record']} at {decision['revision']}."
            )
        if file_id.endswith("-10"):
            return f"Opened the independent reconciliation rows and {facts['eligible_coverage']['rubric']}"
        if file_id.endswith("-11"):
            return f"Opened the raw operating-window calendar and {facts['finite_capacity']['rubric']}"
        if file_id.endswith("-12"):
            return f"Opened the effective control specification and {facts['effective_requirement']['rubric']}"
        return facts["effective_requirement"]["rubric"]
    if tool == "google_sheets.spreadsheets.get":
        return (
            f"Confirmed the case, effective source revision, and actual Control, Approvals, and Audit tabs in the workbook metadata before relying on its cells."
        )
    if tool in {
        "google_sheets.spreadsheets.values.get",
        "google_sheets.spreadsheets.values.batchGet",
    }:
        return f"{facts['eligible_coverage']['rubric']} {facts['finite_capacity']['rubric']}"
    if tool == "slack.search_messages":
        return (
            f"Located the existing operations thread for {decision['case_reference']} and its immutable channel and thread timestamp before using the discussion."
        )
    if tool in {"slack.conversations_history", "slack.conversations_replies"}:
        return (
            f"Read the scoped operations discussion, confirmed the independently stated stakeholder need date, and separated operational context from formal approval: {facts['approval_scope']['rubric']}"
        )
    if tool == "slack.files_info":
        return (
            f"Inspected the attachment linked from the scoped Slack discussion and correlated its case and source revision before using its control evidence."
        )
    raise ValueError(f"no investigation description for {tool}")


def _investigation_result_fragment(
    tool: str,
    ordinal: int,
    scenario: Scenario,
    arguments: dict[str, Any],
    *,
    after_primary_mutation: bool = False,
) -> dict[str, Any]:
    """Identify the task evidence returned by one valid source operation.

    Filters and pagination choices are intentionally not part of the rubric.
    The trace must instead show that the operation actually returned the
    task-scoped record, file, thread, workbook, or attachment.  This prevents
    one repeated broad call from satisfying several different discoveries
    while still allowing an agent to investigate with its own query shape.
    """

    case = f"CASE-{ordinal:03d}"
    if tool == "factorybench.context.get":
        return {"reference_records": {"case_reference": case}}
    if tool.startswith("oracle_fusion."):
        decision = build_decision_case(scenario, ordinal)
        quantity: float | int = (
            decision["transaction_measure"]
            if decision["decision_mode"] == "financial"
            and decision["transaction_unit"] != "USD"
            else (
                1
                if decision["decision_mode"] == "financial"
                else decision["raw_decision_values"]["scope"]
            )
        )
        target = _oracle_record(tool, ordinal, scenario, decision, quantity)
        creates_this_resource = (
            not after_primary_mutation
            and _materializes_new_provider_record(scenario.primary_write)
            and tool.rsplit(".", 1)[0]
            == _post_write_read_tool(scenario.primary_write, scenario).rsplit(".", 1)[0]
        )
        if creates_this_resource:
            # Before a create, the collection search must establish that the
            # future target does not already exist.  Score an actually returned
            # nearby record from that duplicate/overlap search, never the
            # not-yet-materialized target identity.
            target_identity = _oracle_identity(target)
            distractor = next(
                row
                for row in _oracle_candidate_rows(
                    tool,
                    target,
                    ordinal,
                    decision,
                )
                if not all(
                    row.get(key) == value
                    for key, value in target_identity.items()
                )
            )
            return _oracle_identity(distractor)
        return _oracle_identity(target)
    if tool == "gmail.messages.list":
        return {"messages": [{"id": f"msg-{ordinal:03d}"}]}
    if tool == "gmail.messages.get":
        return {"id": f"msg-{ordinal:03d}", "threadId": f"thread-{ordinal:03d}"}
    if tool == "gmail.threads.get":
        return {"id": f"thread-{ordinal:03d}"}
    if tool == "gmail.messages.attachments.get":
        response = _response(
            tool,
            ordinal,
            scenario,
            arguments,
        )
        return {"size": response["size"], "data": response["data"]}
    if tool == "google_drive.files.list":
        return {
            "files": [
                {"id": f"drive-{ordinal:03d}"},
                {"id": f"drive-approval-{ordinal:03d}"},
            ]
        }
    if tool in {
        "google_drive.files.get",
        "google_drive.files.download",
        "google_drive.files.export",
    }:
        return {"id": arguments["fileId"]}
    if tool == "google_sheets.spreadsheets.get":
        return {
            "spreadsheetId": f"sheet-{ordinal:03d}",
            "developerMetadata": [
                {"metadataKey": "case", "metadataValue": case}
            ],
        }
    if tool in {
        "google_sheets.spreadsheets.values.get",
        "google_sheets.spreadsheets.values.batchGet",
    }:
        return {"values": [[case]]}
    if tool == "slack.search_messages":
        return {
            "messages": {
                "matches": [{"ts": f"1768{ordinal:06d}.000100"}]
            }
        }
    if tool in {"slack.conversations_history", "slack.conversations_replies"}:
        return {"messages": [{"ts": f"1768{ordinal:06d}.000100"}]}
    if tool == "slack.files_info":
        return {"file": {"id": f"F-{ordinal:06d}"}}
    raise ValueError(f"no investigation result fragment for {tool}")


def _investigation_alternatives(
    tool: str,
    ordinal: int,
    scenario: Scenario,
    arguments: dict[str, Any] | None = None,
    *,
    after_primary_mutation: bool = False,
) -> list[dict[str, Any]]:
    """Return equivalent source operations for one business discovery.

    The benchmark grades the source record or evidence class that was
    investigated, not one preferred list/get spelling or exact filter shape.
    Oracle alternatives stay on the same REST resource so separate table
    correlations cannot collapse into a single broad read.
    """

    if tool == "factorybench.context.get":
        names = [tool]
    elif tool.startswith("oracle_fusion."):
        resource = tool.rsplit(".", 1)[0]
        names = sorted(name for name in READ_TOOLS if name.rsplit(".", 1)[0] == resource)
        if (
            not after_primary_mutation
            and _materializes_new_provider_record(scenario.primary_write)
            and resource
            == _post_write_read_tool(scenario.primary_write, scenario).rsplit(".", 1)[0]
        ):
            names = [name for name in names if name.endswith(".list")]
    elif tool == "gmail.messages.list":
        names = [tool]
    elif tool in {"gmail.messages.get", "gmail.threads.get"}:
        names = sorted(
            name
            for name in READ_TOOLS
            if name in {
                "gmail.messages.get",
                "gmail.threads.get",
            }
        )
    elif tool == "gmail.messages.attachments.get":
        names = [tool]
    elif tool == "google_drive.files.list":
        names = [tool]
    elif tool.startswith("google_drive."):
        names = sorted(
            name
            for name in READ_TOOLS
            if name in {
                "google_drive.files.get",
                "google_drive.files.download",
                "google_drive.files.export",
            }
        )
    elif tool == "google_sheets.spreadsheets.get":
        names = [tool]
    elif tool in {
        "google_sheets.spreadsheets.values.get",
        "google_sheets.spreadsheets.values.batchGet",
    }:
        names = sorted(
            name
            for name in READ_TOOLS
            if name
            in {
                "google_sheets.spreadsheets.values.get",
                "google_sheets.spreadsheets.values.batchGet",
            }
        )
    elif tool == "slack.search_messages":
        names = [tool]
    elif tool in {"slack.conversations_history", "slack.conversations_replies"}:
        names = sorted(
            name
            for name in READ_TOOLS
            if name in {"slack.conversations_history", "slack.conversations_replies"}
        )
    elif tool == "slack.files_info":
        names = [tool]
    else:
        names = [tool]
    alternatives = []
    for name in names:
        alternative_arguments = _arguments(name, ordinal, scenario)
        if tool.startswith("google_drive.files.") and arguments and "fileId" in arguments:
            alternative_arguments["fileId"] = arguments["fileId"]
        alternatives.append(
            {
                "tool": name,
                "arguments": alternative_arguments,
                "match": "result_contains",
                "expected_result_contains": _investigation_result_fragment(
                    name,
                    ordinal,
                    scenario,
                    alternative_arguments,
                    after_primary_mutation=after_primary_mutation,
                ),
            }
        )
    return alternatives


def _key_investigation_slot(call: dict[str, Any]) -> tuple[str, str] | None:
    """Map one reference read to a material business discovery, if it is key.

    The reference trajectory deliberately traverses a broad enterprise evidence
    room.  The verifier should not turn every surrounding or corroborative file
    into a mandatory click.  This selector retains the records a human must
    actually join to establish identity, operative requirements, constraints,
    authority, and the relevant ERP state.
    """

    tool = str(call["tool"])
    arguments = call.get("arguments") or {}
    if tool == "factorybench.context.get":
        return "scope.context", "investigation.scope"
    if tool == "gmail.messages.list":
        return "scope.email_index", "investigation.scope"
    if tool in {"gmail.messages.get", "gmail.threads.get"}:
        return "requirements.email_content", "investigation.requirements"
    if tool == "gmail.messages.attachments.get":
        return "requirements.email_attachment", "investigation.requirements"
    if tool == "google_drive.files.list":
        return "scope.drive_index", "investigation.scope"
    if tool.startswith("google_drive.files."):
        file_id = str(arguments.get("fileId") or "")
        if file_id.startswith("drive-approval-"):
            return "authority.approval", "investigation.authority"
        suffix_to_slot = {
            "-04": ("requirements.source_workbook", "investigation.requirements"),
            "-10": ("constraints.reconciliation", "investigation.constraints"),
            "-11": ("constraints.calendar", "investigation.constraints"),
            "-12": ("requirements.control_spec", "investigation.requirements"),
        }
        for suffix, mapped in suffix_to_slot.items():
            if file_id.endswith(suffix):
                return mapped
        return None
    if tool.startswith("google_sheets.spreadsheets"):
        return "constraints.control_workbook", "investigation.constraints"
    if tool.startswith("slack.") and tool in {
        "slack.search_messages",
        "slack.conversations_history",
        "slack.conversations_replies",
        "slack.files_info",
    }:
        return "authority.operations_thread", "investigation.authority"
    if tool.startswith("oracle_fusion."):
        resource = tool.rsplit(".", 1)[0]
        return f"erp.{resource}", "investigation.erp_correlation"
    return None


def _select_key_read_calls(calls: list[dict[str, Any]]) -> list[tuple[dict[str, Any], str]]:
    selected: list[tuple[dict[str, Any], str]] = []
    observed_slots: set[str] = set()
    for call in calls:
        mapped = _key_investigation_slot(call)
        if mapped is None:
            continue
        slot, milestone_id = mapped
        if slot in observed_slots:
            continue
        observed_slots.add(slot)
        selected.append((call, milestone_id))
    return selected


def _calculation_milestone_id(criterion: dict[str, Any]) -> str:
    field = str(criterion.get("field") or criterion.get("id") or "").casefold()
    if any(token in field for token in ("option", "cost", "approval", "escalation")):
        return "decision.options"
    if any(
        token in field
        for token in (
            "date",
            "due",
            "window",
            "horizon",
            "outcome",
            "timing",
            "variance",
        )
    ):
        return "analysis.timeline"
    return "analysis.inputs"


def _rubric_milestones(
    *,
    scenario: Scenario,
    decision: dict[str, Any],
    investigations: list[dict[str, Any]],
    calculations: list[dict[str, Any]],
    assertions: list[dict[str, Any]],
    answer_checks: list[dict[str, Any]],
    post_write_verifications: list[dict[str, Any]],
    collaboration_writes: tuple[str, ...],
) -> list[dict[str, Any]]:
    facts = {fact["id"]: fact for fact in decision["facts"]}
    oracle_resources = sorted(
        {
            alternative["tool"].removeprefix("oracle_fusion.").rsplit(".", 1)[0].replace("_", " ")
            for investigation in investigations
            if investigation["milestone_id"] == "investigation.erp_correlation"
            for alternative in investigation["any_of"][:1]
        }
    )
    descriptions = {
        "investigation.scope": (
            f"Establish the isolated {decision['case_reference']} scope and immutable identities across the mailbox, Drive index, and mounted systems before relying on similarly named records."
        ),
        "investigation.requirements": (
            f"Determine the operative {decision['revision']} requirement for {decision['record']}, reconcile the current source material, and distinguish current evidence from superseded or merely contextual records."
        ),
        "investigation.constraints": (
            f"Reconcile the supported operating inputs: {facts['eligible_coverage']['rubric']} {facts['finite_capacity']['rubric']}"
        ),
        "investigation.authority": (
            f"Establish what is actually authorized and what remains conditional: {facts['approval_scope']['rubric']}"
        ),
        "investigation.erp_correlation": (
            f"Correlate {decision['record']} by immutable IDs across the material Oracle records ({', '.join(oracle_resources)}) and preserve the effective {decision['revision']} state."
        ),
        "analysis.inputs": (
            f"Derive the eligible scope, exclusions, unit, and controlling threshold from the joined evidence rather than copying a headline quantity for {decision['record_noun']}."
        ),
        "analysis.timeline": (
            f"Calculate the feasible timing for {decision['selected_option']} under the actual operating window and report whether the {decision['selected_completion']} outcome meets the control date."
        ),
        "decision.options": (
            f"Compare all three task-specific alternatives, including timing, cost or exposure, authority, and residual risk; select {decision['selected_option']} only because the joined evidence supports it."
        ),
        "state.primary": (
            f"Persist exactly the supported {scenario.result_status!r} transition for {decision['record']} through the documented Oracle operation, with no neighboring record or unsupported field changed."
        ),
        "state.collaboration": (
            f"After the Oracle outcome is known, {_communication_requirement(collaboration_writes)} with the supported decision, timing, constraint, and business reference."
        ),
        "verification.readback": (
            f"Read {decision['record']} back after the primary mutation and verify the persisted provider state rather than trusting the write acknowledgement."
        ),
        "answer.insights": (
            f"Return the exact task-supported recommendation, outcome date, immutable business record, decisive operating insight, and timing status for {decision['record_noun']}."
        ),
        "containment.scope": (
            f"Keep all successful changes inside {decision['case_reference']}'s declared Oracle, collaboration, answer, and audit scope."
        ),
        "execution.mutations": (
            "Complete without a rejected state-changing call; failed exploratory reads may be recovered from, but an invalid mutation is not accepted."
        ),
    }
    categories = {
        "investigation.scope": "investigation",
        "investigation.requirements": "investigation",
        "investigation.constraints": "investigation",
        "investigation.authority": "investigation",
        "investigation.erp_correlation": "investigation",
        "analysis.inputs": "analysis",
        "analysis.timeline": "analysis",
        "decision.options": "decision",
        "state.primary": "state",
        "state.collaboration": "state",
        "verification.readback": "verification",
        "answer.insights": "answer",
        "containment.scope": "containment",
        "execution.mutations": "execution",
    }
    semantic_weights = {
        "investigation.scope": 4.0,
        "investigation.requirements": 6.0,
        "investigation.constraints": 8.0,
        "investigation.authority": 6.0,
        "investigation.erp_correlation": 10.0,
        "analysis.inputs": 8.0,
        "analysis.timeline": 8.0,
        "decision.options": 8.0,
        "state.primary": 14.0,
        "state.collaboration": 6.0,
        "verification.readback": 6.0,
        "answer.insights": 10.0,
        "containment.scope": 4.0,
        "execution.mutations": 2.0,
    }
    atomic = [
        *investigations,
        *calculations,
        *assertions,
        *post_write_verifications,
        *answer_checks,
        {
            "id": "write_scope",
            "weight": 1.0,
            "milestone_id": "containment.scope",
        },
        {
            "id": "no_rejected_mutation",
            "weight": 1.0,
            "milestone_id": "execution.mutations",
        },
    ]
    by_milestone: dict[str, list[dict[str, Any]]] = {}
    for criterion in atomic:
        by_milestone.setdefault(str(criterion["milestone_id"]), []).append(criterion)
    missing_descriptions = sorted(set(by_milestone) - set(descriptions))
    if missing_descriptions:
        raise ValueError(f"missing semantic milestone descriptions: {missing_descriptions}")
    missing_weights = sorted(set(by_milestone) - set(semantic_weights))
    if missing_weights:
        raise ValueError(f"missing semantic milestone weights: {missing_weights}")
    if set(by_milestone) != set(semantic_weights):
        absent = sorted(set(semantic_weights) - set(by_milestone))
        raise ValueError(f"task omitted required semantic milestones: {absent}")
    if sum(semantic_weights.values()) != 100.0:
        raise ValueError("semantic milestone weights must total 100")
    return [
        {
            "id": milestone_id,
            "category": categories[milestone_id],
            "description": descriptions[milestone_id],
            "weight": semantic_weights[milestone_id],
            "atomic_weight": round(
                sum(float(criterion.get("weight", 1.0)) for criterion in criteria),
                2,
            ),
            "criterion_ids": [str(criterion["id"]) for criterion in criteria],
        }
        for milestone_id in semantic_weights
        for criteria in (by_milestone[milestone_id],)
    ]


def _provider_argument_summary(arguments: dict[str, Any]) -> str:
    leaves: list[tuple[str, Any]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else key)
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
            return
        leaves.append((path, value))

    walk(arguments, "")
    return ", ".join(f"{path}={value!r}" for path, value in leaves)


def _primary_semantic_payload_groups(
    arguments: dict[str, Any],
    decision: dict[str, Any],
) -> list[list[str]]:
    """Return deterministic meaning checks for human-authored provider prose."""

    # Most Oracle narrative attributes (for example OperationName or Description)
    # are optional context, not a second identifier surface.  Requiring an
    # internal case token in those fields turns a natural provider update into a
    # hidden string-copying exercise.  Document attachment mutations are the one
    # place where the human-authored name is itself the business control: it must
    # identify the approved, revision-scoped evidence being linked.
    request_body = arguments.get("requestBody")
    if not isinstance(request_body, dict) or not {
        "DocumentName",
        "DocumentType",
    }.issubset(request_body):
        return []

    semantic_values: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in _SEMANTIC_PROVIDER_FIELDS:
                    semantic_values.append(str(item))
                else:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(arguments)
    if not semantic_values:
        return []
    gold_text = " ".join(semantic_values).casefold()
    candidate_groups = (
        [decision["case_reference"], decision["record"]],
        [
            decision["selected_option"],
            decision["selected_completion"],
            decision["revision"],
            f"AP-{int(decision['case_reference'].split('-')[1]):04d}",
        ],
    )
    return [
        group
        for group in candidate_groups
        if any(str(fragment).casefold() in gold_text for fragment in group)
    ]


_CONTENT_BEARING_WRITE_TOOLS = frozenset(
    {
        "gmail.drafts.create",
        "gmail.messages.send",
        "google_drive.comments.create",
        "google_sheets.spreadsheets.values.append",
        "google_sheets.spreadsheets.values.update",
        "slack.chat_postMessage",
    }
)


def _mutation_scope_arguments(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Keep provider target fields while allowing natural-language write content."""

    if tool == "gmail.drafts.create":
        return {
            "userId": arguments["userId"],
            "message": {"threadId": arguments["message"]["threadId"]},
        }
    if tool == "gmail.messages.send":
        return {
            "userId": arguments["userId"],
            "threadId": arguments["threadId"],
        }
    if tool == "google_drive.comments.create":
        return {"fileId": arguments["fileId"]}
    if tool.startswith("google_sheets.spreadsheets.values."):
        return {
            "spreadsheetId": arguments["spreadsheetId"],
            "range": arguments["range"],
        }
    if tool == "slack.chat_postMessage":
        return {
            "channel": arguments["channel"],
            "thread_ts": arguments["thread_ts"],
        }
    return deepcopy(arguments)


def _collaboration_post_write_verification(
    write_tool: str,
    ordinal: int,
    scenario: Scenario,
    *,
    index: int,
) -> dict[str, Any]:
    """Describe the provider read that must reopen one collaboration write.

    Projection paths are evaluated against the arguments the agent actually
    wrote. This proves persistence without exact-string-grading oracle prose.
    """

    write_arguments = _arguments(write_tool, ordinal, scenario)
    if write_tool == "gmail.drafts.create":
        read_tool = "gmail.drafts.get"
        read_arguments = {
            "userId": "me",
            "id": f"draft-{ordinal:03d}",
            "format": "full",
        }
        expected = {
            "id": f"draft-{ordinal:03d}",
            "message": {
                "id": f"draft-msg-{ordinal:03d}",
                "threadId": write_arguments["message"]["threadId"],
            },
        }
        projection_paths = ["message.raw"]
    elif write_tool == "gmail.messages.send":
        read_tool = "gmail.messages.get"
        read_arguments = {
            "userId": "me",
            "id": f"sent-{ordinal:03d}",
            "format": "full",
        }
        expected = {
            "id": f"sent-{ordinal:03d}",
            "threadId": write_arguments["threadId"],
        }
        projection_paths = ["raw"]
    elif write_tool == "google_drive.comments.create":
        read_tool = "google_drive.comments.get"
        read_arguments = {
            "fileId": write_arguments["fileId"],
            "commentId": f"comment-{ordinal:03d}",
            "fields": "id,content,resolved,createdTime",
        }
        expected = {"id": f"comment-{ordinal:03d}", "resolved": False}
        projection_paths = ["requestBody.content"]
    elif write_tool.startswith("google_sheets.spreadsheets.values."):
        read_tool = "google_sheets.spreadsheets.values.get"
        read_arguments = {
            "spreadsheetId": write_arguments["spreadsheetId"],
            "range": write_arguments["range"],
            "majorDimension": "ROWS",
            "valueRenderOption": "UNFORMATTED_VALUE",
        }
        expected = {
            "range": write_arguments["range"],
            "majorDimension": write_arguments["requestBody"].get(
                "majorDimension", "ROWS"
            ),
        }
        projection_paths = ["requestBody.values"]
    elif write_tool == "slack.chat_postMessage":
        read_tool = "slack.conversations_replies"
        read_arguments = {
            "channel": write_arguments["channel"],
            "ts": write_arguments["thread_ts"],
            "limit": 100,
        }
        expected = {"ok": True}
        projection_paths = ["text"]
    elif write_tool == "slack.reactions_add":
        read_tool = "slack.conversations_replies"
        read_arguments = {
            "channel": write_arguments["channel"],
            "ts": write_arguments["timestamp"],
            "limit": 100,
        }
        expected = {"ok": True}
        projection_paths = ["name"]
    else:  # pragma: no cover - every evidence pattern is enumerated above.
        raise ValueError(f"no collaboration readback contract for {write_tool}")

    return {
        "id": f"verify_collaboration_{index:02d}",
        "milestone_id": "verification.readback",
        "description": (
            f"Reopened the task-scoped {write_tool} result through {read_tool} "
            "and confirmed the agent's actual written value persisted instead "
            "of trusting the mutation acknowledgement."
        ),
        "weight": 1.0,
        "after_tool": write_tool,
        "any_of": [
            {
                "tool": read_tool,
                "arguments": read_arguments,
                "expected_result_contains": expected,
                "match": "result_contains",
            }
        ],
        "expected_result_contains": expected,
        "write_argument_projection_paths": projection_paths,
        "materializes_new_record": True,
    }


def _mutation_description(
    tool: str,
    scenario: Scenario,
    decision: dict[str, Any],
    arguments: dict[str, Any],
    *,
    primary: bool,
) -> str:
    if primary:
        critical_arguments = _provider_critical_arguments(arguments)
        semantic_note = (
            " Human-authored names, descriptions, notes, and reasons are accepted "
            "when they preserve the task-scoped business meaning."
            if _has_semantic_provider_fields(arguments)
            else ""
        )
        return (
            f"Required immutable record {decision['record']} to reach business outcome {scenario.result_status!r} through {tool} with exact provider-critical values {_provider_argument_summary(critical_arguments)}.{semantic_note} The audited transition binds selected option {decision['selected_option']}, revision {decision['revision']}, approval AP-{int(decision['case_reference'].split('-')[1]):04d}, and constraint {decision['binding_constraint']}; no other provider record satisfies this state criterion."
        )
    if tool.startswith("gmail.messages.send"):
        return (
            f"Sent {decision['stakeholder']} the scoped outcome for {decision['case_reference']}, including completion {decision['selected_completion']}, the binding constraint, alternatives, and the Oracle business reference."
        )
    if tool.startswith("gmail.drafts"):
        return (
            f"Created—but did not send—the requested {decision['case_reference']} decision draft with completion, constraint, alternatives, and the Oracle business reference."
        )
    if tool.startswith("slack.chat"):
        return (
            f"Replied in the existing operations thread with {decision['selected_option']}, completion {decision['selected_completion']}, the constraint, alternatives, and Oracle result."
        )
    if tool.startswith("slack.reactions"):
        return (
            f"Marked the existing {decision['case_reference']} approval thread complete only after the Oracle decision was persisted."
        )
    if tool.startswith("google_sheets") and tool.endswith("update"):
        return (
            f"Wrote {decision['selected_option']}, completion {decision['selected_completion']}, and the binding constraint into the existing task-scoped control cell without altering another row."
        )
    if tool.startswith("google_sheets") and tool.endswith("append"):
        return (
            f"Appended one audit row for {decision['case_reference']} with the selected option, completion, role, and AP-{int(decision['case_reference'].split('-')[1]):04d}."
        )
    if tool.startswith("google_drive.comments"):
        return (
            f"Added the Oracle result to the existing case file as a comment containing {decision['selected_option']}, completion {decision['selected_completion']}, and the binding constraint."
        )
    return f"Persisted the scoped {decision['case_reference']} collaboration outcome."


def _build_task(ordinal: int, scenario: Scenario) -> dict[str, Any]:
    task_id = f"factorybench-{ordinal:03d}"
    decision = build_decision_case(scenario, ordinal)
    family_index = FAMILIES.index(scenario.family)
    pattern_index = ((ordinal - 1) + ((ordinal - 1) // 10) * 3) % len(EVIDENCE_PATTERNS)
    pattern = EVIDENCE_PATTERNS[pattern_index]
    pattern_reads = list(pattern["reads"])
    rotation = (((ordinal - 1) // 10) + family_index) % len(pattern_reads)
    pattern_reads = pattern_reads[rotation:] + pattern_reads[:rotation]
    if ((ordinal - 1) // 5 + family_index) % 2:
        pattern_reads.reverse()
    pattern_writes = list(pattern["writes"])
    if ((ordinal - 1) // 10 + family_index) % 2:
        pattern_writes.reverse()
    read_names = pattern_reads
    oracle_reads = list(decision["oracle_reads"])
    oracle_rotation = (ordinal - 1) % len(oracle_reads)
    oracle_reads = oracle_reads[oracle_rotation:] + oracle_reads[:oracle_rotation]
    if ordinal % 2 == 0:
        oracle_reads.reverse()
    for tool in oracle_reads:
        if tool.startswith("oracle_fusion."):
            resource = tool.rsplit(".", 1)[0]
            if any(
                existing.startswith("oracle_fusion.")
                and existing.rsplit(".", 1)[0] == resource
                for existing in read_names
            ):
                continue
        elif tool in read_names:
            continue
        read_names.append(tool)
    answer = deepcopy(decision["answer"])
    answer_schema = _answer_schema(answer, decision["answer_descriptions"])
    answer_schema["properties"]["recommended_option"]["enum"] = [
        option["id"] for option in decision["options"]
    ]
    answer_schema["properties"]["decision_timing_status"]["enum"] = [
        "ON_TIME",
        "LATE",
    ]
    post_write_read = _post_write_read_tool(scenario.primary_write, scenario)
    post_write_read_arguments = _arguments(post_write_read, ordinal, scenario)
    read_specs: list[dict[str, Any]] = []
    for tool in read_names:
        read_specs.append({"tool": tool, "arguments": _arguments(tool, ordinal, scenario)})
        if tool == "google_drive.files.list":
            read_specs.extend(_required_asset_read_calls(ordinal, scenario, decision))
    # A real planner does not stop after opening the minimum set of decisive
    # records. Corroborate the case through additional populated provider
    # surfaces. These task-scoped reads become part of the executed oracle
    # investigation, not decorative release metadata.
    preferred_corroboration = (
        "gmail.messages.list",
        "gmail.messages.get",
        "gmail.threads.get",
        "slack.search_messages",
        "slack.conversations_history",
        "slack.conversations_replies",
        "google_sheets.spreadsheets.get",
        "google_sheets.spreadsheets.values.batchGet",
        "google_sheets.spreadsheets.values.get",
        "google_drive.files.list",
        "google_drive.files.get",
        "google_drive.files.download",
        "google_drive.files.export",
    )
    observed_reference_selectors = {
        (spec["tool"], _canonical(spec["arguments"])) for spec in read_specs
    }
    for tool in preferred_corroboration:
        if 1 + len(read_specs) >= MINIMUM_PROVIDER_READ_CALLS:
            break
        arguments = _arguments(tool, ordinal, scenario)
        selector = (tool, _canonical(arguments))
        if selector in observed_reference_selectors:
            continue
        read_specs.append({"tool": tool, "arguments": arguments})
        observed_reference_selectors.add(selector)
    if 1 + len(read_specs) < MINIMUM_PROVIDER_READ_CALLS:
        raise ValueError(
            f"{task_id} has only {1 + len(read_specs)} provider reads; "
            f"expected at least {MINIMUM_PROVIDER_READ_CALLS}"
        )
    collaboration_verifications = [
        _collaboration_post_write_verification(
            tool,
            ordinal,
            scenario,
            index=index,
        )
        for index, tool in enumerate(pattern_writes, start=1)
    ]
    collaboration_steps: list[dict[str, Any]] = []
    for tool, verification in zip(
        pattern_writes, collaboration_verifications, strict=True
    ):
        collaboration_steps.extend(
            [
                {
                    "tool": tool,
                    "arguments": _arguments(tool, ordinal, scenario),
                    "phase": "collaboration_mutation",
                },
                {
                    "tool": verification["any_of"][0]["tool"],
                    "arguments": deepcopy(
                        verification["any_of"][0]["arguments"]
                    ),
                    "phase": "post_write_verification",
                },
            ]
        )
    step_specs = [
        {"tool": "factorybench.context.get", "arguments": {}, "phase": "investigation"},
        *read_specs,
        {
            "tool": scenario.primary_write,
            "arguments": _arguments(scenario.primary_write, ordinal, scenario),
            "phase": "primary_mutation",
        },
        {
            "tool": post_write_read,
            "arguments": post_write_read_arguments,
            "phase": "post_write_verification",
        },
        *collaboration_steps,
        {"tool": "factorybench.submit_answer", "arguments": deepcopy(answer), "phase": "answer"},
    ]
    tool_names = [step["tool"] for step in step_specs]
    steps: list[dict[str, Any]] = []
    fixture_rows: list[dict[str, Any]] = []
    assertions: list[dict[str, Any]] = []
    write_number = 0
    for step_index, step_spec in enumerate(step_specs):
        tool = step_spec["tool"]
        arguments = deepcopy(step_spec["arguments"])
        read_only = tool in READ_TOOLS
        phase = step_spec.get("phase", "investigation")
        step = {
            "tool": tool,
            "arguments": arguments,
            "control": read_only and phase == "investigation",
            "phase": phase,
        }
        steps.append(step)
        if tool in {"factorybench.context.get", "factorybench.submit_answer"}:
            continue
        response = _response(
            tool,
            ordinal,
            scenario,
            arguments,
            collaboration_writes=tuple(pattern_writes),
        )
        effect: dict[str, Any] | None = None
        if tool in WRITE_TOOLS:
            write_number += 1
            server = TOOL_BY_NAME[tool]["_meta"]["factorybench"]["server"]
            resource_id = f"{task_id}-mutation-{write_number:02d}"
            primary = tool == scenario.primary_write
            status = scenario.result_status if primary else "Recorded"
            effect = {
                "task_id": task_id,
                "system": server,
                "resource_type": tool.rsplit(".", 1)[0],
                "resource_id": resource_id,
                "status": status,
                "effective_at": decision["selected_completion"],
                "payload_json": _canonical(
                    {
                        "tool": tool,
                        "arguments": arguments,
                    }
                ),
                "revision": 1,
            }
            assertion_values = {
                "system": server,
                "resource_type": effect["resource_type"],
                "status": status,
                "revision": 1,
            }
            assertion = {
                "id": f"mutation_{write_number:02d}",
                "milestone_id": "state.primary" if primary else "state.collaboration",
                "description": _mutation_description(
                    tool,
                    scenario,
                    decision,
                    arguments,
                    primary=primary,
                ),
                "weight": 3.0 if primary else 1.5,
                "table": "resource_state",
                "where": {"task_id": task_id, "resource_id": resource_id},
                "values": assertion_values,
                "payload_contains": {
                    "tool": tool,
                    "arguments": (
                        _provider_critical_arguments(arguments)
                        if primary
                        else arguments
                        if tool not in _CONTENT_BEARING_WRITE_TOOLS
                        or tool.startswith("google_sheets.spreadsheets.values.")
                        else _mutation_scope_arguments(tool, arguments)
                    ),
                },
            }
            if primary:
                assertion["payload_allowed_argument_paths"] = sorted(
                    _provider_argument_paths(arguments)
                )
                semantic_groups = _primary_semantic_payload_groups(
                    arguments,
                    decision,
                )
                if semantic_groups:
                    assertion["payload_text_any_of"] = semantic_groups
            if tool in _CONTENT_BEARING_WRITE_TOOLS:
                assertion["payload_text_contains"] = [
                    decision["selected_completion"],
                    decision["selected_option"],
                ]
                if not tool.startswith("google_sheets.spreadsheets.values."):
                    assertion["payload_text_any_of"] = [
                        [
                            decision["case_reference"],
                            decision["record"],
                            decision["item"],
                        ]
                    ]
                if tool.startswith("gmail."):
                    stakeholder_mailbox = (
                        f"{decision['stakeholder'].replace(' ', '.')}@northstar.example"
                    )
                    assertion["payload_text_contains"].append(stakeholder_mailbox)
                    assertion["payload_email_to"] = stakeholder_mailbox
                if tool in {
                    "gmail.drafts.create",
                    "gmail.messages.send",
                    "google_drive.comments.create",
                    "slack.chat_postMessage",
                }:
                    assertion["payload_narrative"] = {
                        "minimum_words": 30,
                        "minimum_punctuation": 2,
                        "reject_serialized": True,
                    }
            assertions.append(assertion)
        fixture_key = (tool, _canonical(arguments))
        if any(
            (row["tool_name"], row["arguments_json"]) == fixture_key
            for row in fixture_rows
        ):
            continue
        fixture_rows.append(
            {
                "fixture_id": f"{task_id}-call-{step_index:02d}",
                "task_id": task_id,
                "tool_name": tool,
                "arguments_json": _canonical(arguments),
                "response_json": _canonical(response),
                "effect_json": _canonical(effect) if effect else None,
                "read_only": 1 if read_only else 0,
            }
        )

    # Collaboration systems expose their full task-scoped read surface. Oracle
    # exposes only resources genuinely linked to this case, with list/get
    # variants on the same REST resource. An exploratory call to an unrelated
    # Oracle table therefore has no case rows instead of fabricating a matching
    # invoice, maintenance program, or receipt for every task. The runtime
    # returns an ordinary empty collection for exploratory list calls.
    seeded_tools = {row["tool_name"] for row in fixture_rows}
    relevant_oracle_resources = {
        tool.rsplit(".", 1)[0]
        for tool in (
            *decision["oracle_reads"],
            post_write_read,
        )
        if tool.startswith("oracle_fusion.")
    }
    optional_reads = {
        tool
        for tool in READ_TOOLS - {"factorybench.context.get"}
        if not tool.startswith("oracle_fusion.")
        or tool.rsplit(".", 1)[0] in relevant_oracle_resources
    }
    for discovery_index, tool in enumerate(sorted(optional_reads), start=1):
        if tool in seeded_tools:
            continue
        arguments = _arguments(tool, ordinal, scenario)
        fixture_rows.append(
            {
                "fixture_id": f"{task_id}-discovery-{discovery_index:02d}",
                "task_id": task_id,
                "tool_name": tool,
                "arguments_json": _canonical(arguments),
                "response_json": _canonical(
                    _response(
                        tool,
                        ordinal,
                        scenario,
                        arguments,
                        collaboration_writes=tuple(pattern_writes),
                    )
                ),
                "effect_json": None,
                "read_only": 1,
            }
        )

    assets = _task_evidence(
        task_id,
        scenario,
        ordinal,
        collaboration_writes=tuple(pattern_writes),
    )
    evidence_rows = [
        {
            "asset_id": asset["asset_id"],
            "task_id": task_id,
            "path": asset["path"],
            "title": asset["title"],
            "kind": asset["kind"],
            "source": asset["source"],
            "media_type": asset["media_type"],
            "extracted_text": asset["content"],
            "sha256": hashlib.sha256(asset["content"].encode()).hexdigest(),
        }
        for asset in assets
    ]
    primary_read_tool = decision["oracle_reads"][0]
    primary_read_arguments = _arguments(primary_read_tool, ordinal, scenario)
    primary_path = TOOL_BY_NAME[primary_read_tool]["_meta"]["factorybench"]["upstream"]["path"]
    primary_path_names = re.findall(r"\{([^{}]+)\}", primary_path)
    primary_resource_id = next(
        (str(primary_read_arguments[name]) for name in primary_path_names if name in primary_read_arguments),
        f"NS-{ordinal:06d}",
    )
    initial_record = {
        "task_id": task_id,
        "system": "oracle_fusion",
        "resource_type": primary_read_tool.rsplit(".", 1)[0],
        "resource_id": primary_resource_id,
        "status": "Open",
        "effective_at": AS_OF_DATE.isoformat(),
        "payload_json": _canonical(
            {
                "case": decision["case_reference"],
                "record": decision["record"],
                "revision": decision["revision"],
                "requested_quantity": decision["requested_quantity"],
                "identifiers": primary_read_arguments,
            }
        ),
        "revision": 0,
    }
    reference_read_calls = [
        {
            "tool": step["tool"],
            "arguments": deepcopy(step["arguments"]),
            "match": "result_contains",
            "expected_result_contains": _investigation_result_fragment(
                step["tool"],
                ordinal,
                scenario,
                step["arguments"],
            ),
        }
        for step in steps
        if step["control"]
    ]
    selected_read_calls = _select_key_read_calls(reference_read_calls)
    required_read_calls = [call for call, _ in selected_read_calls]
    required_investigations = [
        {
            "id": f"investigation_{index:02d}",
            "milestone_id": milestone_id,
            "description": _investigation_description(call["tool"], decision, call["arguments"]),
            "weight": 1.0,
            "before_primary_mutation": True,
            "any_of": _investigation_alternatives(call["tool"], ordinal, scenario, call["arguments"]),
        }
        for index, (call, milestone_id) in enumerate(selected_read_calls, start=1)
    ]
    post_read_quantity: float | int = (
        decision["transaction_measure"]
        if decision["decision_mode"] == "financial"
        and decision["transaction_unit"] != "USD"
        else (
            1
            if decision["decision_mode"] == "financial"
            else decision["raw_decision_values"]["scope"]
        )
    )
    post_read_target = _oracle_record(
        post_write_read,
        ordinal,
        scenario,
        decision,
        post_read_quantity,
    )
    post_read_identity = _oracle_identity(post_read_target)
    post_read_patch = _post_write_state_patch(
        scenario.primary_write,
        post_write_read,
        ordinal,
        scenario,
        decision,
    )
    post_write_verifications = [
        {
            "id": "verify_primary_oracle_state",
            "milestone_id": "verification.readback",
            "description": (
                f"Read {decision['record']} back through the documented Oracle "
                f"{post_write_read.removeprefix('oracle_fusion.').replace('_', ' ')} operation after the mutation and confirmed "
                f"the resource-specific changed fields {sorted(post_read_patch)}, including the effective update at {decision['selected_completion']}, rather than relying on the write acknowledgement."
            ),
            "weight": 2.0,
            "after_tool": scenario.primary_write,
            "any_of": _investigation_alternatives(
                post_write_read,
                ordinal,
                scenario,
                post_write_read_arguments,
                after_primary_mutation=True,
            ),
            "target_identity": post_read_identity,
            "expected_result_contains": post_read_patch,
            "materializes_new_record": _materializes_new_provider_record(
                scenario.primary_write
            ),
        },
        *collaboration_verifications,
    ]
    insight_fields_by_mode = {
        "plan": ("recommended_option", "recommended_outcome_date", "coverage_item_or_resource", "shortage_quantity", "decision_timing_status"),
        "quantity": ("recommended_option", "recommended_outcome_date", "controlled_item_or_record", "transaction_quantity", "decision_timing_status"),
        "schedule": ("recommended_option", "recommended_outcome_date", "affected_resource_or_operation", "selected_resource_or_control", "decision_timing_status"),
        "identity": ("recommended_option", "recommended_outcome_date", "source_or_target_record", "immutable_match_key", "decision_timing_status"),
        "forecast": ("recommended_option", "recommended_outcome_date", "program_or_asset_record", "safe_window_start", "decision_timing_status"),
        "financial": ("recommended_option", "recommended_outcome_date", "financial_document_or_record", "supported_amount_usd", "decision_timing_status"),
    }
    calculations = deepcopy(decision["calculations"])
    for criterion in calculations:
        criterion["milestone_id"] = _calculation_milestone_id(criterion)
    answer_checks = [
        {
            "id": f"answer_{field}",
            "milestone_id": "answer.insights",
            "field": field,
            "weight": 1.0,
            "description": (
                f"Reported {field.replace('_', ' ')} as {value!r}, tied to {decision['record']}, revision {decision['revision']}, and the selected {decision['selected_option']} outcome."
            ),
        }
        for field in insight_fields_by_mode[decision["decision_mode"]]
        for value in (answer[field],)
    ]
    rubric_milestones = _rubric_milestones(
        scenario=scenario,
        decision=decision,
        investigations=required_investigations,
        calculations=calculations,
        assertions=assertions,
        answer_checks=answer_checks,
        post_write_verifications=post_write_verifications,
        collaboration_writes=tuple(pattern_writes),
    )
    instruction = decision["request"]
    return {
        "benchmark": BENCHMARK_NAME,
        "benchmark_version": BENCHMARK_VERSION,
        "task_id": task_id,
        "family": scenario.family,
        "variant": None,
        "level": "L4",
        "title": scenario.title,
        "role": scenario.role,
        "instruction": instruction,
        "as_of": AS_OF_DATE.isoformat(),
        "world": {
            "id": WORLD_ID,
            "name": "Northstar Controls enterprise operations sandbox",
            "organization_id": "NSC",
            "primary_plant": "SEA",
            "database": "SQLite",
            "systems": _systems_for(tool_names),
            "synthetic": True,
        },
        "workflow": {
            "support_read": decision["oracle_reads"][1],
            "primary_read": primary_read_tool,
            "primary_write": scenario.primary_write,
            "post_write_read": post_write_read,
            "oracle_investigation_reads": list(decision["oracle_reads"]),
            "decision_branch": (
                f"Reconcile the {decision['decision_mode']} decision for {decision['record_noun']}; "
                f"apply {decision['binding_constraint']}, compare the three task-specific alternatives, "
                "and persist only the supported scope."
            ),
        },
        "decision_model": {
            "mode": decision["decision_mode"],
            "subject": decision["record_noun"],
            "source_document": decision["source_document"],
            "case_reference": decision["case_reference"],
            "record": decision["record"],
            "revision": decision["revision"],
            "selected_completion": decision["selected_completion"],
            "facts": deepcopy(decision["facts"]),
            "calculations": deepcopy(decision["calculations"]),
            "options": deepcopy(decision["options"]),
            "selected_option": decision["selected_option"],
        },
        "assets": assets,
        "seed_tables": {
            "organizations": [{"organization_id": "NSC", "name": "Northstar Controls Manufacturing", "ledger_currency": "USD"}],
            "users": [
                {"user_id": "U-AGENT", "display_name": "Jordan Lee", "role": scenario.role, "approval_limit": 0},
                {"user_id": "U-APPROVER", "display_name": "Avery Morgan", "role": "authorized_approver", "approval_limit": 250000},
                {"user_id": "U-OPS-LEAD", "display_name": "Maya Chen", "role": "operations_lead", "approval_limit": 25000},
            ],
            "evidence_files": evidence_rows,
            "api_fixtures": fixture_rows,
            "resource_state": [initial_record],
        },
        "required_reads": [call["tool"] for call in required_read_calls],
        "required_read_calls": required_read_calls,
        "reference_read_calls": reference_read_calls,
        "required_investigations": required_investigations,
        "rubric_milestones": rubric_milestones,
        "post_write_verifications": post_write_verifications,
        "answer_schema": answer_schema,
        "allowed_write_tables": ["resource_state", "answers", "audit_log"],
        "oracle_steps": steps,
        "expected": {
            "investigations": required_investigations,
            "post_write_verifications": post_write_verifications,
            "calculations": calculations,
            "assertions": assertions,
            "answer_checks": answer_checks,
            "answer": answer,
        },
        "evaluation": {
            "metric": "FactoryScore",
            "definition": "100 × passed deterministic criterion weight / available criterion weight",
            "checks": [
                "task-specific prerequisite discoveries, in any valid order",
                "task-specific calculations and conditional branch",
                "comparison of three scenario-specific alternatives",
                "exact Oracle and collaboration state transitions",
                "task-specific answer insights",
                "write-scope containment and no rejected mutations",
            ],
            "weighted": True,
        },
        "sequence_signature": hashlib.sha256("\n".join(tool_names).encode()).hexdigest(),
    }


def task_tool_sequence(task: dict[str, Any], *, include_harness: bool = False) -> tuple[str, ...]:
    names = tuple(step["tool"] for step in task["oracle_steps"])
    if include_harness:
        return names
    return tuple(name for name in names if not name.startswith("factorybench."))


def task_fingerprint(task: dict[str, Any]) -> str:
    """Hash the complete executable task contract for model-run pinning."""

    return hashlib.sha256(_canonical(task).encode()).hexdigest()


def catalog_fingerprint(tasks: list[dict[str, Any]]) -> str:
    """Hash an order-independent set of executable task contracts."""

    task_hashes = {
        task["task_id"]: task_fingerprint(task)
        for task in tasks
    }
    return hashlib.sha256(
        "".join(
            f"{task_id}:{task_hashes[task_id]}\n"
            for task_id in sorted(task_hashes)
        ).encode()
    ).hexdigest()


def catalog_quality_report(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    sequences = {task["task_id"]: task_tool_sequence(task) for task in tasks}
    duplicate_sequences: list[list[str]] = []
    by_sequence: dict[tuple[str, ...], list[str]] = {}
    for task_id, sequence in sequences.items():
        by_sequence.setdefault(sequence, []).append(task_id)
    duplicate_sequences = [task_ids for task_ids in by_sequence.values() if len(task_ids) > 1]
    closest_pair: dict[str, Any] = {"task_ids": [], "similarity": 0.0}
    task_ids = list(sequences)
    for left_index, left_id in enumerate(task_ids):
        for right_id in task_ids[left_index + 1 :]:
            similarity = SequenceMatcher(a=sequences[left_id], b=sequences[right_id], autojunk=False).ratio()
            if similarity > closest_pair["similarity"]:
                closest_pair = {"task_ids": [left_id, right_id], "similarity": round(similarity, 4)}
    generic_oracle_tools = sorted(
        name
        for name in {step["tool"] for task in tasks for step in task["oracle_steps"]}
        if name.startswith("oracle_") and name not in TOOL_BY_NAME
    )
    asset_counts = [len(task["assets"]) for task in tasks]
    native_format_counts = [
        len({asset["path"].rsplit(".", 1)[-1].casefold() for asset in task["assets"]})
        for task in tasks
    ]
    system_counts = [len(task["world"]["systems"]) for task in tasks]
    asset_content_hashes: dict[str, set[str]] = {}
    for task in tasks:
        for asset in task["assets"]:
            asset_content_hashes.setdefault(asset["kind"], set()).add(
                hashlib.sha256(asset["content"].encode()).hexdigest()
            )
    asset_role_unique_content_counts = {
        path: len(hashes) for path, hashes in sorted(asset_content_hashes.items())
    }
    semantic_violations: list[dict[str, str]] = []
    semantic_invariants_checked = 0

    def require(task: dict[str, Any], invariant: str, condition: bool) -> None:
        nonlocal semantic_invariants_checked
        semantic_invariants_checked += 1
        if not condition:
            semantic_violations.append(
                {"task_id": task["task_id"], "invariant": invariant}
            )

    for task in tasks:
        answer = task["expected"]["answer"]
        options = task["decision_model"]["options"]
        selected = [option for option in options if option["recommended"]]
        require(task, "exactly one recommended option", len(selected) == 1)
        if selected:
            option = selected[0]
            require(task, "recommended option is currently approved", option["approval"] == "APPROVED")
            require(task, "answer option matches decision", answer["recommended_option"] == option["id"])
            require(task, "answer date matches selected option", answer["recommended_outcome_date"] == option["completion"])
            require(task, "answer cost matches selected option", answer["recommended_incremental_cost_usd"] == option["incremental_cost"])
        outcome_variance = (
            date.fromisoformat(answer["recommended_outcome_date"])
            - date.fromisoformat(answer["business_need_date"])
        ).days
        require(
            task,
            "signed outcome variance matches independent dates",
            answer["outcome_vs_control_days"] == outcome_variance,
        )
        require(
            task,
            "timing status honestly reports late outcomes",
            answer["decision_timing_status"]
            == (
                "LATE"
                if outcome_variance > 0
                else "ON_TIME"
            ),
        )
        mode = task["decision_model"]["mode"]
        if mode == "plan":
            require(task, "plan coverage nets exclusions", answer["usable_coverage_quantity"] == answer["observed_coverage_quantity"] - answer["ineligible_coverage_quantity"])
            require(task, "plan shortage nets usable coverage", answer["shortage_quantity"] == answer["required_quantity"] - answer["usable_coverage_quantity"])
        elif mode == "quantity":
            require(task, "controlled quantity nets exclusions", answer["supported_quantity"] == answer["observed_quantity"] - answer["excluded_quantity"])
        elif mode == "schedule":
            require(task, "schedule nets protected capacity exactly once", answer["net_usable_capacity"] == answer["candidate_capacity"] - answer["unavailable_or_protected_capacity"])
            require(task, "schedule gap uses net usable capacity", answer["capacity_gap"] == answer["required_capacity"] - answer["net_usable_capacity"])
        elif mode == "financial":
            require(task, "financial bridge reconciles", abs(answer["document_amount_usd"] - answer["supported_amount_usd"] - answer["exception_amount_usd"]) <= 0.01)
            require(task, "financial control is task-specific", answer["financial_control"] != "generic invoice tolerance")
            require(task, "financial control threshold is nonnegative", answer["control_threshold_usd"] >= 0)
            if "physical_transaction_quantity" in answer:
                bridged = round(answer["physical_transaction_quantity"] * answer["approved_unit_rate_usd"], 2)
                expected_bridge = (
                    answer["exception_amount_usd"]
                    if task["title"] == "Reverse a duplicated copper issue"
                    else answer["supported_amount_usd"]
                )
                require(task, "physical transaction and approved rate bridge to the controlled amount", abs(bridged - expected_bridge) <= 0.01)
            if task["title"] == "Award the enclosure tooling package":
                require(task, "technical bid gate removes one response", answer["evaluated_bid_count"] == answer["technically_acceptable_bid_count"] + 1)
            elif task["title"] == "Release a hold after the supplier credit arrives":
                require(task, "matched credit exactly clears the scoped hold", answer["hold_amount_usd"] == answer["matched_credit_amount_usd"])
            elif task["title"] == "Correct payment terms from the signed contract":
                require(task, "payment-term correction is signed less current", answer["payment_term_correction_days"] == answer["signed_payment_term_days"] - answer["current_payment_term_days"])
            elif task["title"] == "Hold a duplicate invoice found in reconciliation":
                require(task, "confirmed duplicate has zero payable amount", answer["duplicate_invoice_amount_usd"] == answer["document_amount_usd"] and answer["payable_amount_usd"] == 0)
        elif mode == "identity":
            require(task, "identity candidates reconcile", answer["candidate_record_count"] == answer["matching_record_count"] + answer["excluded_record_count"])
        elif mode == "forecast":
            require(task, "forecast source measure reconciles", answer["source_measure"] == answer["qualifying_measure"] + answer["excluded_measure"])
            require(task, "forecast trigger is satisfied", answer["qualifying_measure"] >= answer["trigger_threshold"])
            require(task, "forecast safe window follows due date", date.fromisoformat(answer["safe_window_start"]) >= date.fromisoformat(answer["due_date"]))
            require(task, "forecast horizon contains safe window", date.fromisoformat(answer["forecast_horizon_end"]) >= date.fromisoformat(answer["safe_window_start"]))
        primary_tool = task["workflow"]["primary_write"]
        primary_assertion = next(
            assertion
            for assertion in task["expected"]["assertions"]
            if assertion["weight"] == 3.0
        )
        require(
            task,
            "primary mutation rubric names the provider operation and critical payload",
            primary_tool in primary_assertion["description"]
            and "requestBody." in primary_assertion["description"]
            and "exact provider-critical values" in primary_assertion["description"],
        )
        primary_step = next(
            step
            for step in task["oracle_steps"]
            if step.get("phase") == "primary_mutation"
        )
        require(
            task,
            "primary mutation rubric grades exact provider-critical arguments",
            primary_assertion.get("payload_contains")
            == {
                "tool": primary_tool,
                "arguments": _provider_critical_arguments(primary_step["arguments"]),
            },
        )
        require(
            task,
            "primary mutation rubric rejects unauthorized provider fields",
            primary_assertion.get("payload_allowed_argument_paths")
            == sorted(_provider_argument_paths(primary_step["arguments"])),
        )
        exact_scalars: list[Any] = []

        def collect_exact_scalars(value: Any) -> None:
            if isinstance(value, dict):
                for item in value.values():
                    collect_exact_scalars(item)
            elif isinstance(value, list):
                for item in value:
                    collect_exact_scalars(item)
            elif value is not None:
                exact_scalars.append(value)

        collect_exact_scalars(
            primary_assertion["payload_contains"]["arguments"]
        )
        visible_sources = "\n".join(
            asset["content"] for asset in task["assets"]
        ).casefold()
        require(
            task,
            "every exact provider-critical scalar is discoverable in task evidence",
            all(
                _canonical(value).strip('"').casefold() in visible_sources
                for value in exact_scalars
            ),
        )
        expected_semantic_groups = _primary_semantic_payload_groups(
            primary_step["arguments"],
            task["decision_model"],
        )
        if expected_semantic_groups:
            require(
                task,
                "free-form provider prose is graded by scoped semantic alternatives",
                primary_assertion.get("payload_text_any_of")
                == expected_semantic_groups,
            )
        require(
            task,
            "every mutation rubric grades persisted provider payload",
            [
                assertion.get("payload_contains", {}).get("tool")
                for assertion in task["expected"]["assertions"]
            ]
            == [
                step["tool"]
                for step in task["oracle_steps"]
                if step["tool"] in WRITE_TOOLS
                and step["tool"] != "factorybench.submit_answer"
            ],
        )
        require(
            task,
            "every investigation proves returned task evidence",
            all(
                alternative.get("match") == "result_contains"
                and bool(alternative.get("expected_result_contains"))
                for investigation in task["required_investigations"]
                for alternative in investigation["any_of"]
            ),
        )
        readback = task["post_write_verifications"][0]
        require(
            task,
            "provider readback checks identity plus changed business state",
            bool(readback["target_identity"])
            and "LastUpdateDate" in readback["expected_result_contains"]
            and len(readback["expected_result_contains"]) >= 2,
        )
        if primary_tool in {"oracle_fusion.purchase_orders.close", "oracle_fusion.invoices.validate"}:
            if "exception_amount_usd" in answer:
                require(task, "close or validation has no unresolved financial exception", answer["exception_amount_usd"] == 0)
            if "excluded_quantity" in answer:
                require(task, "close has no unresolved quantity exception", answer["excluded_quantity"] == 0)
    recipe_markers = (
        "resolve factorybench",
        "evidence is distributed",
        "return exactly",
        "after the documented",
        "oracle_fusion.",
        "gmail.",
        "google_drive.",
        "google_sheets.",
        "slack.",
        "`",
        "we cannot make a decision on",
        "treat “",
        "do not trust the header quantity",
        "compare the credible alternatives",
    )
    prompt_violations: dict[str, list[str]] = {}
    for task in tasks:
        prompt = task["instruction"]
        violations = [marker for marker in recipe_markers if marker in prompt.lower()]
        word_count = len(prompt.split())
        if word_count < 45 or word_count > 220:
            violations.append(f"word_count={word_count}")
        if violations:
            prompt_violations[task["task_id"]] = violations
    closest_prompt_pair: dict[str, Any] = {"task_ids": [], "similarity": 0.0}
    closest_prompt_shingle_pair: dict[str, Any] = {
        "task_ids": [],
        "similarity": 0.0,
    }

    def prompt_shingles(value: str) -> set[tuple[str, ...]]:
        words = re.findall(r"[a-z0-9]+", value.casefold())
        return {
            tuple(words[index : index + 5])
            for index in range(max(0, len(words) - 4))
        }

    for left_index, left_task in enumerate(tasks):
        for right_task in tasks[left_index + 1 :]:
            similarity = SequenceMatcher(
                a=left_task["instruction"],
                b=right_task["instruction"],
                autojunk=False,
            ).ratio()
            if similarity > closest_prompt_pair["similarity"]:
                closest_prompt_pair = {
                    "task_ids": [left_task["task_id"], right_task["task_id"]],
                    "similarity": round(similarity, 4),
                }
            left_shingles = prompt_shingles(left_task["instruction"])
            right_shingles = prompt_shingles(right_task["instruction"])
            union = left_shingles | right_shingles
            shingle_similarity = (
                len(left_shingles & right_shingles) / len(union) if union else 1.0
            )
            if shingle_similarity > closest_prompt_shingle_pair["similarity"]:
                closest_prompt_shingle_pair = {
                    "task_ids": [left_task["task_id"], right_task["task_id"]],
                    "similarity": round(shingle_similarity, 6),
                }
    structured_roles = (
        "source_workbook",
        "spreadsheet_export",
        "source_reconciliation",
        "control_calendar",
    )
    minimum_structured_rows_by_asset_role = {
        role: min(
            len(next(asset for asset in task["assets"] if asset["kind"] == role).get("rows", []))
            for task in tasks
        )
        for role in structured_roles
    }
    minimum_email_chars = min(
        len(next(asset for asset in task["assets"] if asset["kind"] == "email")["content"])
        for task in tasks
    )
    minimum_slack_messages = min(
        len(json.loads(next(asset for asset in task["assets"] if asset["kind"] == "chat_thread")["content"])["messages"])
        for task in tasks
    )
    minimum_investigations = min(len(task["expected"]["investigations"]) for task in tasks)
    minimum_provider_reads = min(len(task["reference_read_calls"]) for task in tasks)
    minimum_calculations = min(len(task["expected"]["calculations"]) for task in tasks)
    minimum_options = min(len(task["decision_model"]["options"]) for task in tasks)
    minimum_answer_fields = min(len(task["expected"]["answer"]) for task in tasks)
    decision_mode_counts: dict[str, int] = {}
    option_signatures: set[tuple[str, ...]] = set()
    source_documents: set[str] = set()
    for task in tasks:
        mode = str(task["decision_model"]["mode"])
        decision_mode_counts[mode] = decision_mode_counts.get(mode, 0) + 1
        option_signatures.add(tuple(option["id"] for option in task["decision_model"]["options"]))
        source_documents.add(str(task["decision_model"]["source_document"]))
    minimum_oracle_read_tables = min(
        len(
            {
                call["tool"].rsplit(".", 1)[0]
                for call in task["required_read_calls"]
                if call["tool"].startswith("oracle_fusion.")
            }
        )
        for task in tasks
    )
    criterion_signatures: set[str] = set()
    minimum_criteria = 10_000
    generic_criteria: list[dict[str, str]] = []
    maximum_precomputed_options_in_one_read = 0
    preassembled_packet_leaks: list[dict[str, str]] = []
    for task in tasks:
        criteria = task["rubric_milestones"]
        minimum_criteria = min(minimum_criteria, len(criteria))
        criterion_signatures.add(
            hashlib.sha256("\n".join(criterion["description"] for criterion in criteria).encode()).hexdigest()
        )
        for criterion in criteria:
            lowered = criterion["description"].lower()
            if "produced the task-scoped" in lowered or lowered in {
                "read-before-write control",
                "exact answer fields",
                "write-scope containment",
                "error-free execution",
            }:
                generic_criteria.append({"task_id": task["task_id"], "criterion": criterion["description"]})
        for fixture in task["seed_tables"]["api_fixtures"]:
            if not fixture["read_only"]:
                continue
            response = fixture["response_json"]
            precomputed_options = sum(
                option["id"] in response
                and option["completion"] in response
                and (
                    option["incremental_cost"] == 0
                    or str(option["incremental_cost"]) in response
                )
                for option in task["decision_model"]["options"]
            )
            maximum_precomputed_options_in_one_read = max(
                maximum_precomputed_options_in_one_read,
                precomputed_options,
            )
            if (
                any(marker in response for marker in ("approvedArguments", "returnFields", "oracleOperation", '"recommended":true'))
                or precomputed_options >= 2
            ):
                preassembled_packet_leaks.append(
                    {"task_id": task["task_id"], "tool": fixture["tool_name"]}
                )
    realism = {
        "prompt_violations": prompt_violations,
        "closest_prompt_pair": closest_prompt_pair,
        "closest_prompt_5_shingle_pair": closest_prompt_shingle_pair,
        "minimum_structured_rows_by_asset_role": minimum_structured_rows_by_asset_role,
        "minimum_email_chars": minimum_email_chars,
        "minimum_slack_messages": minimum_slack_messages,
        "minimum_investigations_per_task": minimum_investigations,
        "minimum_provider_reads_per_task": minimum_provider_reads,
        "minimum_calculations_per_task": minimum_calculations,
        "minimum_options_per_task": minimum_options,
        "minimum_answer_fields_per_task": minimum_answer_fields,
        "minimum_oracle_read_tables_per_task": minimum_oracle_read_tables,
        "minimum_task_specific_criteria": minimum_criteria,
        "unique_criterion_sets": len(criterion_signatures),
        "generic_criteria": generic_criteria,
        "preassembled_packet_leaks": preassembled_packet_leaks,
        "maximum_precomputed_options_exposed_by_one_read": maximum_precomputed_options_in_one_read,
        "decision_mode_counts": dict(sorted(decision_mode_counts.items())),
        "unique_option_sets": len(option_signatures),
        "unique_source_documents": len(source_documents),
    }
    return {
        "task_count": len(tasks),
        "unique_titles": len({task["title"] for task in tasks}),
        "unique_sequences": len(by_sequence),
        "duplicate_sequences": duplicate_sequences,
        "closest_pair": closest_pair,
        "minimum_assets_per_task": min(asset_counts),
        "maximum_assets_per_task": max(asset_counts),
        "minimum_native_formats_per_task": min(native_format_counts),
        "asset_role_count": len(asset_content_hashes),
        "asset_role_unique_content_counts": asset_role_unique_content_counts,
        "asset_roles_with_unique_task_content": sum(
            count == len(tasks) for count in asset_role_unique_content_counts.values()
        ),
        "semantic_invariants_checked": semantic_invariants_checked,
        "semantic_violations": semantic_violations,
        "minimum_systems_per_task": min(system_counts),
        "unmapped_oracle_tools": generic_oracle_tools,
        "realism": realism,
        "passed": (
            len(tasks) == 100
            and len({task["title"] for task in tasks}) == 100
            and not duplicate_sequences
            and closest_pair["similarity"] <= 0.80
            and min(asset_counts) >= 28
            and min(native_format_counts) >= 7
            and len(asset_content_hashes) >= 28
            and all(count == len(tasks) for count in asset_role_unique_content_counts.values())
            and not semantic_violations
            and min(system_counts) >= 5
            and not generic_oracle_tools
            and not prompt_violations
            and closest_prompt_pair["similarity"] <= 0.70
            and closest_prompt_shingle_pair["similarity"] <= 0.72
            and minimum_structured_rows_by_asset_role["source_workbook"] >= 10
            and minimum_structured_rows_by_asset_role["spreadsheet_export"] >= 8
            and minimum_structured_rows_by_asset_role["source_reconciliation"] >= 10
            and minimum_structured_rows_by_asset_role["control_calendar"] >= 7
            and minimum_email_chars >= 1_500
            and minimum_slack_messages >= 6
            and minimum_investigations >= 9
            and minimum_calculations >= 4
            and minimum_options >= 3
            and minimum_answer_fields >= 6
            and minimum_oracle_read_tables >= 3
            and minimum_criteria >= 10
            and len(criterion_signatures) == len(tasks)
            and len(decision_mode_counts) == 6
            and len(option_signatures) == len(tasks)
            and len(source_documents) == len(tasks)
            and not generic_criteria
            and not preassembled_packet_leaks
            and maximum_precomputed_options_in_one_read <= 1
        ),
    }


@lru_cache(maxsize=1)
def build_catalog() -> list[dict[str, Any]]:
    """Return the 100 deterministic, independently authored tasks."""

    tasks = [_build_task(ordinal, scenario) for ordinal, scenario in enumerate(SCENARIOS, start=1)]
    quality = catalog_quality_report(tasks)
    if not quality["passed"]:
        raise ValueError(f"catalog fidelity gate failed: {quality}")
    return tasks


def get_task(task_id: str) -> dict[str, Any]:
    for task in build_catalog():
        if task["task_id"] == task_id:
            return deepcopy(task)
    raise KeyError(f"Unknown task: {task_id}")


__all__ = [
    "AS_OF_DATE",
    "BENCHMARK_NAME",
    "BENCHMARK_VERSION",
    "FAMILIES",
    "FAMILY_DESCRIPTIONS",
    "WORLD_ID",
    "build_catalog",
    "catalog_fingerprint",
    "catalog_quality_report",
    "get_task",
    "task_fingerprint",
    "task_tool_sequence",
]
