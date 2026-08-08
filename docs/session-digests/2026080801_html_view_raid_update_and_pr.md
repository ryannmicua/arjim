---
lorespec: "0.1"
id: "2026080801"
date: "2026-08-08"
source: "opencode"
topic: "HTML system view build and serve, RAID log update with Proof sync, serve-process lesson capture, and the workstream PR opening"
tags: [workstream-registration, html-artifacts, raid-log, ce-proof, paseo-orchestration, serve-ops, pr-ship]
classification:
  type: technical
  secondary_type: operational
  domains: [workstream-registration, plan-governance, documentation, delivery]
  value: high
trails: [workstream-registration-planning, docs-usage, html-system-view, raid-log]
---

## Session Arc

### Started
The luna agent (`opencode-go/gpt-5.6-luna`, max thinking, build mode) had just finished `tmp/system-view/index.html`: 82,203 bytes, all 9 sections (hero, layered architecture with 9 modules, register lifecycle, raw-bytes-to-result pipeline, 17-state machine, filesystem/projection, security model, scope boundaries, glossary), zero external references, direct-file and local-HTTP Edge renders passed with no horizontal overflow at a 390px viewport. The earlier `claude-opus-5` build had failed (provider not logged in), so luna was the fallback that delivered. The operator's remaining queue: capture the serve lesson, write this session digest, open the PR.

### Pivots
- **Serve attempt #1 failed silently** — a Paseo supervised terminal echoed `python -m http.server 8890 --bind 100.84.85.1` but never executed it (no output, no process, no listener; `Invoke-WebRequest` → "actively refused"). Relaunched detached via `Start-Process` with redirected stdout/stderr → PID 17240, listener on `100.84.85.1:8890` (Listen), HTTP 200 with title marker verified. The lesson was captured as a solution doc (A2) instead of being forgotten.
- **RAID log updated (operator directive)** — D-003 moved to Resolved with its final pins (CPython 3.14.6, `jsonschema` 4.26.0, stdlib `sqlite3` 3.50.4, NTFS tested profile with fail-closed POSIX branches, verified 362 tests / 87/87 conformance); R-001–R-006 mitigation cells marked implemented-and-verified (risks stay Active — ongoing product properties); intro note added. Synced to Proof (`fpi7ic3c`, revision 4) via the ce-proof mechanics with read-back verification, committed `1939b11`.
- **Housekeeping** — five finished lane agents archived (luna, opus-5 failure, ce-compound-refresh, docs round, rename worker) to free Windows server memory per the paseo-ops learning; stale `tmp/liveview/` deleted.
- **PR opened** — the final gate of the workstream: `gh pr create` on `feat/workstream-registration` against `main` with a full verification-and-docs summary.

### Ended
Branch at 29 commits vs main, pushed, PR open. The workstream-registration feature arc is delivered end-to-end: implementation, terminal verification, review (P1s fixed, P2s filed as issues #2–#7), marker-path rename ruling, five-file Diataxis usage docs, six-file architecture set, six solution docs, two decision digests, this digest, and the PR. Remaining: merge (operator), heypogi skill push (operator), server persistence (operator).

## ARTIFACTS

### A1. System HTML view — `tmp/system-view/index.html`, served at http://100.84.85.1:8890/
- **What:** 82,203-byte single-file visual view of the whole system: 9 sections, inline SVG/CSS diagrams (architecture stack/module map, lifecycle flow, actor sequence, raw-guard pipeline, validation branches, state/outcome map, lock lifecycle, projection schema/idempotency model), interactive filters and module focus. Zero external dependencies (grep-verified: no `http://`, `https://`, `<link`, `<script src`); rendered in Edge from file:// and local HTTP; 390px viewport no overflow.
- **Build:** luna (gpt-5.6-luna, max thinking) after opus-5 failed on `claude auth` (not logged in). Judgment call accepted: `conformance_runner.py` shown as a cross-cutting proof rail, not a sixth runtime layer.
- **Serve:** detached `Start-Process` (PID 17240), NetBird interface bind, verified HTTP 200. Session-bound — dies with the session unless made a service (O1).

### A2. Serve-lesson solution doc — `docs/solutions/workflow-issues/paseo-terminal-keystrokes-echo-without-executing-windows.md`
- **What:** the Paseo-terminal-echo-without-execute failure mode on Windows: an echoed command is not proof of execution; verify by listener (`Get-NetTCPConnection`); launch long-running processes detached (`Start-Process` + redirected logs, `-PassThru` for the PID); bind deliberately (NetBird IP vs localhost). Includes the actual working command and the anti-pattern.
- **Role:** sixth solution doc in `docs/solutions/` (workflow-issues category, companion to the paseo-worker-verifier-loop-operations doc).

### A3. RAID log update — `docs/raid.md` (commit `1939b11`) + Proof sync
- **What:** D-003 resolved (final pins per `contracts/.../v1/compatibility.md`, verified on host); R-001–R-006 mitigations confirmed implemented and verified; update note in the intro. Proof doc `fpi7ic3c` synced to revision 4 via `set_document` with the CE identity, verified by read-back (all markers present, no stale D-003 row).
- **Role:** closes O1 from digest 2026080703 (the documented open question about RAID staleness).

### A4. This session digest
- **What:** records the HTML view delivery, the serve failure mode and fix, the RAID/Proof update, and the PR opening.

### A5. The PR — `feat/workstream-registration` → `main`
- **What:** 29 commits: the 11-unit implementation (raw-input guard, bundled Draft 2020-12 validation, normalized bounded diagnostics, create-only write and read-back, confirmed conditional delete, replaceable SQLite projection, operator CLI, conformance runner), P1 fixes, marker-path rename to `.workstream/manifest.json`, usage + architecture docs, solution store, RAID update. Body carries the verification evidence (362 tests, 87/87 conformance, terminal pass 11 units / 13 gates / 14 DoD, review APPROVE-WITH-NITPICKS with P1s fixed and P2s as issues #2–#7) and the install/verify recipe.

## DECISIONS

### D1. Serve via detached `Start-Process`, not terminal keystrokes (2026-08-08)
- **Decision:** long-running serve processes on this Windows host launch detached with redirected logs; Paseo terminal keystrokes are used only when the shell demonstrably executes them, and a port-listener check is the acceptance test either way.
- **Issue:** how to reliably serve the HTML view to NetBird viewers after the terminal delivery failed once.
- **Warrant:** the detached launch succeeded immediately where the terminal echoed without executing; it also yields a PID and log files.
- **Qualifier:** usually (terminal may work; the listener check decides). **Status:** settled.

### D2. RAID update scope: resolve D-003, keep R-001–R-006 Active with verified mitigations
- **Decision:** D-003 (a one-time selection) closes to Resolved; risks remain Active because their mitigations are ongoing product properties — the cells now state "Implemented and verified 2026-08-08".
- **Issue:** what does "up to date" mean for the risk register after implementation?
- **Warrant:** a resolved selection is done; a mitigated risk still applies as long as the product runs.
- **Status:** settled.

### D3. Open the PR now (operator, 2026-08-08)
- **Decision:** the last gate opens: `feat/workstream-registration` → `main` with the full summary.
- **Issue:** the operator deferred PR creation across multiple sessions; all work was pushed and verified.
- **Status:** settled — PR open; merge remains the operator's call.

## INSIGHTS

### I1. An echoed command is not evidence of execution — verify by listener
The Paseo terminal echoed the serve command in full and never ran it. `Get-NetTCPConnection` / `Invoke-WebRequest` turned an ambiguous echo into a binary answer in seconds. Confidence: high (observed).

### I2. A zero-external-dependency single-file artifact is the right shape for network-shared views
The 82 KB HTML view with inline SVG/CSS renders identically offline and over NetBird, works from file:// and HTTP, and has no CDN/version drift risk. The luna build met every gate on the first delivery. Confidence: high.

### I3. RAID entries need an explicit close event — staleness is the default
D-003 sat Active for six days after U11 finalized the pins because no pass existed to move it. The operator-triggered update is the close event; without a closing convention, registers rot by default. Confidence: medium.

## PATTERNS

### P1. Verify-by-listener after any serve/daemon launch (local)
Send/launch → `Get-NetTCPConnection -LocalPort <port>` (assert `Listen` + bound address) → `Invoke-WebRequest` content marker → only then report "serving". Any other sequence risks reporting a service that never started.

### P2. Proof sync after editing a proof-backed doc (local)
Edit local canonical file → read `v3/document` for revision → `set_document` with the full local markdown + `baseRevision` → verify by read-back (new markers present, stale content absent) → commit. Local stays canonical; the Proof doc is a mirror.

## OPEN_QUESTION

### O1. System-view server persistence
The view at `http://100.84.85.1:8890/` (PID 17240) dies with this session. A scheduled task / service would make it durable across reboots. Operator hasn't decided.

### O2. heypogi skill push
`f6c0f27` (architecture-doc-set skill in `C:\Users\rmicua\myrepo\heypogi`) is local-only, 1 commit ahead of origin/main. Push or leave local? Operator hasn't decided.

## NEXT_STEP

### N1. Merge decision on the PR (operator)
The PR is open against `main` with the full evidence body. Merge is the operator's call; on approval the remaining follow-ups (issues #2–#7) can be triaged from the merge.

### N2. Decide O1 / O2 (operator, whenever)
Server persistence and the heypogi skill push are both one-command decisions; neither blocks anything.

## Connections
- A1 —[failed_then_fixed]→ A2; A1 —[served_by]→ D1
- A3 —[closes]→ O1 (digest 2026080703); A3 —[instance_of]→ P2
- A2 —[related_to]→ paseo-worker-verifier-loop-operations (same category, complementary failure modes)
- D3 / A5 —[follows_from]→ N1 (digest 2026080703)

## Trail Updates
- **workstream-registration-planning:** RAID log current (D-003 resolved, R-001–R-006 verified), serve lesson captured, session digest recorded.
- **docs-usage:** unchanged this session (architecture + usage docs live from previous rounds).
- **html-system-view:** built (luna), verified (9 sections, zero external refs, no overflow), served on NetBird (100.84.85.1:8890) — session-bound.
- **raid-log:** D-003 resolved, risks annotated verified, Proof synced to revision 4.
