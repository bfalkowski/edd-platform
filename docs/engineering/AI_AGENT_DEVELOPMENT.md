# AI Agent Development Practices

This repo intentionally uses AI coding agents as engineering collaborators.

The goal is not to hide that. The goal is to demonstrate a disciplined loop for
using agents without letting the product drift.

## Core Principle

AI agents can accelerate implementation, but the repo remains governed by human
intent, explicit product documents, deterministic tests, and reviewable commits.

Agents may propose and implement changes. They do not get to silently redefine
the product.

## Steering Files

The project uses a small set of steering files:

- `AGENTS.md`: repo rules, product direction, commit constraints
- `docs/WORK_PLAN.md`: active implementation checklist
- `docs/engineering/TASK_TRACKING.md`: repo-local task tracking policy
- `docs/design/FRONTEND_GUIDE.md`: frontend interaction and visual rules
- `docs/hld/`: canonical high-level designs
- `docs/decisions/`: short architectural decision records

If a proposed change conflicts with these files, the steering files win unless
the user explicitly changes direction.

## Agent Loop

The expected development loop is:

1. Read the relevant steering files.
2. Select and read the matching local skill in `.agents/skills`.
3. Read the skill reference file when the task matches a specific workflow.
4. Check the task queue when a repo-local tracker such as Beads is available.
5. Translate the request into a small, verifiable outcome.
6. Update or identify tests where practical.
7. Make scoped changes.
8. Run the relevant checks.
9. Browser-smoke visible UI changes.
10. Update task status and `docs/WORK_PLAN.md` when milestones move.
11. Commit only when explicitly asked.

This loop is meant to keep AI-assisted work boring, inspectable, and reversible.

## Drift Prevention

Drift is treated as an engineering risk.

Common drift modes:

- vocabulary drift
- UI pattern drift
- hidden provider-key dependency drift
- demo-only code that bypasses the platform model
- HLD sprawl with no implementation mapping
- agent-generated abstractions that do not serve the current slice

Guardrails:

- use the product vocabulary in `AGENTS.md`
- apply the relevant `.agents/skills` workflow before meaningful work
- keep frontend work aligned with the design guide
- keep HLDs tied to `docs/WORK_PLAN.md`
- require local/mock behavior to work without provider keys
- store meaningful outputs as evidence artifacts
- prefer small vertical slices over broad speculative scaffolding
- keep commits human-readable and free of co-author trailers

## Testing Expectations

Every meaningful slice should have at least one of:

- API test
- domain/unit test
- web build/typecheck
- browser smoke test
- script-level smoke test

CI should not require model-provider credentials. Live LLM behavior is opt-in.

## UI Expectations

Frontend changes must follow `docs/design/FRONTEND_GUIDE.md`.

Important examples:

- keep the left rail simple and recoverable
- place actions near the artifact or workflow they affect
- use a right review panel for artifact detail/editing
- show evidence context instead of generic workflow noise
- do not add disconnected wizard controls

## Evaluation Expectations

Product work should reinforce the evaluation-driven thesis:

- define what good means
- create artifacts for targets, judges, gates, runs, failures, and decisions
- link evidence to conclusions
- make regressions diagnosable
- show bounded fixes and comparisons

The repo should make it clear that AI system iteration is evidence-backed, not
vibes-based.

## Commit Expectations

Commits should be:

- requested by the user
- scoped to the completed slice
- free of `Co-authored-by` trailers
- free of secrets and local run artifacts
- supported by relevant verification

## Engineering Signal

For engineering reviewers, this repo should demonstrate:

- practical AI-assisted engineering discipline
- evaluation infrastructure thinking
- product-quality frontend judgment
- API and domain modeling
- deterministic local development
- observability and evidence orientation
- ability to turn ambiguous AI behavior into measurable artifacts

The strongest signal is not that an AI agent wrote code.

The strongest signal is that the project shows how to keep AI-assisted work
aligned, testable, and useful.
