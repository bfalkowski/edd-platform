import sys
import threading
from datetime import datetime, timezone

from edd_platform_api import main  # noqa: F401  (imported first: routers import main)
from edd_platform_api.routers.agent_designs import create_agent_version
from edd_platform_api.routers.artifacts import list_project_artifacts
from edd_platform_api.schemas import AgentDesign, AgentVersionCreate, ArtifactRecord
from edd_platform_api.state import _agent_designs, _agent_versions, _artifacts


def make_artifact(index: int) -> ArtifactRecord:
    now = datetime.now(timezone.utc)
    return ArtifactRecord(
        id=f"artifact_concurrency_{index}",
        project_id="project_concurrency",
        agent_design_id="agent_concurrency",
        artifact_type="RUN_RESULT",
        artifact_id=f"run_concurrency_{index}",
        title=f"Run {index}",
        body="Run output",
        source="test",
        created_at=now,
        updated_at=now,
    )


def test_listing_a_collection_survives_a_concurrent_insert() -> None:
    # FastAPI runs sync routes on a thread pool, so one request can add a record
    # while another iterates the same collection.
    for index in range(20_000):
        artifact = make_artifact(index)
        _artifacts[artifact.id] = artifact
    stop = threading.Event()

    def insert_records() -> None:
        index = 20_000
        while not stop.is_set():
            artifact = make_artifact(index)
            _artifacts[artifact.id] = artifact
            index += 1

    writer = threading.Thread(target=insert_records)
    writer.start()
    try:
        for _ in range(20):
            list_project_artifacts("project_default")
    finally:
        stop.set()
        writer.join()
        for artifact_id in [key for key in _artifacts if key.startswith("artifact_concurrency_")]:
            del _artifacts[artifact_id]


def test_concurrent_version_creates_get_distinct_labels() -> None:
    # create_agent_version labels a version "v{n}" by counting the agent's
    # versions. Two requests that count before either saves pick the same label.
    now = datetime.now(timezone.utc)
    agent = AgentDesign(
        id="agent_concurrency_versions",
        project_id="project_default",
        name="Concurrency agent",
        intent="Answer questions.",
        status="designing",
        created_at=now,
        updated_at=now,
    )
    _agent_designs[agent.id] = agent
    thread_count = 16
    start = threading.Barrier(thread_count)
    labels: list[str] = []

    def create_version() -> None:
        start.wait()
        version = create_agent_version("project_default", agent.id, AgentVersionCreate())
        labels.append(version.version_label)

    switch_interval = sys.getswitchinterval()
    # Switch threads as often as possible so a count and its save get interleaved.
    sys.setswitchinterval(1e-6)
    try:
        for _ in range(20):
            threads = [threading.Thread(target=create_version) for _ in range(thread_count)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
    finally:
        sys.setswitchinterval(switch_interval)
        del _agent_designs[agent.id]
        for version_id in [
            key for key, value in _agent_versions.items() if value.agent_design_id == agent.id
        ]:
            del _agent_versions[version_id]
        for artifact_id in [
            key for key, value in _artifacts.items() if value.agent_design_id == agent.id
        ]:
            del _artifacts[artifact_id]

    assert len(labels) == 20 * thread_count
    assert len(set(labels)) == len(labels)
