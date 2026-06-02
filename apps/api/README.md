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
- `GET /api/projects/{project_id}/artifacts`
- `GET /api/projects/{project_id}/artifacts/search`
- `GET /api/projects/{project_id}/artifacts/{artifact_id}`
- `POST /api/projects/{project_id}/context-packs`
