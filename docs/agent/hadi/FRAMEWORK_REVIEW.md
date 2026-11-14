# Framework review: points of failure

> Agent draft for `hadi`, 2026-11-14. Severity: 🔴 will break things · 🟠 likely to bite · 🟡 worth fixing

## Process and governance

### Resolved by Hadi's decisions (2026-11-14)
- ~~F1 ownership conflict~~: "Everyone owns everything, nothing is split." Recorded in `docs/human/TEAM_PROCESS.md`.
- ~~F5 is reading allowed?~~: reading is allowed anywhere.
- ~~F7 consensus bottleneck~~: one explicit decision with no conflict goes straight into the top-level docs. Conflicts get flagged, and the human either overrules or discusses with the team.
- ~~F9 code outside docs / shared AI_USAGE~~: any agent may edit any code; git attributes the change. `AI_USAGE.md` is one shared file that only separates agent from human.

### Still open
**F2 🔴 No shared remote. This is now the single biggest risk.** Three things now depend
on git:
- **Ownership:** "everyone owns everything" relies on git to say who changed what.
- **The usage log:** the AI-usage log relies on git to tell agents and people apart.
- **Conflict checks:** an agent can only check for conflicts against the latest top-level docs, and only git provides that.

*Update 2026-11-14:* the folder **is** a git repo, on `master` with one `init` commit. There
is **no remote yet**; Hadi will add one. Until then, attribution works locally, but teammates
can't see changes and conflict checks can't pull. *Remaining fix:*
- Add the remote and use a branch per person or feature.
- Pull before every conflict check. Merge through PRs.

**F3 🔴 The rules are only advisory.** Nothing physically stops an agent writing into
`docs/human/`, a top-level doc, or another person's folder. *Fix:* a Claude Code
`PreToolUse` hook that blocks writes to `docs/*/<not-$ME>/**`, with each person setting `ME`
in their own gitignored `.claude/settings.local.json`. It doesn't need to guard top-level
docs, since §5 allows writing them.

**F4 🟠 Identity isn't bound to the session.** Same fix as F3, using `ME`.

**F6 🟠 Secondhand decisions** still end up in `docs/agent/{me}/` until the person who made
the decision confirms it to their own agent. That's less of a problem now, because any
human's explicit decision can go straight into the top-level docs.

**F8 🟡 AGENTS.md itself.** Hadi wrote it alone. Teammates' agents will follow it as soon as
it's in the repo. Make sure the other three have actually read it.

**F10 🟡 Private memory isn't shared.** Claude, Omi, or Notion memory is invisible to
teammates. `docs/` is the only source of truth.

### New risks from the 2026-11-14 decisions
**F11 🟠 Two people can write the top-level docs at the same time.** Suppose two people
record conflicting decisions within minutes. Each agent checks for conflicts, finds none
because the other's change hasn't been pulled yet, and writes. The last write wins silently.
*Fix:* git (F2), plus pulling right before the check and pushing right after the write.

**F12 🟠 "Overrule as trivial" happens without telling anyone.** One person can overwrite an
agreed decision, and the people who made it never find out. AGENTS.md keeps the old text
under a `Previously:` line, but nothing notifies anyone. *Fix:* a convention for overrule
commits, e.g. `docs(overrule): …`, so everyone can see them in `git log`, or a ping in the
team chat.

**F13 🟡 Conflict checks get harder as the docs grow.** Each agent re-reads every top-level
doc for every statement. That's fine while there are a few small topic files; it gets
unreliable if they grow large. Keep them short and organized by topic.

**F14 🟡 Several agents may edit the same file at once.** Under "everyone owns everything,"
four people's agents can all edit `gesture.c` in the same afternoon. Use branches per
feature, and merge often.

**F15 🟡 Subagent supervision costs context.** Reviewing every diff and coordinating a tester
and a reviewer for each ticket uses up the main agent's context. The board in `BOARD.md`
must be detailed enough that a fresh main session can pick it up after the conversation is
summarized.

## Technical points of failure that the framework must catch

**T1 🔴 Python and C rounding differ.**
- Python `//` floors; C `/` truncates toward zero. They disagree on negative means, and every
  axis has negative samples.
- Right-shifting a negative number is implementation-defined in C (XC16 shifts arithmetically).

"Must match exactly" fails silently unless C3 spells out the rounding.

**T2 🔴 Host tests can lie.** `int` is 32 bits on a laptop and 16 bits on XC16. Expressions
like `a * b` with int16 operands overflow only on the PIC24. The host harness passing is
not enough; gate G3 (on-target vectors) is mandatory.

**T3 🔴 Energy overflow.** Σx² over 15 samples of a 12-bit value can reach about 6×10⁷. That
needs an int32 accumulator, a defined shift back to int16, and saturation. All of it must be
identical in Python.

**T4 🟠 The training config and the runtime config can differ.** `gesture_init(odr_hz,
range_g)` accepts any ODR or range, but the model is only valid at 100 Hz and ±4 g. Either
remove those parameters or check them against constants in `gesture_model.h`. The same
applies to model version drift: put a hash in the header and print it at boot.

**T5 🟠 Float training versus integer inference.** Accuracy measured in float during training
says nothing about the int8 model. Evaluate with the integer reference only.

**T6 🟠 WS2812 bit-banging versus the sensor.** It needs interrupts masked for about 2 ms
per frame. During a capture that can delay FIFO draining, though the 32-deep FIFO gives
320 ms of slack. It can also corrupt I2C transactions. Define the rule in C6.

**T7 🟡 Learned gestures are volatile.** k-NN templates in RAM vanish at reset. Decide
whether to persist them to flash (RTSP) before writing `knn.c`.

**T8 🟡 Subagents can't test on hardware.** Sonnet subagents can only verify on the host.
Every on-target step needs a human with the board, so plan those sessions into the schedule.

**T9 🟡 Too many unknowns are still open:**
- XC16 version
- pins
- I2C bus and address
- the bulb control method
- deadlines

Each one blocks a contract. Track them in each person's `docs/agent/{me}/open_questions.md`.
