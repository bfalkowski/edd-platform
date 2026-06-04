from edd_langfuse_adapter import (
    LangfuseTraceRef,
    build_langfuse_trace_url,
    build_trace_ref_payload,
)


def test_build_langfuse_trace_url_normalizes_base_url() -> None:
    assert build_langfuse_trace_url(
        base_url="https://cloud.langfuse.com/",
        project_id="project_demo",
        trace_id="trace_123",
    ) == "https://cloud.langfuse.com/project/project_demo/traces/trace_123"


def test_trace_ref_payload_matches_platform_contract() -> None:
    payload = build_trace_ref_payload(
        trace_id="trace_123",
        run_id="run_abc",
        base_url="https://cloud.langfuse.com",
        langfuse_project_id="project_demo",
        metadata={"environment": "local"},
        related_artifact_ids=["artifact_eval"],
    )

    assert payload == {
        "provider": "langfuse",
        "external_trace_id": "trace_123",
        "run_id": "run_abc",
        "url": "https://cloud.langfuse.com/project/project_demo/traces/trace_123",
        "metadata": {"environment": "local"},
        "related_artifact_ids": ["artifact_eval"],
    }


def test_trace_ref_model_can_emit_platform_payload() -> None:
    trace_ref = LangfuseTraceRef(
        external_trace_id="trace_456",
        run_id="run_def",
        url="https://cloud.langfuse.com/project/project_demo/traces/trace_456",
    )

    assert trace_ref.to_platform_payload()["provider"] == "langfuse"
    assert trace_ref.to_platform_payload()["external_trace_id"] == "trace_456"
