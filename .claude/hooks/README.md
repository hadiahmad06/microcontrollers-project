# guard_docs.py

PreToolUse hook (registered in `.claude/settings.json`) enforcing AGENTS.md section 3 folder rules.

## What it enforces
- `docs/archive/**`: never writable.
- `docs/human/<slug>/**` and `docs/agent/<slug>/**`: writable only when `<slug>` equals your `ME`.
  If `ME` is unset or not a valid slug, these folders are blocked.
- Everything else (code, top-level `docs/human/*.md`, `docs/agent/*.md`): allowed.
- Valid slugs: `hadi`, `emanuel`, `david-li`, `david-leh`.

Blocking = exit code 2 with a one-line reason on stderr. Bad/empty stdin = warning and exit 0 (fail open).

## Setting ME
Each teammate creates their own, git-ignored `.claude/settings.local.json`:
```json
{"env": {"ME": "your-slug"}}
```
Alternatively export `ME=your-slug` in the shell (takes precedence).

## Bash limitation
Bash checking is a best-effort heuristic: it blocks commands that mention a forbidden
`docs/...` path AND contain a write-like operation (`>`, `tee`, `sed -i`, `mv`, `cp`, `rm`,
`touch`, python `open(..., 'w')`, ...). It can be bypassed (variables, `cd` then relative paths,
scripts, globs, encoded commands). Reads (cat, grep, ls, git diff) pass.

## Manual test
```sh
export CLAUDE_PROJECT_DIR="$PWD" ME=hadi
echo '{"tool_name":"Write","cwd":"'$PWD'","tool_input":{"file_path":"docs/human/david-li/x.md"}}' \
  | python3 .claude/hooks/guard_docs.py; echo $?   # prints reason, 2
```
