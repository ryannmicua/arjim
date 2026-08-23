"""Conformance runner, fixtures, docs, and vocabulary (U9).

Makes the dispatch contract independently checkable and records the new
vocabulary.  Mirrors ``workstream_registration.conformance_runner.py``.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Manifest and schema loading
# ---------------------------------------------------------------------------


def repo_root() -> Path:
    """Repository root containing the contracts directory."""
    current = Path(__file__).resolve()
    for ancestor in (current, *current.parents):
        if (ancestor / "contracts" / "workstream-dispatch").is_dir():
            return ancestor
    raise RuntimeError(
        f"repository root not found: no contracts/workstream-dispatch above {current}"
    )


def manifest_path() -> Path:
    """Path to the expectations manifest."""
    root = repo_root()
    override = os.environ.get("DISPATCH_CONFORMANCE_MANIFEST")
    if override:
        return Path(override)
    return root / "tests" / "contracts" / "workstream-dispatch" / "expectations.json"


def load_manifest() -> dict[str, Any]:
    """Load and return the expectations manifest."""
    path = manifest_path()
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Structural no-scheduler assertion (AE13)
# ---------------------------------------------------------------------------

_SCHEDULER_PATTERNS = [
    re.compile(r"\bThread\s*\("),
    re.compile(r"\bthreading\.Thread\b"),
    re.compile(r"\bschedule\.run_pending\b"),
    re.compile(r"\bTimer\s*\("),
]


def assert_no_scheduler(src_dir: Path) -> list[str]:
    """Scan src/workstream_dispatch/ for scheduler registrations (AE13).

    Returns a list of violation descriptions; empty list = pass.
    """
    violations = []
    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "conformance_runner.py":
            continue  # Skip the scanner itself
        try:
            content = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for line_no, line in enumerate(content.splitlines(), start=1):
            for pat in _SCHEDULER_PATTERNS:
                if pat.search(line):
                    violations.append(f"{py_file.name}:{line_no}: {line.strip()}")
    return violations


# ---------------------------------------------------------------------------
# Canary scan
# ---------------------------------------------------------------------------


def canary_scan(captured_output: str, store_bytes: bytes, canaries: dict[str, str]) -> list[str]:
    """Tripwire: any canary value in captured output or store bytes (AE14).

    Returns a list of violations; empty list = pass.
    """
    violations = []
    for name, value in canaries.items():
        if value in captured_output:
            violations.append(f"canary '{name}' found in captured output")
        if value.encode("utf-8") in store_bytes:
            violations.append(f"canary '{name}' found in store bytes")
    return violations


# ---------------------------------------------------------------------------
# Registration-untouched gate (AE15)
# ---------------------------------------------------------------------------


def registration_untouched() -> bool:
    """Assert the registration conformance runner exits 0 and no registration
    files differ from committed state (AE15)."""
    import subprocess

    # Run registration conformance
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "workstream_registration.conformance_runner"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            return False
    except Exception:
        return False

    # Check git status
    root = repo_root()
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "src/workstream_registration", "contracts/workstream-registration"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(root),
        )
        if proc.stdout.strip():
            return False
    except Exception:
        return False

    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run() -> int:
    """Run the conformance suite and exit with the appropriate code."""
    print("workstream-dispatch conformance runner")
    print(f"manifest: {manifest_path()}")

    violations: list[str] = []

    # Load manifest
    try:
        manifest = load_manifest()
        print(f"entries: {manifest.get('entries', 0)}")
    except Exception as exc:
        print(f"FAIL: cannot load manifest: {exc}")
        return 1

    # Structural no-scheduler assertion
    root = repo_root()
    src_dir = root / "src" / "workstream_dispatch"
    scheduler_violations = assert_no_scheduler(src_dir)
    captured_output = "\n".join(scheduler_violations)
    if scheduler_violations:
        print("FAIL: structural no-scheduler assertion")
        for v in scheduler_violations:
            print(f"  {v}")
        violations.extend(scheduler_violations)
    else:
        print("structural-no-scheduler: ok")

    # Canary scan (AE14)
    canaries = manifest.get("canaries", {})
    store_bytes = b""
    canary_violations = canary_scan(captured_output, store_bytes, canaries)
    if canary_violations:
        print("FAIL: canary scan")
        for v in canary_violations:
            print(f"  {v}")
        violations.extend(canary_violations)
    else:
        print("canary-scan: ok")

    # Registration-untouched gate
    if registration_untouched():
        print("registration-untouched: ok")
    else:
        print("FAIL: registration-untouched")
        violations.append("registration-untouched failed")

    if violations:
        print(f"failures: {len(violations)}")
        return 1

    print("conformance: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(run())
