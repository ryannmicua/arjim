# AGENTS.md

Conventions not obvious from the file tree:

- **Grounding.** Use `VISION.md` for product direction; new work must answer the three questions in its "How to use this vision" section.
- **Compound Engineering (CE) plugin in use.** `.compound-engineering/config.local.yaml` is the active local config and is intentionally gitignored (per-checkout); `.compound-engineering/config.local.example.yaml` is the tracked template. Never commit `config.local.yaml`.
- **`docs/` is the CE artifact root** (plans, solutions, explainers, etc.). `tmp/` is a gitignored scratch space; use it for scratch work when possible.
