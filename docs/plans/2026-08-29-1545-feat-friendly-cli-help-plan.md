---
title: Friendly CLI Help and Discoverability - Plan
type: feat
date: 2026-08-29
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
---

## Goal Capsule

- **Objective:** A new user or agent can understand what the tool does, how to use it, and what each command does without reading external docs — from the CLI alone.
- **Means:** Replace the terse `_usage()` output and add per-subcommand `--help` dispatch (KTD1).
- **Stop conditions:** `workstream-registration` with no args shows a helpful guide; every subcommand accepts `--help` with examples and argument descriptions; existing conformance tests still pass.

## Product Contract

### Summary

The `workstream-registration` CLI currently has minimal discoverability: no-args output is a bare error, `--help` is a terse command list, and subcommand `--help` is not implemented. This plan adds friendlier output at three levels so users and agents can self-serve from the CLI.

### Problem Frame

The CLI is the only operator-facing surface of Arjim's v1 capability. A user who runs `workstream-registration` with no arguments gets `error: a command is required` — no guidance, no examples, no context. Agents parsing CLI output for tool-use also get nothing actionable. The quickstart and guide docs exist but the CLI itself should be self-explanatory.

### Requirements

- R1. Running `workstream-registration` with no arguments (or `--help`) shows a welcome guide explaining what the tool does, the common workflow, all commands with one-line descriptions, and a pointer to per-subcommand help.
- R2. Running `workstream-registration <command> --help` shows detailed help for that command: arguments with descriptions, what the command does step-by-step, output meaning, examples, and the `--json` flag.
- R3. All existing behavior is preserved — no command's output changes when `--help` is not requested; the conformance runner passes; exit codes are unchanged.
- R4. The help output is readable by both humans and agents (plain text, no ANSI, no colors).

### Scope Boundaries

- **In scope:** `_usage()` rewrite, top-level `--help`, per-subcommand `--help` dispatch, new help text functions.
- **Out of scope:** Changing command behavior, adding commands, changing the confirmation flow, changing the `--json` envelope, modifying the conformance corpus.

---

## Planning Contract

### Key Technical Decisions

- KTD1. **Per-subcommand help via `--help` flag in the arg parser.** The existing `_Parser` class handles `--help` at the top level only. Extend it so each subcommand also captures `--help` and routes to a dedicated help function per command. This avoids adding an external dependency (argparse, click) and stays within the existing hand-rolled parser pattern. `(session-settled: user-directed — chosen over switching to argparse: keeps the parser consistent with the existing codebase and avoids a dependency change.)`
- KTD2. **Help text lives in `_help_<command>()` functions in `cli.py`.** Each command gets a dedicated function returning its help string. This keeps all CLI text in one module, matches the existing pattern where `_usage()` holds the top-level text, and makes the help easy to maintain alongside the command implementations.
- KTD3. **No-args output uses the same `_usage()` function as `--help`.** Both routes print the same welcome guide. This avoids duplication and ensures consistency.

### Assumptions

- The existing `_Parser` class can be extended to handle `--help` per-subcommand without breaking its current parsing behavior.
- Help text does not need i18n/l10n in v1.
- The conformance runner does not test help text content (it tests outcomes and exit codes).

---

## Implementation Units

### U1. Extend the arg parser to support per-subcommand `--help`

- **Goal:** Each subcommand captures `--help` and routes to a help function instead of failing with "unknown option".
- **Requirements:** R2, R3
- **Dependencies:** none
- **Files:** `src/workstream_registration/cli.py`
- **Approach:**
  1. Add a `help` boolean flag to each subcommand definition in `_build_parser()`.
  2. In the `main()` dispatch, check `args.get("help")` before running the command handler; if set, print the command's help text and return exit 0.
  3. Handle `--help` for unknown commands gracefully (show top-level usage, not an error).
- **Test scenarios:**
  - `workstream-registration register --help` prints register help and exits 0.
  - `workstream-registration inspect --help` prints inspect help and exits 0.
  - `workstream-registration --help` prints top-level usage and exits 0.
  - `workstream-registration help` prints top-level usage and exits 0.
  - `workstream-registration unknown-command --help` prints error + command list, exits 3.
- **Verification:** Existing tests still pass; `--help` on each subcommand produces expected output.

### U2. Write the top-level usage/welcome text

- **Goal:** No-args and `--help` output explains the tool, shows the workflow, lists commands with descriptions, and points to per-subcommand help.
- **Requirements:** R1, R3, R4
- **Dependencies:** U1
- **Files:** `src/workstream_registration/cli.py`
- **Approach:**
  1. Replace the `_usage()` function body with a multi-section welcome: one-sentence description, quick-start example, command table, and a note about `--help` per command.
  2. Keep it concise — roughly 25-35 lines of output, not a full manual.
  3. Include a concrete `register` example showing the `--record-source` format.
- **Test scenarios:**
  - Output contains "workstream-registration" and all seven command names.
  - Output contains an example with `--record-source type=uri` format.
  - Output mentions per-subcommand `--help`.
- **Verification:** `workstream-registration --help` and `workstream-registration` (no args) both print the same text.

### U3. Write per-subcommand help text functions

- **Goal:** Each command has a `_help_<command>()` function returning its detailed help text with arguments, description, examples, and output explanation.
- **Requirements:** R2, R4
- **Dependencies:** U1
- **Files:** `src/workstream_registration/cli.py`
- **Approach:**
  1. Create `_help_register()`, `_help_inspect()`, `_help_link()`, `_help_rebuild()`, `_help_unregister()`, `_help_resolve_invalid()`, `_help_recover_lock()`.
  2. Each returns a string with: usage line, description, argument descriptions (what each flag does, allowed values), example invocations, and output explanation (what each outcome means).
  3. For `register`, explain the confirmation flow and that record-source URIs are redacted.
  4. For `inspect`, explain the state values.
  5. For `rebuild`, explain that workspace paths are explicit (no auto-discovery).
  6. For `unregister`, `resolve-invalid`, `recover-lock`, explain the confirmation flow.
- **Test scenarios:**
  - `register --help` output contains "record-source", "confirm", "label", and "example".
  - `inspect --help` output contains "state" and "linked-existing".
  - `rebuild --help` output contains "rebuild" and explains explicit paths.
  - `unregister --help` output contains "confirm" and "identity".
  - All help output is plain text (no ANSI escape codes).
- **Verification:** Each subcommand `--help` produces readable, accurate help text.

---

## Verification Contract

- `python -m workstream_registration.conformance_runner` — all 87 fixtures pass (existing baseline: 86 pass, 1 pre-existing failure; this plan does not change the conformance corpus).
- `pytest` from the repo root — full test suite passes.
- Manual smoke test: run each `--help` variant and verify output.

## Definition of Done

- [ ] `workstream-registration` (no args) shows the welcome guide.
- [ ] `workstream-registration --help` shows the same welcome guide.
- [ ] `workstream-registration <command> --help` shows detailed help for each of the seven commands.
- [ ] All help output is plain text, readable by humans and agents.
- [ ] Existing conformance tests pass unchanged.
- [ ] No command's non-help behavior is altered.
