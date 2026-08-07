"""U8 bounded diagnostics tests (PLAN:440; KTD12 PLAN:197).

Covers: validator-keyword -> stable-code mapping; the never-emit guarantees
(no native messages, no instance values, no property names, no URI content,
no snippets, no secrets); count and serialized-size caps; field length caps;
guard-code mapping; vocabulary conformance to the closed enums in
registration-result.schema.json; output-shape conformance to the result
schema; and the canary no-echo corpus assertion (PLAN:440; spec:475-476).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from workstream_registration import conformance_runner as cr
from workstream_registration import diagnostics as diag
from workstream_registration import raw_guard as rg
from workstream_registration import validation as vd

CANARY_VALUES: tuple[str, ...] = (
    "wst_live_9f2k3LmN4pQr5sT6uV7wX8yZ1aB2cD",
    "ghp_J0kF2x9Qz8LmN4pR6sT7uV3wX5yZ2bC",
    "https://svc-account:fake-secret-token-9Xz2@records.example.org/projects/workstream-01",
    "ssh://deploy:sup3r-fake-secret@git.example.org/workstream-registration.git",
    "https://redacted:redacted-fake-secret@sharepoint.example.org/sites/records/workstream-02",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "AKIAFAKEKEYEXAMPLE01",
    "-----BEGIN PRIVATE KEY-----",
    "sk_fake_7O8x2P4mN9vQ0cW2eR5tY6uI8oP0aSd3",
)


@pytest.fixture(scope="module")
def root() -> Path:
    return cr.repo_root()


@pytest.fixture(scope="module")
def manifest_data(root: Path) -> dict:
    return cr.load_manifest(root / cr.MANIFEST_RELATIVE_PATH)


@pytest.fixture(scope="module")
def corpus(root: Path) -> Path:
    return root / "tests" / "contracts" / "workstream-registration"


def _err(
    message: str = "native message",
    validator: str = "required",
    path: tuple = (),
    validator_value: object = None,
    instance: object = None,
) -> ValidationError:
    return ValidationError(
        message=message,
        validator=validator,
        path=path,
        validator_value=validator_value,
        instance=instance,
        schema={},
    )


@pytest.mark.parametrize(
    "validator",
    [
        "required",
        "additionalProperties",
        "type",
        "enum",
        "const",
        "pattern",
        "maxLength",
        "minLength",
        "maxItems",
        "minItems",
        "uniqueItems",
        "allOf",
        "anyOf",
        "oneOf",
        "not",
        "if",
        "then",
        "minimum",
        "maximum",
    ],
)
def test_every_schema_keyword_maps_to_schema_invalid(validator: str) -> None:
    diagnostics = diag.normalize([_err(validator=validator)])
    assert diagnostics.count == 1
    item = diagnostics.items[0]
    assert item.phase == diag.PHASE_SCHEMA
    assert item.code == diag.CODE_SCHEMA_INVALID
    assert item.safe_path == diag.SAFE_PATH_MARKER
    assert item.label is None
    assert item.affected_local_path is None


def test_normalize_never_emits_message_instance_properties_or_uris() -> None:
    error = _err(
        message=f"native message with {CANARY_VALUES[0]} and {CANARY_VALUES[5]}",
        validator="pattern",
        validator_value=["record_sources", "uri", "label"],
        instance={
            "uri": "https://svc-account:fake-secret-token-9Xz2@records.example.org/x",
            "label": "-----BEGIN PRIVATE KEY-----",
        },
    )
    serialized = diag.normalize([error]).serialize()
    for value in CANARY_VALUES:
        assert value not in serialized
    payload = json.loads(serialized)
    assert set(payload) == {"count", "items"}
    assert set(payload["items"][0]) == {"phase", "code", "safe_path"}


def test_count_capped_at_32() -> None:
    errors = [_err(validator="type", path=(f"f{i}",)) for i in range(100)]
    diagnostics = diag.normalize(errors)
    assert diagnostics.count == 32
    assert len(diagnostics.items) == 32


def test_serialized_size_cap_with_max_length_fields() -> None:
    items = tuple(
        diag.Diagnostic(
            phase="operation",
            code=diag.CODE_READ_BACK_TARGET_MISMATCH,
            safe_path="s" * diag.MAX_SAFE_PATH_LENGTH,
            label="l" * diag.MAX_LABEL_LENGTH,
            affected_local_path="p" * diag.MAX_AFFECTED_LOCAL_PATH_LENGTH,
        )
        for _ in range(diag.MAX_DIAGNOSTIC_COUNT)
    )
    diagnostics = diag.Diagnostics(count=len(items), items=items)
    text = diagnostics.serialize()
    assert len(text.encode("utf-8")) <= diag.MAX_SERIALIZED_BYTES
    payload = json.loads(text)
    assert payload["count"] == len(payload["items"]) == 32
    for item in payload["items"]:
        assert len(item["safe_path"]) == diag.MAX_SAFE_PATH_LENGTH
        assert len(item["label"]) == diag.MAX_LABEL_LENGTH
        assert len(item["affected_local_path"]) == diag.MAX_AFFECTED_LOCAL_PATH_LENGTH


def test_field_length_caps_truncate() -> None:
    item = diag.Diagnostic(
        phase="operation",
        code=diag.CODE_SAFE_INTERNAL_ERROR,
        safe_path="z" * 300,
        label="x" * 3000,
        affected_local_path="y" * 5000,
    ).bounded()
    assert len(item.safe_path) == diag.MAX_SAFE_PATH_LENGTH
    assert len(item.label) == diag.MAX_LABEL_LENGTH
    assert len(item.affected_local_path) == diag.MAX_AFFECTED_LOCAL_PATH_LENGTH


@pytest.mark.parametrize(
    ("guard_phase", "guard_code", "expected_code"),
    [
        (rg.PHASE_READ, "READ_OVER_LIMIT", "READ_LIMIT"),
        (rg.PHASE_UTF8, "UTF8_BOM_PREFIX", "UTF8_INVALID"),
        (rg.PHASE_UTF8, "UTF8_DECODE_ERROR", "UTF8_INVALID"),
        (rg.PHASE_DEPTH, "DEPTH_EXCEEDED", "DEPTH_LIMIT"),
        (rg.PHASE_DUPLICATES, "DUPLICATE_NAME", "DUPLICATE_KEYS"),
        (rg.PHASE_NONFINITE, "NONFINITE_CONSTANT", "NON_FINITE"),
        (rg.PHASE_CONTROLS, "CONTROL_CHARACTER", "CONTROL_CHARACTER"),
    ],
)
def test_guard_codes_map_onto_result_vocabulary(
    guard_phase: str, guard_code: str, expected_code: str
) -> None:
    diagnostics = diag.from_guard_result(guard_phase, guard_code)
    assert diagnostics.count == 1
    assert diagnostics.items[0].phase == guard_phase
    assert diagnostics.items[0].code == expected_code


def test_unmapped_guard_code_collapses_to_schema_invalid() -> None:
    diagnostics = diag.from_guard_result("schema", None)
    assert diagnostics.items[0].code == diag.CODE_SCHEMA_INVALID


def test_vocabulary_matches_result_schema_closed_enums(root: Path) -> None:
    schema = json.loads(
        (root / vd.CONTRACTS_DIR / vd.RESULT_SCHEMA_NAME).read_text(encoding="utf-8")
    )
    schema_codes = schema["$defs"]["diagnostic"]["properties"]["code"]["enum"]
    schema_phases = schema["$defs"]["diagnostic"]["properties"]["phase"]["enum"]
    assert list(diag.CODES) == schema_codes
    assert list(diag.PHASES) == schema_phases
    assert len(schema_codes) == 29


def test_diagnostics_output_conforms_to_result_schema(root: Path) -> None:
    result_schema = json.loads(
        (root / vd.CONTRACTS_DIR / vd.RESULT_SCHEMA_NAME).read_text(encoding="utf-8")
    )
    diagnostics_schema = {
        "$id": result_schema["$id"],
        "$defs": result_schema["$defs"],
        "$ref": "#/$defs/diagnostics",
    }
    validator = Draft202012Validator(diagnostics_schema)
    errors = [_err(validator="type", path=(f"f{i}",)) for i in range(50)]
    payload = diag.normalize(errors).to_dict()
    assert list(validator.iter_errors(payload)) == []


def test_canary_no_echo_through_validate_and_normalize(
    manifest_data: dict, corpus: Path
) -> None:
    for entry in manifest_data["entries"]:
        canary_values: list[str] = []
        for group_name in entry.get("canaries", []):
            canary_values.extend(manifest_data["canaries"][group_name]["values"])
        if not canary_values:
            continue
        case = json.loads(
            (corpus / entry["fixture"]).read_text(encoding="utf-8")
        )
        assert case["kind"] == "parsed-value"
        payload = case["payload"]
        result = vd.validate_marker(payload)
        assert result.valid, entry["id"]
        serialized = result.diagnostics.serialize()
        for value in canary_values:
            assert value not in serialized, (entry["id"], value)


def test_canary_no_echo_when_diagnostics_are_produced(
    manifest_data: dict, corpus: Path
) -> None:
    for entry in manifest_data["entries"]:
        canary_values: list[str] = []
        for group_name in entry.get("canaries", []):
            canary_values.extend(manifest_data["canaries"][group_name]["values"])
        if not canary_values:
            continue
        case = json.loads((corpus / entry["fixture"]).read_text(encoding="utf-8"))
        payload = case["payload"]
        mutated = dict(payload)
        mutated.pop("identity", None)  # schema-invalid -> diagnostics produced
        result = vd.validate_marker(mutated)
        assert not result.valid, entry["id"]
        assert result.diagnostics.count >= 1, entry["id"]
        serialized = result.diagnostics.serialize()
        for value in canary_values:
            assert value not in serialized, (entry["id"], value)


def test_normalize_never_prints_or_logs_input(capsys) -> None:
    error = _err(message=CANARY_VALUES[0], instance={"uri": CANARY_VALUES[2]})
    diag.normalize([error]).serialize()
    vd.validate_marker({"version": 1})
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
