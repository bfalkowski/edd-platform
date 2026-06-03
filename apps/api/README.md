# apps/api

FastAPI backend for EDD Platform.

This app owns persistence, agent designs, judge prompts, gates, evidence
context, promotion, and integration boundaries.

Current first slice:

- `GET /health`
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `GET /api/projects/{project_id}/agent-designs`
- `POST /api/projects/{project_id}/agent-designs`
- `GET /api/projects/{project_id}/agent-designs/{agent_id}`
- `DELETE /api/projects/{project_id}/agent-designs/{agent_id}`
- `POST /api/projects/{project_id}/agent-designs/{agent_id}/runs`
- `POST /api/projects/{project_id}/artifact-links`
- `GET /api/projects/{project_id}/artifacts`
- `GET /api/projects/{project_id}/artifacts/search`
- `GET /api/projects/{project_id}/artifacts/{artifact_id}`
- `POST /api/projects/{project_id}/artifacts/{artifact_id}/evaluate`
- `GET /api/projects/{project_id}/artifacts/{artifact_id}/links`
- `POST /api/projects/{project_id}/context-packs`

Local state is stored in Postgres by default. The API reads
`EDD_PLATFORM_DATABASE_URL`, defaulting to
`postgresql://edd_platform:edd_platform@127.0.0.1:5432/edd_platform`.

Tests use `EDD_PLATFORM_STORAGE_BACKEND=memory` so they do not require a
database service.

Run requests default to deterministic mock mode. To use live OpenAI mode, set
`OPENAI_API_KEY` before starting the API and send `"mode": "live"` to the run
endpoint. The default live model is `gpt-5-nano`; set `EDD_OPENAI_MODEL` to
override it.
