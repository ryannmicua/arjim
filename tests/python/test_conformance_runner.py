"""U6 scaffold tests: manifest load, validation, zero-cases report, exit codes."""

from __future__ import annotations

import importlib.util
import json
import platform
import tomllib
from collections import Counter
from pathlib import Path

import pytest

import workstream_registration
from workstream_registration import conformance_runner as cr

EXPECTED_ENTRIES = 87
EXPECTED_CATEGORIES = {"mandatory": 87, "capability": 0, "warning": 0}


@pytest.fixture(scope="module")
def root() -> Path:
    return cr.repo_root()


@pytest.fixture(scope="module")
def manifest_data(root: Path) -> dict:
    return cr.load_manifest(root / cr.MANIFEST_RELATIVE_PATH)


@pytest.fixture(scope="module")
def manifest_schema(root: Path) -> dict:
    return cr.load_bundled_schema(root / cr.EXPECTATIONS_SCHEMA_RELATIVE_PATH)


def test_manifest_load_reports_87_entries(manifest_data) -> None:
    assert len(manifest_data["entries"]) == EXPECTED_ENTRIES


def test_manifest_categories_are_all_mandatory(manifest_data) -> None:
    counts = Counter(entry["category"] for entry in manifest_data["entries"])
    for category in ("mandatory", "capability", "warning"):
        assert counts.get(category, 0) == EXPECTED_CATEGORIES[category]


def test_manifest_validation_passes(manifest_data, manifest_schema) -> None:
    assert cr.validate_manifest(manifest_data, manifest_schema) == []


def test_expectations_schema_refs_are_bundled_only(manifest_schema) -> None:
    refs: list[str] = []
    stack: list[object] = [manifest_schema]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                refs.append(ref)
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    assert refs, "schema carries no $ref to inspect"
    assert all(ref.startswith("#") for ref in refs), f"non-bundled refs: {refs}"


def test_summary_zero_executable_cases(manifest_data) -> None:
    summary = cr.summarize(manifest_data)
    assert summary["manifest_version"] == "1.0.0"
    assert summary["contract"] == "workstream-registration/v1"
    assert summary["entries"] == EXPECTED_ENTRIES
    assert summary["categories"] == EXPECTED_CATEGORIES
    assert summary["executable_cases"] == 0


def test_run_exit_code_zero() -> None:
    assert cr.run() == cr.EXIT_OK


def test_run_reports_87_entries_and_zero_cases(capsys) -> None:
    assert cr.run() == cr.EXIT_OK
    out = capsys.readouterr().out
    assert f"entries: {EXPECTED_ENTRIES}" in out
    assert "executable_cases: 0" in out
    assert "schema: ok" in out
    assert "sqlite3: ok" in out


def test_run_missing_manifest_is_nonzero(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv(cr.ENV_MANIFEST_PATH, str(tmp_path / "missing.json"))
    assert cr.run() == cr.EXIT_MANIFEST_ERROR
    assert "manifest not found" in capsys.readouterr().err


def test_run_without_sqlite3_fails_explicitly(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cr, "sqlite3_available", lambda: False)
    assert cr.run() == cr.EXIT_NO_SQLITE3
    assert "sqlite3" in capsys.readouterr().err


def test_sqlite3_available_on_this_host() -> None:
    if importlib.util.find_spec("sqlite3") is None:
        pytest.skip("this Python build lacks sqlite3")
    assert cr.sqlite3_available() is True


def test_system_info_reports_runtime() -> None:
    info = cr.system_info()
    major, minor = (int(p) for p in info["python"].split(".")[:2])
    assert (major, minor) >= (3, 14)
    assert info["jsonschema"] == "4.26.0"
    assert info["sqlite3"] is not None


def test_repo_root_discovery_finds_contracts(root) -> None:
    assert (root / cr.CONTRACTS_DIR).is_dir()
    assert (root / cr.MANIFEST_RELATIVE_PATH).is_file()


def test_manifest_path_env_override(tmp_path, monkeypatch) -> None:
    target = tmp_path / "custom.json"
    monkeypatch.setenv(cr.ENV_MANIFEST_PATH, str(target))
    assert cr.manifest_path(root) == target.resolve()


def test_manifest_path_default_is_repo_root_relative(root) -> None:
    assert cr.manifest_path(root) == (root / cr.MANIFEST_RELATIVE_PATH).resolve()


def test_pyproject_pins_match_plan(root) -> None:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["requires-python"] == ">=3.14,<3.15"
    assert data["project"]["dependencies"] == ["jsonschema==4.26.0"]


def test_pyproject_dev_extra_has_pytest(root) -> None:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["optional-dependencies"]["dev"] == ["pytest"]


def test_pytest_testpaths_point_at_tests_python(root) -> None:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests/python"]


def test_host_python_matches_pinned_line() -> None:
    major, minor = (int(p) for p in platform.python_version().split(".")[:2])
    assert (3, 14) <= (major, minor) < (3, 15)


def test_package_version_matches_pyproject(root) -> None:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert workstream_registration.__version__ == data["project"]["version"]


def test_contract_fixtures_are_not_python_tests(root) -> None:
    corpus = root / "tests" / "contracts" / "workstream-registration"
    assert corpus.is_dir()
    for fixture in corpus.rglob("*.json"):
        try:
            json.loads(fixture.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            pytest.fail(f"fixture is not valid JSON: {fixture}: {exc}")
