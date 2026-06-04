# AGENTS.md

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

- Only commit when asked.
- Never add `Co-authored-by` trailers to commits.
- Do not commit secrets, `.env` files, API keys, or local run artifacts.

## Product Direction

- This repo is the canonical product surface.
- The React console in `apps/web` is the only frontend.
- Frontend work must follow `docs/design/FRONTEND_GUIDE.md`.
- The API in `apps/api` owns platform state, evidence, judges, gates, and promotion.
- Runner code belongs in `packages/runner` and returns evidence to the API.
- Langfuse integration is optional trace evidence, not the source of truth.

## Local Skills

- Project skills live in `.agents/skills`.
- At the start of any meaningful planning, API, UI, eval-loop, or Langfuse
  slice, consult the matching local skill before changing implementation or
  docs. Use the skill references when the task matches a specific workflow.
- For Langfuse tracing, prompt/dataset management, scores, trace inspection, or
  judge calibration, consult `.agents/skills/langfuse/SKILL.md` before changing
  implementation or docs.

## Implementation Rules

- Keep changes small and directly tied to the active request.
- Preserve deterministic local and CI behavior without model-provider keys.
- Prefer fresh code in the new product language over bulk-copying legacy files.
- If useful code is copied from older repos, rename and simplify it into this repo's model.
- Follow `docs/engineering/AI_AGENT_DEVELOPMENT.md` for AI-assisted development guardrails.
- Follow `docs/API_CONTRACT.md` before adding or stubbing API routes.
