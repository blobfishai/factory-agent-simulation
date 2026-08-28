"""Rich, task-scoped evidence packets for the enterprise sandbox."""

from __future__ import annotations

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
    """Build twelve deep, heterogeneous, scenario-specific source artifacts."""

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
    ]
