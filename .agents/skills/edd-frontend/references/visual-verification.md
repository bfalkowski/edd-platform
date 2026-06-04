# Visual Verification

Use this reference before handing off frontend changes.

## Required Checks

1. Run the web build.
2. Open the app in the browser when a dev server is running or can be started.
3. Inspect at least the affected viewport.
4. Verify the left rail, main workspace, and right panel still make sense.
5. Check that text does not overlap, truncate badly, or repeat unnecessarily.
6. Check that controls are near the state they change.

## Commands

```bash
npm run web:build
./scripts/dev.sh
```

## Browser Review Targets

- new agent state;
- selected agent state;
- run/eval playground;
- review panel open and closed;
- left rail open and collapsed;
- mobile or narrow width if layout changed.

## Avoid

- accepting a build-only pass for layout-heavy changes;
- leaving visible old visual systems after a redesign;
- testing only the happy path when panels or sidebars changed.
