---
lorespec: "0.1"
id: "2026080401"
date: "2026-08-04"
source: "opencode"
topic: "Rename 'record home' to 'record source' and settle proxy/workspace terminology across the workstream registration plan and live docs"
tags: [terminology, record-source, workstream-registration, data-governance, docs-rename]
classification:
  type: drafting
  secondary_type: technical
  domains: [workstream-registration, data-management-terminology]
  value: high
trails: [workstream-registration-planning, record-source-terminology]
---

## Session Arc

### Started
User asked to read prior review session `ses_0360518d9ffen0p4SnRPWB6Nk5` (anti-sycophancy review of the workstream registration plan) and apply the terminology changes from its review notes, excluding the register/unregister item.

### Pivots
- **Term selection opened:** after proposing options for replacing "record home", the user asked for alternate terms, then grounded the choice by asking how the term is used and what values are stored under it (marker `{type, uri}` pairs, CLI `--record-home <type>=<uri>`, redaction boundary language).
- **Data classification lens:** user asked what data classification says about the data; repo has no formal taxonomy, so a web search surfaced the source-classification taxonomy (SoO/SoR/SoRf/SoT) and the data-vault meaning of "record source" (lineage/provenance).
- **Term confirmed:** user chose "record source" with the proposed definition ("authoritative location where a workstream's records are maintained — provenance of the workstream's truth"), scoped to the plan, CONCEPTS.md, and VISION.md, then extended to three live docs (RAID, research, solution).

### Ended
Rename applied across 6 files, decision recorded in the plan's 2026-08-04 operator decision section, and the user committed the work (`6b965de "docs: standardize record source and proxy workspace terminology"`). Wrap-up: digest saved, git confirmed clean, solution compounded.

## ARTIFACTS

### A1. Repo-wide "record source" terminology rename
- **What:** "record home(s)"/"record-home" renamed to "record source(s)"/"record-source" across: `docs/plans/2026-08-01-001-feat-workstream-registration-discovery-plan.md`, `CONCEPTS.md`, `VISION.md` (16 occurrences), `docs/raid.md`, `docs/research/2026-08-01-workstream-registration-runtime-stack.md`, `docs/solutions/tooling-decisions/runtime-validation-stack-python-jsonschema.md`. Proxy-folder terminology replaced by proxy workspace / regular workspace; marker kind enum `folder|proxy` → `direct|proxy`. "Marker", "point-and-read", "register"/"unregister" retained.
- **Evolution:** decision entry added to the plan's "From the 2026-08-04 operator decision" section ("Terminology settled") so future agents do not treat the renames as drift.
- **Scope notes:** historical artifacts intentionally untouched: `docs/ideation/2026-08-01-arjim-improvement-ideation.md`, `docs/reviews/2026-08-02-001-...-review.md`, archived plan, generated `output-html/` snapshot.
- **Committed:** `6b965de`.

## DECISIONS

### D1. Rename "record home" to "record source"
- **Decision:** The typed URI reference to a workstream's authoritative record location is now called "record source", defined as "the authoritative location where a workstream's records are maintained (in the data-vault sense: the provenance of the workstream's truth)".
- **Issue:** "Record home" was flagged as genuinely opaque in the 08-04 review; no destination term existed.
- **Positions:** record location; home system; record source; authoritative record; keep "record home".
- **Arguments:** "record location" is literal but file-path-flavored; "home system" is clunky in the redaction construction ("home-system URI content"); "authoritative record" misnames the stored value (we store a reference, not the records); "record source" is established (data vault, ETL) and reads cleanly in CLI (`--record-source <type>=<uri>`), field (`record_sources`), prose, and classification-boundary language ("record-source URI content is redacted").
- **Warrant:** The term must work in four registers (concept, marker field, CLI flag, classification-boundary prose), and a stored value that is always a `{type, uri}` reference favors a term naming the pointer. If the marker ever stored record content rather than references, the term should be revisited.
- **Qualifier:** always (within this project).
- **Status:** settled (recorded as 2026-08-04 operator decision in the plan).

### D2. Proxy-folder → proxy/regular workspace terminology; kind enum `folder` → `direct`
- **Decision:** "proxy folder" residue replaced with "proxy workspace" (holds the marker for a workstream whose real location cannot store assistant metadata) and "regular workspace" (where a workstream actually lives); the marker `kind` enum value `folder` becomes `direct`, freezing `direct|proxy` at U1.
- **Issue:** plan already half-used "proxy workspace" (KD2, F3); the enum value `folder` was the residue.
- **Arguments:** renaming the enum before U1 ships costs nothing; after U1 it is a contract change. "Folder" vs "workspace" mismatch confused the metadata-workspace designation.
- **Warrant:** schema enums are cheapest to fix before the first release; terminology should match the CLI (`register <workspace>`).
- **Qualifier:** always (v1).
- **Status:** settled.

### D3. Retain "marker", "point-and-read", "register"/"unregister"
- **Decision:** "marker" is kept (established convention, cf. `.git`, sentinel files); "point-and-read" is kept as internal plan vocabulary that never reaches the operator-facing surface (now defined in CONCEPTS.md); "register"/"unregister" are retained as lifecycle language — the user explicitly excluded them from this work after the review found no destination term.
- **Issue:** the 08-04 review notes asked to reconsider all of these.
- **Arguments:** renaming "register" without a destination term is a change request without a target; "point-and-read" is plan-internal.
- **Warrant:** renaming beats defining only when the rename improves clarity; established convention and internal-only usage do not meet that bar.
- **Qualifier:** usually.
- **Status:** settled.

## INSIGHTS

### I1. Data-management source-classification taxonomy maps cleanly onto the design
The industry taxonomy (Planet Kodiak; Wikipedia/IBM/DMBOK on system of record) classifies data sources as Source of Origin (SoO), Source of Record (SoR — authoritative system), Source of Reference (SoRf — non-authoritative copy), Source of Truth (SoT). Arjim's design maps: record source = SoR, local projection = SoRf, workspace marker = SoT. Caveat: in data vault modeling, "record source" specifically means lineage/provenance metadata (which system loaded a row), i.e., backward-looking; the marker's use is a forward pointer to the authoritative location. Source: web research 2026-08-04. Confidence: high.

### I2. The repo has no formal data classification taxonomy
No Public/Internal/Confidential/Secret tiers exist in `arjim`. The de facto classification is two-tier: record-source URI content and secrets = protected (redacted in previews, no-echo everywhere, never copied to projection); labels and local paths = safe to emit under length caps (downgraded on 2026-08-04). VISION.md §5 is the closest policy: workspaces do not store live credentials; least access needed. Source: repo grep + VISION.md. Confidence: high.

### I3. Terminology decisions must be recorded inside the plan or they get reverted as drift
The 08-04 review flagged that plan decisions marked `session-settled` are treated as authoritative; a rename without a recorded operator decision looks like drift to the next agent. Fix applied: a "Terminology settled (2026-08-04)" entry in the plan's Deferred/Open Questions section. Source: review session `ses_0360518d9ffen0p4SnRPWB6Nk5`. Confidence: high.

## PATTERNS

### P1. Term-fit check before renaming a domain term (local)
Before choosing a replacement term, verify it across: (1) every surface it appears on (concept prose, schema field, CLI flag, diagnostics boundary), (2) the shape of the stored values (here: always a `{type, uri}` reference — the term must name the pointer, not the referent), and (3) classification/redaction-boundary constructions ("___ URI content is redacted"). A term that fails any register reads fine on a slide and wrong in code.

## NEXT_STEPS

### N1. Sync plan and RAID log to Proof (now)
Both `docs/plans/2026-08-01-001-...-plan.md` and `docs/raid.md` carry `proof_url` frontmatter and were edited; run `/ce-proof` to publish the renamed versions. Prompted by: AGENTS.md proof-sync convention.

### N2. Decide whether historical artifacts keep the old term (someday)
`docs/ideation/2026-08-01-arjim-improvement-ideation.md` (10 occurrences) and `docs/reviews/2026-08-02-001-...-review.md` still say "record home". Kept intentionally as dated records; revisit only if a future search for "record source" must find them.

## Connections

- D1 —[led_to]→ A1
- D2 —[led_to]→ A1
- D3 —[related_to]→ D1
- I1 —[informed_by]→ web research; —[informed]→ D1
- I2 —[informed]→ D1
- I3 —[informed_by]→ prior review session `ses_0360518d9ffen0p4SnRPWB6Nk5`
- P1 —[instance_of]→ D1's decision process

## Trail Updates

- **workstream-registration-planning:** extended with 2026-08-04 terminology decisions (supersedes the review-session state of the plan).
- **record-source-terminology:** created by this session.
