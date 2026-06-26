from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List, Literal, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel


class ServiceStatus(BaseModel):
    id: str
    name: str
    status: Literal["online", "offline", "configured", "not_configured"]
    configured: bool
    url: Optional[str] = None
    description: str


class ServiceStatusResponse(BaseModel):
    services: List[ServiceStatus]
    updated_at: datetime


def service_url_reachable(url: str) -> bool:
    try:
        request = Request(url.rstrip("/"), method="GET")
        with urlopen(request, timeout=1.0) as response:
            return 200 <= response.status < 500
    except (HTTPError, URLError, TimeoutError, OSError):
        return False


def dependency_statuses() -> List[ServiceStatus]:
    storage_backend = os.environ.get("EDD_PLATFORM_STORAGE_BACKEND", "postgres").strip() or "postgres"
    anthropic_configured = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    langfuse_url = (
        os.environ.get("LANGFUSE_HOST", "").strip()
        or os.environ.get("LANGFUSE_BASE_URL", "").strip()
        or "http://localhost:3001"
    )
    langfuse_configured = bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
        and os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    )
    langfuse_online = langfuse_configured and service_url_reachable(langfuse_url)

    return [
        ServiceStatus(
            id="storage",
            name="Storage",
            status="online",
            configured=True,
            description=f"API persistence backend: {storage_backend}.",
        ),
        ServiceStatus(
            id="anthropic",
            name="Anthropic",
            status="configured" if anthropic_configured else "not_configured",
            configured=anthropic_configured,
            url="https://console.anthropic.com/settings/keys",
            description=(
                "Live agent runs are enabled."
                if anthropic_configured
                else "Set ANTHROPIC_API_KEY before starting the API to enable live runs."
            ),
        ),
        ServiceStatus(
            id="langfuse",
            name="Langfuse",
            status="online" if langfuse_online else ("offline" if langfuse_configured else "not_configured"),
            configured=langfuse_configured,
            url=langfuse_url,
            description=(
                "Trace links are available for live runs."
                if langfuse_online
                else (
                    "Tracing is configured, but the Langfuse UI is not reachable."
                    if langfuse_configured
                    else "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to link live traces."
                )
            ),
        ),
    ]


def service_status_response() -> ServiceStatusResponse:
    return ServiceStatusResponse(
        services=dependency_statuses(),
        updated_at=datetime.now(timezone.utc),
    )
