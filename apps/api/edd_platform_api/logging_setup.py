from __future__ import annotations

import logging

APP_LOGGER = "edd_platform_api"
APP_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_app_logging() -> None:
    # uvicorn's LOGGING_CONFIG only gives handlers to the uvicorn.* loggers, so
    # without this, app warnings reach stderr through logging.lastResort with no
    # time or logger name, and vanish if the root logger is set above WARNING.
    logger = logging.getLogger(APP_LOGGER)
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(APP_LOG_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
