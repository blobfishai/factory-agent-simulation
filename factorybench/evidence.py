"""Rich, task-scoped evidence packets for the enterprise sandbox."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from .scenarios import FAMILY_DESCRIPTIONS, Scenario


AS_OF_DATE = date(2026, 1, 12)


def build_evidence(task_id: str, scenario: Scenario, ordinal: int) -> list[dict[str, Any]]:
    """Return a heterogeneous evidence packet with inspectable extracted text."""

    case = f"CASE-{ordinal:03d}"
    record = f"NS-{ordinal:06d}"
    effective = AS_OF_DATE + timedelta(days=(ordinal % 19) + 1)
    supplier = ("Cascade Industrial", "Rainier Components", "Olympic Metrology")[ordinal % 3]
    quantity = 8 + ordinal % 37
    unit_price = round(42.5 + ordinal * 1.17, 2)
    total = round(quantity * unit_price, 2)
    channel = ("C-PRODUCTION", "C-PROCUREMENT", "C-QUALITY", "C-FINANCE")[ordinal % 4]

    policy = (
        f"# {scenario.title} — operating control\n\n"
        f"Scope: {FAMILY_DESCRIPTIONS[scenario.family]}\n\n"
        "The operator must reconcile the authoritative ERP record with the named collaboration "
        "and document evidence. A write is permitted only after the record identity, effective "
        "revision, quantity or amount, and recorded approval agree. Preserve task, lot, serial, "
        "supplier, project, and work-order references. Communicate the resulting identifier and "
        "effective date; never infer approval from silence.\n"
    )
    contract = (
        f"# Commercial or service control for {case}\n\n"
        f"The approved operational objective is: {scenario.outcome}\n\n"
        f"Effective date: {effective.isoformat()}\n"
        f"Reference record: {record}\n"
        "Any deviation affecting price, completion, inspected quantity, compliance, or customer "
        "commit requires explicit approval preserved in the case packet.\n"
    )
    quote_text = (
        f"VENDOR QUOTATION {case}\nSupplier: {supplier}\nItem: NS-COMP-{ordinal:03d}\n"
        f"Quantity: {quantity} EA\nUnit price: USD {unit_price:.2f}\nExtended: USD {total:.2f}\n"
        f"Lead time: {3 + ordinal % 11} calendar days\nValid through: {(effective + timedelta(days=30)).isoformat()}\n"
        "Freight: included\nQuality certificate: required with shipment\n"
    )
    email = (
        f"From: operations-{ordinal}@northstar.example\n"
        f"To: {scenario.role.replace('_', '.')}@northstar.example\n"
        f"Date: {AS_OF_DATE.isoformat()}\n"
        f"Message-ID: <msg-{ordinal:03d}@northstar.example>\n"
        f"Subject: {case} — evidence and requested action\n"
        "MIME-Version: 1.0\nContent-Type: text/plain; charset=UTF-8\n\n"
        f"Please complete: {scenario.outcome}\n"
        f"Use record {record}; approved effective date is {effective.isoformat()}. "
        "The supporting quotation and spreadsheet are attached. Reply with the Oracle reference.\n"
    )
    slack = {
        "channel": channel,
        "thread_ts": f"1768{ordinal:06d}.000100",
        "messages": [
            {
                "user": "U-OPS-LEAD",
                "ts": f"1768{ordinal:06d}.000100",
                "text": f"{case}: physical/operational evidence checked for {record}.",
            },
            {
                "user": "U-APPROVER",
                "ts": f"1768{ordinal:06d}.000200",
                "text": f"Approved exactly as documented; effective {effective.isoformat()}. No broader change authorized.",
            },
            {
                "user": "U-CONTROLLER",
                "ts": f"1768{ordinal:06d}.000300",
                "text": "Post the resulting Oracle reference back to this thread and the control workbook.",
            },
        ],
    }
    approval = {
        "approvalId": f"approval-{ordinal:03d}",
        "fileId": f"drive-approval-{ordinal:03d}",
        "case": case,
        "status": "IN_PROGRESS",
        "requiredReviewers": ["U-APPROVER"],
        "reviewerResponses": [{"reviewer": "U-APPROVER", "response": "APPROVED"}],
        "approvedScope": scenario.outcome,
        "effectiveDate": effective.isoformat(),
    }
    erp_export = {
        "source": "Oracle Fusion Cloud 26a-shaped synthetic export",
        "case": case,
        "recordId": record,
        "status": "Open",
        "organizationCode": "SEA",
        "itemNumber": f"NS-COMP-{ordinal:03d}",
        "quantity": quantity,
        "supplier": supplier,
        "lastUpdateDate": f"{AS_OF_DATE.isoformat()}T08:00:00-08:00",
    }
    measurements = [
        ["sample", "characteristic", "value", "unit", "lower", "upper", "result"],
        [f"S-{ordinal:03d}-1", "dimension_a", round(24.95 + (ordinal % 3) * 0.02, 2), "mm", 24.9, 25.1, "PASS"],
        [f"S-{ordinal:03d}-2", "dimension_a", round(25.01 + (ordinal % 2) * 0.03, 2), "mm", 24.9, 25.1, "PASS"],
        [f"S-{ordinal:03d}-3", "dielectric", 1510 + ordinal % 40, "V", 1500, "", "PASS"],
    ]
    lead_time_rows = [
        ["supplier", "item", "quoted_days", "historical_p50", "historical_p90", "capacity_confirmed", "valid_through"],
        [supplier, f"NS-COMP-{ordinal:03d}", 3 + ordinal % 11, 5 + ordinal % 4, 9 + ordinal % 5, "YES", (effective + timedelta(days=30)).isoformat()],
        ["Alternate Dynamics", f"NS-COMP-{ordinal:03d}", 7 + ordinal % 8, 8, 15, "NO", (effective + timedelta(days=20)).isoformat()],
    ]
    decision_rows = [
        ["timestamp", "case", "actor", "decision", "scope", "source"],
        [f"{AS_OF_DATE.isoformat()}T09:10:00-08:00", case, "U-OPS-LEAD", "evidence_verified", record, "slack"],
        [f"{AS_OF_DATE.isoformat()}T10:05:00-08:00", case, "U-APPROVER", "approved", effective.isoformat(), "drive_approval"],
    ]
    risk_rows = [
        ["risk_id", "case", "risk", "likelihood", "impact", "owner", "mitigation", "status"],
        [f"R-{ordinal:03d}-A", case, "incorrect record selection", "low", "high", scenario.role, "cross-check immutable identifiers", "OPEN"],
        [f"R-{ordinal:03d}-B", case, "unapproved scope expansion", "medium", "high", "U-APPROVER", "limit write to approved fields", "MITIGATED"],
    ]

    return [
        {
            "asset_id": f"{task_id}-policy",
            "path": "operating-policy.md",
            "title": "Operating policy",
            "kind": "policy",
            "source": "google_drive",
            "media_type": "text/markdown",
            "content": policy,
            "preview": policy.split("\n\n", 2)[-1][:320],
        },
        {
            "asset_id": f"{task_id}-contract",
            "path": "contract-or-service-control.md",
            "title": "Contract / service control",
            "kind": "contract",
            "source": "google_drive",
            "media_type": "text/markdown",
            "content": contract,
            "preview": contract.split("\n\n", 2)[-1][:320],
        },
        {
            "asset_id": f"{task_id}-quote",
            "path": "supplier-quotation.pdf",
            "title": "Supplier quotation",
            "kind": "vendor_pdf",
            "source": "gmail_attachment",
            "media_type": "application/pdf",
            "content": quote_text,
            "preview": quote_text.replace("\n", " · ")[:320],
        },
        {
            "asset_id": f"{task_id}-leadtime",
            "path": "supplier-lead-time-and-capacity.xlsx",
            "title": "Supplier lead-time and capacity workbook",
            "kind": "spreadsheet",
            "source": "google_drive",
            "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "rows": lead_time_rows,
            "content": json.dumps(lead_time_rows),
            "preview": f"Two supplier options; {supplier} has confirmed capacity through {(effective + timedelta(days=30)).isoformat()}.",
        },
        {
            "asset_id": f"{task_id}-decision",
            "path": "approval-decision-log.csv",
            "title": "Approval decision log",
            "kind": "spreadsheet_export",
            "source": "google_sheets",
            "media_type": "text/csv",
            "rows": decision_rows,
            "content": "\n".join(",".join(map(str, row)) for row in decision_rows) + "\n",
            "preview": "Timestamped operational verification and approval rows.",
        },
        {
            "asset_id": f"{task_id}-email",
            "path": "source-email-thread.eml",
            "title": "Source email thread",
            "kind": "email",
            "source": "gmail",
            "media_type": "message/rfc822",
            "content": email,
            "preview": email.split("\n\n", 1)[-1][:320],
        },
        {
            "asset_id": f"{task_id}-slack",
            "path": "operations-slack-thread.json",
            "title": "Operations Slack thread",
            "kind": "chat_thread",
            "source": "slack",
            "media_type": "application/json",
            "content": json.dumps(slack, indent=2, sort_keys=True) + "\n",
            "preview": " · ".join(message["text"] for message in slack["messages"])[:360],
        },
        {
            "asset_id": f"{task_id}-approval",
            "path": "drive-approval-record.json",
            "title": "Drive approval record",
            "kind": "approval",
            "source": "google_drive",
            "media_type": "application/json",
            "content": json.dumps(approval, indent=2, sort_keys=True) + "\n",
            "preview": f"Approval {approval['approvalId']} has the required reviewer response for the documented scope.",
        },
        {
            "asset_id": f"{task_id}-erp",
            "path": "oracle-starting-record.json",
            "title": "Oracle starting-record export",
            "kind": "erp_export",
            "source": "oracle_fusion",
            "media_type": "application/json",
            "content": json.dumps(erp_export, indent=2, sort_keys=True) + "\n",
            "preview": f"Open Oracle record {record} for item NS-COMP-{ordinal:03d}, quantity {quantity}.",
        },
        {
            "asset_id": f"{task_id}-measurements",
            "path": "inspection-measurements.csv",
            "title": "Inspection measurements",
            "kind": "quality_data",
            "source": "laboratory_drive",
            "media_type": "text/csv",
            "rows": measurements,
            "content": "\n".join(",".join(map(str, row)) for row in measurements) + "\n",
            "preview": "Three sample-level characteristic results with limits, units, and disposition.",
        },
        {
            "asset_id": f"{task_id}-risk",
            "path": "workflow-risk-register.xlsx",
            "title": "Workflow risk register",
            "kind": "spreadsheet",
            "source": "google_drive",
            "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "rows": risk_rows,
            "content": json.dumps(risk_rows),
            "preview": "Task-scoped record-selection and approval-scope risks with owners and mitigations.",
        },
        {
            "asset_id": f"{task_id}-spec",
            "path": "technical-specification.md",
            "title": "Technical specification",
            "kind": "specification",
            "source": "google_drive",
            "media_type": "text/markdown",
            "content": f"# Technical specification {record}\n\nRevision: R{1 + ordinal % 7}\nEffective: {effective.isoformat()}\nItem: NS-COMP-{ordinal:03d}\nRequired control: {scenario.outcome}\n",
            "preview": f"Revision R{1 + ordinal % 7}, effective {effective.isoformat()}, tied to {record}.",
        },
    ]

