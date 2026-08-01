# AGENTS.md

Conventions not obvious from the file tree:

- **Grounding.** Use `VISION.md` for product direction; new work must answer the three questions in its "How to use this vision" section.
- **`docs/` is the CE artifact root** (plans, solutions, explainers, etc.). `docs/solutions/` is a searchable store of documented solutions to past problems and decisions, organized by category with YAML frontmatter (`module`, `tags`, `problem_type`); relevant when implementing, debugging, or deciding in documented areas.
- **`tmp/`** is a gitignored scratch space; use it for scratch work when possible.
- **`CONCEPTS.md`** is the shared domain vocabulary glossary (entities, named processes, status concepts); relevant when orienting to the codebase or discussing domain concepts.
- **Proof sync.** Some markdown files are published to Proof — see frontmatter `proof_url`/`proof_slug`. Tokens live in `tmp/proof-state.json` (gitignored). Never commit tokens. Use `/ce-proof` to publish or sync; the skill owns the mechanics.
