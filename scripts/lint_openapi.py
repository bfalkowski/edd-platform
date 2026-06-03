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
    "/api/projects/{project_id}/agent-designs",
    "/api/projects/{project_id}/agent-designs/{agent_id}",
    "/api/projects/{project_id}/agent-designs/{agent_id}/runs",
    "/api/projects/{project_id}/artifact-links",
    "/api/projects/{project_id}/artifacts",
    "/api/projects/{project_id}/artifacts/search",
    "/api/projects/{project_id}/artifacts/{artifact_id}",
    "/api/projects/{project_id}/artifacts/{artifact_id}/evaluate",
    "/api/projects/{project_id}/artifacts/{artifact_id}/links",
    "/api/projects/{project_id}/context-packs",
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
