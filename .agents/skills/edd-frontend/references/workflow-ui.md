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
9. Keep evidence sections compact: count plus inspectable artifact rows, not
   giant stage-summary paragraphs.
10. Render related evidence only when the artifact can be resolved and named.
11. Make related evidence clickable; otherwise remove the row.
12. Translate internal relationships into user labels. Never show raw
    `GENERATED_FROM`, `OBSERVES`, or `SUPPORTS`.
13. Show Langfuse traces as Open trace actions, not trace ids alone.

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
- placeholder panels with no artifact, action, or state;
- unknown Saved evidence fallback cards;
- duplicate service/status explanations in multiple places.
