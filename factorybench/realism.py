"""Human decision cases for FactoryBench-100.

The public request is intentionally short and non-procedural.  This module
holds the private decision model that makes the request executable: source
facts, conditional investigations, calculations, alternatives, and the exact
answer contract.  No source packet contains the assembled answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import Any, TYPE_CHECKING

from .decision_specs import SCENARIO_DECISION_SPECS
from .human_requests import HUMAN_REQUESTS

if TYPE_CHECKING:
    from .scenarios import Scenario


AS_OF_DATE = date(2026, 1, 12)


@dataclass(frozen=True)
class FamilyProfile:
    request_frame: str
    record_noun: str
    requirement_label: str
    coverage_label: str
    excluded_label: str
    capacity_label: str
    external_label: str
    stakeholder: str
    unit: str
    oracle_reads: tuple[str, ...]


FAMILY_PROFILES: dict[str, FamilyProfile] = {
    "customer_commitment": FamilyProfile(
        "Tell sales what we can honestly promise, what prevents an earlier commitment, and which fallback is worth offering. If the evidence supports a change, commit the plan and close the loop with the account team.",
        "customer demand and its linked production supply",
        "released demand translated through the effective bill of material",
        "nettable finished-goods and component supply",
        "reserved, quarantined, or already allocated stock",
        "qualified production capacity that does not displace higher-priority work",
        "confirmed replenishment for the uncovered component demand",
        "account team",
        "HR",
        (
            "oracle_fusion.sales_orders.get",
            "oracle_fusion.work_order_materials.list",
            "oracle_fusion.inventory_onhand_balances.list",
            "oracle_fusion.work_order_operations.list",
        ),
    ),
    "production_control": FamilyProfile(
        "Work out whether the build can proceed without violating revision, material, or capacity controls. Give the floor a defensible plan and record it only if the release conditions are met.",
        "discrete work order and released routing",
        "released build quantity at the effective design revision",
        "usable components already available to the order",
        "material committed elsewhere or blocked by quality",
        "open qualified operation time on the dispatch schedule",
        "approved recovery supply for the material gap",
        "cell lead",
        "EA",
        (
            "oracle_fusion.work_orders.get",
            "oracle_fusion.work_order_materials.list",
            "oracle_fusion.inventory_onhand_balances.list",
            "oracle_fusion.work_order_operations.list",
        ),
    ),
    "material_execution": FamilyProfile(
        "Determine the quantity and controlled lot that should actually move, including anything that must be excluded. If the transaction is supported, post it and leave the shift with an auditable result.",
        "shop-floor material requirement and physical movement",
        "authorized transaction quantity at the effective component revision",
        "lot-controlled quantity available for this operation",
        "expired, reserved, or already consumed quantity",
        "operation window in which the movement remains valid",
        "replacement or correction timing for any uncovered quantity",
        "shift supervisor",
        "EA",
        (
            "oracle_fusion.work_orders.get",
            "oracle_fusion.work_order_materials.list",
            "oracle_fusion.inventory_onhand_balances.list",
            "oracle_fusion.quality_inspection_results.list",
        ),
    ),
    "capacity_recovery": FamilyProfile(
        "Find the earliest safe way to recover the affected output, explain the real bottleneck, and compare the qualified alternatives. Put the approved recovery plan on the schedule and tell operations what changed.",
        "constrained work-order operation",
        "remaining production quantity exposed to the disruption",
        "capacity still usable on qualified resources",
        "capacity lost to downtime, absence, calibration, or protected demand",
        "first qualified alternate slot with labor and tooling",
        "external resource or supplier recovery timing",
        "operations control",
        "EA",
        (
            "oracle_fusion.work_order_operations.list",
            "oracle_fusion.work_order_resources.list",
            "oracle_fusion.maintenance_work_orders.get",
            "oracle_fusion.work_orders.get",
        ),
    ),
    "corrective_maintenance": FamilyProfile(
        "Give operations the earliest credible return-to-service date, what is driving it, and whether expediting parts or moving the work materially helps. If the approved scope covers the best plan, record it and notify the people waiting on the asset.",
        "asset and open corrective maintenance order",
        "approved repair scope after diagnosis or teardown",
        "labor, parts, and shop time already available",
        "unapproved scope, unavailable parts, or unqualified labor",
        "qualified maintenance-shop window",
        "repair-part or vendor-service replenishment",
        "production operations",
        "EA",
        (
            "oracle_fusion.maintenance_work_orders.get",
            "oracle_fusion.maintenance_operations.list",
            "oracle_fusion.maintenance_resources.list",
            "oracle_fusion.inventory_onhand_balances.list",
        ),
    ),
    "preventive_maintenance": FamilyProfile(
        "Decide when this maintenance is genuinely due and how to fit it around protected production. Explain the risk of the available windows, then record the approved program decision and notify reliability operations.",
        "meter- or calendar-driven maintenance program",
        "maintenance demand inside the controlled forecast horizon",
        "qualified maintenance capacity inside allowed shutdown windows",
        "blackout periods, inactive assets, or work already generated",
        "next production-safe maintenance window",
        "parts or contractor readiness for the due work",
        "reliability operations",
        "HR",
        (
            "oracle_fusion.maintenance_programs.get",
            "oracle_fusion.maintenance_work_orders.list",
            "oracle_fusion.inventory_onhand_balances.list",
            "oracle_fusion.maintenance_resources.list",
        ),
    ),
    "strategic_procurement": FamilyProfile(
        "Recommend the commercially sound way to cover the demand, including the realistic timing and the strongest alternative. If the sourcing authority is sufficient, record the bounded commitment and tell the requestor what to expect.",
        "approved demand and prospective purchasing document",
        "net uncovered demand at the approved specification",
        "usable inventory and already-open supply",
        "stock reserved elsewhere or supply that arrives too late",
        "need-by window the plant can actually consume",
        "qualified supplier lead time and capacity",
        "requesting planner",
        "USD",
        (
            "oracle_fusion.suppliers.get",
            "oracle_fusion.purchase_orders.list",
            "oracle_fusion.inventory_onhand_balances.list",
            "oracle_fusion.supply_requests.list",
        ),
    ),
    "receiving_control": FamilyProfile(
        "Work out what quantity can be accepted today, what must be rejected or held, and the downstream impact. Record only the supported receipt decision and give receiving and quality the same answer.",
        "purchase-order shipment and receipt interface record",
        "documented shipment quantity at the ordered revision",
        "quantity physically received and eligible for acceptance",
        "damaged, uncertified, duplicated, or misidentified units",
        "inspection and delivery window for accepted material",
        "supplier replacement timing for rejected quantity",
        "receiving and quality teams",
        "EA",
        (
            "oracle_fusion.purchase_orders.get",
            "oracle_fusion.purchase_order_lines.list",
            "oracle_fusion.receiving_receipt_transactions.list",
            "oracle_fusion.quality_inspection_results.list",
        ),
    ),
    "payables_control": FamilyProfile(
        "Decide what can be paid, what must remain held, and why. Quantify the supported amount and timing, compare the clean resolution paths, and record the approved Payables outcome.",
        "supplier invoice and its purchasing support",
        "invoice value requiring valid PO, receipt, tax, and period support",
        "value matched to accepted goods or approved services",
        "duplicate, unmatched, disputed, or out-of-period value",
        "open accounting and payment-processing window",
        "supplier correction or missing-document timing",
        "accounts payable",
        "USD",
        (
            "oracle_fusion.invoices.get",
            "oracle_fusion.purchase_orders.get",
            "oracle_fusion.receiving_receipt_transactions.list",
            "oracle_fusion.purchase_order_lines.list",
        ),
    ),
    "supplier_governance": FamilyProfile(
        "Assess the supplier exposure and recommend the least risky authorized response, with a practical fallback for continuity. Record the decision only within the approved governance scope and brief procurement leadership.",
        "supplier master record and affected open commitments",
        "demand or spend exposed to the supplier condition",
        "coverage from approved sources and accepted commitments",
        "unqualified, sanctioned, uninsured, or overdue exposure",
        "time available before production or cash impact",
        "qualified alternate-source readiness",
        "procurement leadership",
        "USD",
        (
            "oracle_fusion.suppliers.get",
            "oracle_fusion.purchase_orders.list",
            "oracle_fusion.purchase_order_lines.list",
            "oracle_fusion.supply_requests.list",
        ),
    ),
    "quality_execution": FamilyProfile(
        "Determine the defensible disposition and exact controlled quantity from the applicable plan and measurements. Explain the alternative disposition, then record the result and make the decision visible to the floor.",
        "inspection plan, result, and affected material lot",
        "quantity and characteristics governed by the effective inspection plan",
        "sampled quantity meeting every applicable acceptance limit",
        "failed, expired, untested, or out-of-scope quantity",
        "quality-review window before the material is consumed",
        "rework or replacement timing for nonconforming material",
        "quality and production teams",
        "EA",
        (
            "oracle_fusion.inspection_plans.list",
            "oracle_fusion.quality_inspection_results.list",
            "oracle_fusion.inventory_onhand_balances.list",
            "oracle_fusion.work_orders.get",
        ),
    ),
    "inventory_control": FamilyProfile(
        "Work out the exact controlled quantity that can move without breaking reservations, ownership, or lot status. Compare transfer and replenishment options, then post the approved movement and alert material control.",
        "lot-, serial-, or project-controlled inventory position",
        "quantity required at the destination or for the correction",
        "nettable quantity at the eligible source location",
        "reserved, quarantined, project-owned, or physically unverified stock",
        "earliest handling and transit window",
        "replenishment timing if the transfer cannot cover the gap",
        "material control",
        "EA",
        (
            "oracle_fusion.inventory_onhand_balances.list",
            "oracle_fusion.supply_requests.list",
            "oracle_fusion.work_order_materials.list",
            "oracle_fusion.quality_inspection_results.list",
        ),
    ),
    "supply_planning": FamilyProfile(
        "Give planning the earliest feasible coverage date, the constraint behind it, and the best alternative if the requested date cannot be met. Record the approved supply decision without double-covering demand.",
        "net demand and its pegged supply position",
        "uncovered demand at the current planning snapshot",
        "usable on-hand and firm supply arriving before need-by",
        "reserved stock, unfirm supply, and receipts after need-by",
        "first feasible production or transfer slot",
        "supplier or source-organization replenishment timing",
        "supply planning",
        "EA",
        (
            "oracle_fusion.supply_requests.list",
            "oracle_fusion.inventory_onhand_balances.list",
            "oracle_fusion.purchase_orders.list",
            "oracle_fusion.work_order_operations.list",
        ),
    ),
    "engineering_change": FamilyProfile(
        "Determine which open work is actually inside the change effectivity and what can be changed safely now. Compare rework and deferment, record the approved implementation, and tell manufacturing what remains unchanged.",
        "released engineering change and affected open work",
        "open quantity inside the revision or serial effectivity",
        "work already compatible with the released design",
        "completed, out-of-effectivity, or concession-controlled work",
        "first operation window where the change can be applied",
        "new material, fixture, or document readiness",
        "manufacturing engineering",
        "EA",
        (
            "oracle_fusion.work_orders.get",
            "oracle_fusion.work_order_operations.list",
            "oracle_fusion.work_order_materials.list",
            "oracle_fusion.work_order_resources.list",
        ),
    ),
    "cost_accounting": FamilyProfile(
        "Reconstruct the supported production actual, quantify the variance, and decide what belongs in this period. Record the approved correction and give the controller a concise reconciliation.",
        "manufacturing cost transaction and source work order",
        "actual cost or quantity expected from controlled source records",
        "amount already posted once to the correct operation and period",
        "duplicate, unsupported, or wrong-period value",
        "remaining open posting window",
        "source correction timing for unresolved actuals",
        "plant controller",
        "USD",
        (
            "oracle_fusion.work_orders.get",
            "oracle_fusion.work_order_resources.list",
            "oracle_fusion.work_order_materials.list",
            "oracle_fusion.invoices.get",
        ),
    ),
    "project_manufacturing": FamilyProfile(
        "Find the plan that meets the project milestone without crossing ownership or task boundaries. Quantify the uncovered need and alternatives, then record the approved project-scoped action and notify the project team.",
        "project task, milestone demand, and attributed manufacturing record",
        "project-owned demand at the authorized task",
        "eligible inventory and supply carrying the same project attribution",
        "common, other-project, reserved, or released ownership",
        "project-compatible production or transfer window",
        "project-specific replenishment timing",
        "project team",
        "EA",
        (
            "oracle_fusion.work_orders.get",
            "oracle_fusion.inventory_onhand_balances.list",
            "oracle_fusion.supply_requests.list",
            "oracle_fusion.work_order_materials.list",
        ),
    ),
    "field_service_supply": FamilyProfile(
        "Tell service when the technician can really have the required stock or repaired unit, what blocks an earlier answer, and the best fallback. Record the approved field-supply plan and update dispatch.",
        "service demand, serialized asset, and field stock position",
        "quantity needed for the entitled service event",
        "usable technician, regional, or depot stock",
        "reserved, wrong-owner, quarantined, or wrong-serial stock",
        "dispatch and depot handling window",
        "regional replenishment or repair timing",
        "service dispatch",
        "EA",
        (
            "oracle_fusion.supply_requests.list",
            "oracle_fusion.inventory_onhand_balances.list",
            "oracle_fusion.receiving_receipt_requests.list",
            "oracle_fusion.maintenance_work_orders.list",
        ),
    ),
    "compliance_traceability": FamilyProfile(
        "Establish the exact affected scope and the safest authorized containment or documentation response. Explain what is unaffected, compare the available resolutions, then record the controlled outcome for audit and operations.",
        "regulated lot, serial, document, or payment record",
        "quantity or value inside the applicable compliance scope",
        "traceable quantity or value with complete supporting evidence",
        "untraceable, recalled, restricted, or undocumented scope",
        "time remaining before consumption, payment, or audit cutoff",
        "replacement evidence or compliant-source readiness",
        "compliance and operations",
        "EA",
        (
            "oracle_fusion.quality_inspection_results.list",
            "oracle_fusion.inventory_onhand_balances.list",
            "oracle_fusion.receiving_receipt_transactions.list",
            "oracle_fusion.purchase_orders.get",
        ),
    ),
    "period_close": FamilyProfile(
        "Resolve the exception only if the source activity belongs in the closing period. Quantify the supported amount or quantity, compare correction with deferral, then record the approved close treatment and brief the controller.",
        "period-close exception and its source document",
        "activity presented for the current accounting period",
        "value supported by accepted, completed, and approved source activity",
        "unmatched, incomplete, duplicate, or post-cutoff value",
        "remaining close-calendar processing window",
        "source-team correction timing",
        "plant controller",
        "USD",
        (
            "oracle_fusion.purchase_orders.get",
            "oracle_fusion.invoices.get",
            "oracle_fusion.receiving_receipt_transactions.list",
            "oracle_fusion.work_orders.get",
        ),
    ),
    "supplier_operations": FamilyProfile(
        "Work out the accepted supplier-operation quantity and the date it can support manufacturing, including the best recovery option. Record the supported outside-processing action and give production and the supplier the same commitment.",
        "outside-processing purchase order and supplier operation",
        "quantity due back from the controlled supplier operation",
        "accepted receipt and inspection quantity",
        "rejected, missing, unreceived, or uninvoiced quantity",
        "manufacturing operation window after supplier receipt",
        "supplier recovery and replacement timing",
        "production and supplier operations",
        "EA",
        (
            "oracle_fusion.purchase_orders.get",
            "oracle_fusion.receiving_receipt_transactions.list",
            "oracle_fusion.quality_inspection_results.list",
            "oracle_fusion.work_order_operations.list",
        ),
    ),
}


def human_request(scenario: "Scenario") -> str:
    """Return a natural employee request without revealing an execution recipe."""

    try:
        request = HUMAN_REQUESTS[scenario.title]
    except KeyError as exc:
        raise ValueError(f"missing individually authored request for {scenario.title}") from exc
    if len(request.split()) < 45:
        request += (
            " If the evidence still conflicts, keep the unsupported scope unchanged "
            "and leave operations with the unresolved risk and owner."
        )
    return request


def _identifier_values(ordinal: int) -> dict[str, str]:
    return {
        "order_number": f"SO-{47_000 + ordinal}",
        "affected_order": f"WO-{ordinal:04d}",
        "affected_work_order": f"WO-{ordinal:04d}",
        "work_order": f"WO-{ordinal:04d}",
        "maintenance_order": f"MWO-{ordinal:04d}",
        "program_code": f"PM-{ordinal:04d}",
        "purchase_document": f"PO-{ordinal:04d}",
        "receipt_reference": f"RCV-{ordinal:04d}",
        "invoice_reference": f"INV-{ordinal:04d}",
        "invoice_number": f"INV-{ordinal:04d}",
        "hold_or_reference": f"HOLD-{ordinal:04d}",
        "supplier": f"SUP-{ordinal:04d}",
        "inspection_reference": f"INSP-{ordinal:04d}",
        "inventory_transaction": f"TX-{ordinal:04d}",
        "supply_reference": f"SUPPLY-{ordinal:04d}",
        "change_order": f"ECO-{ordinal:04d}",
        "cost_reference": f"COST-{ordinal:04d}",
        "project_task": f"PRJ-{ordinal:03d}.TASK-{1 + ordinal % 7:02d}",
        "service_request": f"SR-{ordinal:04d}",
        "compliance_case": f"CASE-{ordinal:03d}",
        "close_exception": f"CLOSE-{ordinal:04d}",
        "supplier_operation": f"OSP-{ordinal:04d}",
        "transaction_reference": f"TX-{ordinal:04d}",
        "item_lot": f"NS-COMP-{ordinal:03d}/LOT-{ordinal:04d}",
        "asset_or_resource": f"ASSET-{ordinal:03d}",
        "manufacturing_record": f"WO-{ordinal:04d}",
        "contained_record": f"LOT-{ordinal:04d}",
        "evidence_reference": f"DOC-{ordinal:04d}",
        "case_reference": f"CASE-{ordinal:03d}",
    }


_ACTION_READ_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "oracle_fusion.work_orders.create": (
        "oracle_fusion.work_orders.list",
        "oracle_fusion.sales_orders.list",
        "oracle_fusion.inventory_onhand_balances.list",
        "oracle_fusion.supply_requests.list",
    ),
    "oracle_fusion.work_orders.update": (
        "oracle_fusion.work_orders.get",
        "oracle_fusion.work_order_operations.list",
        "oracle_fusion.work_order_materials.list",
        "oracle_fusion.inventory_onhand_balances.list",
    ),
    "oracle_fusion.supply_requests.create": (
        "oracle_fusion.supply_requests.list",
        "oracle_fusion.inventory_onhand_balances.list",
        "oracle_fusion.purchase_orders.list",
        "oracle_fusion.sales_orders.list",
    ),
    "oracle_fusion.work_order_materials.replace_with_substitute": (
        "oracle_fusion.work_order_materials.list",
        "oracle_fusion.work_orders.get",
        "oracle_fusion.inventory_onhand_balances.list",
        "oracle_fusion.quality_inspection_results.list",
    ),
    "oracle_fusion.work_order_operations.update": (
        "oracle_fusion.work_order_operations.list",
        "oracle_fusion.work_order_resources.list",
        "oracle_fusion.work_orders.get",
        "oracle_fusion.maintenance_work_orders.get",
    ),
    "oracle_fusion.work_order_operations.create": (
        "oracle_fusion.work_order_operations.list",
        "oracle_fusion.quality_inspection_results.list",
        "oracle_fusion.work_orders.get",
        "oracle_fusion.work_order_resources.list",
    ),
    "oracle_fusion.work_order_resources.create": (
        "oracle_fusion.work_order_resources.list",
        "oracle_fusion.work_order_operations.list",
        "oracle_fusion.work_orders.get",
        "oracle_fusion.suppliers.list",
    ),
    "oracle_fusion.work_order_resources.update": (
        "oracle_fusion.work_order_resources.list",
        "oracle_fusion.work_order_operations.list",
        "oracle_fusion.work_orders.get",
        "oracle_fusion.purchase_order_lines.list",
    ),
    "oracle_fusion.material_transactions.create": (
        "oracle_fusion.work_order_materials.list",
        "oracle_fusion.inventory_onhand_balances.list",
        "oracle_fusion.work_orders.get",
        "oracle_fusion.quality_inspection_results.list",
    ),
    "oracle_fusion.inventory_transactions.create": (
        "oracle_fusion.inventory_onhand_balances.list",
        "oracle_fusion.quality_inspection_results.list",
        "oracle_fusion.supply_requests.list",
        "oracle_fusion.work_order_materials.list",
    ),
    "oracle_fusion.operation_transactions.create": (
        "oracle_fusion.work_order_operations.list",
        "oracle_fusion.work_orders.get",
        "oracle_fusion.quality_inspection_results.list",
        "oracle_fusion.receiving_receipt_transactions.list",
    ),
    "oracle_fusion.resource_transactions.create": (
        "oracle_fusion.work_order_resources.list",
        "oracle_fusion.work_order_operations.list",
        "oracle_fusion.work_orders.get",
        "oracle_fusion.maintenance_work_orders.get",
    ),
    "oracle_fusion.maintenance_work_orders.create": (
        "oracle_fusion.maintenance_work_orders.list",
        "oracle_fusion.maintenance_programs.get",
        "oracle_fusion.inventory_onhand_balances.list",
        "oracle_fusion.quality_inspection_results.list",
    ),
    "oracle_fusion.maintenance_work_orders.update": (
        "oracle_fusion.maintenance_work_orders.get",
        "oracle_fusion.maintenance_operations.list",
        "oracle_fusion.maintenance_resources.list",
        "oracle_fusion.inventory_onhand_balances.list",
    ),
    "oracle_fusion.maintenance_operations.update": (
        "oracle_fusion.maintenance_operations.list",
        "oracle_fusion.maintenance_work_orders.get",
        "oracle_fusion.maintenance_resources.list",
        "oracle_fusion.work_order_operations.list",
    ),
    "oracle_fusion.maintenance_documents.create": (
        "oracle_fusion.maintenance_documents.list",
        "oracle_fusion.maintenance_work_orders.get",
        "oracle_fusion.maintenance_programs.get",
        "oracle_fusion.quality_inspection_results.list",
    ),
    "oracle_fusion.maintenance_programs.create": (
        "oracle_fusion.maintenance_programs.list",
        "oracle_fusion.maintenance_work_orders.list",
        "oracle_fusion.quality_inspection_results.list",
        "oracle_fusion.inventory_onhand_balances.list",
    ),
    "oracle_fusion.maintenance_programs.update": (
        "oracle_fusion.maintenance_programs.get",
        "oracle_fusion.maintenance_work_orders.list",
        "oracle_fusion.maintenance_resources.list",
        "oracle_fusion.inventory_onhand_balances.list",
    ),
    "oracle_fusion.maintenance_programs.generate_forecasts": (
        "oracle_fusion.maintenance_programs.get",
        "oracle_fusion.maintenance_work_orders.list",
        "oracle_fusion.maintenance_resources.list",
        "oracle_fusion.inventory_onhand_balances.list",
    ),
    "oracle_fusion.maintenance_programs.generate_work_orders": (
        "oracle_fusion.maintenance_programs.get",
        "oracle_fusion.maintenance_work_orders.list",
        "oracle_fusion.maintenance_resources.list",
        "oracle_fusion.inventory_onhand_balances.list",
    ),
    "oracle_fusion.draft_purchase_orders.create": (
        "oracle_fusion.draft_purchase_orders.list",
        "oracle_fusion.suppliers.get",
        "oracle_fusion.purchase_orders.list",
        "oracle_fusion.supply_requests.list",
    ),
    "oracle_fusion.purchase_orders.acknowledge": (
        "oracle_fusion.purchase_orders.get",
        "oracle_fusion.purchase_order_lines.list",
        "oracle_fusion.suppliers.get",
        "oracle_fusion.supply_requests.list",
    ),
    "oracle_fusion.purchase_orders.cancel": (
        "oracle_fusion.purchase_orders.get",
        "oracle_fusion.purchase_order_lines.list",
        "oracle_fusion.supply_requests.list",
        "oracle_fusion.inventory_onhand_balances.list",
    ),
    "oracle_fusion.purchase_orders.close": (
        "oracle_fusion.purchase_orders.get",
        "oracle_fusion.purchase_order_lines.list",
        "oracle_fusion.receiving_receipt_transactions.list",
        "oracle_fusion.invoices.get",
    ),
    "oracle_fusion.receiving_receipt_requests.create": (
        "oracle_fusion.receiving_receipt_requests.list",
        "oracle_fusion.purchase_orders.get",
        "oracle_fusion.purchase_order_lines.list",
        "oracle_fusion.quality_inspection_results.list",
    ),
    "oracle_fusion.receiving_receipt_transactions.create": (
        "oracle_fusion.receiving_receipt_transactions.list",
        "oracle_fusion.purchase_order_lines.list",
        "oracle_fusion.quality_inspection_results.list",
        "oracle_fusion.inventory_onhand_balances.list",
    ),
    "oracle_fusion.receiving_receipt_transactions.update": (
        "oracle_fusion.receiving_receipt_transactions.list",
        "oracle_fusion.receiving_receipt_requests.list",
        "oracle_fusion.purchase_order_lines.list",
        "oracle_fusion.quality_inspection_results.list",
    ),
    "oracle_fusion.invoices.validate": (
        "oracle_fusion.invoices.get",
        "oracle_fusion.purchase_orders.get",
        "oracle_fusion.purchase_order_lines.list",
        "oracle_fusion.receiving_receipt_transactions.list",
    ),
    "oracle_fusion.invoices.create": (
        "oracle_fusion.invoices.list",
        "oracle_fusion.suppliers.get",
        "oracle_fusion.purchase_orders.list",
        "oracle_fusion.receiving_receipt_transactions.list",
    ),
    "oracle_fusion.invoices.update": (
        "oracle_fusion.invoices.get",
        "oracle_fusion.suppliers.get",
        "oracle_fusion.purchase_orders.get",
        "oracle_fusion.purchase_order_lines.list",
    ),
    "oracle_fusion.invoice_holds.create": (
        "oracle_fusion.invoices.get",
        "oracle_fusion.purchase_orders.get",
        "oracle_fusion.purchase_order_lines.list",
        "oracle_fusion.receiving_receipt_transactions.list",
    ),
    "oracle_fusion.invoice_holds.update": (
        "oracle_fusion.invoices.get",
        "oracle_fusion.purchase_orders.get",
        "oracle_fusion.purchase_order_lines.list",
        "oracle_fusion.receiving_receipt_transactions.list",
    ),
    "oracle_fusion.quality_inspection_results.create": (
        "oracle_fusion.inspection_plans.list",
        "oracle_fusion.quality_inspection_results.list",
        "oracle_fusion.receiving_receipt_transactions.list",
        "oracle_fusion.inventory_onhand_balances.list",
    ),
    "oracle_fusion.quality_inspection_results.update": (
        "oracle_fusion.quality_inspection_results.list",
        "oracle_fusion.inspection_plans.list",
        "oracle_fusion.inventory_onhand_balances.list",
        "oracle_fusion.receiving_receipt_transactions.list",
    ),
}


# These two repairs look similar only at the mutation boundary.  The evidence an
# employee must reconcile is deliberately different: the servo case is an
# internal reliability decision, while the depot case is an entitlement/RMA
# decision for a customer-owned asset.  Keep those investigations distinct
# instead of letting the generic maintenance dependency list flatten them into
# the same benchmark task.
_TASK_ORACLE_READ_OVERRIDES: dict[str, tuple[str, ...]] = {
    "Open repair for a failed servo drive": (
        "oracle_fusion.maintenance_programs.get",
        "oracle_fusion.maintenance_work_orders.list",
        "oracle_fusion.quality_inspection_results.list",
        "oracle_fusion.inventory_onhand_balances.list",
        "oracle_fusion.maintenance_documents.list",
    ),
    "Open depot repair for a customer asset": (
        "oracle_fusion.sales_orders.get",
        "oracle_fusion.receiving_receipt_requests.list",
        "oracle_fusion.maintenance_work_orders.list",
        "oracle_fusion.maintenance_documents.list",
        "oracle_fusion.quality_inspection_results.list",
    ),
    "Post a blind cycle-count adjustment": (
        "oracle_fusion.inventory_onhand_balances.list",
        "oracle_fusion.cycle_count_definitions.list",
        "oracle_fusion.cycle_count_sequence_details.list",
        "oracle_fusion.cycle_count_history.list",
    ),
    "Post calibrated test-bench labor actuals": (
        "oracle_fusion.work_orders.get",
        "oracle_fusion.work_order_operations.list",
        "oracle_fusion.work_order_resources.list",
        "oracle_fusion.maintenance_programs.get",
    ),
    "Move a repair to the qualified electrical shop": (
        "oracle_fusion.maintenance_work_orders.get",
        "oracle_fusion.maintenance_operations.list",
        "oracle_fusion.maintenance_resources.list",
        "oracle_fusion.maintenance_documents.list",
    ),
    "Post missing setup labor from signed timecards": (
        "oracle_fusion.work_orders.get",
        "oracle_fusion.work_order_operations.list",
        "oracle_fusion.work_order_resources.list",
        "oracle_fusion.purchase_order_lines.list",
    ),
    "Issue a reserved spare to an emergency repair": (
        "oracle_fusion.maintenance_work_orders.get",
        "oracle_fusion.maintenance_materials.list",
        "oracle_fusion.inventory_onhand_balances.list",
        "oracle_fusion.supply_requests.list",
    ),
    "Hold payment for a missing conflict-minerals report": (
        "oracle_fusion.invoices.get",
        "oracle_fusion.suppliers.get",
        "oracle_fusion.purchase_orders.get",
        "oracle_fusion.purchase_order_lines.list",
        "oracle_fusion.receiving_receipt_transactions.list",
    ),
    "Post an omitted maintenance labor charge": (
        "oracle_fusion.maintenance_work_orders.get",
        "oracle_fusion.maintenance_operations.list",
        "oracle_fusion.maintenance_resources.list",
        "oracle_fusion.purchase_order_lines.list",
    ),
}


_CREATE_TARGET_COLLECTION_READS = {
    "oracle_fusion.work_orders.create": "oracle_fusion.work_orders.list",
    "oracle_fusion.maintenance_work_orders.create": (
        "oracle_fusion.maintenance_work_orders.list"
    ),
    "oracle_fusion.maintenance_programs.create": (
        "oracle_fusion.maintenance_programs.list"
    ),
    "oracle_fusion.invoices.create": "oracle_fusion.invoices.list",
}


def _valid_pre_create_read(tool: str, primary_write: str) -> str:
    """Use a collection duplicate search, never GET a future record."""

    collection = _CREATE_TARGET_COLLECTION_READS.get(primary_write)
    if collection is None:
        return tool
    if tool.rsplit(".", 1)[0] == collection.rsplit(".", 1)[0]:
        return collection
    return tool


def _scenario_oracle_reads(scenario: "Scenario") -> tuple[str, ...]:
    override = _TASK_ORACLE_READ_OVERRIDES.get(scenario.title)
    if override is not None:
        return override
    candidates = [
        _valid_pre_create_read(tool, scenario.primary_write)
        for tool in (
            scenario.primary_read,
            scenario.support_read,
            *_ACTION_READ_DEPENDENCIES.get(
                scenario.primary_write,
                FAMILY_PROFILES[scenario.family].oracle_reads,
            ),
        )
    ]
    reads: list[str] = []
    resources: set[str] = set()
    for tool in candidates:
        if not tool.startswith("oracle_fusion."):
            continue
        resource = tool.rsplit(".", 1)[0]
        if resource in resources:
            continue
        resources.add(resource)
        reads.append(tool)
    fallback = tuple(
        _valid_pre_create_read(tool, scenario.primary_write)
        for tool in FAMILY_PROFILES[scenario.family].oracle_reads
    )
    for tool in fallback:
        resource = tool.rsplit(".", 1)[0]
        if resource not in resources:
            resources.add(resource)
            reads.append(tool)
        if len(reads) >= 4:
            break
    return tuple(reads[:5])


def _criterion(
    criterion_id: str,
    field: str,
    weight: float,
    description: str,
) -> dict[str, Any]:
    return {
        "id": criterion_id,
        "field": field,
        "weight": weight,
        "description": description,
    }


_FULLY_RECONCILED_TITLES = {
    "Release the flight-test controller build",
    "Close a fully received calibration-services PO",
    "Validate a clean three-way-matched invoice",
    "Release a hold after the supplier credit arrives",
    "Correct payment terms from the signed contract",
    "Enter a non-PO metrology invoice",
    "Close a supplier remediation purchase order",
    "Validate an outside-processing invoice",
    "Close a fully settled tooling PO before cutoff",
    "Validate the final matched invoice batch item",
    "Hold a duplicate invoice found in reconciliation",
    "Close an outside-processing PO after final acceptance",
}


_EXPLICIT_DECISION_VALUES: dict[str, tuple[float | int, float | int, float | int, float | int]] = {
    "Release a hold after the supplier credit arrives": (402.05, 402.05, 0.0, 402.05),
    "Post missing setup labor from signed timecards": (1_020.0, 1_020.0, 0.0, 1_020.0),
    "Reverse a duplicated copper issue": (1_152.0, 1_152.0, 576.0, 576.0),
    "Post an omitted maintenance labor charge": (782.0, 782.0, 0.0, 782.0),
    "Hold payment for a missing conflict-minerals report": (19_578.0, 19_578.0, 19_578.0, 0.0),
    "Hold a duplicate invoice found in reconciliation": (20_264.25, 20_264.25, 20_264.25, 0.0),
    "Close an outside-processing PO after final acceptance": (49, 49, 0, 49),
}


_PHYSICAL_TRANSACTION_VALUES: dict[str, tuple[float | int, str]] = {
    "Post missing setup labor from signed timecards": (12.0, "HR"),
    "Reverse a duplicated copper issue": (48.0, "KG"),
    "Post an omitted maintenance labor charge": (8.5, "HR"),
}


_PHYSICAL_TRANSACTION_RATES_USD = {
    "Post missing setup labor from signed timecards": 85.0,
    "Reverse a duplicated copper issue": 12.0,
    "Post an omitted maintenance labor charge": 92.0,
}


_FORECAST_DECISION_VALUES: dict[
    str,
    tuple[int, int, int, int, int],
] = {
    # source measure, independently observed measure, excluded measure,
    # qualifying measure, effective trigger threshold
    "Convert a repeated bearing alarm into planned work": (7, 7, 2, 5, 3),
    "Advance lubrication after a meter spike": (2_150, 2_150, 150, 2_000, 1_800),
    "Generate the quarterly compressor forecast": (14, 14, 4, 10, 1),
    "Create due work for guarded saw inspections": (11, 11, 3, 8, 1),
    "Create a contamination-control program": (18, 18, 5, 13, 1),
}


def _decision_timeline(
    spec: Any,
    ordinal: int,
) -> tuple[tuple[str, str, str], str, dict[str, str]]:
    """Create an independent control date and mode-coherent option timeline."""

    mode = spec.mode
    selected_index = spec.recommended_index
    if mode == "plan":
        need = AS_OF_DATE + timedelta(days=7 + ordinal % 5)
        if selected_index == 0:
            baseline_offset = 1 if ordinal % 6 == 0 else -1
            dates = (
                need + timedelta(days=baseline_offset),
                need - timedelta(days=3),
                need - timedelta(days=4),
            )
        else:
            dates = (
                need + timedelta(days=3),
                need,
                need - timedelta(days=1),
            )
        forecast = {}
    elif mode == "schedule":
        need = AS_OF_DATE + timedelta(days=4 + ordinal % 5)
        if selected_index == 0:
            # Some controlled recoveries are honestly late because every
            # superficially faster path fails qualification or scope.
            base_offset = 1 if ordinal % 4 == 1 else 0
            dates = (
                need + timedelta(days=base_offset),
                need - timedelta(days=1),
                need - timedelta(days=2),
            )
        else:
            dates = (
                need + timedelta(days=3),
                need,
                need - timedelta(days=1),
            )
        forecast = {}
    elif mode == "quantity":
        need = AS_OF_DATE + timedelta(days=1 + ordinal % 3)
        if selected_index == 1:
            dates = (
                need + timedelta(days=2),
                need,
                need + timedelta(days=1),
            )
        else:
            dates = (
                need,
                need + timedelta(days=1),
                need + timedelta(days=2),
            )
        forecast = {}
    elif mode == "financial":
        need = AS_OF_DATE + timedelta(days=2 + ordinal % 4)
        dates = (
            need,
            need if selected_index == 1 else need + timedelta(days=1),
            need + timedelta(days=2),
        )
        forecast = {}
    elif mode == "identity":
        need = AS_OF_DATE + timedelta(days=3 + ordinal % 3)
        if selected_index == 1:
            dates = (
                AS_OF_DATE + timedelta(days=1),
                AS_OF_DATE + timedelta(days=2),
                need + timedelta(days=3),
            )
        else:
            dates = (
                AS_OF_DATE + timedelta(days=1),
                AS_OF_DATE,
                need + timedelta(days=3),
            )
        forecast = {}
    elif mode == "forecast":
        need = AS_OF_DATE + timedelta(days=2 + ordinal % 3)
        due = AS_OF_DATE + timedelta(days=10 + ordinal % 12)
        safe_window = due + timedelta(days=ordinal % 4)
        horizon = safe_window + timedelta(days=75 + (ordinal % 4) * 15)
        dates = (
            need,
            due + timedelta(days=30),
            need + timedelta(days=1),
        )
        forecast = {
            "due_date": due.isoformat(),
            "safe_window_start": safe_window.isoformat(),
            "forecast_horizon_end": horizon.isoformat(),
        }
    else:  # pragma: no cover - validated scenario modes.
        raise ValueError(f"unknown decision mode: {mode}")
    return tuple(value.isoformat() for value in dates), need.isoformat(), forecast


def _decision_option_costs(
    spec: Any,
    ordinal: int,
    *,
    scope: float | int,
    gap: float | int,
    unit_price: float,
) -> tuple[int, int, int]:
    """Return grounded premiums or avoidable exposure, never arbitrary spend."""

    selected = spec.recommended_index
    if spec.mode in {"plan", "schedule"}:
        return (0, 350 + ordinal * 17, 1_100 + ordinal * 31)
    if spec.mode in {"quantity", "identity", "forecast"}:
        return (0, 0, 0)
    if spec.mode == "financial":
        low_exposure = int(round(float(gap)))
        high_exposure = int(round(float(scope)))
    else:
        low_exposure = int(round(float(gap) * unit_price))
        high_exposure = int(round(max(1.0, float(scope)) * unit_price))
    values = [low_exposure, low_exposure, high_exposure]
    values[selected] = 0
    return tuple(values)  # type: ignore[return-value]


_CONTROL_FAILURE_TOKENS = {
    "all",
    "entire",
    "globally",
    "unapproved",
    "uncertified",
    "unconfirmed",
    "unrelated",
    "without",
    "wrong",
    "latest_filename",
    "latest_named",
    "infer",
    "skip",
    "force",
    "both",
    "open_balance",
    "full_",
    "generic",
    "similar",
    "superseded",
    "expired",
    "lowest_sticker",
    "closed_period",
    "unreconciled",
    "estimate",
    "average",
    "discard",
    "verbal_waiver",
    "use_as_is",
}


def _option_control_status(option_id: str, *, selected: bool, escalated: bool) -> str:
    if selected:
        return "SUPPORTED_AND_APPROVED"
    if escalated:
        return "SEPARATE_APPROVAL_OR_POLICY_EXCEPTION_REQUIRED"
    if any(token in option_id for token in _CONTROL_FAILURE_TOKENS):
        return "FAILS_CURRENT_CONTROL"
    return "FEASIBLE_WITH_INFERIOR_TRADEOFF"


def _option_consequence(
    spec: Any,
    option_id: str,
    *,
    completion: str,
    business_need: str,
    option_cost: int,
    selected_option: str,
    selected_completion: str,
    selected_cost: int,
    selected: bool,
    escalated: bool,
) -> str:
    phrase = option_id.replace("_", " ")
    variance = (
        date.fromisoformat(completion) - date.fromisoformat(business_need)
    ).days
    timing = (
        f"{variance} day(s) after the control date"
        if variance > 0
        else f"{abs(variance)} day(s) on or ahead of the control date"
    )
    relative_days = (
        date.fromisoformat(completion) - date.fromisoformat(selected_completion)
    ).days
    relative_timing = (
        f"{abs(relative_days)} day(s) earlier than {selected_option}"
        if relative_days < 0
        else (
            f"{relative_days} day(s) later than {selected_option}"
            if relative_days > 0
            else f"on the same date as {selected_option}"
        )
    )
    cost_delta = option_cost - selected_cost
    cost_clause = (
        f" and adds USD {cost_delta} versus {selected_option}"
        if cost_delta > 0
        else (
            f" and saves USD {abs(cost_delta)} versus {selected_option}"
            if cost_delta < 0
            else " with no documented economic difference"
        )
    )
    if selected:
        return (
            f"{phrase} uses only {spec.eligible_label}, satisfies {spec.constraint_label}, "
            f"lands {timing}, and carries the documented economic impact of USD {option_cost}."
        )
    if escalated:
        return (
            f"{phrase} would finish {relative_timing}{cost_clause}, but current approval does not "
            f"authorize it and it could expose {spec.excluded_label}."
        )
    if any(token in option_id for token in _CONTROL_FAILURE_TOKENS):
        return (
            f"{phrase} would land {timing}, but it fails {spec.constraint_label} because it would "
            f"use or ignore {spec.excluded_label}."
        )
    return (
        f"{phrase} would finish {relative_timing}{cost_clause}; it remains controlled but is not "
        f"the best authorized tradeoff once {spec.excluded_label} stays out of scope."
    )


_TRANSACTION_BASIS_BY_TITLE = {
    "Reject water-damaged enclosures at inspection": "excluded",
    "Record failed dielectric-test samples": "excluded",
    "Post a blind cycle-count adjustment": "negative_gap",
    "Record scrap discovered during final count": "excluded",
    "Record yield loss from rejected processed parts": "excluded",
}


def _mutation_measure(
    scenario: "Scenario",
    spec: Any,
    *,
    scope: float | int,
    excluded: float | int,
    eligible: float | int,
    gap: float | int,
) -> tuple[float | int, str]:
    """Return the business measure actually persisted by the provider call."""

    if scenario.title in _PHYSICAL_TRANSACTION_VALUES:
        return _PHYSICAL_TRANSACTION_VALUES[scenario.title]
    basis = _TRANSACTION_BASIS_BY_TITLE.get(scenario.title)
    if basis == "excluded":
        return excluded, spec.unit
    if basis == "gap":
        return gap, spec.unit
    if basis == "negative_gap":
        return -float(gap), spec.unit
    if scenario.primary_write == "oracle_fusion.supply_requests.create" and spec.mode == "plan":
        return gap, spec.unit
    if scenario.primary_write == "oracle_fusion.work_orders.create" and spec.mode == "plan":
        return scope, spec.unit
    if scenario.primary_write == "oracle_fusion.draft_purchase_orders.create":
        return 1, "LOT"
    return eligible, spec.unit


def _financial_control(
    scenario_title: str,
    *,
    scope: float | int,
) -> tuple[str, float]:
    zero_residual = {
        "Close a fully received calibration-services PO": "final-close residual balance",
        "Release a hold after the supplier credit arrives": "credit-to-hold residual variance",
        "Close a supplier remediation purchase order": "open remediation balance",
        "Post missing setup labor from signed timecards": "signed-timecard posting variance",
        "Reverse a duplicated copper issue": "duplicate-issue residual variance",
        "Hold payment for a missing conflict-minerals report": "unsupported covered value allowed before compliance hold",
        "Close a fully settled tooling PO before cutoff": "final-close residual balance",
        "Hold a duplicate invoice found in reconciliation": "duplicate invoice payable amount",
        "Post an omitted maintenance labor charge": "signed-maintenance-labor posting variance",
    }
    if scenario_title in zero_residual:
        return zero_residual[scenario_title], 0.0
    if scenario_title == "Award the enclosure tooling package":
        return "sourcing authority ceiling", 250_000.0
    if scenario_title == "Enter a non-PO metrology invoice":
        return "non-PO service approval ceiling", 25_000.0
    if scenario_title == "Escalate sole-source spend concentration":
        return "unmitigated concentration escalation threshold", 250.0
    if scenario_title == "Correct payment terms from the signed contract":
        return "unsupported monetary variance after applying signed terms", 0.0
    if scenario_title == "Place a freight-variance hold":
        return "contract freight tolerance", 50.0
    return "document-specific matching tolerance", round(max(25.0, float(scope) * 0.005), 2)


def _mode_answer_bundle(
    *,
    scenario_title: str,
    mode: str,
    subject: str,
    spec: Any,
    scope: float | int,
    observed: float | int,
    excluded: float | int,
    eligible: float | int,
    gap: float | int,
    revision: str,
    item: str,
    record: str,
    identifiers: dict[str, str],
    primary_write: str,
    option_dates: tuple[str, str, str],
    option_costs: tuple[int, int, int],
    selected_option: str,
    selected_date: str,
    selected_cost: int,
    business_need: str,
    ordinal: int,
    transaction_measure: float | int,
    transaction_unit: str,
    transaction_rate_usd: float | None,
    forecast_timeline: dict[str, str],
    trigger_threshold: float | int | None,
    standard_readiness: str,
    expedited_readiness: str,
) -> tuple[dict[str, Any], dict[str, str], list[dict[str, Any]]]:
    timing_variance = (
        date.fromisoformat(selected_date) - date.fromisoformat(business_need)
    ).days
    timing_status = "LATE" if timing_variance > 0 else "ON_TIME"
    economic_label = (
        "incremental recovery cost"
        if mode in {"plan", "schedule"}
        else "incremental spend or avoidable exposure"
    )
    answer: dict[str, Any] = {
        "business_need_date": business_need,
        "recommended_option": selected_option,
        "recommended_outcome_date": selected_date,
        "recommended_incremental_cost_usd": selected_cost,
        "escalation_approval_required": 1,
        "outcome_vs_control_days": timing_variance,
        "decision_timing_status": timing_status,
    }
    descriptions: dict[str, str] = {
        "business_need_date": "Documented business or control date that the decision must protect.",
        "recommended_option": f"Best authorized option identifier after comparing {', '.join(spec.options)}.",
        "recommended_outcome_date": "Date produced by the selected option after applying all source constraints.",
        "recommended_incremental_cost_usd": f"Documented {economic_label} of the selected option in USD; zero when spend is not a decision driver.",
        "escalation_approval_required": "Use 1 because the third option is outside current authority; otherwise use 0.",
        "outcome_vs_control_days": "Selected outcome date minus the independently documented business/control date; positive means late.",
        "decision_timing_status": "Use ON_TIME when the selected outcome is on or before the control date; otherwise use LATE.",
    }
    calculations: list[dict[str, Any]] = [
        _criterion(
            "identify_business_date",
            "business_need_date",
            1.0,
            f"Preserved {business_need} as the documented date for {subject}; did not infer urgency from the title.",
        )
    ]

    if mode == "plan":
        answer.update(
            {
                "coverage_item_or_resource": item,
                "required_quantity": int(scope),
                "observed_coverage_quantity": int(observed),
                "ineligible_coverage_quantity": int(excluded),
                "usable_coverage_quantity": int(eligible),
                "shortage_quantity": int(gap),
                "quantity_unit": spec.unit,
                "baseline_completion": option_dates[0],
                "accelerated_completion": option_dates[1],
                "escalated_completion": option_dates[2],
                "standard_external_readiness": standard_readiness,
                "expedited_external_readiness": expedited_readiness,
                "external_recovery_quantity": int(gap),
            }
        )
        descriptions.update(
            {
                "coverage_item_or_resource": "Immutable item or resource whose requirement and eligible coverage were reconciled.",
                "required_quantity": spec.scope_label,
                "observed_coverage_quantity": f"Gross observed coverage for {spec.eligible_label} before exclusions.",
                "ineligible_coverage_quantity": spec.excluded_label,
                "usable_coverage_quantity": f"Net eligible coverage after removing {spec.excluded_label}.",
                "shortage_quantity": f"Uncovered {spec.unit} after netting eligible coverage from the requirement.",
                "quantity_unit": f"Unit shared by the requirement and coverage calculations: {spec.unit}.",
                "baseline_completion": f"Outcome date for {spec.options[0]}.",
                "accelerated_completion": f"Outcome date for {spec.options[1]}.",
                "escalated_completion": f"Outcome date for {spec.options[2]}.",
                "standard_external_readiness": f"Standard readiness date independently confirmed for {spec.external_label}.",
                "expedited_external_readiness": f"Expedited readiness date independently confirmed for {spec.external_label}.",
                "external_recovery_quantity": f"Uncovered {spec.unit} that the external recovery must cover.",
            }
        )
        calculations.extend(
            [
                _criterion("derive_plan_requirement", "required_quantity", 2.0, f"Derived {int(scope)} {spec.unit} for {spec.scope_label} at revision {revision}."),
                _criterion("read_gross_coverage", "observed_coverage_quantity", 1.0, f"Read {int(observed)} {spec.unit} of gross observed {spec.eligible_label}."),
                _criterion("remove_ineligible_coverage", "ineligible_coverage_quantity", 1.5, f"Excluded {int(excluded)} {spec.unit} for {spec.excluded_label}."),
                _criterion("calculate_usable_coverage", "usable_coverage_quantity", 2.0, f"Calculated {int(observed)} observed − {int(excluded)} ineligible = {int(eligible)} usable {spec.unit}."),
                _criterion("calculate_plan_gap", "shortage_quantity", 2.0, f"Calculated {int(scope)} required − {int(eligible)} usable = {int(gap)} {spec.unit} uncovered."),
                _criterion("preserve_plan_unit", "quantity_unit", 0.5, f"Kept every planning quantity in {spec.unit}."),
                _criterion("compare_baseline_plan", "baseline_completion", 1.0, f"Calculated {spec.options[0]} outcome as {option_dates[0]} under {spec.capacity_label}."),
                _criterion("compare_accelerated_plan", "accelerated_completion", 1.0, f"Calculated {spec.options[1]} outcome as {option_dates[1]} using {spec.external_label}."),
                _criterion("compare_escalated_plan", "escalated_completion", 1.0, f"Calculated {spec.options[2]} outcome as {option_dates[2]} and kept its separate-approval condition."),
                _criterion("read_standard_external_readiness", "standard_external_readiness", 1.0, f"Read {standard_readiness} as the independently confirmed standard readiness date for {spec.external_label}."),
                _criterion("read_expedited_external_readiness", "expedited_external_readiness", 1.0, f"Read {expedited_readiness} as the independently confirmed expedited readiness date for {spec.external_label}."),
                _criterion("bound_external_recovery_quantity", "external_recovery_quantity", 1.0, f"Bound external recovery to the {int(gap)} {spec.unit} uncovered requirement rather than ordering the full header quantity."),
            ]
        )
        if scenario_title == "Commit one pallet of Luma lamps":
            answer.update(
                {
                    "earliest_qualified_base_slot": "2026-01-18",
                    "expedite_completion_days_saved": 0,
                    "weekend_shift_completion_days_saved": 2,
                }
            )
            descriptions.update(
                {
                    "earliest_qualified_base_slot": "First qualified non-displacing assembly slot after material readiness.",
                    "expedite_completion_days_saved": "Completion days saved by expedited bulbs after finite-capacity scheduling is reapplied.",
                    "weekend_shift_completion_days_saved": "Completion days the unapproved weekend shift would save versus the selected standard plan.",
                }
            )
            calculations.extend(
                [
                    _criterion("calculate_lamp_bom", "required_quantity", 2.0, "Calculated 120 Luma lamp kits × 4 revision-C bulbs per kit = 480 LMP-BULB-12 bulbs."),
                    _criterion("test_lamp_expedite_against_capacity", "expedite_completion_days_saved", 2.0, "Compared the 2026-01-14 expedited bulb readiness with the first non-displacing WC-2 slot on 2026-01-18 and proved that expediting alone still completes on 2026-01-20, saving 0 days."),
                    _criterion("test_lamp_weekend_shift", "weekend_shift_completion_days_saved", 2.0, "Calculated that the 2026-01-17 weekend slot would complete on 2026-01-18, two days earlier than the selected plan, but kept it outside action because the shift lacks approval."),
                ]
            )
    elif mode == "quantity":
        answer.update(
            {
                "controlled_item_or_record": item,
                "source_quantity": int(scope),
                "observed_quantity": int(observed),
                "excluded_quantity": int(excluded),
                "supported_quantity": int(eligible),
                "transaction_quantity": int(transaction_measure),
                "quantity_unit": spec.unit,
                "baseline_resolution_date": option_dates[0],
                "controlled_resolution_date": option_dates[1],
                "escalated_resolution_date": option_dates[2],
            }
        )
        descriptions.update(
            {
                "controlled_item_or_record": "Immutable item, lot, serial set, or transaction record in scope.",
                "source_quantity": spec.scope_label,
                "observed_quantity": f"Observed source quantity before applying the control for {spec.subject if hasattr(spec, 'subject') else subject}.",
                "excluded_quantity": spec.excluded_label,
                "supported_quantity": spec.eligible_label,
                "transaction_quantity": "Exact quantity the Oracle mutation may persist.",
                "quantity_unit": f"Unit of measure for every controlled quantity: {spec.unit}.",
                "baseline_resolution_date": f"Resolution date for {spec.options[0]}.",
                "controlled_resolution_date": f"Resolution date for {spec.options[1]}.",
                "escalated_resolution_date": f"Resolution date for {spec.options[2]}.",
            }
        )
        calculations.extend(
            [
                _criterion("establish_source_quantity", "source_quantity", 1.5, f"Established {int(scope)} {spec.unit} for {spec.scope_label}."),
                _criterion("reconcile_observed_quantity", "observed_quantity", 1.5, f"Correlated the independent source records to {int(observed)} observed {spec.unit}."),
                _criterion("identify_excluded_quantity", "excluded_quantity", 1.5, f"Removed {int(excluded)} {spec.unit} for {spec.excluded_label}."),
                _criterion("calculate_supported_quantity", "supported_quantity", 2.0, f"Calculated {int(observed)} observed − {int(excluded)} excluded = {int(eligible)} supported {spec.unit}."),
                _criterion("bound_transaction_quantity", "transaction_quantity", 2.0, f"Bound the Oracle transaction to exactly {int(transaction_measure)} {spec.unit}, the measure required by the chosen disposition; did not substitute the header or another business quantity."),
                _criterion("preserve_transaction_unit", "quantity_unit", 0.5, f"Kept the receipt, issue, transfer, inspection, or completion quantity in {spec.unit}."),
                _criterion("compare_quantity_option_one", "baseline_resolution_date", 1.0, f"Derived {option_dates[0]} for {spec.options[0]}."),
                _criterion("compare_quantity_option_two", "controlled_resolution_date", 1.0, f"Derived {option_dates[1]} for {spec.options[1]}."),
                _criterion("compare_quantity_option_three", "escalated_resolution_date", 1.0, f"Derived {option_dates[2]} for {spec.options[2]} and recognized its control impact."),
            ]
        )
    elif mode == "schedule":
        # Return the authoritative, evidence-visible provider record.  Earlier
        # releases synthesized labels such as WO-0016/OP-10 even though no source
        # exposed that composite value, which made the final-answer check a hidden
        # benchmark convention instead of an investigation result.
        affected_resource = record
        selected_resource = (
            f"WC-ALT-{1 + ordinal % 3}"
            if "work_order_operations.update" in primary_write
            else f"RES-ALT-{ordinal:03d}"
            if "work_order_resources.update" in primary_write
            else f"RES-CERT-{ordinal:03d}"
            if "work_order_resources.create" in primary_write
            else f"MAINT-{1 + ordinal % 3}"
            if "maintenance_operations.update" in primary_write
            else f"SUP-ACK-{ordinal:04d}"
            if "purchase_orders.acknowledge" in primary_write
            else identifiers["asset_or_resource"]
            if "maintenance_work_orders" in primary_write
            else identifiers["work_order"]
        )
        answer.update(
            {
                "affected_resource_or_operation": affected_resource,
                "required_capacity": int(scope),
                "candidate_capacity": int(observed),
                "unavailable_or_protected_capacity": int(excluded),
                "net_usable_capacity": int(eligible),
                "capacity_gap": int(gap),
                "capacity_unit": spec.unit,
                "selected_resource_or_control": selected_resource,
                "base_completion": option_dates[0],
                "qualified_alternative_completion": option_dates[1],
                "escalated_completion": option_dates[2],
            }
        )
        descriptions.update(
            {
                "affected_resource_or_operation": "Immutable operation, asset, supplier operation, or resource in the recovery scope.",
                "required_capacity": spec.scope_label,
                "candidate_capacity": f"Gross candidate capacity associated with {spec.eligible_label} before protected or unavailable load is removed.",
                "unavailable_or_protected_capacity": spec.excluded_label,
                "net_usable_capacity": f"Candidate capacity remaining after removing {spec.excluded_label}.",
                "capacity_gap": f"Uncovered {spec.unit} after applying finite availability.",
                "capacity_unit": f"Capacity unit used throughout the schedule comparison: {spec.unit}.",
                "selected_resource_or_control": "Provider identifier of the qualified resource, workcenter, asset, supplier control, or bounded order used by the selected recovery.",
                "base_completion": f"Completion under {spec.options[0]}.",
                "qualified_alternative_completion": f"Completion under {spec.options[1]}.",
                "escalated_completion": f"Completion under {spec.options[2]}.",
            }
        )
        calculations.extend(
            [
                _criterion("calculate_required_capacity", "required_capacity", 2.0, f"Calculated {int(scope)} {spec.unit} for {spec.scope_label}."),
                _criterion("establish_candidate_capacity", "candidate_capacity", 1.5, f"Established {int(observed)} gross candidate {spec.unit} associated with {spec.eligible_label}; did not call it usable before applying protected load."),
                _criterion("remove_protected_capacity", "unavailable_or_protected_capacity", 1.5, f"Excluded {int(excluded)} {spec.unit} for {spec.excluded_label}."),
                _criterion("calculate_net_usable_capacity", "net_usable_capacity", 2.0, f"Calculated {int(observed)} candidate − {int(excluded)} unavailable/protected = {int(eligible)} net usable {spec.unit}."),
                _criterion("calculate_capacity_gap", "capacity_gap", 2.0, f"Calculated {int(scope)} required − {int(eligible)} effective capacity = {int(gap)} {spec.unit} uncovered."),
                _criterion("preserve_capacity_unit", "capacity_unit", 0.5, f"Kept load and availability in {spec.unit}."),
                _criterion("identify_selected_resource_or_control", "selected_resource_or_control", 1.5, f"Bound the recovery to provider identifier {selected_resource} only after confirming {spec.constraint_label}."),
                _criterion("compare_base_schedule", "base_completion", 1.0, f"Calculated {option_dates[0]} for {spec.options[0]}."),
                _criterion("compare_qualified_schedule", "qualified_alternative_completion", 1.0, f"Calculated {option_dates[1]} for {spec.options[1]} using {spec.capacity_label}."),
                _criterion("compare_escalated_schedule", "escalated_completion", 1.0, f"Calculated {option_dates[2]} for {spec.options[2]} and retained its authority constraint."),
            ]
        )
    elif mode == "financial":
        control_label, control_threshold = _financial_control(
            scenario_title,
            scope=scope,
        )
        financial_record = (
            f"DRAFT-PO-{ordinal:04d}"
            if "draft_purchase_orders" in primary_write
            else identifiers["purchase_document"]
            if "purchase_orders" in primary_write
            else identifiers["invoice_reference"]
            if "invoice" in primary_write
            else identifiers["cost_reference"]
        )
        answer.update(
            {
                "financial_document_or_record": financial_record,
                "document_amount_usd": round(float(scope), 2),
                "supported_amount_usd": round(float(eligible), 2),
                "exception_amount_usd": round(float(gap), 2),
                "financial_control": control_label,
                "control_threshold_usd": control_threshold,
                "baseline_settlement_date": option_dates[0],
                "controlled_settlement_date": option_dates[1],
                "escalated_settlement_date": option_dates[2],
            }
        )
        descriptions.update(
            {
                "financial_document_or_record": "Immutable invoice, PO, cost record, or close exception being reconciled.",
                "document_amount_usd": spec.scope_label,
                "supported_amount_usd": spec.eligible_label,
                "exception_amount_usd": spec.excluded_label,
                "financial_control": "Task-specific monetary control that governs the action; it is not assumed to be an invoice tolerance.",
                "control_threshold_usd": f"Exact USD threshold for {control_label}.",
                "baseline_settlement_date": f"Posting, payment, or close date under {spec.options[0]}.",
                "controlled_settlement_date": f"Posting, payment, or close date under {spec.options[1]}.",
                "escalated_settlement_date": f"Posting, payment, or close date under {spec.options[2]}.",
            }
        )
        calculations.extend(
            [
                _criterion("establish_document_amount", "document_amount_usd", 2.0, f"Established the exact {spec.scope_label} as USD {float(scope):.2f}."),
                _criterion("calculate_supported_amount", "supported_amount_usd", 2.0, f"Reconciled independent source activity to USD {float(eligible):.2f} of {spec.eligible_label}."),
                _criterion("calculate_exception_amount", "exception_amount_usd", 2.0, f"Calculated USD {float(scope):.2f} document − USD {float(eligible):.2f} supported = USD {float(gap):.2f} exception for {spec.excluded_label}."),
                _criterion("identify_financial_control", "financial_control", 1.5, f"Identified {control_label} as the governing monetary control for {scenario_title}; did not substitute a generic invoice tolerance."),
                _criterion("apply_financial_control_threshold", "control_threshold_usd", 1.5, f"Applied the exact USD {control_threshold:.2f} threshold for {control_label} to the USD {float(gap):.2f} unsupported or residual value."),
                _criterion("compare_financial_option_one", "baseline_settlement_date", 1.0, f"Derived {option_dates[0]} for {spec.options[0]}."),
                _criterion("compare_financial_option_two", "controlled_settlement_date", 1.0, f"Derived {option_dates[1]} for {spec.options[1]}."),
                _criterion("compare_financial_option_three", "escalated_settlement_date", 1.0, f"Derived {option_dates[2]} for {spec.options[2]} and applied its approval impact."),
            ]
        )
        if scenario_title == "Award the enclosure tooling package":
            answer.update(
                {
                    "evaluated_bid_count": 3,
                    "technically_acceptable_bid_count": 2,
                    "selected_landed_cost_usd": round(float(eligible), 2),
                    "lowest_sticker_price_usd": 10_982.11,
                    "lowest_sticker_landed_cost_usd": 11_882.11,
                    "next_acceptable_landed_cost_usd": 11_680.50,
                    "sourcing_authority_headroom_usd": round(
                        250_000.0 - float(eligible), 2
                    ),
                }
            )
            descriptions.update(
                {
                    "evaluated_bid_count": "Commercial bids included in the controlled evaluation.",
                    "technically_acceptable_bid_count": "Bids that survived the independent technical gate.",
                    "selected_landed_cost_usd": "Supported landed cost of the best-value technically acceptable bid.",
                    "lowest_sticker_price_usd": "Sticker price of the superficially cheapest bid before freight and technical gating.",
                    "lowest_sticker_landed_cost_usd": "Landed cost of the lowest-sticker bid after freight; the bid still fails the technical gate.",
                    "next_acceptable_landed_cost_usd": "Landed cost of the other technically acceptable bid, which misses the launch-capacity date.",
                    "sourcing_authority_headroom_usd": "Remaining sourcing authority after the selected supported landed cost.",
                }
            )
            calculations.extend(
                [
                    _criterion("count_evaluated_bids", "evaluated_bid_count", 1.0, "Evaluated three supplier bids rather than comparing only the two lowest sticker prices."),
                    _criterion("apply_technical_bid_gate", "technically_acceptable_bid_count", 1.5, "Retained two technically acceptable bids after removing the noncompliant response."),
                    _criterion("calculate_selected_landed_cost", "selected_landed_cost_usd", 2.0, f"Calculated USD {float(eligible):.2f} as the supported landed cost after removing noncompliant lines and unsupported fees."),
                    _criterion("compare_lowest_sticker_landed_cost", "lowest_sticker_landed_cost_usd", 1.5, "Calculated USD 10,982.11 sticker + USD 900.00 freight = USD 11,882.11 landed for the superficially cheapest bid, then rejected it at the independent technical gate."),
                    _criterion("compare_next_acceptable_bid", "next_acceptable_landed_cost_usd", 1.5, "Calculated USD 11,680.50 landed for the other technically acceptable bid and kept its launch-capacity miss visible."),
                    _criterion("calculate_sourcing_authority_headroom", "sourcing_authority_headroom_usd", 1.5, f"Calculated USD 250,000.00 authority − USD {float(eligible):.2f} selected landed cost = USD {250_000.0 - float(eligible):.2f} remaining authority."),
                ]
            )
        elif scenario_title == "Release a hold after the supplier credit arrives":
            answer.update(
                {
                    "hold_amount_usd": round(float(scope), 2),
                    "matched_credit_amount_usd": round(float(eligible), 2),
                }
            )
            descriptions.update(
                {
                    "hold_amount_usd": "Exact amount on the one invoice hold in scope.",
                    "matched_credit_amount_usd": "Credit memo amount correlated to the same invoice, supplier, currency, and hold reason.",
                }
            )
            calculations.extend(
                [
                    _criterion("establish_held_variance", "hold_amount_usd", 1.5, f"Established the scoped hold amount as USD {float(scope):.2f}."),
                    _criterion("match_supplier_credit", "matched_credit_amount_usd", 2.0, f"Matched the USD {float(eligible):.2f} credit to that exact hold and proved a zero residual."),
                ]
            )
        elif scenario_title == "Correct payment terms from the signed contract":
            answer.update(
                {
                    "current_payment_term_days": 30,
                    "signed_payment_term_days": 45,
                    "payment_term_correction_days": 15,
                }
            )
            descriptions.update(
                {
                    "current_payment_term_days": "Days in the invoice's obsolete current payment term.",
                    "signed_payment_term_days": "Days in the effective supplier-site contract term.",
                    "payment_term_correction_days": "Signed term minus obsolete invoice term.",
                }
            )
            calculations.extend(
                [
                    _criterion("read_current_invoice_terms", "current_payment_term_days", 1.0, "Read Net 30 from the scoped invoice rather than the supplier master default."),
                    _criterion("read_signed_contract_terms", "signed_payment_term_days", 1.5, "Applied Net 45 from the executed, effective supplier-site contract."),
                    _criterion("calculate_term_correction", "payment_term_correction_days", 2.0, "Calculated 45 signed days − 30 obsolete invoice days = a 15-day correction on this invoice only."),
                ]
            )
        elif scenario_title == "Hold a duplicate invoice found in reconciliation":
            answer.update(
                {
                    "duplicate_invoice_amount_usd": round(float(scope), 2),
                    "payable_amount_usd": 0.0,
                }
            )
            descriptions.update(
                {
                    "duplicate_invoice_amount_usd": "Amount duplicated by the second invoice after normalized identity matching.",
                    "payable_amount_usd": "Supported payable amount for the confirmed duplicate; zero means hold it rather than pay it.",
                }
            )
            calculations.extend(
                [
                    _criterion("establish_duplicate_amount", "duplicate_invoice_amount_usd", 1.5, f"Established USD {float(scope):.2f} as the amount already represented by the original invoice."),
                    _criterion("calculate_duplicate_payable_amount", "payable_amount_usd", 2.0, "Calculated the confirmed duplicate's payable amount as USD 0.00 while leaving the original invoice untouched."),
                ]
            )
        if transaction_rate_usd is not None and transaction_unit != "USD":
            answer.update(
                {
                    "physical_transaction_quantity": transaction_measure,
                    "physical_transaction_unit": transaction_unit,
                    "approved_unit_rate_usd": transaction_rate_usd,
                }
            )
            descriptions.update(
                {
                    "physical_transaction_quantity": (
                        "Positive provider-posted quantity magnitude. The Oracle transaction type "
                        "supplies the issue, return, or reversal direction; do not negate a return."
                    ),
                    "physical_transaction_unit": "Provider unit of measure for the physical transaction.",
                    "approved_unit_rate_usd": "Approved unit rate used to bridge the physical transaction to the reconciled financial amount.",
                }
            )
            calculations.extend(
                [
                    _criterion(
                        "establish_physical_transaction_quantity",
                        "physical_transaction_quantity",
                        2.0,
                        f"Established the provider-posted quantity magnitude as {transaction_measure} {transaction_unit}; used the transaction type, not a negative sign, to carry issue or return direction.",
                    ),
                    _criterion(
                        "apply_approved_physical_rate",
                        "approved_unit_rate_usd",
                        1.5,
                        f"Applied the approved USD {transaction_rate_usd:.2f}/{transaction_unit} rate from the signed rate source.",
                    ),
                    _criterion(
                        "preserve_physical_transaction_unit",
                        "physical_transaction_unit",
                        0.5,
                        f"Kept the Oracle transaction in {transaction_unit}, rather than posting the reconciled USD amount as a physical quantity.",
                    ),
                ]
            )
    elif mode == "identity":
        match_key = f"{record}|{revision}|{identifiers['case_reference']}"
        answer.update(
            {
                "source_or_target_record": record,
                "candidate_record_count": int(scope),
                "matching_record_count": int(eligible),
                "excluded_record_count": int(gap),
                "effective_revision": revision,
                "immutable_match_key": match_key,
                "baseline_action_date": option_dates[0],
                "controlled_action_date": option_dates[1],
                "escalated_action_date": option_dates[2],
            }
        )
        descriptions.update(
            {
                "source_or_target_record": "Immutable source or target record identifier in the effectivity or traceability decision.",
                "candidate_record_count": spec.scope_label,
                "matching_record_count": spec.eligible_label,
                "excluded_record_count": spec.excluded_label,
                "effective_revision": "Effective approved revision after rejecting drafts and superseded records.",
                "immutable_match_key": (
                    "Pipe-delimited source_or_target_record|effective_revision|case_reference "
                    "used to correlate source and target without name matching."
                ),
                "baseline_action_date": f"Action date under {spec.options[0]}.",
                "controlled_action_date": f"Action date under {spec.options[1]}.",
                "escalated_action_date": f"Action date under {spec.options[2]}.",
            }
        )
        calculations.extend(
            [
                _criterion("enumerate_candidate_records", "candidate_record_count", 1.5, f"Enumerated {int(scope)} candidates for {spec.scope_label}."),
                _criterion("correlate_matching_records", "matching_record_count", 2.0, f"Correlated immutable identifiers and retained {int(eligible)} record(s) for {spec.eligible_label}."),
                _criterion("exclude_nonmatching_records", "excluded_record_count", 1.5, f"Excluded {int(gap)} candidate(s) for {spec.excluded_label}."),
                _criterion("apply_effective_revision", "effective_revision", 1.5, f"Applied released revision {revision}; did not select a draft or similarly named record."),
                _criterion("construct_immutable_match", "immutable_match_key", 2.0, f"Used composite match key {match_key} to correlate the source and target."),
                _criterion("compare_identity_option_one", "baseline_action_date", 1.0, f"Derived {option_dates[0]} for {spec.options[0]}."),
                _criterion("compare_identity_option_two", "controlled_action_date", 1.0, f"Derived {option_dates[1]} for {spec.options[1]}."),
                _criterion("compare_identity_option_three", "escalated_action_date", 1.0, f"Derived {option_dates[2]} for {spec.options[2]} and rejected any out-of-scope shortcut."),
            ]
        )
    elif mode == "forecast":
        if trigger_threshold is None:
            raise ValueError("forecast mode requires an explicit trigger threshold")
        answer.update(
            {
                "program_or_asset_record": identifiers["program_code"],
                "source_measure": int(scope),
                "qualifying_measure": int(eligible),
                "excluded_measure": int(gap),
                "measure_unit": spec.unit,
                "trigger_threshold": int(trigger_threshold),
                "due_date": forecast_timeline["due_date"],
                "safe_window_start": forecast_timeline["safe_window_start"],
                "forecast_horizon_end": forecast_timeline["forecast_horizon_end"],
                "baseline_program_date": option_dates[0],
                "alternative_program_date": option_dates[1],
                "escalated_program_date": option_dates[2],
            }
        )
        descriptions.update(
            {
                "program_or_asset_record": "Immutable maintenance program or asset identifier.",
                "source_measure": spec.scope_label,
                "qualifying_measure": spec.eligible_label,
                "excluded_measure": spec.excluded_label,
                "measure_unit": f"Unit used by the source measure and trigger: {spec.unit}.",
                "trigger_threshold": "Effective meter, event, due-row, or asset threshold that triggers the program action.",
                "due_date": "Due date calculated from the effective trigger after invalid or duplicate inputs are removed.",
                "safe_window_start": "First production-safe window on or after the controlled due date.",
                "forecast_horizon_end": "Last date inside the bounded generation horizon; it must not precede the safe window.",
                "baseline_program_date": f"Program action date under {spec.options[0]}.",
                "alternative_program_date": f"Program action date under {spec.options[1]}.",
                "escalated_program_date": f"Program action date under {spec.options[2]}.",
            }
        )
        calculations.extend(
            [
                _criterion("establish_forecast_source_measure", "source_measure", 1.5, f"Established {int(scope)} {spec.unit} for {spec.scope_label}."),
                _criterion("qualify_forecast_measure", "qualifying_measure", 2.0, f"Retained {int(eligible)} {spec.unit} for {spec.eligible_label}."),
                _criterion("exclude_invalid_forecast_measure", "excluded_measure", 1.5, f"Removed {int(gap)} {spec.unit} for {spec.excluded_label}."),
                _criterion("preserve_forecast_measure_unit", "measure_unit", 0.5, f"Applied the trigger and reconciliation in {spec.unit}."),
                _criterion("apply_trigger_threshold", "trigger_threshold", 2.0, f"Applied the effective {int(trigger_threshold)} {spec.unit} threshold under {spec.constraint_label}."),
                _criterion("calculate_due_date", "due_date", 1.5, f"Calculated {forecast_timeline['due_date']} from the qualifying measure and effective trigger."),
                _criterion("identify_safe_window", "safe_window_start", 1.5, f"Identified {forecast_timeline['safe_window_start']} as the first safe window under {spec.capacity_label}."),
                _criterion("bound_forecast_horizon", "forecast_horizon_end", 1.0, f"Bound generation at {forecast_timeline['forecast_horizon_end']}; did not use the emergency-option date as the horizon."),
                _criterion("compare_baseline_forecast_action", "baseline_program_date", 1.0, f"Calculated {spec.options[0]} outcome as {option_dates[0]} under {spec.capacity_label}."),
                _criterion("compare_alternative_forecast_action", "alternative_program_date", 1.0, f"Calculated {spec.options[1]} outcome as {option_dates[1]} using {spec.external_label}."),
                _criterion("compare_escalated_forecast_action", "escalated_program_date", 1.0, f"Calculated {spec.options[2]} outcome as {option_dates[2]} and kept its separate-approval condition."),
            ]
        )
    else:  # pragma: no cover - specs are validated at import/build time.
        raise ValueError(f"unknown decision mode: {mode}")

    calculations.extend(
        [
            _criterion(
                "calculate_selected_cost",
                "recommended_incremental_cost_usd",
                1.0,
                f"Applied USD {selected_cost} as the documented {economic_label} for {selected_option}; did not invent a premium where spend is not a decision driver.",
            ),
            _criterion(
                "apply_escalation_authority",
                "escalation_approval_required",
                1.0,
                f"Recognized that {spec.options[2]} remains outside current authority and requires an additional approval.",
            ),
            _criterion(
                "choose_task_specific_option",
                "recommended_option",
                2.0,
                f"Compared the timing, economic impact, control status, and consequence of {spec.options[0]}, {spec.options[1]}, and {spec.options[2]}; selected {selected_option} because it alone gives the best currently authorized result under {spec.constraint_label}.",
            ),
            _criterion(
                "calculate_recommended_outcome",
                "recommended_outcome_date",
                2.0,
                f"Calculated {selected_date} as the supported outcome date for {selected_option}.",
            ),
            _criterion(
                "calculate_outcome_variance",
                "outcome_vs_control_days",
                1.5,
                f"Compared {selected_date} with the independent control date {business_need} and calculated a signed variance of {timing_variance} day(s).",
            ),
            _criterion(
                "state_honest_timing_status",
                "decision_timing_status",
                1.0,
                f"Reported {timing_status}; did not relabel a controlled but late result as on time.",
            ),
        ]
    )
    return answer, descriptions, calculations


@lru_cache(maxsize=None)
def build_decision_case(scenario: "Scenario", ordinal: int) -> dict[str, Any]:
    """Build a scenario-specific, deterministic employee decision."""

    spec = SCENARIO_DECISION_SPECS[scenario.title]
    profile = FAMILY_PROFILES[scenario.family]
    identifiers = _identifier_values(ordinal)
    case_reference = f"CASE-{ordinal:03d}"
    record = f"NS-{ordinal:06d}"
    revision = f"R{1 + ordinal % 7}"
    item = f"NS-COMP-{ordinal:03d}"
    supplier = ("Cascade Industrial", "Rainier Components", "Olympic Metrology")[ordinal % 3]
    alternate_supplier = ("Evergreen Supply", "Sound Industrial", "Columbia Technical")[ordinal % 3]

    if spec.mode == "financial":
        scope: float | int = round(7_500 + ordinal * 137.25, 2)
        exception = round(max(125.0, float(scope) * (0.025 + (ordinal % 3) * 0.005)), 2)
        observed: float | int = scope
        excluded: float | int = exception
        eligible: float | int = round(float(scope) - exception, 2)
    elif spec.mode == "identity":
        scope = 3 + ordinal % 3
        observed = scope
        eligible = 1
        excluded = int(scope) - 1
    elif spec.mode == "forecast":
        scope, observed, excluded, eligible, _ = _FORECAST_DECISION_VALUES[
            scenario.title
        ]
    elif spec.mode == "schedule":
        scope = 32 + (ordinal * 7) % 49
        observed = max(8, int(scope) - (8 + ordinal % 13))
        excluded = 4 + ordinal % 9
        eligible = max(0, int(observed) - int(excluded))
    else:
        scope = 48 + (ordinal * 11) % 83
        excluded = max(1, int(scope) // (7 + ordinal % 4))
        observed = max(int(excluded), int(scope) - (5 + ordinal % 17) + int(excluded))
        eligible = max(0, int(observed) - int(excluded))
    gap: float | int = round(float(scope) - float(eligible), 2)
    unit_price = round(42.5 + ordinal * 1.17, 2)
    option_dates, business_need, forecast_timeline = _decision_timeline(spec, ordinal)

    if ordinal == 1:
        scope, observed, excluded, eligible, gap = 480, 420, 60, 360, 120
        option_dates = ("2026-01-20", "2026-01-20", "2026-01-18")
        business_need = "2026-01-21"
        item, revision = "LMP-BULB-12", "C"
    elif ordinal == 2:
        scope, observed, excluded, eligible, gap = 80, 80, 28, 52, 28
        option_dates = ("2026-02-02", "2026-01-20", "2026-01-14")
        business_need = "2026-01-21"
        item, revision = "CTRL-DEF-EXPORT", "R3"
    elif ordinal == 22:
        scope, observed, excluded, eligible, gap = 1, 2, 2, 0, 1
        option_dates = ("2026-01-25", "2026-01-22", "2026-01-21")
        business_need = "2026-01-22"
        item, revision = "PUMP-SEAL-HSG-07", "R4"
    elif ordinal == 38:
        scope, observed, excluded, eligible, gap = 162, 162, 36, 126, 36
        option_dates = ("2026-01-12", "2026-01-12", "2026-01-13")
        business_need = "2026-01-12"
        item, revision = "RCV-0038-LINE-1", "R4"
    elif ordinal == 57:
        scope, observed, excluded, eligible, gap = 94, 83, 0, 83, 11
        item, revision = "NS-COMP-057", "R2"

    if scenario.title in _FULLY_RECONCILED_TITLES:
        observed = scope
        excluded = 0
        eligible = scope
    if scenario.title == "Release the flight-test controller build":
        # The held components are visible in gross stock, but an equal amount
        # of additional released stock covers them; the build itself is fully
        # releasable.
        excluded = 12
        observed = float(scope) + float(excluded)
        eligible = scope
    if scenario.title in _EXPLICIT_DECISION_VALUES:
        scope, observed, excluded, eligible = _EXPLICIT_DECISION_VALUES[scenario.title]
    gap = round(float(scope) - float(eligible), 2)
    option_costs = _decision_option_costs(
        spec,
        ordinal,
        scope=scope,
        gap=gap,
        unit_price=unit_price,
    )
    if ordinal == 1:
        option_costs = (0, 640, 1_280)
    elif ordinal == 2:
        option_costs = (0, 0, 900)
    elif ordinal == 22:
        option_costs = (0, 1_480, 2_100)
    elif ordinal == 38:
        option_costs = (
            int(round(float(gap) * unit_price)),
            0,
            int(round(float(scope) * unit_price)),
        )
    elif ordinal == 31:
        option_costs = (0, 480, 1_200)

    transaction_measure, transaction_unit = _mutation_measure(
        scenario,
        spec,
        scope=scope,
        excluded=excluded,
        eligible=eligible,
        gap=gap,
    )
    transaction_rate_usd = _PHYSICAL_TRANSACTION_RATES_USD.get(scenario.title)
    duration_days = 1 + ordinal % 2
    standard_start = (
        date.fromisoformat(option_dates[0]) - timedelta(days=duration_days)
    ).isoformat()
    accelerated_start = (
        date.fromisoformat(option_dates[1]) - timedelta(days=duration_days)
    ).isoformat()
    standard_readiness = (
        date.fromisoformat(standard_start) - timedelta(days=1)
    ).isoformat()
    expedited_readiness = (
        date.fromisoformat(accelerated_start) - timedelta(days=1)
    ).isoformat()
    if ordinal == 1:
        standard_readiness = "2026-01-17"
        expedited_readiness = "2026-01-14"

    selected_index = spec.recommended_index
    selected_option = spec.options[selected_index]
    selected_completion = option_dates[selected_index]
    selected_cost = option_costs[selected_index]
    trigger_threshold = (
        _FORECAST_DECISION_VALUES[scenario.title][4]
        if spec.mode == "forecast"
        else None
    )
    financial_control = (
        _financial_control(scenario.title, scope=scope)
        if spec.mode == "financial"
        else (None, None)
    )

    answer, answer_descriptions, calculations = _mode_answer_bundle(
        scenario_title=scenario.title,
        mode=spec.mode,
        subject=spec.subject,
        spec=spec,
        scope=scope,
        observed=observed,
        excluded=excluded,
        eligible=eligible,
        gap=gap,
        revision=revision,
        item=item,
        record=record,
        identifiers=identifiers,
        primary_write=scenario.primary_write,
        option_dates=option_dates,
        option_costs=option_costs,
        selected_option=selected_option,
        selected_date=selected_completion,
        selected_cost=selected_cost,
        business_need=business_need,
        ordinal=ordinal,
        transaction_measure=transaction_measure,
        transaction_unit=transaction_unit,
        transaction_rate_usd=transaction_rate_usd,
        forecast_timeline=forecast_timeline,
        trigger_threshold=trigger_threshold,
        standard_readiness=standard_readiness,
        expedited_readiness=expedited_readiness,
    )

    effective_start = (
        date.fromisoformat(selected_completion) - timedelta(days=1 + ordinal % 2)
    ).isoformat()
    options = []
    for index, option_id in enumerate(spec.options):
        selected = index == selected_index
        escalated = index == 2 and not selected
        control_status = _option_control_status(
            option_id,
            selected=selected,
            escalated=escalated,
        )
        if selected:
            authority = "APPROVED"
        elif escalated:
            authority = "ADDITIONAL_APPROVAL_REQUIRED"
        elif control_status == "FAILS_CURRENT_CONTROL":
            authority = "NOT_SUPPORTED_BY_CURRENT_EVIDENCE"
        else:
            authority = "AVAILABLE_NOT_RECOMMENDED"
        consequence = _option_consequence(
            spec,
            option_id,
            completion=option_dates[index],
            business_need=business_need,
            option_cost=option_costs[index],
            selected_option=selected_option,
            selected_completion=selected_completion,
            selected_cost=selected_cost,
            selected=selected,
            escalated=escalated,
        )
        options.append(
            {
                "id": option_id,
                "label": (
                    f"{option_id}: outcome {option_dates[index]}, economic impact USD "
                    f"{option_costs[index]}, {control_status}"
                ),
                "completion": option_dates[index],
                "incremental_cost": option_costs[index],
                "approval": authority,
                "control_status": control_status,
                "consequence": consequence,
                "recommended": selected,
            }
        )

    internal_required = int(round(float(scope)))
    internal_observed = int(round(float(observed)))
    internal_excluded = int(round(float(excluded)))
    internal_eligible = int(round(float(eligible)))
    internal_gap = max(0, internal_required - internal_eligible)
    finished_quantity = 120 if ordinal == 1 else internal_required
    quantity_per_finished_unit = 4 if ordinal == 1 else 1
    approved_value = (
        round(float(scope), 2)
        if spec.mode == "financial"
        else round(internal_required * unit_price, 2)
    )
    selected_start = effective_start
    early_slot = option_dates[2]
    next_slot = option_dates[0]
    binding_constraint = (
        f"{spec.constraint_label}; {spec.excluded_label} = {excluded} {spec.unit}; "
        f"uncovered or unsupported scope = {gap} {spec.unit}"
    )
    alternative_impact = "; ".join(option["label"] for option in options)
    selected_variance = (
        date.fromisoformat(selected_completion) - date.fromisoformat(business_need)
    ).days
    timing_reason = (
        f"is honestly {selected_variance} day(s) late because no faster option passes the control"
        if selected_variance > 0
        else f"lands {abs(selected_variance)} day(s) on or before the control date"
    )
    recommendation_reason = (
        f"{selected_option} is the only best-authorized response that satisfies "
        f"{spec.constraint_label} and {timing_reason}."
    )

    case: dict[str, Any] = {
        "request": human_request(scenario),
        "case_reference": case_reference,
        "record": record,
        "record_noun": spec.subject,
        "decision_mode": spec.mode,
        "forecast_timeline": forecast_timeline,
        "decision_spec": spec,
        "source_document": spec.source_document,
        "item": item,
        "revision": revision,
        "supplier": supplier,
        "alternate_supplier": alternate_supplier,
        "identifiers": identifiers,
        "requested_quantity": finished_quantity,
        "per_unit": quantity_per_finished_unit,
        "required_quantity": internal_required,
        "physical_quantity": internal_observed,
        "excluded_quantity": internal_excluded,
        "usable_quantity": internal_eligible,
        "shortage": internal_gap,
        "external_recovery_quantity": internal_gap,
        "unit": spec.unit,
        "unit_price": unit_price,
        "approved_value": approved_value,
        "committed_measure": transaction_measure,
        "transaction_measure": transaction_measure,
        "transaction_unit": transaction_unit,
        "transaction_rate_usd": transaction_rate_usd,
        "financial_control": financial_control,
        "supported_value": round(float(eligible), 2),
        "early_slot": early_slot,
        "standard_arrival": standard_readiness,
        "expedite_arrival": expedited_readiness,
        "next_slot": next_slot,
        "duration_days": duration_days,
        "standard_start": standard_start,
        "standard_finish": option_dates[0],
        "expedite_start": accelerated_start,
        "expedite_finish": option_dates[1],
        "overtime_start": (
            date.fromisoformat(option_dates[2]) - timedelta(days=1)
        ).isoformat(),
        "overtime_finish": option_dates[2],
        "overtime_duration_days": 1,
        "requested_by": business_need,
        "selected_start": selected_start,
        "selected_completion": selected_completion,
        "selected_cost": selected_cost,
        "selected_option": selected_option,
        "binding_constraint": binding_constraint,
        "alternative_impact": alternative_impact,
        "recommendation_reason": recommendation_reason,
        "stakeholder": profile.stakeholder,
        "profile": profile,
        "options": options,
        "oracle_reads": _scenario_oracle_reads(scenario),
        "raw_decision_values": {
            "scope": scope,
            "observed": observed,
            "excluded": excluded,
            "eligible": eligible,
            "gap": gap,
            "option_dates": option_dates,
            "option_costs": option_costs,
            "transaction_measure": transaction_measure,
            "transaction_unit": transaction_unit,
            "transaction_rate_usd": transaction_rate_usd,
            "trigger_threshold": trigger_threshold,
            "forecast_timeline": forecast_timeline,
            "financial_control_label": financial_control[0],
            "financial_control_threshold_usd": financial_control[1],
        },
    }

    case["facts"] = [
        {
            "id": "authoritative_identity",
            "sources": ["oracle_fusion"],
            "statement": f"{case_reference} resolves to immutable record {case['record']} for {spec.subject}; the effective revision is {revision}.",
            "rubric": f"Located {case['record']} for {spec.subject} using immutable IDs and preserved effective revision {revision}.",
        },
        {
            "id": "effective_requirement",
            "sources": ["oracle_fusion", "google_drive"],
            "statement": f"The effective source record states {spec.scope_label} = {scope} {spec.unit} at revision {revision}. The business control date is {business_need}.",
            "rubric": f"Applied revision {revision} and established {scope} {spec.unit} for {spec.scope_label}, with control date {business_need}.",
        },
        {
            "id": "eligible_coverage",
            "sources": ["oracle_fusion", "google_sheets"],
            "statement": f"Independent source rows show {observed} {spec.unit} observed. A separate exclusion row identifies {excluded} {spec.unit} for {spec.excluded_label}; eligibility requires subtraction rather than trusting the header total.",
            "rubric": f"Reconciled {observed} observed less {excluded} excluded to {eligible} supported {spec.unit} for {spec.eligible_label}.",
        },
        {
            "id": "conditional_external_recovery",
            "sources": ["gmail", "google_drive"],
            "statement": (
                f"{spec.external_label}: the independent source confirms readiness for "
                f"{spec.options[1]} on {expedited_readiness}; finite-capacity scheduling produces "
                f"the separate operating outcome {option_dates[1]}"
                + (
                    f" with economic impact USD {option_costs[1]}"
                    if option_costs[1]
                    else " with no separately documented spend"
                )
                + "; that source alone does not prove eligibility, identity, or approval."
            ),
            "rubric": (
                f"Used the independently confirmed {expedited_readiness} readiness input for {spec.options[1]}, "
                f"then separately derived its {option_dates[1]} operating outcome under {spec.constraint_label} instead of treating an external promise as authorization or a completion date."
            ),
        },
        {
            "id": "finite_capacity",
            "sources": ["oracle_fusion", "google_sheets"],
            "statement": f"{spec.capacity_label}: source windows are {option_dates[0]} for {spec.options[0]}, {option_dates[1]} for {spec.options[1]}, and {option_dates[2]} for {spec.options[2]}; protected or ineligible scope cannot be displaced.",
            "rubric": f"Applied {spec.capacity_label} to derive the three option outcomes without using excluded or protected scope.",
        },
        {
            "id": "approval_scope",
            "sources": ["slack", "google_drive"],
            "statement": (
                f"Approval AP-{ordinal:04d} permits one control-compliant action on {case['record']} "
                f"up to {transaction_measure} {transaction_unit}, provided {spec.constraint_label}. "
                f"It does not select an option in advance and does not authorize broader records or {spec.options[2]}."
            ),
            "rubric": (
                f"Applied AP-{ordinal:04d} only to {selected_option}, {case['record']}, and the "
                f"supported {transaction_measure} {transaction_unit}; kept broader scope and {spec.options[2]} outside current authority."
            ),
        },
        {
            "id": "business_impact",
            "sources": ["gmail", "slack"],
            "statement": f"{profile.stakeholder.capitalize()} needs one defensible decision for {spec.subject} by {business_need}; a faster or broader action has value only if it remains inside {spec.constraint_label}.",
            "rubric": f"Compared all three scenario-specific alternatives and selected {selected_option}: {recommendation_reason}",
        },
    ]

    case["answer"] = answer
    case["answer_descriptions"] = answer_descriptions
    case["calculations"] = calculations
    return case


def source_fact_text(case: dict[str, Any], source: str) -> str:
    """Return only the facts mounted in one source system."""

    facts = [fact["statement"] for fact in case["facts"] if source in fact["sources"]]
    return "\n".join(facts)


def fact_for_oracle_tool(case: dict[str, Any], tool: str) -> dict[str, Any]:
    """Choose the decision fact represented by an Oracle resource collection."""

    if any(token in tool for token in ("inventory_onhand", "quality_inspection", "receiving_receipt", "cycle_count_sequence", "cycle_count_history")):
        fact_id = "eligible_coverage"
    elif any(token in tool for token in ("work_order_material", "maintenance_materials", "sales_orders", "purchase_order_lines", "invoices", "cycle_count_definitions")):
        fact_id = "effective_requirement"
    elif any(token in tool for token in ("work_order_operations", "work_order_resources", "maintenance_operations", "maintenance_resources")):
        fact_id = "finite_capacity"
    elif any(token in tool for token in ("suppliers", "purchase_orders", "supply_requests")):
        fact_id = "conditional_external_recovery"
    else:
        fact_id = "authoritative_identity"
    return next(fact for fact in case["facts"] if fact["id"] == fact_id)


__all__ = [
    "FAMILY_PROFILES",
    "FamilyProfile",
    "build_decision_case",
    "fact_for_oracle_tool",
    "human_request",
    "source_fact_text",
]
