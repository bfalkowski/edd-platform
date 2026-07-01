# apps/web

React product console for EDD Platform. This is the only product UI.

Layout: dark warm left sidebar (agent list, service status) and a main
workspace with five tabs per agent — Agent, Proof loop, Error analysis,
Evidence, Readiness.

Two wizards drive the workflow:

- **Agent creation wizard** (`Wizard.tsx`): Describe → Review → Run → Name
  the failure → Fix → Compare → Done. Runs live against Anthropic.
- **Error analysis wizard** (inline in `main.tsx`): Build review set →
  Review & code (in Langfuse, synced back with one click) → Confirm modes →
  Done.

See [`../../docs/design/FRONTEND_GUIDE.md`](../../docs/design/FRONTEND_GUIDE.md)
for the full interaction and visual model, and
[`../../docs/HAPPY_PATH_WALKTHROUGH.md`](../../docs/HAPPY_PATH_WALKTHROUGH.md)
for a step-by-step manual walkthrough.

`main.tsx` and `Wizard.tsx` are large single files; component extraction is a
known next step, not yet done.
