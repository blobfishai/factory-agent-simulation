"""FactoryBench-100 v2 enterprise workflow catalog.

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
from typing import Any

from .contracts import READ_TOOLS, TOOL_BY_NAME, WRITE_TOOLS
from .evidence import build_evidence
from .scenarios import FAMILIES, FAMILY_DESCRIPTIONS, SCENARIOS, Scenario


BENCHMARK_NAME = "FactoryBench-100"
BENCHMARK_VERSION = "2.0.0"
AS_OF_DATE = date(2026, 1, 12)
WORLD_ID = "northstar-enterprise-fusion-v2"


EVIDENCE_PATTERNS: tuple[dict[str, tuple[str, ...]], ...] = (
    {
        "reads": ("gmail.messages.list", "gmail.messages.get", "gmail.messages.attachments.get", "google_drive.approvals.list"),
        "writes": ("google_sheets.spreadsheets.values.update", "gmail.drafts.create"),
    },
    {
        "reads": ("slack.search_messages", "slack.conversations_replies", "google_drive.files.get", "google_sheets.spreadsheets.values.get"),
        "writes": ("google_drive.approvals.approve", "slack.chat_postMessage"),
    },
    {
        "reads": ("google_drive.files.list", "google_drive.files.download", "google_sheets.spreadsheets.values.batchGet", "slack.conversations_history"),
        "writes": ("google_sheets.spreadsheets.values.append", "slack.reactions_add"),
    },
    {
        "reads": ("gmail.threads.get", "slack.conversations_history", "google_sheets.spreadsheets.get", "google_drive.approvals.list"),
        "writes": ("gmail.drafts.create", "google_drive.comments.create"),
    },
    {
        "reads": ("google_sheets.spreadsheets.values.get", "google_drive.files.export", "slack.files_info", "gmail.messages.get"),
        "writes": ("gmail.messages.send", "google_sheets.spreadsheets.values.update"),
    },
    {
        "reads": ("slack.conversations_history", "gmail.messages.list", "google_drive.files.get", "google_sheets.spreadsheets.values.batchGet"),
        "writes": ("slack.chat_postMessage", "gmail.drafts.create"),
    },
    {
        "reads": ("google_drive.files.list", "slack.search_messages", "gmail.threads.get", "google_sheets.spreadsheets.get"),
        "writes": ("google_drive.approvals.approve", "google_sheets.spreadsheets.values.append"),
    },
    {
        "reads": ("gmail.messages.list", "google_drive.files.download", "slack.conversations_replies", "google_sheets.spreadsheets.get"),
        "writes": ("google_drive.comments.create", "gmail.messages.send"),
    },
    {
        "reads": ("google_sheets.spreadsheets.values.batchGet", "gmail.messages.get", "slack.files_info", "google_drive.approvals.list"),
        "writes": ("google_sheets.spreadsheets.values.update", "slack.chat_postMessage"),
    },
    {
        "reads": ("google_drive.files.list", "gmail.messages.attachments.get", "slack.conversations_history", "google_sheets.spreadsheets.values.get"),
        "writes": ("gmail.drafts.create", "slack.reactions_add"),
    },
)

def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _answer_schema(answer: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, dict[str, Any]] = {}
    for field, value in answer.items():
        if isinstance(value, int):
            properties[field] = {"type": "integer"}
        elif isinstance(value, float):
            properties[field] = {"type": "number", "multipleOf": 0.01}
        else:
            properties[field] = {"type": "string"}
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
    return {field: _field_value(field, ordinal, scenario) for field in scenario.answer_keys}


def _base64_message(scenario: Scenario, ordinal: int, *, sent: bool) -> str:
    case = f"CASE-{ordinal:03d}"
    kind = "Completed" if sent else "Draft"
    message = (
        f"From: {scenario.role.replace('_', '.')}@northstar.example\r\n"
        "To: operations-control@northstar.example\r\n"
        f"Subject: {case} — {kind} enterprise workflow\r\n"
        "Content-Type: text/plain; charset=UTF-8\r\n\r\n"
        f"{scenario.result_status}. Oracle and collaboration references are recorded under {case}.\r\n"
    )
    return base64.urlsafe_b64encode(message.encode()).decode().rstrip("=")


def _path_value(name: str, ordinal: int) -> Any:
    if name in {"WorkOrderId", "WoOperationId", "WoOperationMaterialId", "WoOperationResourceId", "MaintenanceProgramId", "SupplierId", "HeaderInterfaceId", "InterfaceTransactionId", "InvoiceId", "HoldId", "InspectionId"}:
        offsets = {
            "WorkOrderId": 100_000,
            "WoOperationId": 200_000,
            "WoOperationMaterialId": 300_000,
            "WoOperationResourceId": 400_000,
            "MaintenanceProgramId": 500_000,
            "SupplierId": 600_000,
            "HeaderInterfaceId": 700_000,
            "InterfaceTransactionId": 800_000,
            "InvoiceId": 900_000,
            "HoldId": 1_000_000,
            "InspectionId": 1_100_000,
        }
        return offsets[name] + ordinal
    return f"{name}-{ordinal:04d}"


def _oracle_body(tool: str, ordinal: int, scenario: Scenario) -> dict[str, Any]:
    effective = AS_OF_DATE + timedelta(days=(ordinal % 19) + 1)
    completion = effective + timedelta(days=3 + ordinal % 5)
    quantity = 8 + ordinal % 37
    case = f"CASE-{ordinal:03d}"
    common: dict[str, dict[str, Any]] = {
        "oracle_fusion.work_orders.create": {"OrganizationCode": "SEA", "WorkOrderNumber": f"WO-{ordinal:04d}", "ItemNumber": f"NS-COMP-{ordinal:03d}", "WorkOrderQuantity": quantity, "WorkOrderStatusCode": "Released", "PlannedStartDate": effective.isoformat(), "PlannedCompletionDate": completion.isoformat()},
        "oracle_fusion.work_orders.update": {"WorkOrderStatusCode": "Released", "PlannedStartDate": effective.isoformat(), "PlannedCompletionDate": completion.isoformat()},
        "oracle_fusion.maintenance_work_orders.create": {"OrganizationCode": "SEA", "WorkOrderNumber": f"MWO-{ordinal:04d}", "AssetNumber": f"ASSET-{ordinal:03d}", "WorkOrderDescription": scenario.outcome, "WorkOrderTypeCode": "CORRECTIVE", "WorkOrderStatusCode": "Released", "PlannedStartDate": effective.isoformat(), "PlannedCompletionDate": completion.isoformat()},
        "oracle_fusion.maintenance_work_orders.update": {"WorkOrderDescription": scenario.outcome, "WorkOrderStatusCode": "Released", "PlannedCompletionDate": completion.isoformat()},
        "oracle_fusion.maintenance_programs.create": {"MaintenanceProgramCode": f"PM-{ordinal:04d}", "MaintenanceProgramName": scenario.title, "OrganizationCode": "SEA", "StatusCode": "ACTIVE", "ForecastStartDate": effective.isoformat(), "ForecastEndDate": (effective + timedelta(days=90)).isoformat()},
        "oracle_fusion.maintenance_programs.update": {"StatusCode": "ACTIVE", "ForecastStartDate": effective.isoformat(), "ForecastEndDate": (effective + timedelta(days=90)).isoformat()},
        "oracle_fusion.invoices.create": {"BusinessUnit": "Northstar Manufacturing BU", "Supplier": "Cascade Industrial", "SupplierSite": "SEA", "InvoiceNumber": f"INV-{ordinal:04d}", "InvoiceDate": effective.isoformat(), "InvoiceAmount": round(quantity * (42.5 + ordinal * 1.17), 2), "InvoiceCurrency": "USD", "PaymentTerms": "Net 30"},
        "oracle_fusion.invoices.update": {"PaymentTerms": "Net 45"},
        "oracle_fusion.draft_purchase_orders.create": {"SupplierId": 600_000 + ordinal, "SupplierSiteId": 610_000 + ordinal, "ProcurementBUId": 204, "RequisitioningBUId": 204, "BuyerId": 9100 + ordinal, "DocumentStyleId": 1, "CurrencyCode": "USD", "Description": scenario.title, "RequiredAcknowledgment": "Document and Schedule", "lines": [{"LineNumber": 1, "LineType": "Goods", "Item": f"NS-COMP-{ordinal:03d}", "ItemDescription": scenario.title, "Quantity": quantity, "UOM": "EA", "Price": round(42.5 + ordinal * 1.17, 2)}]},
        "oracle_fusion.quality_inspection_results.create": {"OrganizationCode": "SEA", "InspectionPlanName": f"PLAN-{1 + ordinal % 12:02d}", "InspectionPlanId": 1_200_000 + ordinal, "DocumentType": "RECEIVING", "DocumentNumber": f"RCV-{ordinal:04d}", "ItemNumber": f"NS-COMP-{ordinal:03d}", "Quantity": quantity, "LotNumber": f"LOT-{ordinal:04d}", "InspectionStatus": "IN_PROGRESS", "samples": [{"SampleNumber": 1, "Result": "PASS"}]},
        "oracle_fusion.quality_inspection_results.update": {"InspectionStatus": "COMPLETE", "InspectionResult": "ACCEPT", "QuantityAccepted": quantity, "QuantityRejected": 0, "samples": [{"SampleNumber": 1, "Result": "PASS"}]},
        "oracle_fusion.work_order_operations.create": {"OperationSequenceNumber": 30 + ordinal % 10, "OperationName": f"Approved rework {case}", "WorkCenterCode": "WC-REWORK", "PlannedStartDate": effective.isoformat(), "PlannedCompletionDate": completion.isoformat()},
        "oracle_fusion.work_order_operations.update": {"WorkCenterCode": f"WC-ALT-{1 + ordinal % 3}", "PlannedStartDate": effective.isoformat(), "PlannedCompletionDate": completion.isoformat(), "OperationName": f"Controlled operation {case}"},
        "oracle_fusion.work_order_materials.update": {"Quantity": quantity, "SupplySubinventory": "STORES", "ItemNumber": f"NS-COMP-{ordinal:03d}"},
        "oracle_fusion.work_order_resources.create": {"ResourceCode": f"RES-CERT-{ordinal:03d}", "UsageRate": 1.0, "AssignedUnits": 1, "BasisType": "VARIABLE"},
        "oracle_fusion.work_order_resources.update": {"ResourceCode": f"RES-ALT-{ordinal:03d}", "UsageRate": 1.0, "AssignedUnits": 1},
        "oracle_fusion.maintenance_operations.update": {"WorkCenterCode": f"MAINT-{1 + ordinal % 3}", "OperationName": f"Corrective action {case}", "PlannedStartDate": effective.isoformat()},
        "oracle_fusion.receiving_receipt_transactions.update": {"TransactionType": "CORRECT", "Quantity": quantity, "InspectionQualityCode": "ACCEPT", "Comments": case},
        "oracle_fusion.work_order_materials.replace_with_substitute": {"SubstituteItemNumber": f"NS-SUB-{ordinal:03d}", "SubstituteQuantity": quantity},
        "oracle_fusion.material_transactions.create": {"SourceSystemCode": "FUSION_MOBILE", "SourceSystemType": "EXTERNAL", "MaterialTransactionDetail": [{"OrganizationCode": "SEA", "WorkOrderNumber": f"WO-{ordinal:04d}", "InventoryItemNumber": f"NS-COMP-{ordinal:03d}", "TransactionTypeCode": "MATERIAL_ISSUE", "TransactionQuantity": quantity, "TransactionUnitOfMeasure": "EA", "SubinventoryCode": "STORES", "LotNumber": f"LOT-{ordinal:04d}"}]},
        "oracle_fusion.operation_transactions.create": {"SourceSystemCode": "FUSION_MOBILE", "SourceSystemType": "EXTERNAL", "OperationTransactionDetail": [{"OrganizationCode": "SEA", "WorkOrderNumber": f"WO-{ordinal:04d}", "WoOperationSequenceNumber": 10, "FromDispatchState": "READY", "ToDispatchState": "COMPLETE", "TransactionQuantity": quantity, "TransactionUnitOfMeasure": "EA"}]},
        "oracle_fusion.resource_transactions.create": {"SourceSystemCode": "FUSION_MOBILE", "ResourceTransactionDetail": [{"OrganizationCode": "SEA", "WorkOrderNumber": f"WO-{ordinal:04d}", "WoOperationSequenceNumber": 10, "ResourceCode": f"RES-{ordinal:03d}", "TransactionQuantity": round(quantity * 0.75, 2), "TransactionUnitOfMeasure": "HR"}]},
        "oracle_fusion.inventory_transactions.create": {"SourceSystemCode": "EXTERNAL", "TransactionMode": "ONLINE", "TransactionLines": [{"OrganizationCode": "SEA", "Item": f"NS-COMP-{ordinal:03d}", "Subinventory": "STORES", "TransactionType": "Subinventory Transfer", "TransactionQuantity": quantity, "TransactionUnitOfMeasure": "EA", "LotNumber": f"LOT-{ordinal:04d}", "TransferSubinventory": "CONTROLLED"}]},
        "oracle_fusion.supply_requests.create": {"SupplyOrderReferenceNumber": f"SUPPLY-{ordinal:04d}", "SupplyRequestSystem": "EXT", "SupplyRequestDate": effective.isoformat(), "supplyRequestLines": [{"SupplyOrderSource": "EXT", "SupplyType": "BUY", "ItemNumber": f"NS-COMP-{ordinal:03d}", "Quantity": quantity, "NeedByDate": completion.isoformat(), "DestinationOrganizationCode": "SEA"}]},
        "oracle_fusion.receiving_receipt_requests.create": {"ReceiptSourceCode": "VENDOR", "OrganizationCode": "SEA", "VendorName": "Cascade Industrial", "EmployeeId": 7100 + ordinal, "lines": [{"SourceDocumentCode": "PO", "POHeaderId": 2_000_000 + ordinal, "POLineId": 2_100_000 + ordinal, "ItemNumber": f"NS-COMP-{ordinal:03d}", "Quantity": quantity, "UnitOfMeasure": "EA", "LotNumber": f"LOT-{ordinal:04d}"}]},
        "oracle_fusion.receiving_receipt_transactions.create": {"TransactionType": "RECEIVE", "Quantity": quantity, "ItemNumber": f"NS-COMP-{ordinal:03d}", "InspectionQualityCode": "ACCEPT", "lotItemLots": [{"LotNumber": f"LOT-{ordinal:04d}", "PrimaryQuantity": quantity}]},
        "oracle_fusion.maintenance_documents.create": {"DocumentName": f"{case}-technical-evidence", "DocumentNumber": f"DOC-{ordinal:04d}", "DocumentType": "URL", "Description": scenario.outcome},
        "oracle_fusion.invoices.validate": {"ProcessAction": "Validate", "BusinessUnit": "Northstar Manufacturing BU", "Supplier": "Cascade Industrial", "InvoiceNumber": f"INV-{ordinal:04d}"},
        "oracle_fusion.invoice_holds.create": {"InvoiceId": 900_000 + ordinal, "HoldName": "CONTROL REVIEW", "HoldReason": scenario.outcome},
        "oracle_fusion.invoice_holds.update": {"ReleaseName": "APPROVED EVIDENCE", "ReleaseReason": scenario.outcome},
        "oracle_fusion.purchase_orders.acknowledge": {"supplierOrder": f"SUP-ACK-{ordinal:04d}", "acknowledgementNote": scenario.outcome},
        "oracle_fusion.purchase_orders.close": {"closeAction": "finallyClose", "closeReason": scenario.outcome},
        "oracle_fusion.purchase_orders.cancel": {"cancellationReason": scenario.outcome, "cancelUnfulfilledDemandFlag": True, "initiatingParty": "buyer"},
        "oracle_fusion.maintenance_programs.generate_forecasts": {"MaintenanceProgramCode": f"PM-{ordinal:04d}", "ForecastStartDate": effective.isoformat(), "ForecastEndDate": (effective + timedelta(days=90)).isoformat()},
        "oracle_fusion.maintenance_programs.generate_work_orders": {"MaintenanceProgramCode": f"PM-{ordinal:04d}", "WorkOrderStartDate": effective.isoformat(), "WorkOrderEndDate": (effective + timedelta(days=30)).isoformat()},
    }
    return deepcopy(common.get(tool, {}))


def _arguments(tool: str, ordinal: int, scenario: Scenario) -> dict[str, Any]:
    case = f"CASE-{ordinal:03d}"
    message_id = f"msg-{ordinal:03d}"
    file_id = f"drive-{ordinal:03d}"
    sheet_id = f"sheet-{ordinal:03d}"
    channel = ("C-PRODUCTION", "C-PROCUREMENT", "C-QUALITY", "C-FINANCE")[ordinal % 4]
    thread_ts = f"1768{ordinal:06d}.000100"
    explicit: dict[str, dict[str, Any]] = {
        "factorybench.context.get": {},
        "gmail.messages.list": {"userId": "me", "q": f'"{case}"', "maxResults": 20},
        "gmail.messages.get": {"userId": "me", "id": message_id, "format": "full"},
        "gmail.messages.attachments.get": {"userId": "me", "messageId": message_id, "id": f"att-{ordinal:03d}"},
        "gmail.threads.get": {"userId": "me", "id": f"thread-{ordinal:03d}", "format": "full"},
        "gmail.drafts.create": {"userId": "me", "message": {"raw": _base64_message(scenario, ordinal, sent=False), "threadId": f"thread-{ordinal:03d}"}},
        "gmail.messages.send": {"userId": "me", "raw": _base64_message(scenario, ordinal, sent=True), "threadId": f"thread-{ordinal:03d}"},
        "google_drive.files.list": {"q": f"name contains '{case}' and trashed = false", "pageSize": 50, "fields": "files(id,name,mimeType,modifiedTime,md5Checksum)"},
        "google_drive.files.get": {"fileId": file_id, "fields": "id,name,mimeType,modifiedTime,md5Checksum,description"},
        "google_drive.files.download": {"fileId": file_id},
        "google_drive.files.export": {"fileId": file_id, "mimeType": "text/plain"},
        "google_drive.approvals.list": {"fileId": f"drive-approval-{ordinal:03d}", "pageSize": 20},
        "google_drive.approvals.approve": {"fileId": f"drive-approval-{ordinal:03d}", "approvalId": f"approval-{ordinal:03d}", "requestBody": {"message": f"Approved for {case} only."}},
        "google_drive.comments.create": {"fileId": file_id, "requestBody": {"content": f"{case}: {scenario.result_status}; Oracle reference recorded."}},
        "google_sheets.spreadsheets.get": {"spreadsheetId": sheet_id, "ranges": ["Control!A1:H50"], "includeGridData": False},
        "google_sheets.spreadsheets.values.get": {"spreadsheetId": sheet_id, "range": "Control!A1:H50", "majorDimension": "ROWS", "valueRenderOption": "UNFORMATTED_VALUE"},
        "google_sheets.spreadsheets.values.batchGet": {"spreadsheetId": sheet_id, "ranges": ["Control!A1:H50", "Approvals!A1:G20"], "majorDimension": "ROWS", "valueRenderOption": "UNFORMATTED_VALUE"},
        "google_sheets.spreadsheets.values.update": {"spreadsheetId": sheet_id, "range": f"Control!H{2 + ordinal % 40}", "valueInputOption": "RAW", "includeValuesInResponse": True, "requestBody": {"range": f"Control!H{2 + ordinal % 40}", "majorDimension": "ROWS", "values": [[scenario.result_status]]}},
        "google_sheets.spreadsheets.values.append": {"spreadsheetId": sheet_id, "range": "Audit!A:F", "valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS", "requestBody": {"range": "Audit!A:F", "majorDimension": "ROWS", "values": [[AS_OF_DATE.isoformat(), case, scenario.role, scenario.result_status, f"REF-{ordinal:04d}", "posted"]]}},
        "slack.search_messages": {"query": f'"{case}"', "count": 50, "sort": "timestamp", "sort_dir": "asc"},
        "slack.conversations_history": {"channel": channel, "oldest": "1768000000.000000", "inclusive": True, "limit": 100},
        "slack.conversations_replies": {"channel": channel, "ts": thread_ts, "limit": 100},
        "slack.files_info": {"file": f"F-{ordinal:06d}"},
        "slack.chat_postMessage": {"channel": channel, "thread_ts": thread_ts, "text": f"{case}: {scenario.result_status}. Oracle reference REF-{ordinal:04d}; control workbook updated."},
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
    if tool.endswith(".list"):
        arguments.update({"q": f"ReferenceNumber='{case}'", "limit": 50, "onlyData": True})
    if "requestBody" in schema.get("properties", {}) and "requestBody" not in arguments:
        arguments["requestBody"] = _oracle_body(tool, ordinal, scenario)
    return arguments


def _response(tool: str, ordinal: int, scenario: Scenario, arguments: dict[str, Any]) -> dict[str, Any]:
    case = f"CASE-{ordinal:03d}"
    quantity = 8 + ordinal % 37
    task_id = f"factorybench-{ordinal:03d}"
    approved_arguments = _arguments(scenario.primary_write, ordinal, scenario)
    answer = _answer(scenario, ordinal)
    control_packet = {
        "case": case,
        "approvalStatus": "APPROVED",
        "decision": scenario.outcome,
        "oracleOperation": scenario.primary_write,
        "approvedArguments": approved_arguments,
        "controlWorkbookOutcomeRange": f"Control!H{2 + ordinal % 40}",
        "controlWorkbookAuditRange": "Audit!A:F",
        "returnFields": answer,
    }
    control_text = (
        f"{case} | APPROVED | {scenario.outcome} | "
        f"Oracle operation {scenario.primary_write} | "
        f"approved control packet {_canonical(control_packet)}"
    )
    reference_ids = {
        name: _path_value(name, ordinal)
        for name in (
            "WorkOrderId",
            "WoOperationId",
            "WoOperationMaterialId",
            "WoOperationResourceId",
            "MaintenanceProgramId",
            "SupplierId",
            "HeaderInterfaceId",
            "InterfaceTransactionId",
            "InvoiceId",
            "HoldId",
            "InspectionId",
            "salesOrdersForOrderHubUniqID",
            "purchaseOrdersUniqID",
        )
    }
    record = {
        "ReferenceNumber": case,
        "RecordId": 10_000_000 + ordinal,
        "OrderNumber": f"ORD-{ordinal:04d}",
        "WorkOrderNumber": f"WO-{ordinal:04d}",
        "OrganizationCode": "SEA",
        "ItemNumber": f"NS-COMP-{ordinal:03d}",
        "Quantity": quantity,
        "StatusCode": "OPEN",
        "LastUpdateDate": f"{AS_OF_DATE.isoformat()}T08:00:00-08:00",
        **reference_ids,
    }
    if tool == "factorybench.context.get":
        return {}
    if tool == "gmail.messages.list":
        return {"messages": [{"id": f"msg-{ordinal:03d}", "threadId": f"thread-{ordinal:03d}"}], "resultSizeEstimate": 1}
    if tool == "gmail.messages.get":
        encoded = base64.urlsafe_b64encode(control_text.encode()).decode().rstrip("=")
        return {"id": f"msg-{ordinal:03d}", "threadId": f"thread-{ordinal:03d}", "labelIds": ["INBOX"], "snippet": scenario.outcome, "payload": {"headers": [{"name": "Subject", "value": f"{case} — evidence and requested action"}], "body": {"data": encoded, "size": len(control_text)}, "parts": [{"filename": "supplier-quotation.pdf", "body": {"attachmentId": f"att-{ordinal:03d}", "size": 1024}}]}}
    if tool == "gmail.threads.get":
        encoded = base64.urlsafe_b64encode(control_text.encode()).decode().rstrip("=")
        return {"id": f"thread-{ordinal:03d}", "historyId": str(900_000 + ordinal), "messages": [{"id": f"msg-{ordinal:03d}", "threadId": f"thread-{ordinal:03d}", "labelIds": ["INBOX"], "snippet": scenario.outcome, "payload": {"headers": [{"name": "Subject", "value": f"{case} — approved enterprise action"}], "body": {"data": encoded, "size": len(control_text)}}}]}
    if tool == "gmail.messages.attachments.get":
        content = f"Supplier quotation attachment for {case}: quantity {quantity}. {control_text}".encode()
        return {"size": len(content), "data": base64.urlsafe_b64encode(content).decode().rstrip("=")}
    if tool == "gmail.drafts.create":
        return {"id": f"draft-{ordinal:03d}", "message": {"id": f"draft-msg-{ordinal:03d}", "threadId": f"thread-{ordinal:03d}", "labelIds": ["DRAFT"]}}
    if tool == "gmail.messages.send":
        return {"id": f"sent-{ordinal:03d}", "threadId": f"thread-{ordinal:03d}", "labelIds": ["SENT"]}
    if tool.startswith("google_drive.files.list"):
        files = []
        for index, asset in enumerate(build_evidence(task_id, scenario, ordinal), start=1):
            if asset["path"] == "contract-or-service-control.md":
                file_id = f"drive-{ordinal:03d}"
            elif asset["path"] == "drive-approval-record.json":
                file_id = f"drive-approval-{ordinal:03d}"
            else:
                file_id = f"drive-{ordinal:03d}-{index:02d}"
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
        return {"kind": "drive#file", "id": f"drive-{ordinal:03d}", "name": "contract-or-service-control.md", "mimeType": "text/plain", "description": scenario.outcome, "content": control_text, "modifiedTime": f"{AS_OF_DATE.isoformat()}T09:00:00Z"}
    if tool == "google_drive.approvals.list":
        return {"approvals": [{"id": f"approval-{ordinal:03d}", "fileId": f"drive-approval-{ordinal:03d}", "status": "IN_PROGRESS", "reviewerResponses": [{"reviewer": "U-APPROVER", "response": "APPROVED", "comment": control_text}]}]}
    if tool == "google_drive.approvals.approve":
        return {"id": f"approval-{ordinal:03d}", "fileId": f"drive-approval-{ordinal:03d}", "status": "APPROVED"}
    if tool == "google_drive.comments.create":
        return {"id": f"comment-{ordinal:03d}", "content": arguments["requestBody"]["content"], "resolved": False}
    if tool == "google_sheets.spreadsheets.get":
        return {"spreadsheetId": f"sheet-{ordinal:03d}", "properties": {"title": f"{case} control workbook"}, "namedRanges": [{"namedRangeId": f"decision-{ordinal:03d}", "name": "ApprovedDecision"}], "developerMetadata": [{"metadataKey": "case", "metadataValue": case}, {"metadataKey": "approvalStatus", "metadataValue": "APPROVED"}, {"metadataKey": "approvedControlPacket", "metadataValue": _canonical(control_packet)}], "sheets": [{"properties": {"sheetId": 0, "title": "Control"}}]}
    if tool in {"google_sheets.spreadsheets.values.get", "google_sheets.spreadsheets.values.batchGet"}:
        values = [
            ["case", "record", "quantity", "approval", "approved_operation", "approved_arguments_json", "return_fields_json"],
            [case, f"NS-{ordinal:06d}", quantity, "APPROVED", scenario.primary_write, _canonical(approved_arguments), _canonical(answer)],
        ]
        if tool.endswith("batchGet"):
            return {"spreadsheetId": f"sheet-{ordinal:03d}", "valueRanges": [{"range": "Control!A1:E2", "majorDimension": "ROWS", "values": values}]}
        return {"range": "Control!A1:E2", "majorDimension": "ROWS", "values": values}
    if tool == "google_sheets.spreadsheets.values.update":
        return {"spreadsheetId": f"sheet-{ordinal:03d}", "updatedRange": arguments["range"], "updatedRows": 1, "updatedColumns": 1, "updatedCells": 1}
    if tool == "google_sheets.spreadsheets.values.append":
        return {"spreadsheetId": f"sheet-{ordinal:03d}", "tableRange": "Audit!A1:F20", "updates": {"updatedRange": "Audit!A21:F21", "updatedRows": 1, "updatedCells": 6}}
    if tool == "slack.search_messages":
        channel = _arguments("slack.conversations_history", ordinal, scenario)["channel"]
        return {"ok": True, "query": arguments["query"], "messages": {"total": 1, "matches": [{"channel": {"id": channel}, "ts": f"1768{ordinal:06d}.000100", "text": control_text, "user": "U-APPROVER"}]}}
    if tool in {"slack.conversations_history", "slack.conversations_replies"}:
        return {"ok": True, "messages": [{"ts": f"1768{ordinal:06d}.000100", "user": "U-OPS-LEAD", "text": f"{case}: evidence checked."}, {"ts": f"1768{ordinal:06d}.000200", "user": "U-APPROVER", "text": control_text}], "has_more": False, "response_metadata": {"next_cursor": ""}}
    if tool == "slack.files_info":
        return {"ok": True, "file": {"id": f"F-{ordinal:06d}", "name": "inspection-evidence.pdf", "mimetype": "application/pdf", "title": f"{case} inspection evidence", "preview": control_text}}
    if tool == "slack.chat_postMessage":
        return {"ok": True, "channel": arguments["channel"], "ts": f"1768{ordinal:06d}.000900", "message": {"text": arguments["text"], "thread_ts": arguments.get("thread_ts")}}
    if tool == "slack.reactions_add":
        return {"ok": True}
    if tool == "oracle_fusion.invoices.validate":
        return {"result": "The current action Validate Invoice has completed successfully."}
    if tool.startswith("oracle_fusion.") and tool.endswith(".list"):
        return {"items": [record], "count": 1, "hasMore": False, "limit": arguments.get("limit", 25), "offset": arguments.get("offset", 0), "links": []}
    if tool.startswith("oracle_fusion.") and tool in READ_TOOLS:
        return record
    if tool.startswith("oracle_fusion."):
        return {**record, "StatusCode": scenario.result_status.upper().replace(" ", "_"), "Operation": tool, "links": []}
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
        elif tool.startswith("google_drive.approvals"):
            labels.append("record the current reviewer's Drive approval")
        elif tool.startswith("google_drive.comments"):
            labels.append("add the Oracle result as a Drive comment")
    return "; then ".join(labels)


def _build_task(ordinal: int, scenario: Scenario) -> dict[str, Any]:
    task_id = f"factorybench-{ordinal:03d}"
    family_index = FAMILIES.index(scenario.family)
    pattern_index = ((ordinal - 1) + ((ordinal - 1) // 10) * 3) % len(EVIDENCE_PATTERNS)
    # Tasks 060 and 081 otherwise share the same coherent evidence route and
    # Oracle operation family. Use the adjacent evidence route for 081 instead
    # of injecting unrelated ERP reads merely to manufacture uniqueness.
    if ordinal == 81:
        pattern_index = (pattern_index + 1) % len(EVIDENCE_PATTERNS)
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
    for tool in (scenario.support_read, scenario.primary_read):
        if tool not in read_names:
            read_names.append(tool)
    tool_names = ["factorybench.context.get", *read_names, scenario.primary_write, *pattern_writes, "factorybench.submit_answer"]
    answer = _answer(scenario, ordinal)
    answer_schema = _answer_schema(answer)
    steps: list[dict[str, Any]] = []
    fixture_rows: list[dict[str, Any]] = []
    assertions: list[dict[str, Any]] = []
    write_number = 0
    for step_index, tool in enumerate(tool_names):
        arguments = deepcopy(answer) if tool == "factorybench.submit_answer" else _arguments(tool, ordinal, scenario)
        read_only = tool in READ_TOOLS
        step = {"tool": tool, "arguments": arguments, "control": read_only}
        steps.append(step)
        if tool in {"factorybench.context.get", "factorybench.submit_answer"}:
            continue
        response = _response(tool, ordinal, scenario, arguments)
        effect: dict[str, Any] | None = None
        if tool in WRITE_TOOLS:
            write_number += 1
            server = TOOL_BY_NAME[tool]["_meta"]["factorybench"]["server"]
            resource_id = f"{task_id}-mutation-{write_number:02d}"
            status = scenario.result_status if tool == scenario.primary_write else "Recorded"
            effect = {
                "task_id": task_id,
                "system": server,
                "resource_type": tool.rsplit(".", 1)[0],
                "resource_id": resource_id,
                "status": status,
                "effective_at": (AS_OF_DATE + timedelta(days=(ordinal % 19) + 1)).isoformat(),
                "payload_json": _canonical({"tool": tool, "arguments": arguments, "case": f"CASE-{ordinal:03d}", "outcome": scenario.outcome}),
                "revision": 1,
            }
            assertion_values = {
                "system": server,
                "resource_type": effect["resource_type"],
                "status": status,
                "revision": 1,
            }
            if tool == scenario.primary_write:
                assertion_values["payload_json"] = effect["payload_json"]
            assertions.append(
                {
                    "id": f"mutation_{write_number:02d}",
                    "description": f"{tool} produced the task-scoped, source-audited state transition.",
                    "table": "resource_state",
                    "where": {"task_id": task_id, "resource_id": resource_id},
                    "values": assertion_values,
                }
            )
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

    # The connected enterprise systems expose their documented read surface,
    # not only the calls in the reference trajectory. Seed task-scoped records
    # for those additional reads so alternate, reasonable discovery paths have
    # normal API behavior. They remain optional and do not alter the gold
    # sequence or read-before-write contract.
    seeded_tools = {row["tool_name"] for row in fixture_rows}
    for discovery_index, tool in enumerate(sorted(READ_TOOLS - {"factorybench.context.get"}), start=1):
        if tool in seeded_tools:
            continue
        arguments = _arguments(tool, ordinal, scenario)
        fixture_rows.append(
            {
                "fixture_id": f"{task_id}-discovery-{discovery_index:02d}",
                "task_id": task_id,
                "tool_name": tool,
                "arguments_json": _canonical(arguments),
                "response_json": _canonical(_response(tool, ordinal, scenario, arguments)),
                "effect_json": None,
                "read_only": 1,
            }
        )

    assets = build_evidence(task_id, scenario, ordinal)
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
    primary_read_arguments = _arguments(scenario.primary_read, ordinal, scenario)
    primary_path = TOOL_BY_NAME[scenario.primary_read]["_meta"]["factorybench"]["upstream"]["path"]
    primary_path_names = re.findall(r"\{([^{}]+)\}", primary_path)
    primary_resource_id = next(
        (str(primary_read_arguments[name]) for name in primary_path_names if name in primary_read_arguments),
        f"NS-{ordinal:06d}",
    )
    initial_record = {
        "task_id": task_id,
        "system": "oracle_fusion",
        "resource_type": scenario.primary_read.rsplit(".", 1)[0],
        "resource_id": primary_resource_id,
        "status": "Open",
        "effective_at": AS_OF_DATE.isoformat(),
        "payload_json": _canonical({"case": f"CASE-{ordinal:03d}", "record": f"NS-{ordinal:06d}", "quantity": 8 + ordinal % 37, "identifiers": primary_read_arguments}),
        "revision": 0,
    }
    required_read_calls = [
        {"tool": step["tool"], "arguments": deepcopy(step["arguments"]), "match": "successful_tool_call"}
        for step in steps
        if step["control"]
    ]
    evidence_names = ", ".join(f"`{asset['path']}`" for asset in assets[:8])
    instruction = (
        f"You are the {scenario.role.replace('_', ' ')} for Northstar Controls. Resolve {task_id.upper()} ({scenario.title}). "
        f"{scenario.outcome} The case is an isolated snapshot as of {AS_OF_DATE.isoformat()}; correlate immutable IDs and effective revisions rather than matching names alone. "
        f"Evidence is distributed across Oracle Fusion, Gmail, Drive, Sheets, and Slack, with inspectable files including {evidence_names}. "
        f"After the documented Oracle operation, {_communication_requirement(tuple(pattern_writes))}. "
        f"Return exactly: {', '.join(scenario.answer_keys)}."
    )
    return {
        "benchmark": BENCHMARK_NAME,
        "benchmark_version": BENCHMARK_VERSION,
        "task_id": task_id,
        "family": scenario.family,
        "variant": None,
        "level": "L3",
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
            "support_read": scenario.support_read,
            "primary_read": scenario.primary_read,
            "primary_write": scenario.primary_write,
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
        "required_reads": [step["tool"] for step in steps if step["control"]],
        "required_read_calls": required_read_calls,
        "answer_schema": answer_schema,
        "allowed_write_tables": ["resource_state", "answers", "audit_log"],
        "oracle_steps": steps,
        "expected": {"assertions": assertions, "answer": answer},
        "evaluation": {
            "metric": "FactoryScore",
            "definition": "100 × passed deterministic workflow checks / total checks",
            "checks": [
                "required evidence and system reads before mutation",
                "exact cross-system state transitions",
                "exact submitted answer fields",
                "write-scope containment",
                "error-free tool execution",
            ],
        },
        "sequence_signature": hashlib.sha256("\n".join(tool_names).encode()).hexdigest(),
    }


def task_tool_sequence(task: dict[str, Any], *, include_harness: bool = False) -> tuple[str, ...]:
    names = tuple(step["tool"] for step in task["oracle_steps"])
    if include_harness:
        return names
    return tuple(name for name in names if not name.startswith("factorybench."))


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
    system_counts = [len(task["world"]["systems"]) for task in tasks]
    asset_content_hashes: dict[str, set[str]] = {}
    for task in tasks:
        for asset in task["assets"]:
            asset_content_hashes.setdefault(asset["path"], set()).add(
                hashlib.sha256(asset["content"].encode()).hexdigest()
            )
    asset_role_unique_content_counts = {
        path: len(hashes) for path, hashes in sorted(asset_content_hashes.items())
    }
    return {
        "task_count": len(tasks),
        "unique_titles": len({task["title"] for task in tasks}),
        "unique_sequences": len(by_sequence),
        "duplicate_sequences": duplicate_sequences,
        "closest_pair": closest_pair,
        "minimum_assets_per_task": min(asset_counts),
        "maximum_assets_per_task": max(asset_counts),
        "asset_role_count": len(asset_content_hashes),
        "asset_role_unique_content_counts": asset_role_unique_content_counts,
        "asset_roles_with_unique_task_content": sum(
            count == len(tasks) for count in asset_role_unique_content_counts.values()
        ),
        "minimum_systems_per_task": min(system_counts),
        "unmapped_oracle_tools": generic_oracle_tools,
        "passed": (
            len(tasks) == 100
            and len({task["title"] for task in tasks}) == 100
            and not duplicate_sequences
            and closest_pair["similarity"] <= 0.82
            and min(asset_counts) >= 12
            and len(asset_content_hashes) >= 12
            and all(count == len(tasks) for count in asset_role_unique_content_counts.values())
            and min(system_counts) >= 5
            and not generic_oracle_tools
        ),
    }


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
    "catalog_quality_report",
    "get_task",
    "task_tool_sequence",
]
