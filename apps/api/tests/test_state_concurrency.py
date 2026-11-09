import threading
from datetime import datetime, timezone

from edd_platform_api.routers.artifacts import list_project_artifacts
from edd_platform_api.schemas import ArtifactRecord
from edd_platform_api.state import _artifacts


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
