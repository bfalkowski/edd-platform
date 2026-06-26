from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from edd_platform_api.main import app


def create_agent(client: TestClient) -> dict:
    response = client.post(
        "/api/projects/project_default/agent-designs",
        json={
            "name": "Discovery Agent",
            "intent": "Review traces and discover failure modes.",
        },
    )
    assert response.status_code == 201
    return response.json()["agent"]


def test_review_corpus_trace_annotation_failure_mode_and_suggestion_flow() -> None:
    client = TestClient(app)
    agent = create_agent(client)

    corpus_response = client.post(
        "/api/projects/project_default/review-corpora",
        json={
            "agent_design_id": agent["id"],
            "name": "Open coding pass",
            "description": "Review Langfuse generation observations.",
            "source": "langfuse",
            "langfuse_queue_id": "queue_open_coding",
            "langfuse_score_config_ids": ["score_open_coding", "score_pass_fail"],
            "status": "active",
        },
    )

    assert corpus_response.status_code == 201
    corpus = corpus_response.json()
    assert corpus["langfuse_queue_id"] == "queue_open_coding"
    assert corpus["artifact_ids"]

    item_response = client.post(
        "/api/projects/project_default/review-items",
        json={
            "corpus_id": corpus["id"],
            "source_kind": "trace",
            "source_id": "trace_123",
            "title": "Trace 123 final response",
            "content": "The agent refused to look up current device information.",
            "langfuse_ref": {
                "trace_id": "trace_123",
                "observation_id": "generation_456",
                "object_type": "OBSERVATION",
                "url": "https://us.cloud.langfuse.com/project/proj/traces/trace_123",
                "queue_id": "queue_open_coding",
                "score_ids": ["score_open_coding"],
            },
            "metadata": {"sampling_reason": "high_latency"},
        },
    )

    assert item_response.status_code == 201
    item = item_response.json()
    assert item["agent_design_id"] == agent["id"]
    assert item["langfuse_ref"]["object_type"] == "OBSERVATION"
    assert item["langfuse_ref"]["observation_id"] == "generation_456"

    failure_mode_response = client.post(
        "/api/projects/project_default/failure-modes",
        json={
            "agent_design_id": agent["id"],
            "name": "missing_device_lookup",
            "description": "Answered generically without checking device-specific facts.",
            "root_cause": "The agent did not use the available lookup path before answering.",
            "severity": "high",
            "status": "confirmed",
            "langfuse_score_name": "failure_missing_device_lookup",
        },
    )

    assert failure_mode_response.status_code == 201
    failure_mode = failure_mode_response.json()
    assert failure_mode["name"] == "missing_device_lookup"
    assert failure_mode["langfuse_score_name"] == "failure_missing_device_lookup"

    annotation_response = client.post(
        "/api/projects/project_default/review-annotations",
        json={
            "review_item_id": item["id"],
            "body": "Agent gave generic advice instead of checking the user's device.",
            "quote": "refused to look up current device information",
            "author": "human",
            "failure_mode_id": failure_mode["id"],
            "langfuse_score_id": "score_open_coding_value",
            "status": "accepted",
        },
    )

    assert annotation_response.status_code == 201
    annotation = annotation_response.json()
    assert annotation["corpus_id"] == corpus["id"]
    assert annotation["failure_mode_id"] == failure_mode["id"]
    assert annotation["status"] == "accepted"

    suggestion_response = client.post(
        "/api/projects/project_default/agent-suggestions",
        json={
            "review_item_id": item["id"],
            "failure_mode_id": failure_mode["id"],
            "body": "Likely another missing_device_lookup instance.",
            "quote": "refused to look up",
            "rationale": "Matches the confirmed failure mode definition.",
            "confidence": 0.82,
            "status": "pending",
        },
    )

    assert suggestion_response.status_code == 201
    suggestion = suggestion_response.json()
    assert suggestion["status"] == "pending"
    assert suggestion["failure_mode_id"] == failure_mode["id"]

    accepted_response = client.patch(
        f"/api/projects/project_default/agent-suggestions/{suggestion['id']}",
        json={"status": "accepted"},
    )

    assert accepted_response.status_code == 200
    assert accepted_response.json()["status"] == "accepted"

    annotations_response = client.get(
        "/api/projects/project_default/review-annotations",
        params={"failure_mode_id": failure_mode["id"]},
    )

    assert annotations_response.status_code == 200
    assert annotations_response.json()[0]["id"] == annotation["id"]


def test_trace_review_item_requires_langfuse_trace_or_observation_ref() -> None:
    client = TestClient(app)
    agent = create_agent(client)
    corpus = client.post(
        "/api/projects/project_default/review-corpora",
        json={"agent_design_id": agent["id"], "name": "Invalid trace corpus"},
    ).json()

    response = client.post(
        "/api/projects/project_default/review-items",
        json={
            "corpus_id": corpus["id"],
            "source_kind": "trace",
            "source_id": "trace_without_ref",
            "title": "Trace without ref",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Trace review items require a Langfuse trace or observation reference."
    )


def test_langfuse_item_and_annotation_import_materializes_discovery_records() -> None:
    client = TestClient(app)
    agent = create_agent(client)
    corpus = client.post(
        "/api/projects/project_default/review-corpora",
        json={
            "agent_design_id": agent["id"],
            "name": "Langfuse queue import",
            "source": "langfuse",
            "langfuse_queue_id": "queue_123",
            "langfuse_score_config_ids": ["open_coding", "pass_fail", "category"],
        },
    ).json()

    import_response = client.post(
        f"/api/projects/project_default/review-corpora/{corpus['id']}/langfuse-items",
        json={
            "items": [
                {
                    "source_id": "trace_alpha:generation_final",
                    "title": "Final generation for trace alpha",
                    "content": "The model skipped the refund policy lookup.",
                    "trace_id": "trace_alpha",
                    "observation_id": "generation_final",
                    "object_type": "OBSERVATION",
                    "url": "https://us.cloud.langfuse.com/project/demo/traces/trace_alpha",
                    "score_ids": ["score_open_coding_alpha"],
                    "metadata": {"latency_ms": 1200},
                },
                {
                    "source_id": "trace_alpha:generation_final",
                    "title": "Duplicate final generation",
                    "trace_id": "trace_alpha",
                    "observation_id": "generation_final",
                    "object_type": "OBSERVATION",
                },
                {
                    "source_id": "trace_without_object",
                    "title": "No reviewable object",
                },
            ]
        },
    )

    assert import_response.status_code == 201
    import_payload = import_response.json()
    assert import_payload["imported_count"] == 1
    assert import_payload["skipped_count"] == 2
    item = import_payload["review_items"][0]
    assert item["langfuse_ref"]["queue_id"] == "queue_123"
    assert item["langfuse_ref"]["object_type"] == "OBSERVATION"
    assert item["metadata"]["import_source"] == "langfuse"

    annotation_response = client.post(
        f"/api/projects/project_default/review-corpora/{corpus['id']}/langfuse-annotations",
        json={
            "annotations": [
                {
                    "observation_id": "generation_final",
                    "open_coding": "Skipped lookup and answered from memory.",
                    "pass_fail": "fail",
                    "failure_mode_name": "missing_policy_lookup",
                    "failure_mode_description": "The agent answers without checking required policy evidence.",
                    "langfuse_score_id": "score_category_alpha",
                    "metadata": {"reviewer": "human@example.com"},
                },
                {
                    "source_id": "missing_trace",
                    "open_coding": "Cannot match this row to a review item.",
                    "pass_fail": "unknown",
                },
            ]
        },
    )

    assert annotation_response.status_code == 201
    annotation_payload = annotation_response.json()
    assert annotation_payload["imported_count"] == 1
    assert annotation_payload["skipped_count"] == 1
    assert annotation_payload["failure_modes"][0]["name"] == "missing_policy_lookup"
    annotation = annotation_payload["annotations"][0]
    assert annotation["body"] == "Skipped lookup and answered from memory."
    assert annotation["langfuse_score_id"] == "score_category_alpha"
    assert annotation["metadata"]["pass_fail"] == "fail"

    item_response = client.get(f"/api/projects/project_default/review-items/{item['id']}")
    assert item_response.status_code == 200
    assert item_response.json()["status"] == "reviewed"

    artifacts_response = client.get(
        "/api/projects/project_default/artifacts",
        params={"agent_design_id": agent["id"], "artifact_type": "FAILURE_MODE"},
    )
    assert artifacts_response.status_code == 200
    assert artifacts_response.json()[0]["title"] == "missing_policy_lookup"


def test_sampling_plan_explains_breadth_depth_and_recoding_candidates() -> None:
    client = TestClient(app)
    agent = create_agent(client)
    corpus = client.post(
        "/api/projects/project_default/review-corpora",
        json={
            "agent_design_id": agent["id"],
            "name": "Sampling corpus",
            "source": "langfuse",
        },
    ).json()

    import_response = client.post(
        f"/api/projects/project_default/review-corpora/{corpus['id']}/langfuse-items",
        json={
            "items": [
                {
                    "source_id": "trace_reviewed:generation",
                    "title": "Reviewed generic answer",
                    "content": "The answer was reviewed before we named the policy lookup issue.",
                    "trace_id": "trace_reviewed",
                    "observation_id": "generation_reviewed",
                    "object_type": "OBSERVATION",
                },
                {
                    "source_id": "trace_unreviewed:generation",
                    "title": "Unreviewed policy miss",
                    "content": "The agent skipped the required policy lookup before answering.",
                    "trace_id": "trace_unreviewed",
                    "observation_id": "generation_unreviewed",
                    "object_type": "OBSERVATION",
                },
            ]
        },
    )
    items = import_response.json()["review_items"]
    reviewed_item = next(item for item in items if item["source_id"] == "trace_reviewed:generation")
    unreviewed_item = next(
        item for item in items if item["source_id"] == "trace_unreviewed:generation"
    )

    annotation_response = client.post(
        f"/api/projects/project_default/review-corpora/{corpus['id']}/langfuse-annotations",
        json={
            "annotations": [
                {
                    "review_item_id": reviewed_item["id"],
                    "open_coding": "Generic answer without a named mode yet.",
                    "pass_fail": "fail",
                }
            ]
        },
    )
    assert annotation_response.status_code == 201

    mode_response = client.post(
        "/api/projects/project_default/failure-modes",
        json={
            "agent_design_id": agent["id"],
            "name": "missing_policy_lookup",
            "description": "The agent skipped required policy lookup evidence.",
            "severity": "high",
            "status": "confirmed",
        },
    )
    mode = mode_response.json()

    plan_response = client.get(
        f"/api/projects/project_default/review-corpora/{corpus['id']}/sampling-plan",
        params={"create_suggestions": "true"},
    )

    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["coverage"] == {
        "total_items": 2,
        "reviewed_items": 1,
        "unreviewed_items": 1,
        "accepted_annotations": 1,
        "failure_modes": 1,
        "pending_suggestions": 2,
    }
    assert plan["breadth_candidates"][0]["review_item_id"] == unreviewed_item["id"]
    assert any(
        candidate["review_item_id"] == unreviewed_item["id"]
        and candidate["failure_mode_id"] == mode["id"]
        for candidate in plan["depth_candidates"]
    )
    assert any(
        candidate["review_item_id"] == reviewed_item["id"]
        and candidate["failure_mode_id"] == mode["id"]
        for candidate in plan["recoding_prompts"]
    )
    assert len(plan["generated_suggestions"]) == 2

    suggestions_response = client.get(
        "/api/projects/project_default/agent-suggestions",
        params={"corpus_id": corpus["id"], "status": "pending"},
    )
    assert suggestions_response.status_code == 200
    assert len(suggestions_response.json()) == 2


def test_review_corpus_analysis_uses_polars_for_failure_rates() -> None:
    client = TestClient(app)
    agent = create_agent(client)
    corpus = client.post(
        "/api/projects/project_default/review-corpora",
        json={
            "agent_design_id": agent["id"],
            "name": "Polars analysis corpus",
            "source": "langfuse",
        },
    ).json()

    import_response = client.post(
        f"/api/projects/project_default/review-corpora/{corpus['id']}/langfuse-items",
        json={
            "items": [
                {
                    "source_id": "trace_failed:generation",
                    "title": "Failed generation",
                    "content": "The agent skipped policy evidence.",
                    "trace_id": "trace_failed",
                    "observation_id": "generation_failed",
                    "object_type": "OBSERVATION",
                },
                {
                    "source_id": "trace_passed:generation",
                    "title": "Passed generation",
                    "content": "The agent checked policy evidence.",
                    "trace_id": "trace_passed",
                    "observation_id": "generation_passed",
                    "object_type": "OBSERVATION",
                },
            ]
        },
    )
    items = import_response.json()["review_items"]
    failed_item = next(item for item in items if item["source_id"] == "trace_failed:generation")
    passed_item = next(item for item in items if item["source_id"] == "trace_passed:generation")
    mode = client.post(
        "/api/projects/project_default/failure-modes",
        json={
            "agent_design_id": agent["id"],
            "name": "missing_policy_evidence",
            "description": "The agent skipped policy evidence.",
            "severity": "high",
            "status": "confirmed",
        },
    ).json()

    annotation_response = client.post(
        f"/api/projects/project_default/review-corpora/{corpus['id']}/langfuse-annotations",
        json={
            "annotations": [
                {
                    "review_item_id": failed_item["id"],
                    "open_coding": "Skipped policy evidence.",
                    "pass_fail": "fail",
                    "failure_mode_name": mode["name"],
                },
                {
                    "review_item_id": passed_item["id"],
                    "open_coding": "Checked policy evidence.",
                    "pass_fail": "pass",
                },
            ]
        },
    )
    assert annotation_response.status_code == 201

    analysis_response = client.get(
        f"/api/projects/project_default/review-corpora/{corpus['id']}/analysis"
    )

    assert analysis_response.status_code == 200
    analysis = analysis_response.json()
    assert analysis["backend"] == "polars"
    assert analysis["coverage"]["total_items"] == 2
    assert analysis["coverage"]["reviewed_items"] == 2
    assert analysis["source_kind_counts"] == {"trace": 2}
    assert analysis["annotation_status_counts"] == {"accepted": 2}
    assert analysis["pass_fail_counts"] == {"fail": 1, "pass": 1}
    assert analysis["failure_rates"] == [
        {
            "source_kind": "trace",
            "total_items": 2,
            "reviewed_items": 2,
            "failed_items": 1,
            "failure_rate": 0.5,
        }
    ]
    assert analysis["failure_mode_counts"][0]["name"] == "missing_policy_evidence"


def test_review_corpus_analysis_materializes_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("EDD_PLATFORM_ANALYSIS_SNAPSHOT_DIR", str(tmp_path))
    client = TestClient(app)
    agent = create_agent(client)
    corpus = client.post(
        "/api/projects/project_default/review-corpora",
        json={
            "agent_design_id": agent["id"],
            "name": "Snapshot analysis corpus",
            "source": "langfuse",
        },
    ).json()

    import_response = client.post(
        f"/api/projects/project_default/review-corpora/{corpus['id']}/langfuse-items",
        json={
            "items": [
                {
                    "source_id": "snapshot_trace:generation",
                    "title": "Snapshot generation",
                    "content": "The agent skipped evidence.",
                    "trace_id": "snapshot_trace",
                    "observation_id": "snapshot_generation",
                    "object_type": "OBSERVATION",
                },
            ]
        },
    )
    item = import_response.json()["review_items"][0]
    annotation_response = client.post(
        f"/api/projects/project_default/review-corpora/{corpus['id']}/langfuse-annotations",
        json={
            "annotations": [
                {
                    "review_item_id": item["id"],
                    "open_coding": "Skipped evidence.",
                    "pass_fail": "fail",
                    "failure_mode_name": "snapshot_missing_evidence",
                },
            ]
        },
    )
    assert annotation_response.status_code == 201

    analysis_response = client.get(
        f"/api/projects/project_default/review-corpora/{corpus['id']}/analysis"
    )

    assert analysis_response.status_code == 200
    analysis = analysis_response.json()
    assert analysis["coverage"]["total_items"] == 1
    assert analysis["snapshot"]["status"] == "loaded"
    assert analysis["snapshot"]["item_count"] == 1
    assert analysis["snapshot"]["annotation_count"] == 1
    snapshot_dir = (
        tmp_path
        / "projects"
        / "project_default"
        / "review-corpora"
        / corpus["id"]
    )
    assert (snapshot_dir / "review_items.parquet").exists()
    assert (snapshot_dir / "annotations.parquet").exists()
    assert (snapshot_dir / "failure_modes.parquet").exists()
    assert (snapshot_dir / "metadata.json").exists()


def test_promote_annotation_creates_proof_loop_artifacts() -> None:
    client = TestClient(app)
    agent = create_agent(client)
    corpus = client.post(
        "/api/projects/project_default/review-corpora",
        json={"agent_design_id": agent["id"], "name": "Promotion corpus"},
    ).json()
    item = client.post(
        "/api/projects/project_default/review-items",
        json={
            "corpus_id": corpus["id"],
            "source_kind": "trace",
            "source_id": "trace_promote",
            "title": "Promotable policy miss",
            "content": "The agent answered without checking the refund policy.",
            "langfuse_ref": {
                "trace_id": "trace_promote",
                "object_type": "TRACE",
                "url": "https://cloud.langfuse.com/project/demo/traces/trace_promote",
            },
        },
    ).json()
    mode = client.post(
        "/api/projects/project_default/failure-modes",
        json={
            "agent_design_id": agent["id"],
            "name": "missing_refund_policy",
            "description": "The agent must check refund policy evidence before answering.",
            "severity": "high",
            "status": "confirmed",
        },
    ).json()
    annotation = client.post(
        "/api/projects/project_default/review-annotations",
        json={
            "review_item_id": item["id"],
            "body": "Answered from memory instead of checking refund policy evidence.",
            "author": "human",
            "failure_mode_id": mode["id"],
            "status": "accepted",
        },
    ).json()

    response = client.post(
        f"/api/projects/project_default/review-annotations/{annotation['id']}/promote",
        json={"create_failure_packet": True, "create_eval_case": True},
    )

    assert response.status_code == 201
    promotion = response.json()
    scenario = promotion["scenario"]
    contract = promotion["eval_contract"]
    failure_packet = promotion["failure_packet"]
    assert scenario["name"] == "Discovery case: Promotable policy miss"
    assert scenario["fixture_refs"]
    assert contract["scenario_id"] == scenario["id"]
    assert contract["checks"][0]["type"] == "manual_review_required"
    assert failure_packet["eval_contract_id"] == contract["id"]
    assert failure_packet["severity"] == "high"
    assert failure_packet["evidence_artifact_ids"]
    assert len(promotion["artifact_ids"]) >= 5

    scenarios_response = client.get(
        "/api/projects/project_default/scenarios",
        params={"agent_design_id": agent["id"]},
    )
    assert scenarios_response.status_code == 200
    assert scenarios_response.json()[0]["id"] == scenario["id"]

    packets_response = client.get(
        "/api/projects/project_default/failure-packets",
        params={"agent_design_id": agent["id"]},
    )
    assert packets_response.status_code == 200
    assert packets_response.json()[0]["id"] == failure_packet["id"]

    finding_artifact_id = promotion["artifact_ids"][0]
    links_response = client.get(
        f"/api/projects/project_default/artifacts/{finding_artifact_id}/links"
    )
    assert links_response.status_code == 200
    assert links_response.json()
