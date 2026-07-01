# OpenAPI Drift

Use this reference when API behavior changes or CI reports OpenAPI mismatch.

## Checks

1. Run API tests.
2. Run OpenAPI lint.
3. Export the latest OpenAPI contract.
4. Compare the generated file with `docs/openapi.json`.
5. Commit the regenerated contract when the API change is intentional.

## Commands

```bash
npm run api:lint-openapi
npm run api:openapi
./scripts/test.sh
```

## Review Questions

- Did the path belong in `scripts/lint_openapi.py` required paths?
- Does every operation have a useful summary and operation id?
- Are request and response models explicit?
- Does `docs/API_CONTRACT.md` describe the behavior?
- Did the change preserve deterministic CI behavior?

## Avoid

- editing `docs/openapi.json` by hand;
- leaving generated contract changes unstaged after route changes;
- adding endpoints whose objects are missing from the product spine.
