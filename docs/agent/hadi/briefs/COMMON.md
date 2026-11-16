<!-- [AI-GENERATED: Claude Code] -->
# Common brief rules (every Sprint 6 subagent reads this first)

**Working for: hadi** (Hadi Ahmad). You are a subagent of Hadi's main agent (the scrum master).
Hadi is offline: never wait for him; report questions back to the main agent instead.

## Paths
- Repo: your worktree (the current directory when you start). Use quoted absolute paths with `cd`, and check the `cd` worked
  before writing output files.
- You may write ONLY the paths listed under "Allowed write paths" in your ticket brief. Everything else is read-only.
- **Forbidden:** `docs/human/**`, every top-level doc (`docs/agent/*.md`, `docs/human/*.md`), `AI_USAGE.md`, other people's
  folders (`docs/*/emanuel/**`, `docs/*/david-li/**`, `docs/*/david-leh/**`), `docs/archive/**`.
- Commit your work on your worktree branch (several small commits are fine) as
  `git -c user.name="Hadi Ahmad (Claude)" -c user.email=hadiahmadv@gmail.com commit ...` with these trailer lines at the end of
  the message:
  ```
  Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
  ```
  Do not push. Do not merge. The main agent merges.

## AI-marking rule (AGENTS.md §7, word for word)
**Marking AI-written code**
- Wrap all AI-written code like this:
  ```c
  // [AI-GENERATED: Claude Code]
  ...
  // [END AI-GENERATED]
  ```
  Use the actual tool's name.
- If a human later edits inside the block, keep the markers.

(Python and Makefiles use `# [AI-GENERATED: Claude Code]` / `# [END AI-GENERATED]`; Markdown uses
`<!-- [AI-GENERATED: Claude Code] -->` / `<!-- [END AI-GENERATED] -->`. Every line you write sits inside a block,
including shebangs only if you can: a shebang must be line 1, so put the opening marker on line 2.)

## Code rules (AGENTS.md §7)
- Cite borrowed code (reference drivers, app notes, our own spikes) in a comment.
- Every public function needs a doc comment covering its purpose, each argument, and the return value.
- C: C99, one `.c`/`.h` pair per module, fixed-width types (`int16_t`, `int32_t`) everywhere (XC16's `int` is 16 bits),
  no `float`/`double` in firmware, no `malloc`, no blocking delays in library code. Comment every register write.
- Firmware headers are on the `-iquote` path only; include them as `"x.h"`.
- Python: python3 + numpy only (numpy 2.x is installed). No new third-party dependency unless the ticket says so.
- Code built on an open question carries in its header comment: `WORKING ASSUMPTION: open_questions Qn, not decided`
  (see `docs/agent/WORKING_ASSUMPTIONS.md`).

## Budget and stop conditions (prevents rumination)
- Work in small verified steps. Aim to finish in about 60 tool calls. If the same problem resists two honest attempts,
  stop and report it instead of trying a third way.
- **Stop and report back (do not improvise)** if: the spec is ambiguous or self-contradictory; a test needs a file outside
  your allowed paths; a value is missing from the spec; the existing code disagrees with the spec.
- Do not read large unrelated files. Read only what your ticket names plus what you need to call.

## Report format (your final message)
1. Files changed (paths) and commits (hashes) on your branch.
2. Functions added (file | function | one-line purpose), so the main agent can fill `AI_USAGE.md`.
3. The acceptance command(s) you ran and their last ~15 lines of output.
4. Open questions / spec ambiguities / deviations, each in one or two lines.
Keep the report under 60 lines.
<!-- [END AI-GENERATED] -->
