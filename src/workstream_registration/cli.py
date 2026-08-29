"""Operator CLI for Workstream Registration v1 (U11, PLAN:475).

Commands (PLAN:475)::

    workstream-registration register <workspace> --label <label>
        --record-source <type>=<uri>... [--kind direct|proxy]
    workstream-registration inspect <workspace>
    workstream-registration link <workspace>
    workstream-registration rebuild <workspace>...
    workstream-registration unregister <workspace>
    workstream-registration resolve-invalid <workspace>
    workstream-registration recover-lock <workspace>

``--kind`` defaults to ``direct``; the marker schema always requires the
field. A ``--json`` flag emits the stable result envelope after completion.

Interactive sessions: ``register``, ``unregister``, ``resolve-invalid``, and
``recover-lock`` are single-process interactive sessions. They display a
preview — label and local paths SHOWN, record-source URI content REDACTED
(KTD9, PLAN:194; 08-04 decision PLAN:546) — plus the in-memory HMAC-SHA-256
digest (process-ephemeral key, KTD6 PLAN:191), then read ``confirm <digest>``
from stdin. Cancellation, EOF, or a digest mismatch performs no write. A
digest is never accepted across invocations because the HMAC key is
process-ephemeral.

``register`` on a workspace that already holds a valid supported marker
degrades to linking and reports ``linked-existing`` without confirmation (no
write, PLAN:475/555). ``resolve-invalid`` previews the ``occupied-invalid``
state, marker-component identity, bounded byte length/digest, target handle,
and current lock status, and deletes only after the active/stale lock checks
and a confirmed target-handle match (``invalid-marker-resolved``, or
``invalid-deleted-unverified``, exit 5, on delete-succeeded/read-back-failed).
``recover-lock`` applies the same target-handle-bound confirmation and
reports the resulting lock state.

Exit codes (PLAN:556) are derived from the result envelope outcome via
:data:`OUTCOME_EXIT_CODE` — ``--json`` outcome and exit code never diverge:

    0  registered / linked-existing / unregistered / invalid-marker-resolved
    2  cancelled / stopped
    3  invalid or inaccessible input (including occupied-invalid inspection;
       also CLI usage errors — no envelope is produced for usage errors)
    4  conflict / changed-marker-stopped
    5  written-unverified / registered-unlinked / invalid-deleted-unverified
    6  safe internal failure (no envelope produced)

``rebuild`` and ``recover-lock`` are not result-vocabulary operations: the
frozen outcome set has no lock-recovery or rebuild outcome, so they report
their own stable surfaces. ``rebuild`` emits the projection ``RebuildResult``
report (``{status, entries, detail}``; exit 0 rebuilt / 3 failed). 
``recover-lock`` emits ``{"workspace", "lock_state"}`` with ``lock_state`` in
``absent | recovered | held`` (exit 0 absent/recovered, 4 held — a live
owner's lock is never broken, the conflict family of PLAN:556; 2 on
cancellation/EOF/mismatch).

The projection hook is the real U10 projection
(``registration.install_default_projection_hook``), so ``register`` reports
``registered`` with a linked projection unless the projection fails
(``registered-unlinked``).

Safety: human output redacts record-source URI content everywhere; labels
and local paths may appear under length caps (08-04 decision, PLAN:546).
Unexpected exceptions exit 6 with a fixed bounded message — never a raw
traceback carrying instance content.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TextIO

from workstream_registration import diagnostics as diag
from workstream_registration import filesystem as fs
from workstream_registration import registration as reg
from workstream_registration import unregister as unr

__all__ = [
    "EXIT_CONFLICT",
    "EXIT_INTERNAL_FAILURE",
    "EXIT_INVALID_INPUT",
    "EXIT_OK",
    "EXIT_PARTIAL",
    "EXIT_STOP",
    "OUTCOME_EXIT_CODE",
    "RECOVER_LOCK_STATES",
    "UsageError",
    "main",
    "recover_lock_interactive_cli",
    "register_interactive_cli",
    "resolve_invalid_interactive_cli",
    "unregister_interactive_cli",
]

EXIT_OK = 0
EXIT_STOP = 2
EXIT_INVALID_INPUT = 3
EXIT_CONFLICT = 4
EXIT_PARTIAL = 5
EXIT_INTERNAL_FAILURE = 6

# Frozen PLAN:556 mapping: outcome -> exit code. The conformance runner
# asserts this table against the corpus (REV:67) and tests assert the
# ``--json`` outcome and the exit code never diverge (PLAN:476).
OUTCOME_EXIT_CODE: dict[str, int] = {
    "registered": EXIT_OK,
    "linked-existing": EXIT_OK,
    "unregistered": EXIT_OK,
    "invalid-marker-resolved": EXIT_OK,
    "cancelled": EXIT_STOP,
    "stopped": EXIT_STOP,
    "occupied-invalid": EXIT_INVALID_INPUT,
    "conflict": EXIT_CONFLICT,
    "changed-marker-stopped": EXIT_CONFLICT,
    "written-unverified": EXIT_PARTIAL,
    "registered-unlinked": EXIT_PARTIAL,
    "invalid-deleted-unverified": EXIT_PARTIAL,
}

RECOVER_LOCK_STATES = ("absent", "recovered", "held")

_REDACTED = "<redacted>"


class UsageError(ValueError):
    """Invalid CLI input (exit 3): no result envelope is produced."""


@dataclass(frozen=True)
class RecoverLockReport:
    """The ``recover-lock`` report surface (no frozen outcome exists for lock
    recovery; the result vocabulary is not stretched, PLAN:556)."""

    workspace: str
    lock_state: str

    def to_dict(self) -> dict[str, str]:
        return {"workspace": self.workspace, "lock_state": self.lock_state}

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)


def _parse_record_sources(raw: list[str]) -> list[dict[str, str]]:
    """Parse ``--record-source <type>=<uri>`` entries; malformed entries are
    usage errors (exit 3)."""
    sources: list[dict[str, str]] = []
    for item in raw:
        type_token, separator, uri = item.partition("=")
        if not separator or not type_token.strip() or not uri.strip():
            raise UsageError(
                f"invalid --record-source {item!r}: expected <type>=<uri>"
            )
        sources.append({"type": type_token, "uri": uri})
    if not sources:
        raise UsageError("at least one --record-source <type>=<uri> is required")
    return sources


def _emit_line(emit: Callable[[str], None], line: str) -> None:
    emit(line)


def _preview_record_sources(record_sources: list[dict[str, str]]) -> list[str]:
    """Preview lines: type tokens shown (structural), URI content redacted."""
    lines = [f"  record_sources: {len(record_sources)}"]
    for index, source in enumerate(record_sources):
        lines.append(f"    [{index}] type={source['type']} uri={_REDACTED}")
    return lines


def register_interactive_cli(
    workspace: Path,
    *,
    label: str,
    record_sources: list[dict[str, str]],
    kind: str = "direct",
    emit: Callable[[str], None] | None = None,
    read_line: Callable[[], str] | None = None,
) -> reg.RegistrationResult:
    """Interactive ``register`` flow: inspect -> degrade/link -> draft ->
    preview -> ``confirm <digest>`` -> register (PLAN:475, 555).

    ``emit`` receives every preview line (defaults to ``print(flush=True)``);
    ``read_line`` returns one stdin line (defaults to ``sys.stdin.readline``).
    Both are seams for tests and embedding; the digest is only ever accepted
    within this invocation (process-ephemeral key, KTD6 PLAN:191).
    """
    reg.install_default_projection_hook()
    emit = emit if emit is not None else lambda line: print(line, flush=True)
    read_line = read_line if read_line is not None else sys.stdin.readline
    inspection = reg.inspect(workspace)
    if inspection.state != reg.STATE_DRAFT_READY:
        return reg.inspection_result(inspection)
    try:
        draft = reg.draft(
            workspace,
            label=label,
            record_sources=record_sources,
            kind=kind,
            inspection=inspection,
        )
    except reg.DraftInputError as exc:
        code = (
            exc.diagnostics.items[0].code
            if exc.diagnostics.count
            else diag.CODE_SCHEMA_INVALID
        )
        return reg.RegistrationResult(
            outcome=reg.OUTCOME_STOPPED,
            validity=reg.VALIDITY_NOT_APPLICABLE,
            effects=reg.Effects(False, False, False, False, False, reg.PROJECTION_NONE),
            diagnostics=diag.single(reg.PHASE_OPERATION, code),
        )
    lines = [
        "preview: register",
        f"  workspace: {workspace}",
        f"  marker path: {fs.marker_path(workspace)}",
        f"  label: {draft.label}",
        f"  kind: {draft.marker['kind']}",
    ]
    lines.extend(_preview_record_sources(draft.marker["record_sources"]))
    lines.append(f"  digest: {draft.digest}")
    lines.append(f"confirm {draft.digest}")
    for line in lines:
        _emit_line(emit, line)
    confirmation = _confirm_digest(draft.digest, read_line, reg.confirm, draft)
    return reg.register(workspace, draft, confirmation)


def unregister_interactive_cli(
    workspace: Path,
    *,
    emit: Callable[[str], None] | None = None,
    read_line: Callable[[], str] | None = None,
) -> reg.RegistrationResult:
    """Interactive ``unregister`` flow: fresh inspection -> unregister draft
    -> preview -> ``confirm <digest>`` -> confirmed conditional delete."""
    reg.install_default_projection_hook()
    emit = emit if emit is not None else lambda line: print(line, flush=True)
    read_line = read_line if read_line is not None else sys.stdin.readline
    inspection = reg.inspect(workspace)
    if inspection.state != reg.STATE_LINKED_EXISTING:
        return reg.inspection_result(inspection)
    try:
        envelope = unr.unregister_envelope(workspace, inspection=inspection)
    except unr.UnregisterEnvelopeError:
        return reg.inspection_result(inspection)
    marker = envelope.marker
    lines = [
        "preview: unregister",
        f"  workspace: {workspace}",
        f"  marker path: {fs.marker_path(workspace)}",
        f"  identity: {envelope.identity}",
        f"  label: {marker.get('label', '')}",
        f"  kind: {marker.get('kind', '')}",
    ]
    lines.extend(_preview_record_sources(marker.get("record_sources", [])))
    lines.append(f"  digest: {envelope.digest}")
    lines.append(f"confirm {envelope.digest}")
    for line in lines:
        _emit_line(emit, line)
    confirmation = _confirm_digest(
        envelope.digest, read_line, unr.confirm_unregister, envelope
    )
    return unr.unregister(workspace, confirmation)


def resolve_invalid_interactive_cli(
    workspace: Path,
    *,
    emit: Callable[[str], None] | None = None,
    read_line: Callable[[], str] | None = None,
) -> reg.RegistrationResult | None:
    """Interactive ``resolve-invalid`` flow (PLAN:475): preview the
    ``occupied-invalid`` state, marker-component identity, bounded byte
    length/digest, target handle, and current lock status; delete only after
    the active/stale lock checks and a confirmed target-handle match.

    Returns ``None`` when the workspace is not ``occupied-invalid`` (invalid
    input for this command, exit 3).
    """
    reg.install_default_projection_hook()
    emit = emit if emit is not None else lambda line: print(line, flush=True)
    read_line = read_line if read_line is not None else sys.stdin.readline
    inspection = reg.inspect(workspace)
    if inspection.state != reg.STATE_OCCUPIED_INVALID:
        return None
    envelope = reg.resolution_envelope(workspace, inspection=inspection)
    handle = envelope.handle.to_dict()
    lines = [
        "preview: resolve-invalid",
        f"  workspace: {workspace}",
        f"  marker path: {fs.marker_path(workspace)}",
        "  state: occupied-invalid",
        f"  marker_identity: {envelope.marker_identity if envelope.marker_identity else '<none>'}",
        f"  marker_length: {envelope.marker_length}",
        f"  marker_digest_sha256: {envelope.marker_digest.hex()}",
        f"  target_handle: {handle['workspace']}:{handle['parent']}",
        f"  lock_status: {envelope.lock_status}",
        f"  digest: {envelope.digest}",
        f"confirm {envelope.digest}",
    ]
    for line in lines:
        _emit_line(emit, line)
    confirmation = _confirm_digest(
        envelope.digest, read_line, reg.confirm_resolution, envelope
    )
    return reg.resolve_invalid(workspace, confirmation)


def recover_lock_interactive_cli(
    workspace: Path,
    *,
    emit: Callable[[str], None] | None = None,
    read_line: Callable[[], str] | None = None,
) -> RecoverLockReport | None:
    """Interactive ``recover-lock`` flow (PLAN:475): target-handle-bound
    confirmation, then the resulting lock state (``absent`` | ``recovered`` |
    ``held``). Returns ``None`` on cancellation/EOF/digest mismatch or an
    unrecoverable workspace (caller decides the exit code)."""
    reg.install_default_projection_hook()
    emit = emit if emit is not None else lambda line: print(line, flush=True)
    read_line = read_line if read_line is not None else sys.stdin.readline
    try:
        handle = fs.capture_target_handle(workspace)
    except fs.FilesystemError:
        return None
    lock = fs.lock_metadata(workspace)
    if lock is None:
        lock_state = "absent"
    elif lock.is_stale():
        lock_state = "stale"
    else:
        lock_state = "held"
    content = {
        "contract": {
            "marker": reg.MARKER_VERSION,
            "conformance": reg.RESULT_VERSION,
            "protocol": reg.PROTOCOL_VERSION,
        },
        "envelope_kind": "recover-lock",
        "target_handle": handle.to_dict(),
        "observed_lock_state": lock_state,
    }
    envelope_bytes = json.dumps(
        content, separators=(",", ":"), ensure_ascii=False, sort_keys=True
    ).encode("utf-8")
    digest = reg.envelope_digest(envelope_bytes)
    handle_dict = handle.to_dict()
    lines = [
        "preview: recover-lock",
        f"  workspace: {workspace}",
        f"  target_handle: {handle_dict['workspace']}:{handle_dict['parent']}",
        f"  lock_status: {lock_state}",
        f"  digest: {digest}",
        f"confirm {digest}",
    ]
    for line in lines:
        _emit_line(emit, line)
    line = read_line()
    if line is None or line.strip() != f"confirm {digest}":
        return None
    if lock_state == "absent":
        return RecoverLockReport(str(workspace), "absent")
    if lock_state == "held":
        return RecoverLockReport(str(workspace), "held")
    try:
        fs.recover_lock(workspace, handle)
    except fs.LockNotRecoverableError:
        return RecoverLockReport(str(workspace), "held")
    after = fs.lock_metadata(workspace)
    if after is None:
        return RecoverLockReport(str(workspace), "absent")
    return RecoverLockReport(str(workspace), "recovered")


def _confirm_digest(
    digest: str,
    read_line: Callable[[], str],
    confirm_fn: Callable[..., object],
    bound: object,
) -> object:
    """Read one ``confirm <digest>`` line; exact match only (PLAN:475).

    Cancellation, EOF, or a mismatched digest yields ``None`` — the caller's
    operation performs no write. ``confirm_fn`` is the module's own
    exact-digest confirmation (``reg.confirm``, ``reg.confirm_resolution``,
    ``unr.confirm_unregister``); for ``recover-lock`` the comparison is the
    exact string match itself.
    """
    line = read_line()
    if line is None or line.strip() != f"confirm {digest}":
        return None
    return confirm_fn(bound, digest)


# ---------------------------------------------------------------------------
# Argument parsing (usage errors exit 3, not argparse's default 2)
# ---------------------------------------------------------------------------


class _Parser:
    """Bounded argparse replacement: usage errors raise UsageError (exit 3).

    Supports the CLI contract exactly: a positional ``workspace`` (or several
    for ``rebuild``), a repeatable ``--record-source <type>=<uri>`` flag, and
    single-value flags (``--label``, ``--kind``). ``--json`` is accepted
    before or after the command.
    """

    def __init__(self) -> None:
        self._subparsers: list[dict[str, Any]] = []

    def add_subcommand(
        self, name: str, help: str, args: list[dict[str, Any]]
    ) -> None:
        self._subparsers.append({"name": name, "help": help, "args": args})

    def _is_boolean_flag(self, sub: dict[str, Any], name: str) -> bool:
        for spec in sub["args"]:
            if spec["name"] == name:
                return spec.get("boolean", False)
        return False

    def parse(self, argv: list[str]) -> dict[str, Any]:
        if not argv:
            raise UsageError("a command is required")
        args: dict[str, Any] = {}
        index = 0
        while index < len(argv) and argv[index] == "--json":
            args["json"] = True
            index += 1
        if index >= len(argv):
            raise UsageError("a command is required")
        if argv[index] in ("--help", "help"):
            args["help"] = True
            return args
        command = argv[index]
        index += 1
        sub = next((s for s in self._subparsers if s["name"] == command), None)
        if sub is None:
            raise UsageError(f"unknown command {command!r}")
        args["command"] = command
        tokens = argv[index:]
        positionals: list[str] = []
        flag_values: dict[str, list[str]] = {}
        token_index = 0
        while token_index < len(tokens):
            token = tokens[token_index]
            if token == "--json":
                args["json"] = True
                token_index += 1
                continue
            if token.startswith("--"):
                name = token[2:].replace("-", "_")
                if name == "help" or self._is_boolean_flag(sub, name):
                    args["help"] = True
                    token_index += 1
                    continue
                if token_index + 1 >= len(tokens):
                    raise UsageError(f"option {token!r} requires a value")
                flag_values.setdefault(name, []).append(tokens[token_index + 1])
                token_index += 2
                continue
            positionals.append(token)
            token_index += 1
        if not args.get("help"):
            for spec in sub["args"]:
                name = spec["name"]
                if spec.get("positional"):
                    if spec.get("greedy"):
                        got = positionals[:]
                        if not got:
                            raise UsageError(f"missing required argument <{name}>")
                        args[name] = got
                        positionals = []
                    else:
                        if not positionals:
                            raise UsageError(f"missing required argument <{name}>")
                        args[name] = positionals.pop(0)
                    continue
                values = flag_values.pop(name, None)
                if spec.get("required") and not values:
                    raise UsageError(f"missing required option --{name.replace('_', '-')}")
                if spec.get("repeatable"):
                    args[name] = values or []
                else:
                    args[name] = values[0] if values else spec.get("default")
            if positionals:
                raise UsageError(f"unexpected argument {positionals[0]!r}")
            if flag_values:
                unknown = next(iter(flag_values))
                raise UsageError(f"unknown option --{unknown.replace('_', '-')}")
        return args


def _build_parser() -> _Parser:
    parser = _Parser()
    parser.add_subcommand(
        "register",
        "register a workspace (interactive confirmation)",
        [
            {"name": "workspace", "positional": True},
            {"name": "label", "required": True},
            {"name": "record_source", "required": True, "repeatable": True},
            {"name": "kind", "default": "direct"},
            {"name": "help", "boolean": True},
        ],
    )
    parser.add_subcommand(
        "inspect",
        "read-only inspection of a workspace",
        [{"name": "workspace", "positional": True}, {"name": "help", "boolean": True}],
    )
    parser.add_subcommand(
        "link",
        "link an existing valid marker (no write, no confirmation)",
        [{"name": "workspace", "positional": True}, {"name": "help", "boolean": True}],
    )
    parser.add_subcommand(
        "rebuild",
        "transactionally rebuild the projection from explicit workspace roots",
        [{"name": "workspace", "positional": True, "greedy": True}, {"name": "help", "boolean": True}],
    )
    parser.add_subcommand(
        "unregister",
        "unregister a workspace (interactive confirmation)",
        [{"name": "workspace", "positional": True}, {"name": "help", "boolean": True}],
    )
    parser.add_subcommand(
        "resolve-invalid",
        "resolve an occupied-invalid marker (interactive confirmation)",
        [{"name": "workspace", "positional": True}, {"name": "help", "boolean": True}],
    )
    parser.add_subcommand(
        "recover-lock",
        "recover a stale per-workspace lock (interactive confirmation)",
        [{"name": "workspace", "positional": True}, {"name": "help", "boolean": True}],
    )
    return parser


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def _emit_result(
    result: reg.RegistrationResult, *, json_flag: bool, stdout: TextIO
) -> None:
    """Emit the stable result envelope (--json) or a bounded human summary."""
    if json_flag:
        stdout.write(result.serialize() + "\n")
        stdout.flush()
        return
    stdout.write(f"outcome: {result.outcome}\n")
    if result.identity is not None:
        stdout.write(f"identity: {result.identity}\n")
    if result.diagnostics.count:
        stdout.write(
            f"diagnostics: count={result.diagnostics.count} "
            f"code={result.diagnostics.items[0].code}\n"
        )
    stdout.flush()


def _cmd_register(args: dict[str, Any], stdin: TextIO, stdout: TextIO) -> int:
    workspace = Path(args["workspace"])
    label = args["label"]
    kind = args["kind"]
    if kind not in ("direct", "proxy"):
        raise UsageError(f"invalid --kind {kind!r}: expected direct or proxy")
    sources = _parse_record_sources(args["record_source"])

    def emit(line: str) -> None:
        print(line, file=stdout, flush=True)

    result = register_interactive_cli(
        workspace,
        label=label,
        record_sources=sources,
        kind=kind,
        emit=emit,
        read_line=stdin.readline,
    )
    _emit_result(result, json_flag=args.get("json", False), stdout=stdout)
    return OUTCOME_EXIT_CODE[result.outcome]


def _cmd_inspect(args: dict[str, Any], stdout: TextIO) -> int:
    workspace = Path(args["workspace"])
    inspection = reg.inspect(workspace)
    result = reg.inspection_result(inspection)
    if not args.get("json", False):
        print(f"state: {inspection.state}", file=stdout)
        if inspection.handle is not None and not args.get("json", False):
            handle = inspection.handle.to_dict()
            print(
                f"target_handle: {handle['workspace']}:{handle['parent']}",
                file=stdout,
            )
    _emit_result(result, json_flag=args.get("json", False), stdout=stdout)
    return OUTCOME_EXIT_CODE[result.outcome]


def _cmd_link(args: dict[str, Any], stdout: TextIO) -> int:
    result = reg.link(Path(args["workspace"]))
    _emit_result(result, json_flag=args.get("json", False), stdout=stdout)
    return OUTCOME_EXIT_CODE[result.outcome]


def _cmd_rebuild(args: dict[str, Any], stdout: TextIO, stderr: TextIO) -> int:
    from workstream_registration.projection import Projection

    paths = [Path(path) for path in args["workspace"]]
    result = Projection().rebuild(paths)
    if result.status == "rebuilt":
        if args.get("json", False):
            stdout.write(json.dumps(result.to_dict(), separators=(",", ":"), ensure_ascii=False) + "\n")
        else:
            print(f"rebuild: rebuilt ({len(result.entries)} entries)", file=stdout)
        stdout.flush()
        return EXIT_OK
    if args.get("json", False):
        stdout.write(json.dumps(result.to_dict(), separators=(",", ":"), ensure_ascii=False) + "\n")
    else:
        print(f"rebuild: failed", file=stdout)
    print(f"error: {result.detail}", file=stderr)
    return EXIT_INVALID_INPUT


def _cmd_unregister(args: dict[str, Any], stdin: TextIO, stdout: TextIO) -> int:
    def emit(line: str) -> None:
        print(line, file=stdout, flush=True)

    result = unregister_interactive_cli(
        Path(args["workspace"]), emit=emit, read_line=stdin.readline
    )
    _emit_result(result, json_flag=args.get("json", False), stdout=stdout)
    return OUTCOME_EXIT_CODE[result.outcome]


def _cmd_resolve_invalid(args: dict[str, Any], stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
    def emit(line: str) -> None:
        print(line, file=stdout, flush=True)

    result = resolve_invalid_interactive_cli(
        Path(args["workspace"]), emit=emit, read_line=stdin.readline
    )
    if result is None:
        print(
            "error: resolve-invalid requires an occupied-invalid workspace",
            file=stderr,
        )
        return EXIT_INVALID_INPUT
    _emit_result(result, json_flag=args.get("json", False), stdout=stdout)
    return OUTCOME_EXIT_CODE[result.outcome]


def _cmd_recover_lock(args: dict[str, Any], stdin: TextIO, stdout: TextIO, stderr: TextIO) -> int:
    def emit(line: str) -> None:
        print(line, file=stdout, flush=True)

    report = recover_lock_interactive_cli(
        Path(args["workspace"]), emit=emit, read_line=stdin.readline
    )
    if report is None:
        if not Path(args["workspace"]).is_dir():
            print("error: workspace inaccessible", file=stderr)
        else:
            print("cancelled: no write", file=stdout)
        return EXIT_STOP
    if args.get("json", False):
        stdout.write(report.serialize() + "\n")
    else:
        print(f"lock: {report.lock_state}", file=stdout)
    stdout.flush()
    if report.lock_state == "held":
        return EXIT_CONFLICT
    return EXIT_OK


def _usage() -> str:
    return """\
workstream-registration - register and manage workstream identities

Quick start:
  workstream-registration register ./my-workspace \\
      --label "My Project" \\
      --record-source sharepoint/site=https://sharepoint.example.org/sites/project

Commands:
  register        Register a workspace (interactive confirmation)
  inspect         Read-only inspection of a workspace state
  link            Link an existing valid marker (no write, no confirmation)
  rebuild         Rebuild the projection from explicit workspace roots
  unregister      Unregister a workspace (interactive confirmation)
  resolve-invalid Resolve an occupied-invalid marker (interactive confirmation)
  recover-lock    Recover a stale per-workspace lock (interactive confirmation)

Global options:
  --json          Emit the stable result envelope (JSON) after completion

Each command supports --help for detailed usage:
  workstream-registration <command> --help
"""


def _help_register() -> str:
    return """\
workstream-registration register - register a workspace

Usage:
  workstream-registration register <workspace> --label <label> \\
      --record-source <type>=<uri>... [--kind direct|proxy]

Arguments:
  <workspace>                 Path to the workspace directory
  --label <label>             Human-readable label for this workspace
  --record-source <type>=<uri>  Record source (repeatable; at least one required)
                              Format: type token = URI
  --kind <direct|proxy>       Registration kind (default: direct)

What happens:
  1. Inspects the workspace for an existing valid marker
  2. If a valid marker already exists, degrades to linking (linked-existing)
  3. Otherwise, drafts the marker and shows a preview with the digest
  4. You confirm by typing: confirm <digest>
  5. The marker is written and the projection is updated

The preview shows labels and local paths, but record-source URI content
is redacted for safety. The digest uses a process-ephemeral key, so it
is only valid within this invocation.

Examples:
  workstream-registration register ./my-workspace \\
      --label "My Project" \\
      --record-source sharepoint/site=https://sharepoint.example.org/sites/p

  workstream-registration register ./proxy-ws \\
      --label "Proxy Setup" \\
      --record-source git=https://github.com/org/repo.git \\
      --kind proxy

  workstream-registration --json register ./my-workspace \\
      --label "Json Run" \\
      --record-source example/records=https://records.example.org/x

Output:
  Human mode:  preview lines, then "outcome: <result>"
  --json mode: {"outcome": "...", "identity": "...", "validity": "...",
                "effects": {...}, "diagnostics": {...}}

Exit codes:
  0  registered / linked-existing
  2  cancelled / stopped
  3  invalid input
  4  conflict
  5  written-unverified / registered-unlinked
"""


def _help_inspect() -> str:
    return """\
workstream-registration inspect - read-only inspection of a workspace

Usage:
  workstream-registration inspect <workspace> [--json]

Arguments:
  <workspace>    Path to the workspace directory

What happens:
  Reads the workspace marker (if any) and reports its state without
  modifying anything.

States:
  draft-ready        No marker found; workspace is ready for registration
  linked-existing    A valid marker is present and linked
  occupied-invalid   A marker exists but is invalid or unreadable

Examples:
  workstream-registration inspect ./my-workspace
  workstream-registration --json inspect ./my-workspace

Output:
  Human mode:  "state: <state>" followed by outcome and identity
  --json mode: {"outcome": "...", "identity": "...", ...}

Exit codes:
  0  linked-existing
  2  stopped (draft-ready or missing workspace)
  3  occupied-invalid
"""


def _help_link() -> str:
    return """\
workstream-registration link - link an existing valid marker

Usage:
  workstream-registration link <workspace> [--json]

Arguments:
  <workspace>    Path to the workspace directory

What happens:
  Reads an existing valid marker and links it to the projection.
  No write occurs, no confirmation is required.

  This is useful when a marker was written manually or by another
  process and you want to register it in the projection.

Examples:
  workstream-registration link ./my-workspace
  workstream-registration --json link ./my-workspace

Output:
  Human mode:  "outcome: linked-existing" with identity
  --json mode: {"outcome": "linked-existing", "identity": "...", ...}

Exit codes:
  0  linked-existing
  2  stopped (no valid marker found)
"""


def _help_rebuild() -> str:
    return """\
workstream-registration rebuild - rebuild the projection from workspace roots

Usage:
  workstream-registration rebuild <workspace>... [--json]

Arguments:
  <workspace>...    One or more workspace root paths (greedy; at least one required)

What happens:
  Scans the given workspace roots, reads each valid marker, and
  rebuilds the projection database. Workspace paths must be provided
  explicitly -- there is no auto-discovery.

  Use this after projection data loss or corruption, or to force a
  full re-scan of known workspaces.

Examples:
  workstream-registration rebuild ./my-workspace
  workstream-registration rebuild ./ws-a ./ws-b ./ws-c
  workstream-registration --json rebuild ./my-workspace

Output:
  Human mode:  "rebuild: rebuilt (N entries)" or "rebuild: failed"
  --json mode: {"status": "rebuilt", "entries": [...], "detail": "..."}

Exit codes:
  0  rebuilt successfully
  3  failed (invalid root or no valid markers)
"""


def _help_unregister() -> str:
    return """\
workstream-registration unregister - unregister a workspace

Usage:
  workstream-registration unregister <workspace> [--json]

Arguments:
  <workspace>    Path to the workspace directory

What happens:
  1. Inspects the workspace for a valid linked marker
  2. If linked, drafts an unregister envelope and shows a preview
  3. You confirm by typing: confirm <digest>
  4. The marker is deleted and the projection is updated

  If the workspace has no valid marker, the operation stops (exit 2).
  If the marker identity changes between preview and confirmation,
  the operation stops with changed-marker-stopped (exit 4).

Examples:
  workstream-registration unregister ./my-workspace
  workstream-registration --json unregister ./my-workspace

Output:
  Human mode:  preview lines, then "outcome: <result>"
  --json mode: {"outcome": "...", "identity": "...", ...}

Exit codes:
  0  unregistered
  2  cancelled / stopped
  4  changed-marker-stopped
"""


def _help_resolve_invalid() -> str:
    return """\
workstream-registration resolve-invalid - resolve an occupied-invalid marker

Usage:
  workstream-registration resolve-invalid <workspace> [--json]

Arguments:
  <workspace>    Path to the workspace directory

What happens:
  1. Inspects the workspace for an occupied-invalid marker
  2. Shows a preview with marker identity, length, digest, lock status,
     and target handle
  3. You confirm by typing: confirm <digest>
  4. The invalid marker is deleted (after active/stale lock checks)

  If the workspace is not occupied-invalid, the operation fails (exit 3).
  If verification of absence fails after deletion, reports
  invalid-deleted-unverified (exit 5).

Examples:
  workstream-registration resolve-invalid ./my-workspace
  workstream-registration --json resolve-invalid ./my-workspace

Output:
  Human mode:  preview lines, then "outcome: <result>"
  --json mode: {"outcome": "...", "identity": "...", ...}

Exit codes:
  0  invalid-marker-resolved
  2  cancelled
  3  not occupied-invalid
  5  invalid-deleted-unverified
"""


def _help_recover_lock() -> str:
    return """\
workstream-registration recover-lock - recover a stale per-workspace lock

Usage:
  workstream-registration recover-lock <workspace> [--json]

Arguments:
  <workspace>    Path to the workspace directory

What happens:
  1. Captures the target handle and reads the current lock status
  2. Shows a preview with workspace, target handle, and lock status
  3. You confirm by typing: confirm <digest>
  4. A stale lock is recovered; a live owner's lock is never broken

  Lock states:
    absent    No lock file exists
    recovered A stale lock was successfully recovered
    held      A live owner holds the lock (conflict; exit 4)

Examples:
  workstream-registration recover-lock ./my-workspace
  workstream-registration --json recover-lock ./my-workspace

Output:
  Human mode:  preview lines, then "lock: <state>"
  --json mode: {"workspace": "...", "lock_state": "..."}

Exit codes:
  0  absent / recovered
  2  cancelled
  4  held (live owner)
"""


_HELP_DISPATCH: dict[str, Callable[[], str]] = {
    "register": _help_register,
    "inspect": _help_inspect,
    "link": _help_link,
    "rebuild": _help_rebuild,
    "unregister": _help_unregister,
    "resolve-invalid": _help_resolve_invalid,
    "recover-lock": _help_recover_lock,
}


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """CLI entry point; returns the process exit code (PLAN:556).

    Installs the real U10 projection hook once at startup so registration
    reports ``registered`` with a linked projection.
    """
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    stderr = stderr if stderr is not None else sys.stderr
    reg.install_default_projection_hook()
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse(argv)
    except UsageError as exc:
        print(f"error: {exc}", file=stderr)
        print("commands: register inspect link rebuild unregister resolve-invalid recover-lock", file=stderr)
        return EXIT_INVALID_INPUT
    if args.get("help"):
        command = args.get("command")
        if command is None:
            print(_usage(), file=stdout)
        else:
            help_fn = _HELP_DISPATCH.get(command)
            if help_fn is not None:
                print(help_fn(), file=stdout)
            else:
                print(_usage(), file=stdout)
        return EXIT_OK
    try:
        command = args["command"]
        if command == "register":
            return _cmd_register(args, stdin, stdout)
        if command == "inspect":
            return _cmd_inspect(args, stdout)
        if command == "link":
            return _cmd_link(args, stdout)
        if command == "rebuild":
            return _cmd_rebuild(args, stdout, stderr)
        if command == "unregister":
            return _cmd_unregister(args, stdin, stdout)
        if command == "resolve-invalid":
            return _cmd_resolve_invalid(args, stdin, stdout, stderr)
        if command == "recover-lock":
            return _cmd_recover_lock(args, stdin, stdout, stderr)
        raise UsageError(f"unknown command {command!r}")
    except UsageError as exc:
        print(f"error: {exc}", file=stderr)
        return EXIT_INVALID_INPUT
    except Exception:
        print("error: safe internal failure", file=stderr)
        return EXIT_INTERNAL_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
