#!/usr/bin/env python3
"""Exercise the deterministic Error Analysis workflow against a local API."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


JsonObject = Dict[str, Any]


class ApiClient:
    def __init__(self, base_url: str, project_id: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.project_id = project_id

    def request(
        self,
        method: str,
        path: str,
        payload: Optional[JsonObject] = None,
        query: Optional[JsonObject] = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else None
        except HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc

    def create_agent(self) -> JsonObject:
        response = self.request(
            "POST",
            f"/projects/{self.project_id}/agent-designs",
            {
                "name": "Error Analysis E2E Agent",
                "intent": "Review traces, discover failures, and promote proof-loop evidence.",
            },
        )
        return response["agent"]

    def delete_agent(self, agent_id: str) -> None:
        self.request("DELETE", f"/projects/{self.project_id}/agent-designs/{agent_id}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def first_by_source(items: List[JsonObject], source_id: str) -> JsonObject:
    for item in items:
        if item["source_id"] == source_id:
            return item
    raise AssertionError(f"Missing imported review item {source_id!r}.")


def run_error_analysis_flow(client: ApiClient, cleanup: bool) -> JsonObject:
    agent = client.create_agent()
    try:
        corpus = client.request(
            "POST",
            f"/projects/{client.project_id}/review-corpora",
            {
                "agent_design_id": agent["id"],
                "name": "Error Analysis E2E Corpus",
                "description": "Deterministic trace review corpus for E2E validation.",
                "source": "langfuse",
                "langfuse_queue_id": "queue_error_analysis_e2e",
                "langfuse_score_config_ids": ["open_coding", "pass_fail", "category"],
                "status": "active",
            },
        )
        import_result = client.request(
            "POST",
            f"/projects/{client.project_id}/review-corpora/{corpus['id']}/langfuse-items",
            {
                "items": [
                    {
                        "source_id": "trace_failed:generation",
                        "title": "Failed refund generation",
                        "content": "The agent answered without checking refund policy evidence.",
                        "trace_id": "trace_failed",
                        "observation_id": "generation_failed",
                        "object_type": "OBSERVATION",
                        "url": "https://cloud.langfuse.com/project/demo/traces/trace_failed",
                    },
                    {
                        "source_id": "trace_passed:generation",
                        "title": "Passed refund generation",
                        "content": "The agent checked refund policy evidence before answering.",
                        "trace_id": "trace_passed",
                        "observation_id": "generation_passed",
                        "object_type": "OBSERVATION",
                    },
                    {
                        "source_id": "trace_unreviewed:generation",
                        "title": "Unreviewed policy miss",
                        "content": "Another answer skipped required refund policy lookup.",
                        "trace_id": "trace_unreviewed",
                        "observation_id": "generation_unreviewed",
                        "object_type": "OBSERVATION",
                    },
                ]
            },
        )
        require(import_result["imported_count"] == 3, "Expected three imported review items.")
        failed_item = first_by_source(
            import_result["review_items"],
            "trace_failed:generation",
        )
        passed_item = first_by_source(
            import_result["review_items"],
            "trace_passed:generation",
        )

        annotation_result = client.request(
            "POST",
            f"/projects/{client.project_id}/review-corpora/{corpus['id']}/langfuse-annotations",
            {
                "annotations": [
                    {
                        "review_item_id": failed_item["id"],
                        "open_coding": "Answered from memory instead of checking refund policy.",
                        "pass_fail": "fail",
                        "failure_mode_name": "missing_refund_policy_lookup",
                        "failure_mode_description": (
                            "The agent must check refund policy evidence before answering."
                        ),
                        "langfuse_score_id": "score_failed",
                    },
                    {
                        "review_item_id": passed_item["id"],
                        "open_coding": "Checked refund policy before answering.",
                        "pass_fail": "pass",
                        "langfuse_score_id": "score_passed",
                    },
                ]
            },
        )
        require(annotation_result["imported_count"] == 2, "Expected two imported annotations.")
        require(annotation_result["failure_modes"], "Expected a discovered failure mode.")
        failure_mode = annotation_result["failure_modes"][0]
        failed_annotation = next(
            annotation
            for annotation in annotation_result["annotations"]
            if annotation["review_item_id"] == failed_item["id"]
        )
        require(
            failed_annotation["failure_mode_id"] == failure_mode["id"],
            "Failed annotation should link to the imported failure mode.",
        )

        sampling_plan = client.request(
            "GET",
            f"/projects/{client.project_id}/review-corpora/{corpus['id']}/sampling-plan",
            query={"create_suggestions": "true"},
        )
        require(
            sampling_plan["coverage"]["total_items"] == 3,
            "Sampling coverage should include all review items.",
        )
        require(
            sampling_plan["coverage"]["reviewed_items"] == 2,
            "Sampling coverage should include reviewed items.",
        )
        require(
            sampling_plan["depth_candidates"],
            "Expected at least one depth candidate for the known failure mode.",
        )
        require(
            sampling_plan["generated_suggestions"],
            "Expected deterministic agent suggestions from sampling.",
        )

        analysis = client.request(
            "GET",
            f"/projects/{client.project_id}/review-corpora/{corpus['id']}/analysis",
        )
        require(analysis["backend"] == "polars", "Analysis should use the Polars backend.")
        require(
            analysis["pass_fail_counts"] == {"fail": 1, "pass": 1},
            f"Unexpected pass/fail counts: {analysis['pass_fail_counts']}",
        )
        require(
            analysis["failure_rates"][0]["failed_items"] == 1,
            "Expected one failed trace item in failure-rate table.",
        )

        promotion = client.request(
            "POST",
            f"/projects/{client.project_id}/review-annotations/{failed_annotation['id']}/promote",
            {"create_failure_packet": True, "create_eval_case": True},
        )
        require(promotion["scenario"], "Promotion should create a scenario.")
        require(promotion["eval_contract"], "Promotion should create an eval contract.")
        require(promotion["failure_packet"], "Promotion should create a failure packet.")
        require(
            promotion["failure_packet"]["severity"] == failure_mode["severity"],
            "Failure packet should preserve failure-mode severity.",
        )
        require(
            promotion["artifact_ids"],
            "Promotion should return linked artifact ids.",
        )

        failure_packets = client.request(
            "GET",
            f"/projects/{client.project_id}/failure-packets",
            query={"agent_design_id": agent["id"]},
        )
        require(
            any(packet["id"] == promotion["failure_packet"]["id"] for packet in failure_packets),
            "Promoted failure packet should be listable.",
        )

        return {
            "agent": agent["name"],
            "corpus_id": corpus["id"],
            "imported_items": import_result["imported_count"],
            "imported_annotations": annotation_result["imported_count"],
            "failure_mode": failure_mode["name"],
            "generated_suggestions": len(sampling_plan["generated_suggestions"]),
            "analysis_backend": analysis["backend"],
            "promoted_scenario_id": promotion["scenario"]["id"],
            "promoted_eval_contract_id": promotion["eval_contract"]["id"],
            "promoted_failure_packet_id": promotion["failure_packet"]["id"],
        }
    finally:
        if cleanup:
            client.delete_agent(agent["id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8001/api")
    parser.add_argument("--project-id", default="project_default")
    parser.add_argument(
        "--keep-agent",
        action="store_true",
        help="Leave the temporary agent and generated records for manual inspection.",
    )
    args = parser.parse_args()

    client = ApiClient(args.api_base_url, args.project_id)
    result = run_error_analysis_flow(client, cleanup=not args.keep_agent)
    print(
        "PASS error_analysis: "
        f"items={result['imported_items']} annotations={result['imported_annotations']} "
        f"suggestions={result['generated_suggestions']} "
        f"failure_packet={result['promoted_failure_packet_id']}"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
