"""U11 full-corpus conformance runner tests (PLAN:476; spec:247-251).

Keeps the U6 scaffold assertions that still hold (manifest load and
validation, bundled-only refs, sqlite3 capability, pyproject pins) and adds
the U11 full-corpus assertions: run() executes every mandatory fixture
exactly once and exits 0; a fault-injected fixture yields a non-zero exit;
the coverage report contains every R1-R15 and AE1-AE9 (REV:67); the
state-table assertion is green (REV:65); the grep blacklist is green
(REV:66); the canary tripwire fails on an injected canary (TS-TRUST).
"""

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

# PLAN:556 exit-code buckets asserted against cli.OUTCOME_EXIT_CODE (the
# runner and the CLI must never diverge).
EXPECTED_OUTCOME_EXIT = cr.EXPECTED_OUTCOME_EXIT


@pytest.fixture(scope="module")
def root() -> Path:
    return cr.repo_root()


@pytest.fixture(scope="module")
def manifest_data(root: Path) -> dict:
    return cr.load_manifest(root / cr.MANIFEST_RELATIVE_PATH)


@pytest.fixture(scope="module")
def manifest_schema(root: Path) -> dict:
    return cr.load_bundled_schema(root / cr.EXPECTATIONS_SCHEMA_RELATIVE_PATH)


@pytest.fixture(scope="module")
def corpus(root: Path) -> Path:
    return root / "tests" / "contracts" / "workstream-registration"


# -- U6 scaffold assertions that still hold ---------------------------------


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


def test_summary_reports_all_entries_executable(manifest_data) -> None:
    summary = cr.summarize(manifest_data)
    assert summary["manifest_version"] == "1.0.0"
    assert summary["contract"] == "workstream-registration/v1"
    assert summary["entries"] == EXPECTED_ENTRIES
    assert summary["categories"] == EXPECTED_CATEGORIES
    assert summary["executable_cases"] == EXPECTED_ENTRIES


def test_run_exit_code_zero() -> None:
    assert cr.run() == cr.EXIT_OK


def test_run_reports_full_corpus_execution(capsys) -> None:
    assert cr.run() == cr.EXIT_OK
    out = capsys.readouterr().out
    assert f"entries: {EXPECTED_ENTRIES}" in out
    assert "executed: 87 (mandatory=87 capability=0 warning=0)" in out
    assert "failures: 0" in out
    assert "conformance: PASS" in out
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
    assert data["project"]["dependencies"] == [
        "jsonschema==4.26.0",
        "referencing==0.37.0",
    ]


def test_pyproject_console_script_registered(root) -> None:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["scripts"] == {
        "workstream-registration": "workstream_registration.cli:main",
        "workstream-dispatch": "workstream_dispatch.cli:main",
    }


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


# -- U11 full-corpus assertions ---------------------------------------------


def test_full_corpus_executes_every_entry_exactly_once(root, manifest_data, corpus) -> None:
    """Gate G5 / PLAN:476: no inventory errors; every entry executed once."""
    assert cr.inventory_assertion(manifest_data, corpus) == []
    import tempfile

    with tempfile.TemporaryDirectory() as work:
        executed = {
            entry["id"]: cr.execute_entry(manifest_data, entry, corpus, Path(work))
            for entry in manifest_data["entries"]
        }
    assert len(executed) == EXPECTED_ENTRIES
    assert all(not report.get("errors") for report in executed.values()), [
        error
        for report in executed.values()
        for error in report.get("errors", [])
    ]


def test_fault_injected_fixture_yields_nonzero(monkeypatch, capsys) -> None:
    """A broken (fault-injected) fixture must fail the whole corpus run."""
    original_raw = cr.run_raw_case

    def broken_raw(case, entry) -> dict:
        report = original_raw(case, entry)
        if entry["id"] == "raw-oversize-input":
            report["errors"] = ["fault-injected failure"]
        return report

    monkeypatch.setattr(cr, "run_raw_case", broken_raw)
    assert cr.run() != cr.EXIT_OK
    captured = capsys.readouterr()
    assert "fault-injected failure" in captured.out + captured.err


def test_coverage_report_covers_all_r1_r15_and_ae1_ae9(root, manifest_data) -> None:
    """REV:67 / TS-D2/TS-D3: every R1-R15 and AE1-AE9 present."""
    report = cr.coverage_report(manifest_data)
    for requirement in (f"R{i}" for i in range(1, 16)):
        assert requirement in report, f"coverage report misses {requirement}"
    for acceptance in (f"AE{i}" for i in range(1, 10)):
        assert acceptance in report, f"coverage report misses {acceptance}"
    assert cr.coverage_gaps(root, manifest_data) == []


def test_state_table_assertion_green(root, manifest_data) -> None:
    """REV:65 / TS-G3: every fixture outcome exists in the machine-readable
    table with >= 1 outgoing transition or a terminal flag."""
    assert cr.state_table_assertion(root, manifest_data) == []


def test_grep_blacklist_green(root) -> None:
    """REV:66 / TS-D14: zero matches in the implementation change set."""
    assert cr.grep_blacklist(root) == []


def test_canary_scan_clean_output_passes(manifest_data) -> None:
    assert cr.canary_scan("clean output with no secrets\n", manifest_data) == []


def test_canary_tripwire_fails_on_injected_canary(manifest_data) -> None:
    """TS-TRUST: a canary value in a captured output surface is non-zero."""
    hits = cr.canary_scan(
        "some output containing wst_live_9f2k3LmN4pQr5sT6uV7wX8yZ1aB2cD now",
        manifest_data,
    )
    assert hits
    assert cr.canary_values(manifest_data)  # corpus defines concrete values


def test_cli_exit_table_matches_plan_556() -> None:
    """PLAN:556: the runner's expected table equals the CLI's live mapping."""
    from workstream_registration import cli

    assert set(cli.OUTCOME_EXIT_CODE) == set(EXPECTED_OUTCOME_EXIT)
    for outcome, expected in EXPECTED_OUTCOME_EXIT.items():
        assert cli.OUTCOME_EXIT_CODE[outcome] == expected, outcome


def test_runner_exit_code_table_is_complete() -> None:
    """The 12 frozen outcomes map to exit codes 0/2/3/4/5 exactly."""
    assert set(EXPECTED_OUTCOME_EXIT) == {
        "registered",
        "linked-existing",
        "cancelled",
        "stopped",
        "written-unverified",
        "registered-unlinked",
        "unregistered",
        "occupied-invalid",
        "invalid-marker-resolved",
        "invalid-deleted-unverified",
        "changed-marker-stopped",
        "conflict",
    }
    assert set(EXPECTED_OUTCOME_EXIT.values()) == {0, 2, 3, 4, 5}
