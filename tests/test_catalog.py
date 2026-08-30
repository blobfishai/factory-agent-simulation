from __future__ import annotations

import hashlib
import json
import base64
import re
from collections import Counter

from factorybench.catalog import (
    FAMILIES,
    MINIMUM_PROVIDER_READ_CALLS,
    build_catalog,
    catalog_fingerprint,
    catalog_quality_report,
    task_fingerprint,
    task_tool_sequence,
)
from factorybench.server import tool_definitions
from factorybench.world import READ_TOOLS


def test_catalog_has_twenty_balanced_workflow_families() -> None:
    tasks = build_catalog()
    assert len(tasks) == 100
    assert len({task["task_id"] for task in tasks}) == 100
    assert Counter(task["family"] for task in tasks) == Counter({family: 5 for family in FAMILIES})
    assert "supply_action" not in tasks[0]["expected"]["answer"]
    assert tasks[0]["expected"]["answer"]["decision_timing_status"] == "ON_TIME"
    assert tasks[0]["answer_schema"]["properties"]["decision_timing_status"]["enum"] == [
        "ON_TIME",
        "LATE",
    ]
    assert tasks[0]["expected"]["answer"]["coverage_item_or_resource"] == "LMP-BULB-12"


def test_every_task_has_a_distinct_tool_call_sequence() -> None:
    tasks = build_catalog()
    report = catalog_quality_report(tasks)
    assert report["passed"] is True
    assert report["unique_titles"] == 100
    assert report["unique_sequences"] == 100
    assert report["duplicate_sequences"] == []
    assert report["closest_pair"]["similarity"] <= 0.80
    assert report["asset_role_count"] == 28
    assert report["asset_roles_with_unique_task_content"] == 28
    assert set(report["asset_role_unique_content_counts"].values()) == {100}
    assert report["semantic_invariants_checked"] >= 700
    assert report["semantic_violations"] == []
    assert len({task_tool_sequence(task) for task in tasks}) == 100


def test_task_and_catalog_fingerprints_pin_the_complete_executable_contract() -> None:
    tasks = build_catalog()
    rebuilt = build_catalog()
    assert task_fingerprint(tasks[0]) == task_fingerprint(rebuilt[0])
    assert catalog_fingerprint(tasks) == catalog_fingerprint(list(reversed(rebuilt)))

    changed = json.loads(json.dumps(tasks[0]))
    changed["instruction"] += " Changed contract."
    assert task_fingerprint(changed) != task_fingerprint(tasks[0])
    assert catalog_fingerprint([changed, *tasks[1:]]) != catalog_fingerprint(tasks)


def test_every_task_is_executable_cross_system_and_richly_seeded() -> None:
    tool_names = {tool["name"] for tool in tool_definitions()}
    for task in build_catalog():
        assert task["instruction"]
        assert task["seed_tables"]
        assert len(task["assets"]) == 28
        assert len(task["world"]["systems"]) >= 5
        assert {"oracle_fusion", "factorybench"} <= set(task["world"]["systems"])
        assert task["expected"]["assertions"]
        assert task["expected"]["investigations"]
        assert task["expected"]["calculations"]
        assert task["expected"]["answer_checks"]
        assert task["expected"]["answer"]
        assert task["required_reads"]
        assert len(task["reference_read_calls"]) >= MINIMUM_PROVIDER_READ_CALLS
        assert len(task["required_read_calls"]) == len(task["required_reads"])
        assert all(call["match"] == "result_contains" for call in task["required_read_calls"])
        assert all(call["expected_result_contains"] for call in task["required_read_calls"])
        assert all(
            alternative["match"] == "result_contains"
            and alternative["expected_result_contains"]
            for investigation in task["required_investigations"]
            for alternative in investigation["any_of"]
        )
        required_oracle_reads = {
            call["tool"]
            for call in task["required_read_calls"]
            if call["tool"].startswith("oracle_fusion.")
        }
        assert required_oracle_reads <= {
            *task["workflow"]["oracle_investigation_reads"],
        }
        assert len(required_oracle_reads) >= 4
        seeded_read_tools = {
            row["tool_name"]
            for row in task["seed_tables"]["api_fixtures"]
            if row["read_only"]
        }
        assert {
            tool
            for tool in READ_TOOLS
            if not tool.startswith("oracle_fusion.")
            and tool != "factorybench.context.get"
        } <= seeded_read_tools
        seeded_oracle_resources = {
            tool.rsplit(".", 1)[0]
            for tool in seeded_read_tools
            if tool.startswith("oracle_fusion.")
        }
        expected_oracle_resources = {
            tool.rsplit(".", 1)[0]
            for tool in (
                *task["workflow"]["oracle_investigation_reads"],
                task["workflow"]["post_write_read"],
            )
            if tool.startswith("oracle_fusion.")
        }
        assert seeded_oracle_resources == expected_oracle_resources
        assert task["answer_schema"]["additionalProperties"] is False
        assert set(task["answer_schema"]["required"]) == set(task["expected"]["answer"])
        assert task["oracle_steps"][0]["tool"] == "factorybench.context.get"
        assert task["oracle_steps"][-1]["tool"] == "factorybench.submit_answer"
        assert task["oracle_steps"][-1]["arguments"] == task["expected"]["answer"]
        assert {step["tool"] for step in task["oracle_steps"]} <= tool_names
        assert task["evaluation"]["metric"] == "FactoryScore"
        assert task["evaluation"]["weighted"] is True
        primary_assertion = next(
            assertion
            for assertion in task["expected"]["assertions"]
            if assertion["weight"] == 3.0
        )
        assert task["workflow"]["primary_write"] in primary_assertion["description"]
        assert "requestBody." in primary_assertion["description"]
        assert "exact provider-critical values" in primary_assertion["description"]


def test_employee_requests_hide_the_investigation_recipe_and_rubrics_are_specific() -> None:
    forbidden = {
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
    }
    tasks = build_catalog()
    report = catalog_quality_report(tasks)
    assert report["realism"] == {
        "prompt_violations": {},
        "closest_prompt_pair": {
            "task_ids": ["factorybench-060", "factorybench-088"],
            "similarity": 0.5871,
        },
        "closest_prompt_5_shingle_pair": {
            "task_ids": ["factorybench-058", "factorybench-079"],
            "similarity": 0.154639,
        },
        "minimum_structured_rows_by_asset_role": {
            "source_workbook": 12,
            "spreadsheet_export": 8,
            "source_reconciliation": 12,
            "control_calendar": 8,
        },
        "minimum_email_chars": 1738,
        "minimum_slack_messages": 6,
        "minimum_investigations_per_task": 14,
        "minimum_provider_reads_per_task": 26,
        "minimum_calculations_per_task": 15,
        "minimum_options_per_task": 3,
        "minimum_answer_fields_per_task": 16,
        "minimum_oracle_read_tables_per_task": 4,
        "minimum_task_specific_criteria": 14,
        "unique_criterion_sets": 100,
        "generic_criteria": [],
        "preassembled_packet_leaks": [],
        "maximum_precomputed_options_exposed_by_one_read": 1,
        "decision_mode_counts": {
            "financial": 17,
            "forecast": 5,
            "identity": 14,
            "plan": 11,
            "quantity": 34,
            "schedule": 19,
        },
        "unique_option_sets": 100,
        "unique_source_documents": 100,
    }
    assert len({task["instruction"] for task in tasks}) == 100
    assert len({tuple(option["id"] for option in task["decision_model"]["options"]) for task in tasks}) == 100
    for task in tasks:
        prompt = task["instruction"]
        assert 45 <= len(prompt.split()) <= 220
        assert not any(marker in prompt.lower() for marker in forbidden)
        assert 14 <= len(task["required_investigations"]) <= 16
        assert len(task["reference_read_calls"]) > len(task["required_read_calls"])
        assert len(task["decision_model"]["options"]) == 3
        option_ids = [option["id"] for option in task["decision_model"]["options"]]
        assert task["answer_schema"]["properties"]["recommended_option"]["enum"] == option_ids
        assert sum(option["recommended"] for option in task["decision_model"]["options"]) == 1
        assert next(option for option in task["decision_model"]["options"] if option["recommended"])["approval"] == "APPROVED"
        milestones = task["rubric_milestones"]
        descriptions = [milestone["description"] for milestone in milestones]
        assert len(milestones) == 14
        assert len({milestone["id"] for milestone in milestones}) == 14
        assert len(set(descriptions)) == 14
        assert sum(milestone["weight"] for milestone in milestones) == 100.0
        atomic_ids = {
            criterion["id"]
            for key in (
                "investigations",
                "post_write_verifications",
                "calculations",
                "assertions",
                "answer_checks",
            )
            for criterion in task["expected"][key]
        } | {"write_scope", "no_rejected_mutation"}
        milestone_atomic_ids = [
            criterion_id
            for milestone in milestones
            for criterion_id in milestone["criterion_ids"]
        ]
        assert len(milestone_atomic_ids) == len(set(milestone_atomic_ids))
        assert set(milestone_atomic_ids) == atomic_ids
        assert not any("produced the task-scoped" in description.lower() for description in descriptions)


def test_sources_require_option_calculation_instead_of_publishing_the_answer() -> None:
    for task in build_catalog():
        assets = {asset["kind"]: asset for asset in task["assets"]}
        assert set(assets) == {
            "policy",
            "contract",
            "external_pdf",
            "source_workbook",
            "spreadsheet_export",
            "email",
            "chat_thread",
            "approval",
            "erp_export",
            "source_reconciliation",
            "control_calendar",
            "specification",
            "engineering_bom_current",
            "engineering_bom_superseded",
            "vendor_price_catalog",
            "production_schedule",
            "shift_capacity",
            "supplier_capacity",
            "authority_matrix",
            "material_on_hand",
            "component_requirements",
            "quality_holds",
            "maintenance_outages",
            "planning_chat",
            "procurement_email",
            "source_lineage",
            "control_audit_log",
            "revision_index",
        }
        calendar = assets["control_calendar"]
        assert not {"completion", "recommended", "selected_option"} & set(calendar["rows"][0])
        assert len(calendar["rows"]) >= 8
        source_workbook = assets["source_workbook"]
        assert len(source_workbook["rows"]) >= 12
        assert "OBSERVED_NOT_NETTED" in source_workbook["content"]
        assert "recommended" not in source_workbook["content"].lower()
        assert len(assets["source_reconciliation"]["rows"]) >= 12
        external = assets["external_pdf"]["content"]
        option_ids = [option["id"] for option in task["decision_model"]["options"]]
        assert option_ids[1] in external
        assert sum(option_id in external for option_id in option_ids) == 1


def test_exact_provider_values_are_discoverable_without_publishing_a_decision_packet() -> None:
    for task in build_catalog():
        erp_export = json.loads(
            next(
                asset["content"]
                for asset in task["assets"]
                if asset["kind"] == "erp_export"
            )
        )
        crosswalk = erp_export["providerSetupCrosswalk"]
        applicable = next(
            candidate
            for candidate in crosswalk["candidates"]
            if candidate["controlStatus"] == "ACTIVE_APPLICABLE"
        )
        primary_assertion = next(
            assertion
            for assertion in task["expected"]["assertions"]
            if assertion["weight"] == 3.0
        )
        assert applicable["immutableRecord"] == task["decision_model"]["record"]
        assert applicable["sourceRevision"] == task["decision_model"]["revision"]
        assert (
            applicable["targetAndProviderValues"]
            == primary_assertion["payload_contains"]["arguments"]
        )
        assert "decisionOption" not in crosswalk
        assert '"recommended"' not in json.dumps(crosswalk)

    document_task = next(
        task for task in build_catalog() if task["task_id"] == "factorybench-024"
    )
    document_assertion = next(
        assertion
        for assertion in document_task["expected"]["assertions"]
        if assertion["weight"] == 3.0
    )
    exact_body = document_assertion["payload_contains"]["arguments"]["requestBody"]
    assert exact_body == {"DocumentType": "URL"}
    assert document_assertion["payload_text_any_of"] == [
        ["CASE-024", "NS-000024"],
        ["attach_matching_report", "2026-01-13", "R4", "AP-0024"],
    ]


def test_drive_read_fixtures_return_the_actual_listed_asset_content() -> None:
    for task in build_catalog():
        fixtures = task["seed_tables"]["api_fixtures"]
        drive_list = json.loads(
            next(
                fixture["response_json"]
                for fixture in fixtures
                if fixture["tool_name"] == "google_drive.files.list"
            )
        )
        path_by_id = {
            file["id"]: file["name"] for file in drive_list["files"]
        }
        content_by_path = {
            asset["path"]: asset["content"] for asset in task["assets"]
        }
        task_asset_reads = [
            call
            for call in task["reference_read_calls"]
            if call["tool"]
            in {
                "google_drive.files.get",
                "google_drive.files.download",
                "google_drive.files.export",
            }
            and "fileId" in call["arguments"]
        ]
        assert any(
            call["arguments"]["fileId"].endswith("-09")
            for call in task_asset_reads
        )
        for call in task_asset_reads:
            canonical_arguments = json.dumps(
                call["arguments"], sort_keys=True, separators=(",", ":")
            )
            response = json.loads(
                next(
                    fixture["response_json"]
                    for fixture in fixtures
                    if fixture["tool_name"] == call["tool"]
                    and fixture["arguments_json"] == canonical_arguments
                )
            )
            file_id = call["arguments"]["fileId"]
            assert response["id"] == file_id
            assert response["name"] == path_by_id[file_id]
            assert response["content"] == content_by_path[path_by_id[file_id]]


def test_sheets_metadata_and_seeded_ranges_describe_the_same_workbook() -> None:
    for task in build_catalog():
        fixtures = task["seed_tables"]["api_fixtures"]
        metadata = json.loads(
            next(
                fixture["response_json"]
                for fixture in fixtures
                if fixture["tool_name"] == "google_sheets.spreadsheets.get"
            )
        )
        tabs = {
            sheet["properties"]["title"] for sheet in metadata["sheets"]
        }
        assert tabs == {"Control", "Approvals", "Audit"}

        batch_fixture = next(
            fixture
            for fixture in fixtures
            if fixture["tool_name"]
            == "google_sheets.spreadsheets.values.batchGet"
        )
        batch_arguments = json.loads(batch_fixture["arguments_json"])
        batch_response = json.loads(batch_fixture["response_json"])
        assert [row["range"] for row in batch_response["valueRanges"]] == batch_arguments[
            "ranges"
        ]
        assert {
            row["range"].split("!", 1)[0]
            for row in batch_response["valueRanges"]
        } <= tabs
        assert all(row["values"] for row in batch_response["valueRanges"])


def test_business_semantics_and_provider_mutations_are_coherent() -> None:
    tasks = {task["task_id"]: task for task in build_catalog()}

    lamp = tasks["factorybench-001"]["expected"]["answer"]
    assert lamp["quantity_unit"] == "EA"
    assert lamp["required_quantity"] == 480
    assert lamp["usable_coverage_quantity"] == 360
    assert lamp["shortage_quantity"] == 120
    assert lamp["standard_external_readiness"] == "2026-01-17"
    assert lamp["expedited_external_readiness"] == "2026-01-14"
    assert lamp["baseline_completion"] == lamp["accelerated_completion"] == "2026-01-20"
    assert lamp["earliest_qualified_base_slot"] == "2026-01-18"
    assert lamp["expedite_completion_days_saved"] == 0
    assert lamp["weekend_shift_completion_days_saved"] == 2
    lamp_spec = next(
        asset for asset in tasks["factorybench-001"]["assets"] if asset["kind"] == "specification"
    )["content"]
    assert "Source finished or header quantity: 120" in lamp_spec

    reroute = tasks["factorybench-016"]
    reroute_write = next(
        step
        for step in reroute["oracle_steps"]
        if step["phase"] == "primary_mutation"
    )
    assert reroute["expected"]["answer"]["affected_resource_or_operation"] == (
        "NS-000016"
    )
    assert reroute["expected"]["answer"]["selected_resource_or_control"] == (
        reroute_write["arguments"]["requestBody"]["WorkCenterCode"]
    )

    diagnostic = tasks["factorybench-024"]
    assert diagnostic["expected"]["answer"]["source_or_target_record"] == (
        diagnostic["decision_model"]["record"]
    )
    assert diagnostic["expected"]["answer"]["immutable_match_key"] == (
        "NS-000024|R4|CASE-024"
    )
    assert diagnostic["answer_schema"]["properties"]["immutable_match_key"][
        "description"
    ].startswith(
        "Pipe-delimited source_or_target_record|effective_revision|case_reference"
    )

    forecast = tasks["factorybench-027"]["expected"]["answer"]
    assert forecast["program_or_asset_record"] == "PM-0027"

    invoice = tasks["factorybench-041"]["expected"]["answer"]
    assert invoice["financial_document_or_record"] == "INV-0041"
    assert "Effective usage per finished or header unit: 4 EA" in lamp_spec
    assert "Required quantity: 480 EA" not in lamp_spec

    tooling = tasks["factorybench-031"]["expected"]["answer"]
    assert tooling["evaluated_bid_count"] == 3
    assert tooling["technically_acceptable_bid_count"] == 2
    assert tooling["selected_landed_cost_usd"] == 11_402.11
    assert tooling["lowest_sticker_landed_cost_usd"] == 11_882.11
    assert tooling["next_acceptable_landed_cost_usd"] == 11_680.50
    assert tooling["sourcing_authority_headroom_usd"] == 238_597.89

    for task_id in ("factorybench-034", "factorybench-041", "factorybench-049", "factorybench-074", "factorybench-091", "factorybench-092"):
        answer = tasks[task_id]["expected"]["answer"]
        assert answer["exception_amount_usd"] == 0
        assert answer["supported_amount_usd"] == answer["document_amount_usd"]

    closed_osp = tasks["factorybench-100"]["expected"]["answer"]
    assert closed_osp["excluded_quantity"] == 0
    assert closed_osp["supported_quantity"] == closed_osp["source_quantity"] == 49

    emergency = tasks["factorybench-035"]
    emergency_write = next(step for step in emergency["oracle_steps"] if step["tool"] == emergency["workflow"]["primary_write"])
    assert emergency_write["arguments"]["requestBody"]["supplyRequestLines"][0]["Quantity"] == emergency["expected"]["answer"]["shortage_quantity"]

    rejected = tasks["factorybench-037"]
    rejected_write = next(step for step in rejected["oracle_steps"] if step["tool"] == rejected["workflow"]["primary_write"])
    assert rejected["expected"]["answer"]["supported_quantity"] == 115
    assert rejected["expected"]["answer"]["transaction_quantity"] == 15
    assert rejected_write["arguments"]["requestBody"]["TransactionType"] == "RETURN TO VENDOR"
    assert rejected_write["arguments"]["requestBody"]["Quantity"] == 15

    count = tasks["factorybench-057"]
    count_write = next(step for step in count["oracle_steps"] if step["tool"] == count["workflow"]["primary_write"])
    count_line = count_write["arguments"]["requestBody"]["TransactionLines"][0]
    assert count["expected"]["answer"]["transaction_quantity"] == -11
    assert count["expected"]["answer"]["source_quantity"] == 94
    assert count["expected"]["answer"]["observed_quantity"] == 83
    assert count["expected"]["answer"]["excluded_quantity"] == 0
    assert count["expected"]["answer"]["supported_quantity"] == 83
    assert count_line["TransactionType"] == "Cycle Count Adjustment"
    assert count_line["TransactionQuantity"] == -11

    labor = tasks["factorybench-071"]
    labor_write = next(step for step in labor["oracle_steps"] if step["tool"] == labor["workflow"]["primary_write"])
    labor_line = labor_write["arguments"]["requestBody"]["ResourceTransactionDetail"][0]
    assert labor_line["TransactionQuantity"] == 12
    assert labor_line["TransactionUnitOfMeasure"] == "HR"
    assert labor["expected"]["answer"]["supported_amount_usd"] == 1020

    duplicate = tasks["factorybench-072"]
    duplicate_write = next(step for step in duplicate["oracle_steps"] if step["tool"] == duplicate["workflow"]["primary_write"])
    duplicate_line = duplicate_write["arguments"]["requestBody"]["MaterialTransactionDetail"][0]
    assert duplicate_line["TransactionTypeCode"] == "MATERIAL_RETURN"
    assert duplicate_line["TransactionQuantity"] == 48
    assert duplicate_line["TransactionUnitOfMeasure"] == "KG"
    assert duplicate["answer_schema"]["properties"]["physical_transaction_quantity"][
        "description"
    ].startswith("Positive provider-posted quantity magnitude")
    assert duplicate["expected"]["answer"]["supported_amount_usd"] == 576

    compliance = tasks["factorybench-088"]["expected"]["answer"]
    assert compliance["supported_amount_usd"] == 0
    assert compliance["exception_amount_usd"] == compliance["document_amount_usd"]


def test_oracle_tools_are_documented_operations_not_business_verb_shortcuts() -> None:
    def assert_every_object_is_closed(schema: dict) -> None:
        if schema.get("type") == "object":
            assert schema.get("additionalProperties") is False
            for child in schema.get("properties", {}).values():
                assert_every_object_is_closed(child)
        elif schema.get("type") == "array":
            assert_every_object_is_closed(schema["items"])

    forbidden = {
        "approve_invoice",
        "hold_invoice",
        "create_work_order",
        "reroute_operation",
        "reschedule_work_order",
        "search_documents",
    }
    definitions = tool_definitions()
    names = {tool["name"] for tool in definitions}
    assert not names & forbidden
    oracle = [tool for tool in definitions if tool["name"].startswith("oracle_fusion.")]
    assert len(oracle) == 67
    for tool in oracle:
        upstream = tool["_meta"]["factorybench"]["upstream"]
        assert upstream["method"] in {"GET", "POST", "PATCH", "DELETE"}
        assert upstream["path"].startswith("/fscmRestApi/resources/11.13.18.05/")
        assert upstream["source"].startswith("https://docs.oracle.com/")
        assert "/26a/" in upstream["source"]
        assert not upstream["source"].endswith("/toc.htm")
        path_parameters = set(re.findall(r"\{([^{}]+)\}", upstream["path"]))
        assert path_parameters <= set(tool["inputSchema"]["required"])
        assert_every_object_is_closed(tool["inputSchema"])

    by_name = {tool["name"]: tool for tool in oracle}
    exact_operations = {
        "oracle_fusion.work_order_operations.list": (
            "GET",
            "/fscmRestApi/resources/11.13.18.05/workOrders/{WorkOrderId}/child/WorkOrderOperation",
            "https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fasrp/api-manufacturing-discrete-work-orders-active-operations-work-orders.html",
        ),
        "oracle_fusion.work_order_materials.list": (
            "GET",
            "/fscmRestApi/resources/11.13.18.05/workOrders/{WorkOrderId}/child/WorkOrderMaterial",
            "https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fasrp/api-manufacturing-discrete-work-orders-work-order-materials.html",
        ),
        "oracle_fusion.work_order_resources.list": (
            "GET",
            "/fscmRestApi/resources/11.13.18.05/workOrders/{WorkOrderId}/child/WorkOrderResource",
            "https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fasrp/api-manufacturing-discrete-work-orders-resources-operations.html",
        ),
        "oracle_fusion.work_order_operations.update": (
            "PATCH",
            "/fscmRestApi/resources/11.13.18.05/workOrders/{WorkOrderId}/child/WorkOrderOperation/{WorkOrderOperationId}",
            "https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fasrp/api-manufacturing-discrete-work-orders-active-operations-work-orders.html",
        ),
        "oracle_fusion.work_order_materials.update": (
            "PATCH",
            "/fscmRestApi/resources/11.13.18.05/workOrders/{WorkOrderId}/child/WorkOrderOperation/{WorkOrderOperationId2}/child/WorkOrderOperationMaterial/{WorkOrderOperationMaterialId}",
            "https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fasrp/api-manufacturing-discrete-work-orders-active-operations-work-orders-work-order-materials.html",
        ),
        "oracle_fusion.work_order_resources.update": (
            "PATCH",
            "/fscmRestApi/resources/11.13.18.05/workOrders/{WorkOrderId}/child/WorkOrderOperation/{WorkOrderOperationId}/child/WorkOrderOperationResource/{WorkOrderOperationResourceId}",
            "https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fasrp/api-manufacturing-discrete-work-orders-active-operations-work-orders-resources-operations.html",
        ),
        "oracle_fusion.maintenance_materials.list": (
            "GET",
            "/fscmRestApi/resources/11.13.18.05/maintenanceWorkOrders/{WorkOrderId}/child/WorkOrderOperation/{WoOperationId}/child/WorkOrderOperationMaterial",
            "https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fasrp/api-maintenance-maintenance-work-orders-operations-materials.html",
        ),
        "oracle_fusion.maintenance_resources.list": (
            "GET",
            "/fscmRestApi/resources/11.13.18.05/maintenanceWorkOrders/{WorkOrderId}/child/WorkOrderOperation/{WoOperationId}/child/WorkOrderOperationResource",
            "https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fasrp/api-maintenance-maintenance-work-orders-operations-resources.html",
        ),
        "oracle_fusion.receiving_receipt_transactions.list": (
            "GET",
            "/fscmRestApi/resources/11.13.18.05/receivingReceiptRequests/{HeaderInterfaceId}/child/lines",
            "https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fasrp/api-inventory-management-receiving-receipt-requests-requests-receiving-transactions.html",
        ),
        "oracle_fusion.purchase_order_lines.list": (
            "GET",
            "/fscmRestApi/resources/11.13.18.05/purchaseOrders/{purchaseOrdersUniqID}/child/lines",
            "https://docs.oracle.com/en/cloud/saas/procurement/26a/fapra/api-purchase-orders-lines.html",
        ),
    }
    for name, (method, path, source) in exact_operations.items():
        assert by_name[name]["_meta"]["factorybench"]["upstream"] == {
            "method": method,
            "path": path,
            "source": source,
        }

    substitute_body = by_name[
        "oracle_fusion.work_order_materials.replace_with_substitute"
    ]["inputSchema"]["properties"]["requestBody"]
    assert set(substitute_body["properties"]) == {
        "substituteItemId",
        "substituteItemNumber",
    }
    assert substitute_body["required"] == []

    material_update_body = by_name["oracle_fusion.work_order_materials.update"][
        "inputSchema"
    ]["properties"]["requestBody"]
    assert {"Quantity", "ItemNumber"}.isdisjoint(material_update_body["properties"])
    assert {
        "QuantityPERProduct",
        "SupplySubinventory",
        "SupplyType",
        "YieldFactor",
    } <= set(material_update_body["properties"])

    resource_update_body = by_name["oracle_fusion.work_order_resources.update"][
        "inputSchema"
    ]["properties"]["requestBody"]
    assert "ResourceCode" not in resource_update_body["properties"]
    assert {"AssignedUnits", "RequiredUsage", "UsageRate"} <= set(
        resource_update_body["properties"]
    )

    purchase_cancel_body = by_name["oracle_fusion.purchase_orders.cancel"][
        "inputSchema"
    ]["properties"]["requestBody"]
    assert set(purchase_cancel_body["properties"]) == {
        "acknowledgeWithinDays",
        "BCCEmail",
        "cancellationReason",
        "cancelUnfulfilledDemandFlag",
        "CCEmail",
        "communicationMethod",
        "email",
        "fax",
        "initiatingParty",
        "requiredAcknowledgment",
    }
    validation = next(tool for tool in oracle if tool["name"] == "oracle_fusion.invoices.validate")
    assert validation["_meta"]["factorybench"]["upstream"] == {
        "method": "POST",
        "path": "/fscmRestApi/resources/11.13.18.05/invoices/action/validateInvoice",
        "source": "https://docs.oracle.com/en/cloud/saas/financials/26a/farfa/op-invoices-action-validateinvoice-post.html",
    }
    assert validation["inputSchema"]["properties"]["requestBody"]["required"] == [
        "ProcessAction",
        "BusinessUnit",
        "Supplier",
        "InvoiceNumber",
    ]


def test_oracle_read_fixtures_keep_resource_specific_shapes_and_queries() -> None:
    protected_identifiers = {
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
        "InspectionId",
        "InspectionPlanId",
        "InventoryItemId",
        "HeaderInterfaceId",
        "InterfaceTransactionId",
        "HeaderId",
        "SupplyRequestId",
        "DocumentId",
        "CycleCountEntryId",
        "CycleCountHeaderId",
        "EntryHistoryId",
        "salesOrdersForOrderHubUniqID",
        "purchaseOrdersUniqID",
    }
    allowed = {
        "work_orders": {"WorkOrderId"},
        "sales_orders": {"HeaderId"},
        "work_order_operations": {"WorkOrderId", "WorkOrderOperationId"},
        "work_order_materials": {
            "WorkOrderId",
            "WorkOrderOperationId",
            "WorkOrderOperationMaterialId",
        },
        "work_order_resources": {
            "WorkOrderId",
            "WorkOrderOperationId",
            "WorkOrderOperationResourceId",
        },
        "maintenance_resources": {
            "WorkOrderId",
            "WoOperationId",
            "WoOperationResourceId",
        },
        "maintenance_materials": {
            "WorkOrderId",
            "WoOperationId",
            "WoOperationMaterialId",
        },
        "maintenance_work_orders": {"WorkOrderId"},
        "maintenance_operations": {"WorkOrderId", "WoOperationId"},
        "maintenance_documents": {"WorkOrderId", "DocumentId"},
        "maintenance_programs": {"MaintenanceProgramId"},
        "inventory_onhand_balances": {"InventoryItemId"},
        "cycle_count_definitions": {"CycleCountHeaderId"},
        "cycle_count_sequence_details": {
            "CycleCountEntryId",
            "CycleCountHeaderId",
        },
        "cycle_count_history": {"CycleCountEntryId", "EntryHistoryId"},
        "supply_requests": {"SupplyRequestId"},
        "receiving_receipt_requests": {"HeaderInterfaceId"},
        "receiving_receipt_transactions": {
            "HeaderInterfaceId",
            "InterfaceTransactionId",
        },
        "quality_inspection_results": {"InspectionId", "InspectionPlanId"},
        "inspection_plans": {"InspectionPlanId"},
        "suppliers": {"SupplierId"},
        "purchase_orders": {"POHeaderId", "SupplierId"},
        "purchase_order_lines": {"POHeaderId", "POLineId"},
        "draft_purchase_orders": {"POHeaderId", "SupplierId"},
        "invoices": {"InvoiceId"},
    }
    for task in build_catalog():
        for fixture in task["seed_tables"]["api_fixtures"]:
            tool = fixture["tool_name"]
            if not fixture["read_only"] or not tool.startswith("oracle_fusion."):
                continue
            resource = tool.removeprefix("oracle_fusion.").rsplit(".", 1)[0]
            response = json.loads(fixture["response_json"])
            records = response.get("items", [response])
            for record in records:
                assert not ((set(record) & protected_identifiers) - allowed[resource]), (
                    task["task_id"],
                    tool,
                    sorted((set(record) & protected_identifiers) - allowed[resource]),
                )
                assert "RecordId" not in record
                assert "ReferenceNumber" not in record
            arguments = json.loads(fixture["arguments_json"])
            assert not arguments.get("q", "").startswith("ReferenceNumber=")


def test_evidence_hashes_match_extracted_task_content() -> None:
    required_media = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "message/rfc822",
        "text/csv",
        "application/json",
        "text/markdown",
        "text/plain",
        "application/yaml",
    }
    for task in build_catalog():
        assert required_media <= {asset["media_type"] for asset in task["assets"]}
        rows = {row["asset_id"]: row for row in task["seed_tables"]["evidence_files"]}
        for asset in task["assets"]:
            row = rows[asset["asset_id"]]
            assert row["sha256"] == hashlib.sha256(asset["content"].encode()).hexdigest()


def test_every_asset_role_has_task_specific_content() -> None:
    hashes_by_role: dict[str, set[str]] = {}
    for task in build_catalog():
        for asset in task["assets"]:
            hashes_by_role.setdefault(asset["kind"], set()).add(
                hashlib.sha256(asset["content"].encode()).hexdigest()
            )

    assert len(hashes_by_role) == 28
    assert all(len(hashes) == 100 for hashes in hashes_by_role.values())


def test_collaboration_api_fixtures_expose_the_same_seeded_evidence() -> None:
    """The sandbox API and asset room must be two views of one task world."""

    for task in build_catalog():
        assets = {asset["kind"]: asset for asset in task["assets"]}
        fixtures = task["seed_tables"]["api_fixtures"]

        gmail = next(
            row for row in fixtures if row["tool_name"] == "gmail.messages.get"
        )
        gmail_response = json.loads(gmail["response_json"])
        encoded_body = gmail_response["payload"]["body"]["data"]
        encoded_body += "=" * (-len(encoded_body) % 4)
        assert base64.urlsafe_b64decode(encoded_body).decode() == assets["email"]["content"]

        seeded_thread = json.loads(assets["chat_thread"]["content"])
        seeded_text = [message["text"] for message in seeded_thread["messages"]]
        for tool in ("slack.conversations_history", "slack.conversations_replies"):
            fixture = next(row for row in fixtures if row["tool_name"] == tool)
            response = json.loads(fixture["response_json"])
            assert [message["text"] for message in response["messages"]] == seeded_text
