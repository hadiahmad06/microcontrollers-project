# Hadi: explicit statements and decisions

This file is append-only. See AGENTS.md §4.

## 2026-11-14: Docs governance structure
- Statement: "docs/human/{person} should only be updated when someone makes a statement or decision explicitly. prompt the user if its unclear whether their decision or statement is explicit."
- Context: Setting up the docs framework.
- Supersedes: none

## 2026-11-14: Agent folders are free to edit
- Statement: "docs/agent/{person} can be updated by you whenever."
- Context: Setting up the docs framework.
- Supersedes: none

## 2026-11-14: Agents stay in their own person's folders
- Statement: "agents can only interact with their own {person}'s folders."
- Context: Setting up the docs framework. It isn't settled yet whether "interact" includes *reading* other people's folders.
- Supersedes: none

## 2026-11-14: Shared top-level docs need consensus
- Statement: "within docs/human/ and docs/agent/ there may be files outside of a subdirectory. These shuoldn't be edited until we give clear consesus." … "files like docs/human/TRAINING_PIPELINE.md where multiple people have come to a consesus or one person has made a clear decision that isnt contested by anyone else. the same goes for docs/agent/*.md"
- Context: Setting up the docs framework.
- Supersedes: none

## 2026-11-14: Use cheaper subagents with unambiguous briefs
- Statement: "You should use subagents of cheaper models, like Sonnet 5.5 Medium, and give them clear unambigious instructions."
- Context: How the project work will be carried out.
- Supersedes: none

## 2026-11-14: Reading is allowed everywhere
- Statement: "Reading is allowed anywhere within the repo."
- Context: Answers whether "interact" includes reading.
- Supersedes: clarifies "Agents stay in their own person's folders" (that rule is about writing only)

## 2026-11-14: Shared ownership
- Statement: "Everyone owns everything, nothing is split."
- Context: Resolves the conflict between proposal.pdf (one lead per part) and INITIAL_OVERVIEW.md ("EVERYONE").
- Supersedes: none

## 2026-11-14: Agents may edit any code; git records who
- Statement: "Yes, its okay because it will show exactly who's agent made a change in git commit logs"
- Context: Answers whether an agent may edit code in modules other people work on.
- Supersedes: none

## 2026-11-14: The AI usage log only separates agent from human
- Statement: "for the log differentiation only matters between agent and human. not between different agents and different humans. We can differentiate later from git diff for different agents/humans"
- Context: How AI_USAGE.md is kept.
- Supersedes: none

## 2026-11-14: Subagents are managed like employees, SCRUM style
- Statement: "you should be keeping track of your subagents and reviewing their work, and asking other subagents to cross check their work / write tests. They aren't contractors, they are employees. Keep track of them SCRUM style"
- Context: How subagents are run.
- Supersedes: none

## 2026-11-14: Rule for top-level docs and conflicts
- Statement: "if a human makes an explicit decision that isnt contested by top-level documents, then you can directly place it in the top-level. the issue arises when a statement/decision conflicts with the top-level, in which case the human can overrule it as a trivial conflict, or decide to speak with the others and compromise with them. just make it clear to the human when something they are saying is conflicting a top level statement"
- Context: Replaces the earlier "consensus first" rule for top-level files.
- Supersedes: "Shared top-level docs need consensus" (2026-11-14)

## 2026-11-14: Subagents work in git worktrees
- Statement: "Use worktree mode please."
- Context: Each subagent works on its own git worktree and branch instead of the shared checkout.
- Supersedes: none

## 2026-11-14: Base commit for worktrees
- Statement: chose "Commit stable files (Recommended)": commit AGENTS.md, CLAUDE.md, docs/human, the plan, board and review, .gitignore, the hook, and the archive move on master. Leave out the in-progress proposals, spikes and ug.txt.
- Context: Answer to a direct question about the worktree base commit.
- Supersedes: none

## 2026-11-14: The main agent merges subagent branches after review
- Statement: chose "I merge after review (Recommended)": the main agent merges locally once a ticket is done, meaning the tests it ran itself pass and the review findings are fixed. Visible on the board and in git log.
- Context: Answer to a direct question about who merges worktree branches.
- Supersedes: none
