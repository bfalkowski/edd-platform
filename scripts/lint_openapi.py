from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Set


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))
os.environ.setdefault("EDD_PLATFORM_STORAGE_BACKEND", "memory")

from edd_platform_api.main import app  # noqa: E402


REQUIRED_PATHS = {
    "/api/projects",
    "/api/projects/{project_id}",
    "/api/projects/{project_id}/tools",
    "/api/projects/{project_id}/tools/{tool_id}/adapter-contracts",
    "/api/projects/{project_id}/agent-designs",
    "/api/projects/{project_id}/agent-designs/{agent_id}",
    "/api/projects/{project_id}/agent-designs/{agent_id}/runs",
    "/api/projects/{project_id}/agent-designs/{agent_id}/versions",
    "/api/projects/{project_id}/agent-designs/{agent_id}/versions/{version_id}",
    "/api/projects/{project_id}/agent-suggestions",
    "/api/projects/{project_id}/agent-suggestions/{suggestion_id}",
    "/api/projects/{project_id}/artifact-links",
    "/api/projects/{project_id}/artifacts",
    "/api/projects/{project_id}/artifacts/search",
    "/api/projects/{project_id}/artifacts/{artifact_id}",
    "/api/projects/{project_id}/artifacts/{artifact_id}/evaluate",
    "/api/projects/{project_id}/artifacts/{artifact_id}/links",
    "/api/projects/{project_id}/comparisons",
    "/api/projects/{project_id}/comparisons/{comparison_id}",
    "/api/projects/{project_id}/context-packs",
    "/api/projects/{project_id}/eval-contracts",
    "/api/projects/{project_id}/eval-contracts/{contract_id}",
    "/api/projects/{project_id}/eval-results",
    "/api/projects/{project_id}/eval-results/{eval_result_id}",
    "/api/projects/{project_id}/failure-packets",
    "/api/projects/{project_id}/failure-packets/{failure_packet_id}",
    "/api/projects/{project_id}/failure-modes",
    "/api/projects/{project_id}/failure-modes/{failure_mode_id}",
    "/api/projects/{project_id}/fix-proposals",
    "/api/projects/{project_id}/fix-proposals/{fix_proposal_id}",
    "/api/projects/{project_id}/runs",
    "/api/projects/{project_id}/runs/{run_id}",
    "/api/projects/{project_id}/runs/{run_id}/evaluate",
    "/api/projects/{project_id}/review-notes",
    "/api/projects/{project_id}/review-notes/{review_note_id}",
    "/api/projects/{project_id}/review-corpora",
    "/api/projects/{project_id}/review-corpora/{corpus_id}",
    "/api/projects/{project_id}/review-corpora/{corpus_id}/analysis",
    "/api/projects/{project_id}/review-corpora/{corpus_id}/sampling-plan",
    "/api/projects/{project_id}/review-corpora/{corpus_id}/langfuse-items",
    "/api/projects/{project_id}/review-corpora/{corpus_id}/langfuse-annotations",
    "/api/projects/{project_id}/review-items",
    "/api/projects/{project_id}/review-items/{review_item_id}",
    "/api/projects/{project_id}/review-annotations",
    "/api/projects/{project_id}/review-annotations/{annotation_id}",
    "/api/projects/{project_id}/review-annotations/{annotation_id}/promote",
    "/api/projects/{project_id}/scenarios",
    "/api/projects/{project_id}/scenarios/{scenario_id}",
}


def lint_openapi(schema: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    if not str(schema.get("openapi", "")).startswith("3."):
        errors.append("OpenAPI version must start with 3.")

    info = schema.get("info", {})
    if info.get("title") != "EDD Platform API":
        errors.append("OpenAPI info.title must be EDD Platform API.")

    paths = schema.get("paths", {})
    missing_paths = sorted(REQUIRED_PATHS - set(paths))
    for path in missing_paths:
        errors.append(f"Missing required path: {path}")

    operation_ids: Set[str] = set()
    for path, operations in paths.items():
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                errors.append(f"{method.upper()} {path} is missing operationId.")
                continue
            if operation_id in operation_ids:
                errors.append(f"Duplicate operationId: {operation_id}")
            operation_ids.add(operation_id)
            if not operation.get("summary"):
                errors.append(f"{method.upper()} {path} is missing summary.")

    return errors


def main() -> None:
    errors = lint_openapi(app.openapi())
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print("OpenAPI contract lint passed.")


if __name__ == "__main__":
    main()
