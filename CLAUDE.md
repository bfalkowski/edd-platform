# CLAUDE.md

Clean-room product repo for the consolidated EDD Platform.

## Always-Applied Behavioral Guidelines

These guidelines reduce common LLM coding mistakes. Merge them with the
project-specific instructions below.

Source:
[multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills)
(MIT).

Tradeoff: these guidelines bias toward caution over speed. For trivial tasks,
use judgment.

### 1. Think Before Coding

Do not assume. Do not hide confusion. Surface tradeoffs.

Before implementing:

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them instead of picking silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop, name what is confusing, and ask.
- In an office session, "ask" and "present" mean: write it down where the
  person will read it. See [Working in an office](#working-in-an-office).

### 2. Simplicity First

Use the minimum code that solves the problem. Do not add speculative behavior.

- No features beyond what was asked.
- No abstractions for single-use code.
- No flexibility or configurability that was not requested.
- No error handling for impossible scenarios.
- If 200 lines could be 50, simplify.

Ask: would a senior engineer call this overcomplicated? If yes, simplify.

### 3. Surgical Changes

Touch only what is necessary. Clean up only your own changes.

When editing existing code:

- Do not improve adjacent code, comments, or formatting.
- Do not refactor things that are not broken.
- Match existing style, even if you would choose differently.
- If you notice unrelated dead code, mention it instead of deleting it.

When your changes create orphans:

- Remove imports, variables, and functions that your changes made unused.
- Do not remove pre-existing dead code unless asked.

Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

Define success criteria and loop until verified.

Transform tasks into verifiable goals:

- "Add validation" means write tests for invalid inputs, then make them pass.
- "Fix the bug" means write a test that reproduces it, then make it pass.
- "Refactor X" means ensure tests pass before and after.

For multi-step tasks, state a brief plan:

```text
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
3. [Step] -> verify: [check]
```

These guidelines are working when diffs have fewer unnecessary changes, fewer
rewrites happen due to overcomplication, and clarifying questions come before
implementation rather than after mistakes.

## Commit Rules

- Only commit when asked. An office ticket counts as asking (see
  [Working in an office](#working-in-an-office)).
- Never add `Co-authored-by` trailers to commits.
- Do not commit secrets, `.env` files, API keys, or local run artifacts.

## Task Tracking

- Use `docs/WORK_PLAN.md` for the public milestone checklist.
- When Beads is installed, use repo-local Beads tasks for active work, blockers,
  dependencies, and resume state. In an office session, the office ticket
  takes this place.
- Before resuming implementation, check the ready task queue and the work plan.
- After meaningful work, update task status, verification notes, and the work
  plan when milestone state changes.
- Do not commit private scratch notes, secrets, or local-only run artifacts.

## Working in an office

This repo can be worked on by an office: a relay that runs Claude Code sessions
as a Lead, Devs, reviewers and a PM, with a person as the manager. You are in an
office session when the office started you: you got a brief, and
`OFFICE_TICKET_TOKEN` is set. In an office session, these rules replace the
ones above where they differ:

- **The ticket is the request.** Your brief names one ticket. Do that ticket
  in one pull request. Every changed line should trace to it.
- **Commit, push and open the PR.** Commit on the ticket's own branch in your
  own worktree, push with a plain `git push`, open the pull request against
  `main` ready for review, then stop. Never commit to `main` directly, and do
  not merge. Who merges follows the office's rules.
- **Choose, then say what you chose.** Nobody may be watching, so do not wait
  on a question. For a choice that is easy to undo, pick the simpler option and
  write the choice and the reason in the pull request. Stop and ask only for a
  one-way door: deleting data, changing a public API or the database schema in
  a way that cannot be rolled back, or changing these rules.
- **File other work, do not do it.** When you find work outside your ticket,
  file it with the ticket command your brief names, and carry on.
- **Use the office board, not Beads.** Do not create, update or close Beads
  tasks, and do not change files in `.beads/` in your pull request. Parallel
  branches would conflict on its JSONL files, and the Beads git hook writes the
  shared Beads database into the main folder's `.beads/` on every commit. You
  may read Beads (`bd ready`, `bd show`) for context. Update
  `docs/WORK_PLAN.md` when a milestone moves, as before.
- **Show evidence.** In the pull request, say what you ran, what you checked
  by hand, what you could not check, and what else the change can affect. For
  a bug or new behavior, show the test that failed before your change and
  passes after it.
- **Everything else still holds:** no `Co-authored-by` trailers, no secrets,
  CI stays green without provider keys, frontend work follows
  `docs/design/FRONTEND_GUIDE.md`, and new routes follow
  `docs/API_CONTRACT.md`.

## Product Direction

- This repo is the canonical product surface.
- The React console in `apps/web` is the only frontend.
- Frontend work must follow `docs/design/FRONTEND_GUIDE.md`.
- The API in `apps/api` owns platform state, evidence, judges, gates, and promotion.
- Runner code belongs in `packages/runner` and returns evidence to the API.
- Langfuse integration is optional trace evidence, not the source of truth.

## Local Skills

- Project skills live in `.claude/skills`.
- At the start of any meaningful planning, API, UI, eval-loop, or Langfuse
  slice, consult the matching local skill before changing implementation or
  docs. Use the skill references when the task matches a specific workflow.
- For Langfuse tracing, prompt/dataset management, scores, trace inspection, or
  judge calibration, consult `.claude/skills/langfuse/SKILL.md` before changing
  implementation or docs.

## Implementation Rules

- Keep changes small and directly tied to the active request.
- Preserve deterministic local and CI behavior without model-provider keys.
- Prefer fresh code in the new product language over bulk-copying legacy files.
- If useful code is copied from older repos, rename and simplify it into this repo's model.
- Follow `docs/engineering/AI_AGENT_DEVELOPMENT.md` for AI-assisted development guardrails.
- Follow `docs/engineering/TASK_TRACKING.md` when using Beads or another local
  task tracker to coordinate agent work.
- Follow `docs/API_CONTRACT.md` before adding or stubbing API routes.
