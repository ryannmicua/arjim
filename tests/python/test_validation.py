"""U8 bundled-schema validation tests (PLAN:440; KTD3, KTD5, KTD12).

Covers: valid direct/proxy markers; closed-object unknown properties;
unsupported-version dispatch; non-dict fail-closed input; non-bundled ``$ref``
fails closed without fetching; duplicate keys already guard-rejected; unusual,
user-info, and token-like URIs accepted and never inspected; format assertion
disabled by construction; result-envelope validation; and the PLAN:441 corpus
hook that runs every parsed-value fixture through
guard_decoded_text -> validate -> normalize and asserts the manifest-declared
result (per-fixture table).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from referencing.exceptions import Unresolvable

from workstream_registration import conformance_runner as cr
from workstream_registration import diagnostics as diag
from workstream_registration import raw_guard as rg
from workstream_registration import validation as vd

CODE_SCHEMA_INVALID = diag.CODE_SCHEMA_INVALID
CODE_UNSUPPORTED_VERSION = diag.CODE_UNSUPPORTED_VERSION


@pytest.fixture(scope="module")
def root() -> Path:
    return cr.repo_root()


@pytest.fixture(scope="module")
def manifest_data(root: Path) -> dict:
    return cr.load_manifest(root / cr.MANIFEST_RELATIVE_PATH)


@pytest.fixture(scope="module")
def corpus(root: Path) -> Path:
    return root / "tests" / "contracts" / "workstream-registration"


def _load_case(corpus: Path, fixture: str) -> dict:
    return json.loads((corpus / fixture).read_text(encoding="utf-8"))


def _marker(**overrides: object) -> dict:
    base: dict = {
        "version": 1,
        "identity": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "label": "boundary",
        "kind": "direct",
        "workspace": ".",
        "record_sources": [
            {"type": "example/records", "uri": "https://records.example.org/x"}
        ],
    }
    base.update(overrides)
    return base


def test_valid_direct_marker_passes(corpus: Path) -> None:
    payload = _load_case(corpus, "valid/ae1-new-workspace-marker.json")["payload"]
    result = vd.validate_marker(payload)
    assert result.valid
    assert result.validity == vd.VALIDITY_VALID
    assert result.phase == vd.PHASE_SCHEMA
    assert result.code is None
    assert result.diagnostics.count == 0


def test_valid_proxy_marker_passes(corpus: Path) -> None:
    payload = _load_case(corpus, "valid/ae3-proxy-marker.json")["payload"]
    assert vd.validate_marker(payload).valid


def test_closed_object_unknown_properties_fail(corpus: Path) -> None:
    payload = _load_case(corpus, "invalid/invalid-unknown-field.json")["payload"]
    result = vd.validate_marker(payload)
    assert not result.valid
    assert result.validity == vd.VALIDITY_INVALID
    assert result.code == CODE_SCHEMA_INVALID
    assert result.phase == vd.PHASE_SCHEMA
    assert result.diagnostics.count >= 1
    for item in result.diagnostics:
        assert item.code == CODE_SCHEMA_INVALID
        assert item.safe_path == diag.SAFE_PATH_MARKER


def test_unsupported_version_2_is_distinct_outcome(corpus: Path) -> None:
    payload = _load_case(corpus, "invalid/invalid-unsupported-version-2.json")["payload"]
    result = vd.validate_marker(payload)
    assert not result.valid
    assert result.code == CODE_UNSUPPORTED_VERSION
    assert result.diagnostics.items[0].code == CODE_UNSUPPORTED_VERSION
    assert result.diagnostics.count == 1


@pytest.mark.parametrize("version", ["1", 1.0, True, "2", [1], None])
def test_wrong_type_version_is_unsupported(version: object) -> None:
    result = vd.validate_marker(_marker(version=version))
    assert not result.valid
    assert result.code == CODE_UNSUPPORTED_VERSION


def test_missing_version_falls_to_closed_schema(corpus: Path) -> None:
    payload = _load_case(corpus, "invalid/invalid-missing-version.json")["payload"]
    result = vd.validate_marker(payload)
    assert not result.valid
    assert result.code == CODE_SCHEMA_INVALID


@pytest.mark.parametrize("data", [None, "not a dict", [], 3, 3.5, True])
def test_non_dict_input_fails_closed(data: object) -> None:
    for validate in (vd.validate_marker, vd.validate_result_envelope):
        result = validate(data)
        assert not result.valid
        assert result.code == CODE_SCHEMA_INVALID
        assert result.phase == vd.PHASE_SCHEMA
        assert result.diagnostics.count == 1
        assert len(result.diagnostics.serialize()) <= diag.MAX_SERIALIZED_BYTES


def _doctored_schema_with_external_ref() -> dict:
    schema = dict(vd.load_bundled_schema(vd.MARKER_SCHEMA_NAME))
    schema["properties"] = dict(schema["properties"])
    schema["properties"]["label"] = {
        "$ref": "https://example.org/not-bundled-schema.json#/$defs/label"
    }
    return schema


def test_non_bundled_ref_fails_closed_never_fetches(monkeypatch) -> None:
    doctored = _doctored_schema_with_external_ref()
    validator = vd._validator_for(doctored)
    with pytest.raises(Unresolvable):
        validator.validate(_marker())
    monkeypatch.setattr(vd, "load_bundled_schema", lambda name: doctored)
    result = vd.validate_marker(_marker())
    assert not result.valid
    assert result.code == CODE_SCHEMA_INVALID
    assert result.phase == vd.PHASE_SCHEMA
    assert result.diagnostics.count == 1
    assert result.diagnostics.items[0].safe_path == diag.SAFE_PATH_MARKER


def test_bundled_schemas_refs_are_internal_only() -> None:
    for name in (vd.MARKER_SCHEMA_NAME, vd.RESULT_SCHEMA_NAME):
        schema = vd.load_bundled_schema(name)
        stack: list[object] = [schema]
        refs: list[str] = []
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                ref = node.get("$ref")
                if isinstance(ref, str):
                    refs.append(ref)
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
        assert refs, name
        for ref in refs:
            assert ref.startswith("#/$defs/"), (name, ref)


def test_load_bundled_schema_returns_defensive_copy() -> None:
    for name in (vd.MARKER_SCHEMA_NAME, vd.RESULT_SCHEMA_NAME):
        first = vd.load_bundled_schema(name)
        assert "properties" in first
        original_properties = dict(first["properties"])
        first["properties"] = {"hacked": {"type": "string"}}
        second = vd.load_bundled_schema(name)
        assert second is not first
        assert second["properties"] == original_properties
        assert second["properties"] is not first["properties"]


def test_duplicate_keys_are_guard_rejected() -> None:
    text = '{"version":1,"version":2}'
    guard = rg.guard_decoded_text(text)
    assert guard.phase == rg.PHASE_DUPLICATES
    assert guard.code == "DUPLICATE_NAME"


@pytest.mark.parametrize(
    "uri",
    [
        "https://canary-user-1@records.example.invalid/stream",
        "https://svc-account:fake-secret-token-9Xz2@records.example.org/projects/workstream-01",
        "ssh://deploy:sup3r-fake-secret@git.example.org/workstream-registration.git",
        "https://redacted:redacted-fake-secret@sharepoint.example.org/sites/records/workstream-02",
        "https://s3.example.invalid/bucket-01?X-Amz-Credential=AKIAFAKEKEYEXAMPLE01",
        "https://vault.example.invalid/secret/sk_fake_7O8x2P4mN9vQ0cW2eR5tY6uI8oP0aSd3",
    ],
)
def test_unusual_userinfo_tokenlike_uris_validate(uri: str) -> None:
    result = vd.validate_marker(_marker(record_sources=[{"type": "open/typed", "uri": uri}]))
    assert result.valid
    assert result.diagnostics.count == 0


@pytest.mark.parametrize(
    "fixture",
    [
        "valid/canary-fake-token-1.json",
        "valid/canary-fake-token-2.json",
        "valid/canary-userinfo-uri-1.json",
        "valid/canary-userinfo-uri-2.json",
        "valid/canary-key-shaped-1.json",
        "valid/canary-key-shaped-2.json",
        "valid/instruction-like-label-remains-data.json",
        "valid/ae9-userinfo-uri-record-source.json",
    ],
)
def test_canary_and_instruction_like_fixtures_validate(corpus: Path, fixture: str) -> None:
    payload = _load_case(corpus, fixture)["payload"]
    assert vd.validate_marker(payload).valid


def test_format_assertion_disabled_by_construction() -> None:
    schema = {"type": "string", "format": "uri"}
    validator = vd._validator_for(schema)
    assert validator.format_checker is None
    errors = list(validator.iter_errors("not a uri at all"))
    assert errors == []


def test_result_envelope_valid_fixtures_pass(corpus: Path) -> None:
    for fixture in (
        "result-registered.json",
        "result-linked-existing.json",
        "result-occupied-invalid.json",
        "result-diagnostic-count-cap.json",
        "result-diagnostic-size-caps.json",
        "result-valid-with-warnings.json",
    ):
        payload = _load_case(corpus, f"transitions/{fixture}")["payload"]
        result = vd.validate_result_envelope(payload)
        assert result.valid, fixture
        assert result.diagnostics.count == 0, fixture


@pytest.mark.parametrize(
    "fixture",
    [
        "result-contradiction-invalid-promoted.json",
        "result-contradiction-unverified-identity.json",
        "result-contradiction-unregistered-write.json",
    ],
)
def test_result_envelope_contradictions_rejected(corpus: Path, fixture: str) -> None:
    payload = _load_case(corpus, f"transitions/{fixture}")["payload"]
    result = vd.validate_result_envelope(payload)
    assert not result.valid
    assert result.code == CODE_SCHEMA_INVALID
    assert result.phase == vd.PHASE_SCHEMA
    assert result.diagnostics.count >= 1


def _run_parsed_value_pipeline(
    manifest_data: dict,
    corpus: Path,
    entry: dict,
) -> dict:
    """guard_decoded_text -> validate -> normalize; returns produced outcomes."""
    case = _load_case(corpus, entry["fixture"])
    assert case["id"] == entry["id"]
    assert case["kind"] == "parsed-value"
    payload = case["payload"]
    text = json.dumps(payload)
    guard = rg.guard_decoded_text(text)
    is_result = entry["fixture"].startswith("transitions/result-")
    if not guard.passed:
        diagnostics = diag.from_guard_result(guard.phase, guard.code)
        return {
            "validity": vd.VALIDITY_INVALID,
            "phase": guard.phase,
            "code": diagnostics.items[0].code,
            "diagnostics": diagnostics,
            "is_result": is_result,
        }
    result = (
        vd.validate_result_envelope(payload) if is_result else vd.validate_marker(payload)
    )
    return {
        "validity": result.validity,
        "phase": result.phase,
        "code": result.code,
        "diagnostics": result.diagnostics,
        "is_result": is_result,
    }


def test_every_parsed_value_fixture_produces_declared_result(
    manifest_data: dict, root: Path, corpus: Path, capsys
) -> None:
    table: list[dict] = []
    mismatches: list[str] = []
    for entry in sorted(manifest_data["entries"], key=lambda e: e["id"]):
        case = _load_case(corpus, entry["fixture"])
        if case["kind"] != "parsed-value":
            continue
        produced = _run_parsed_value_pipeline(manifest_data, corpus, entry)
        declared = entry["expected"]
        mismatch: str | None = None
        if "validity" in declared:
            if declared["validity"] == "valid" and produced["validity"] != vd.VALIDITY_VALID:
                mismatch = (
                    f"{entry['id']}: declared validity {declared['validity']!r}, "
                    f"produced {produced['validity']!r} (code {produced['code']})"
                )
            elif (
                declared["validity"] == "invalid"
                and produced["validity"] != vd.VALIDITY_INVALID
            ):
                mismatch = (
                    f"{entry['id']}: declared validity {declared['validity']!r}, "
                    f"produced {produced['validity']!r}"
                )
            elif (
                declared["validity"] == "valid-with-warnings"
                and produced["validity"] != vd.VALIDITY_VALID
            ):
                # Warning category: the schema-valid class is required here;
                # warning emission is a later-unit capability (PLAN:362).
                mismatch = (
                    f"{entry['id']}: declared validity {declared['validity']!r}, "
                    f"produced {produced['validity']!r}"
                )
        if "phase" in declared and produced["phase"] != declared["phase"]:
            mismatch = (
                f"{entry['id']}: declared phase {declared['phase']!r}, "
                f"produced {produced['phase']!r}"
            )
        if produced["is_result"] and "outcome" in declared:
            if case["payload"]["outcome"] != declared["outcome"]:
                mismatch = (
                    f"{entry['id']}: declared outcome {declared['outcome']!r}, "
                    f"envelope outcome {case['payload']['outcome']!r}"
                )
        if (
            declared.get("validity") == "valid-with-warnings"
            and produced["is_result"]
        ):
            if case["payload"]["validity"] != "valid-with-warnings":
                mismatch = f"{entry['id']}: envelope validity not valid-with-warnings"
            elif case["payload"].get("warnings") != declared.get("warnings"):
                mismatch = f"{entry['id']}: envelope warnings mismatch"
        if mismatch is not None:
            mismatches.append(mismatch)
        canary_values: list[str] = []
        for group_name in entry.get("canaries", []):
            canary_values.extend(manifest_data["canaries"][group_name]["values"])
        for value in canary_values:
            assert value not in produced["diagnostics"].serialize(), entry["id"]
        for item in produced["diagnostics"]:
            assert item.phase in diag.PHASES, entry["id"]
            assert item.code in diag.CODES, entry["id"]
            assert len(item.safe_path) <= diag.MAX_SAFE_PATH_LENGTH, entry["id"]
        table.append(
            {
                "id": entry["id"],
                "surface": "result" if produced["is_result"] else "marker",
                "declared": declared.get("validity", "-"),
                "produced": produced["validity"],
                "phase": produced["phase"],
                "code": produced["code"] or "-",
                "count": produced["diagnostics"].count,
            }
        )
    print()
    print(
        f"{'id':<42}{'surface':<8}{'declared':<18}{'produced':<10}{'phase':<12}{'code':<28}{'count':>5}"
    )
    for row in table:
        print(
            f"{row['id']:<42}{row['surface']:<8}{row['declared']:<18}"
            f"{row['produced']:<10}{row['phase']:<12}{row['code']:<28}{row['count']:>5}"
        )
    assert len(table) == 78  # 18 valid + 17 invalid + 2 warn + 41 transitions
    assert mismatches == [], "\n".join(mismatches)
