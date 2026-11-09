"""List routes reject query parameters they do not support instead of ignoring them."""

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from edd_platform_api.main import app

PROJECT = "/api/projects/project_default"


def _filtered_get_routes() -> list[APIRoute]:
    """Every GET route that declares query parameters, so a new filtered list route is covered too."""
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and "GET" in route.methods and route.dependant.query_params
    ]


def _url(path: str) -> str:
    return path.replace("{project_id}", "project_default").replace("{corpus_id}", "corpus_missing")


def test_judge_outputs_rejects_unsupported_run_id_filter() -> None:
    client = TestClient(app)

    response = client.get(f"{PROJECT}/judge-outputs", params={"run_id": "run_123"})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "run_id" in detail
    assert "eval_result_id" in detail


def test_judge_outputs_still_accepts_supported_filter() -> None:
    client = TestClient(app)

    response = client.get(f"{PROJECT}/judge-outputs", params={"eval_result_id": "missing"})

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("route", _filtered_get_routes(), ids=lambda route: route.path)
def test_filtered_routes_reject_unknown_query_parameter(route: APIRoute) -> None:
    client = TestClient(app)
    supported = sorted(param.alias for param in route.dependant.query_params)

    response = client.get(_url(route.path), params={"not_a_filter": "x"})

    assert response.status_code == 400
    assert response.json() == {
        "detail": (
            "Unsupported query parameter: not_a_filter. "
            f"Supported query parameters: {', '.join(supported)}."
        )
    }


def test_filtered_routes_cover_every_list_route_with_filters() -> None:
    paths = {route.path for route in _filtered_get_routes()}

    assert f"/api/projects/{{project_id}}/judge-outputs" in paths
    assert len(paths) == 20
