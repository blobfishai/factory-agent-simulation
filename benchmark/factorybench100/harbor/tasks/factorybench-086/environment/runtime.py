"""Closed, stateful multi-system sandbox for FactoryBench tasks."""

from __future__ import annotations

import base64
import json
import re
import sqlite3
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

try:
    from .contracts import READ_TOOLS, TOOL_BY_NAME, WRITE_TOOLS
except ImportError:  # Standalone Harbor/service bundle.
    from contracts import READ_TOOLS, TOOL_BY_NAME, WRITE_TOOLS  # type: ignore[no-redef]


TOOL_DESCRIPTIONS = {name: tool["description"] for name, tool in TOOL_BY_NAME.items()}
_SERVER_DESCRIPTIONS = {
    "oracle_fusion": "Documented Oracle Fusion Cloud ERP/SCM REST operations over synthetic task state.",
    "gmail": "Documented Gmail API operations over task-scoped messages and attachments.",
    "google_drive": "Documented Google Drive API operations over task-scoped files and comments.",
    "google_sheets": "Documented Google Sheets API operations over task-scoped workbooks.",
    "slack": "Documented Slack Web API operations over task-scoped conversations and files.",
    "factorybench": "Benchmark-only discovery and answer submission controls.",
}
TOOL_CONTRACTS = {
    server: {
        "description": description,
        "tools": sorted(
            name
            for name, tool in TOOL_BY_NAME.items()
            if tool["_meta"]["factorybench"]["server"] == server
        ),
    }
    for server, description in _SERVER_DESCRIPTIONS.items()
}

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _canonical_argument(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _canonical_argument(item)) for key, item in value.items()))
    if isinstance(value, list):
        return tuple(_canonical_argument(item) for item in value)
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def missing_required_read_calls(
    task: dict[str, Any],
    trace: list[dict[str, Any]],
    *,
    before_index: int | None = None,
) -> list[dict[str, Any]]:
    """Return task-bound read calls absent from a successful trace prefix."""

    investigations = task.get("required_investigations")
    if investigations is not None:
        missing_investigations = missing_required_investigations(
            task,
            trace,
            before_index=before_index,
        )
        return [
            {
                **investigation["any_of"][0],
                "investigation_id": investigation["id"],
                "description": investigation["description"],
            }
            for investigation in missing_investigations
        ]
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
        matched = any(
            _investigation_requirement_matches(entry, requirement)
            for entry in successful
        )
        if not matched:
            missing.append(requirement)
    return missing


def missing_required_investigations(
    task: dict[str, Any],
    trace: list[dict[str, Any]],
    *,
    before_index: int | None = None,
) -> list[dict[str, Any]]:
    """Return unsatisfied business investigations, independent of call order."""

    investigations = task.get("required_investigations")
    if investigations is None:
        investigations = [
            {
                "id": f"required_read_{index:02d}",
                "description": requirement["tool"],
                "any_of": [requirement],
            }
            for index, requirement in enumerate(task.get("required_read_calls", []), start=1)
        ]
    successful = [
        entry
        for entry in trace
        if entry.get("success") and (before_index is None or entry["index"] < before_index)
    ]
    missing: list[dict[str, Any]] = []
    for investigation in investigations:
        alternatives = investigation.get("any_of", [])
        matched = any(
            _investigation_requirement_matches(entry, requirement)
            for requirement in alternatives
            for entry in successful
        )
        if not matched:
            missing.append(investigation)
    return missing


def _result_contains(actual: Any, expected: Any) -> bool:
    """Return whether one nested provider response contains an expected fragment."""

    if isinstance(expected, dict):
        if isinstance(actual, dict) and all(
            key in actual and _result_contains(actual[key], value)
            for key, value in expected.items()
        ):
            return True
        if isinstance(actual, dict):
            return any(_result_contains(value, expected) for value in actual.values())
        if isinstance(actual, list):
            return any(_result_contains(value, expected) for value in actual)
        return False
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        return all(
            any(_result_contains(actual_item, expected_item) for actual_item in actual)
            for expected_item in expected
        )
    return actual == expected


def _investigation_requirement_matches(
    entry: dict[str, Any],
    requirement: dict[str, Any],
) -> bool:
    if entry["tool"] != requirement["tool"]:
        return False
    match = requirement.get("match")
    if match == "result_contains":
        fragment = requirement.get("expected_result_contains")
        return fragment is not None and _result_contains(entry.get("result"), fragment)
    if match == "successful_tool_call":
        return True
    expected_arguments = requirement.get("arguments")
    return expected_arguments is None or _canonical_argument(
        entry.get("arguments", {})
    ) == _canonical_argument(expected_arguments)


def missing_post_write_verifications(
    task: dict[str, Any],
    trace: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return provider readbacks not observed after their successful mutation."""

    successful = [entry for entry in trace if entry.get("success")]
    missing: list[dict[str, Any]] = []
    for verification in task.get("post_write_verifications", []):
        mutations = [
            entry
            for entry in successful
            if entry["tool"] == verification["after_tool"]
        ]
        if not mutations:
            missing.append(verification)
            continue
        mutation = min(mutations, key=lambda entry: entry["index"])
        mutation_index = mutation["index"]

        def projected_values_persisted(entry: dict[str, Any]) -> bool:
            for path in verification.get("write_argument_projection_paths", []):
                value: Any = mutation.get("arguments", {})
                for component in path.split("."):
                    if not isinstance(value, dict) or component not in value:
                        return False
                    value = value[component]
                if not _contains_nested_value(entry.get("result"), value):
                    return False
            return True

        matched = any(
            entry["index"] > mutation_index
            and _investigation_requirement_matches(entry, requirement)
            and _result_contains(
                entry.get("result"),
                verification.get("expected_result_contains", {}),
            )
            and projected_values_persisted(entry)
            for requirement in verification.get("any_of", [])
            for entry in successful
        )
        if not matched:
            missing.append(verification)
    return missing


def _contains_nested_value(actual: Any, expected: Any) -> bool:
    """Return whether an exact projected write value occurs in a read result."""

    if _result_contains(actual, expected):
        return True
    if isinstance(actual, dict):
        return any(_contains_nested_value(value, expected) for value in actual.values())
    if isinstance(actual, list):
        return any(_contains_nested_value(value, expected) for value in actual)
    return False


def _nested_subset_mismatches(
    actual: Any,
    expected: Any,
    path: str = "payload",
) -> dict[str, dict[str, Any]]:
    """Return exact-path mismatches for a nested expected subset."""

    mismatches: dict[str, dict[str, Any]] = {}
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return {path: {"expected": expected, "actual": actual}}
        for key, value in expected.items():
            child_path = f"{path}.{key}"
            if key not in actual:
                mismatches[child_path] = {
                    "expected": value,
                    "actual": None,
                    "reason": "missing key",
                }
                continue
            mismatches.update(
                _nested_subset_mismatches(actual[key], value, child_path)
            )
        return mismatches
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return {path: {"expected": expected, "actual": actual}}
        if len(actual) != len(expected):
            mismatches[path] = {
                "expected_length": len(expected),
                "actual_length": len(actual),
            }
            return mismatches
        for index, value in enumerate(expected):
            mismatches.update(
                _nested_subset_mismatches(actual[index], value, f"{path}[{index}]")
            )
        return mismatches
    if actual != expected:
        mismatches[path] = {"expected": expected, "actual": actual}
    return mismatches


def _decoded_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_decoded_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_decoded_text(item) for item in value)
    if not isinstance(value, str):
        return str(value)
    variants = [value]
    try:
        padded = value + "=" * (-len(value) % 4)
        variants.append(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        pass
    return " ".join(variants)


def _leaf_paths(value: Any, path: str = "") -> set[str]:
    if isinstance(value, dict):
        return {
            leaf
            for key, item in value.items()
            for leaf in _leaf_paths(item, f"{path}.{key}" if path else key)
        }
    if isinstance(value, list):
        return {
            leaf
            for index, item in enumerate(value)
            for leaf in _leaf_paths(item, f"{path}[{index}]")
        }
    return {path}


def payload_assertion_mismatches(
    row: dict[str, Any],
    assertion: dict[str, Any],
) -> dict[str, Any]:
    """Grade the actual provider payload persisted for a state assertion."""

    if not any(
        key in assertion
        for key in (
            "payload_contains",
            "payload_text_contains",
            "payload_text_any_of",
            "payload_narrative",
            "payload_email_to",
            "payload_allowed_argument_paths",
        )
    ):
        return {}
    raw_payload = row.get("payload_json")
    try:
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
    except json.JSONDecodeError:
        return {"payload_json": {"reason": "invalid JSON", "actual": raw_payload}}
    if not isinstance(payload, dict):
        return {"payload_json": {"reason": "payload is not an object", "actual": payload}}

    evidence: dict[str, Any] = {}
    expected_subset = assertion.get("payload_contains")
    if expected_subset is not None:
        nested = _nested_subset_mismatches(payload, expected_subset)
        if nested:
            evidence["payload_mismatches"] = nested
    expected_text = assertion.get("payload_text_contains", [])
    if expected_text:
        searchable = re.sub(
            r"[^a-z0-9.]+",
            " ",
            _decoded_text(payload.get("arguments", payload)).casefold(),
        )
        missing = [
            str(fragment)
            for fragment in expected_text
            if re.sub(r"[^a-z0-9.]+", " ", str(fragment).casefold()).strip()
            not in searchable
        ]
        if missing:
            evidence["missing_payload_text"] = missing
    expected_groups = assertion.get("payload_text_any_of", [])
    if expected_groups:
        searchable = re.sub(
            r"[^a-z0-9.]+",
            " ",
            _decoded_text(payload.get("arguments", payload)).casefold(),
        )
        missing_groups = [
            [str(fragment) for fragment in group]
            for group in expected_groups
            if not any(
                normalized
                and normalized in searchable
                for fragment in group
                for normalized in (
                    re.sub(
                        r"[^a-z0-9.]+",
                        " ",
                        str(fragment).casefold(),
                    ).strip(),
                )
            )
        ]
        if missing_groups:
            evidence["missing_payload_text_any_of"] = missing_groups
    expected_email_to = assertion.get("payload_email_to")
    if expected_email_to is not None:
        arguments = payload.get("arguments", {})
        envelope = arguments.get("message", arguments)
        raw = str(envelope.get("raw", ""))
        try:
            padded = raw + "=" * (-len(raw) % 4)
            decoded_email = base64.urlsafe_b64decode(padded).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            decoded_email = ""
        to_headers = [
            line.removeprefix("To: ").strip()
            for line in decoded_email.splitlines()
            if line.startswith("To: ")
        ]
        if to_headers != [expected_email_to]:
            evidence["payload_email_to_mismatch"] = {
                "expected": expected_email_to,
                "actual": to_headers,
            }
    narrative = assertion.get("payload_narrative")
    if narrative:
        arguments = payload.get("arguments", {})
        tool = payload.get("tool")
        if tool in {"gmail.drafts.create", "gmail.messages.send"}:
            envelope = arguments.get("message", arguments)
            raw = str(envelope.get("raw", ""))
            try:
                padded = raw + "=" * (-len(raw) % 4)
                narrative_text = base64.urlsafe_b64decode(padded).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                narrative_text = ""
            narrative_text = narrative_text.split("\r\n\r\n", 1)[-1]
        elif tool == "google_drive.comments.create":
            narrative_text = str(arguments.get("requestBody", {}).get("content", ""))
        elif tool == "slack.chat_postMessage":
            narrative_text = str(arguments.get("text", ""))
        else:
            narrative_text = _decoded_text(arguments)
        word_count = len(re.findall(r"\b[\w][\w'-]*\b", narrative_text))
        punctuation_count = sum(narrative_text.count(mark) for mark in ".;:!?")
        serialized = narrative_text.lstrip().startswith(("{", "["))
        narrative_mismatches = {
            key: value
            for key, value in {
                "minimum_words": (
                    {
                        "expected": narrative.get("minimum_words", 0),
                        "actual": word_count,
                    }
                    if word_count < narrative.get("minimum_words", 0)
                    else None
                ),
                "minimum_punctuation": (
                    {
                        "expected": narrative.get("minimum_punctuation", 0),
                        "actual": punctuation_count,
                    }
                    if punctuation_count < narrative.get("minimum_punctuation", 0)
                    else None
                ),
                "serialized": (
                    {"expected": False, "actual": True}
                    if narrative.get("reject_serialized") and serialized
                    else None
                ),
            }.items()
            if value is not None
        }
        if narrative_mismatches:
            evidence["payload_narrative_mismatches"] = narrative_mismatches
    allowed_paths = assertion.get("payload_allowed_argument_paths")
    if allowed_paths is not None:
        actual_paths = _leaf_paths(payload.get("arguments", {}))
        unexpected_paths = sorted(actual_paths - set(allowed_paths))
        if unexpected_paths:
            evidence["unexpected_payload_paths"] = unexpected_paths
    return evidence


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


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "any":
        return True
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def _validate_schema(value: Any, schema: dict[str, Any], path: str = "arguments") -> None:
    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        if not any(_type_matches(value, candidate) for candidate in expected_type):
            raise ValueError(f"{path} must match one of {expected_type}")
    elif isinstance(expected_type, str) and not _type_matches(value, expected_type):
        raise ValueError(f"{path} must be {expected_type}")
    if "const" in schema and value != schema["const"]:
        raise ValueError(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} must be one of {schema['enum']}")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        missing = [name for name in required if name not in value]
        if missing:
            raise ValueError(f"{path} missing required properties: {missing}")
        if schema.get("additionalProperties") is False:
            unexpected = sorted(set(value) - set(properties))
            if unexpected:
                raise ValueError(f"{path} has unexpected properties: {unexpected}")
        for name, item in value.items():
            if name in properties:
                _validate_schema(item, properties[name], f"{path}.{name}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            _validate_schema(item, schema["items"], f"{path}[{index}]")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError(f"{path} must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValueError(f"{path} must be <= {schema['maximum']}")


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
    """An isolated task world with schema validation and transactional writes."""

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

    def _one(self, query: str, params: Iterable[Any] = ()) -> dict[str, Any]:
        row = self.connection.execute(query, tuple(params)).fetchone()
        if row is None:
            raise ValueError("record not found")
        return dict(row)

    def _all(self, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(query, tuple(params)).fetchall()]

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        tables = [
            row["name"]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        snapshot: dict[str, list[dict[str, Any]]] = {}
        for table in tables:
            columns = [row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")]
            order = ", ".join(columns)
            rows = self.connection.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
            snapshot[table] = [dict(row) for row in rows]
        return snapshot

    def call_tool(self, tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        arguments = arguments or {}
        if tool not in TOOL_BY_NAME:
            result = {"error": f"unknown tool: {tool}"}
            self.trace.append({"index": len(self.trace), "tool": tool, "arguments": arguments, "success": False, "result": result})
            return result
        try:
            _validate_schema(arguments, self._input_schema(tool))
            if tool == "factorybench.context.get":
                result = self._context()
            elif tool == "factorybench.submit_answer":
                result = self._submit_answer(arguments)
            else:
                result = self._call_fixture(tool, arguments)
            self.connection.commit()
            success = True
        except (KeyError, TypeError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
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

    def _input_schema(self, tool: str) -> dict[str, Any]:
        if tool == "factorybench.submit_answer":
            return self.task["answer_schema"]
        return TOOL_BY_NAME[tool]["inputSchema"]

    def _audit(self, tool: str, table: str, record_id: str, action: str, payload: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO audit_log (task_id, tool, table_name, record_id, action, payload) VALUES (?, ?, ?, ?, ?, ?)",
            (self.task["task_id"], tool, table, record_id, action, json.dumps(payload, sort_keys=True)),
        )

    def _context(self) -> dict[str, Any]:
        evidence = self._all(
            "SELECT asset_id, path, title, kind, source, media_type, sha256 FROM evidence_files WHERE task_id = ? ORDER BY path",
            (self.task["task_id"],),
        )
        starting_records = self._all(
            "SELECT system, resource_type, resource_id, status, effective_at, revision FROM resource_state WHERE task_id = ? ORDER BY resource_id",
            (self.task["task_id"],),
        )
        mounted_servers = [
            {
                "name": server,
                "description": TOOL_CONTRACTS[server]["description"],
                "tools": TOOL_CONTRACTS[server]["tools"],
            }
            for server in self.task["world"]["systems"]
        ]
        ordinal = int(self.task["task_id"].rsplit("-", 1)[1])
        case = f"CASE-{ordinal:03d}"
        channel = ("C-PRODUCTION", "C-PROCUREMENT", "C-QUALITY", "C-FINANCE")[ordinal % 4]
        reference_records = {
            "case_reference": case,
            "gmail": {"userId": "me", "search_query": f'"{case}"'},
            "google_drive": {
                "search_query": f"name contains '{case}' and trashed = false",
                "primary_file_id": f"drive-{ordinal:03d}",
                "approval_file_id": f"drive-approval-{ordinal:03d}",
            },
            "google_sheets": {
                "spreadsheet_id": f"sheet-{ordinal:03d}",
                "decision_range": "Control!A1:I50",
                "outcome_write_range": f"Control!H{2 + ordinal % 40}",
                "audit_append_range": "Audit!A:G",
            },
            "slack": {
                "search_query": f'"{case}"',
                "channel": channel,
                "thread_ts": f"1768{ordinal:06d}.000100",
            },
            "oracle_fusion": {
                "case_reference": case,
                "only_data": True,
                "record_handles": self._oracle_record_handles(),
            },
        }
        return {
            "task": {
                "task_id": self.task["task_id"],
                "family": self.task["family"],
                "role": self.task["role"],
                "as_of": self.task["as_of"],
            },
            "organization": {
                "organization_id": self.task["world"]["organization_id"],
                "primary_plant": self.task["world"]["primary_plant"],
                "world_id": self.task["world"]["id"],
                "world": self.task["world"]["name"],
            },
            "state": {
                "scope": "isolated task snapshot",
                "persistence": "episode-local SQLite",
                "network": "closed",
            },
            "identity": self._all("SELECT user_id, display_name, role, approval_limit FROM users ORDER BY user_id"),
            "starting_records": starting_records,
            "reference_records": reference_records,
            "evidence_index": evidence,
            "tool_servers": mounted_servers,
        }

    def _oracle_record_handles(self) -> dict[str, Any]:
        ignored = {
            "requestBody",
            "q",
            "finder",
            "fields",
            "expand",
            "limit",
            "offset",
            "onlyData",
            "totalResults",
        }
        handles: dict[str, Any] = {}
        rows = self.connection.execute(
            "SELECT arguments_json FROM api_fixtures WHERE task_id = ? "
            "AND tool_name LIKE 'oracle_fusion.%' ORDER BY fixture_id",
            (self.task["task_id"],),
        ).fetchall()
        for row in rows:
            for key, value in json.loads(row["arguments_json"]).items():
                if key not in ignored:
                    handles.setdefault(key, value)
        return handles

    def _fixture_rows(self, tool: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT response_json, effect_json, read_only, arguments_json FROM api_fixtures "
            "WHERE task_id = ? AND tool_name = ? ORDER BY fixture_id",
            (self.task["task_id"], tool),
        ).fetchall()

    @staticmethod
    def _path_parameter_names(tool: str) -> set[str]:
        path = TOOL_BY_NAME[tool]["_meta"]["factorybench"]["upstream"]["path"]
        return set(re.findall(r"\{([^{}]+)\}", path))

    def _validate_read_identity(
        self,
        tool: str,
        arguments: dict[str, Any],
        expected: dict[str, Any],
    ) -> None:
        # Collection endpoints behave like their real APIs: a caller may use a
        # broad or alternate valid filter. Item endpoints still require the
        # immutable identifier discovered from a collection or task context.
        if tool in {
            "google_drive.files.get",
            "google_drive.files.download",
            "google_drive.files.export",
        }:
            self._drive_file_response(tool, str(arguments["fileId"]))
            return
        if tool.endswith(".list") or tool in {
            "gmail.messages.list",
            "google_drive.files.list",
            "slack.search_messages",
        }:
            return
        identity_keys = self._path_parameter_names(tool)
        if tool == "slack.conversations_history":
            identity_keys = {"channel"}
        elif tool == "slack.conversations_replies":
            identity_keys = {"channel"}
            expected_ts = str(expected.get("ts", ""))
            actual_ts = str(arguments.get("ts", ""))
            if actual_ts != expected_ts:
                ordinal = int(self.task["task_id"].rsplit("-", 1)[1])
                created_root_ts = f"1768{ordinal:06d}.000900"
                root_exists = any(
                    mutation.get("channel") == arguments.get("channel")
                    and not mutation.get("thread_ts")
                    for mutation in self._mutation_arguments(
                        "slack.chat_postMessage"
                    )
                )
                if actual_ts != created_root_ts or not root_exists:
                    raise ValueError(
                        f"{tool} record not found for ts={arguments.get('ts')!r}"
                    )
        elif tool == "slack.files_info":
            identity_keys = {"file"}
        elif tool in {
            "google_sheets.spreadsheets.values.get",
            "google_sheets.spreadsheets.values.batchGet",
        }:
            identity_keys = {"spreadsheetId"}
        for key in identity_keys:
            if key in expected and arguments.get(key) != expected[key]:
                raise ValueError(f"{tool} record not found for {key}={arguments.get(key)!r}")

    def _validate_write_arguments(
        self,
        tool: str,
        arguments: dict[str, Any],
        expected: dict[str, Any],
    ) -> None:
        server = TOOL_BY_NAME[tool]["_meta"]["factorybench"]["server"]
        if server == "oracle_fusion":
            for key in self._path_parameter_names(tool):
                if key in expected and arguments.get(key) != expected[key]:
                    raise ValueError(f"{tool} targets the wrong {key}")
            expected_body = expected.get("requestBody")
            if expected_body is None:
                return
            actual_body = arguments.get("requestBody")
            if not isinstance(actual_body, dict) or not actual_body:
                raise ValueError(f"{tool} requestBody must contain a scoped change")
            return

        target_keys = {
            "userId",
            "messageId",
            "id",
            "fileId",
            "approvalId",
            "spreadsheetId",
            "range",
            "channel",
            "thread_ts",
            "timestamp",
            "file",
        }
        if tool == "google_drive.comments.create":
            target_keys.remove("fileId")
            self._drive_file_response(
                "google_drive.files.get",
                str(arguments.get("fileId", "")),
            )
        if tool.startswith("google_sheets.spreadsheets.values."):
            target_keys.remove("range")
            actual_range = str(arguments.get("range", ""))
            expected_range = str(expected.get("range", ""))
            if "!" not in actual_range or actual_range.split("!", 1)[0] not in {
                "Control",
                "Audit",
            }:
                raise ValueError(f"{tool} targets a range outside the mounted workbook")
            if "!" not in expected_range:
                raise ValueError(f"{tool} fixture range is invalid")
        if tool == "slack.chat_postMessage":
            target_keys.remove("thread_ts")
        for key in target_keys:
            if key in expected and arguments.get(key) != expected[key]:
                raise ValueError(f"{tool} targets the wrong {key}")
        if tool == "gmail.drafts.create":
            expected_thread = expected.get("message", {}).get("threadId")
            if expected_thread is not None and arguments.get("message", {}).get(
                "threadId"
            ) != expected_thread:
                raise ValueError(f"{tool} targets the wrong message.threadId")

    def _drive_file_response(self, tool: str, file_id: str) -> dict[str, Any]:
        ordinal = int(self.task["task_id"].rsplit("-", 1)[1])
        rows = self._all(
            "SELECT path, title, kind, source, media_type, extracted_text, sha256 "
            "FROM evidence_files WHERE task_id = ? ORDER BY rowid",
            (self.task["task_id"],),
        )
        by_id: dict[str, dict[str, Any]] = {}
        for index, row in enumerate(rows, start=1):
            if row["path"] == "business-request-and-control.md":
                mounted_id = f"drive-{ordinal:03d}"
            elif row["path"] == "drive-approval-record.json":
                mounted_id = f"drive-approval-{ordinal:03d}"
            else:
                mounted_id = f"drive-{ordinal:03d}-{index:02d}"
            by_id[mounted_id] = row
        if file_id not in by_id:
            raise ValueError(f"{tool} record not found for fileId={file_id!r}")
        row = by_id[file_id]
        return {
            "kind": "drive#file",
            "id": file_id,
            "name": row["path"],
            "mimeType": row["media_type"],
            "description": row["title"],
            "modifiedTime": f"{self.task['as_of']}T09:00:00Z",
            "md5Checksum": row["sha256"],
            "content": row["extracted_text"],
        }

    def _mutation_arguments(self, write_tool: str) -> list[dict[str, Any]]:
        """Return the actual arguments persisted by successful provider writes."""

        rows = self.connection.execute(
            "SELECT payload_json FROM resource_state WHERE task_id = ? AND revision = 1 "
            "ORDER BY rowid",
            (self.task["task_id"],),
        ).fetchall()
        arguments: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            if payload.get("tool") == write_tool and isinstance(payload.get("arguments"), dict):
                arguments.append(payload["arguments"])
        return arguments

    def _gmail_message_from_write(self, write_tool: str) -> dict[str, Any] | None:
        mutations = self._mutation_arguments(write_tool)
        if not mutations:
            return None
        ordinal = int(self.task["task_id"].rsplit("-", 1)[1])
        arguments = mutations[-1]
        if write_tool == "gmail.drafts.create":
            envelope = arguments["message"]
            message_id = f"draft-msg-{ordinal:03d}"
            labels = ["DRAFT"]
        else:
            envelope = arguments
            message_id = f"sent-{ordinal:03d}"
            labels = ["SENT"]
        raw = envelope["raw"]
        return {
            "id": message_id,
            "threadId": envelope.get("threadId", f"thread-{ordinal:03d}"),
            "labelIds": labels,
            "raw": raw,
            "sizeEstimate": len(raw),
            "payload": {"body": {"data": raw, "size": len(raw)}},
        }

    def _seeded_gmail_messages(self) -> list[dict[str, Any]]:
        row = self.connection.execute(
            "SELECT response_json FROM api_fixtures WHERE task_id = ? "
            "AND tool_name = 'gmail.threads.get' ORDER BY fixture_id LIMIT 1",
            (self.task["task_id"],),
        ).fetchone()
        if row is None:
            return []
        response = json.loads(row["response_json"])
        return [
            deepcopy(message)
            for message in response.get("messages", [])
            if isinstance(message, dict)
        ]

    @staticmethod
    def _format_gmail_message(
        message: dict[str, Any],
        format_name: str,
    ) -> dict[str, Any]:
        common = {
            key: deepcopy(message[key])
            for key in ("id", "threadId", "labelIds", "snippet")
            if key in message
        }
        if format_name == "minimal":
            return common
        if format_name == "raw":
            body = message.get("payload", {}).get("body", {})
            return {
                **common,
                "raw": body.get("data", ""),
                "sizeEstimate": body.get("size", 0),
            }
        if format_name == "metadata":
            return {
                **common,
                "payload": {
                    "headers": deepcopy(
                        message.get("payload", {}).get("headers", [])
                    )
                },
            }
        return deepcopy(message)

    def _materialized_collaboration_response(
        self,
        tool: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Serve records created during the episode through provider read APIs."""

        ordinal = int(self.task["task_id"].rsplit("-", 1)[1])
        draft = self._gmail_message_from_write("gmail.drafts.create")
        sent = self._gmail_message_from_write("gmail.messages.send")
        if tool == "gmail.drafts.get" and arguments["id"] == f"draft-{ordinal:03d}":
            if draft is None:
                raise ValueError(f"gmail.drafts.get record not found for id={arguments['id']!r}")
            return {"id": arguments["id"], "message": draft}
        if tool == "gmail.messages.get":
            for message in (draft, sent):
                if message is not None and arguments["id"] == message["id"]:
                    return self._format_gmail_message(
                        message,
                        str(arguments.get("format", "full")),
                    )
            seeded = next(
                (
                    message
                    for message in self._seeded_gmail_messages()
                    if message.get("id") == arguments["id"]
                ),
                None,
            )
            if seeded is not None:
                return self._format_gmail_message(
                    seeded,
                    str(arguments.get("format", "full")),
                )
            if arguments["id"] in {f"draft-msg-{ordinal:03d}", f"sent-{ordinal:03d}"}:
                raise ValueError(f"gmail.messages.get record not found for id={arguments['id']!r}")
            if str(arguments["id"]).startswith(f"msg-{ordinal:03d}"):
                raise ValueError(f"gmail.messages.get record not found for id={arguments['id']!r}")

        if tool in {"google_drive.comments.list", "google_drive.comments.get"}:
            self._drive_file_response("google_drive.files.get", str(arguments["fileId"]))
            mutations = self._mutation_arguments("google_drive.comments.create")
            comments = [
                {
                    "id": f"comment-{ordinal:03d}",
                    "content": mutation["requestBody"]["content"],
                    "resolved": False,
                    "createdTime": f"{self.task['as_of']}T16:00:00Z",
                }
                for mutation in mutations
                if mutation.get("fileId") == arguments["fileId"]
            ]
            if tool == "google_drive.comments.list":
                return {
                    "kind": "drive#commentList",
                    "comments": comments,
                    "nextPageToken": None,
                }
            comment = next(
                (item for item in comments if item["id"] == arguments["commentId"]),
                None,
            )
            if comment is None:
                raise ValueError(
                    f"google_drive.comments.get record not found for commentId={arguments['commentId']!r}"
                )
            return comment
        return None

    def _sheet_values_from_mutation(
        self,
        spreadsheet_id: str,
        requested_range: str,
    ) -> dict[str, Any] | None:
        for write_tool in (
            "google_sheets.spreadsheets.values.update",
            "google_sheets.spreadsheets.values.append",
        ):
            for mutation in reversed(self._mutation_arguments(write_tool)):
                if mutation.get("spreadsheetId") != spreadsheet_id:
                    continue
                target_range = str(mutation["range"])
                same_range = requested_range == target_range
                same_append_sheet = (
                    write_tool.endswith(".append")
                    and requested_range.split("!", 1)[0] == target_range.split("!", 1)[0]
                )
                if not (same_range or same_append_sheet):
                    continue
                body = mutation["requestBody"]
                return {
                    "range": requested_range,
                    "majorDimension": body.get("majorDimension", "ROWS"),
                    "values": deepcopy(body["values"]),
                }
        return None

    def _seeded_sheet_value_range(
        self,
        spreadsheet_id: str,
        requested_range: str,
    ) -> dict[str, Any] | None:
        """Resolve a valid alternate range from the mounted workbook fixture.

        A task may use ``batchGet`` for its investigation and ``values.get``
        only for a post-write cell readback. Real Sheets clients can still call
        ``values.get`` for another range in that mounted workbook, so do not
        accidentally treat the narrow readback fixture as the whole sheet.
        """

        requested_sheet = requested_range.split("!", 1)[0]
        candidates: list[dict[str, Any]] = []
        for tool in (
            "google_sheets.spreadsheets.values.get",
            "google_sheets.spreadsheets.values.batchGet",
        ):
            for row in self._fixture_rows(tool):
                fixture_arguments = json.loads(row["arguments_json"])
                if str(fixture_arguments.get("spreadsheetId")) != spreadsheet_id:
                    continue
                response = json.loads(row["response_json"])
                value_ranges = (
                    response.get("valueRanges", [])
                    if tool.endswith("batchGet")
                    else [response]
                )
                candidates.extend(
                    value_range
                    for value_range in value_ranges
                    if str(value_range.get("range", "")).split("!", 1)[0]
                    == requested_sheet
                )
        if not candidates:
            return None

        a1 = re.compile(
            r"^(?:(?P<sheet>[^!]+)!)?(?P<column>[A-Z]+)(?P<row>\d+)"
        )
        requested_start = a1.match(requested_range)

        def column_number(letters: str) -> int:
            value = 0
            for letter in letters:
                value = value * 26 + ord(letter) - ord("A") + 1
            return value

        def source_rank(value_range: dict[str, Any]) -> tuple[bool, int]:
            source_start = a1.match(str(value_range.get("range", "")))
            covers_requested_start = bool(
                requested_start
                and source_start
                and int(source_start.group("row"))
                <= int(requested_start.group("row"))
                and column_number(source_start.group("column"))
                <= column_number(requested_start.group("column"))
            )
            return (
                covers_requested_start,
                sum(len(row) for row in value_range.get("values", [])),
            )

        source = max(
            candidates,
            key=source_rank,
        )
        return self._slice_value_range(source, requested_range)

    @staticmethod
    def _slice_value_range(
        value_range: dict[str, Any],
        requested_range: str,
    ) -> dict[str, Any]:
        """Apply basic A1 row/column bounds like the Sheets values API."""

        pattern = re.compile(
            r"^(?:(?P<sheet>[^!]+)!)?(?P<start_col>[A-Z]+)(?P<start_row>\d+)"
            r"(?::(?P<end_col>[A-Z]+)(?P<end_row>\d+))?$"
        )
        requested = pattern.fullmatch(requested_range)
        source = pattern.fullmatch(str(value_range.get("range", "")))
        if requested is None or source is None:
            return deepcopy(value_range)
        if requested.group("sheet") != source.group("sheet"):
            return {
                "range": requested_range,
                "majorDimension": value_range.get("majorDimension", "ROWS"),
                "values": [],
            }

        def column_index(letters: str) -> int:
            value = 0
            for letter in letters:
                value = value * 26 + ord(letter) - ord("A") + 1
            return value - 1

        requested_start_col = column_index(requested.group("start_col"))
        requested_end_col = column_index(
            requested.group("end_col") or requested.group("start_col")
        )
        requested_start_row = int(requested.group("start_row")) - 1
        requested_end_row = int(
            requested.group("end_row") or requested.group("start_row")
        ) - 1
        source_start_col = column_index(source.group("start_col"))
        source_start_row = int(source.group("start_row")) - 1
        row_start = max(0, requested_start_row - source_start_row)
        row_end = max(row_start, requested_end_row - source_start_row + 1)
        column_start = max(0, requested_start_col - source_start_col)
        column_end = max(column_start, requested_end_col - source_start_col + 1)
        values = [
            list(row[column_start:column_end])
            for row in value_range.get("values", [])[row_start:row_end]
        ]
        return {
            "range": requested_range,
            "majorDimension": value_range.get("majorDimension", "ROWS"),
            "values": values,
        }

    def _reflect_collaboration_state(
        self,
        tool: str,
        arguments: dict[str, Any],
        response: dict[str, Any],
    ) -> dict[str, Any]:
        """Overlay successful collaboration writes on subsequent provider reads."""

        ordinal = int(self.task["task_id"].rsplit("-", 1)[1])
        draft = self._gmail_message_from_write("gmail.drafts.create")
        sent = self._gmail_message_from_write("gmail.messages.send")
        if tool == "gmail.messages.list":
            query = str(arguments.get("q", "")).lower()
            label_ids = {str(label).upper() for label in arguments.get("labelIds", [])}
            if "in:drafts" in query or "DRAFT" in label_ids:
                messages = [draft] if draft is not None else []
            elif "in:sent" in query or "SENT" in label_ids:
                messages = [sent] if sent is not None else []
            else:
                messages = [*response.get("messages", [])]
                messages.extend(message for message in (draft, sent) if message is not None)
            summaries = [
                {"id": message["id"], "threadId": message["threadId"]}
                for message in messages
            ]
            return {"messages": summaries, "resultSizeEstimate": len(summaries)}

        if tool == "gmail.threads.get":
            messages = [*response.get("messages", [])]
            known_ids = {message.get("id") for message in messages}
            messages.extend(
                deepcopy(message)
                for message in (draft, sent)
                if message is not None
                and message["threadId"] == arguments["id"]
                and message["id"] not in known_ids
            )
            response["messages"] = messages
            return response

        if tool == "google_sheets.spreadsheets.values.get":
            dynamic = self._sheet_values_from_mutation(
                str(arguments["spreadsheetId"]),
                str(arguments["range"]),
            )
            return dynamic or self._slice_value_range(
                response,
                str(arguments["range"]),
            )

        if tool == "google_sheets.spreadsheets.values.batchGet":
            base_ranges = response.get("valueRanges", [])
            value_ranges = []
            for requested_range in arguments["ranges"]:
                dynamic = self._sheet_values_from_mutation(
                    str(arguments["spreadsheetId"]),
                    str(requested_range),
                )
                requested_sheet = str(requested_range).split("!", 1)[0]
                seeded = next(
                    (
                        item
                        for item in base_ranges
                        if item.get("range") == requested_range
                    ),
                    None,
                ) or next(
                    (
                        item
                        for item in base_ranges
                        if str(item.get("range", "")).split("!", 1)[0]
                        == requested_sheet
                    ),
                    None,
                )
                value_ranges.append(
                    dynamic
                    or (
                        self._slice_value_range(
                            seeded,
                            str(requested_range),
                        )
                        if seeded is not None
                        else None
                    )
                    or {
                        "range": requested_range,
                        "majorDimension": "ROWS",
                        "values": [],
                    }
                )
            return {
                "spreadsheetId": arguments["spreadsheetId"],
                "valueRanges": value_ranges,
            }

        if tool == "slack.conversations_replies":
            root_ts = f"1768{ordinal:06d}.000900"
            messages = (
                []
                if arguments.get("ts") == root_ts
                else [*response.get("messages", [])]
            )
            for index, mutation in enumerate(
                self._mutation_arguments("slack.chat_postMessage"),
                start=1,
            ):
                mutation_target = mutation.get("thread_ts") or root_ts
                if (
                    mutation.get("channel") == arguments["channel"]
                    and mutation_target == arguments["ts"]
                ):
                    messages.append(
                        {
                            "type": "message",
                            "ts": (
                                root_ts
                                if not mutation.get("thread_ts")
                                else f"1768{ordinal:06d}.{900 + index:06d}"
                            ),
                            **(
                                {"thread_ts": mutation["thread_ts"]}
                                if mutation.get("thread_ts")
                                else {}
                            ),
                            "text": mutation["text"],
                            "user": "U-FACTORY-AGENT",
                        }
                    )
            for mutation in self._mutation_arguments("slack.reactions_add"):
                if mutation.get("channel") != arguments["channel"]:
                    continue
                target = next(
                    (
                        message
                        for message in messages
                        if message.get("ts") == mutation.get("timestamp")
                    ),
                    None,
                )
                if target is None:
                    continue
                reactions = target.setdefault("reactions", [])
                if not any(
                    reaction.get("name") == mutation.get("name")
                    for reaction in reactions
                ):
                    reactions.append(
                        {
                            "name": mutation["name"],
                            "count": 1,
                            "users": ["U-FACTORY-AGENT"],
                        }
                    )
            response["messages"] = messages
            return response
        return response

    def _oracle_readback_response(
        self,
        tool: str,
        response: dict[str, Any],
    ) -> dict[str, Any]:
        """Reflect the committed Oracle mutation on a subsequent provider read."""

        tool_resource = tool.rsplit(".", 1)[0]
        verification = next(
            (
                item
                for item in self.task.get("post_write_verifications", [])
                if any(
                    alternative["tool"].rsplit(".", 1)[0] == tool_resource
                    for alternative in item.get("any_of", [])
                )
            ),
            None,
        )
        if verification is None:
            return response
        primary_write_resource = self.task["workflow"]["primary_write"].rsplit(".", 1)[0]
        state = self.connection.execute(
            "SELECT status, effective_at, payload_json FROM resource_state "
            "WHERE task_id = ? AND system = 'oracle_fusion' AND resource_type = ? "
            "AND revision = 1 ORDER BY rowid LIMIT 1",
            (self.task["task_id"], primary_write_resource),
        ).fetchone()
        # Harbor deliberately omits the private oracle trajectory from the
        # sidecar task payload.  The authoritative fixture table still contains
        # the provider request used to define the expected transition, so use it
        # as the comparison source in both the full and slim runtime shapes.
        reference_fixture = self.connection.execute(
            "SELECT arguments_json FROM api_fixtures "
            "WHERE task_id = ? AND tool_name = ? ORDER BY fixture_id LIMIT 1",
            (self.task["task_id"], self.task["workflow"]["primary_write"]),
        ).fetchone()
        reference_arguments: dict[str, Any] = (
            json.loads(reference_fixture["arguments_json"])
            if reference_fixture is not None
            else {}
        )
        primary_assertion = next(
            (
                assertion
                for assertion in self.task.get("expected", {}).get(
                    "assertions", []
                )
                if assertion.get("payload_contains", {}).get("tool")
                == self.task["workflow"]["primary_write"]
            ),
            None,
        )
        reference_critical_arguments = (
            primary_assertion["payload_contains"]["arguments"]
            if primary_assertion is not None
            else reference_arguments
        )
        actual_arguments: dict[str, Any] = {}
        if state is not None:
            payload = json.loads(state["payload_json"])
            if isinstance(payload.get("arguments"), dict):
                actual_arguments = payload["arguments"]
        unexpected_argument_paths = (
            _leaf_paths(actual_arguments)
            - set(primary_assertion.get("payload_allowed_argument_paths", []))
            if primary_assertion is not None
            and "payload_allowed_argument_paths" in primary_assertion
            else set()
        )
        exact_transition = not _nested_subset_mismatches(
            actual_arguments,
            reference_critical_arguments,
            "arguments",
        ) and not unexpected_argument_paths
        identity = verification.get("target_identity", {})

        def matches_identity(item: Any) -> bool:
            return isinstance(item, dict) and all(
                item.get(key) == value for key, value in identity.items()
            )

        if isinstance(response.get("items"), list):
            target = next((item for item in response["items"] if matches_identity(item)), None)
            if state is None and verification.get("materializes_new_record"):
                response["items"] = [
                    item for item in response["items"] if not matches_identity(item)
                ]
                response["count"] = len(response["items"])
                return response
            if target is None or state is None:
                return response
        else:
            if state is None and verification.get("materializes_new_record"):
                return {
                    "error": {
                        "code": "404",
                        "message": "The requested Fusion resource does not exist yet.",
                    }
                }
            if state is None:
                return response
            target = response

        def merge(actual: dict[str, Any], patch: dict[str, Any]) -> None:
            for key, value in patch.items():
                if isinstance(value, dict) and isinstance(actual.get(key), dict):
                    merge(actual[key], value)
                else:
                    actual[key] = deepcopy(value)

        if exact_transition:
            # Critical state may be correct while optional human prose differs.
            # Preserve the caller's narrative in the readback, then apply only
            # the verifier's provider-critical/system-generated state patch.
            for key, value in actual_arguments.get("requestBody", {}).items():
                if key in target:
                    target[key] = deepcopy(value)
            merge(target, verification.get("expected_result_contains", {}))
            return response

        # Provider-valid business mistakes are accepted and observable. Reflect
        # only values supplied by the caller; never synthesize the gold state in
        # a read response or leak it through a write-time validation error.
        actual_body = actual_arguments.get("requestBody", {})
        reference_body = reference_arguments.get("requestBody", {})

        def merge_supplied(actual: dict[str, Any], supplied: dict[str, Any]) -> None:
            for key, value in supplied.items():
                if key not in actual:
                    continue
                if isinstance(value, dict) and isinstance(actual.get(key), dict):
                    merge_supplied(actual[key], value)
                else:
                    actual[key] = deepcopy(value)

        def value_at_path(value: Any, path: tuple[str | int, ...]) -> tuple[bool, Any]:
            current = value
            for part in path:
                if isinstance(part, int):
                    if not isinstance(current, list) or part >= len(current):
                        return False, None
                    current = current[part]
                else:
                    if not isinstance(current, dict) or part not in current:
                        return False, None
                    current = current[part]
            return True, current

        def matching_paths(
            value: Any,
            needle: Any,
            prefix: tuple[str | int, ...] = (),
        ) -> list[tuple[str | int, ...]]:
            if isinstance(value, dict):
                return [
                    path
                    for key, item in value.items()
                    for path in matching_paths(item, needle, (*prefix, key))
                ]
            if isinstance(value, list):
                return [
                    path
                    for index, item in enumerate(value)
                    for path in matching_paths(item, needle, (*prefix, index))
                ]
            return [prefix] if value == needle else []

        merge_supplied(target, actual_body)
        for key, expected_value in verification.get(
            "expected_result_contains", {}
        ).items():
            paths = matching_paths(reference_body, expected_value)
            replacements = [
                actual_value
                for path in paths
                for found, actual_value in [value_at_path(actual_body, path)]
                if found
            ]
            if replacements and all(value == replacements[0] for value in replacements):
                target[key] = deepcopy(replacements[0])
        return response

    @staticmethod
    def _reflect_oracle_write_response(
        response: dict[str, Any],
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Echo caller-supplied record fields in Oracle create/update results.

        Oracle record-shaped POST/PATCH fixtures return a representation of the
        affected resource.  A schema-valid business mistake must therefore be
        visible in that acknowledgement, not silently replaced by the private
        benchmark answer.  Action endpoints whose result does not expose a
        request field are left unchanged.
        """

        body = arguments.get("requestBody")
        if not isinstance(body, dict):
            return response
        for key, value in body.items():
            if key in response:
                response[key] = deepcopy(value)
        return response

    def _call_fixture(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        materialized = self._materialized_collaboration_response(tool, arguments)
        if materialized is not None:
            return materialized
        row = self.connection.execute(
            "SELECT response_json, effect_json, read_only FROM api_fixtures WHERE task_id = ? AND tool_name = ? AND arguments_json = ?",
            (self.task["task_id"], tool, _canonical_json(arguments)),
        ).fetchone()
        if row is None:
            if tool == "google_sheets.spreadsheets.values.get":
                seeded = self._seeded_sheet_value_range(
                    str(arguments["spreadsheetId"]),
                    str(arguments["range"]),
                )
                if seeded is not None:
                    return self._reflect_collaboration_state(
                        tool,
                        arguments,
                        seeded,
                    )
            rows = self._fixture_rows(tool)
            if not rows:
                if tool.startswith("oracle_fusion.") and tool.endswith(".list"):
                    return {
                        "items": [],
                        "count": 0,
                        "hasMore": False,
                        "limit": arguments.get("limit", 25),
                        "offset": arguments.get("offset", 0),
                        "links": [],
                    }
                raise ValueError(f"no task-scoped resource is mounted for {tool}")
            row = rows[0]
            expected_arguments = json.loads(row["arguments_json"])
            if tool in READ_TOOLS:
                self._validate_read_identity(tool, arguments, expected_arguments)
            else:
                self._validate_write_arguments(tool, arguments, expected_arguments)
        if bool(row["read_only"]) != (tool in READ_TOOLS):
            raise ValueError(f"fixture mutability does not match the pinned contract for {tool}")
        response = json.loads(row["response_json"])
        if tool in {
            "google_drive.files.get",
            "google_drive.files.download",
            "google_drive.files.export",
        }:
            response = self._drive_file_response(tool, str(arguments["fileId"]))
            if tool == "google_drive.files.get" and arguments.get("alt") != "media":
                response.pop("content", None)
        if tool.startswith("oracle_fusion.") and tool in READ_TOOLS:
            response = self._oracle_readback_response(tool, response)
        elif tool.startswith("oracle_fusion."):
            response = self._reflect_oracle_write_response(response, arguments)
        elif tool in READ_TOOLS:
            response = self._reflect_collaboration_state(tool, arguments, response)
        if tool == "google_sheets.spreadsheets.values.update" and arguments.get(
            "includeValuesInResponse"
        ):
            body = arguments["requestBody"]
            response["updatedData"] = {
                "range": arguments["range"],
                "majorDimension": body.get("majorDimension", "ROWS"),
                "values": deepcopy(body["values"]),
            }
        if row["effect_json"] is not None:
            effect = json.loads(row["effect_json"])
            payload = json.loads(effect["payload_json"])
            payload["arguments"] = deepcopy(arguments)
            effect["payload_json"] = _canonical_json(payload)
            self.connection.execute(
                "INSERT INTO resource_state (task_id, system, resource_type, resource_id, status, effective_at, payload_json, revision) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(task_id, resource_id) DO UPDATE SET "
                "system = excluded.system, resource_type = excluded.resource_type, "
                "status = excluded.status, effective_at = excluded.effective_at, "
                "payload_json = excluded.payload_json, revision = excluded.revision",
                (
                    effect["task_id"],
                    effect["system"],
                    effect["resource_type"],
                    effect["resource_id"],
                    effect["status"],
                    effect["effective_at"],
                    effect["payload_json"],
                    effect["revision"],
                ),
            )
            self._audit(tool, "resource_state", effect["resource_id"], "upsert", effect)
        return response

    def _submit_answer(self, fields: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_answer_fields(self.task, fields)
        for field, value in normalized.items():
            self.connection.execute(
                "INSERT INTO answers (task_id, field, value) VALUES (?, ?, ?) "
                "ON CONFLICT(task_id, field) DO UPDATE SET value = excluded.value",
                (self.task["task_id"], field, value),
            )
        self._audit("factorybench.submit_answer", "answers", self.task["task_id"], "submit", normalized)
        return {"accepted": True, "task_id": self.task["task_id"], "fields": normalized}


__all__ = [
    "FactoryWorld",
    "READ_TOOLS",
    "TOOL_CONTRACTS",
    "TOOL_DESCRIPTIONS",
    "WRITE_TOOLS",
    "missing_required_investigations",
    "missing_required_read_calls",
    "missing_post_write_verifications",
    "normalize_answer_fields",
    "payload_assertion_mismatches",
    "seed_database",
]
