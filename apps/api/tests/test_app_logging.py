import io
import logging
from datetime import datetime, timezone

import edd_platform_api.main  # noqa: F401  (importing the app configures logging)
from edd_platform_api.schemas import Scenario


def _stored_scenario(status: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": "scenario_logging",
        "project_id": "project_default",
        "agent_design_id": "agent_logging",
        "name": "Logging test",
        "input": "Hello",
        "setup_context": "",
        "fixture_refs": [],
        "status": status,
        "created_at": now,
        "updated_at": now,
    }


def _app_handler() -> logging.Handler:
    handlers = logging.getLogger("edd_platform_api").handlers
    assert len(handlers) == 1
    return handlers[0]


def test_schema_warning_reaches_the_app_handler_with_time_and_logger_name() -> None:
    handler = _app_handler()
    stream = io.StringIO()
    previous = handler.setStream(stream)
    root = logging.getLogger()
    root_level = root.level
    root.setLevel(logging.CRITICAL)
    try:
        Scenario.model_validate(_stored_scenario("archived"))
    finally:
        handler.setStream(previous)
        root.setLevel(root_level)

    line = stream.getvalue()
    assert "WARNING edd_platform_api.schemas: Scenario status 'archived' is not valid" in line
    assert line[:4].isdigit()  # starts with the asctime timestamp
