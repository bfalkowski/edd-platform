from __future__ import annotations

from datetime import datetime
from typing import List

from edd_platform_api.schemas import ToolDefinition

WEATHER_TOOL_ID = "tool_get_weather"

PREVIOUS_SENTIMENT_OBSERVER_INTENT = (
    "Monitor conversations, score sentiment, identify escalation risk, "
    "summarize emotional trajectory, and produce concise observer notes "
    "without taking over the conversation."
)
SENTIMENT_OBSERVER_INTENT = (
    "Run as a long-running observer for conversations. Maintain a running "
    "model of the emotional arc, score sentiment and escalation movement, "
    "summarize trajectory changes, and produce concise observer notes "
    "that downstream APIs can use without taking over the conversation."
)

APARTMENT_SEARCH_AGENT_INTENT = (
    "Find rental listings for a requested location and return a concrete list of homes or apartments. "
    "Use call_http_api first for simple pages. If the fetched page looks like a JavaScript app shell, "
    "use browse_webpage on the same URL to inspect visible listings. For Zillow-style searches, return "
    "listing name or address, visible rent, bedrooms when shown, and a source link. Do not mark the task "
    "complete with only a limitation explanation unless both static fetch and rendered page inspection fail."
)

SCHEDULE_TOOL_MOCK_RESPONSE = (
    "Race: Austrian Grand Prix. Date: 2026-06-28. Venue: Red Bull Ring, "
    "Spielberg, Austria. Source: Formula 1 calendar."
)
RESULT_TOOL_MOCK_RESPONSE = (
    "Race: Barcelona-Catalunya Grand Prix. Date: 2026-06-14. "
    "Winner: Lewis Hamilton. Source: Formula 1 race results."
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


def build_sentiment_observer_tools(project_id: str, now: datetime) -> List[ToolDefinition]:
    """Mock tools backing the seeded Sentiment Observer demo agent."""
    score_sentiment_tool = ToolDefinition(
        id="tool_score_conversation_sentiment",
        project_id=project_id,
        name="score_conversation_sentiment",
        description="Score sentiment for the latest conversation window and report movement from prior state.",
        input_schema={
            "type": "object",
            "properties": {
                "conversation_id": {
                    "type": "string",
                    "description": "Stable id for the conversation being monitored.",
                },
                "conversation_text": {
                    "type": "string",
                    "description": "Conversation transcript or message text to score.",
                },
                "speaker": {
                    "type": "string",
                    "description": "Optional speaker or participant to focus on.",
                },
                "previous_sentiment_score": {
                    "type": "number",
                    "minimum": -1,
                    "maximum": 1,
                    "description": "Prior normalized score for this conversation, if known.",
                },
            },
            "required": ["conversation_text"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "label": {"type": "string", "enum": ["positive", "neutral", "negative", "mixed"]},
                "score": {"type": "number", "minimum": -1, "maximum": 1},
                "delta": {"type": "number", "description": "Score movement from prior state."},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "rationale": {"type": "string"},
            },
            "required": ["label", "score", "confidence", "rationale"],
        },
        output_description="Sentiment label, normalized score, delta, confidence, and rationale.",
        implementation_kind="mock",
        implementation_key="mock.score_conversation_sentiment",
        config_schema={},
        mock_response=(
            "Sentiment: mixed. Score: -0.25. Delta: -0.18. Confidence: 0.82. "
            "Rationale: the customer is frustrated but still cooperative."
        ),
        status="approved",
        created_at=now,
        updated_at=now,
    )
    detect_escalation_tool = ToolDefinition(
        id="tool_detect_escalation_risk",
        project_id=project_id,
        name="detect_escalation_risk",
        description="Detect escalation risk and risk movement from language, urgency, and unresolved blockers.",
        input_schema={
            "type": "object",
            "properties": {
                "conversation_text": {
                    "type": "string",
                    "description": "Conversation transcript or message text to assess.",
                },
                "known_issue_age_hours": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Optional age of the issue in hours.",
                },
                "previous_risk_score": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Prior escalation risk score for this conversation, if known.",
                },
            },
            "required": ["conversation_text"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                "risk_score": {"type": "number", "minimum": 0, "maximum": 1},
                "risk_delta": {"type": "number", "description": "Risk movement from prior state."},
                "triggers": {"type": "array", "items": {"type": "string"}},
                "recommended_observer_note": {"type": "string"},
            },
            "required": ["risk_level", "risk_score", "triggers"],
        },
        output_description="Escalation risk level, score, triggers, and observer note.",
        implementation_kind="mock",
        implementation_key="mock.detect_escalation_risk",
        config_schema={},
        mock_response=(
            "Escalation risk: high. Score: 0.78. Delta: +0.21. Triggers: repeated blocker, "
            "urgent language, unresolved ownership."
        ),
        status="approved",
        created_at=now,
        updated_at=now,
    )
    summarize_signals_tool = ToolDefinition(
        id="tool_summarize_conversation_signals",
        project_id=project_id,
        name="summarize_conversation_signals",
        description="Summarize sentiment drivers, emotional trajectory, and the updated running arc state.",
        input_schema={
            "type": "object",
            "properties": {
                "conversation_text": {
                    "type": "string",
                    "description": "Conversation transcript or message text to summarize.",
                },
                "include_recommendations": {
                    "type": "boolean",
                    "description": "Whether to include recommended monitoring actions.",
                },
                "previous_arc_state": {
                    "type": "object",
                    "description": "Prior conversation emotional-arc state maintained by the consumer.",
                    "additionalProperties": True,
                },
            },
            "required": ["conversation_text"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "sentiment_drivers": {"type": "array", "items": {"type": "string"}},
                "trajectory": {
                    "type": "string",
                    "enum": ["improving", "stable", "worsening", "unclear"],
                },
                "trend_score": {"type": "number", "minimum": -1, "maximum": 1},
                "arc_state": {
                    "type": "object",
                    "description": "Updated running emotional-arc state for downstream consumers.",
                    "additionalProperties": True,
                },
                "recommended_actions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary", "sentiment_drivers", "trajectory", "trend_score", "arc_state"],
        },
        output_description="Concise monitoring summary with drivers, trajectory, trend score, and updated arc state.",
        implementation_kind="mock",
        implementation_key="mock.summarize_conversation_signals",
        config_schema={},
        mock_response=(
            "Summary: customer sentiment is worsening around unresolved deployment impact. "
            "Trajectory: worsening. Trend score: -0.34. Drivers: uncertainty, repeated failure, "
            "lack of timeline. Arc state updated for downstream monitoring."
        ),
        status="approved",
        created_at=now,
        updated_at=now,
    )
    return [score_sentiment_tool, detect_escalation_tool, summarize_signals_tool]
