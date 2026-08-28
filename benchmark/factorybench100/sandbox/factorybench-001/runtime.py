"""Closed, stateful multi-system sandbox for FactoryBench tasks."""

from __future__ import annotations

import base64
import json
import re
import sqlite3
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
    "google_drive": "Documented Google Drive API operations over task-scoped files and approvals.",
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
        expected_arguments = requirement.get("arguments")
        matched = any(
            entry["tool"] == requirement["tool"]
            and (
                requirement.get("match") == "successful_tool_call"
                or expected_arguments is None
                or _canonical_argument(entry.get("arguments", {}))
                == _canonical_argument(expected_arguments)
            )
            for entry in successful
        )
        if not matched:
            missing.append(requirement)
    return missing


def _contains_expected(actual: Any, expected: Any, path: str = "arguments") -> None:
    """Require an approved Oracle payload while allowing harmless extra fields."""

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise ValueError(f"{path} must be an object")
        for key, value in expected.items():
            if key not in actual:
                raise ValueError(f"{path} is missing approved field {key}")
            _contains_expected(actual[key], value, f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError(f"{path} must contain the approved {len(expected)} item(s)")
        for index, value in enumerate(expected):
            _contains_expected(actual[index], value, f"{path}[{index}]")
        return
    if actual != expected:
        raise ValueError(f"{path} does not match the approved value")


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
            if tool in WRITE_TOOLS:
                self._require_preflight()
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

    def _require_preflight(self) -> None:
        missing = missing_required_read_calls(self.task, self.trace)
        if missing:
            rendered = ", ".join(
                f"{requirement['tool']}({json.dumps(requirement.get('arguments', {}), sort_keys=True)})"
                for requirement in missing
            )
            raise ValueError(f"read-before-write control failed; missing: {rendered}")

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
                "decision_range": "Control!A1:H50",
                "outcome_write_range": f"Control!H{2 + ordinal % 40}",
                "audit_append_range": "Audit!A:F",
            },
            "slack": {
                "search_query": f'"{case}"',
                "channel": channel,
                "thread_ts": f"1768{ordinal:06d}.000100",
            },
            "oracle_fusion": {
                "filter": f"ReferenceNumber='{case}'",
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
            identity_keys = {"channel", "ts"}
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
            _contains_expected(arguments, expected)
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
        for key in target_keys:
            if key in expected and key in arguments and arguments[key] != expected[key]:
                raise ValueError(f"{tool} targets the wrong {key}")
        if tool in {
            "gmail.drafts.create",
            "gmail.messages.send",
            "google_drive.comments.create",
            "google_sheets.spreadsheets.values.append",
            "google_sheets.spreadsheets.values.update",
            "slack.chat_postMessage",
        }:
            searchable = _decoded_text(arguments)
            ordinal = int(self.task["task_id"].rsplit("-", 1)[1])
            case = f"CASE-{ordinal:03d}"
            expected_values = [str(value) for value in self.task["expected"]["answer"].values()]
            if case not in searchable and not any(value in searchable for value in expected_values):
                raise ValueError(f"{tool} content must reference the approved case or outcome")

    def _drive_file_response(self, tool: str, file_id: str) -> dict[str, Any]:
        ordinal = int(self.task["task_id"].rsplit("-", 1)[1])
        rows = self._all(
            "SELECT path, title, kind, source, media_type, extracted_text, sha256 "
            "FROM evidence_files WHERE task_id = ? ORDER BY rowid",
            (self.task["task_id"],),
        )
        by_id: dict[str, dict[str, Any]] = {}
        for index, row in enumerate(rows, start=1):
            if row["path"] == "contract-or-service-control.md":
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

    def _call_fixture(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT response_json, effect_json, read_only FROM api_fixtures WHERE task_id = ? AND tool_name = ? AND arguments_json = ?",
            (self.task["task_id"], tool, _canonical_json(arguments)),
        ).fetchone()
        if row is None:
            rows = self._fixture_rows(tool)
            if not rows:
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
        if row["effect_json"] is not None:
            effect = json.loads(row["effect_json"])
            payload = json.loads(effect["payload_json"])
            payload["arguments"] = arguments
            effect["payload_json"] = _canonical_json(payload)
            self.connection.execute(
                "INSERT INTO resource_state (task_id, system, resource_type, resource_id, status, effective_at, payload_json, revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
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
    "missing_required_read_calls",
    "normalize_answer_fields",
    "seed_database",
]
