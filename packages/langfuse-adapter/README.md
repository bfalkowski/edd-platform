# packages/langfuse-adapter

Optional Langfuse trace evidence integration.

Langfuse is not required for local development or CI. When enabled, this package
builds platform `TraceRef` payloads from Langfuse trace ids and project URLs.

Langfuse remains the source of truth for raw trace observability. The platform
stores only trace references and links them to EDD evidence artifacts.

Current helpers:

- `build_langfuse_trace_url`
- `build_trace_ref_payload`
- `LangfuseTraceRef.to_platform_payload`

Example:

```python
from edd_langfuse_adapter import build_trace_ref_payload

payload = build_trace_ref_payload(
    trace_id="trace_123",
    run_id="run_abc",
    base_url="https://cloud.langfuse.com",
    langfuse_project_id="project_demo",
    related_artifact_ids=["artifact_eval"],
)
```

Send the payload to:

```text
POST /api/projects/{project_id}/trace-refs
```
