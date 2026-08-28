"""One hundred independently authored enterprise workflow blueprints.

There are no numeric variants in this corpus.  Each entry names a different
operational incident, source mix, Oracle operation, and required outcome.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    family: str
    role: str
    title: str
    outcome: str
    support_read: str
    primary_read: str
    primary_write: str
    result_status: str
    answer_keys: tuple[str, str, str]


FAMILY_LABELS = {
    "customer_commitment": "Customer commitment",
    "production_control": "Production control",
    "material_execution": "Material execution",
    "capacity_recovery": "Capacity recovery",
    "corrective_maintenance": "Corrective maintenance",
    "preventive_maintenance": "Preventive maintenance",
    "strategic_procurement": "Strategic procurement",
    "receiving_control": "Receiving control",
    "payables_control": "Payables control",
    "supplier_governance": "Supplier governance",
    "quality_execution": "Quality execution",
    "inventory_control": "Inventory control",
    "supply_planning": "Supply planning",
    "engineering_change": "Engineering change",
    "cost_accounting": "Cost accounting",
    "project_manufacturing": "Project manufacturing",
    "field_service_supply": "Field-service supply",
    "compliance_traceability": "Compliance & traceability",
    "period_close": "Period close",
    "supplier_operations": "Supplier operations",
}

FAMILY_DESCRIPTIONS = {
    "customer_commitment": "Reconcile customer correspondence, contractual commitments, and Order Management state before changing supply execution.",
    "production_control": "Release or revise discrete production only after checking drawings, dispatch state, materials, and resource constraints.",
    "material_execution": "Post traceable material, inventory, operation, and resource transactions from controlled shop-floor evidence.",
    "capacity_recovery": "Recover constrained production with approved work-center, labor, tooling, and timing decisions.",
    "corrective_maintenance": "Convert equipment failures into auditable maintenance work, routing, resources, and technical references.",
    "preventive_maintenance": "Maintain meter- and calendar-driven programs and generate bounded forecasts and work orders.",
    "strategic_procurement": "Turn approved demand and supplier evidence into correctly controlled purchase-order actions.",
    "receiving_control": "Process receipt, inspection, correction, delivery, and return evidence against source documents.",
    "payables_control": "Apply Oracle invoice validation and hold operations to multi-document invoice evidence.",
    "supplier_governance": "Combine supplier master, performance, approval, and collaboration evidence into controlled ERP follow-up.",
    "quality_execution": "Execute inspection plans and disposition evidence while preserving lot and result traceability.",
    "inventory_control": "Correct and move lot-, serial-, project-, and organization-controlled inventory through documented transactions.",
    "supply_planning": "Create or revise supply execution from shortages, allocation decisions, and constrained-plan approvals.",
    "engineering_change": "Apply approved engineering changes to active work-order operations, materials, resources, and attachments.",
    "cost_accounting": "Post and reconcile production actuals against time, material, invoice, and close evidence.",
    "project_manufacturing": "Preserve project and task attribution while moving material and revising production supply.",
    "field_service_supply": "Replenish and recover technician stock from field evidence without losing item or ownership controls.",
    "compliance_traceability": "Contain regulated material and assemble document, lot, serial, and approval evidence for audit.",
    "period_close": "Resolve purchasing, receiving, invoice, and production exceptions before the accounting cutoff.",
    "supplier_operations": "Coordinate outside processing purchase orders, receipts, yield, and manufacturing completion.",
}


def _s(
    family: str,
    role: str,
    support_read: str,
    answer_keys: tuple[str, str, str],
    rows: tuple[tuple[str, str, str, str, str], ...],
) -> list[Scenario]:
    return [
        Scenario(
            family=family,
            role=role,
            title=title,
            outcome=outcome,
            support_read=support_read,
            primary_read=primary_read,
            primary_write=primary_write,
            result_status=result_status,
            answer_keys=answer_keys,
        )
        for title, outcome, primary_read, primary_write, result_status in rows
    ]


SCENARIOS = tuple(
    [
        *_s(
            "customer_commitment",
            "order_fulfillment_manager",
            "oracle_fusion.sales_orders.list",
            ("order_number", "supply_action", "revised_commit_date"),
            (
                ("Expedite a penalty-backed hospital order", "Verify the signed service-level addendum and planner approval, then move the linked production supply to the approved commit date and notify the account team.", "oracle_fusion.sales_orders.get", "oracle_fusion.work_orders.update", "Rescheduled"),
                ("Split a defense order around an export hold", "Separate the unrestricted domestic quantity from the export-controlled line, create supply only for the released demand, and document the split for compliance.", "oracle_fusion.sales_orders.get", "oracle_fusion.supply_requests.create", "Partial supply created"),
                ("Recover a customer promise after a carrier rollover", "Reconcile the carrier email, allocation sheet, and customer thread, then revise the production completion supporting the new confirmed delivery.", "oracle_fusion.work_orders.get", "oracle_fusion.work_orders.update", "Customer commit recovered"),
                ("Replace an obsolete configuration before fulfillment", "Confirm engineering approval for the replacement configuration and revise the open manufacturing material without changing the customer's contracted quantity.", "oracle_fusion.work_order_materials.list", "oracle_fusion.work_order_materials.replace_with_substitute", "Approved substitute applied"),
                ("Stop supply for a duplicated customer release", "Prove that the EDI release duplicates an existing order and cancel only the unconsumed purchase commitment created for the duplicate.", "oracle_fusion.purchase_orders.get", "oracle_fusion.purchase_orders.cancel", "Duplicate supply canceled"),
            ),
        ),
        *_s(
            "production_control",
            "production_planner",
            "oracle_fusion.work_orders.list",
            ("work_order", "production_decision", "effective_timestamp"),
            (
                ("Release the flight-test controller build", "Check the released drawing, approved deviation, material readiness, and dispatch window before creating the discrete work order.", "oracle_fusion.inventory_onhand_balances.list", "oracle_fusion.work_orders.create", "Work order created"),
                ("Resequence burn-in ahead of final assembly", "Use the dispatch escalation and capacity workbook to revise the active operation dates without changing completed quantities.", "oracle_fusion.work_order_operations.list", "oracle_fusion.work_order_operations.update", "Operation resequenced"),
                ("Insert an approved rework operation", "Confirm the quality disposition and approved routing note, then add the rework step to the active order and alert the cell lead.", "oracle_fusion.quality_inspection_results.list", "oracle_fusion.work_order_operations.create", "Rework operation added"),
                ("Replace a constrained relay on an active order", "Match the engineering substitute authorization to the correct material line and replace it at the approved quantity.", "oracle_fusion.work_order_materials.list", "oracle_fusion.work_order_materials.replace_with_substitute", "Material substituted"),
                ("Assign certified contract labor to wiring", "Verify the training certificate, approved rate, and remaining capacity before adding the resource to the wiring operation.", "oracle_fusion.work_order_resources.list", "oracle_fusion.work_order_resources.create", "Certified resource assigned"),
            ),
        ),
        *_s(
            "material_execution",
            "shop_floor_controller",
            "oracle_fusion.inventory_onhand_balances.list",
            ("transaction_reference", "item_lot", "posted_quantity"),
            (
                ("Issue the earliest-expiry conforming adhesive", "Reconcile the reservation, shelf-life waiver, and lot certificate before posting the exact work-order material issue.", "oracle_fusion.work_order_materials.list", "oracle_fusion.material_transactions.create", "Material issued"),
                ("Return unused copper from a canceled operation", "Confirm the cancellation and physical count, then return the excess from WIP to the original controlled subinventory.", "oracle_fusion.work_orders.get", "oracle_fusion.material_transactions.create", "Material returned"),
                ("Correct a wrong-lot scan before consumption", "Use the scanner log and supervisor confirmation to reverse the erroneous inventory movement and post the verified lot.", "oracle_fusion.inventory_onhand_balances.list", "oracle_fusion.inventory_transactions.create", "Lot correction posted"),
                ("Report serial-controlled panel completion", "Check all electronic traveler signatures and serial assignments before moving the completed quantity through the final operation.", "oracle_fusion.work_order_operations.list", "oracle_fusion.operation_transactions.create", "Serial completion posted"),
                ("Post calibrated test-bench labor actuals", "Match the signed timecard and calibration window to the correct operation before posting resource usage.", "oracle_fusion.work_order_resources.list", "oracle_fusion.resource_transactions.create", "Resource actuals posted"),
            ),
        ),
        *_s(
            "capacity_recovery",
            "manufacturing_scheduler",
            "oracle_fusion.work_order_operations.list",
            ("affected_order", "recovery_route", "revised_completion"),
            (
                ("Reroute assembly after a spindle failure", "Confirm the downtime diagnosis, alternate-cell qualification, open load, and manager approval before rerouting the affected operation.", "oracle_fusion.maintenance_work_orders.get", "oracle_fusion.work_order_operations.update", "Alternate cell scheduled"),
                ("Recover output after a certified welder absence", "Use the shift roster and skills matrix to assign the approved labor resource and preserve the customer commit.", "oracle_fusion.work_order_resources.list", "oracle_fusion.work_order_resources.update", "Labor capacity recovered"),
                ("Move outsourced coating around a supplier outage", "Reconcile the supplier notice, open PO line, and qualified alternate before revising the outside-processing resource.", "oracle_fusion.purchase_order_lines.list", "oracle_fusion.work_order_resources.update", "Supplier operation rerouted"),
                ("Apply approved weekend overtime to backlog", "Verify the overtime authorization and finite-capacity workbook before moving operation dates and reporting the schedule change.", "oracle_fusion.work_orders.get", "oracle_fusion.work_order_operations.update", "Overtime plan applied"),
                ("Hold production for an expired torque-tool calibration", "Confirm the expired certificate and affected serial range, then move the operation out of the unsafe window and create corrective maintenance.", "oracle_fusion.maintenance_programs.get", "oracle_fusion.maintenance_work_orders.create", "Calibration recovery opened"),
            ),
        ),
        *_s(
            "corrective_maintenance",
            "maintenance_planner",
            "oracle_fusion.maintenance_work_orders.list",
            ("maintenance_order", "asset_or_resource", "planned_finish"),
            (
                ("Open repair for a failed servo drive", "Correlate the alarm email, technician Slack thread, fault-history export, and service manual before opening the high-priority asset work order.", "oracle_fusion.maintenance_programs.get", "oracle_fusion.maintenance_work_orders.create", "Corrective work opened"),
                ("Extend a pump repair after teardown findings", "Use the teardown photos, parts quote, and approved scope change to update the existing maintenance order dates and description.", "oracle_fusion.maintenance_work_orders.get", "oracle_fusion.maintenance_work_orders.update", "Repair scope revised"),
                ("Move a repair to the qualified electrical shop", "Check shop qualification and current load before changing the maintenance operation's work center.", "oracle_fusion.maintenance_operations.list", "oracle_fusion.maintenance_operations.update", "Repair operation rerouted"),
                ("Attach the vendor diagnostic report to maintenance", "Verify the report belongs to the failed asset and create the document reference on the existing work order.", "oracle_fusion.maintenance_documents.list", "oracle_fusion.maintenance_documents.create", "Diagnostic reference attached"),
                ("Convert a repeated bearing alarm into planned work", "Confirm the third qualifying alarm and reliability approval before creating the recurring maintenance program.", "oracle_fusion.maintenance_work_orders.list", "oracle_fusion.maintenance_programs.create", "Recurring program created"),
            ),
        ),
        *_s(
            "preventive_maintenance",
            "reliability_engineer",
            "oracle_fusion.maintenance_programs.list",
            ("program_code", "generation_action", "forecast_horizon"),
            (
                ("Advance lubrication after a meter spike", "Validate the meter export and reliability threshold, then revise the program forecast window without altering unrelated assets.", "oracle_fusion.maintenance_programs.get", "oracle_fusion.maintenance_programs.update", "Forecast window advanced"),
                ("Generate the quarterly compressor forecast", "Check the approved calendar pattern and blackout dates before generating the bounded maintenance forecast.", "oracle_fusion.maintenance_programs.get", "oracle_fusion.maintenance_programs.generate_forecasts", "Forecast generated"),
                ("Create due work for guarded saw inspections", "Reconcile the approved forecast due dates with the shutdown calendar before generating work orders.", "oracle_fusion.maintenance_work_orders.list", "oracle_fusion.maintenance_programs.generate_work_orders", "Due work generated"),
                ("Create a contamination-control program", "Use the signed sanitation standard, asset roster, and quality approval to establish a new active maintenance program.", "oracle_fusion.quality_inspection_results.list", "oracle_fusion.maintenance_programs.create", "Program activated"),
                ("Link the revised lockout procedure to PM work", "Confirm the revision is approved and attach its document reference to the correct generated maintenance order.", "oracle_fusion.maintenance_work_orders.get", "oracle_fusion.maintenance_documents.create", "Procedure linked"),
            ),
        ),
        *_s(
            "strategic_procurement",
            "buyer",
            "oracle_fusion.suppliers.list",
            ("purchase_document", "supplier_decision", "committed_value"),
            (
                ("Award the enclosure tooling package", "Compare the technical bid, commercial workbook, supplier status, and approval thread before creating the draft purchase order.", "oracle_fusion.draft_purchase_orders.list", "oracle_fusion.draft_purchase_orders.create", "Draft purchase order created"),
                ("Record the supplier's expedited promise", "Match the signed acknowledgment email to the open PO and record the supplier order reference and note.", "oracle_fusion.purchase_orders.get", "oracle_fusion.purchase_orders.acknowledge", "Supplier promise acknowledged"),
                ("Cancel a resin order after a safety bulletin", "Verify the affected material and remaining open quantity, then cancel the PO with the approved reason and notify stakeholders.", "oracle_fusion.purchase_order_lines.list", "oracle_fusion.purchase_orders.cancel", "Unsafe supply canceled"),
                ("Close a fully received calibration-services PO", "Reconcile accepted service entry, invoice status, and buyer approval before closing the PO for receiving and invoicing.", "oracle_fusion.purchase_orders.get", "oracle_fusion.purchase_orders.close", "Purchase order closed"),
                ("Create emergency supply for a line-down shortage", "Net usable inventory, verify the approved sole-source exception, and create the bounded supply request for the shortage.", "oracle_fusion.inventory_onhand_balances.list", "oracle_fusion.supply_requests.create", "Emergency supply requested"),
            ),
        ),
        *_s(
            "receiving_control",
            "receiving_specialist",
            "oracle_fusion.receiving_receipt_requests.list",
            ("receipt_reference", "inspection_disposition", "accepted_quantity"),
            (
                ("Receive a lot-controlled relay shipment", "Match packing slip, PO, certificate, and dock count before creating the receipt request with the supplier lot.", "oracle_fusion.purchase_orders.get", "oracle_fusion.receiving_receipt_requests.create", "Receipt request created"),
                ("Reject water-damaged enclosures at inspection", "Use dock photos and the inspection plan to post the rejected receiving transaction and preserve the carrier claim evidence.", "oracle_fusion.receiving_receipt_transactions.list", "oracle_fusion.receiving_receipt_transactions.create", "Receipt rejected"),
                ("Correct a transposed receiving quantity", "Reconcile scale ticket, packing slip, and receiver acknowledgment before updating only the erroneous interface transaction.", "oracle_fusion.receiving_receipt_transactions.list", "oracle_fusion.receiving_receipt_transactions.update", "Receipt quantity corrected"),
                ("Deliver inspected copper to project stores", "Verify inspection acceptance and project ownership before posting the inventory delivery transaction to the controlled subinventory.", "oracle_fusion.quality_inspection_results.list", "oracle_fusion.inventory_transactions.create", "Accepted stock delivered"),
                ("Return mislabeled relays to the supplier", "Confirm the label nonconformance and return authorization before creating the return receiving transaction.", "oracle_fusion.purchase_order_lines.list", "oracle_fusion.receiving_receipt_transactions.create", "Return transaction created"),
            ),
        ),
        *_s(
            "payables_control",
            "accounts_payable_specialist",
            "oracle_fusion.invoices.get",
            ("invoice_number", "validation_outcome", "hold_or_reference"),
            (
                ("Validate a clean three-way-matched invoice", "Compare the supplier PDF, PO line, accepted receipt, and tolerance policy before invoking Oracle invoice validation.", "oracle_fusion.purchase_order_lines.list", "oracle_fusion.invoices.validate", "Validated"),
                ("Place a freight-variance hold", "Confirm freight is excluded from the PO and exceeds tolerance, then create the documented Payables hold with the approved reason.", "oracle_fusion.purchase_orders.get", "oracle_fusion.invoice_holds.create", "Freight hold placed"),
                ("Release a hold after the supplier credit arrives", "Match the credit memo and manager approval to the existing hold before recording its release reason.", "oracle_fusion.invoices.get", "oracle_fusion.invoice_holds.update", "Hold released"),
                ("Correct payment terms from the signed contract", "Verify the executed agreement and supplier site before updating only the invoice payment terms.", "oracle_fusion.suppliers.get", "oracle_fusion.invoices.update", "Payment terms corrected"),
                ("Enter a non-PO metrology invoice", "Extract the invoice PDF, validate business unit and approval coding, and create the Payables invoice without inventing a purchase order.", "oracle_fusion.suppliers.get", "oracle_fusion.invoices.create", "Invoice entered"),
            ),
        ),
        *_s(
            "supplier_governance",
            "supplier_quality_manager",
            "oracle_fusion.suppliers.list",
            ("supplier", "governance_action", "case_reference"),
            (
                ("Approve a conditional alternate for molded parts", "Reconcile audit results, insurance certificate, trial-lot quality, and sourcing approval before documenting conditional use and creating supply.", "oracle_fusion.suppliers.get", "oracle_fusion.supply_requests.create", "Conditional source enabled"),
                ("Escalate sole-source spend concentration", "Combine supplier master, open PO exposure, spend workbook, and controller approval before recording the mitigation action.", "oracle_fusion.purchase_orders.list", "oracle_fusion.purchase_orders.acknowledge", "Mitigation acknowledged"),
                ("Suspend orders after a sanctions-screening hit", "Verify the screening match and legal direction before canceling the identified open PO and notifying procurement leadership.", "oracle_fusion.purchase_orders.get", "oracle_fusion.purchase_orders.cancel", "Supplier order suspended"),
                ("Close a supplier remediation purchase order", "Confirm every corrective-action deliverable was accepted and invoiced before finally closing the remediation PO.", "oracle_fusion.purchase_order_lines.list", "oracle_fusion.purchase_orders.close", "Remediation PO closed"),
                ("Open maintenance after vendor-caused equipment damage", "Correlate the supplier incident report and technician evidence to the asset before creating corrective maintenance and an audit trail.", "oracle_fusion.maintenance_work_orders.list", "oracle_fusion.maintenance_work_orders.create", "Vendor incident work opened"),
            ),
        ),
        *_s(
            "quality_execution",
            "quality_engineer",
            "oracle_fusion.inspection_plans.list",
            ("inspection_reference", "quality_result", "controlled_quantity"),
            (
                ("Create incoming inspection for plated busbars", "Select the approved receiving inspection plan and create a result record tied to the receipt and supplier lot.", "oracle_fusion.receiving_receipt_transactions.list", "oracle_fusion.quality_inspection_results.create", "Inspection created"),
                ("Record failed dielectric-test samples", "Transcribe the signed lab worksheet into the correct inspection result and preserve sample-level values.", "oracle_fusion.quality_inspection_results.list", "oracle_fusion.quality_inspection_results.update", "Failed result recorded"),
                ("Correct a mistyped dimensional result", "Compare the instrument export and technician correction note before updating only the erroneous characteristic value.", "oracle_fusion.quality_inspection_results.list", "oracle_fusion.quality_inspection_results.update", "Inspection result corrected"),
                ("Quarantine an expired chemical lot", "Confirm expiry, remaining on-hand, and quality direction before posting the inventory status movement.", "oracle_fusion.inventory_onhand_balances.list", "oracle_fusion.inventory_transactions.create", "Lot quarantined"),
                ("Create rework supply from a failed final inspection", "Use the approved disposition and remaining good quantity to create the specific rework supply request.", "oracle_fusion.quality_inspection_results.list", "oracle_fusion.supply_requests.create", "Rework supply created"),
            ),
        ),
        *_s(
            "inventory_control",
            "inventory_control_manager",
            "oracle_fusion.inventory_onhand_balances.list",
            ("inventory_transaction", "from_to_location", "controlled_quantity"),
            (
                ("Transfer a constrained relay lot between plants", "Check donor availability, lot status, transit lead time, and allocation approval before posting the interorganization movement.", "oracle_fusion.supply_requests.list", "oracle_fusion.inventory_transactions.create", "Interorganization transfer posted"),
                ("Post a blind cycle-count adjustment", "Reconcile independent count sheets and recount approval before posting the bounded quantity correction.", "oracle_fusion.inventory_onhand_balances.list", "oracle_fusion.inventory_transactions.create", "Cycle count adjusted"),
                ("Move suspect housings into quarantine", "Match the supplier alert to affected lots and post only those quantities to the quarantine subinventory.", "oracle_fusion.quality_inspection_results.list", "oracle_fusion.inventory_transactions.create", "Suspect stock quarantined"),
                ("Return excess project copper to common stock", "Verify project completion and finance release before moving residual project-owned inventory to common stores.", "oracle_fusion.work_orders.get", "oracle_fusion.inventory_transactions.create", "Project stock returned"),
                ("Create supply for an approved kanban breach", "Validate the physical count and min-max exception before creating a replenishment supply request.", "oracle_fusion.supply_requests.list", "oracle_fusion.supply_requests.create", "Replenishment requested"),
            ),
        ),
        *_s(
            "supply_planning",
            "supply_planner",
            "oracle_fusion.supply_requests.list",
            ("supply_reference", "planning_action", "need_by_date"),
            (
                ("Cover an unplanned copper demand spike", "Net the revised demand workbook against usable on-hand and create supply for only the uncovered quantity.", "oracle_fusion.inventory_onhand_balances.list", "oracle_fusion.supply_requests.create", "Shortage supply created"),
                ("Pull in supply after a forecast-consumption jump", "Verify sales-order consumption and supplier confirmation before revising the linked production dates.", "oracle_fusion.sales_orders.list", "oracle_fusion.work_orders.update", "Supply pulled in"),
                ("Cancel redundant purchase supply after demand deletion", "Confirm the demand removal and lack of downstream reservations before canceling the unneeded PO.", "oracle_fusion.purchase_orders.get", "oracle_fusion.purchase_orders.cancel", "Redundant supply canceled"),
                ("Replace a constrained component in planned work", "Use the approved substitute matrix and available stock to update the planned material line.", "oracle_fusion.work_order_materials.list", "oracle_fusion.work_order_materials.replace_with_substitute", "Planning substitute applied"),
                ("Create constrained supply for a service allocation", "Honor the approved priority allocation and create the supply request with the correct destination and need-by date.", "oracle_fusion.inventory_onhand_balances.list", "oracle_fusion.supply_requests.create", "Priority supply created"),
            ),
        ),
        *_s(
            "engineering_change",
            "manufacturing_engineer",
            "oracle_fusion.work_orders.get",
            ("change_order", "affected_work_order", "implementation_result"),
            (
                ("Implement a released relay substitution", "Verify the effective engineering change and serial breakpoint before replacing the active material component.", "oracle_fusion.work_order_materials.list", "oracle_fusion.work_order_materials.replace_with_substitute", "Change material implemented"),
                ("Move inspection to the revised routing step", "Match the released routing redline to the open operation and update its work center and timing.", "oracle_fusion.work_order_operations.list", "oracle_fusion.work_order_operations.update", "Routing change implemented"),
                ("Add new test-fixture capacity to an active order", "Check fixture qualification and change approval before adding the resource requirement.", "oracle_fusion.work_order_resources.list", "oracle_fusion.work_order_resources.create", "Fixture resource added"),
                ("Attach the released service bulletin to repair work", "Confirm document revision and asset applicability before creating the maintenance document reference.", "oracle_fusion.maintenance_documents.list", "oracle_fusion.maintenance_documents.create", "Bulletin attached"),
                ("Create a pilot work order for the revised design", "Use the approved prototype quantity, revision, and start window to create an isolated pilot order.", "oracle_fusion.inventory_onhand_balances.list", "oracle_fusion.work_orders.create", "Pilot order created"),
            ),
        ),
        *_s(
            "cost_accounting",
            "manufacturing_cost_accountant",
            "oracle_fusion.work_orders.get",
            ("cost_reference", "posting_action", "reconciled_amount"),
            (
                ("Post missing setup labor from signed timecards", "Match employee time, resource rate, and operation status before posting the omitted resource transaction.", "oracle_fusion.work_order_resources.list", "oracle_fusion.resource_transactions.create", "Labor cost posted"),
                ("Reverse a duplicated copper issue", "Prove the duplicate scan and remaining physical stock before posting the material return that corrects WIP cost.", "oracle_fusion.work_order_materials.list", "oracle_fusion.material_transactions.create", "Duplicate issue reversed"),
                ("Record scrap discovered during final count", "Reconcile the supervisor report and production quantities before posting the operation transaction to reject status.", "oracle_fusion.work_order_operations.list", "oracle_fusion.operation_transactions.create", "Scrap quantity posted"),
                ("Validate an outside-processing invoice", "Tie accepted supplier-operation quantity to the PO and invoice before invoking invoice validation.", "oracle_fusion.purchase_orders.get", "oracle_fusion.invoices.validate", "Outside-processing invoice validated"),
                ("Reschedule incomplete WIP out of the close window", "Use the close checklist and production evidence to move the unfinished order beyond cutoff without marking it complete.", "oracle_fusion.work_orders.list", "oracle_fusion.work_orders.update", "WIP rescheduled"),
            ),
        ),
        *_s(
            "project_manufacturing",
            "project_material_controller",
            "oracle_fusion.work_orders.list",
            ("project_task", "manufacturing_record", "ownership_result"),
            (
                ("Move project-owned relays to the build subinventory", "Verify project, task, lot, and approval before posting the project inventory transfer.", "oracle_fusion.inventory_onhand_balances.list", "oracle_fusion.inventory_transactions.create", "Project material transferred"),
                ("Create project supply for a customer milestone", "Reconcile milestone approval and net availability before creating supply with the correct project destination.", "oracle_fusion.supply_requests.list", "oracle_fusion.supply_requests.create", "Project supply requested"),
                ("Align an order to the corrected project task", "Confirm finance's correction and update only the open work order's project attribution and dates.", "oracle_fusion.work_orders.get", "oracle_fusion.work_orders.update", "Project task corrected"),
                ("Return unused project material from WIP", "Match operation cancellation and physical count before returning the project lot from the work order.", "oracle_fusion.work_order_materials.list", "oracle_fusion.material_transactions.create", "Project material returned"),
                ("Create a project-specific prototype order", "Use the signed statement of work and engineering release to create the exact project prototype quantity.", "oracle_fusion.sales_orders.get", "oracle_fusion.work_orders.create", "Project prototype created"),
            ),
        ),
        *_s(
            "field_service_supply",
            "service_supply_coordinator",
            "oracle_fusion.inventory_onhand_balances.list",
            ("service_request", "stock_action", "field_destination"),
            (
                ("Replenish a technician's critical relay stock", "Validate the van count, open service demand, and regional allocation before creating replenishment supply.", "oracle_fusion.supply_requests.list", "oracle_fusion.supply_requests.create", "Technician stock requested"),
                ("Quarantine a returned field controller", "Match the RMA, serial, and failure report before posting the returned unit into quarantine.", "oracle_fusion.receiving_receipt_requests.list", "oracle_fusion.inventory_transactions.create", "Field return quarantined"),
                ("Open depot repair for a customer asset", "Correlate the service email, entitlement evidence, and failure code before creating the maintenance work order.", "oracle_fusion.maintenance_work_orders.list", "oracle_fusion.maintenance_work_orders.create", "Depot repair opened"),
                ("Issue a reserved spare to an emergency repair", "Verify reservation, lot, and technician assignment before posting the material issue to the repair order.", "oracle_fusion.work_order_materials.list", "oracle_fusion.material_transactions.create", "Repair spare issued"),
                ("Receive an advance-replacement return", "Match shipment, RMA, and serial evidence before creating the receipt request for the returned asset.", "oracle_fusion.sales_orders.get", "oracle_fusion.receiving_receipt_requests.create", "Replacement return received"),
            ),
        ),
        *_s(
            "compliance_traceability",
            "compliance_manager",
            "oracle_fusion.quality_inspection_results.list",
            ("compliance_case", "contained_record", "evidence_reference"),
            (
                ("Contain relays named in a supplier recall", "Trace the supplier lot across receiving and on-hand evidence, then quarantine only the affected remaining quantity.", "oracle_fusion.inventory_onhand_balances.list", "oracle_fusion.inventory_transactions.create", "Recall stock contained"),
                ("Attach a certificate of conformance to repair work", "Verify certificate issuer, lot, and asset applicability before creating the maintenance document reference.", "oracle_fusion.maintenance_work_orders.get", "oracle_fusion.maintenance_documents.create", "Certificate attached"),
                ("Hold payment for a missing conflict-minerals report", "Confirm the contract requirement and compliance escalation before creating the invoice hold.", "oracle_fusion.invoices.get", "oracle_fusion.invoice_holds.create", "Compliance hold placed"),
                ("Create inspection for restricted-substance screening", "Select the approved plan and receipt lot before creating the compliance inspection result.", "oracle_fusion.inspection_plans.list", "oracle_fusion.quality_inspection_results.create", "Compliance inspection created"),
                ("Open corrective maintenance after a safety interlock bypass", "Correlate the incident record, asset, and lockout approval before creating urgent corrective work.", "oracle_fusion.maintenance_work_orders.list", "oracle_fusion.maintenance_work_orders.create", "Safety maintenance opened"),
            ),
        ),
        *_s(
            "period_close",
            "plant_controller",
            "oracle_fusion.purchase_orders.list",
            ("close_exception", "resolution_action", "accounting_period"),
            (
                ("Close a fully settled tooling PO before cutoff", "Reconcile PO, accepted receipt, final invoice, and buyer confirmation before finally closing the document.", "oracle_fusion.purchase_orders.get", "oracle_fusion.purchase_orders.close", "PO close exception resolved"),
                ("Validate the final matched invoice batch item", "Confirm the invoice belongs to the open period and matches accepted quantity before validation.", "oracle_fusion.invoices.get", "oracle_fusion.invoices.validate", "Invoice validated for close"),
                ("Hold a duplicate invoice found in reconciliation", "Use the duplicate report and supplier email to place the specific invoice hold before payment selection.", "oracle_fusion.invoices.get", "oracle_fusion.invoice_holds.create", "Duplicate invoice held"),
                ("Move unfinished production beyond period end", "Check the WIP count and operations log before revising the incomplete order dates beyond cutoff.", "oracle_fusion.work_order_operations.list", "oracle_fusion.work_orders.update", "Incomplete WIP deferred"),
                ("Post an omitted maintenance labor charge", "Match the approved technician time and maintenance order before posting the resource transaction for close.", "oracle_fusion.maintenance_work_orders.get", "oracle_fusion.resource_transactions.create", "Maintenance labor posted"),
            ),
        ),
        *_s(
            "supplier_operations",
            "outside_processing_coordinator",
            "oracle_fusion.purchase_orders.get",
            ("supplier_operation", "execution_action", "accepted_output"),
            (
                ("Acknowledge the anodizer's revised promise", "Match the supplier email to the correct outside-processing PO and record the new supplier order reference.", "oracle_fusion.purchase_order_lines.list", "oracle_fusion.purchase_orders.acknowledge", "Revised promise acknowledged"),
                ("Receive accepted plated housings from processing", "Reconcile packing slip, operation quantity, and inspection certificate before creating the receipt transaction.", "oracle_fusion.receiving_receipt_transactions.list", "oracle_fusion.receiving_receipt_transactions.create", "Processed units received"),
                ("Report outside operation completion after receipt", "Confirm accepted receipt quantity and serial scope before posting completion at the supplier operation.", "oracle_fusion.work_order_operations.list", "oracle_fusion.operation_transactions.create", "Supplier operation completed"),
                ("Record yield loss from rejected processed parts", "Use the supplier concession and quality result to post the rejected operation quantity without completing it as good output.", "oracle_fusion.quality_inspection_results.list", "oracle_fusion.operation_transactions.create", "Yield loss recorded"),
                ("Close an outside-processing PO after final acceptance", "Verify the final receipt, invoice validation, and no open schedules before closing for receiving and invoicing.", "oracle_fusion.purchase_order_lines.list", "oracle_fusion.purchase_orders.close", "Outside-processing PO closed"),
            ),
        ),
    ]
)

FAMILIES = tuple(FAMILY_LABELS)

assert len(SCENARIOS) == 100
assert set(scenario.family for scenario in SCENARIOS) == set(FAMILIES)
assert len({scenario.title for scenario in SCENARIOS}) == 100

