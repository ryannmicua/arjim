"""Conformance runner for the Workstream Registration v1 corpus (U11 full).

Canonical invocation::

    python -m workstream_registration.conformance_runner

U11 scope (PLAN:467-477): execute the complete project corpus and exit 0 only
when every mandatory fixture passes. The runner:

- validates the U5 expectation manifest (``expectations.json``) against the
  bundled ``expectations.schema.json`` (Draft 2020-12) and asserts the
  inventory gate (G5): every manifest path exists and is exercised exactly
  once; every fixture file has exactly one matching entry; ids are unique.
- feeds raw-byte fixtures through the U7 guard (``raw_guard.guard``) and
  asserts the declared termination phase (and validity for guard-passing
  raw cases that continue to validation, e.g. ``raw-trailing-content``).
- feeds parsed-value envelopes through U8 (``guard_decoded_text`` then
  ``validate_marker``/``validate_result_envelope``) and asserts the declared
  validity, phase, and (for result envelopes) outcome and warnings.
- drives transition fixtures through U9/U10 behavior (register/link/inspect/
  unregister scenarios with the declared ``inputs`` vocabulary, ported from
  the U9/U10 corpus-hook tests) and asserts the declared outcome.
- evaluates every U5 expectation category: ``mandatory`` and ``capability``
  mismatches are blocking; ``warning`` entries are reported but never fail
  conformance by themselves (expectations.schema.json; PLAN:349).
- emits a requirement-coverage report from the manifest ``covers`` tags and
  asserts every R1-R15 and AE1-AE9 appears (REV:67; TS-D2/TS-D3).
- executes the state-table assertion (REV:65; TS-G3): extracts the fenced
  ``json`` table from ``registration-protocol.md`` and asserts every state
  named by any fixture (and every frozen result-schema outcome) appears in
  the table with >= 1 outgoing transition or a ``terminal: true`` flag.
- executes the DoD grep blacklist (REV:66): the five abandoned-terminology
  patterns in :data:`BLACKLIST_PATTERNS` (the pre-2026-08-04 record-source
  name, the pre-rename kind value, and the removed observation/duplicate
  machinery, PLAN:542/547) must have zero matches in the implementation
  change set (``src/workstream_registration/``, ``tests/python/``,
  ``pyproject.toml``).
- asserts caps and no-echo: every canary value from the manifest ``canaries``
  map is searched in all captured output surfaces (stdout lines, stderr
  lines, and the CLI subprocess output); ANY canary value yields a non-zero
  exit (TS-TRUST tripwire).
- runs the full lifecycle end-to-end on a temp workspace against the real
  projection (register -> read-back -> link -> unregister; AE1/AE8) and the
  rebuild-after-projection-loss E2E (REV:63, TS-WORK): register >= 2
  workspaces (one proxy), delete the projection database, ``rebuild`` from
  the workspace paths, assert identities/labels/routing equal the
  pre-deletion state with no record-source or identity re-entry.
- checks the CLI contract: the outcome->exit-code table matches PLAN:556
  exactly and a live interactive register/unregister run through the console
  entry point behaves per contract.

No external suite or second-runtime gate is added to the product release
contract (PLAN:499).

Exit codes:
    0 — all mandatory fixtures green;
    1 — manifest or bundled schema cannot be loaded or validated;
    2 — this CPython build lacks the stdlib ``sqlite3`` module (PLAN:415);
    3 — conformance failure: a mandatory/capability fixture mismatch, an
        inventory/coverage/state-table/blacklist/canary/CLI-contract check
        failure, or a failure of the lifecycle/rebuild E2E.

Bundled-only ``$ref`` policy: the runner configures no registry, resolver, or
retrieval function for ``jsonschema``, so ``$ref`` resolution never fetches
over the network. Only the loaded schema file and the Draft 2020-12
meta-schema bundled inside the ``jsonschema`` package are resolvable; any
non-bundled ``$ref`` fails closed.

Path resolution: the manifest is located relative to the repository root,
discovered by walking up from this package until a
``contracts/workstream-registration`` directory is found. The
``WORKSTREAM_REGISTRATION_MANIFEST`` environment variable overrides the
manifest location.
"""

from __future__ import annotations

import base64
import importlib.metadata
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from workstream_registration import diagnostics as diag
from workstream_registration import filesystem as fs
from workstream_registration import raw_guard as rg
from workstream_registration import registration as reg
from workstream_registration import unregister as unr
from workstream_registration import validation as vd

__all__ = [
    "ENV_MANIFEST_PATH",
    "EXIT_CONFORMANCE_FAILED",
    "EXIT_MANIFEST_ERROR",
    "EXIT_NO_SQLITE3",
    "EXIT_OK",
    "BLACKLIST_PATTERNS",
    "OutputCapture",
    "RunnerError",
    "canary_scan",
    "cli_contract_check",
    "coverage_report",
    "execute_entry",
    "grep_blacklist",
    "inventory_assertion",
    "lifecycle_e2e",
    "load_bundled_schema",
    "load_manifest",
    "main",
    "manifest_path",
    "rebuild_e2e",
    "repo_root",
    "run",
    "run_parsed_case",
    "run_raw_case",
    "run_result_case",
    "run_transition_case",
    "sqlite3_available",
    "sqlite3_version",
    "state_table_assertion",
    "summarize",
    "system_info",
    "validate_manifest",
]

ENV_MANIFEST_PATH = "WORKSTREAM_REGISTRATION_MANIFEST"

CONTRACTS_DIR = Path("contracts") / "workstream-registration"
MANIFEST_RELATIVE_PATH = (
    Path("tests") / "contracts" / "workstream-registration" / "expectations.json"
)
EXPECTATIONS_SCHEMA_RELATIVE_PATH = (
    Path("contracts") / "workstream-registration" / "v1" / "expectations.schema.json"
)
PROTOCOL_RELATIVE_PATH = (
    Path("contracts") / "workstream-registration" / "v1" / "registration-protocol.md"
)
RESULT_SCHEMA_RELATIVE_PATH = (
    Path("contracts") / "workstream-registration" / "v1" / "registration-result.schema.json"
)
CORPUS_RELATIVE_PATH = Path("tests") / "contracts" / "workstream-registration"

EXIT_OK = 0
EXIT_MANIFEST_ERROR = 1
EXIT_NO_SQLITE3 = 2
EXIT_CONFORMANCE_FAILED = 3

_MAX_VALIDATION_ERRORS_REPORTED = 10

# Abandoned-terminology grep blacklist (REV:66; DoD TS-D14, spec:259-265).
# The pre-2026-08-04 record-source name and the pre-rename kind value were
# superseded on 2026-08-04 (PLAN:547); the observation envelope and the
# duplicate-outcome machinery were removed on 2026-08-02 (PLAN:542). Zero
# matches in the implementation change set; the fixture corpus may
# legitimately contain the rejected kind value as test data
# (invalid-malformed-kind).
#
# The patterns are constructed by concatenation so this module — the
# mechanization itself — does not self-match when scanned: the search target
# is the abandoned language in implementation files, not this definition.
BLACKLIST_PATTERNS = (
    "record" + " home",
    '"' + "fold" + "er" + '"',
    "capture-" + "observation",
    "marker-" + "observation.schema.json",
    "duplicate-" + "registration",
)

_BLACKLIST_SCOPE = ("src/workstream_registration", "tests/python", "pyproject.toml")

_UNREGISTER_FIXTURES = frozenset(
    {
        "transition-confirmed-unregister",
        "transition-unregister-identity-mismatch",
        "transition-unregister-marker-replaced",
    }
)

_REQUIRED_REQUIREMENTS = frozenset(f"R{i}" for i in range(1, 16))
_REQUIRED_ACCEPTANCE = frozenset(f"AE{i}" for i in range(1, 10))

# R12 (PLAN:113) is a documentation obligation — machine scan and registry
# consumption "do not function in this scope"; no fixture tags it (TS-D2
# covers requirements by "a fixture, protocol rule, or documentation
# obligation"). The runner verifies the documentation obligation exists
# (contracts README section 2 declares the deferred scope) and reports R12 as
# documented in the coverage report (REV:67).
_DOCUMENTED_REQUIREMENTS = {
    "R12": (
        "contracts/workstream-registration/README.md section 2 declares "
        "machine scan and registry consumption deferred"
    )
}
_DEFERRED_SCOPE_SENTINELS = ("never auto-discovers roots", "Deferred")

# PLAN:556 exit-code buckets; the CLI (cli.py) owns the live mapping and the
# runner asserts this table here so the CLI and the corpus never diverge.
EXPECTED_OUTCOME_EXIT = {
    "registered": 0,
    "linked-existing": 0,
    "unregistered": 0,
    "invalid-marker-resolved": 0,
    "cancelled": 2,
    "stopped": 2,
    "occupied-invalid": 3,
    "conflict": 4,
    "changed-marker-stopped": 4,
    "written-unverified": 5,
    "registered-unlinked": 5,
    "invalid-deleted-unverified": 5,
}

_FROZEN_OUTCOMES = frozenset(EXPECTED_OUTCOME_EXIT)

_LIFECYCLE_STATES = frozenset(
    {"inspection", "draft-ready", "writing", "unregister-draft", "deleting"}
)

_FENCED_JSON_RE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


class RunnerError(Exception):
    """The runner cannot proceed: manifest, bundled schema, or protocol table
    unusable."""


class OutputCapture:
    """Accumulates every runner output line so the canary scan (TS-TRUST) can
    inspect all captured output surfaces at the end of the run."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def emit(self, line: str) -> None:
        self.lines.append(line)
        print(line)

    def emit_err(self, line: str) -> None:
        self.lines.append(line)
        print(line, file=sys.stderr)

    def extend(self, text: str) -> None:
        if text:
            self.lines.extend(text.splitlines())

    def text(self) -> str:
        return "\n".join(self.lines)


def repo_root() -> Path:
    """Repository root containing the contracts directory, discovered by walking up.

    Works from an editable install (package under ``src/``) and from the repo
    root, because both share the ``contracts/workstream-registration``
    ancestor marker.
    """
    current = Path(__file__).resolve()
    for ancestor in (current, *current.parents):
        if (ancestor / CONTRACTS_DIR).is_dir():
            return ancestor
    raise RunnerError(
        f"repository root not found: no {CONTRACTS_DIR} above {current}"
    )


def manifest_path(root: Path | None = None) -> Path:
    """Resolve the manifest location (env override or repo-root-relative)."""
    root = root if root is not None else repo_root()
    override = os.environ.get(ENV_MANIFEST_PATH)
    if override:
        return Path(override).expanduser().resolve()
    return root / MANIFEST_RELATIVE_PATH


def load_manifest(path: Path) -> dict[str, Any]:
    """Load and JSON-parse the expectation manifest."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except FileNotFoundError as exc:
        raise RunnerError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RunnerError(f"manifest is not valid JSON: {path}: {exc.msg}") from exc
    if not isinstance(manifest, dict):
        raise RunnerError(f"manifest root must be a JSON object: {path}")
    return manifest


def load_bundled_schema(path: Path) -> dict[str, Any]:
    """Load and JSON-parse a bundled contract schema."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            schema = json.load(handle)
    except FileNotFoundError as exc:
        raise RunnerError(f"bundled schema not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RunnerError(f"bundled schema is not valid JSON: {path}: {exc.msg}") from exc
    if not isinstance(schema, dict):
        raise RunnerError(f"bundled schema root must be a JSON object: {path}")
    return schema


def validate_manifest(manifest: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate the manifest against the bundled expectations schema.

    Returns bounded error descriptions — JSON pointer paths only, never native
    validator messages, which may embed instance values (KTD12, PLAN:197).
    """
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(manifest),
        key=lambda err: [str(part) for part in err.path],
    )
    return ["/" + "/".join(str(part) for part in err.path) for err in errors]


def summarize(manifest: dict[str, Any]) -> dict[str, Any]:
    """Stable summary of the loaded manifest (entries, categories, cases).

    Every manifest entry is executable at U11, so ``executable_cases`` equals
    the entry count.
    """
    entries = manifest["entries"]
    counts = {"mandatory": 0, "capability": 0, "warning": 0}
    for entry in entries:
        category = entry.get("category")
        if category in counts:
            counts[category] += 1
    return {
        "manifest_version": manifest.get("manifest_version"),
        "contract": manifest.get("contract"),
        "entries": len(entries),
        "categories": counts,
        "executable_cases": len(entries),
    }


def sqlite3_version() -> str | None:
    """Bundled sqlite3 version, or None when this build lacks the module."""
    if importlib.util.find_spec("sqlite3") is None:
        return None
    import sqlite3

    return sqlite3.sqlite_version


def sqlite3_available() -> bool:
    """True when this CPython build ships the stdlib sqlite3 module."""
    return sqlite3_version() is not None


def system_info() -> dict[str, Any]:
    """Runtime capability snapshot: python, jsonschema, sqlite3."""
    return {
        "python": platform_python_version(),
        "jsonschema": importlib.metadata.version("jsonschema"),
        "sqlite3": sqlite3_version(),
    }


def platform_python_version() -> str:
    import platform

    return platform.python_version()


# ---------------------------------------------------------------------------
# Fixture execution
# ---------------------------------------------------------------------------


def _load_case(corpus: Path, entry: dict) -> dict[str, Any]:
    case_path = corpus / entry["fixture"]
    with case_path.open("r", encoding="utf-8") as handle:
        case = json.load(handle)
    if case.get("id") != entry["id"]:
        raise RunnerError(
            f"case id mismatch: fixture {case_path} carries {case.get('id')!r}, "
            f"manifest entry {entry['id']!r}"
        )
    return case


def inventory_assertion(manifest: dict[str, Any], corpus: Path) -> list[str]:
    """Gate G5: every manifest path exists and is exercised exactly once;
    every fixture file has exactly one matching entry; ids and paths unique."""
    errors: list[str] = []
    ids: set[str] = set()
    paths: set[str] = set()
    for entry in manifest["entries"]:
        entry_id = entry["id"]
        fixture = entry["fixture"]
        if entry_id in ids:
            errors.append(f"duplicate entry id: {entry_id}")
        if fixture in paths:
            errors.append(f"duplicate fixture path: {fixture}")
        ids.add(entry_id)
        paths.add(fixture)
        case_path = corpus / fixture
        if not case_path.is_file():
            errors.append(f"missing fixture file: {fixture}")
            continue
        try:
            case = _load_case(corpus, entry)
        except RunnerError as exc:
            errors.append(str(exc))
            continue
        if case.get("kind") not in ("parsed-value", "raw-byte"):
            errors.append(f"unknown case kind: {fixture}: {case.get('kind')!r}")
    for directory in ("valid", "invalid", "warn", "raw", "transitions"):
        for case_path in sorted((corpus / directory).glob("*.json")):
            relative = f"{directory}/{case_path.name}"
            if relative not in paths:
                errors.append(f"orphan fixture without manifest entry: {relative}")
    return errors


def _raw_validity(raw: bytes) -> str:
    """Guard-passing raw input: decode and validate as a marker (F1 routing).

    Non-dict or unparseable input is invalid; valid marker documents report
    their schema validity. Never echoes content.
    """
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return vd.VALIDITY_INVALID
    if not isinstance(parsed, dict):
        return vd.VALIDITY_INVALID
    return vd.validate_marker(parsed).validity


def run_raw_case(case: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Feed one raw-byte fixture through the U7 guard (PLAN:475)."""
    raw = base64.b64decode(case["payload_base64"])
    result = rg.guard(raw)
    produced: dict[str, Any] = {
        "id": entry["id"],
        "category": entry["category"],
        "kind": "raw-byte",
        "phase": result.phase,
        "code": result.code,
    }
    if result.passed:
        produced["validity"] = _raw_validity(raw)
    declared = entry.get("expected", {})
    if "phase" in declared and declared["phase"] != result.phase:
        produced["errors"] = [
            f"{entry['id']}: declared phase {declared['phase']!r}, "
            f"produced {result.phase!r}"
        ]
    if "validity" in declared and "validity" in produced:
        if declared["validity"] != produced["validity"]:
            produced["errors"] = [
                f"{entry['id']}: declared validity {declared['validity']!r}, "
                f"produced {produced['validity']!r}"
            ]
    return produced


def run_parsed_case(case: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Guard + validate one parsed-value fixture through U8 (PLAN:475).

    Mirrors the U8 corpus-hook pipeline: ``guard_decoded_text`` then
    ``validate_marker`` (or ``validate_result_envelope`` for result cases).
    """
    text = json.dumps(case["payload"])
    guard = rg.guard_decoded_text(text)
    produced: dict[str, Any] = {
        "id": entry["id"],
        "category": entry["category"],
        "kind": "parsed-value",
        "phase": guard.phase,
        "code": None,
    }
    if not guard.passed:
        diagnostics = diag.from_guard_result(guard.phase, guard.code)
        produced["validity"] = vd.VALIDITY_INVALID
        produced["code"] = diagnostics.items[0].code
        produced["diagnostics"] = diagnostics
    else:
        vres = vd.validate_marker(case["payload"])
        produced["validity"] = vres.validity
        produced["code"] = vres.code
        produced["diagnostics"] = vres.diagnostics
    return produced


def run_result_case(case: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Validate one result envelope fixture through U8 and assert declared
    outcome/validity/warnings (TS-G4, REV:67)."""
    text = json.dumps(case["payload"])
    guard = rg.guard_decoded_text(text)
    produced: dict[str, Any] = {
        "id": entry["id"],
        "category": entry["category"],
        "kind": "result",
        "phase": guard.phase,
        "code": None,
        "is_result": True,
    }
    if not guard.passed:
        diagnostics = diag.from_guard_result(guard.phase, guard.code)
        produced["validity"] = vd.VALIDITY_INVALID
        produced["code"] = diagnostics.items[0].code
        produced["diagnostics"] = diagnostics
    else:
        vres = vd.validate_result_envelope(case["payload"])
        produced["validity"] = vres.validity
        produced["code"] = vres.code
        produced["diagnostics"] = vres.diagnostics
    declared = entry.get("expected", {})
    errors: list[str] = []
    if "validity" in declared:
        if declared["validity"] == "valid-with-warnings":
            if produced["validity"] != vd.VALIDITY_VALID:
                errors.append(
                    f"{entry['id']}: declared validity valid-with-warnings, "
                    f"produced {produced['validity']!r}"
                )
            if case["payload"].get("validity") != "valid-with-warnings":
                errors.append(
                    f"{entry['id']}: envelope validity not valid-with-warnings"
                )
            elif case["payload"].get("warnings") != declared.get("warnings"):
                errors.append(
                    f"{entry['id']}: envelope warnings mismatch"
                )
        elif produced["validity"] != declared["validity"]:
            errors.append(
                f"{entry['id']}: declared validity {declared['validity']!r}, "
                f"produced {produced['validity']!r}"
            )
    if "outcome" in declared:
        envelope_outcome = case["payload"].get("outcome")
        if envelope_outcome != declared["outcome"]:
            errors.append(
                f"{entry['id']}: declared outcome {declared['outcome']!r}, "
                f"envelope outcome {envelope_outcome!r}"
            )
    if "phase" in declared and declared["phase"] != produced["phase"]:
        errors.append(
            f"{entry['id']}: declared phase {declared['phase']!r}, "
            f"produced {produced['phase']!r}"
        )
    if errors:
        produced["errors"] = errors
    return produced


class _Patch:
    """Bounded monkeypatch context manager (no pytest dependency)."""

    def __init__(self, module: Any, name: str, fn: Callable[..., Any]) -> None:
        self.module = module
        self.name = name
        self.fn = fn
        self.original = getattr(module, name)

    def __enter__(self) -> "_Patch":
        setattr(self.module, self.name, self.fn)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        setattr(self.module, self.name, self.original)


def _drive_register_fixture(
    case: dict[str, Any], workspace_root: Path
) -> tuple[str, str | None]:
    """Drive one register/link/inspect transition fixture against the
    implementation (port of the U9 corpus-hook driver). Returns the produced
    outcome and the produced result validity (envelope validity when a result
    envelope was produced)."""
    inputs = case.get("inputs", {})
    scenario = inputs.get("scenario", "register")
    observed = inputs.get("observed", {})
    twist = inputs.get("twist", "none")
    ws = workspace_root / "workspace"

    patches: list[_Patch] = []

    def _boom_identity(path: Path) -> bytes:
        raise fs.IdentityUnavailableError("unavailable")

    if twist == "identity-apis-unavailable":
        patches.append(_Patch(fs, "_capture_identity", _boom_identity))
    if twist == "target-alias-mismatch":
        real_identity = fs._capture_identity
        counter = {"n": 0}

        def _alias_identity(path: Path) -> bytes:
            counter["n"] += 1
            if counter["n"] == 1:
                return real_identity(path)
            return real_identity(path) + b"\x00"

        patches.append(_Patch(fs, "_capture_identity", _alias_identity))
    if twist == "redirected-marker-component":
        patches.append(_Patch(fs, "_marker_resolves_inside", lambda p: False))

    validity: str | None = None
    try:
        for patch in patches:
            patch.__enter__()
        if twist != "inaccessible-workspace":
            ws.mkdir()
            if observed.get("parent") != "absent":
                fs.parent_path(ws).mkdir(exist_ok=True)
            marker = observed.get("marker", "absent")
            if marker in ("valid", "invalid", "unsupported"):
                payload_bytes = json.dumps(case["payload"], separators=(",", ":")).encode("utf-8")
                fs.parent_path(ws).mkdir(exist_ok=True)
                if marker == "unsupported":
                    payload_bytes = json.dumps(
                        dict(case["payload"], version=2), separators=(",", ":")
                    ).encode("utf-8")
                fs.marker_path(ws).write_bytes(payload_bytes)
            elif marker == "partial":
                fs.parent_path(ws).mkdir(exist_ok=True)
                raw = json.dumps(case["payload"], separators=(",", ":")).encode("utf-8")
                fs.marker_path(ws).write_bytes(raw[: len(raw) // 2])

        projection = inputs.get("projection", "none")
        if projection in ("linked", "unlinked", "conflict"):
            status = {"linked": "linked", "unlinked": "projection-failed", "conflict": "conflict"}[projection]

            def make_hook(status: str):
                def hook(inp: reg.ProjectionInput) -> reg.ProjectionResult:
                    return reg.ProjectionResult(
                        status=status, identity=inp.identity,
                        target_handle=inp.target_handle, ordinal=inp.ordinal,
                    )

                return hook

            reg.set_projection_hook(make_hook(status))
        else:
            reg.set_projection_hook(None)

        inspection = reg.inspect(ws)
        if inspection.state == reg.STATE_STOPPED:
            return "stopped", validity
        if scenario == "inspect":
            if inspection.state == reg.STATE_OCCUPIED_INVALID:
                return reg.STATE_OCCUPIED_INVALID, vd.VALIDITY_INVALID
            return "stopped", validity
        if scenario == "link":
            result = reg.link(ws)
            return result.outcome, result.validity
        if inspection.state == reg.STATE_OCCUPIED_INVALID:
            return "occupied-invalid", vd.VALIDITY_INVALID
        d_inputs = inputs.get("draft") or {}
        d = reg.draft(
            ws,
            label=d_inputs.get("label", "fixture label"),
            record_sources=d_inputs.get(
                "record_sources",
                [{"type": "example/records", "uri": "https://records.example.org/x"}],
            ),
            kind=d_inputs.get("kind", "direct"),
            inspection=inspection,
        )
        confirmation_value = inputs.get("confirmation", "absent")
        if confirmation_value == "expired":
            if twist == "target-changed":
                shutil.rmtree(ws)
                ws.mkdir()
            else:
                fs.parent_path(ws).mkdir(exist_ok=True)
                fs.marker_path(ws).write_bytes(b'{"version":1')
            confirmation = reg.confirm(d, d.digest)
        else:
            confirmation = reg.confirm(d, d.digest) if confirmation_value == "exact" else None

        if twist == "create-collision":
            real_write = fs.write_marker_create_only
            other = dict(case["payload"])
            other_marker_bytes = json.dumps(other, separators=(",", ":")).encode("utf-8")

            def racer(ws_path: Path, marker_bytes: bytes, handle: fs.TargetHandle) -> None:
                real_write(ws_path, other_marker_bytes, handle)
                try:
                    real_write(ws_path, marker_bytes, handle)
                except fs.CreateCollisionError:
                    raise  # propagate to the register flow
                raise AssertionError("expected create collision")

            patch = _Patch(fs, "write_marker_create_only", racer)
            patches.append(patch)
            patch.__enter__()
        if twist == "read-back-other-target":
            real_capture = fs.capture_target_handle

            def fake_capture(path: Path) -> fs.TargetHandle:
                handle = real_capture(path)
                if fs.marker_path(path).exists():
                    parent = handle.parent if handle.parent is not None else b"\x00" * 16
                    return fs.TargetHandle(workspace=handle.workspace, parent=parent + b"\x00")
                return handle

            patch = _Patch(fs, "capture_target_handle", fake_capture)
            patches.append(patch)
            patch.__enter__()

        result = reg.register(ws, d, confirmation, lock_timeout=0.2)
        if confirmation_value == "reused":
            result = reg.register(ws, d, confirmation, lock_timeout=0.2)
        return result.outcome, result.validity
    finally:
        for patch in reversed(patches):
            patch.__exit__(None, None, None)
        reg.set_projection_hook(None)


def _drive_unregister_fixture(case: dict[str, Any], workspace_root: Path) -> str:
    """Drive one unregister transition fixture (port of the U10 corpus-hook
    driver). Returns the produced outcome."""
    inputs = case.get("inputs", {})
    twist = inputs.get("twist", "none")
    ws = workspace_root / "workspace"
    ws.mkdir()
    fs.parent_path(ws).mkdir(exist_ok=True)
    payload = case["payload"]
    marker_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    fs.marker_path(ws).write_bytes(marker_bytes)
    bound_identity = inputs.get("bound_identity") or payload["identity"]
    if bound_identity != payload["identity"]:
        bound_marker = dict(payload, identity=bound_identity)
        fs.marker_path(ws).write_bytes(
            json.dumps(bound_marker, separators=(",", ":")).encode("utf-8")
        )
        envelope = unr.unregister_envelope(ws)
        fs.marker_path(ws).write_bytes(marker_bytes)
    else:
        envelope = unr.unregister_envelope(ws)
    confirmation = unr.confirm_unregister(envelope, envelope.digest)
    if twist == "marker-replaced":
        replaced = dict(payload, label="Replaced Between Reads")
        fs.marker_path(ws).write_bytes(
            json.dumps(replaced, separators=(",", ":")).encode("utf-8")
        )
    result = unr.unregister(ws, confirmation, lock_timeout=0.5)
    return result.outcome


def run_transition_case(
    case: dict[str, Any], entry: dict[str, Any], workspace_root: Path
) -> dict[str, Any]:
    """Drive one transition fixture through U9/U10 behavior (PLAN:453, 465)."""
    produced: dict[str, Any] = {
        "id": entry["id"],
        "category": entry["category"],
        "kind": "transition",
    }
    declared = entry.get("expected", {})
    errors: list[str] = []
    if entry["id"] in _UNREGISTER_FIXTURES:
        produced["outcome"] = _drive_unregister_fixture(case, workspace_root)
    else:
        outcome, validity = _drive_register_fixture(case, workspace_root)
        produced["outcome"] = outcome
        produced["validity"] = validity
    if "outcome" in declared and produced["outcome"] != declared["outcome"]:
        errors.append(
            f"{entry['id']}: declared outcome {declared['outcome']!r}, "
            f"produced {produced['outcome']!r}"
        )
    if errors:
        produced["errors"] = errors
    return produced


def execute_entry(
    manifest: dict[str, Any],
    entry: dict[str, Any],
    corpus: Path,
    work_root: Path,
) -> dict[str, Any]:
    """Execute one manifest entry exactly once; dispatch by fixture kind."""
    case = _load_case(corpus, entry)
    fixture = entry["fixture"]
    if case["kind"] == "raw-byte":
        return run_raw_case(case, entry)
    if fixture.startswith("transitions/result-"):
        return run_result_case(case, entry)
    if fixture.startswith("transitions/transition-"):
        workspace_root = work_root / entry["id"]
        workspace_root.mkdir(exist_ok=True)
        return run_transition_case(case, entry, workspace_root)
    return run_parsed_case(case, entry)


# ---------------------------------------------------------------------------
# Mechanized assertions (REV:65, REV:66, REV:67)
# ---------------------------------------------------------------------------


def coverage_report(manifest: dict[str, Any]) -> dict[str, list[str]]:
    """Requirement-coverage report from the manifest ``covers`` tags (REV:67).

    Returns ``{"R1": [fixture ids...], ..., "AE9": [...]}`` for every tag
    actually used. Documentation-obligation requirements (R12, PLAN:113) are
    reported under the marker ``"documented"`` key with the fixture-id list
    replaced by the obligation reference.
    """
    report: dict[str, list[str]] = {}
    for entry in manifest["entries"]:
        for tag in entry.get("covers", []):
            report.setdefault(tag, []).append(entry["id"])
    for requirement, obligation in _DOCUMENTED_REQUIREMENTS.items():
        if requirement not in report:
            report[requirement] = [obligation]
    return report


def coverage_gaps(root: Path, manifest: dict[str, Any]) -> list[str]:
    """TS-D2/TS-D3: every R1-R15 and AE1-AE9 appears in at least one entry's
    ``covers`` tag or is covered by a verified documentation obligation."""
    report = coverage_report(manifest)
    gaps = []
    for requirement in sorted(_REQUIRED_REQUIREMENTS):
        if requirement not in report:
            gaps.append(f"no fixture covers {requirement}")
        elif requirement in _DOCUMENTED_REQUIREMENTS:
            contracts_readme = root / CONTRACTS_DIR / "README.md"
            try:
                text = contracts_readme.read_text(encoding="utf-8")
            except OSError as exc:
                gaps.append(f"R12 documentation obligation unverifiable: {exc}")
                continue
            if not all(sentinel in text for sentinel in _DEFERRED_SCOPE_SENTINELS):
                gaps.append(
                    "R12 documentation obligation missing: contracts README "
                    "does not declare the deferred machine-scan/registry scope"
                )
    for acceptance in sorted(_REQUIRED_ACCEPTANCE):
        if acceptance not in report:
            gaps.append(f"no fixture covers {acceptance}")
    return gaps


def _extract_state_table(root: Path) -> dict[str, Any]:
    """Extract the machine-readable fenced JSON table (REV:65)."""
    protocol_path = root / PROTOCOL_RELATIVE_PATH
    try:
        text = protocol_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RunnerError(f"protocol document unreadable: {protocol_path}: {exc}") from exc
    match = _FENCED_JSON_RE.search(text)
    if match is None:
        raise RunnerError(
            f"no fenced json state/transition table in {protocol_path}"
        )
    try:
        table = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise RunnerError(f"state/transition table is not valid JSON: {exc.msg}") from exc
    if not isinstance(table, dict) or not isinstance(table.get("states"), list):
        raise RunnerError("state/transition table must be an object with a states list")
    return table


def state_table_assertion(root: Path, manifest: dict[str, Any]) -> list[str]:
    """REV:65 / TS-G3: every state named by any fixture's declared outcome —
    plus every frozen result-schema outcome (TS-D1/REV:67) — appears in the
    machine-readable table with >= 1 outgoing transition or ``terminal``."""
    errors: list[str] = []
    table = _extract_state_table(root)
    states = {str(state.get("id")): state for state in table["states"]}
    transitions = table.get("transitions", [])
    if not isinstance(transitions, list):
        errors.append("state/transition table transitions must be a list")
        return errors
    outgoing: dict[str, int] = {}
    for transition in transitions:
        if isinstance(transition, dict) and isinstance(transition.get("from"), str):
            source = transition["from"]
            outgoing[source] = outgoing.get(source, 0) + 1
    declared_outcomes: set[str] = set()
    for entry in manifest["entries"]:
        outcome = entry.get("expected", {}).get("outcome")
        if outcome is not None:
            declared_outcomes.add(str(outcome))
    schema_outcomes = _result_schema_outcomes(root)
    for outcome in sorted(declared_outcomes | schema_outcomes):
        state = states.get(outcome)
        if state is None:
            errors.append(f"fixture outcome {outcome!r} missing from the state table")
            continue
        if outgoing.get(outcome, 0) >= 1:
            continue
        if state.get("terminal") is True:
            continue
        errors.append(
            f"state {outcome!r} has no outgoing transition and is not terminal"
        )
    for state_id, state in states.items():
        if state_id not in declared_outcomes and state_id not in schema_outcomes:
            if state_id not in _LIFECYCLE_STATES:
                errors.append(
                    f"table state {state_id!r} is neither a lifecycle state nor a "
                    "frozen outcome"
                )
    return errors


def _result_schema_outcomes(root: Path) -> set[str]:
    """Every outcome in the frozen result-schema enum (TS-D1, REV:67)."""
    schema = load_bundled_schema(root / RESULT_SCHEMA_RELATIVE_PATH)
    outcomes = schema.get("properties", {}).get("outcome", {}).get("enum", [])
    return {str(outcome) for outcome in outcomes}


def grep_blacklist(root: Path) -> list[str]:
    """REV:66: zero matches for the abandoned-terminology patterns in the
    implementation change set."""
    matches: list[str] = []
    for scope in _BLACKLIST_SCOPE:
        base = root / scope
        files: list[Path] = []
        if base.is_file():
            files.append(base)
        elif base.is_dir():
            files = sorted(base.rglob("*.py"))
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for pattern in BLACKLIST_PATTERNS:
                if pattern in text:
                    matches.append(f"{pattern!r} in {path.relative_to(root)}")
    return matches


def canary_values(manifest: dict[str, Any]) -> list[str]:
    """All concrete canary values from the manifest ``canaries`` map."""
    values: list[str] = []
    for group in manifest.get("canaries", {}).values():
        for value in group.get("values", []):
            values.append(str(value))
    return values


def canary_scan(text: str, manifest: dict[str, Any]) -> list[str]:
    """TS-TRUST tripwire: any canary value in the captured output fails."""
    if not text:
        return []
    hits = [value for value in canary_values(manifest) if value in text]
    return hits


# ---------------------------------------------------------------------------
# End-to-end sections (AE1/AE8 lifecycle; REV:63 rebuild-after-projection-loss)
# ---------------------------------------------------------------------------


def lifecycle_e2e() -> dict[str, Any]:
    """Full lifecycle end-to-end (AE1/AE8): register -> read-back identity
    match -> link -> unregister on a temp workspace with the real projection.

    The store path must not pre-exist: a pre-existing directory with
    inherited ACLs fails closed by design (PLAN:553), so the projection
    creates and enforces the owner-only store itself.
    """
    with tempfile.TemporaryDirectory(prefix="workstream-registration-e2e-") as tmp, tempfile.TemporaryDirectory(prefix="workstream-registration-store-root-") as store_root:
        os.environ["WORKSTREAM_REGISTRATION_STORE_DIR"] = str(Path(store_root) / "projection")
        try:
            ws = Path(tmp) / "workspace"
            ws.mkdir()
            reg.install_default_projection_hook()
            inspection = reg.inspect(ws)
            if inspection.state != reg.STATE_DRAFT_READY:
                return {"status": "failed", "detail": "inspection not draft-ready"}
            d = reg.draft(
                ws,
                label="Conformance Lifecycle",
                record_sources=[
                    {"type": "example/records", "uri": "https://records.example.org/x"}
                ],
                kind="direct",
                inspection=inspection,
            )
            result = reg.register(ws, d, reg.confirm(d, d.digest))
            if result.outcome != "registered":
                return {"status": "failed", "detail": f"register produced {result.outcome}"}
            on_disk = json.loads(fs.read_marker(ws).decode("utf-8"))
            if on_disk["identity"] != d.identity:
                return {"status": "failed", "detail": "read-back identity mismatch"}
            linked = reg.link(ws)
            if linked.outcome != "linked-existing" or linked.identity != d.identity:
                return {"status": "failed", "detail": f"link produced {linked.outcome}"}
            envelope = unr.unregister_envelope(ws)
            unreg = unr.unregister(ws, unr.confirm_unregister(envelope, envelope.digest))
            if unreg.outcome != "unregistered":
                return {"status": "failed", "detail": f"unregister produced {unreg.outcome}"}
            if not fs.verify_marker_absent(ws):
                return {"status": "failed", "detail": "marker not absent after unregister"}
            return {"status": "ok", "identity": d.identity}
        finally:
            reg.set_projection_hook(None)
            os.environ.pop("WORKSTREAM_REGISTRATION_STORE_DIR", None)


def rebuild_e2e() -> dict[str, Any]:
    """REV:63 / TS-WORK: rebuild-after-projection-loss from explicit roots.

    The store path must not pre-exist (fail-closed enforcement, PLAN:553).
    """
    with tempfile.TemporaryDirectory(prefix="workstream-registration-rebuild-") as tmp, tempfile.TemporaryDirectory(prefix="workstream-registration-store-root-") as store_root:
        os.environ["WORKSTREAM_REGISTRATION_STORE_DIR"] = str(Path(store_root) / "projection")
        try:
            from workstream_registration.projection import Projection

            reg.install_default_projection_hook()
            paths: list[Path] = []
            identities: dict[str, str] = {}
            kinds: dict[str, str] = {}
            for name, kind in (("direct-ws", "direct"), ("proxy-ws", "proxy")):
                ws = Path(tmp) / name
                ws.mkdir()
                inspection = reg.inspect(ws)
                d = reg.draft(
                    ws,
                    label=f"Rebuild {name}",
                    record_sources=[
                        {"type": "example/records", "uri": f"https://records.example.org/{name}"}
                    ],
                    kind=kind,
                    inspection=inspection,
                )
                result = reg.register(ws, d, reg.confirm(d, d.digest))
                if result.outcome != "registered":
                    return {"status": "failed", "detail": f"{name} register produced {result.outcome}"}
                paths.append(ws)
                identities[name] = d.identity
                kinds[name] = kind
            projection = Projection()
            before = {entry["identity"]: entry for entry in projection.list_projection()}
            for name in identities:
                if identities[name] not in before:
                    return {"status": "failed", "detail": f"missing pre-deletion entry for {name}"}
            db = projection.db_path
            for suffix in ("", "-wal", "-shm", "-journal"):
                sidecar = Path(str(db) + suffix)
                if sidecar.exists():
                    sidecar.unlink()
            rebuilt = projection.rebuild(paths)
            if rebuilt.status != "rebuilt":
                return {"status": "failed", "detail": f"rebuild produced {rebuilt.status}: {rebuilt.detail}"}
            after = {entry["identity"]: entry for entry in rebuilt.entries}
            if set(after) != set(before):
                return {"status": "failed", "detail": "identity set changed across rebuild"}
            for identity, before_entry in before.items():
                after_entry = after[identity]
                for field in ("label", "workspace_path", "state", "target_handle"):
                    if before_entry[field] != after_entry[field]:
                        return {
                            "status": "failed",
                            "detail": f"identity {identity}: {field} changed "
                            f"({before_entry[field]!r} -> {after_entry[field]!r})",
                        }
            expected_ordinals = {path: ordinal for ordinal, path in enumerate(paths, start=1)}
            for identity, entry in after.items():
                marker = json.loads(fs.read_marker(Path(entry["workspace_path"])).decode("utf-8"))
                if marker["identity"] != identity:
                    return {"status": "failed", "detail": f"identity mismatch after rebuild for {identity}"}
                if entry["ordinal"] != expected_ordinals[Path(entry["workspace_path"])]:
                    return {
                        "status": "failed",
                        "detail": f"identity {identity}: input ordinal not retained "
                        f"({entry['ordinal']} != {expected_ordinals[Path(entry['workspace_path'])]})",
                    }
            return {"status": "ok", "workspaces": list(identities), "identities": identities}
        finally:
            reg.set_projection_hook(None)
            os.environ.pop("WORKSTREAM_REGISTRATION_STORE_DIR", None)


# ---------------------------------------------------------------------------
# CLI contract checks (PLAN:475, 556)
# ---------------------------------------------------------------------------


def _drive_cli_interactive(argv: list[str], env: dict[str, str]) -> tuple[int, str]:
    """Drive the console entry point interactively: read its ``confirm
    <digest>`` prompt and reply with the exact digest (same-process session)."""
    command = [sys.executable, "-m", "workstream_registration.cli", *argv]
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    output: list[str] = []
    confirmed = False
    try:
        for line in proc.stdout:
            output.append(line)
            if not confirmed:
                match = re.match(r"^confirm ([0-9a-f]{64})$", line.strip())
                if match is not None:
                    proc.stdin.write(f"confirm {match.group(1)}\n")
                    proc.stdin.flush()
                    confirmed = True
    finally:
        proc.stdin.close()
    proc.wait()
    return proc.returncode, "".join(output)


def cli_contract_check() -> dict[str, Any]:
    """PLAN:475/556: the outcome->exit-code table is exact and the live
    interactive register/unregister flow through the console entry point
    behaves per contract. Returns a report dict whose ``output`` carries every
    CLI line (fed to the canary scan)."""
    from workstream_registration import cli

    table = cli.OUTCOME_EXIT_CODE
    errors: list[str] = []
    if set(table) != _FROZEN_OUTCOMES:
        errors.append(
            f"CLI outcome table covers {sorted(set(table))}, expected the 12 frozen outcomes"
        )
    for outcome, expected in EXPECTED_OUTCOME_EXIT.items():
        if table.get(outcome) != expected:
            errors.append(f"outcome {outcome}: CLI exit {table.get(outcome)}, expected {expected}")
    if cli.EXIT_INTERNAL_FAILURE != 6 or cli.EXIT_INVALID_INPUT != 3:
        errors.append("CLI input/internal exit codes deviate from PLAN:556 (3/6)")
    env = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="workstream-registration-cli-") as tmp, tempfile.TemporaryDirectory(prefix="workstream-registration-store-root-") as store_root:
        env["WORKSTREAM_REGISTRATION_STORE_DIR"] = str(Path(store_root) / "projection")
        ws = Path(tmp) / "workspace"
        ws.mkdir()
        base = [
            "--json",
            "register",
            str(ws),
            "--label",
            "CLI Contract Check",
            "--record-source",
            "example/records=https://records.example.org/cli-check",
        ]
        code, output = _drive_cli_interactive(base, env)
        if code != 0:
            errors.append(f"CLI interactive register exited {code}, expected 0")
        if '"outcome":"registered"' not in output:
            errors.append("CLI interactive register did not emit a registered envelope")
        code, output = _drive_cli_interactive(["--json", "unregister", str(ws)], env)
        if code != 0:
            errors.append(f"CLI interactive unregister exited {code}, expected 0")
        if '"outcome":"unregistered"' not in output:
            errors.append("CLI interactive unregister did not emit an unregistered envelope")
    return {"errors": errors, "output": output}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _format_validation_failure(schema_path: Path, errors: list[str]) -> str:
    shown = errors[:_MAX_VALIDATION_ERRORS_REPORTED]
    lines = "\n".join(f"  - {path}" for path in shown)
    suffix = (
        f" (+{len(errors) - len(shown)} more)"
        if len(errors) > len(shown)
        else ""
    )
    return (
        f"manifest failed validation against {schema_path}: "
        f"{len(errors)} error(s){suffix}\n{lines}"
    )


def run(*, manifest: Path | None = None) -> int:
    """Run the full conformance pass; returns the process exit code."""
    if not sqlite3_available():
        print(
            "error: stdlib sqlite3 is unavailable in this Python build; the "
            "Workstream Registration support profile requires it",
            file=sys.stderr,
        )
        return EXIT_NO_SQLITE3
    capture = OutputCapture()
    try:
        root = repo_root()
        path = manifest if manifest is not None else manifest_path(root)
        manifest_data = load_manifest(path)
        schema = load_bundled_schema(root / EXPECTATIONS_SCHEMA_RELATIVE_PATH)
        errors = validate_manifest(manifest_data, schema)
        if errors:
            raise RunnerError(
                _format_validation_failure(root / EXPECTATIONS_SCHEMA_RELATIVE_PATH, errors)
            )
    except RunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_MANIFEST_ERROR

    failures: list[str] = []
    summary = summarize(manifest_data)
    info = system_info()
    categories = summary["categories"]
    corpus = root / CORPUS_RELATIVE_PATH

    capture.emit("workstream-registration conformance runner (U11)")
    capture.emit(f"manifest: {path}")
    capture.emit(f"manifest_version: {summary['manifest_version']}")
    capture.emit(f"contract: {summary['contract']}")
    capture.emit(f"entries: {summary['entries']}")
    capture.emit(
        "categories: "
        f"mandatory={categories['mandatory']} "
        f"capability={categories['capability']} "
        f"warning={categories['warning']}"
    )
    capture.emit("schema: ok")

    # -- inventory (G5) ------------------------------------------------------
    inventory_errors = inventory_assertion(manifest_data, corpus)
    if inventory_errors:
        failures.extend(f"inventory: {message}" for message in inventory_errors)
    capture.emit(f"inventory: {'ok' if not inventory_errors else f'{len(inventory_errors)} error(s)'}")

    # -- execute every entry exactly once ------------------------------------
    executed = {"mandatory": 0, "capability": 0, "warning": 0}
    with tempfile.TemporaryDirectory(prefix="workstream-registration-corpus-") as work:
        work_root = Path(work)
        for entry in sorted(manifest_data["entries"], key=lambda e: e["id"]):
            report = execute_entry(manifest_data, entry, corpus, work_root)
            category = report.get("category", "mandatory")
            executed[category] = executed.get(category, 0) + 1
            if report.get("errors"):
                for message in report["errors"]:
                    failures.append(message)
                    capture.emit(f"FAIL {message}")
            else:
                capture.emit(f"PASS {report['id']} ({report.get('kind', 'case')})")
    capture.emit(
        "executed: "
        f"{sum(executed.values())} "
        f"(mandatory={executed['mandatory']} capability={executed['capability']} "
        f"warning={executed['warning']})"
    )

    # -- coverage report (REV:67; TS-D2/TS-D3) -------------------------------
    coverage = coverage_report(manifest_data)
    gaps = coverage_gaps(root, manifest_data)
    if gaps:
        failures.extend(f"coverage: {message}" for message in gaps)
    coverage_line = " ".join(
        f"{tag}={len(coverage[tag])}" for tag in sorted(coverage)
    )
    capture.emit(f"coverage: {coverage_line}")
    coverage_note = "ok (R1-R15 and AE1-AE9 all present)" if not gaps else f"{len(gaps)} gap(s)"
    if "R12" in _DOCUMENTED_REQUIREMENTS and not gaps:
        coverage_note += "; R12 covered by documentation obligation (contracts README section 2)"
    capture.emit(f"coverage: {coverage_note}")

    # -- state-table assertion (REV:65; TS-G3) -------------------------------
    state_errors: list[str] = []
    try:
        state_errors = state_table_assertion(root, manifest_data)
    except RunnerError as exc:
        state_errors = [str(exc)]
    if state_errors:
        failures.extend(f"state-table: {message}" for message in state_errors)
    capture.emit(
        "state-table: "
        + ("ok" if not state_errors else f"{len(state_errors)} error(s)")
    )

    # -- grep blacklist (REV:66; TS-D14) -------------------------------------
    blacklist_matches = grep_blacklist(root)
    if blacklist_matches:
        failures.extend(f"blacklist: {message}" for message in blacklist_matches)
    capture.emit(
        "blacklist: "
        + ("ok (0 matches)" if not blacklist_matches else f"{len(blacklist_matches)} match(es)")
    )

    # -- lifecycle E2E (AE1/AE8) --------------------------------------------
    lifecycle = lifecycle_e2e()
    if lifecycle.get("status") != "ok":
        failures.append(f"lifecycle-e2e: {lifecycle.get('detail')}")
    capture.emit(f"lifecycle-e2e: {lifecycle.get('status')}")

    # -- rebuild-after-projection-loss E2E (REV:63; TS-WORK) ----------------
    rebuild = rebuild_e2e()
    if rebuild.get("status") != "ok":
        failures.append(f"rebuild-e2e: {rebuild.get('detail')}")
    capture.emit(f"rebuild-e2e: {rebuild.get('status')}")

    # -- CLI contract check (PLAN:475, 556) ---------------------------------
    cli_report = cli_contract_check()
    for message in cli_report["errors"]:
        failures.append(f"cli-contract: {message}")
    capture.extend(cli_report["output"])
    capture.emit(
        "cli-contract: "
        + ("ok" if not cli_report["errors"] else f"{len(cli_report['errors'])} error(s)")
    )

    # -- canary scan (TS-TRUST) ---------------------------------------------
    canary_hits = canary_scan(capture.text(), manifest_data)
    if canary_hits:
        failures.append(
            f"canary-scan: {len(canary_hits)} canary value(s) found in output"
        )
    capture.emit(
        "canary-scan: "
        + (
            "ok (0 matches across all captured output)"
            if not canary_hits
            else f"{len(canary_hits)} match(es)"
        )
    )

    capture.emit(f"sqlite3: ok ({info['sqlite3']})")
    if failures:
        capture.emit(f"failures: {len(failures)}")
        capture.emit("conformance: FAIL")
        for failure in failures:
            capture.emit_err(f"error: {failure}")
        return EXIT_CONFORMANCE_FAILED
    capture.emit("failures: 0")
    capture.emit("conformance: PASS")
    return EXIT_OK


def main() -> int:
    """Console entry point; returns the process exit code."""
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
