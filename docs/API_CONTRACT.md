# API Contract

The platform API contract is generated from FastAPI's OpenAPI schema.

The generated contract lives at:

- [`docs/openapi.json`](openapi.json)

Regenerate it with:

```bash
npm run api:openapi
```

Lint it with:

```bash
npm run api:lint-openapi
```

The repo test script runs the OpenAPI lint through API tests. The current lint
checks:

- OpenAPI 3.x schema
- expected API title
- required project-scoped paths
- operation ids on every route
- unique operation ids
- summaries on every route

This is intentionally lightweight for the first slice. As the API grows, the
lint can become stricter or move to a dedicated OpenAPI linter in CI.

## Stubbing Rule

Stub APIs sparingly.

Do not stub every future endpoint. Stub only contract-defining APIs that are
part of the next two work-plan phases or are needed to stabilize UI/domain
design.

Stubbed APIs must:

- return `501 Not Implemented`
- define request and response shapes in OpenAPI
- have a contract test
- be marked clearly as planned behavior, not working behavior

Current near-term candidates:

- artifact links
- artifact update
- runner invocation
- evaluation invocation
- gate decision creation

Do not stub Langfuse, live LLM routing, or comparison endpoints until they are
close enough to implementation to validate the contract.
