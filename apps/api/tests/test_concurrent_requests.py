import sys
import threading

from fastapi.testclient import TestClient

from edd_platform_api.main import app
from edd_platform_api.state import _agent_designs, default_project


def test_listing_agents_while_another_request_adds_one_does_not_fail() -> None:
    # FastAPI runs sync routes on a thread pool, so one request can add an
    # agent while another is looping over the agents to list them.
    client = TestClient(app, raise_server_exceptions=False)
    template = client.post(
        f"/api/projects/{default_project.id}/agent-designs",
        json={"name": "Concurrency template", "intent": "Template for added agents."},
    ).json()["agent"]
    agent = _agent_designs[template["id"]]
    stop = threading.Event()

    def add_and_remove_agents() -> None:
        index = 0
        while not stop.is_set():
            agent_id = f"agent_concurrency_{index % 50}"
            _agent_designs[agent_id] = agent.model_copy(update={"id": agent_id})
            _agent_designs.pop(f"agent_concurrency_{(index + 25) % 50}", None)
            index += 1

    previous_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    writer = threading.Thread(target=add_and_remove_agents)
    writer.start()
    try:
        statuses = [
            client.get(f"/api/projects/{default_project.id}/agent-designs").status_code
            for _ in range(200)
        ]
    finally:
        stop.set()
        writer.join()
        sys.setswitchinterval(previous_interval)
        for agent_id in [key for key in list(_agent_designs) if key.startswith("agent_concurrency_")]:
            _agent_designs.pop(agent_id, None)

    assert statuses == [200] * len(statuses)
