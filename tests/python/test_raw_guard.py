"""U7 raw-input guard tests (PLAN:428; KTD11 PLAN:196).

Covers the bounded pipeline boundaries, the full fixture-defined Bidi_Control
set, the F1-reconciled parsed-value routing, and the corpus hook that runs
every U5 raw-byte fixture and asserts its manifest-declared phase (PLAN:429).
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import pytest

from workstream_registration import conformance_runner as cr
from workstream_registration import raw_guard as rg

CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_-]{0,63}$")

MAX = rg.MAX_READ_BYTES
DEEP8 = b"[[[[[[[[0]]]]]]]]"
DEEP9 = b"[[[[[[[[[0]]]]]]]]]"


def _marker(label: str = "boundary", n_sources: int = 1, uri_len: int = 40) -> str:
    return json.dumps(
        {
            "version": 1,
            "identity": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "label": label,
            "kind": "direct",
            "workspace": ".",
            "record_sources": [
                {
                    "type": "example/records",
                    "uri": "https://records.example.org/" + "u" * (uri_len - 29),
                }
                for _ in range(n_sources)
            ],
        }
    )


def test_read_cap_262144_allowed() -> None:
    raw = b'{"a":"' + b"x" * (MAX - 8) + b'"}' 
    assert len(raw) == MAX
    result = rg.guard(raw)
    assert result.passed
    assert result.phase == rg.PHASE_SCHEMA


def test_read_cap_262145_rejected() -> None:
    raw = b'{"a":"' + b"x" * (MAX - 7) + b'"}' 
    assert len(raw) == MAX + 1
    result = rg.guard(raw)
    assert result.phase == rg.PHASE_READ
    assert result.code == "READ_OVER_LIMIT"


def test_oversized_rejected_before_any_scan() -> None:
    oversized = b"[" * 9 + b"0" + b"]" * 9
    raw = oversized + b" " * (MAX - len(oversized) + 1)
    assert len(raw) > MAX
    result = rg.guard(raw)
    assert result.phase == rg.PHASE_READ
    assert result.code == "READ_OVER_LIMIT"


def test_malformed_utf8_rejected() -> None:
    result = rg.guard(b'{"a":"' + b"\xff\xfe" + b'"}')
    assert result.phase == rg.PHASE_UTF8
    assert result.code == "UTF8_DECODE_ERROR"


def test_utf8_bom_prefix_rejected() -> None:
    raw = b"\xef\xbb\xbf" + _marker().encode("utf-8")
    result = rg.guard(raw)
    assert result.phase == rg.PHASE_UTF8
    assert result.code == "UTF8_BOM_PREFIX"


def test_utf16_bom_rejected() -> None:
    raw = b"\xff\xfe" + '{"a":1}'.encode("utf-16-le")
    result = rg.guard(raw)
    assert result.phase == rg.PHASE_UTF8
    assert result.code == "UTF8_BOM_PREFIX"


def test_utf16_be_bom_rejected() -> None:
    raw = b"\xfe\xff" + '{"a":1}'.encode("utf-16-be")
    result = rg.guard(raw)
    assert result.phase == rg.PHASE_UTF8


def test_utf32_bom_rejected() -> None:
    raw = b"\xff\xfe\x00\x00" + '{"a":1}'.encode("utf-32-le")
    result = rg.guard(raw)
    assert result.phase == rg.PHASE_UTF8


def test_utf32_be_bom_rejected() -> None:
    raw = b"\x00\x00\xfe\xff" + '{"a":1}'.encode("utf-32-be")
    result = rg.guard(raw)
    assert result.phase == rg.PHASE_UTF8


def test_depth_8_accepted() -> None:
    result = rg.guard(DEEP8)
    assert result.passed
    assert result.phase == rg.PHASE_SCHEMA


def test_depth_9_rejected() -> None:
    result = rg.guard(DEEP9)
    assert result.phase == rg.PHASE_DEPTH
    assert result.code == "DEPTH_EXCEEDED"


def test_brackets_inside_string_values_do_not_count() -> None:
    text = '{"a":"' + "[" * 20 + '" ,"b":"' + "]" * 20 + '"}'
    result = rg.guard(text.encode("utf-8"))
    assert result.passed


def test_brackets_inside_escaped_quotes_do_not_count() -> None:
    text = '{"a":"[\\"]"}'
    assert json.loads(text) == {"a": '["]'}
    result = rg.guard(text.encode("utf-8"))
    assert result.passed


def test_brackets_inside_names_do_not_count() -> None:
    text = '{"[[[[[[[[[[[[":1}'
    result = rg.guard(text.encode("utf-8"))
    assert result.passed


def test_root_duplicate_names_rejected() -> None:
    result = rg.guard(b'{"a":1,"a":2}')
    assert result.phase == rg.PHASE_DUPLICATES
    assert result.code == "DUPLICATE_NAME"


def test_nested_duplicate_names_rejected() -> None:
    result = rg.guard(b'{"o":{"a":1,"a":2},"b":3}')
    assert result.phase == rg.PHASE_DUPLICATES


def test_nan_rejected() -> None:
    result = rg.guard(b'{"a":NaN}')
    assert result.phase == rg.PHASE_NONFINITE
    assert result.code == "NONFINITE_CONSTANT"


def test_infinity_rejected() -> None:
    assert rg.guard(b'{"a":Infinity}').phase == rg.PHASE_NONFINITE


def test_negative_infinity_rejected() -> None:
    assert rg.guard(b'{"a":-Infinity}').phase == rg.PHASE_NONFINITE


def test_nan_in_string_is_data_not_constant() -> None:
    result = rg.guard(b'{"a":"NaN","b":"Infinity","c":"-Infinity"}')
    assert result.passed


def test_raw_control_byte_in_value_rejected() -> None:
    result = rg.guard(b'{"label":"a\x01b"}')
    assert result.phase == rg.PHASE_CONTROLS
    assert result.code == "CONTROL_CHARACTER"


def test_escaped_control_in_value_rejected() -> None:
    result = rg.guard(b'{"label":"a\\u0001b"}')
    assert result.phase == rg.PHASE_CONTROLS


def test_escaped_c1_control_in_value_rejected() -> None:
    result = rg.guard('{"label":"a\\u007fb"}'.encode("utf-8"))
    assert result.phase == rg.PHASE_CONTROLS


def test_control_in_name_rejected() -> None:
    result = rg.guard('{"a\\u0001b":1}'.encode("utf-8"))
    assert result.phase == rg.PHASE_CONTROLS


@pytest.mark.parametrize("cp", sorted(rg.BIDI_CONTROL_POINTS))
def test_every_fixture_defined_bidi_code_point_rejected(cp: int) -> None:
    payload = {"label": "a" + chr(cp) + "b"}
    escaped = rg.guard(json.dumps(payload).encode("utf-8"))
    assert escaped.phase == rg.PHASE_CONTROLS
    raw_bytes = rg.guard(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    assert raw_bytes.phase == rg.PHASE_CONTROLS


def test_field_boundaries_within_limits_pass() -> None:
    text = _marker(label="x" * 256, n_sources=1, uri_len=2048)
    result = rg.guard(text.encode("utf-8"))
    assert result.passed


def test_collection_boundaries_within_limits_pass() -> None:
    text = _marker(label="x" * 256, n_sources=32, uri_len=2048)
    result = rg.guard(text.encode("utf-8"))
    assert result.passed


def test_minimum_collection_passes() -> None:
    assert rg.guard(_marker(n_sources=1).encode("utf-8")).passed


def test_guard_decoded_text_controls_f1_routing() -> None:
    text = json.dumps(
        {
            "version": 1,
            "identity": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "label": "bad\u0001label",
            "kind": "direct",
            "workspace": ".",
            "record_sources": [
                {
                    "type": "example/records",
                    "uri": "https://records.example.invalid/ctrl-label",
                }
            ],
        }
    )
    result = rg.guard_decoded_text(text)
    assert result.phase == rg.PHASE_CONTROLS
    assert result.code == "CONTROL_CHARACTER"


def test_guard_decoded_text_clean_passes() -> None:
    assert rg.guard_decoded_text(_marker()).passed


def test_guard_decoded_text_depth_9_rejected() -> None:
    assert rg.guard_decoded_text(DEEP9.decode("utf-8")).phase == rg.PHASE_DEPTH


def test_guard_decoded_text_duplicates_rejected() -> None:
    assert rg.guard_decoded_text('{"a":1,"a":2}').phase == rg.PHASE_DUPLICATES


def test_guard_decoded_text_nonfinite_rejected() -> None:
    assert rg.guard_decoded_text('{"a":NaN}').phase == rg.PHASE_NONFINITE


def test_result_phases_and_codes_are_stable() -> None:
    for raw in (b"x" * (MAX + 1), b"\xff", DEEP9, b'{"a":1,"a":2}', b'{"a":NaN}'):
        result = rg.guard(raw)
        assert result.phase in rg.PHASES
        assert result.code is not None
        assert CODE_PATTERN.match(result.code)
    assert rg.guard(b"null").phase == rg.PHASE_SCHEMA
    assert rg.guard(b"null").code is None


def test_guard_never_echoes_input(capsys) -> None:
    rg.guard(b'{"label":"a\x01b"}')
    rg.guard_decoded_text('{"label":"a\\u0001b"}')
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.fixture(scope="module")
def root() -> Path:
    return cr.repo_root()


@pytest.fixture(scope="module")
def manifest_data(root: Path) -> dict:
    return cr.load_manifest(root / cr.MANIFEST_RELATIVE_PATH)


def _run_raw_corpus(manifest_data: dict, root: Path) -> list[dict]:
    table: list[dict] = []
    corpus = root / "tests" / "contracts" / "workstream-registration"
    for entry in sorted(manifest_data["entries"], key=lambda e: e["id"]):
        if not entry["fixture"].startswith("raw/"):
            continue
        case = json.loads((corpus / entry["fixture"]).read_text(encoding="utf-8"))
        assert case["id"] == entry["id"]
        raw = base64.b64decode(case["payload_base64"])
        result = rg.guard(raw)
        expected = entry["expected"]
        table.append(
            {
                "id": entry["id"],
                "bytes": len(raw),
                "declared": expected.get("phase"),
                "produced": result.phase,
                "code": result.code,
            }
        )
        assert result.phase == expected.get("phase"), entry["id"]
        if "code" in expected:
            assert result.code == expected["code"], entry["id"]
    return table


def test_every_raw_fixture_terminates_at_declared_phase(
    manifest_data: dict, root: Path, capsys
) -> None:
    table = _run_raw_corpus(manifest_data, root)
    print()
    print(f"{'id':<28}{'bytes':>9}  {'declared':<12}{'produced':<12}code")
    for row in table:
        print(
            f"{row['id']:<28}{row['bytes']:>9}  "
            f"{row['declared']:<12}{row['produced']:<12}{row['code']}"
        )
    assert len(table) == 9


def test_invalid_label_controls_payload_routes_to_controls(
    manifest_data: dict, root: Path
) -> None:
    corpus = root / "tests" / "contracts" / "workstream-registration"
    entry = next(
        e for e in manifest_data["entries"] if e["id"] == "invalid-label-controls"
    )
    case = json.loads((corpus / entry["fixture"]).read_text(encoding="utf-8"))
    text = json.dumps(case["payload"])
    result = rg.guard_decoded_text(text)
    assert entry["expected"]["phase"] == rg.PHASE_CONTROLS
    assert result.phase == rg.PHASE_CONTROLS
    assert result.code == "CONTROL_CHARACTER"
