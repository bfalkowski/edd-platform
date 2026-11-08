import importlib.util
import json
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from edd_platform_api import main as api_main
from edd_platform_api.main import app

import edd_runner  # noqa: E402  (importable once main has put the runner on sys.path)


SEED_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "seed_customer_triage_demo.py"


def load_seed_script(monkeypatch, client: TestClient, calls: list):
    spec = importlib.util.spec_from_file_location("seed_customer_triage_demo", SEED_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def request_via_client(method: str, path: str, payload: Optional[dict] = None):
        calls.append((method, path))
        response = client.request(method, path, json=payload)
        if response.status_code >= 400:
            raise SystemExit(f"{method} {path} failed with {response.status_code}: {response.text}")
        return response.json()

    monkeypatch.setattr(module, "request_json", request_via_client)
    return module


def test_seed_stops_before_writing_when_no_anthropic_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    calls: list = []
    seed = load_seed_script(monkeypatch, TestClient(app), calls)

    with pytest.raises(SystemExit) as exc_info:
        seed.main()

    message = str(exc_info.value.code)
    assert "ANTHROPIC_API_KEY" in message
    assert "\n" not in message
    assert [method for method, _path in calls if method != "GET"] == []


def test_seed_stores_live_anthropic_runs_and_prints_summary(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setattr(edd_runner, "build_langchain_tools", lambda _definitions: [])
    monkeypatch.setattr(
        edd_runner,
        "send_anthropic_messages_request",
        lambda _config, _body: {
            "content": [{"type": "text", "text": "Please share the deployment logs."}],
            "stop_reason": "end_turn",
        },
    )
    monkeypatch.setattr(
        api_main,
        "run_live_judge",
        lambda _prompt, trace_id=None: ("PASS: asks for logs.", "test-judge-model", {}),
    )
    client = TestClient(app)
    seed = load_seed_script(monkeypatch, client, [])

    seed.main()

    summary = json.loads(capsys.readouterr().out)
    assert summary["v0_score"] == "2/2"
    assert summary["v1_score"] == "2/2"
    assert summary["comparison"]
    assert summary["runs"] == {"v0": "live / anthropic", "v1": "live / anthropic"}
    runs = client.get(
        f"/api/projects/project_default/runs?agent_design_id={summary['agent_id']}"
    ).json()
    assert len(runs) == 2
    assert {(run["mode"], run["provider"]) for run in runs} == {("live", "anthropic")}
