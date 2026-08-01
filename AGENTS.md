# AGENTS.md

Conventions not obvious from the file tree:

- **Grounding.** Use `VISION.md` for product direction; new work must answer the three questions in its "How to use this vision" section.
- **Compound Engineering (CE) plugin in use.** `.compound-engineering/config.local.yaml` is the active local config and is intentionally gitignored (per-checkout); `.compound-engineering/config.local.example.yaml` is the tracked template. Never commit `config.local.yaml`.
- **`docs/` is the CE artifact root** (plans, solutions, explainers, etc.). `tmp/` is a gitignored scratch space; use it for scratch work when possible.
- **Proof sync.** Some markdown files are published to Proof. Their frontmatter carries `proof_url` (shareable, tokenized link) and `proof_slug`; the matching `accessToken`/`ownerSecret` live in `tmp/proof-state.json` (gitignored, per-checkout). The local file stays canonical. When you edit a file that has a `proof_url`, push the update to its Proof doc using `POST /api/agent/{proof_slug}/v3/edit` with `set_document` (whole-doc) or narrow `replace` ops, authenticated with the `accessToken` from `tmp/proof-state.json` and `X-Agent-Id: ai:compound-engineering` (`by: ai:compound-engineering`). Read the doc first (`GET /api/agent/{slug}/v3/document`) and use its `revision` as `baseRevision`. Never commit tokens or owner secrets to the repo. To publish a new doc, use `/ce-proof` and record the result in both frontmatter and `tmp/proof-state.json`.
