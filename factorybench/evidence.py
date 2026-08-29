"""Rich, task-scoped evidence packets for the enterprise sandbox."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

from .realism import build_decision_case
from .scenarios import Scenario


AS_OF_DATE = date(2026, 1, 12)


def _partition_measure(value: float | int, count: int) -> list[float | int]:
    """Split one deterministic measure into source rows without rounding drift."""

    scale = 100 if isinstance(value, float) and not float(value).is_integer() else 1
    scaled = int(round(float(value) * scale))
    base, remainder = divmod(abs(scaled), count)
    sign = -1 if scaled < 0 else 1
    parts = [sign * (base + (1 if index < remainder else 0)) for index in range(count)]
    if scale == 1:
        return parts
    return [round(part / scale, 2) for part in parts]


def _closeout_routing(writes: tuple[str, ...]) -> str:
    routes: list[str] = []
    for tool in writes:
        if tool == "google_sheets.spreadsheets.values.update":
            routes.append(
                "record the selected option, committed completion, and binding constraint in the existing Control outcome cell"
            )
        elif tool == "google_sheets.spreadsheets.values.append":
            routes.append(
                "append one dated decision row to the existing audit tab; do not overwrite prior entries"
            )
        elif tool == "gmail.drafts.create":
            routes.append(
                "prepare the reply in the existing email thread and leave it as a draft for review; do not send it"
            )
        elif tool == "gmail.messages.send":
            routes.append(
                "send the scoped completion reply in the existing email thread"
            )
        elif tool == "slack.chat_postMessage":
            routes.append(
                "post the decided option, date, constraint, alternatives, and Oracle reference in the existing operations thread"
            )
        elif tool == "slack.reactions_add":
            routes.append(
                "mark the existing operations thread complete with the approved check reaction"
            )
        elif tool == "google_drive.comments.create":
            routes.append(
                "add the resulting Oracle reference, option, date, and constraint as a comment on the existing case file"
            )
    if not routes:
        return "No secondary closeout record is required."
    return "Required closeout records: " + "; and ".join(routes) + "."


_MODE_ASSET_NAMES = {
    "plan": {
        "pdf": ("supplier-confirmation.pdf", "Supplier readiness confirmation"),
        "inputs": ("planning-inputs.xlsx", "Planning source inputs"),
        "reconciliation": ("requirement-and-coverage.csv", "Requirement and coverage source rows"),
        "calendar": ("factory-capacity-calendar.xlsx", "Finite production and recovery windows"),
        "spec": ("effective-planning-specification.md", "Effective planning specification"),
    },
    "quantity": {
        "pdf": ("source-transaction-document.pdf", "Source transaction document"),
        "inputs": ("eligibility-and-control-inputs.xlsx", "Eligibility and control inputs"),
        "reconciliation": ("quantity-reconciliation.csv", "Independent quantity source rows"),
        "calendar": ("downstream-impact-calendar.xlsx", "Downstream and escalation windows"),
        "spec": ("quantity-control-specification.md", "Quantity-control specification"),
    },
    "schedule": {
        "pdf": ("resource-confirmation.pdf", "Resource and recovery confirmation"),
        "inputs": ("qualification-and-load-inputs.xlsx", "Qualification and load inputs"),
        "reconciliation": ("capacity-reconciliation.csv", "Capacity source rows"),
        "calendar": ("finite-capacity-calendar.xlsx", "Finite-capacity and recovery calendar"),
        "spec": ("resource-qualification-specification.md", "Resource qualification specification"),
    },
    "financial": {
        "pdf": ("commercial-source-document.pdf", "Commercial source document"),
        "inputs": ("matching-and-tolerance-inputs.xlsx", "Matching and tolerance inputs"),
        "reconciliation": ("amount-reconciliation.csv", "Independent amount source rows"),
        "calendar": ("accounting-and-payment-calendar.xlsx", "Accounting and payment calendar"),
        "spec": ("financial-control-specification.md", "Financial control specification"),
    },
    "identity": {
        "pdf": ("signed-source-record.pdf", "Signed source record"),
        "inputs": ("identity-and-effectivity-crosswalk.xlsx", "Identity and effectivity crosswalk"),
        "reconciliation": ("candidate-record-reconciliation.csv", "Candidate-record source rows"),
        "calendar": ("effectivity-and-action-calendar.xlsx", "Effectivity and action calendar"),
        "spec": ("applicability-control.md", "Applicability and identity control"),
    },
    "forecast": {
        "pdf": ("meter-or-calendar-source-report.pdf", "Meter or calendar source report"),
        "inputs": ("trigger-and-eligibility-inputs.xlsx", "Trigger and eligibility inputs"),
        "reconciliation": ("event-reconciliation.csv", "Event and due-row source records"),
        "calendar": ("safe-maintenance-window-calendar.xlsx", "Safe maintenance windows"),
        "spec": ("program-generation-control.md", "Program generation control"),
    },
}


@lru_cache(maxsize=None)
def build_evidence(
    task_id: str,
    scenario: Scenario,
    ordinal: int,
    *,
    collaboration_writes: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Build 28 deep, heterogeneous, scenario-specific source artifacts."""

    decision = build_decision_case(scenario, ordinal)
    spec = decision["decision_spec"]
    names = _MODE_ASSET_NAMES[decision["decision_mode"]]
    values = decision["raw_decision_values"]
    option_dates = values["option_dates"]
    option_costs = values["option_costs"]
    options = decision["options"]
    case = decision["case_reference"]
    record = decision["record"]
    closeout_routing = _closeout_routing(collaboration_writes)
    facts = {fact["id"]: fact for fact in decision["facts"]}
    channel = ("C-PRODUCTION", "C-PROCUREMENT", "C-QUALITY", "C-FINANCE")[ordinal % 4]
    source_slug = re.sub(r"[^a-z0-9]+", "-", decision["source_document"].lower()).strip("-")[:48]
    observed_parts = _partition_measure(values["observed"], 4)
    excluded_parts = _partition_measure(values["excluded"], 2)
    nearby_case = f"CASE-{(ordinal % 100) + 1:03d}"
    stale_revision = f"R{8 + ordinal % 3}"
    external_scope = (
        decision["external_recovery_quantity"]
        if decision["external_recovery_quantity"]
        else decision["transaction_measure"]
    )

    policy = (
        f"# {scenario.title} — operating policy\n\n"
        f"Decision scope: {spec.subject}.\n\n"
        f"Control rule: {spec.constraint_label}. Establish the immutable source record and effective revision, "
        f"then reconcile {spec.scope_label}, {spec.eligible_label}, and {spec.excluded_label} from independent "
        "records. Do not treat a header total, filename, similar name, or unapproved alternative as evidence. "
        "The final mutation must be atomic and limited to the supported record and measure.\n\n"
        f"{closeout_routing}\n"
    )
    business_control = (
        f"# Business request and control — {case}\n\n"
        f"Subject: {spec.subject}\n"
        f"Business/control date: {decision['requested_by']}\n"
        f"Requester reference: {record}\n"
        f"Decision boundary: {spec.constraint_label}.\n"
        f"Escalation boundary: {options[2]['id']} requires a separate approval.\n\n"
        "This record states the boundary only. It does not identify the recommended option or compute the supported outcome.\n"
    )
    external_pdf = "\n".join(
        [
            f"{decision['supplier'].upper()} — CONTROLLED COMMERCIAL / SERVICE RECORD",
            f"Document: {source_slug}-{ordinal:04d}",
            f"Case reference: {case}",
            f"Issued: {AS_OF_DATE.isoformat()} 11:25 Pacific",
            f"Valid through: {(AS_OF_DATE + timedelta(days=7)).isoformat()}",
            "",
            "1. REFERENCED SCOPE",
            f"Source subject: {decision['source_document']}",
            f"Immutable record or item: {decision['item']}",
            f"Effective revision supplied by requester: {decision['revision']}",
            f"Maximum scope represented by this response: {external_scope} {decision['transaction_unit']}",
            "This confirmation is not valid for similarly named items, superseded revisions, other plants, or another case.",
            "",
            "2. CONFIRMED COMMERCIAL / CAPACITY INPUT",
            f"Alternative described by requester: {options[1]['id']}",
            f"Standard input or service readiness: {decision['standard_arrival']}",
            f"Expedited input or service readiness: {decision['expedite_arrival']}",
            f"Resulting operating outcome stated by requester, not by counterparty: {option_dates[1]}",
            f"Economic impact stated by counterparty: USD {option_costs[1]}",
            f"Independent condition: {spec.external_label}",
            "Capacity is reserved only after the buyer or planner supplies the matching immutable record and current approval.",
            "",
            "3. EXCLUSIONS AND ASSUMPTIONS",
            f"Not included: {spec.excluded_label}",
            f"Control not evaluated by counterparty: {spec.constraint_label}",
            f"Nearby but unrelated reference {nearby_case} is explicitly excluded.",
            "Freight, premium, certification, and lot terms apply only where stated above; silence is not approval.",
            "",
            "4. ACCEPTANCE",
            f"Prepared by: {decision['supplier']} operations desk",
            f"Confirmation number: CNF-{ordinal:06d}",
            "Status: CONFIRMED AS AN INPUT, NOT A FINAL OPERATING DECISION",
            "",
        ]
    )
    inputs_rows = [
        ["case", "source_record", "measure", "value", "unit", "revision", "eligibility", "plant", "status"],
        [case, record, spec.scope_label, values["scope"], spec.unit, decision["revision"], "SOURCE_REQUIREMENT", "SEA", "ACTIVE"],
        *[
            [case, f"OBS-{ordinal:04d}-{index}", spec.eligible_label, part, spec.unit, decision["revision"], "OBSERVED_NOT_NETTED", "SEA", status]
            for index, (part, status) in enumerate(
                zip(observed_parts, ("AVAILABLE", "AVAILABLE", "PENDING_CONTROL", "AVAILABLE")),
                start=1,
            )
        ],
        *[
            [case, f"EXCL-{ordinal:04d}-{index}", spec.excluded_label, part, spec.unit, decision["revision"], "EXCLUDE", "SEA", status]
            for index, (part, status) in enumerate(
                zip(excluded_parts, ("PROTECTED_OR_INELIGIBLE", "QUALITY_OR_EFFECTIVITY_HOLD")),
                start=1,
            )
        ],
        [nearby_case, f"OBS-{ordinal + 1:04d}-1", spec.eligible_label, max(1, int(float(values["scope"]) // 3)), spec.unit, decision["revision"], "DISTRACTOR_OTHER_CASE", "SEA", "AVAILABLE"],
        [case, f"OBS-{ordinal:04d}-ARCHIVE", spec.eligible_label, max(1, int(float(values["scope"]) // 4)), spec.unit, stale_revision, "DISTRACTOR_SUPERSEDED", "SEA", "ARCHIVED"],
        [case, f"OBS-{ordinal:04d}-PDX", spec.eligible_label, max(1, int(float(values["scope"]) // 5)), spec.unit, decision["revision"], "DISTRACTOR_OTHER_PLANT", "PDX", "AVAILABLE"],
        [case, f"OBS-{ordinal:04d}-DRAFT", spec.eligible_label, max(1, int(float(values["scope"]) // 6)), spec.unit, "DRAFT", "DISTRACTOR_DRAFT", "SEA", "DRAFT"],
    ]
    if decision["transaction_rate_usd"] is not None:
        inputs_rows.extend(
            [
                [case, f"SIGNED-MEASURE-{ordinal:04d}", "signed physical transaction measure", decision["transaction_measure"], decision["transaction_unit"], decision["revision"], "SOURCE", "SEA", "SIGNED"],
                [case, f"RATE-{ordinal:04d}", "approved unit rate", decision["transaction_rate_usd"], f"USD/{decision['transaction_unit']}", decision["revision"], "SOURCE", "SEA", "APPROVED"],
            ]
        )
    if scenario.title == "Award the enclosure tooling package":
        inputs_rows.extend(
            [
                [case, "BID-A", "sticker price", 11_200.00, "USD", decision["revision"], "COMMERCIAL_INPUT", "SEA", "VALID"],
                [case, "BID-A", "inbound freight", 202.11, "USD", decision["revision"], "COMMERCIAL_INPUT", "SEA", "VALID"],
                [case, "BID-A", "optional service not approved", 352.64, "USD", decision["revision"], "EXCLUDE", "SEA", "NOT_AUTHORIZED"],
                [case, "BID-A", "technical gate", "PASS", "RESULT", decision["revision"], "TECHNICAL_INPUT", "SEA", "ACCEPTABLE"],
                [case, "BID-A", "confirmed tooling lead time", 35, "DAYS", decision["revision"], "CAPACITY_INPUT", "SEA", "MEETS_LAUNCH"],
                [case, "BID-B", "sticker price", 10_982.11, "USD", decision["revision"], "COMMERCIAL_INPUT", "SEA", "VALID"],
                [case, "BID-B", "inbound freight", 900.00, "USD", decision["revision"], "COMMERCIAL_INPUT", "SEA", "VALID"],
                [case, "BID-B", "technical gate", "FAIL", "RESULT", decision["revision"], "TECHNICAL_INPUT", "SEA", "SALT_SPRAY_SPEC_NOT_MET"],
                [case, "BID-B", "confirmed tooling lead time", 28, "DAYS", decision["revision"], "CAPACITY_INPUT", "SEA", "MEETS_LAUNCH"],
                [case, "BID-C", "sticker price", 11_500.50, "USD", decision["revision"], "COMMERCIAL_INPUT", "SEA", "VALID"],
                [case, "BID-C", "inbound freight", 180.00, "USD", decision["revision"], "COMMERCIAL_INPUT", "SEA", "VALID"],
                [case, "BID-C", "technical gate", "PASS", "RESULT", decision["revision"], "TECHNICAL_INPUT", "SEA", "ACCEPTABLE"],
                [case, "BID-C", "confirmed tooling lead time", 49, "DAYS", decision["revision"], "CAPACITY_INPUT", "SEA", "MISSES_LAUNCH"],
            ]
        )
    decision_rows = [
        ["timestamp", "case", "actor", "control", "value", "source"],
        [f"{AS_OF_DATE.isoformat()}T09:10:00-08:00", case, "U-OPS-LEAD", "business_date_confirmed", decision["requested_by"], "slack"],
        [f"{AS_OF_DATE.isoformat()}T09:42:00-08:00", case, "U-CONTROLLER", "immutable_record_scope", record, "oracle_export"],
        [f"{AS_OF_DATE.isoformat()}T09:48:00-08:00", case, "U-CONTROLLER", "effective_revision", decision["revision"], "signed_specification"],
        [f"{AS_OF_DATE.isoformat()}T10:01:00-08:00", case, "U-APPROVER", "maximum_supported_measure", f"{decision['transaction_measure']} {decision['transaction_unit']}", "drive_approval"],
        [f"{AS_OF_DATE.isoformat()}T10:05:00-08:00", case, "U-APPROVER", f"{options[1]['id']}_limit_usd", option_costs[1], "drive_approval"],
        [f"{AS_OF_DATE.isoformat()}T10:07:00-08:00", case, "U-APPROVER", f"{options[2]['id']}_approval", "NOT_GRANTED", "drive_approval"],
        [f"{AS_OF_DATE.isoformat()}T10:09:00-08:00", nearby_case, "U-APPROVER", "unrelated_case_decision", "DO_NOT_APPLY", "drive_approval"],
    ]
    email = (
        f"From: operations-{ordinal}@northstar.example\n"
        f"To: {scenario.role.replace('_', '.')}@northstar.example\n"
        f"Cc: controls@northstar.example, {decision['supplier'].lower().replace(' ', '.')}@supplier.example\n"
        f"Date: {AS_OF_DATE.isoformat()}\n"
        f"Message-ID: <msg-{ordinal:03d}@northstar.example>\n"
        f"Subject: {case} — decision needed for {spec.subject}\n"
        "MIME-Version: 1.0\nContent-Type: text/plain; charset=UTF-8\n\n"
        f"{decision['request']}\n\n"
        "Please use the immutable references in the attached source record; the similarly named archive belongs to another case.\n\n"
        "--- Earlier message: external operations desk ---\n"
        f"Date: {AS_OF_DATE.isoformat()} 11:25 Pacific\n"
        f"{facts['conditional_external_recovery']['statement']}\n"
        f"Confirmation CNF-{ordinal:06d} is valid only for {decision['item']} / {decision['revision']}.\n\n"
        "--- Earlier message: operations lead ---\n"
        f"Date: {AS_OF_DATE.isoformat()} 09:10 Pacific\n"
        f"{facts['business_impact']['statement']}\n"
        f"The date in the prior {nearby_case} thread is not our control date.\n\n"
        "--- Earlier message: controller ---\n"
        f"Date: {(AS_OF_DATE - timedelta(days=1)).isoformat()} 16:40 Pacific\n"
        f"Reconcile the raw rows before acting. {spec.excluded_label.capitalize()} must remain outside the transaction, even if the header total appears to fit.\n"
    )
    slack = {
        "channel": channel,
        "thread_ts": f"1768{ordinal:06d}.000100",
        "messages": [
            {"user": "U-OPS-LEAD", "ts": f"1768{ordinal:06d}.000100", "text": facts["business_impact"]["statement"]},
            {"user": "U-PLANNER", "ts": f"1768{ordinal:06d}.000150", "text": f"I found {values['scope']} {spec.unit} on the header, but the workbook has separate observation and exclusion rows. Please do not net from this message."},
            {"user": "U-APPROVER", "ts": f"1768{ordinal:06d}.000200", "text": facts["approval_scope"]["statement"]},
            {"user": "U-SCHEDULER", "ts": f"1768{ordinal:06d}.000240", "text": f"Protected load remains non-displaceable. The calendar for {spec.capacity_label} is the source for internal windows; the supplier response covers only its stated alternative."},
            {"user": "U-QUALITY", "ts": f"1768{ordinal:06d}.000270", "text": f"Revision {stale_revision} and the {nearby_case} record are visible in search but are not applicable to {case}."},
            {"user": "U-CONTROLLER", "ts": f"1768{ordinal:06d}.000300", "text": f"{closeout_routing} Verify the persisted record after the Oracle call."},
        ],
    }
    approval = {
        "approvalId": f"approval-{ordinal:03d}",
        "fileId": f"drive-approval-{ordinal:03d}",
        "case": case,
        "status": "IN_PROGRESS",
        "requiredReviewers": ["U-APPROVER"],
        "reviewerResponses": [{"reviewer": "U-APPROVER", "response": "APPROVED"}],
        "approvedScope": facts["approval_scope"]["statement"],
        "businessNeedBy": decision["requested_by"],
    }
    erp_export = {
        "source": "Oracle Fusion Cloud 26a-shaped synthetic export",
        "case": case,
        "recordId": record,
        "recordType": scenario.primary_read.rsplit(".", 1)[0],
        "status": "Open",
        "organizationCode": "SEA",
        "itemOrResource": decision["item"],
        "revision": decision["revision"],
        "sourceMeasure": values["scope"],
        "unit": spec.unit,
        "lastUpdateDate": f"{AS_OF_DATE.isoformat()}T08:00:00-08:00",
    }
    reconciliation_rows = [
        ["record", "source", "source_line", "measure", "quantity_or_amount", "unit", "revision", "control_status", "reason"],
        [record, "primary_source", "REQ-1", spec.scope_label, values["scope"], spec.unit, decision["revision"], "AUTHORITATIVE", "effective source requirement"],
        *[
            [record, "independent_observation", f"OBS-{index}", spec.eligible_label, part, spec.unit, decision["revision"], "OBSERVED_NOT_NETTED", f"independent component {index} of the gross observation"]
            for index, part in enumerate(observed_parts, start=1)
        ],
        *[
            [record, "exclusion_ledger", f"EXCL-{index}", spec.excluded_label, part, spec.unit, decision["revision"], "INELIGIBLE", f"documented exclusion component {index}"]
            for index, part in enumerate(excluded_parts, start=1)
        ],
        [f"NS-{ordinal + 1:06d}", "independent_observation", "DIST-CASE", spec.eligible_label, max(1, int(float(values["scope"]) // 3)), spec.unit, decision["revision"], "OTHER_CASE", nearby_case],
        [record, "archive_export", "DIST-REV", spec.eligible_label, max(1, int(float(values["scope"]) // 4)), spec.unit, stale_revision, "SUPERSEDED", "not effective for current case"],
        [record, "other_plant_export", "DIST-PLANT", spec.eligible_label, max(1, int(float(values["scope"]) // 5)), spec.unit, decision["revision"], "OTHER_PLANT", "PDX ownership"],
        [record, "draft_control", "DIST-DRAFT", spec.scope_label, values["scope"], spec.unit, "DRAFT", "NOT_RELEASED", "draft must not replace effective revision"],
    ]
    candidate_capacity = max(1, int(round(float(values["observed"]))))
    protected_capacity = max(0, int(round(float(values["excluded"]))))
    calendar_rows = [
        ["resource_or_control", "window_ref", "window_start", "duration_days", "candidate_capacity", "unit", "qualification", "status", "protected_load", "economic_impact_usd", "authority"],
        [spec.capacity_label, options[0]["id"], decision["standard_start"], decision["duration_days"], candidate_capacity, spec.unit, "QUALIFIED", "OPEN", protected_capacity, option_costs[0], "NORMAL"],
        [f"{spec.capacity_label} / earlier-shift", "EARLY-PROTECTED", (date.fromisoformat(decision["standard_start"]) - timedelta(days=2)).isoformat(), 1, max(1, candidate_capacity // 2), spec.unit, "QUALIFIED", "PROTECTED_LOAD", max(1, protected_capacity), 0, "NOT_DISPLACEABLE"],
        [f"{spec.capacity_label} / alternate-A", "ALT-A", (date.fromisoformat(decision["standard_start"]) - timedelta(days=1)).isoformat(), 1, max(1, candidate_capacity // 3), spec.unit, "QUALIFICATION_EXPIRED", "OPEN", 0, 0, "NOT_ELIGIBLE"],
        [f"{spec.capacity_label} / alternate-B", "ALT-B", decision["standard_start"], 1, max(1, candidate_capacity // 2), spec.unit, "QUALIFIED", "MAINTENANCE_OUTAGE", 0, 0, "NOT_ELIGIBLE"],
        [f"{spec.capacity_label} / PDX", "OTHER-PLANT", decision["standard_start"], 2, candidate_capacity, spec.unit, "QUALIFIED", "OPEN", 0, 0, "OUTSIDE_CASE_SCOPE"],
        [spec.capacity_label, "ESCALATION-RAW", decision["overtime_start"], decision["overtime_duration_days"], max(1, int(round(float(values["scope"])))), spec.unit, "CONDITIONAL", "UNAPPROVED", 0, option_costs[2], "SEPARATE_APPROVAL_REQUIRED"],
        [f"{spec.capacity_label} / nearby-case", "DISTRACTOR", decision["standard_start"], 1, candidate_capacity, spec.unit, "QUALIFIED", "RESERVED", candidate_capacity, 0, f"OWNED_BY_{nearby_case}"],
    ]
    specification = (
        f"# {spec.source_document}\n\n"
        f"Case: {case}\n"
        f"Document control number: SPEC-{ordinal:04d}\n"
        f"Effective revision: {decision['revision']}\n"
        f"Superseded revision visible in archive: {stale_revision}\n"
        f"Subject: {spec.subject}\n"
        f"Primary measure: {spec.scope_label}\n"
        f"Source finished or header quantity: {decision['requested_quantity']}\n"
        f"Effective usage per finished or header unit: {decision['per_unit']} {spec.unit}\n"
        f"Unit: {spec.unit}\n"
        f"Eligibility definition: {spec.eligible_label}\n"
        f"Exclusion definition: {spec.excluded_label}\n"
        f"Control: {spec.constraint_label}\n"
        + (
            f"Effective trigger threshold: {values['trigger_threshold']} {spec.unit}\n"
            if values.get("trigger_threshold") is not None
            else ""
        )
        + (
            f"Task-specific financial control: {values['financial_control_label']}\n"
            f"Control threshold: USD {values['financial_control_threshold_usd']}\n"
            if values.get("financial_control_label") is not None
            else ""
        )
        + "\n## Applicability\n\n"
        f"Apply only to {record}, organization SEA, and {case}. A matching title, filename, supplier, or item description is insufficient without the immutable record and released revision.\n\n"
        "## Reconciliation rule\n\n"
        "Build the supported measure from the independent observed rows and subtract only rows carrying an effective exclusion reason. Do not use archive, draft, other-case, or other-plant rows in either side of the equation.\n\n"
        "## Timing and authority\n\n"
        f"Internal timing comes from {spec.capacity_label}; external timing is conditional on {spec.external_label}. Protected work is not displaceable. Separate approval is required for the escalation path, and a faster date does not waive the control.\n\n"
        "## Output control\n\n"
        "The system action must preserve the source identity, effective revision, supported measure, and scoped approval. This specification deliberately does not contain a netted result, selected option, or final outcome date.\n"
    )

    def csv_content(rows: list[list[Any]]) -> str:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerows(rows)
        return stream.getvalue()

    current_bom = "\n".join(
        [
            "NORTHSTAR CONTROLS — RELEASED ENGINEERING STRUCTURE",
            f"Case: {case}",
            f"Controlled record: {record}",
            f"Finished item or subject: {decision['item']}",
            f"Released revision: {decision['revision']}",
            "Organization: SEA",
            f"Effective date: {AS_OF_DATE.isoformat()}",
            "Status: CURRENT AND RELEASED",
            "",
            "COMPONENT AND CONTROL BASIS",
            f"Primary usage or conversion: {decision['per_unit']} {spec.unit} per finished or header unit",
            f"Source quantity stated on the controlled header: {decision['requested_quantity']}",
            f"Scope definition: {spec.scope_label}",
            f"Eligibility rule: {spec.eligible_label}",
            f"Exclusion rule: {spec.excluded_label}",
            "The released structure identifies inputs only. Inventory availability, lot eligibility, supplier readiness, finite capacity, and approval must be established from their own current records.",
            "",
            "EFFECTIVITY",
            f"Applies only to {case}, immutable record {record}, organization SEA, and revision {decision['revision']}.",
            f"A similarly named structure for {nearby_case}, a PDX record, a draft, or archive revision {stale_revision} is not interchangeable.",
            "Do not infer a supported quantity, selected recovery path, or completion date from this structure alone.",
            "",
            f"Document control: BOM-{ordinal:04d}-{decision['revision']}",
            "Approved by: U-ENGINEERING-CONTROL",
            "Electronic release status: EFFECTIVE",
        ]
    ) + "\n"
    superseded_bom = "\n".join(
        [
            "NORTHSTAR CONTROLS — SUPERSEDED ENGINEERING STRUCTURE",
            f"Case visible in archive: {case}",
            f"Controlled record: {record}",
            f"Finished item or subject: {decision['item']}",
            f"Archived revision: {stale_revision}",
            f"Replaced by revision: {decision['revision']}",
            f"Retired before: {AS_OF_DATE.isoformat()}",
            "Status: SUPERSEDED — REFERENCE ONLY",
            "",
            "This copy is retained to explain historical transactions and search conflicts. It cannot authorize current production, purchasing, inventory, quality, maintenance, service, or financial activity.",
            f"The archived usage basis differs from the released control and must not be combined with current rows for {case}.",
            f"Any matching title, filename, supplier name, or item description remains insufficient without revision {decision['revision']} and immutable record {record}.",
            "",
            "PROHIBITED USES",
            "Do not use this revision to calculate current requirements, select a supplier, release a lot, displace protected work, establish approval, or write Oracle state.",
            f"If a current source still points here, preserve the live record and escalate the revision conflict for {case}.",
            "",
            f"Archive control: BOM-{ordinal:04d}-{stale_revision}",
            "Archive owner: U-ENGINEERING-RECORDS",
        ]
    ) + "\n"
    vendor_catalog = "\n".join(
        [
            f"{decision['supplier'].upper()} — CONTROLLED PRICE AND SERVICE CATALOG",
            f"Case reference: {case}",
            f"Item or service: {decision['item']}",
            f"Applicable source revision: {decision['revision']}",
            f"Catalog effective: {AS_OF_DATE.isoformat()}",
            "Currency: USD",
            "",
            "STANDARD SERVICE TIER",
            f"Confirmed readiness input: {decision['standard_arrival']}",
            f"Maximum case-linked scope: {external_scope} {decision['transaction_unit']}",
            f"Published incremental impact: USD {option_costs[1]}",
            "Reservation status: conditional on buyer release and immutable source match",
            "",
            "PRIORITY SERVICE TIER",
            f"Confirmed readiness input: {decision['expedite_arrival']}",
            f"Maximum case-linked scope: {external_scope} {decision['transaction_unit']}",
            f"Published incremental impact: USD {option_costs[2]}",
            "Authorization status: separate approval required before reservation",
            "",
            "EXCLUSIONS",
            f"No coverage for {spec.excluded_label}, other organizations, nearby case {nearby_case}, draft demand, or superseded revision {stale_revision}.",
            "Readiness is an external input, not a manufacturing completion date or permission to mutate an ERP record.",
            f"Catalog control: CAT-{ordinal:05d}; valid through {(AS_OF_DATE + timedelta(days=7)).isoformat()}.",
        ]
    ) + "\n"

    production_schedule_rows = [
        ["case", "resource", "slot", "start", "duration_days", "available_capacity", "unit", "qualification", "load_status", "authority"],
        [case, spec.capacity_label, f"SEA-BASE-{ordinal:03d}", decision["standard_start"], decision["duration_days"], max(1, candidate_capacity), spec.unit, "QUALIFIED", "OPEN_AFTER_PROTECTED_LOAD", "CURRENT"],
        [case, spec.capacity_label, f"SEA-OT-{ordinal:03d}", decision["overtime_start"], decision["overtime_duration_days"], max(1, int(float(values["scope"]))), spec.unit, "QUALIFIED", "CONDITIONAL", "SEPARATE_APPROVAL"],
        [case, f"{spec.capacity_label}-A", f"SEA-A-{ordinal:03d}", (date.fromisoformat(decision["standard_start"]) - timedelta(days=1)).isoformat(), 1, max(1, candidate_capacity // 3), spec.unit, "EXPIRED", "OPEN", "NOT_ELIGIBLE"],
        [case, f"{spec.capacity_label}-B", f"SEA-B-{ordinal:03d}", decision["standard_start"], 1, max(1, candidate_capacity // 2), spec.unit, "QUALIFIED", "OUTAGE", "NOT_AVAILABLE"],
        [case, f"{spec.capacity_label}-C", f"SEA-C-{ordinal:03d}", (date.fromisoformat(decision["standard_start"]) + timedelta(days=1)).isoformat(), 2, max(1, candidate_capacity // 2), spec.unit, "QUALIFIED", "OPEN", "CURRENT"],
        [nearby_case, spec.capacity_label, f"SEA-OTHER-{ordinal:03d}", decision["standard_start"], 1, candidate_capacity, spec.unit, "QUALIFIED", "RESERVED", "OTHER_CASE"],
        [case, f"{spec.capacity_label}-PDX", f"PDX-{ordinal:03d}", decision["standard_start"], 2, candidate_capacity, spec.unit, "QUALIFIED", "OPEN", "OUTSIDE_ORGANIZATION"],
        [case, spec.capacity_label, f"SEA-ARCH-{ordinal:03d}", (AS_OF_DATE - timedelta(days=4)).isoformat(), 1, candidate_capacity, spec.unit, "QUALIFIED", "ARCHIVED", "SUPERSEDED"],
    ]
    shift_capacity_rows = [
        ["case", "shift", "date", "skill_or_resource", "qualified", "active", "regular_capacity", "overtime_capacity", "protected_capacity", "approval_status"],
        [case, "A", decision["standard_start"], spec.capacity_label, "YES", "YES", max(1, candidate_capacity // 2), 0, max(1, protected_capacity), "NORMAL"],
        [case, "B", decision["standard_start"], spec.capacity_label, "YES", "YES", max(1, candidate_capacity // 2), max(1, candidate_capacity // 4), 0, "OVERTIME_NOT_GRANTED"],
        [case, "C", decision["standard_start"], spec.capacity_label, "NO", "YES", max(1, candidate_capacity // 3), 0, 0, "NOT_QUALIFIED"],
        [case, "WEEKEND", decision["overtime_start"], spec.capacity_label, "YES", "YES", 0, max(1, candidate_capacity), 0, "SEPARATE_APPROVAL"],
        [case, "A", (date.fromisoformat(decision["standard_start"]) + timedelta(days=1)).isoformat(), spec.capacity_label, "YES", "YES", max(1, candidate_capacity), 0, 0, "NORMAL"],
        [nearby_case, "B", decision["standard_start"], spec.capacity_label, "YES", "YES", candidate_capacity, 0, 0, "OTHER_CASE_RESERVED"],
        [case, "ARCHIVE", (AS_OF_DATE - timedelta(days=7)).isoformat(), spec.capacity_label, "YES", "NO", candidate_capacity, 0, 0, "SUPERSEDED"],
    ]
    supplier_capacity_rows = [
        ["case", "supplier", "item_or_service", "revision", "tier", "readiness", "capacity", "unit", "status", "authority"],
        [case, decision["supplier"], decision["item"], decision["revision"], "STANDARD", decision["standard_arrival"], external_scope, decision["transaction_unit"], "CONFIRMED_INPUT", "BUYER_RELEASE_REQUIRED"],
        [case, decision["supplier"], decision["item"], decision["revision"], "PRIORITY", decision["expedite_arrival"], external_scope, decision["transaction_unit"], "CAPACITY_HELD", "SEPARATE_APPROVAL"],
        [case, f"{decision['supplier']} ARCHIVE", decision["item"], stale_revision, "STANDARD", decision["standard_arrival"], external_scope, decision["transaction_unit"], "EXPIRED", "SUPERSEDED"],
        [case, f"Alternate-{ordinal:03d}-A", decision["item"], decision["revision"], "STANDARD", (date.fromisoformat(decision["standard_arrival"]) + timedelta(days=2)).isoformat(), max(1, int(float(external_scope) // 2)), decision["transaction_unit"], "QUALIFICATION_PENDING", "NOT_ELIGIBLE"],
        [case, f"Alternate-{ordinal:03d}-B", decision["item"], decision["revision"], "STANDARD", decision["expedite_arrival"], external_scope, decision["transaction_unit"], "QUALIFIED", "NO_CURRENT_CAPACITY"],
        [nearby_case, decision["supplier"], decision["item"], decision["revision"], "PRIORITY", decision["expedite_arrival"], external_scope, decision["transaction_unit"], "CONFIRMED", "OTHER_CASE"],
        [case, decision["supplier"], f"{decision['item']}-SIMILAR", decision["revision"], "STANDARD", decision["standard_arrival"], external_scope, decision["transaction_unit"], "CONFIRMED", "WRONG_ITEM"],
    ]
    authority_matrix_rows = [
        ["case", "role", "actor", "scope", "limit_usd", "effective_from", "effective_to", "status", "constraint"],
        [case, "operations_planner", "U-AGENT", "investigate_and_prepare", 0, AS_OF_DATE.isoformat(), "", "ACTIVE", "NO_EXCEPTION_APPROVAL"],
        [case, "operations_lead", "U-OPS-LEAD", "normal_operating_scope", 25_000, AS_OF_DATE.isoformat(), "", "ACTIVE", spec.constraint_label],
        [case, "authorized_approver", "U-APPROVER", "case_scoped_decision", 250_000, AS_OF_DATE.isoformat(), "", "ACTIVE", f"AP-{ordinal:04d}"],
        [case, "controller", "U-CONTROLLER", "financial_and_revision_control", 250_000, AS_OF_DATE.isoformat(), "", "ACTIVE", decision["revision"]],
        [case, "former_approver", "U-FORMER", "historical_only", 500_000, (AS_OF_DATE - timedelta(days=365)).isoformat(), (AS_OF_DATE - timedelta(days=1)).isoformat(), "INACTIVE", "EXPIRED_DELEGATION"],
        [nearby_case, "authorized_approver", "U-APPROVER", "other_case", 250_000, AS_OF_DATE.isoformat(), "", "ACTIVE", "NOT_TRANSFERABLE"],
        [case, "executive_exception", "U-EXEC", "broader_or_faster_exception", 1_000_000, AS_OF_DATE.isoformat(), "", "NOT_REQUESTED", "SEPARATE_APPROVAL_REQUIRED"],
    ]
    material_on_hand_rows = [
        ["case", "item", "lot", "organization", "subinventory", "on_hand", "reserved", "quality_hold", "available_status", "revision"],
        [case, decision["item"], f"LOT-{ordinal:03d}-A", "SEA", "STORES", observed_parts[0], 0, 0, "AVAILABLE", decision["revision"]],
        [case, decision["item"], f"LOT-{ordinal:03d}-B", "SEA", "STORES", observed_parts[1], max(0, int(float(excluded_parts[0]))), 0, "PARTLY_RESERVED", decision["revision"]],
        [case, decision["item"], f"LOT-{ordinal:03d}-C", "SEA", "MRB", observed_parts[2], 0, excluded_parts[1], "QUALITY_HOLD", decision["revision"]],
        [case, decision["item"], f"LOT-{ordinal:03d}-D", "SEA", "STORES", observed_parts[3], 0, 0, "AVAILABLE", decision["revision"]],
        [nearby_case, decision["item"], f"LOT-{ordinal:03d}-E", "SEA", "STORES", max(1, int(float(values["scope"]) // 3)), 0, 0, "OTHER_CASE", decision["revision"]],
        [case, decision["item"], f"LOT-{ordinal:03d}-F", "PDX", "STORES", max(1, int(float(values["scope"]) // 4)), 0, 0, "OTHER_ORGANIZATION", decision["revision"]],
        [case, decision["item"], f"LOT-{ordinal:03d}-G", "SEA", "ARCHIVE", max(1, int(float(values["scope"]) // 5)), 0, 0, "SUPERSEDED", stale_revision],
    ]
    component_requirement_rows = [
        ["case", "record", "parent_or_subject", "component_or_control", "usage", "header_quantity", "gross_requirement", "unit", "revision", "effectivity"],
        [case, record, decision["item"], f"COMP-{ordinal:03d}-A", decision["per_unit"], decision["requested_quantity"], values["scope"], spec.unit, decision["revision"], "CURRENT"],
        [case, record, decision["item"], f"COMP-{ordinal:03d}-B", 1, decision["requested_quantity"], decision["requested_quantity"], "EA", decision["revision"], "REFERENCE_INPUT"],
        [case, record, decision["item"], f"COMP-{ordinal:03d}-C", 1, decision["requested_quantity"], max(1, int(float(values["scope"]) // 2)), spec.unit, decision["revision"], "CONDITIONAL"],
        [case, record, decision["item"], f"COMP-{ordinal:03d}-ARCH", decision["per_unit"], decision["requested_quantity"], values["scope"], spec.unit, stale_revision, "SUPERSEDED"],
        [nearby_case, f"NS-{ordinal + 1:06d}", decision["item"], f"COMP-{ordinal + 1:03d}-A", decision["per_unit"], decision["requested_quantity"], values["scope"], spec.unit, decision["revision"], "OTHER_CASE"],
        [case, record, decision["item"], f"COMP-{ordinal:03d}-PDX", decision["per_unit"], decision["requested_quantity"], values["scope"], spec.unit, decision["revision"], "OTHER_ORGANIZATION"],
    ]
    quality_hold_rows = [
        ["case", "item_or_subject", "lot_or_record", "revision", "inspection_status", "hold_status", "disposition", "effective", "scope_note"],
        [case, decision["item"], f"LOT-{ordinal:03d}-A", decision["revision"], "ACCEPTED", "NONE", "USE", AS_OF_DATE.isoformat(), "current case"],
        [case, decision["item"], f"LOT-{ordinal:03d}-B", decision["revision"], "ACCEPTED", "RESERVATION", "PARTIAL", AS_OF_DATE.isoformat(), "preserve reserved quantity"],
        [case, decision["item"], f"LOT-{ordinal:03d}-C", decision["revision"], "PENDING", "QUALITY", "HOLD", AS_OF_DATE.isoformat(), spec.excluded_label],
        [case, decision["item"], f"LOT-{ordinal:03d}-D", decision["revision"], "ACCEPTED", "NONE", "USE", AS_OF_DATE.isoformat(), "current case"],
        [case, decision["item"], f"LOT-{ordinal:03d}-ARCH", stale_revision, "ACCEPTED", "NONE", "ARCHIVE", (AS_OF_DATE - timedelta(days=30)).isoformat(), "superseded result"],
        [nearby_case, decision["item"], f"LOT-{ordinal:03d}-OTHER", decision["revision"], "ACCEPTED", "NONE", "OTHER_CASE", AS_OF_DATE.isoformat(), "not transferable"],
    ]
    maintenance_outages = {
        "case": case,
        "record": record,
        "asOf": AS_OF_DATE.isoformat(),
        "resources": [
            {"resource": spec.capacity_label, "window": decision["standard_start"], "status": "OPEN_AFTER_PROTECTED_LOAD", "qualification": "CURRENT", "case": case},
            {"resource": f"{spec.capacity_label}-A", "window": decision["standard_start"], "status": "OPEN", "qualification": "EXPIRED", "case": case},
            {"resource": f"{spec.capacity_label}-B", "window": decision["standard_start"], "status": "MAINTENANCE_OUTAGE", "qualification": "CURRENT", "case": case},
            {"resource": f"{spec.capacity_label}-PDX", "window": decision["standard_start"], "status": "OPEN", "qualification": "CURRENT", "case": case, "organization": "PDX"},
            {"resource": spec.capacity_label, "window": decision["overtime_start"], "status": "CONDITIONAL", "qualification": "CURRENT", "case": case, "authority": "SEPARATE_APPROVAL"},
            {"resource": spec.capacity_label, "window": decision["standard_start"], "status": "RESERVED", "qualification": "CURRENT", "case": nearby_case},
        ],
        "instruction": "Correlate active qualification, organization, protected load, outage status, and case ownership; row order does not imply preference.",
    }
    planning_slack = {
        "channel": "C-FACTORY-PLANNING",
        "thread_ts": f"1769{ordinal:06d}.000100",
        "case": case,
        "messages": [
            {"user": "U-PLANNING", "ts": f"1769{ordinal:06d}.000100", "text": f"Please reconcile {record} for {case}; the header and detail sources do not yet support a commitment."},
            {"user": "U-MATERIALS", "ts": f"1769{ordinal:06d}.000140", "text": f"On-hand includes a reservation and a quality-held row for {decision['item']}. Use the lot register, not this summary."},
            {"user": "U-SCHEDULER", "ts": f"1769{ordinal:06d}.000180", "text": f"The first open row for {spec.capacity_label} may still be unusable because qualification and protected load are separate controls."},
            {"user": "U-PROCUREMENT", "ts": f"1769{ordinal:06d}.000220", "text": f"{decision['supplier']} confirmed readiness inputs for revision {decision['revision']}; priority service still needs separate approval."},
            {"user": "U-QUALITY", "ts": f"1769{ordinal:06d}.000260", "text": f"Archive revision {stale_revision} and {nearby_case} appear in search results but do not apply to this case."},
            {"user": "U-CONTROLLER", "ts": f"1769{ordinal:06d}.000300", "text": f"Do not select an option until current authority, source identity, exclusions, and Oracle state agree for {case}."},
        ],
    }
    procurement_email = (
        f"From: sourcing-{ordinal:03d}@northstar.example\n"
        f"To: {scenario.role.replace('_', '.')}@northstar.example\n"
        f"Cc: planning@northstar.example, quality@northstar.example, controls@northstar.example\n"
        f"Date: {AS_OF_DATE.isoformat()} 13:15:00 -0800\n"
        f"Message-ID: <procurement-{ordinal:03d}@northstar.example>\n"
        f"References: <msg-{ordinal:03d}@northstar.example>\n"
        f"Subject: Re: {case} source capacity and commercial controls\n"
        "MIME-Version: 1.0\nContent-Type: text/plain; charset=UTF-8\n\n"
        f"We matched the supplier response to {decision['item']}, revision {decision['revision']}, and immutable record {record}. The standard and priority readiness dates are inputs only; neither is an ERP completion date.\n\n"
        f"The current catalog covers no more than {external_scope} {decision['transaction_unit']}. It excludes {spec.excluded_label}, the archived revision {stale_revision}, PDX demand, and nearby case {nearby_case}.\n\n"
        f"Before releasing anything, compare the supplier workbook with current Oracle demand, the released structure, on-hand and reservations, quality holds, finite schedule, and AP-{ordinal:04d}. Priority service has capacity held but no exception approval.\n\n"
        "If those records conflict, retain the current state and send the conflict back to sourcing and controls. Do not convert a supplier promise, filename, or quoted price into authority.\n\n"
        f"Regards,\nSourcing control desk\nNorthstar case {case}\n"
    )
    source_lineage = {
        "case": case,
        "record": record,
        "effectiveRevision": decision["revision"],
        "asOf": AS_OF_DATE.isoformat(),
        "sources": [
            {"sourceId": f"ORACLE-{ordinal:04d}", "system": "oracle_fusion", "status": "CURRENT", "immutableKey": record},
            {"sourceId": f"BOM-{ordinal:04d}-{decision['revision']}", "system": "google_drive", "status": "CURRENT", "immutableKey": decision["revision"]},
            {"sourceId": f"BOM-{ordinal:04d}-{stale_revision}", "system": "google_drive", "status": "SUPERSEDED", "immutableKey": stale_revision},
            {"sourceId": f"CNF-{ordinal:06d}", "system": "gmail", "status": "CONFIRMED_INPUT", "immutableKey": decision["item"]},
            {"sourceId": f"AP-{ordinal:04d}", "system": "google_drive", "status": "CURRENT", "immutableKey": case},
            {"sourceId": f"SHEET-{ordinal:04d}", "system": "google_sheets", "status": "CURRENT", "immutableKey": case},
            {"sourceId": f"SLACK-{ordinal:04d}", "system": "slack", "status": "CORROBORATING", "immutableKey": case},
            {"sourceId": f"OTHER-{ordinal + 1:04d}", "system": "google_drive", "status": "OTHER_CASE", "immutableKey": nearby_case},
        ],
        "control": "Use immutable IDs and effective status. This index describes lineage only and contains no selected option or final calculation.",
    }
    control_audit_log = "\n".join(
        [
            f"2026-01-12T{8 + index // 2:02d}:{(index % 2) * 30:02d}:00-08:00 case={case} record={record} event={event} source_revision={revision} status={status} actor={actor}"
            for index, (event, revision, status, actor) in enumerate(
                [
                    ("oracle_snapshot_indexed", decision["revision"], "CURRENT", "U-SYSTEM"),
                    ("business_date_confirmed", decision["revision"], "CURRENT", "U-OPS-LEAD"),
                    ("released_structure_indexed", decision["revision"], "CURRENT", "U-ENGINEERING-CONTROL"),
                    ("archive_structure_indexed", stale_revision, "SUPERSEDED", "U-ENGINEERING-RECORDS"),
                    ("inventory_rows_indexed", decision["revision"], "UNNETTED", "U-MATERIALS"),
                    ("quality_holds_indexed", decision["revision"], "CURRENT", "U-QUALITY"),
                    ("supplier_capacity_indexed", decision["revision"], "CONDITIONAL", "U-PROCUREMENT"),
                    ("schedule_rows_indexed", decision["revision"], "CURRENT", "U-SCHEDULER"),
                    ("authority_checked", decision["revision"], "CURRENT", "U-CONTROLLER"),
                    ("nearby_case_excluded", decision["revision"], "OTHER_CASE", "U-CONTROLLER"),
                    ("exception_path_unapproved", decision["revision"], "SEPARATE_APPROVAL", "U-APPROVER"),
                    ("decision_pending", decision["revision"], "NO_SELECTION_RECORDED", "U-AGENT"),
                ]
            )
        ]
    ) + "\n"
    revision_index = "\n".join(
        [
            f"case: {case}",
            f"record: {record}",
            f"as_of: {AS_OF_DATE.isoformat()}",
            "evidence:",
            f"  - source: oracle_snapshot\n    revision: {decision['revision']}\n    status: current\n    immutable_key: {record}",
            f"  - source: engineering_structure\n    revision: {decision['revision']}\n    status: current\n    immutable_key: BOM-{ordinal:04d}-{decision['revision']}",
            f"  - source: engineering_archive\n    revision: {stale_revision}\n    status: superseded\n    immutable_key: BOM-{ordinal:04d}-{stale_revision}",
            f"  - source: supplier_confirmation\n    revision: {decision['revision']}\n    status: conditional_input\n    immutable_key: CNF-{ordinal:06d}",
            f"  - source: approval\n    revision: {decision['revision']}\n    status: current_scoped\n    immutable_key: AP-{ordinal:04d}",
            f"  - source: nearby_case\n    revision: {decision['revision']}\n    status: excluded_other_case\n    immutable_key: {nearby_case}",
            "control: >-",
            "  Resolve immutable identity and effective revision before using a row. The index does not authorize a mutation, calculate the supported measure, or select an operating option.",
        ]
    ) + "\n"

    def asset(
        suffix: str,
        path: str,
        title: str,
        kind: str,
        source: str,
        media_type: str,
        content: str,
        preview: str,
        rows: list[list[Any]] | None = None,
    ) -> dict[str, Any]:
        value: dict[str, Any] = {
            "asset_id": f"{task_id}-{suffix}",
            "path": path,
            "title": title,
            "kind": kind,
            "source": source,
            "media_type": media_type,
            "content": content,
            "preview": preview[:360],
        }
        if rows is not None:
            value["rows"] = rows
        return value

    return [
        asset("policy", "operating-policy.md", "Operating policy", "policy", "google_drive", "text/markdown", policy, policy.split("\n\n", 2)[-1]),
        asset("control", "business-request-and-control.md", "Business request and control", "contract", "google_drive", "text/markdown", business_control, business_control.split("\n\n", 2)[-1]),
        asset("external", names["pdf"][0], names["pdf"][1], "external_pdf", "gmail_attachment", "application/pdf", external_pdf, external_pdf.replace("\n", " · ")),
        asset("inputs", names["inputs"][0], names["inputs"][1], "source_workbook", "google_drive", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", json.dumps(inputs_rows), f"Raw {spec.scope_label}, observation, and exclusion rows; no netted result.", inputs_rows),
        asset("decision", "approval-decision-log.csv", "Approval decision log", "spreadsheet_export", "google_sheets", "text/csv", "\n".join(",".join(map(str, row)) for row in decision_rows) + "\n", "Timestamped business-date and approval controls.", decision_rows),
        asset("email", "source-email-thread.eml", "Source email thread", "email", "gmail", "message/rfc822", email, email.split("\n\n", 1)[-1]),
        asset("slack", "operations-slack-thread.json", "Operations Slack thread", "chat_thread", "slack", "application/json", json.dumps(slack, indent=2, sort_keys=True) + "\n", " · ".join(message["text"] for message in slack["messages"])),
        asset("approval", "drive-approval-record.json", "Drive approval record", "approval", "google_drive", "application/json", json.dumps(approval, indent=2, sort_keys=True) + "\n", f"Approval {approval['approvalId']} covers only the stated scope."),
        asset("erp", "oracle-starting-record.json", "Oracle starting-record export", "erp_export", "oracle_fusion", "application/json", json.dumps(erp_export, indent=2, sort_keys=True) + "\n", f"Open Oracle record {record} at revision {decision['revision']}."),
        asset("reconciliation", names["reconciliation"][0], names["reconciliation"][1], "source_reconciliation", "laboratory_drive", "text/csv", "\n".join(",".join(map(str, row)) for row in reconciliation_rows) + "\n", "Independent source, observed, and exclusion rows; the supported result is not precomputed.", reconciliation_rows),
        asset("calendar", names["calendar"][0], names["calendar"][1], "control_calendar", "google_drive", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", json.dumps(calendar_rows), "Base window plus raw escalation start, duration, cost, and authority; the alternative comes from the external source.", calendar_rows),
        asset("spec", names["spec"][0], names["spec"][1], "specification", "google_drive", "text/markdown", specification, specification.split("\n\n", 1)[-1]),
        asset("bom-current", "engineering/current-released-structure.pdf", "Current released engineering structure", "engineering_bom_current", "google_drive", "application/pdf", current_bom, current_bom.replace("\n", " · ")),
        asset("bom-archive", "engineering/superseded-structure.pdf", "Superseded engineering structure", "engineering_bom_superseded", "google_drive", "application/pdf", superseded_bom, superseded_bom.replace("\n", " · ")),
        asset("catalog", "procurement/vendor-price-and-service-catalog.pdf", "Vendor price and service catalog", "vendor_price_catalog", "gmail_attachment", "application/pdf", vendor_catalog, vendor_catalog.replace("\n", " · ")),
        asset("schedule", "planning/current-production-schedule.xlsx", "Current finite production schedule", "production_schedule", "google_sheets", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", json.dumps(production_schedule_rows), "Current and excluded schedule windows with qualification, protected load, and authority.", production_schedule_rows),
        asset("shifts", "planning/shift-and-overtime-capacity.xlsx", "Shift and overtime capacity", "shift_capacity", "google_sheets", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", json.dumps(shift_capacity_rows), "Regular, protected, unqualified, and separately approved shift capacity.", shift_capacity_rows),
        asset("supplier-capacity", "procurement/supplier-lead-time-and-capacity.xlsx", "Supplier lead-time and capacity", "supplier_capacity", "google_drive", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", json.dumps(supplier_capacity_rows), "Supplier readiness and capacity inputs with current, stale, and ineligible alternatives.", supplier_capacity_rows),
        asset("authority-matrix", "approvals/delegation-of-authority.xlsx", "Delegation of authority", "authority_matrix", "google_drive", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", json.dumps(authority_matrix_rows), "Effective and expired authority rows; exception approval remains separate.", authority_matrix_rows),
        asset("on-hand", "materials/raw-material-on-hand.csv", "Raw-material on-hand and reservations", "material_on_hand", "oracle_fusion_export", "text/csv", csv_content(material_on_hand_rows), "Lot-level on-hand, reservations, holds, organizations, and revisions.", material_on_hand_rows),
        asset("requirements", "materials/component-requirements.csv", "Component and control requirements", "component_requirements", "oracle_fusion_export", "text/csv", csv_content(component_requirement_rows), "Current, superseded, other-case, and other-organization requirement rows.", component_requirement_rows),
        asset("quality", "quality/lot-and-hold-register.csv", "Lot and quality-hold register", "quality_holds", "quality_system_export", "text/csv", csv_content(quality_hold_rows), "Inspection and hold status by immutable lot, case, and revision.", quality_hold_rows),
        asset("outages", "maintenance/resource-outages.json", "Resource outage and qualification register", "maintenance_outages", "oracle_fusion_export", "application/json", json.dumps(maintenance_outages, indent=2, sort_keys=True) + "\n", "Resource status, qualification, organization, case ownership, and conditional windows."),
        asset("planning-chat", "collaboration/planning-slack-thread.json", "Production planning Slack thread", "planning_chat", "slack", "application/json", json.dumps(planning_slack, indent=2, sort_keys=True) + "\n", "Cross-functional planning discussion that points to controlling sources without deciding the case."),
        asset("procurement-email", "collaboration/procurement-email-thread.eml", "Procurement source-control email", "procurement_email", "gmail", "message/rfc822", procurement_email, procurement_email.split("\n\n", 1)[-1]),
        asset("lineage", "drive/source-lineage.json", "Cross-system source lineage", "source_lineage", "google_drive", "application/json", json.dumps(source_lineage, indent=2, sort_keys=True) + "\n", "Immutable source IDs and effective status without a selected option."),
        asset("audit-log", "audit/control-events.log", "Control event audit log", "control_audit_log", "audit_export", "text/plain", control_audit_log, "Task-scoped event trail for current, stale, and excluded evidence."),
        asset("revision-index", "audit/evidence-revision-index.yaml", "Evidence revision index", "revision_index", "google_drive", "application/yaml", revision_index, "Effective and superseded source revisions keyed to immutable records."),
    ]
