# Frontend Design Guide

This guide defines the visual and interaction direction for EDD Platform.

The UI should feel like a focused developer/research workspace: quiet, legible,
fast to scan, and built around evidence. It should not feel like a marketing
site, a generic dashboard template, or a wizard that hides the system model.

## Product Principles

- The React console is the only product UI.
- The UI should make the EDD workflow understandable through artifacts,
  context packs, runs, gates, and evidence.
- The interface should be simple enough to demo in minutes and deep enough to
  support real evaluation work.
- Evidence should be visible and inspectable. Do not bury core value in logs or
  backend-only behavior.
- Avoid old product language such as Lab UI, draft, Streamlit, and publish
  unless discussing history.

## Layout

The default product layout is:

```text
left rail     main workspace               right review panel
navigation    selected workflow/evidence    artifact detail/edit
```

### Left Rail

Use the left rail for:

- product/project identity
- new agent action
- search
- runs
- agent list
- future evidence/project sections

Rules:

- The rail must be collapsible.
- The collapse control must stay inside the rail in both open and collapsed
  states.
- Collapsed mode should keep a narrow icon rail visible, not hide navigation
  completely.
- The product/project name appears at the top when expanded.
- The product mark remains visible when collapsed.
- Agent rows should be quiet list items, not heavy cards.
- Row actions should use an ellipsis menu when there are multiple actions.

### Main Workspace

Use the main workspace for the current task:

- creating an agent design
- reviewing evidence context
- running or evaluating a version
- comparing versions
- inspecting gates and failures

Rules:

- Avoid duplicate headings. If the top bar names the selected agent, do not
  repeat the same title in a large card below.
- Avoid passive breadcrumb/status blocks that cannot be clicked.
- Show the current object and available action clearly.
- Prefer artifact/evidence sections over wizard progress strips.
- Do not show all future workflow steps at once unless they are useful and
  actionable.

### Right Review Panel

Use a right-side panel for artifact review, structured editing, and evidence
detail.

Rules:

- The panel should dock to the right edge. It should not float awkwardly over
  unrelated content.
- The panel toggle belongs near the review context, and the close control
  belongs inside the panel.
- Header copy should be concise: artifact title first, minimal labels.
- Use `Edit`, `Save`, and icon-only close/delete controls where meaning is
  obvious.
- Delete should require confirmation for destructive persisted data.
- Diff is only useful when the user is reviewing source/text changes. Do not
  show a disabled or meaningless diff control.

## Visual Style

The visual direction is restrained and app-like:

- light background
- soft neutral left rail
- black/near-black primary text
- muted gray secondary text
- subtle borders
- compact rounded controls
- limited accent color
- no dark table blocks in the main experience
- no oversized hero sections
- no decorative gradients, orbs, or marketing-style panels

Cards are allowed for repeated artifacts, review panels, and bounded tools.
Avoid cards inside cards.

## Typography

- Use strong headings only for true object names or primary task titles.
- Use compact headings inside panels and artifact cards.
- Do not scale font sizes with viewport width.
- Avoid negative letter spacing.
- Use uppercase eyebrow text sparingly for stable categories such as Evidence
  Context or Start From Intent.
- Truncate long nav labels cleanly.

## Controls

Use familiar controls:

- icon buttons for navigation, collapse, close, delete, run, download, and
  review-panel toggles
- text buttons for clear commands such as Create agent, Edit, Save
- segmented controls for mode choices
- menus for grouped row actions
- toggles or checkboxes for binary settings
- inputs/textareas for editable fields

Rules:

- Prefer lucide icons when an icon exists.
- Do not invent custom SVG icons for common actions.
- Do not use generic button rows disconnected from the selected object.
- Put actions where their output appears.
- Disable controls only when the reason is obvious; otherwise hide unavailable
  actions until they are meaningful.

## Evidence UI

Evidence is the center of the product.

Use evidence views for:

- agent design artifacts
- behavior rules
- judge prompts
- gates
- run evidence
- eval results
- failure packets
- fix proposals
- trace references
- design decisions
- context packs

Rules:

- Show evidence as named artifacts with short descriptions.
- Context packs should explain why a set of artifacts is being shown.
- Artifact cards should have a clear type, title, body/summary, and source.
- Related artifacts should be shown through links/relationship summaries once
  artifact links exist.
- Do not expose raw file names as the main UI unless the user is explicitly in a
  source/code review mode.
- Do not call the feature generic memory in the UI. Prefer Evidence, Artifacts,
  or Evidence Context.

## Streaming And Activity

Long-running work should show activity locally where the work is happening.

Rules:

- Activity belongs in the active step/panel, not as a permanent global column.
- Once the user moves to a new section, old ephemeral activity can disappear.
- Persist meaningful results as artifacts, not as activity logs.
- For live LLM or runner work, show clear phases such as preparing context,
  running scenario, judging output, storing evidence.

## Responsive Behavior

- The left rail should remain recoverable at narrow widths.
- Text must not overflow buttons, nav rows, or artifact cards.
- Main workspace sections may stack on narrow screens.
- Fixed-format controls should have stable dimensions to avoid layout jumps.

## Empty States

Empty states should be brief and actionable.

Good:

> Create an agent design to begin collecting targets, judge prompts, gates,
> runs, and evidence.

Avoid:

- long instructional paragraphs
- explaining visual design inside the app
- placeholder language that looks unfinished

## Current Canonical Patterns

The first implemented patterns are:

- collapsible left rail with project identity and agent list
- intent form for creating an agent design
- project-scoped API calls
- automatic `AGENT_DESIGN` artifact creation
- deterministic `AGENT_PROMPT_REVIEW` context pack
- evidence panel backed by context-pack artifacts

Future components should extend these patterns rather than introducing a new
layout model.
