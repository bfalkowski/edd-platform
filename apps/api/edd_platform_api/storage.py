from __future__ import annotations

import json
import os
from typing import Dict, Protocol, Type, TypeVar

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)


class JsonStore(Protocol):
    def load_collection(self, collection: str, model: Type[ModelT]) -> Dict[str, ModelT]:
        ...

    def save_record(self, collection: str, record_id: str, record: BaseModel) -> None:
        ...

    def delete_record(self, collection: str, record_id: str) -> None:
        ...


class InMemoryJsonStore:
    def __init__(self) -> None:
        self._records: Dict[str, Dict[str, str]] = {}

    def load_collection(self, collection: str, model: Type[ModelT]) -> Dict[str, ModelT]:
        records = self._records.get(collection, {})
        return {
            record_id: model.model_validate(json.loads(payload))
            for record_id, payload in records.items()
        }

    def save_record(self, collection: str, record_id: str, record: BaseModel) -> None:
        records = self._records.setdefault(collection, {})
        records[record_id] = json.dumps(record.model_dump(mode="json"), sort_keys=True)

    def delete_record(self, collection: str, record_id: str) -> None:
        self._records.get(collection, {}).pop(record_id, None)


class PostgresJsonStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._initialize()

    def load_collection(self, collection: str, model: Type[ModelT]) -> Dict[str, ModelT]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, payload FROM platform_records WHERE collection = %s",
                    (collection,),
                )
                rows = cursor.fetchall()
        return {
            row[0]: model.model_validate(row[1])
            for row in rows
        }

    def save_record(self, collection: str, record_id: str, record: BaseModel) -> None:
        payload = json.dumps(record.model_dump(mode="json"), sort_keys=True)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO platform_records (collection, id, payload)
                    VALUES (%s, %s, %s::jsonb)
                    ON CONFLICT(collection, id)
                    DO UPDATE SET payload = excluded.payload
                    """,
                    (collection, record_id, payload),
                )

    def delete_record(self, collection: str, record_id: str) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM platform_records WHERE collection = %s AND id = %s",
                    (collection, record_id),
                )

    def _initialize(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS platform_records (
                        collection TEXT NOT NULL,
                        id TEXT NOT NULL,
                        payload JSONB NOT NULL,
                        PRIMARY KEY (collection, id)
                    )
                    """
                )

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "Postgres storage requires psycopg. Install API dependencies before starting the app."
            ) from exc
        return psycopg.connect(self.database_url)


def create_store_from_env() -> JsonStore:
    backend = os.getenv("EDD_PLATFORM_STORAGE_BACKEND", "postgres").lower()
    if backend == "memory":
        return InMemoryJsonStore()
    if backend != "postgres":
        raise RuntimeError(f"Unsupported storage backend: {backend}")

    database_url = os.getenv(
        "EDD_PLATFORM_DATABASE_URL",
        "postgresql://edd_platform:edd_platform@127.0.0.1:5432/edd_platform",
    )
    return PostgresJsonStore(database_url)
