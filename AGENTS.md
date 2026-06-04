# AGENTS.md

Clean-room product repo for the consolidated EDD Platform.

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

- For Langfuse tracing, prompt/dataset management, scores, trace inspection, or judge calibration, consult `skills/langfuse/SKILL.md` before changing implementation or docs.

## Implementation Rules

- Keep changes small and directly tied to the active request.
- Preserve deterministic local and CI behavior without model-provider keys.
- Prefer fresh code in the new product language over bulk-copying legacy files.
- If useful code is copied from older repos, rename and simplify it into this repo's model.
- Follow `docs/engineering/AI_AGENT_DEVELOPMENT.md` for AI-assisted development guardrails.
- Follow `docs/API_CONTRACT.md` before adding or stubbing API routes.
