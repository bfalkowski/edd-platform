import os
from datetime import datetime, timezone

import pytest

from edd_platform_api.main import Project
from edd_platform_api.storage import InMemoryJsonStore, create_store_from_env


def test_memory_store_persists_records_within_instance() -> None:
    store = InMemoryJsonStore()
    project = Project(
        id="project_memory",
        name="Memory Project",
        description="Stored without an external database.",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    store.save_record("projects", project.id, project)

    projects = store.load_collection("projects", Project)
    assert projects[project.id].name == "Memory Project"


def test_storage_backend_rejects_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDD_PLATFORM_STORAGE_BACKEND", "sqlite")

    with pytest.raises(RuntimeError, match="Unsupported storage backend"):
        create_store_from_env()


def test_postgres_is_default_storage_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EDD_PLATFORM_STORAGE_BACKEND", raising=False)
    monkeypatch.setenv("EDD_PLATFORM_DATABASE_URL", "postgresql://user:pass@127.0.0.1/db")

    assert os.getenv("EDD_PLATFORM_STORAGE_BACKEND", "postgres") == "postgres"


def test_postgres_json_store_round_trips_records() -> None:
    database_url = os.getenv("EDD_PLATFORM_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("EDD_PLATFORM_TEST_DATABASE_URL is required for Postgres storage tests.")

    from edd_platform_api.storage import PostgresJsonStore

    store = PostgresJsonStore(database_url)
    project = Project(
        id="project_postgres_ci",
        name="Postgres CI Project",
        description="Stored in a real Postgres JSONB table.",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    store.save_record("test_projects", project.id, project)

    projects = store.load_collection("test_projects", Project)
    assert projects[project.id].name == "Postgres CI Project"

    store.delete_record("test_projects", project.id)
    assert project.id not in store.load_collection("test_projects", Project)
