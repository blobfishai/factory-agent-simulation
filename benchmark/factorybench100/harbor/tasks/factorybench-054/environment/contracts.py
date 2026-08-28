"""Version-pinned upstream API contracts used by the FactoryBench sandbox.

Every public tool below maps to one documented operation.  FactoryBench owns
the deterministic implementation and synthetic records; it does not rename a
business decision (for example, "approve invoice") into a pretend Oracle API.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


Json = dict[str, Any]

ORACLE_SCM = "https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fasrp/"
ORACLE_FINANCIALS = "https://docs.oracle.com/en/cloud/saas/financials/26a/farfa/"
GMAIL = "https://developers.google.com/workspace/gmail/api/reference/rest/v1/users"
DRIVE = "https://developers.google.com/workspace/drive/api/reference/rest/v3"
SHEETS = "https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets"
SLACK = "https://api.slack.com/methods"


def _object(properties: Json | None = None, required: list[str] | None = None) -> Json:
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
        "additionalProperties": False,
    }


def _string(description: str | None = None) -> Json:
    value: Json = {"type": "string"}
    if description:
        value["description"] = description
    return value


def _integer() -> Json:
    return {"type": "integer"}


def _number() -> Json:
    return {"type": "number"}


def _boolean() -> Json:
    return {"type": "boolean"}


LIST_SCHEMA = _object(
    {
        "q": _string("Documented Oracle REST query expression."),
        "finder": _string(),
        "fields": _string(),
        "expand": _string(),
        "orderBy": _string(),
        "limit": {"type": "integer", "minimum": 1},
        "offset": {"type": "integer", "minimum": 0},
        "onlyData": _boolean(),
        "totalResults": _boolean(),
    }
)


def _body_schema(properties: Json, required: list[str]) -> Json:
    return _object(properties, required)


def _contract(
    name: str,
    *,
    server: str,
    method: str,
    path: str,
    source: str,
    description: str,
    input_schema: Json,
    read_only: bool,
) -> Json:
    return {
        "name": name,
        "description": description,
        "inputSchema": input_schema,
        "annotations": {
            "title": name,
            "readOnlyHint": read_only,
            "destructiveHint": not read_only,
            "idempotentHint": read_only,
            "openWorldHint": False,
        },
        "_meta": {
            "factorybench": {
                "server": server,
                "implementation": "closed deterministic sandbox",
                "contractMode": "documented-operation",
                "upstream": {
                    "method": method,
                    "path": path,
                    "source": source,
                },
            }
        },
    }


def _oracle_list(
    name: str,
    resource: str,
    source_page: str,
    description: str,
    *,
    financials: bool = False,
) -> Json:
    return _contract(
        name,
        server="oracle_fusion",
        method="GET",
        path=f"/fscmRestApi/resources/11.13.18.05/{resource}",
        source=f"{ORACLE_FINANCIALS if financials else ORACLE_SCM}{source_page}",
        description=description,
        input_schema=deepcopy(LIST_SCHEMA),
        read_only=True,
    )


def _oracle_get(
    name: str,
    path: str,
    source_page: str,
    parameter: str,
    description: str,
    *,
    financials: bool = False,
) -> Json:
    properties = {
        parameter: _string() if "Id" not in parameter or parameter.endswith("UniqID") else _integer(),
        "fields": _string(),
        "expand": _string(),
        "onlyData": _boolean(),
    }
    return _contract(
        name,
        server="oracle_fusion",
        method="GET",
        path=path,
        source=f"{ORACLE_FINANCIALS if financials else ORACLE_SCM}{source_page}",
        description=description,
        input_schema=_object(properties, [parameter]),
        read_only=True,
    )


def _oracle_write(
    name: str,
    *,
    method: str,
    path: str,
    source_page: str,
    body_properties: Json,
    body_required: list[str],
    description: str,
    path_properties: Json | None = None,
    path_required: list[str] | None = None,
    financials: bool = False,
) -> Json:
    properties = dict(path_properties or {})
    properties["requestBody"] = _body_schema(body_properties, body_required)
    return _contract(
        name,
        server="oracle_fusion",
        method=method,
        path=path,
        source=f"{ORACLE_FINANCIALS if financials else ORACLE_SCM}{source_page}",
        description=description,
        input_schema=_object(properties, [*(path_required or []), "requestBody"]),
        read_only=False,
    )


def _collection_contracts() -> list[Json]:
    work_order_body = {
        "OrganizationCode": _string(),
        "WorkOrderNumber": _string(),
        "ItemNumber": _string(),
        "WorkOrderQuantity": _number(),
        "WorkOrderStatusCode": _string(),
        "PlannedStartDate": _string(),
        "PlannedCompletionDate": _string(),
    }
    maintenance_body = {
        "OrganizationCode": _string(),
        "WorkOrderNumber": _string(),
        "AssetNumber": _string(),
        "WorkOrderDescription": _string(),
        "WorkOrderTypeCode": _string(),
        "WorkOrderStatusCode": _string(),
        "PlannedStartDate": _string(),
        "PlannedCompletionDate": _string(),
    }
    program_body = {
        "MaintenanceProgramCode": _string(),
        "MaintenanceProgramName": _string(),
        "OrganizationCode": _string(),
        "StatusCode": _string(),
        "ForecastStartDate": _string(),
        "ForecastEndDate": _string(),
    }
    invoice_body = {
        "BusinessUnit": _string(),
        "Supplier": _string(),
        "SupplierSite": _string(),
        "InvoiceNumber": _string(),
        "InvoiceDate": _string(),
        "InvoiceAmount": _number(),
        "InvoiceCurrency": _string(),
        "PaymentTerms": _string(),
    }
    contracts: list[Json] = []

    for name, resource, page, description in (
        ("oracle_fusion.work_orders.list", "workOrders", "api-manufacturing-discrete-work-orders.html", "Get discrete manufacturing work orders."),
        ("oracle_fusion.maintenance_work_orders.list", "maintenanceWorkOrders", "api-maintenance-maintenance-work-orders.html", "Get maintenance work orders."),
        ("oracle_fusion.maintenance_programs.list", "maintenancePrograms", "api-maintenance-maintenance-programs.html", "Get maintenance programs."),
        ("oracle_fusion.inventory_onhand_balances.list", "inventoryOnhandBalances", "api-inventory-management-inventory-on-hand-balances.html", "Get inventory on-hand balances."),
        ("oracle_fusion.cycle_count_definitions.list", "cycleCountDefinitions", "op-cyclecountdefinitions-get.html", "Get cycle-count definitions and approval tolerances."),
        ("oracle_fusion.cycle_count_sequence_details.list", "cycleCountSequenceDetails", "op-cyclecountsequencedetails-get.html", "Get cycle-count sequence quantities, recounts, and approval status."),
        ("oracle_fusion.supply_requests.list", "supplyRequests", "api-inventory-management-supply-requests.html", "Get supply requests."),
        ("oracle_fusion.receiving_receipt_requests.list", "receivingReceiptRequests", "api-inventory-management-receiving-receipt-requests.html", "Get receiving receipt requests."),
        ("oracle_fusion.quality_inspection_results.list", "inspectionResults", "api-quality-inspection-results.html", "Get quality inspection results."),
        ("oracle_fusion.inspection_plans.list", "inspectionPlans", "api-quality-inspection-plans.html", "Get quality inspection plans."),
        ("oracle_fusion.purchase_orders.list", "purchaseOrders", "api-procurement-purchase-orders.html", "Get purchase orders."),
        ("oracle_fusion.draft_purchase_orders.list", "draftPurchaseOrders", "api-procurement-draft-purchase-orders.html", "Get draft purchase orders."),
        ("oracle_fusion.suppliers.list", "suppliers", "api-procurement-suppliers.html", "Get suppliers."),
        ("oracle_fusion.sales_orders.list", "salesOrdersForOrderHub", "api-order-management-sales-orders-for-order-hub.html", "Get sales orders from Order Management."),
    ):
        contracts.append(_oracle_list(name, resource, page, description))
    contracts.append(
        _oracle_list(
            "oracle_fusion.invoices.list",
            "invoices",
            "op-invoices-get.html",
            "Get Payables invoices.",
            financials=True,
        )
    )

    contracts.extend(
        [
            _oracle_get("oracle_fusion.work_orders.get", "/fscmRestApi/resources/11.13.18.05/workOrders/{WorkOrderId}", "op-workorders-workorderid-get.html", "WorkOrderId", "Get one discrete work order."),
            _oracle_get("oracle_fusion.maintenance_work_orders.get", "/fscmRestApi/resources/11.13.18.05/maintenanceWorkOrders/{WorkOrderId}", "op-maintenanceworkorders-workorderid-get.html", "WorkOrderId", "Get one maintenance work order."),
            _oracle_get("oracle_fusion.maintenance_programs.get", "/fscmRestApi/resources/11.13.18.05/maintenancePrograms/{MaintenanceProgramId}", "api-maintenance-maintenance-programs.html", "MaintenanceProgramId", "Get one maintenance program."),
            _oracle_get("oracle_fusion.purchase_orders.get", "/fscmRestApi/resources/11.13.18.05/purchaseOrders/{purchaseOrdersUniqID}", "api-procurement-purchase-orders.html", "purchaseOrdersUniqID", "Get one purchase order."),
            _oracle_get("oracle_fusion.suppliers.get", "/fscmRestApi/resources/11.13.18.05/suppliers/{SupplierId}", "api-procurement-suppliers.html", "SupplierId", "Get one supplier."),
            _oracle_get("oracle_fusion.sales_orders.get", "/fscmRestApi/resources/11.13.18.05/salesOrdersForOrderHub/{salesOrdersForOrderHubUniqID}", "api-order-management-sales-orders-for-order-hub.html", "salesOrdersForOrderHubUniqID", "Get one sales order."),
            _oracle_get("oracle_fusion.invoices.get", "/fscmRestApi/resources/11.13.18.05/invoices/{invoicesUniqID}", "op-invoices-invoicesuniqid-get.html", "invoicesUniqID", "Get one Payables invoice.", financials=True),
        ]
    )

    contracts.extend(
        [
            _oracle_write(
                "oracle_fusion.work_orders.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/workOrders", source_page="op-workorders-post.html", body_properties=work_order_body, body_required=["OrganizationCode", "ItemNumber", "WorkOrderQuantity", "PlannedStartDate", "PlannedCompletionDate"], description="Create one discrete manufacturing work order."
            ),
            _oracle_write(
                "oracle_fusion.work_orders.update", method="PATCH", path="/fscmRestApi/resources/11.13.18.05/workOrders/{WorkOrderId}", source_page="op-workorders-workorderid-patch.html", path_properties={"WorkOrderId": _integer()}, path_required=["WorkOrderId"], body_properties=work_order_body, body_required=[], description="Update one discrete manufacturing work order."
            ),
            _oracle_write(
                "oracle_fusion.maintenance_work_orders.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/maintenanceWorkOrders", source_page="op-maintenanceworkorders-post.html", body_properties=maintenance_body, body_required=["OrganizationCode", "AssetNumber", "WorkOrderDescription", "WorkOrderTypeCode", "PlannedStartDate"], description="Create one maintenance work order."
            ),
            _oracle_write(
                "oracle_fusion.maintenance_work_orders.update", method="PATCH", path="/fscmRestApi/resources/11.13.18.05/maintenanceWorkOrders/{WorkOrderId}", source_page="op-maintenanceworkorders-workorderid-patch.html", path_properties={"WorkOrderId": _integer()}, path_required=["WorkOrderId"], body_properties=maintenance_body, body_required=[], description="Update one maintenance work order."
            ),
            _oracle_write(
                "oracle_fusion.maintenance_programs.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/maintenancePrograms", source_page="api-maintenance-maintenance-programs.html", body_properties=program_body, body_required=["MaintenanceProgramCode", "MaintenanceProgramName", "OrganizationCode"], description="Create one maintenance program."
            ),
            _oracle_write(
                "oracle_fusion.maintenance_programs.update", method="PATCH", path="/fscmRestApi/resources/11.13.18.05/maintenancePrograms/{MaintenanceProgramId}", source_page="api-maintenance-maintenance-programs.html", path_properties={"MaintenanceProgramId": _integer()}, path_required=["MaintenanceProgramId"], body_properties=program_body, body_required=[], description="Update one maintenance program."
            ),
            _oracle_write(
                "oracle_fusion.invoices.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/invoices", source_page="op-invoices-post.html", body_properties=invoice_body, body_required=["BusinessUnit", "Supplier", "InvoiceNumber", "InvoiceAmount", "InvoiceCurrency"], description="Create one Payables invoice.", financials=True
            ),
            _oracle_write(
                "oracle_fusion.invoices.update", method="PATCH", path="/fscmRestApi/resources/11.13.18.05/invoices/{invoicesUniqID}", source_page="op-invoices-invoicesuniqid-patch.html", path_properties={"invoicesUniqID": _string()}, path_required=["invoicesUniqID"], body_properties=invoice_body, body_required=[], description="Update one Payables invoice.", financials=True
            ),
            _oracle_write(
                "oracle_fusion.draft_purchase_orders.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/draftPurchaseOrders", source_page="op-draftpurchaseorders-post.html", body_properties={"SupplierId": _integer(), "SupplierSiteId": _integer(), "ProcurementBUId": _integer(), "RequisitioningBUId": _integer(), "BuyerId": _integer(), "DocumentStyleId": _integer(), "CurrencyCode": _string(), "Description": _string(), "RequiredAcknowledgment": _string(), "lines": {"type": "array", "items": {"type": "object"}}}, body_required=["SupplierId", "ProcurementBUId", "BuyerId", "DocumentStyleId", "lines"], description="Create a draft purchase order at the documented resource."
            ),
            _oracle_write(
                "oracle_fusion.quality_inspection_results.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/inspectionResults", source_page="api-quality-inspection-results.html", body_properties={"OrganizationCode": _string(), "InspectionPlanName": _string(), "InspectionPlanId": _integer(), "DocumentType": _string(), "DocumentNumber": _string(), "ItemNumber": _string(), "Quantity": _number(), "LotNumber": _string(), "InspectionStatus": _string(), "samples": {"type": "array", "items": {"type": "object"}}}, body_required=["OrganizationCode", "InspectionPlanName", "DocumentType", "DocumentNumber"], description="Create one quality inspection result."
            ),
            _oracle_write(
                "oracle_fusion.quality_inspection_results.update", method="PATCH", path="/fscmRestApi/resources/11.13.18.05/inspectionResults/{InspectionId}", source_page="api-quality-inspection-results.html", path_properties={"InspectionId": _integer()}, path_required=["InspectionId"], body_properties={"InspectionStatus": _string(), "InspectionResult": _string(), "QuantityAccepted": _number(), "QuantityRejected": _number(), "samples": {"type": "array", "items": {"type": "object"}}}, body_required=[], description="Update one quality inspection result."
            ),
        ]
    )
    return contracts


def _child_and_transaction_contracts() -> list[Json]:
    contracts: list[Json] = []
    child_specs = (
        ("oracle_fusion.work_order_operations.list", "/workOrders/{WorkOrderId}/child/WorkOrderOperation", "WorkOrderId", "Get active operations for a discrete work order."),
        ("oracle_fusion.work_order_materials.list", "/workOrders/{WorkOrderId}/child/WorkOrderMaterial", "WorkOrderId", "Get materials for a discrete work order."),
        ("oracle_fusion.work_order_resources.list", "/workOrders/{WorkOrderId}/child/WorkOrderResource", "WorkOrderId", "Get resources for a discrete work order."),
        ("oracle_fusion.maintenance_operations.list", "/maintenanceWorkOrders/{WorkOrderId}/child/WorkOrderOperation", "WorkOrderId", "Get operations for a maintenance work order."),
        ("oracle_fusion.maintenance_materials.list", "/maintenanceWorkOrders/{WorkOrderId}/child/WorkOrderMaterial", "WorkOrderId", "Get material requirements for a maintenance work order."),
        ("oracle_fusion.maintenance_resources.list", "/maintenanceWorkOrders/{WorkOrderId}/child/WorkOrderResource", "WorkOrderId", "Get labor and equipment resources for a maintenance work order."),
        ("oracle_fusion.maintenance_documents.list", "/maintenanceWorkOrders/{WorkOrderId}/child/documentReference", "WorkOrderId", "Get document references for a maintenance work order."),
        ("oracle_fusion.cycle_count_history.list", "/cycleCountSequenceDetails/{cycleCountSequenceDetailsUniqID}/child/history", "cycleCountSequenceDetailsUniqID", "Get the independently recorded count history for one cycle-count sequence."),
        ("oracle_fusion.receiving_receipt_transactions.list", "/receivingReceiptRequests/{HeaderInterfaceId}/child/lines", "HeaderInterfaceId", "Get receiving transaction requests."),
        ("oracle_fusion.purchase_order_lines.list", "/purchaseOrders/{purchaseOrdersUniqID}/child/lines", "purchaseOrdersUniqID", "Get purchase-order lines."),
    )
    for name, suffix, parameter, description in child_specs:
        schema = deepcopy(LIST_SCHEMA)
        schema["properties"][parameter] = _string() if parameter.endswith("UniqID") else _integer()
        schema["required"] = [parameter]
        contracts.append(
            _contract(
                name,
                server="oracle_fusion",
                method="GET",
                path=f"/fscmRestApi/resources/11.13.18.05{suffix}",
                source=f"{ORACLE_SCM}toc.htm",
                description=description,
                input_schema=schema,
                read_only=True,
            )
        )

    mutation_specs = (
        ("oracle_fusion.work_order_operations.update", "PATCH", "/workOrders/{WorkOrderId}/child/WorkOrderOperation/{WoOperationId}", {"WorkOrderId": _integer(), "WoOperationId": _integer()}, {"WorkCenterCode": _string(), "PlannedStartDate": _string(), "PlannedCompletionDate": _string(), "OperationName": _string()}, "Update one active work-order operation."),
        ("oracle_fusion.work_order_materials.update", "PATCH", "/workOrders/{WorkOrderId}/child/WorkOrderMaterial/{WoOperationMaterialId}", {"WorkOrderId": _integer(), "WoOperationMaterialId": _integer()}, {"Quantity": _number(), "SupplySubinventory": _string(), "ItemNumber": _string()}, "Update one work-order material."),
        ("oracle_fusion.work_order_resources.update", "PATCH", "/workOrders/{WorkOrderId}/child/WorkOrderResource/{WoOperationResourceId}", {"WorkOrderId": _integer(), "WoOperationResourceId": _integer()}, {"ResourceCode": _string(), "UsageRate": _number(), "AssignedUnits": _number()}, "Update one work-order resource."),
        ("oracle_fusion.maintenance_operations.update", "PATCH", "/maintenanceWorkOrders/{WorkOrderId}/child/WorkOrderOperation/{WoOperationId}", {"WorkOrderId": _integer(), "WoOperationId": _integer()}, {"WorkCenterCode": _string(), "OperationName": _string(), "PlannedStartDate": _string()}, "Update one maintenance operation."),
        ("oracle_fusion.receiving_receipt_transactions.update", "PATCH", "/receivingReceiptRequests/{HeaderInterfaceId}/child/lines/{InterfaceTransactionId}", {"HeaderInterfaceId": _integer(), "InterfaceTransactionId": _integer()}, {"TransactionType": _string(), "Quantity": _number(), "InspectionQualityCode": _string(), "Comments": _string()}, "Update one receiving transaction request."),
    )
    for name, method, suffix, path_props, body_props, description in mutation_specs:
        contracts.append(
            _oracle_write(
                name,
                method=method,
                path=f"/fscmRestApi/resources/11.13.18.05{suffix}",
                source_page="toc.htm",
                path_properties=path_props,
                path_required=list(path_props),
                body_properties=body_props,
                body_required=[],
                description=description,
            )
        )

    contracts.extend(
        [
            _oracle_write(
                "oracle_fusion.work_order_operations.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/workOrders/{WorkOrderId}/child/WorkOrderOperation", source_page="api-manufacturing-discrete-work-orders-active-operations.html", path_properties={"WorkOrderId": _integer()}, path_required=["WorkOrderId"], body_properties={"OperationSequenceNumber": _integer(), "OperationName": _string(), "WorkCenterCode": _string(), "PlannedStartDate": _string(), "PlannedCompletionDate": _string()}, body_required=["OperationSequenceNumber", "OperationName", "WorkCenterCode"], description="Create an active operation for a discrete work order."
            ),
            _oracle_write(
                "oracle_fusion.work_order_resources.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/workOrders/{WorkOrderId}/child/WorkOrderOperation/{WoOperationId}/child/WorkOrderOperationResource", source_page="api-manufacturing-discrete-work-orders-active-operations-resources.html", path_properties={"WorkOrderId": _integer(), "WoOperationId": _integer()}, path_required=["WorkOrderId", "WoOperationId"], body_properties={"ResourceCode": _string(), "UsageRate": _number(), "AssignedUnits": _number(), "BasisType": _string()}, body_required=["ResourceCode"], description="Create a resource requirement for a work-order operation."
            ),
            _oracle_write(
                "oracle_fusion.work_order_materials.replace_with_substitute", method="POST", path="/fscmRestApi/resources/11.13.18.05/workOrders/{WorkOrderId}/child/WorkOrderOperation/{WoOperationId}/child/WorkOrderOperationMaterial/{WoOperationMaterialId}/action/replaceWithSubstitute", source_page="api-manufacturing-discrete-work-orders-active-operations-work-order-materials.html", path_properties={"WorkOrderId": _integer(), "WoOperationId": _integer(), "WoOperationMaterialId": _integer()}, path_required=["WorkOrderId", "WoOperationId", "WoOperationMaterialId"], body_properties={"SubstituteItemNumber": _string(), "SubstituteQuantity": _number()}, body_required=["SubstituteItemNumber"], description="Replace a work-order material with a documented substitute."
            ),
            _oracle_write(
                "oracle_fusion.material_transactions.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/materialTransactions", source_page="op-materialtransactions-post.html", body_properties={"SourceSystemCode": _string(), "SourceSystemType": _string(), "MaterialTransactionDetail": {"type": "array", "items": {"type": "object"}}}, body_required=["SourceSystemCode", "MaterialTransactionDetail"], description="Create work-order material transactions."
            ),
            _oracle_write(
                "oracle_fusion.operation_transactions.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/operationTransactions", source_page="op-operationtransactions-post.html", body_properties={"SourceSystemCode": _string(), "SourceSystemType": _string(), "OperationTransactionDetail": {"type": "array", "items": {"type": "object"}}}, body_required=["SourceSystemCode", "OperationTransactionDetail"], description="Create work-order operation transactions."
            ),
            _oracle_write(
                "oracle_fusion.resource_transactions.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/resourceTransactions", source_page="api-manufacturing-work-order-resource-transactions.html", body_properties={"SourceSystemCode": _string(), "ResourceTransactionDetail": {"type": "array", "items": {"type": "object"}}}, body_required=["SourceSystemCode", "ResourceTransactionDetail"], description="Create work-order resource transactions."
            ),
            _oracle_write(
                "oracle_fusion.inventory_transactions.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/inventoryTransactions", source_page="op-inventorytransactions-post.html", body_properties={"SourceSystemCode": _string(), "TransactionLines": {"type": "array", "items": {"type": "object"}}, "TransactionMode": _string()}, body_required=["SourceSystemCode", "TransactionLines"], description="Create inventory transactions."
            ),
            _oracle_write(
                "oracle_fusion.supply_requests.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/supplyRequests", source_page="api-inventory-management-supply-requests.html", body_properties={"SupplyOrderReferenceNumber": _string(), "SupplyRequestSystem": _string(), "SupplyRequestDate": _string(), "supplyRequestLines": {"type": "array", "items": {"type": "object"}}}, body_required=["SupplyOrderReferenceNumber", "SupplyRequestSystem", "SupplyRequestDate", "supplyRequestLines"], description="Create one supply request."
            ),
            _oracle_write(
                "oracle_fusion.receiving_receipt_requests.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/receivingReceiptRequests", source_page="op-receivingreceipttransactionrequests-post.html", body_properties={"ReceiptSourceCode": _string(), "OrganizationCode": _string(), "VendorName": _string(), "EmployeeId": _integer(), "lines": {"type": "array", "items": {"type": "object"}}}, body_required=["ReceiptSourceCode", "OrganizationCode", "lines"], description="Create a receiving receipt request."
            ),
            _oracle_write(
                "oracle_fusion.receiving_receipt_transactions.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/receivingReceiptRequests/{HeaderInterfaceId}/child/lines", source_page="api-inventory-management-receiving-receipt-requests-requests-receiving-transactions.html", path_properties={"HeaderInterfaceId": _integer()}, path_required=["HeaderInterfaceId"], body_properties={"TransactionType": _string(), "Quantity": _number(), "ItemNumber": _string(), "InspectionQualityCode": _string(), "lotItemLots": {"type": "array", "items": {"type": "object"}}}, body_required=["TransactionType", "Quantity"], description="Create a receiving transaction request."
            ),
            _oracle_write(
                "oracle_fusion.maintenance_documents.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/maintenanceWorkOrders/{WorkOrderId}/child/documentReference", source_page="api-maintenance-maintenance-work-orders-document-references.html", path_properties={"WorkOrderId": _integer()}, path_required=["WorkOrderId"], body_properties={"DocumentName": _string(), "DocumentNumber": _string(), "DocumentType": _string(), "Description": _string()}, body_required=["DocumentName", "DocumentType"], description="Create a maintenance work-order document reference."
            ),
        ]
    )
    return contracts


def _action_contracts() -> list[Json]:
    return [
        _oracle_write(
            "oracle_fusion.invoices.validate", method="POST", path="/fscmRestApi/resources/11.13.18.05/invoices/action/validateInvoice", source_page="op-invoices-action-validateinvoice-post.html", financials=True, body_properties={"ProcessAction": {"type": "string", "const": "Validate"}, "BusinessUnit": _string(), "Supplier": _string(), "InvoiceNumber": _string()}, body_required=["ProcessAction", "BusinessUnit", "Supplier", "InvoiceNumber"], description="Validate an invoice; Oracle checks tax and matching tolerances and may place holds."
        ),
        _oracle_write(
            "oracle_fusion.invoice_holds.create", method="POST", path="/fscmRestApi/resources/11.13.18.05/invoiceHolds", source_page="api-invoice-holds.html", financials=True, body_properties={"InvoiceId": _integer(), "HoldName": _string(), "HoldReason": _string()}, body_required=["InvoiceId", "HoldName"], description="Create one Payables invoice hold."
        ),
        _oracle_write(
            "oracle_fusion.invoice_holds.update", method="PATCH", path="/fscmRestApi/resources/11.13.18.05/invoiceHolds/{HoldId}", source_page="api-invoice-holds.html", financials=True, path_properties={"HoldId": _integer()}, path_required=["HoldId"], body_properties={"ReleaseName": _string(), "ReleaseReason": _string()}, body_required=["ReleaseName"], description="Update one Payables invoice hold, including release details."
        ),
        _oracle_write(
            "oracle_fusion.purchase_orders.acknowledge", method="POST", path="/fscmRestApi/resources/11.13.18.05/purchaseOrders/{purchaseOrdersUniqID}/action/acknowledge", source_page="api-procurement-purchase-orders.html", path_properties={"purchaseOrdersUniqID": _string()}, path_required=["purchaseOrdersUniqID"], body_properties={"supplierOrder": _string(), "acknowledgementNote": _string()}, body_required=[], description="Record supplier acknowledgment for a purchase order."
        ),
        _oracle_write(
            "oracle_fusion.purchase_orders.close", method="POST", path="/fscmRestApi/resources/11.13.18.05/purchaseOrders/{purchaseOrdersUniqID}/action/close", source_page="api-procurement-purchase-orders.html", path_properties={"purchaseOrdersUniqID": _string()}, path_required=["purchaseOrdersUniqID"], body_properties={"closeAction": {"type": "string", "enum": ["closeForReceiving", "closeForInvoicing", "close", "finallyClose"]}, "closeReason": _string()}, body_required=["closeAction"], description="Close a purchase order using a documented close action."
        ),
        _oracle_write(
            "oracle_fusion.purchase_orders.cancel", method="POST", path="/fscmRestApi/resources/11.13.18.05/purchaseOrders/{purchaseOrdersUniqID}/action/cancel", source_page="api-procurement-purchase-orders.html", path_properties={"purchaseOrdersUniqID": _string()}, path_required=["purchaseOrdersUniqID"], body_properties={"cancellationReason": _string(), "cancelUnfulfilledDemandFlag": _boolean(), "initiatingParty": {"type": "string", "enum": ["buyer", "requester", "supplier"]}}, body_required=["cancellationReason"], description="Cancel a purchase order."
        ),
        _oracle_write(
            "oracle_fusion.maintenance_programs.generate_forecasts", method="POST", path="/fscmRestApi/resources/11.13.18.05/maintenancePrograms/action/generateProgramForecasts", source_page="api-maintenance-maintenance-programs.html", body_properties={"MaintenanceProgramCode": _string(), "ForecastStartDate": _string(), "ForecastEndDate": _string()}, body_required=["MaintenanceProgramCode"], description="Generate maintenance-program forecasts."
        ),
        _oracle_write(
            "oracle_fusion.maintenance_programs.generate_work_orders", method="POST", path="/fscmRestApi/resources/11.13.18.05/maintenancePrograms/action/generateProgramWorkOrders", source_page="api-maintenance-maintenance-programs.html", body_properties={"MaintenanceProgramCode": _string(), "WorkOrderStartDate": _string(), "WorkOrderEndDate": _string()}, body_required=["MaintenanceProgramCode"], description="Generate maintenance work orders from a program forecast."
        ),
    ]


def _workspace_contracts() -> list[Json]:
    raw_message = _object({"raw": _string(), "threadId": _string()}, ["raw"])
    contracts = [
        _contract("gmail.messages.list", server="gmail", method="GET", path="/gmail/v1/users/{userId}/messages", source=f"{GMAIL}.messages/list", description="Search messages using Gmail's q grammar.", input_schema=_object({"userId": _string(), "q": _string(), "labelIds": {"type": "array", "items": _string()}, "maxResults": _integer(), "pageToken": _string(), "includeSpamTrash": _boolean()}, ["userId"]), read_only=True),
        _contract("gmail.messages.get", server="gmail", method="GET", path="/gmail/v1/users/{userId}/messages/{id}", source=f"{GMAIL}.messages/get", description="Get one Gmail message.", input_schema=_object({"userId": _string(), "id": _string(), "format": {"type": "string", "enum": ["minimal", "full", "raw", "metadata"]}, "metadataHeaders": {"type": "array", "items": _string()}}, ["userId", "id"]), read_only=True),
        _contract("gmail.messages.attachments.get", server="gmail", method="GET", path="/gmail/v1/users/{userId}/messages/{messageId}/attachments/{id}", source=f"{GMAIL}.messages.attachments/get", description="Get an externalized Gmail attachment body.", input_schema=_object({"userId": _string(), "messageId": _string(), "id": _string()}, ["userId", "messageId", "id"]), read_only=True),
        _contract("gmail.threads.get", server="gmail", method="GET", path="/gmail/v1/users/{userId}/threads/{id}", source=f"{GMAIL}.threads/get", description="Get one Gmail thread.", input_schema=_object({"userId": _string(), "id": _string(), "format": _string(), "metadataHeaders": {"type": "array", "items": _string()}}, ["userId", "id"]), read_only=True),
        _contract("gmail.drafts.get", server="gmail", method="GET", path="/gmail/v1/users/{userId}/drafts/{id}", source=f"{GMAIL}.drafts/get", description="Get one Gmail draft and its current message.", input_schema=_object({"userId": _string(), "id": _string(), "format": {"type": "string", "enum": ["minimal", "full", "raw", "metadata"]}}, ["userId", "id"]), read_only=True),
        _contract("gmail.drafts.create", server="gmail", method="POST", path="/gmail/v1/users/{userId}/drafts", source=f"{GMAIL}.drafts/create", description="Create a Gmail draft from a base64url RFC 2822 message.", input_schema=_object({"userId": _string(), "message": raw_message}, ["userId", "message"]), read_only=False),
        _contract("gmail.messages.send", server="gmail", method="POST", path="/gmail/v1/users/{userId}/messages/send", source=f"{GMAIL}.messages/send", description="Send a base64url RFC 2822 Gmail message.", input_schema=_object({"userId": _string(), "raw": _string(), "threadId": _string()}, ["userId", "raw"]), read_only=False),
        _contract("google_drive.files.list", server="google_drive", method="GET", path="/drive/v3/files", source=f"{DRIVE}/files/list", description="Search Drive files using the q grammar.", input_schema=_object({"q": _string(), "spaces": _string(), "orderBy": _string(), "pageSize": _integer(), "pageToken": _string(), "fields": _string()}), read_only=True),
        _contract("google_drive.files.get", server="google_drive", method="GET", path="/drive/v3/files/{fileId}", source=f"{DRIVE}/files/get", description="Get Drive file metadata or media.", input_schema=_object({"fileId": _string(), "alt": _string(), "fields": _string(), "acknowledgeAbuse": _boolean()}, ["fileId"]), read_only=True),
        _contract("google_drive.files.download", server="google_drive", method="POST", path="/drive/v3/files/{fileId}/download", source=f"{DRIVE}/files/download", description="Download file content from Drive.", input_schema=_object({"fileId": _string()}, ["fileId"]), read_only=True),
        _contract("google_drive.files.export", server="google_drive", method="GET", path="/drive/v3/files/{fileId}/export", source=f"{DRIVE}/files/export", description="Export a Google Workspace document.", input_schema=_object({"fileId": _string(), "mimeType": _string()}, ["fileId", "mimeType"]), read_only=True),
        _contract("google_drive.comments.list", server="google_drive", method="GET", path="/drive/v3/files/{fileId}/comments", source=f"{DRIVE}/comments/list", description="List comments on a Drive file.", input_schema=_object({"fileId": _string(), "pageSize": _integer(), "pageToken": _string(), "includeDeleted": _boolean(), "fields": _string()}, ["fileId"]), read_only=True),
        _contract("google_drive.comments.get", server="google_drive", method="GET", path="/drive/v3/files/{fileId}/comments/{commentId}", source=f"{DRIVE}/comments/get", description="Get one Drive comment.", input_schema=_object({"fileId": _string(), "commentId": _string(), "includeDeleted": _boolean(), "fields": _string()}, ["fileId", "commentId"]), read_only=True),
        _contract("google_drive.comments.create", server="google_drive", method="POST", path="/drive/v3/files/{fileId}/comments", source=f"{DRIVE}/comments/create", description="Create a comment on a Drive file.", input_schema=_object({"fileId": _string(), "requestBody": _object({"content": _string()}, ["content"])}, ["fileId", "requestBody"]), read_only=False),
        _contract("google_sheets.spreadsheets.get", server="google_sheets", method="GET", path="/v4/spreadsheets/{spreadsheetId}", source=f"{SHEETS}/get", description="Get a spreadsheet.", input_schema=_object({"spreadsheetId": _string(), "ranges": {"type": "array", "items": _string()}, "includeGridData": _boolean(), "fields": _string()}, ["spreadsheetId"]), read_only=True),
        _contract("google_sheets.spreadsheets.values.get", server="google_sheets", method="GET", path="/v4/spreadsheets/{spreadsheetId}/values/{range}", source=f"{SHEETS}.values/get", description="Get values from a spreadsheet range.", input_schema=_object({"spreadsheetId": _string(), "range": _string(), "majorDimension": _string(), "valueRenderOption": _string(), "dateTimeRenderOption": _string()}, ["spreadsheetId", "range"]), read_only=True),
        _contract("google_sheets.spreadsheets.values.batchGet", server="google_sheets", method="GET", path="/v4/spreadsheets/{spreadsheetId}/values:batchGet", source=f"{SHEETS}.values/batchGet", description="Get multiple spreadsheet ranges.", input_schema=_object({"spreadsheetId": _string(), "ranges": {"type": "array", "items": _string()}, "majorDimension": _string(), "valueRenderOption": _string()}, ["spreadsheetId", "ranges"]), read_only=True),
        _contract("google_sheets.spreadsheets.values.update", server="google_sheets", method="PUT", path="/v4/spreadsheets/{spreadsheetId}/values/{range}", source=f"{SHEETS}.values/update", description="Set values in a spreadsheet range.", input_schema=_object({"spreadsheetId": _string(), "range": _string(), "valueInputOption": _string(), "includeValuesInResponse": _boolean(), "requestBody": _object({"range": _string(), "majorDimension": _string(), "values": {"type": "array", "items": {"type": "array"}}}, ["values"])}, ["spreadsheetId", "range", "valueInputOption", "requestBody"]), read_only=False),
        _contract("google_sheets.spreadsheets.values.append", server="google_sheets", method="POST", path="/v4/spreadsheets/{spreadsheetId}/values/{range}:append", source=f"{SHEETS}.values/append", description="Append values to a spreadsheet table.", input_schema=_object({"spreadsheetId": _string(), "range": _string(), "valueInputOption": _string(), "insertDataOption": _string(), "requestBody": _object({"range": _string(), "majorDimension": _string(), "values": {"type": "array", "items": {"type": "array"}}}, ["values"])}, ["spreadsheetId", "range", "valueInputOption", "requestBody"]), read_only=False),
        _contract("slack.search_messages", server="slack", method="GET", path="/api/search.messages", source=f"{SLACK}/search.messages", description="Search Slack messages visible to the caller.", input_schema=_object({"query": _string(), "count": _integer(), "page": _integer(), "sort": _string(), "sort_dir": _string()}, ["query"]), read_only=True),
        _contract("slack.conversations_history", server="slack", method="GET", path="/api/conversations.history", source=f"{SLACK}/conversations.history", description="Get top-level messages in a Slack conversation.", input_schema=_object({"channel": _string(), "cursor": _string(), "inclusive": _boolean(), "latest": _string(), "oldest": _string(), "limit": _integer()}, ["channel"]), read_only=True),
        _contract("slack.conversations_replies", server="slack", method="GET", path="/api/conversations.replies", source=f"{SLACK}/conversations.replies", description="Get a Slack thread, parent first.", input_schema=_object({"channel": _string(), "ts": _string(), "cursor": _string(), "limit": _integer()}, ["channel", "ts"]), read_only=True),
        _contract("slack.files_info", server="slack", method="GET", path="/api/files.info", source=f"{SLACK}/files.info", description="Get information about a Slack file.", input_schema=_object({"file": _string(), "count": _integer(), "page": _integer()}, ["file"]), read_only=True),
        _contract("slack.chat_postMessage", server="slack", method="POST", path="/api/chat.postMessage", source=f"{SLACK}/chat.postMessage", description="Post a Slack message or thread reply.", input_schema=_object({"channel": _string(), "text": _string(), "thread_ts": _string()}, ["channel", "text"]), read_only=False),
        _contract("slack.reactions_add", server="slack", method="POST", path="/api/reactions.add", source=f"{SLACK}/reactions.add", description="Add a reaction to a Slack message.", input_schema=_object({"channel": _string(), "timestamp": _string(), "name": _string()}, ["channel", "timestamp", "name"]), read_only=False),
    ]
    return contracts


HARNESS_CONTRACTS = [
    _contract(
        "factorybench.context.get",
        server="factorybench",
        method="MCP",
        path="factorybench://context",
        source="https://github.com/blobfishai/factory-agent-simulation",
        description="Discover the isolated task scope, mounted systems, evidence index, and reference identifiers.",
        input_schema=_object(),
        read_only=True,
    ),
    _contract(
        "factorybench.submit_answer",
        server="factorybench",
        method="MCP",
        path="factorybench://answers",
        source="https://github.com/blobfishai/factory-agent-simulation",
        description="Submit the task-specific exact answer fields to the deterministic benchmark harness.",
        input_schema=_object(),
        read_only=False,
    ),
]


TOOL_DEFINITIONS = tuple(
    sorted(
        [*_collection_contracts(), *_child_and_transaction_contracts(), *_action_contracts(), *_workspace_contracts(), *HARNESS_CONTRACTS],
        key=lambda item: item["name"],
    )
)
TOOL_BY_NAME = {tool["name"]: tool for tool in TOOL_DEFINITIONS}
READ_TOOLS = frozenset(name for name, tool in TOOL_BY_NAME.items() if tool["annotations"]["readOnlyHint"])
WRITE_TOOLS = frozenset(TOOL_BY_NAME) - READ_TOOLS


def public_tool_definitions(answer_schema: Json | None = None) -> list[Json]:
    """Return detached MCP tool definitions, optionally binding submit_answer."""

    definitions = deepcopy(list(TOOL_DEFINITIONS))
    if answer_schema is not None:
        for definition in definitions:
            if definition["name"] == "factorybench.submit_answer":
                definition["inputSchema"] = deepcopy(answer_schema)
                break
    return definitions
