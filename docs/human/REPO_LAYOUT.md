# Repository layout

Shared top-level decision. Edits follow AGENTS.md §5.

## Where code lives
Product code lives in `firmware/src/` (one `.c`/`.h` pair per module), host tests in
`firmware/test/`, Python tools in `tools/` (`features_ref`, `infer_ref`, `export_model`,
recorder); spikes stay in `docs/agent/hadi/spikes/`.
- Decided: 2026-11-14 by Hadi. Not contested.
