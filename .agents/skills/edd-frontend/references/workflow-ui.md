# Workflow UI

Use this reference when changing the EDD Platform React console.

## Goal

Make the eval-driven design loop legible without turning the product into a
generic dashboard.

## Layout Model

- Left rail: product identity, navigation, agents, project lists.
- Main workspace: selected agent workflow and evidence.
- Right panel: selected artifact, run, eval, trace, or review details.

## UI Rules

1. Put controls near the artifact or stage they affect.
2. Do not duplicate the agent name or selected step in multiple headers.
3. Avoid disconnected action rows.
4. Prefer artifact cards with clear stage labels and review buttons.
5. Use right-panel review for details and editing.
6. Show relationships: expectation, run, eval, failure, fix, comparison.
7. Hide raw filenames unless the user needs file-level debugging.
8. Keep the visual language quiet, light, and workspace-like.

## EDD Concepts To Preserve

- scenario input;
- eval contract expectations;
- run mode and tool evidence;
- eval result and judge output;
- failure packet;
- fix proposal;
- candidate version;
- comparison;
- gate readiness;
- trace refs.

## Avoid

- static breadcrumbs that cannot be clicked;
- giant step counters that break with v2/v3 versions;
- activity logs as the only explanation of state;
- UI for objects that lack API contracts;
- marketing-page composition inside the app.
