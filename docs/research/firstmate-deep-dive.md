# Firstmate Deep Dive: How the Crew Runs

A source-of-truth report on the `firstmate` agent-distro repository
(`~/myrepo/firstmate`, upstream `github.com/kunchenguid/firstmate`).

Prepared August 2026. All file references are relative to the firstmate repo root.
The report is organized as a system walkthrough: what it is, how a request becomes
shipped work, how the fleet is supervised without spending tokens, and how the
whole thing stays safe and restart-proof.

## 1. What firstmate is

Firstmate is not a model, a harness, an app, a CLI, an MCP server, or a skill.
It is an **agent distro**: a portable directory of instructions, skills, tooling,
policies, and state conventions that turns a general-purpose terminal coding
agent (Claude Code, Grok, Pi, Codex, OpenCode, Cursor...) into a specialized
one — the "first mate". The human who runs it is the "captain".

- Clone the repo, launch a supported harness inside it, and `AGENTS.md` takes
  over as the first mate's entire job description.
- The first mate talks to the captain and to nobody else; every worker
  ("crewmate") reports through the first mate, never directly to the captain.
- The first mate **never writes to projects** (hard rule 1). It reads projects,
  dispatches crewmates into isolated git worktrees, supervises them, and hands
  back finished PRs, approved local merges, or standalone investigation reports.
- Everything that matters survives the death of any conversation: state lives
  on disk, never in chat memory. A restart is a non-event.

Product direction lives in `VISION.md`. The operating contract is `AGENTS.md`
(568 lines; `CLAUDE.md` is a symlink to it). The human-facing companion
architecture document is `docs/architecture.md`; the script-by-script toolbelt
reference is `docs/scripts.md`.

## 2. Repo anatomy: tracked surface vs private home

The repo is deliberately split into a **shared tracked surface** and a
**captain-private home**:

| Surface | Contents | Persistence |
| --- | --- | --- |
| Tracked, committed | `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `.tasks.toml`, `.github/workflows/`, `bin/` (the script toolbelt), `.agents/skills/` (internal skills), `skills/` (public installer-facing skills), harness adapter configs (`.claude/`, `.codex/`, `.cursor/`, `.grok/`, `.pi/`, `.opencode/`) | Shared template, evolved through PRs |
| Private, gitignored | `.env` (optional Relay token), `config/` (local choices), `data/` (durable fleet records), `state/` (runtime records + status events), `projects/` (clones, read-only to firstmate), `.no-mistakes/` (validation state) | Per-instance; `FM_HOME` selects the private dirs while scripts come from the tracked code root |

Key durable records in `data/`:

- `backlog.md` — the task queue (owned by `tasks-axi`; tracks work items, never agents).
- `projects.md` — thin registry of each project's standing delivery posture (`no-mistakes`, `direct-PR`, `local-only`, optional `+yolo`).
- `secondmates.md` — routing table for persistent secondmates (local or remote homes).
- `captain.md` — this home's captain preferences and working style (never propagated).
- `captain-shared.md` — main-authoritative preferences propagated read-only to secondmate homes.
- `learnings.md` — curated fleet-local operational facts, created lazily.
- `<id>/brief.md` — per-task crewmate instructions; `<id>/report.md` — scout deliverables.

Runtime records in `state/` include `<id>.meta` (task metadata: window, worktree,
harness, kind, mode/yolo, spawn generation), `<id>.status` (append-only wake-event
log), `<id>.turn-ended`, `<id>.busy-state` (+ generation sidecar), the durable wake
queue `.wake-queue`, watcher internals (`.watch.lock`, `.last-watcher-beat`,
`.watcher-down`), the session lock `.lock`, and the `.afk` away-mode flag.

## 3. The big picture

```
            you (the captain)
                  |  chat: requests, decisions, "merge it"
                  v
 +-------------------------------------+
 | firstmate            (this repo)    |
 | reads projects/ + firstmate routes  |
 | writes guarded backlog/briefs/state |
 +--+--------------+---------------+---+
    | backend sends / status files |
    v              v               v
 +--------+   +--------+      +--------+
 |fm-task1|   |fm-task2|  ... |fm-taskN|   tmux windows, herdr/zellij tabs, cmux workspaces, or Orca terminals
 |crewmate|   |crewmate|      |crewmate|   one autonomous agent each
 +---+----+   +---+----+      +---+----+
     v            v               v
  treehouse worktree, Orca worktree, or isolated secondmate home
     |
     +- ship: project mode > PR/local merge > teardown
     |
     +- scout: report at data/<id>/report.md > teardown
```

A captain request flows through the system in one loop:

1. **Intake** — the first mate resolves the project, classifies the deliverable
   (ship vs scout), decides the delivery mode and yolo posture, and writes a
   task brief.
2. **Dispatch** — `bin/fm-spawn.sh` creates a session endpoint in the runtime
   backend and a clean git worktree, then launches an autonomous agent into it.
3. **Supervision** — a zero-token bash watcher sleeps on the fleet and wakes the
   first mate only when something is actionable. Harness hooks guarantee no
   turn ends blind.
4. **Delivery** — the crewmate reports through status lines; a ship task lands
   behind the configured merge authority; a scout task leaves a report.
5. **Teardown** — fail-closed: unlanded work is never torn down.

## 4. Session start: one ordered digest

Every session runs `bin/fm-session-start.sh` exactly once. It composes the old
multi-read startup into one ordered digest with nine steps
(`fm-session-start.sh:256`):

1. **Lock** — acquires the per-home session lock (`bin/fm-lock.sh`) *before*
   anything mutates shared state. A lock refusal marks the session
   **READ-ONLY**: bootstrap becomes detect-only, the wake queue is left
   untouched, no network stage runs, and no fleet mutation is allowed.
   Immediately after locking, a bounded deferred network worker
   (`bin/fm-startup-network.sh`) starts in the background.
2. **Bootstrap** — `bin/fm-bootstrap.sh`: detect-only diagnostics always run
   (missing tools, worktree tangle, harness override, dispatch-profile and
   backlog-backend validation); the six mutating sweeps (legacy PR-check
   migration, fleet sync, secondmate convergence/liveness, pending remote
   handoff retry, Relay artifact writes) run only when the session holds the
   lock. Bootstrap detects first and asks for consent before installing.
3. **Wake drain** — presents the durable wake queue (`bin/fm-wake-drain.sh`)
   plus a bounded fleet-wide `OPEN DECISIONS` section and `UNREAD STATUS` lines.
   Presented records stay durable until the generation-bound acknowledgement.
4. **Supervision block** — `bin/fm-supervision-instructions.sh` emits exactly
   one operating block for the detected primary harness, followed by the
   read-once contract that governs it. The digest never starts supervision
   itself.
5. **Fleet-state digest** — compact backlog listing, every `state/<id>.meta`,
   bounded status tails (labeled as wake-event history, not current state),
   the `.afk` flag, and one cheap alive/dead probe per endpoint.
6. **Network checks** — whatever the deferred worker has published so far;
   unconfirmed checks are named "in progress", never reported passed.
7. **Context digest** — `data/projects.md`, `data/secondmates.md`,
   `data/captain.md`, `data/captain-shared.md`, `data/learnings.md`, each with
   an explicit `ABSENT` vs empty distinction (absence is meaningful).
8. **Closing reminder** — points back to the emitted supervision block.

The whole digest runs inside one bounded child (default 120 s); on truncation
it prints a `STARTUP TRUNCATED` banner naming the last stage reached. The
digest itself makes no network call and never waits for one.

## 5. The supervision engine

This is the heart of the system: supervision that costs **zero tokens** when
nothing needs the captain.

### 5.1 The watcher loop (`bin/fm-watch.sh`)

A singleton bash process polls the fleet (15 s cadence), classifies detected
changes in bash, and either **absorbs** them silently or **queues an actionable
wake** for the first mate. Key mechanics:

- **Singleton + self-eviction**: a lock (`state/.watch.lock`) ensures one
  watcher; every cycle the watcher confirms it still owns the lock and touches
  the liveness beacon (`state/.last-watcher-beat`) that guard scripts read.
- **Wake vocabulary**: `signal:` (status/turn-end file changes), `stale:`
  (pane unchanged across two consecutive hashes), `check:` (authenticated poll
  output, e.g. PR merge poll, Relay mention, process-event result),
  `heartbeat:` (periodic fleet-scan backstop).
- **Absorb rules**: a status signal is benign only when `bin/fm-crew-state.sh`
  proves the crew is still working (an actively running no-mistakes run
  attributed to that crew's current code, or an exact busy verdict). Declared
  external waits (`paused:`) are absorbed on a long recheck cadence (default
  1 h) rather than treated as wedges. No-change heartbeats are benign.
- **Wedge detection**: a provably-working pane left unchanged past
  `FM_STALE_ESCALATE_SECS` (240 s) escalates with a count; at
  `FM_WEDGE_DEMAND_INSPECT_COUNT` (3) the wake carries a
  `demand-deep-inspection` marker — for inspection only, never an automatic
  interrupt. Busy panes are exempt until `FM_BUSY_TURN_MAX_SECS` (1 h).
- **Enqueue-before-suppress**: `.seen-*` markers advance only *after* a wake is
  surfaced or deliberately absorbed, so a watcher killed mid-cycle never
  swallows a signal.
- **Fail-closed backstop**: for push-capable herdr sessions the terminal wait
  uses a native event wait (sub-second `blocked` latency); after 3 consecutive
  failures it reverts to pure polling for the rest of the process.

### 5.2 Busy state is semantic, per adapter (`bin/fm-busy-lib.sh`)

The watcher never guesses "is this worker busy?" from rendered terminal text.
Each converted harness reports its own turn lifecycle through a machine-readable
contract: Pi/pi-signed through the Firstmate-owned extension's `agent_start`/
`agent_settled`, OpenCode through its plugin's `session.status`, Claude through
owned `UserPromptSubmit`/`Stop`/`StopFailure`/`SessionEnd` hooks, Muse through
its session log, Cursor through its conversation transcript. Codex and standalone
Kimi classify `unknown` behind explicit probes; Grok keeps one clearly isolated
rendered-tail fallback scoped to Grok tasks only.

Verdicts are `busy | idle | unknown | dead` **with the producing source
attached**. Missing, malformed, stale, or untrusted semantic state is `unknown`,
never `idle` — an unreadable worker surfaces for a closer look instead of being
absorbed as still-working or written off as finished. Records are bound to an
incarnation token so an event from a superseded worker is rejected.

### 5.3 The durable wake queue (`bin/fm-wake-lib.sh`)

Actionable wakes are written to `state/.wake-queue` as TSV rows
(`epoch seq kind key payload`) under a queue lock, **after** generation-bound
recovery evidence is published — so an interrupted watcher or handling turn
recovers without losing the record. `bin/fm-wake-drain.sh` presents rows,
prints the exact `WAKE_ACK_REQUIRED` command, and consumes every row up to a
sequence number; retirement of the recovery episode is generation-bound (a
generation mismatch is non-fatal and named). Acknowledgement happens only
*after* handling, so interruption leaves the work durable for idempotent
re-handling.

### 5.4 Turn-end guards: no turn ends blind

Tracked hook integration gives every verified primary harness a push-based
backstop: when work needs supervision and no identity-matched watcher with a
fresh beacon is live, the harness is prevented from ending its turn silently.

- **Claude**: `Stop` hook (`fm-turnend-guard.sh --claude`) plus the `asyncRewake`
  hook `bin/fm-claude-stop-autoarm.sh`, which claims one home-scoped cycle,
  foregrounds the arm wrapper, and translates actionable closes into exit-2
  rewakes — all tokenless.
- **Grok**: `Stop` hook → `bin/fm-turnend-guard-grok.sh`; a typed `stopHookActive`
  capability decides native support vs the guarded `grok --resume` fallback.
- **Pi / pi-signed**: TypeScript extensions (`fm-primary-turnend-guard.ts`,
  `fm-primary-pi-watch.ts`) fire on `agent_settled`, force one bounded follow-up
  with `deliverAs:"followUp"`, and verify one successor watcher before
  delivering a wake.
- **Codex**: `Stop` hook blocks directly (exit 2); continuity via bounded
  foreground checkpoints (`fm-watch-checkpoint.sh`).
- **OpenCode**: TUI plugin listens for `session.idle` and calls
  `client.session.promptAsync` once for the guarded follow-up.
- **Cursor**: its stop hook cannot block, so `fm-turnend-guard-cursor.sh`
  *parks* the turn boundary on the watcher (zero tokens while parked) and
  returns at most one bounded `followup_message`, with a generation baton so an
  older park stands down when a newer stop claims the cycle.

The pull-based `bin/fm-guard.sh` warns through supervision tool output about
three independent hazards: the **worktree tangle** (primary checkout on a named
non-default branch), a **watcher down** (needed but not provably healthy), and
**queued wakes pending** drain. It always exits 0 — it warns, never blocks.

### 5.5 Away mode (`/afk`)

When the captain walks away, `/afk` writes `state/.afk` and starts a
sub-supervisor daemon (`bin/fm-supervise-daemon.sh`). The watcher reverts to
one-shot mode; the daemon drains and classifies every wake in bash, self-handles
routine signals/stales/heartbeats, and batches captain-relevant escalations
into one single-line digest injected into the captain pane with the canonical
`away-supervisor` operational-input kind (prefixed with U+2063 so it can never
be confused with a real message). Injection is heavily guarded: the pane must
be affirmatively empty per the shared composer classifier, or the escalation
defers. Delivery failure past `FM_MAX_DEFER_SECS` triggers a configurable
active alert (config/wedge-alarm). On return, `bin/fm-afk-return.sh` performs
ordered shutdown and gates ordinary work behind a durable catch-up record until
every live firstmate-actionable blocker is closed.

## 6. Task lifecycle: from request to shipped work

### 6.1 Intake and routing

The intake contract is agent judgment on top of script mechanics (`AGENTS.md`
section 7): resolve the project (explicit wins, follow-up inherits, else the
registry/work-under-way/code match; one concise question on ambiguity), classify
the deliverable — **ship** (default, changes the project) vs **scout**
(investigation/diagnosis/planning/audit, produces `data/<id>/report.md`, never
a PR), and decide the delivery mode + yolo posture per task. The scripts
"refuse to guess": `fm-brief.sh`, `fm-spawn.sh`, and `fm-promote.sh` all
require explicit `--mode` and `--yolo` for ship work and refuse mismatches
between the brief's fixed `Delivery contract: mode=<mode>` line and the spawn
arguments.

Delivery modes (the project's selected path owns its rigor):

- **no-mistakes** — the crewmate commits, then drives the full no-mistakes
  validation pipeline (`no-mistakes axi run`/`respond` are the worker's calls,
  never firstmate's) through PR and green CI. Ask-user findings return as
  `needs-decision` and are never answered by the implementation worker; the
  first mate decides only under the configured authority (yolo on = routine
  gates within accepted intent; yolo off = captain owns every finding) and
  sends the exact decision with `--resolve-key`.
- **direct-PR** — the worker pushes and opens a PR without the pipeline; the
  configured merge authority decides.
- **local-only** — the worker stops with a clean branch `fm/<id>`, never
  pushes; after approval, firstmate lands it through the one sanctioned
  state-changing path: `bin/fm-merge-local.sh`, a clean fast-forward onto the
  project's default branch only.

Merge authority: with yolo off, the captain owns every merge; with yolo on,
firstmate merges only green work through `bin/fm-pr-merge.sh` (which first
records `pr=`/`pr_head=` through `fm-pr-check.sh` and arms the byte-static
merge poll). Never merge a red PR; standing yolo cannot authorize that.

### 6.2 The brief (`bin/fm-brief.sh`)

`data/<id>/brief.md` is the worker's safety contract: the worktree-isolation
assertion (`pwd -P` and `git rev-parse --show-toplevel` must prove the task
worktree, or STOP with `blocked:`), the delivery-mode-shaped definition of done
with its fixed machine-readable line, the sparse status protocol (`working:`,
`needs-decision:`, `blocked:`, `paused:`, `done:`, `failed:` — one append-only
line per supervisor-actionable event, with keyed decisions closed only by a
matching `resolved [key=...]:` line), and the project-memory rule
(`fm-ensure-agents-md.sh`).

### 6.3 The spawn validation sequence (`bin/fm-spawn.sh`)

`fm-spawn.sh` (136 KB — the largest script) validates in a strict order:
gate-agent refusal (exit 3 — a no-mistakes gate agent can never drive the
fleet), guard, flag validation (ship needs mode+yolo; refused on scouts),
relaunch contradiction checks, remote-secondmate preflight, task-set and
per-task locks, backend resolution (explicit flag > env > `config/backend` >
runtime auto-detection > tmux default), kind identity resolution (secondmate
homes must be valid isolated homes), brief/spawn delivery agreement, harness
resolution (explicit > raw command > `config/secondmate-harness` /
`config/crew-harness` / own; dispatch profiles require an explicit harness),
endpoint/worktree creation per backend, the **worktree isolation assertion**
(real worktree root distinct from the primary checkout — a failed assertion
stops the task), **base freshness** (fetch origin tip; dirty worktree or
unreachable origin refuses), per-harness turn-end wiring and busy-state
arming, meta publication (including the `spawn_gen` incarnation token), and
the literal launch with harness-specific flags (e.g. Claude
`--dangerously-skip-permissions`, Cursor `--trust --yolo --workspace <wt>`,
never `-w` which would allocate a second worktree).

Optional **dispatch profiles** (`config/crew-dispatch.json`) let the captain
steer which harness/model/effort handles which kind of task via natural-language
rules; firstmate resolves profile arrays against one `quota-axi --json`
snapshot through the `quota-array-dispatch` skill and passes only concrete axes
to spawn.

### 6.4 Data plane vs control plane

- **`bin/fm-send.sh`** is the data plane: text the worker should read. It
  resolves the target without guessing (exact task id from meta, else recorded
  window), types the message exactly once, retries only the Enter submit until
  the backend confirms composer-empty, and refuses loudly on any other verdict.
  For secondmate targets it wraps messages in the routing-marked
  `from-firstmate` carrier and records a pending-reply expectation before
  delivery. `--resolve-key` closes a keyed decision *at answer time*, in this
  home's own ledger, only after delivery is fully confirmed — a failed send
  never closes a key.
- **`bin/fm-control.sh`** is the control plane: a closed allowlist of
  `interrupt | exit | relaunch` addressed to an exact task id, with per-harness
  mechanics owned by `fm-control-lib.sh` and verified postconditions per verb
  (e.g. `exit` proves the agent is `dead` from a recovery-grade classifier
  before reporting success). `relaunch` is transactional (journaled phases,
  rollback trap, required progress note for ship/scout). `resume` is
  deliberately not a verb.

The split exists because a lifecycle command sent through the data plane
arrives as chat the agent reasons *about* instead of executing.

### 6.5 Judging the run: `bin/fm-crew-state.sh`

The current-state read is deterministic and never trusts the last status line.
For no-mistakes work the **run step** is authoritative — a run is attributed to
the crew only when its branch and code identity match the worktree (pipeline
fix commits may advance the run head). `running`/`fixing`/`ci` → working
(while in `ci`, a checks-green log marker flips the verdict to done);
`awaiting_approval`/`fix_review` → parked with gate findings; terminal
passed/checks-passed → done; failed/cancelled → failed. Without a run, it
falls back to pane busy state, then to the status log.

### 6.6 PR ready, landing, teardown

- The ready signal is mode-shaped: `done: PR <url> checks green` (no-mistakes,
  after CI is green) vs `done: PR <url>` (direct-PR). Firstmate runs
  `fm-pr-check.sh` to record `pr=` and arm the static merge poll, then tells
  the captain the full URL.
- **Teardown (`bin/fm-teardown.sh`) is fail-closed**: the worktree must be
  clean; committed work must be *landed* — reachable from a remote-tracking
  branch, contained in a merged PR head (with patch-id comparison covering
  squash-merge-then-delete flows), or content-equal to the fetched default
  branch. Uncommitted changes are never landed. A teardown refusal is a
  stop-and-investigate result, never an obstacle to bypass; `--force` requires
  explicit discard authority. Scout teardown additionally requires the report
  to exist and the decision-hold completion gate to pass.
- **Scout promotion**: `bin/fm-promote.sh` promotes a scout in place (keeps
  window/worktree/context), rewriting its meta to `kind=ship` with an explicit
  mode+yolo; the worker resets to a clean base, carries over only intended
  changes, and turns a reproduced bug into the regression test.

## 7. Runtime backends

The runtime backend is the session-provider layer below the scripts. Selection
precedence: explicit `--backend` > `FM_BACKEND` env > `config/backend` > runtime
auto-detection (innermost-first: `$TMUX` > `HERDR_ENV=1` > cmux markers;
zellij and orca are never auto-detected) > tmux default. `fm-backend.sh`
centralizes selection and dispatch; `bin/backends/*.sh` are the adapters.

| Backend | Status | Owns | Worktrees | Notes |
| --- | --- | --- | --- | --- |
| tmux | verified reference | session endpoints only | treehouse | recovery-grade agent-state classifier |
| herdr | experimental | tabs per task, workspace per home | treehouse | native busy state + push events; secondmates OK |
| zellij | experimental, explicit only | tabs per task | treehouse | no recovery-grade classifier |
| orca | experimental, macOS, explicit only | terminal **and** worktree | orca itself | no Escape key; no secondmates |
| cmux | experimental, macOS GUI | workspaces per task | treehouse | auto-detectable; no secondmates |

`codex-app` is deliberately not a backend (no shell-callable bridge today; a
status-return channel is a mandatory acceptance contract if it ever ships).

## 8. Secondmates: persistent direct reports

For larger fleets the captain can opt into **secondmates**: persistent agents
that are still ordinary direct reports but run from their own isolated firstmate
homes with their own `FM_HOME`, state, backlog, projects, and session lock.

- **Seeding** (`bin/fm-home-seed.sh`) is transactional: registry validation,
  home acquisition (durable treehouse `--lease` or a fresh clone), project
  clones from the source's origin URL, charter copy, markers written in order
  (`.fm-secondmate-parent` before `.fm-secondmate-home`), and full rollback on
  any failure (refusing unsafe targets like `/`, the active home, or nested
  paths).
- **Routing** (`data/secondmates.md`) records local routes (`home: <abs>`) and
  remote routes (`host: <ssh-alias>; root: <abs>; home: <abs>`). The registry
  is strictly validated (no duplicates, no overlap, safe SSH aliases) and
  serialized under its own lock.
- **Remote homes** place the entire home on an SSH-reachable host. Commands
  travel through a firstmate-owned job worker on the remote account (queue
  with bounded payloads, `env -i` children, filesystem-discovered PATH,
  LaunchAgent-managed) rather than raw SSH; the doctor
  (`bin/fm-remote-doctor.sh`) checks and repairs readiness without ever
  installing packages or creating login sessions. SSH exit 255 means
  "completion unknown" — never blindly retried, never failed over to a local
  replacement.
- **Idle by default**: a secondmate reconciles only work already in its own
  home and then waits silently; an empty queue never authorizes self-initiated
  work. The main firstmate routes in-scope work to it and never reads its chat —
  marked requests return through the status stream with a parent-owned
  pending-reply correlation record (`state/pending-replies/`, keyed escalation,
  exactly one automatic repost, then escalate).
- **Retirement** is explicit and refuses while the home has in-flight work,
  unless the captain authorizes discard with `--force`.

## 9. Relay: opt-in public mentions

`FMX_PAIRING_TOKEN` in the gitignored `.env` activates Relay: the fleet can
answer public mentions of `@myfirstmate` on X and Discord. Without the token,
Relay artifacts are removed and nothing changes.

- A poll (`bin/fm-x-poll.sh`) runs as a byte-static check shim at a 30 s
  cadence; new offers are stashed in `state/x-inbox/<request_id>.json` and wake
  the first mate once per retained request.
- `fmx-respond` (agent-only skill) classifies each mention as actionable
  request, question, or pure acknowledgment, then replies, dismisses, or links
  a spawned task (`fm-x-link.sh`).
- Completion follow-ups: up to 3 public-safe posts within a 7-day window
  (`fm-x-followup.sh`), ending with `--final`. A **promised final reply** is a
  typed durable obligation owned by `tasks-axi public-followup` +
  `fm-public-followup.sh` — never conversation memory, never recovered by
  parsing a `done:` sentence.
- `FMX_DRY_RUN` records would-be replies in `state/x-outbox/` without posting.
- Destructive, irreversible, or security-sensitive asks are never executed
  from a public mention — they escalate to the trusted channel.

## 10. Fleet sync and self-update

- **`bin/fm-fleet-sync.sh`** keeps project clones fresh: fetch + fast-forward
  only, never force/stash/discard; self-heals exactly one drift (clean detached
  HEAD with no unique commits → re-attach and fast-forward); everything else
  reports a quantified `STUCK:` line and is left untouched. It prunes local
  branches whose upstream is gone (only when no worktree holds them) and
  recovers a provably-stale `packed-refs.lock` (age + no lsof holder). Called
  from locked session start, merged-PR wake handling, and teardown.
- **`/updatefirstmate`** (`bin/fm-update.sh` + `bin/fm-ff-lib.sh`, the one
  fast-forward implementation) advances the running repo and every secondmate
  home from origin — fast-forward only; dirty/diverged/offline targets are
  reported and left untouched; gitignored operational dirs are never touched;
  then it re-reads instructions and nudges secondmates.

## 11. Bearings and fleet snapshot

`bin/fm-fleet-snapshot.sh --json` emits the schema `fm-fleet-snapshot.v1`
structured contract from the backlog, task metadata, current crew state,
endpoint probes, PR/report pointers, scout reports, bounded secondmate home
summaries, and secondmate return-channel guidance. `fm-fleet-view.sh` renders
it as Markdown; `bin/fm-bearings-snapshot.sh` projects it to the compact
bearings view (`/bearings`) — local-only by default, with `--include-prs` as
the sole network path. Cross-home reads are bounded (timeouts, byte caps,
record limits) and classify unreadable state as `unknown`, never guessing.

## 12. Knowledge management

Durable knowledge routes to its most specific owner: captain preferences to
`data/captain.md`, cross-home preferences to the primary's `data/captain-shared.md`
(propagated read-only), fleet-local facts to `data/learnings.md`, task-scoped
notes to the backlog, project-intrinsic knowledge to the project's committed
`AGENTS.md` (via crewmates and `fm-ensure-agents-md.sh` — firstmate never
writes a project's AGENTS.md directly). `/stow` sweeps the session for
uncaptured durable knowledge, curates tiered startup memory (aging/perishable/
pinned markers, decay, cold archive, per-home budget), and cascades to
secondmates. Process-event sources (`bin/fm-procevent.sh`,
`fm-procevent-when.sh`) let registered deterministic condition→action watches
run trust-bound actions (e.g. "notify when X") with exactly-once fire markers
and terminal outcome documents.

## 13. Safety and authority model

- **Hard rules** (priority order): never write to a project (except guarded,
  captain-approved operations); never merge without the captain's explicit
  word (yolo is the only standing relaxation); never tear down unlanded work;
  crewmates never address the captain; report outcomes faithfully.
- **Captain instruction precedence**: a current, explicit, concrete captain
  instruction overrides any conflicting standing rule — exactly as stated, no
  inference, no analogy, no standing conversion. Destructive/irreversible/
  security-sensitive/discard/merge actions still require the concrete statement.
- **Fail-closed everywhere**: scripts stop safely and report when the world
  surprises them (locked sessions go read-only; unreadable state is `unknown`
  not `idle`; unresolved targets refuse; failed sends never close decisions;
  gate agents exit 3 before any fleet mutation; PR polls stay silent on error
  rather than ever misread as merged).
- **Escalation etiquette**: captain-facing language is outcomes and decisions,
  never machinery — worktrees are "isolated copies", watchers are
  "monitoring", status files are "durable records". Batch non-urgent updates;
  reach the captain immediately only for review-ready work, findings,
  decisions, blockers, and anything destructive or credential-related.

## 14. The repo's own discipline

- **Two-tier skills**: `.agents/skills/` holds firstmate-loaded internal skills
  (each `metadata.internal: true` so public installers hide them; five are
  captain-invocable — `/afk`, `/ahoy`, `/bearings`, `/updatefirstmate`,
  `/stow` — the rest are agent-only reference skills loaded at precise triggers
  listed in AGENTS.md section 13); `skills/` holds standalone public skills
  with no firstmate dependency (today: `skills/stow`).
- **Harness adapters** are verified empirically: a new adapter earns its way in
  by a supervised test spawn; every fact lands in exactly one owner (launch
  mechanics in `fm-spawn.sh`, busy semantics in `fm-busy-lib.sh`, composer
  shapes in the one shared `fm-composer-lib.sh`, control keys in
  `fm-control-lib.sh`).
- **Tests**: `bin/fm-test-run.sh` is the single behavior-test runner owner —
  portable lanes for CI (parallel + serial shards with a coverage guard proving
  the lanes partition the full `tests/*.test.sh` inventory), a proven-isolated
  set for local `--jobs`, live-harness opt-in tests env-gated and self-skipping,
  and a real-Herdr CI lane. Tests exercise behavior through public interfaces,
  never assert implementation-source bytes.
- **CI** (`.github/workflows/`): lint (pinned ShellCheck via `bin/fm-lint.sh`),
  coverage check, parallel/serial/herdr test lanes, macOS stock-bash checks,
  symlink invariants (CLAUDE.md → AGENTS.md, `.claude/skills` →
  `.agents/skills`), and the no-mistakes gate: every human PR to main must
  carry the `git push no-mistakes` marker.
- **Toolchain**: the axi family (`gh-axi`, `tasks-axi`, `quota-axi`,
  `lavish-axi`, `chrome-devtools-axi`), no-mistakes (floor v1.31.2), treehouse
  (worktree pool), and backend CLIs. Version floors are owned by
  `fm-bootstrap.sh` and never argued down.
- **One-owner rule**: every contract (data format, state machine, decision
  procedure) is stated in full exactly once; every other mention is a one-line
  cross-reference. Restatement is a defect.
- **Verification records**: `docs/verification/` holds dated, version-scoped
  evidence with refresh commands; current behavior lives in the linked guides.

## 15. Quick reference: key files

| File | Role |
| --- | --- |
| `AGENTS.md` | The first mate's entire job description (CLAUDE.md is a symlink) |
| `VISION.md` | Product direction: peace of mind, explicit authority, restart-proof |
| `docs/architecture.md` | Human-facing companion to AGENTS.md, in depth |
| `docs/scripts.md` | Script-by-script toolbelt map |
| `docs/configuration.md` | Single owner of layout and config schemas |
| `bin/fm-session-start.sh` | One-shot session-start digest (9 ordered steps) |
| `bin/fm-watch.sh` | Zero-token always-on watcher |
| `bin/fm-wake-drain.sh` | Presents durable wakes + OPEN DECISIONS |
| `bin/fm-classify-lib.sh` | Wake vocabulary and keyed-decision folds |
| `bin/fm-busy-lib.sh` | Semantic busy-state contract |
| `bin/fm-crew-state.sh` | Deterministic current-state read |
| `bin/fm-spawn.sh` | Spawn validation sequence + launch |
| `bin/fm-brief.sh` | Task brief scaffold (safety contract) |
| `bin/fm-send.sh` | Data plane: verified literal text sends |
| `bin/fm-control.sh` | Control plane: interrupt/exit/relaunch |
| `bin/fm-teardown.sh` | Fail-closed teardown with landed-work proofs |
| `bin/fm-merge-local.sh` | The one sanctioned local merge path |
| `bin/fm-pr-merge.sh` / `fm-pr-check.sh` / `fm-pr-poll.sh` | PR metadata + merge poll |
| `bin/fm-home-seed.sh` | Transactional secondmate provisioning |
| `bin/fm-supervise-daemon.sh` | Away-mode sub-supervisor |
| `bin/fm-bearings-snapshot.sh` | Bearings projection (local-only default) |
| `bin/fm-fleet-sync.sh` / `fm-update.sh` | Clone refresh / self-update |

## 16. Further reading

- `docs/architecture.md` — full architecture (supervision, backends, delivery modes, Relay).
- `docs/turnend-guard.md`, `docs/watcher-continuity.md` — the no-blind-turns backstop.
- `docs/remote-secondmates.md` — whole-home remote secondmates.
- `docs/verification/` — version-scoped maintainer evidence.
- `CONTRIBUTING.md` — how to run the tests and contribute.
