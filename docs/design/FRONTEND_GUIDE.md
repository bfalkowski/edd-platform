# Frontend Design Guide

This guide defines the visual and interaction direction for EDD Platform.

The UI should feel like a focused developer/research workspace: quiet, legible,
fast to scan, and built around evidence. It should not feel like a marketing
site, a generic dashboard template, or a passive log viewer.

## Product Principles

- The React console is the only product UI.
- The interface should make the EDD workflow understandable at a glance and
  executable step by step.
- Evidence should be visible and inspectable. Do not bury core value in logs or
  backend-only behavior.
- Avoid old product language such as Lab UI, draft, Streamlit, or publish unless
  discussing history.
- Mock runs are removed. All runs are live (Live Anthropic). Do not add a
  mock/live toggle.

## Layout

```text
left sidebar      main workspace (tabs)
dark warm rail    agent · proof loop · error analysis · evidence · readiness
```

### Left Sidebar

- Dark warm background (`--bg-sidebar: #1c1917`), warm text (`--text-sidebar`).
- Contains: product wordmark, new agent button, agent list, service status dots.
- Agent rows are quiet list items. Clicking a complete agent opens the workspace
  tabs. Clicking a mid-flow agent re-enters the wizard at the correct step.
- Service status dots (Langfuse, Anthropic) live at the bottom of the rail.

### Main Workspace

The main workspace uses five tabs per agent:

| Tab | Purpose |
|---|---|
| Agent | View and edit agent name and core instruction |
| Proof loop | Run the agent against a test, evaluate, iterate |
| Error analysis | Guided wizard: build review set → sync Langfuse comments → assign failure modes |
| Evidence | Inspect all evidence artifacts for this agent |
| Readiness | Gate decisions and promotion status |

Rules:

- Each tab is a self-contained view. Do not bleed state or navigation across tabs.
- Avoid duplicate headings. If the sidebar names the selected agent, do not
  repeat the full title in a large card below.
- Show the current object and available action clearly.
- Do not add explanatory copy beside controls when the control label is
  already clear.

## Wizard Pattern

Two wizards exist in the product:

**Agent creation wizard** (`Wizard.tsx`) — triggered by "New agent". Steps:
`Describe → Review → Run → Name the failure → Fix → Compare → Done`

**Error analysis wizard** (`ErrorAnalysisTab.tsx`) — triggered by Error analysis
tab. Steps: `Build corpus → Review & code → Confirm modes → Done`

Rules for wizards:

- Show a step indicator at the top. Mark completed steps with a checkmark.
- Each step renders only the UI needed for that step. Do not dump all panels
  on one screen.
- Back/Next navigation lives at the top of each step panel.
- Primary action button (Next, Continue) lives top-right. Back lives top-left.
- A step that is already complete (done state for agent wizard) skips the wizard
  and goes directly to the workspace tabs.

## Gestalt Principles

Every visual decision should map to exactly one of these. If a new UI element
doesn't fit one of these principles, that's a sign it's decorative rather than
functional — cut it.

- **Similarity** (color, shape, badge style). Things that share a visual
  property read as the same kind of thing. Status badges are the canonical
  example: `reviewed`/`passed` is always the same green pill, `open`/`pending`
  is always the same muted pill, regardless of which tab or table it appears
  in. Don't invent a new color for the same status in a new component.
- **Proximity** (spacing). Things placed close together read as one unit.
  Step actions (Back / primary action) sit tight at the top of a step panel;
  the step's content sits with more space below. A form field's label sits
  tight above its input; unrelated fields get more gap. If two things need
  different spacing to *not* look related, that's proximity working correctly
  — don't override it with a divider instead.
- **Common region** (shared container, border, background tint). Things
  inside one visual boundary read as belonging together. A review item and
  its expanded annotations share one row's container (`.discovery-corpus-row`
  + `.discovery-annotation-rows`), not two separate cards. An artifact's
  evidence row and its "Open trace" link share `.workflow-evidence-row`. When
  two pieces of UI are logically linked (a trigger and its detail), put them
  in the same container rather than relying on layout position alone.
- **Figure/ground** (contrast, opacity, `--text` vs `--text-muted`). The
  thing the user needs to act on should be visually louder than the thing
  that's just context. Primary content uses `--text`; eyebrow labels,
  metadata, and hints use `--text-muted`. A dismissible intro card
  (`discovery-intro-card`) recedes once acknowledged. Don't mute something
  the user still needs to read just to make a panel look calmer — muting is
  for redundant or already-established context, not for genuinely new
  information.

Apply these when reviewing new panels, not just when building them: if a
review finds two same-status items rendered with different colors, or a
trigger and its result living in unrelated containers, that's a Gestalt
violation to fix, not a stylistic choice.

## Visual Style

Color tokens (defined in `:root`):

| Token | Value | Use |
|---|---|---|
| `--bg` | `#fafaf8` | Page background |
| `--bg-sidebar` | `#1c1917` | Sidebar |
| `--surface` | `#f2ede6` | Cards, tab content areas, agent panel |
| `--surface2` | `#e8e2d9` | Secondary surfaces, table headers, expanded rows |
| `--surface3` | `#ffffff` | Input fields, textareas, inline editors |
| `--text` | `#1c1917` | Primary text |
| `--text-muted` | `#78716c` | Labels, hints, secondary text |
| `--text-sidebar` | `#e7e5e4` | Sidebar text |
| `--border` | `#e2dbd1` | Warm neutral borders |
| `--accent` | `#cf4a1a` | Primary buttons, active step indicators |
| `--success` | `#15803d` | Pass badges, reviewed status |
| `--error` | `#b91c1c` | Failure indicators |

Rules:

- Cards use `--surface`, not `--surface3` (white). White is reserved for inputs.
- The agent designer panel uses `--surface` to match other tabs.
- No dark table blocks in the main experience.
- No decorative gradients or marketing-style panels.
- Avoid cards inside cards. Nested boxes indicate a specificity bug in CSS.
- Consistent border-radius: 14–18px for cards, 6px for inputs/badges, 999px for pills.

## Typography

- Headings use Source Serif 4 (imported from Google Fonts).
- Body and UI text: `system-ui, -apple-system, sans-serif`.
- Strong headings only for true object names or primary task titles.
- Uppercase eyebrow labels (`ARTIFACT TYPE`, `REVIEW ITEM`) use
  `font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase`.
- Do not scale font sizes with viewport width.

## Controls

- **Primary button**: accent fill (`--accent`), white text. Used for the single
  most important action per step.
- **Secondary button**: transparent with `--border`, no fill. Used for
  supplementary actions.
- **Icon buttons**: lucide icons for close, delete, external link. No custom SVG.
- **Segmented controls** (`mode-option`): for mutually exclusive choices. Not
  used for mock/live (mock removed).
- **Dropdowns**: for assigning failure modes inline. Keep the select element
  styled with `--surface`, `--border`.

Rules:

- Put actions where their output appears.
- Disable controls only when the reason is obvious from context.
- Do not add generic button rows disconnected from the selected object.

## Data Tables

Used in: Error analysis step 1 (review set), Error analysis step 2 (review items).

Pattern:

- Header row: `--surface2` background, uppercase 11px labels.
- Data rows: `--bg` or transparent, 1px `--border` bottom.
- Status badges: pill shape, green for reviewed/passed, muted for open/pending.
- Expandable rows: clicking a row title expands inline content (annotations,
  mode assignment). Expanded row background uses `--surface2`.
- Last row has no bottom border.

CSS classes: `.discovery-corpus-table`, `.discovery-corpus-row`,
`.discovery-corpus-head`, `.discovery-status-badge`.

## Langfuse Integration Pattern

Error analysis depends on Langfuse as the source of truth for trace comments:

1. User reviews a trace in Langfuse and adds comments there.
2. Platform syncs those comments via "Sync Langfuse comments" button →
   `POST /projects/{id}/review-corpora/{corpus_id}/sync-langfuse-comments`.
3. Synced comments appear as `ReviewAnnotation` records (status: accepted,
   metadata includes `langfuse_comment_id` for deduplication).
4. User assigns each annotation to a failure mode using the inline dropdown.
5. Failure modes are promoted to the confirmed taxonomy in step 3.

The platform does **not** duplicate Langfuse's note-writing UI. The "Reviewer
notes" free-text form has been removed. Writing happens in Langfuse; categorization
happens in the platform.

## Evidence UI

Evidence is the center of the product.

Rules:

- Show evidence as named artifacts with short descriptions.
- Artifact cards have a clear type, title, body/summary, and source.
- Trace references must provide an explicit "Open trace" link when a URL exists.
  The trace ID alone is not a useful affordance.
- Do not expose raw relationship names such as `GENERATED_FROM` or `SUPPORTS`.
  Translate to user-facing labels.
- Do not show unresolved artifacts as fallback cards. Omit until they can be
  named.
- Evidence summaries should be compact. Progress belongs in workflow controls.

## Service Status

- Langfuse and Anthropic status dots live in the sidebar.
- Do not duplicate service state in top-bar pills.
- Do not expose secret values. Show only configured / online / offline / not
  configured.

## Empty States

Brief and actionable:

> Run a live agent before adding evidence to the review set — mock runs aren't
> reviewed.

Avoid long instructional paragraphs or placeholder language that looks unfinished.

## Current Canonical Patterns

| Pattern | Location |
|---|---|
| Agent creation wizard | `Wizard.tsx` |
| Error analysis wizard | `ErrorAnalysisTab.tsx` (discoveryStep state) |
| Workspace tab panel | `main.tsx` (workspaceTab state, 5 tabs) |
| Proof loop test card | `main.tsx` (selectedGeneratedDesign, scenario-test-summary) |
| Langfuse comment sync | `POST .../sync-langfuse-comments` + handleSyncLangfuseComments |
| Review set data table | `.discovery-corpus-table` pattern |
| Dismissible intro card | `showDiscoveryIntro` + localStorage key `edd.discoveryIntroDismissed` |
| Failure mode taxonomy | Confirm modes step → axial-code-panel |
| Right-side edit panel | Edit test, Manage tools (right-panel overlay) |

New components should extend these patterns rather than introducing a new layout model.
