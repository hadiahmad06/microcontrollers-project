# AGENTS.md: rules for every AI agent in this repo

These rules apply to every AI agent working here: Claude Code (the main session **and every
subagent**), Codex, Copilot, and any other tool. If a rule is unclear, **stop and ask the
human you are working for**. Don't guess.

Team-level decisions live in `docs/human/*.md`. Read `docs/human/TEAM_PROCESS.md` first.

---

## 1. Know who you are working for

Every session works on behalf of exactly one **person**. Use these slugs:

| Person                   | Slug        |
|--------------------------|-------------|
| Hadi Ahmad               | `hadi`      |
| Emanuel Banderas-Infante | `emanuel`   |
| David Li                 | `david-li`  |
| David Leh                | `david-leh` |

- Never use a bare `david`. There are two Davids.
- If the person hasn't been named at the start of a session, **ask**.
- Don't infer the person from the OS username or from file paths.
- A subagent works for the same person as the agent that started it. The parent agent puts
  the slug in the brief (see §6).

Below, `{me}` means the slug of the person you are working for.

---

## 2. Docs layout

```
docs/
├── human/
│   ├── *.md          ← TOP-LEVEL: team decisions (see §5)
│   └── {person}/     ← one person's explicit statements and decisions (their log)
└── agent/
    ├── *.md          ← TOP-LEVEL: agent docs the team works from (plans, contracts, specs)
    └── {person}/     ← an agent's working notes for one person, including its sprint board
└── archive/          ← original source files (overview, proposal). Read-only reference: don't edit
```

---

## 3. Permissions

**Reading:** allowed anywhere in the repo.

**Writing** means creating, editing, renaming, moving, or deleting a file.

| Path                          | Can your agent write here?                                     |
|-------------------------------|----------------------------------------------------------------|
| Code, tools, tests, and anything outside `docs/` | **Yes.** Everyone owns everything. Git records who changed what. |
| `docs/agent/{me}/**`          | **Yes, at any time.**                                          |
| `docs/human/{me}/**`          | **Only to record an explicit statement or decision by `{me}`** (see §4). |
| `docs/human/*.md`, `docs/agent/*.md` (top level) | Only under the rules in §5.                 |
| `docs/*/{someone-else}/**`    | **Never.** Not even to fix a typo.                             |

Only the main agent, the one talking directly to the human, may write to `docs/human/` or
to top-level docs. Subagents never do: they don't hear the human, so they can't judge whether
a statement was explicit.

---

## 4. What counts as "explicit"

**It counts as explicit when** `{me}` does one of these:
- states a decision or fact in their own words ("We're using I2C1"), or
- answers **yes** to a direct question that quotes the exact wording to record.

**It does not count when** it is:
- a question
- brainstorming, or phrased with "maybe", "I think", or "probably"
- a bare "ok" or "sure" in reply to a long agent message
- something you inferred
- a decision `{me}` says *someone else* made. That is secondhand, so note it in
  `docs/agent/{me}/` as a report instead.

If you're not sure, ask in one line:

> Record this as your decision? → "<exact wording>" (yes/no)

**Personal log format** (`docs/human/{me}/DECISIONS.md`): append only. To change a decision,
add a new entry that supersedes the old one.

```
## YYYY-MM-DD: <short title>
- Statement: "<exact words, or the wording they confirmed>"
- Context: <one line>
- Supersedes: <earlier entry title, or "none">
```

---

## 5. Top-level docs and conflicts

**Check every explicit statement or decision from your human against all top-level docs**
(`docs/human/*.md` and `docs/agent/*.md`). Do this whether or not you're about to record it.
It must be up to date (`git pull` first, once git exists).

### A. No conflict
1. Record the decision in `docs/human/{me}/DECISIONS.md`.
2. Write it directly into the right top-level file. Create the file if it doesn't exist yet.
   Name it by topic, e.g. `TRAINING_PIPELINE.md`.
3. Add a provenance line under the entry:
   `- Decided: YYYY-MM-DD by <Name>. Not contested.`

### B. Conflict
Tell the human at once, before doing anything else, in this format:

> ⚠️ **Conflicts with a top-level doc.**
> You said: "<their words>"
> `docs/human/X.md` says: "<quoted line>" (decided <date> by <name>)
> Options: **(1) Overrule** (treat it as a trivial conflict and I'll update the top-level doc), or **(2) Discuss** with the team first.

- **Overrule:**
  1. Update the top-level entry.
  2. Keep the old text as `- Previously: "<old text>" (<date>, <name>). Overruled YYYY-MM-DD by <Name>.`
  3. Record the decision in their personal log.
- **Discuss:**
  1. Leave the top-level doc untouched.
  2. Record the statement in their personal log, marked `Status: conflicts with <file>; pending team discussion`.
  3. Add the item to `docs/agent/{me}/open_questions.md`.

**Also flag conflicts** with `docs/archive/proposal.pdf` or `docs/archive/INITIAL_OVERVIEW.md`. They aren't top-level
docs, but they are what the course and the team last saw. Mark these as an FYI, not a
blocker.

---

## 6. Subagents are employees: run them SCRUM style

The main agent is the **team lead / scrum master** for its subagents. Subagents are not
throwaway contractors.

**Defaults**
- Use **Sonnet 5.5, medium effort** for well-scoped work.
- Design decisions, and anything that touches a top-level doc, stay with the main agent and the human.

**Sprint board**
- Keep the board in `docs/agent/{me}/BOARD.md`. Update it every time a subagent is assigned
  work, reports back, or gets blocked.
- Each subagent gets a stable **name** (e.g. `impl-features`, `test-mlp`, `review-1`). Reuse
  the same subagent for follow-ups on its own work (`SendMessage`) instead of starting a fresh
  one that has lost the context.
- Every ticket has: ID, title, assignee, status (`backlog → in progress → in review → done`, or `blocked`),
  acceptance criteria, and links to its reviewer and tester tickets.

**Separation of duties**
- Every implementation ticket gets its own **test ticket** and a **review ticket**, each
  assigned to a *different* subagent from the implementer.
- The tester writes tests from the **spec**, not from the implementation.
- The reviewer checks the diff against the spec, AGENTS.md, and the course rules (§7).
- The main agent also reads every diff. A ticket is only `done` when all of these hold:
  - the tests pass, and the main agent ran them itself;
  - the review findings are resolved;
  - the AI markers and log entries are present.

**Standup**
- After each batch of subagent reports, update the board with what got done, what's next,
  and what's blocked. Give the human a short summary.
- Raise blockers to the human. Don't let a subagent improvise around them.

**What every brief must contain**
1. `Working for: {me}` and the subagent's name and role (implementer, tester, or reviewer).
2. Ticket ID and acceptance criteria (a command to run, and the expected output).
3. **Allowed write paths**, listed exactly. Everything else is read-only.
4. A statement that `docs/human/**`, every top-level doc, and other people's folders are forbidden.
5. The relevant spec, **pasted verbatim** (not paraphrased).
6. The AI-marking rule from §7, word for word.
7. **Stop conditions**: report back instead of improvising if the spec is ambiguous, a test
   needs a file outside the allowed paths, or a value is missing.
8. **Report format**: files changed, functions added, test command and its output, open questions.

If a subagent writes outside its allowed paths, revert that change and tell the human.

---

## 7. Course rules (EE 2361). These apply to every line of code

**Marking AI-written code**
- Wrap all AI-written code like this:
  ```c
  // [AI-GENERATED: Claude Code]
  ...
  // [END AI-GENERATED]
  ```
  Use the actual tool's name.
- If a human later edits inside the block, keep the markers.

**AI usage log**
- Append to the shared **`AI_USAGE.md`** at the repo root. Use one row per AI-written function:
  `file | function | what it does | date | author: agent`.
- The log only needs to separate agent from human. You don't need to record which person or
  which agent; git history covers that (`docs/human/TEAM_PROCESS.md`).

**Commits made by an agent**
- Make them as the human's git identity, with a co-author trailer naming the agent. That
  keeps "whose agent" traceable in `git log`.

**Code rules**
- Cite borrowed code (reference drivers, app notes) in a comment **and** in the docs.
- Every public function needs a doc comment covering its purpose, each argument, and the return value.
- C99. One `.c`/`.h` pair per module. Use fixed-width types (`int16_t`, `int32_t`) everywhere,
  because XC16's `int` is 16 bits.
- No `float` or `double` in runtime code, no `malloc`, and no blocking delays in library code.
- Comment every register write with what each bit field does.

---

## 8. Authority when sources disagree

1. `docs/human/*.md` (top-level team decisions)
2. `docs/agent/*.md` (top-level agent docs: plans, contracts)
3. `docs/human/{person}/`
4. `docs/archive/proposal.pdf`, `docs/archive/INITIAL_OVERVIEW.md` (historical baseline)
5. `docs/agent/{person}/`

Don't settle a conflict yourself. Raise it to your human using the format in §5B.
