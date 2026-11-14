# AI usage log

Course requirement (EE 2361): list every piece of AI-written code. In the source, AI-written
code is wrapped in `[AI-GENERATED: …]` / `[END AI-GENERATED]` markers. This log only
separates agent from human (docs/human/TEAM_PROCESS.md). Git history shows which agent and
which person.

| File | Function | What it does | Date | Author |
|------|----------|--------------|------|--------|
| .claude/hooks/guard_docs.py | `project_root` | Finds the project root from CLAUDE_PROJECT_DIR or the script location | 2026-11-14 | agent |
| .claude/hooks/guard_docs.py | `resolve_me` | Works out which person the agent is acting for, from the ME env var or settings.local.json | 2026-11-14 | agent |
| .claude/hooks/guard_docs.py | `check_path` | Blocks file-tool writes to other people's docs folders and to docs/archive | 2026-11-14 | agent |
| .claude/hooks/guard_docs.py | `check_bash` | Heuristic that blocks shell commands writing to forbidden docs paths | 2026-11-14 | agent |
| .claude/hooks/guard_docs.py | `main` | Hook entry point: reads JSON from stdin, exits 2 to block; on bad input it allows and warns | 2026-11-14 | agent |
