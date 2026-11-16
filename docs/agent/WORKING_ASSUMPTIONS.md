<!-- [AI-GENERATED: Claude Code] -->
# Working assumptions (development may proceed on these; they are NOT decisions)

Shared top-level agent doc (AGENTS.md §5). Rank 2 in AGENTS.md §8.

## Open questions are working assumptions, not accepted decisions
None of the questions in `docs/agent/hadi/open_questions.md` (Q1-Q8) has been accepted. Development may
continue on the agent recommendation of each question anyway. Rules that follow from this:
- The recommendation of each open question is the working assumption. Code built on one says so in its
  header comment (`WORKING ASSUMPTION: open_questions Qn, not decided`) and in the board ticket.
- `docs/agent/CONTRACTS.md` is **not** changed by a working assumption. C2 stays "PROPOSED, NOT DECIDED"
  and C1.9 stays OPEN until Hadi (or the team) decides; the spec for code built on them is the proposal
  (`proposals/C2_uart_stream.md` as fixed by S2-1F, `proposals/C1b_trigger.md` as fixed by S2-2F).
- If a decision later differs from the assumption, the code changes to match the decision.
- Current assumptions: Q1 C2 stream as proposed; Q2 trigger C1b as proposed; Q3 keep C1.6 (count only);
  Q4 GM_DEFAULT_REJECT = largest min_conf within 2 %; Q5 exporter divides W1 by K; Q6 train/val/test
  split with validation for selection and the fallback; Q7 drain may stop after 4 bursts; Q8 constants
  stay provisional.
- Decided: 2026-11-16 by Hadi. Not contested.
- FYI: Q6 refines decided C4.3 (one held-out set) and Q3 is listed in open_questions as a conflict with
  C1.6; as assumptions neither changes CONTRACTS.md (Q3's assumption keeps C1.6 as written).
<!-- [END AI-GENERATED] -->
