"""Conformance runner for the Workstream Registration v1 corpus (U6 scaffold).

Canonical invocation::

    python -m workstream_registration.conformance_runner

U6 scope: load the U5 expectation manifest
(``tests/contracts/workstream-registration/expectations.json``), validate it
against the bundled ``contracts/workstream-registration/v1/
expectations.schema.json`` (Draft 2020-12), report the manifest summary, and
report zero executable cases — case execution is wired by U7+ (PLAN:415).
The CLI ``--json`` flag is U11's surface (PLAN:475); this runner emits plain,
stable output only.

Exit codes:
    0 — manifest loaded, validated, summary reported;
    1 — manifest or bundled schema cannot be loaded or validated;
    2 — this CPython build lacks the stdlib ``sqlite3`` module (PLAN:415).

Bundled-only ``$ref`` policy: the runner configures no registry, resolver, or
retrieval function for ``jsonschema``, so ``$ref`` resolution never fetches
over the network. Only the loaded schema file and the Draft 2020-12
meta-schema bundled inside the ``jsonschema`` package are resolvable; any
non-bundled ``$ref`` fails closed (asserted by tests at U8, PLAN:439-440).

Path resolution: the manifest is located relative to the repository root,
discovered by walking up from this package until a
``contracts/workstream-registration`` directory is found (works from an
editable install and from the repo root). The
``WORKSTREAM_REGISTRATION_MANIFEST`` environment variable overrides the
manifest location.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

__all__ = [
    "ENV_MANIFEST_PATH",
    "EXIT_MANIFEST_ERROR",
    "EXIT_NO_SQLITE3",
    "EXIT_OK",
    "RunnerError",
    "load_bundled_schema",
    "load_manifest",
    "main",
    "manifest_path",
    "repo_root",
    "run",
    "sqlite3_available",
    "sqlite3_version",
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

EXIT_OK = 0
EXIT_MANIFEST_ERROR = 1
EXIT_NO_SQLITE3 = 2

_MAX_VALIDATION_ERRORS_REPORTED = 10


class RunnerError(Exception):
    """The runner cannot proceed: manifest or bundled schema unusable."""


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
    """Stable summary of the loaded manifest (entries, categories, cases)."""
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
        "executable_cases": 0,
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
        "python": platform.python_version(),
        "jsonschema": importlib.metadata.version("jsonschema"),
        "sqlite3": sqlite3_version(),
    }


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
    """Run the scaffold conformance pass; returns the process exit code."""
    if not sqlite3_available():
        print(
            "error: stdlib sqlite3 is unavailable in this Python build; the "
            "Workstream Registration support profile requires it",
            file=sys.stderr,
        )
        return EXIT_NO_SQLITE3
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

    summary = summarize(manifest_data)
    info = system_info()
    categories = summary["categories"]
    print("workstream-registration conformance runner (scaffold U6)")
    print(f"manifest: {path}")
    print(f"manifest_version: {summary['manifest_version']}")
    print(f"contract: {summary['contract']}")
    print(f"entries: {summary['entries']}")
    print(
        "categories: "
        f"mandatory={categories['mandatory']} "
        f"capability={categories['capability']} "
        f"warning={categories['warning']}"
    )
    print("schema: ok")
    print(f"executable_cases: {summary['executable_cases']} (case execution wired by U7+)")
    print(f"sqlite3: ok ({info['sqlite3']})")
    return EXIT_OK


def main() -> int:
    """Console entry point; returns the process exit code."""
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
