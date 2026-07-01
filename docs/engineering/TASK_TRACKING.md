# Task Tracking

This repo should be easy to resume after context loss, tool restarts, or a
switch between coding agents.

`docs/WORK_PLAN.md` remains the public milestone checklist. A local task tracker
can carry the more operational details: active slice, dependencies, blockers,
verification notes, and what changed since the last commit.

## Recommended Tool

Use Beads when it is available locally.

Beads is a good fit because it keeps tasks close to the repo and gives agents a
concrete ready queue instead of relying on conversational memory.

## What Gets Committed

Commit:

- the workflow rule in `CLAUDE.md`
- this task-tracking policy
- public roadmap changes in `docs/WORK_PLAN.md`
- durable task metadata only if it is intentionally part of the repo and does
  not include secrets, private notes, API keys, or local run artifacts

Do not commit:

- `.env` files
- provider keys or tokens
- private job-search notes
- scratch planning files
- local run outputs
- transient tool caches

## Agent Workflow

Before starting or resuming a slice:

1. Read `CLAUDE.md`.
2. Read `docs/WORK_PLAN.md`.
3. Check the Beads ready queue when Beads is installed.
4. Pick the smallest task that advances the active milestone.
5. State the success criteria and expected verification.

After finishing meaningful work:

1. Run targeted verification.
2. Update the Beads task with status and verification notes when Beads is
   installed.
3. Update `docs/WORK_PLAN.md` only when milestone state changed.
4. Commit only when the user asks.

## Drift Prevention

Task tracking is here to prevent these failure modes:

- building isolated features that do not prove eval-driven design
- losing track of why a UI or API exists
- repeating work after context compaction
- treating local demos as the product model
- committing changes without clear verification

If a task does not connect to the product spine, the eval loop, the evidence
model, or the product story, pause and re-scope it before coding.
