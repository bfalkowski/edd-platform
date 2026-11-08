from __future__ import annotations

from datetime import datetime
from typing import List

from edd_platform_api.schemas import ToolDefinition

WEATHER_TOOL_ID = "tool_get_weather"

APARTMENT_SEARCH_AGENT_INTENT = (
    "Find rental listings for a requested location and return a concrete list of homes or apartments. "
    "Use call_http_api first for simple pages. If the fetched page looks like a JavaScript app shell, "
    "use browse_webpage on the same URL to inspect visible listings. For Zillow-style searches, return "
    "listing name or address, visible rent, bedrooms when shown, and a source link. Do not mark the task "
    "complete with only a limitation explanation unless both static fetch and rendered page inspection fail."
)


def build_default_tool_definitions(project_id: str, now: datetime) -> List[ToolDefinition]:
    """Weather / HTTP fetch / browser render tools seeded for every project."""
    weather_tool = ToolDefinition(
        id=WEATHER_TOOL_ID,
        project_id=project_id,
        name="get_weather",
        description="Get current weather for a US ZIP code.",
        input_schema={
            "type": "object",
            "properties": {
                "zip_code": {"type": "string", "description": "US ZIP code."}
            },
            "required": ["zip_code"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "source": {"type": "string"},
            },
            "required": ["summary"],
        },
        output_description="Current temperature and conditions.",
        implementation_kind="builtin",
        implementation_key="open_meteo_weather",
        config_schema={},
        mock_response="Current weather for 06511 New Haven, CT: 76°F and clear sky.",
        status="approved",
        created_at=now,
        updated_at=now,
    )
    call_http_api_tool = ToolDefinition(
        id="tool_call_http_api",
        project_id=project_id,
        name="call_http_api",
        description="Make a raw HTTP GET request and return the response body. Best for REST/JSON APIs and static pages. Does not execute JavaScript.",
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "format": "uri",
                    "description": "HTTP or HTTPS URL to fetch.",
                }
            },
            "required": ["url"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "status_code": {"type": "integer"},
                "content_type": {"type": "string"},
                "excerpt": {"type": "string"},
            },
            "required": ["summary"],
        },
        output_description="HTTP status, content type, and a short body excerpt.",
        implementation_kind="builtin",
        implementation_key="call_http_api",
        config_schema={},
        mock_response="Fetched https://example.com: HTTP 200; content-type text/html; excerpt: Example Domain.",
        status="approved",
        created_at=now,
        updated_at=now,
    )
    browse_webpage_tool = ToolDefinition(
        id="tool_browse_webpage",
        project_id=project_id,
        name="browse_webpage",
        description="Open a URL in a real browser, execute JavaScript, and return the visible text. Use this for JavaScript-heavy sites (SPAs, job boards, listings) where call_http_api returns an empty shell.",
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "format": "uri",
                    "description": "HTTP or HTTPS URL to render.",
                },
                "query": {
                    "type": "string",
                    "description": "Optional extraction goal for the rendered page.",
                },
                "max_chars": {
                    "type": "integer",
                    "minimum": 500,
                    "maximum": 8000,
                    "description": "Maximum visible text characters to return.",
                },
            },
            "required": ["url"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "visible_text": {"type": "string"},
                "links": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["visible_text"],
        },
        output_description="Rendered page title, visible text excerpt, and useful links.",
        implementation_kind="builtin",
        implementation_key="browse_webpage",
        config_schema={},
        mock_response=(
            "Rendered https://example.com\nTitle\nExample Domain\n\n"
            "Visible text excerpt\nExample Domain\n\nLinks\nNo links captured."
        ),
        status="approved",
        created_at=now,
        updated_at=now,
    )
    return [weather_tool, call_http_api_tool, browse_webpage_tool]


