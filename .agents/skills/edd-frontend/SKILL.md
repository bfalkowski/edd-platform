---
name: edd-frontend
description: Build or revise the EDD Platform React console UI. Use when changing frontend layout, navigation, builder screens, evidence panels, review panels, artifact cards, agent playground UI, eval loop UI, visual design, or when the user asks to make the app clearer or less clunky.
---

# EDD Frontend

Use this skill for UI work in `apps/web`.

## Required Reading

Read `docs/design/FRONTEND_GUIDE.md` before changing UI.
Check `docs/PRODUCT_SPINE.md` before adding or reshaping workflow concepts.

## UI Model

The console should feel like a focused agent workspace:

- left rail for product identity, navigation, agents, and project lists;
- main workspace for the selected workflow and evidence;
- right review panel for selected artifacts and run/eval details.

## Workflow

1. Identify the user workflow being improved.
2. Keep controls near the artifact or stage they affect.
3. Prefer clear artifact cards, compact controls, and right-panel review.
4. Avoid duplicated headers, disconnected action rows, static breadcrumbs, and raw filenames as primary UI.
5. Keep the EDD loop legible: expectation, run, eval, failure, fix, comparison.
6. Run `npm run build`.
7. Use the browser skill/plugin to inspect `http://localhost:5173` when the app is running or visual behavior changed.

## Guardrails

- Do not make the UI a generic dashboard.
- Do not add marketing/landing pages.
- Do not hide state transitions in activity logs only.
- Do not add UI for objects that lack a stable API contract unless the user explicitly asks for a mockup.
