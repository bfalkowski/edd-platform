"""Runner package for EDD Platform."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from pydantic import BaseModel, Field


class RunnerAgentDesign(BaseModel):
    id: str
    name: str
    intent: str
    allowed_tool_names: List[str] = []


class RunnerScenario(BaseModel):
    input: str


class RunnerToolCall(BaseModel):
    name: str
    input: Optional[str] = None
    output: str


class RunnerToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: Optional[dict[str, Any]] = None
    output_description: str
    implementation_kind: str = "builtin"
    implementation_key: str
    config_schema: dict[str, Any] = Field(default_factory=dict)
    mock_response: Optional[str] = None
    status: str


class RunnerResult(BaseModel):
    id: str
    agent_design_id: str
    mode: str
    scenario_input: str
    response: str
    tool_calls: List[RunnerToolCall]
    evidence: List[str]
    trace_id: Optional[str] = None
    trace_url: Optional[str] = None
    created_at: datetime


@dataclass(frozen=True)
class AnthropicRunnerConfig:
    api_key: str
    model: str = "claude-sonnet-4-6"


def run_mock_agent(agent: RunnerAgentDesign, scenario: RunnerScenario) -> RunnerResult:
    """Run a deterministic agent-shaped scenario without provider credentials."""
    tool_calls = [
        RunnerToolCall(
            name="collect_design_intent",
            input="agent.intent",
            output=agent.intent,
        ),
        RunnerToolCall(
            name="classify_request",
            input=scenario.input,
            output="scenario_requires_grounded_next_action",
        ),
    ]
    response = (
        f"{agent.name} reviewed the scenario and stayed within its design intent. "
        f"Design intent: {agent.intent}. "
        f"It should gather relevant evidence, state assumptions, and recommend a safe next action. "
        f"Scenario: {scenario.input}"
    )
    return RunnerResult(
        id=f"run_{uuid4().hex[:12]}",
        agent_design_id=agent.id,
        mode="mock",
        scenario_input=scenario.input,
        response=response,
        tool_calls=tool_calls,
        evidence=[
            "Used agent design intent as the target behavior.",
            "Used deterministic mock classification instead of a model provider.",
        ],
        created_at=datetime.now(timezone.utc),
    )


def weather_code_label(code: int | None) -> str:
    labels = {
        0: "clear sky",
        1: "mainly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "fog",
        48: "depositing rime fog",
        51: "light drizzle",
        53: "moderate drizzle",
        55: "dense drizzle",
        61: "slight rain",
        63: "moderate rain",
        65: "heavy rain",
        71: "slight snow",
        73: "moderate snow",
        75: "heavy snow",
        80: "slight rain showers",
        81: "moderate rain showers",
        82: "violent rain showers",
        95: "thunderstorm",
    }
    return labels.get(code, "unknown conditions")


def get_zip_location(zip_code: str) -> tuple[str, str, str, str]:
    normalized = zip_code.strip()
    if not normalized:
        raise RuntimeError("ZIP code is required.")
    request = Request(f"https://api.zippopotam.us/us/{quote(normalized)}")
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    places = payload.get("places") if isinstance(payload, dict) else None
    if not isinstance(places, list) or not places:
        raise RuntimeError(f"No location found for ZIP {normalized}.")
    place = places[0]
    return (
        str(place["latitude"]),
        str(place["longitude"]),
        str(place.get("place name", normalized)),
        str(place.get("state abbreviation", "")),
    )


def get_weather(zip_code: str) -> str:
    """Return current weather for a US ZIP code using public weather APIs."""
    normalized = zip_code.strip()
    try:
        latitude, longitude, place_name, state = get_zip_location(normalized)
        query = urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,weather_code",
                "temperature_unit": "fahrenheit",
                "timezone": "auto",
            }
        )
        request = Request(f"https://api.open-meteo.com/v1/forecast?{query}")
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        current = payload.get("current") if isinstance(payload, dict) else None
        if not isinstance(current, dict):
            raise RuntimeError("Open-Meteo response did not include current conditions.")
        temperature = current.get("temperature_2m")
        weather_code = current.get("weather_code")
        location = f"{place_name}, {state}".strip().rstrip(",")
        return (
            f"Current weather for {normalized} {location}: "
            f"{round(float(temperature))}°F and {weather_code_label(weather_code)}. "
            "Source: Open-Meteo current forecast."
        )
    except (HTTPError, URLError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        return f"Weather lookup unavailable for ZIP {normalized}: {exc}"


def call_http_api(url: str) -> str:
    """Fetch a public web page and return a compact response summary."""
    target_url = url.strip()
    parsed = urlparse(target_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "Web page fetch unavailable: URL must use http or https."
    request = Request(target_url, headers={"User-Agent": "edd-platform-agent-tool/1.0"})
    try:
        with urlopen(request, timeout=15) as response:
            status_code = response.getcode()
            content_type = response.headers.get("Content-Type", "unknown")
            body = response.read(65536).decode("utf-8", errors="replace")
    except HTTPError as exc:
        status_code = exc.code
        content_type = exc.headers.get("Content-Type", "unknown") if exc.headers else "unknown"
        body = exc.read(4096).decode("utf-8", errors="replace")
    except URLError as exc:
        return f"Web page fetch unavailable for {target_url}: {exc.reason}"

    is_json = "json" in content_type.lower()
    if is_json:
        # Compact whitespace and cap at 4K — enough to extract structured fields in one pass.
        # Large JSON APIs (e.g. Greenhouse jobs) return many KB; cap prevents context blowout
        # across multi-turn tool loops where each response re-enters the message history.
        content = re.sub(r"\s+", " ", body).strip()[:4000]
    else:
        # Strip HTML tags, collapse whitespace, cap at 4K of readable text.
        content = re.sub(r"<[^>]+>", " ", body)
        content = re.sub(r"\s+", " ", content).strip()[:4000]

    truncated = len(body) > 4000
    suffix = f" [truncated — {len(body)} bytes total]" if truncated else ""
    return (
        f"Fetched {target_url}: HTTP {status_code}; content-type {content_type}; "
        f"{'json' if is_json else 'text'}: {content or 'empty response'}{suffix}"
    )


def get_sync_playwright():
    from playwright.sync_api import sync_playwright

    return sync_playwright()


def browse_webpage(url: str, query: str = "", max_chars: int = 4000) -> str:
    """Render a public web page and return visible text plus useful links."""
    target_url = url.strip()
    parsed = urlparse(target_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "Rendered page unavailable: URL must use http or https."
    try:
        char_limit = max(500, min(int(max_chars), 8000))
    except (TypeError, ValueError):
        char_limit = 4000
    try:
        playwright_context = get_sync_playwright()
    except ImportError:
        return "Rendered page unavailable: Playwright is not installed in the runner environment."

    try:
        with playwright_context as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent="edd-platform-render-tool/1.0")
                page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000)
                payload = page.evaluate(
                    """() => {
                        const text = document.body
                          ? document.body.innerText.replace(/\\s+/g, " ").trim()
                          : "";
                        const links = Array.from(document.querySelectorAll("a[href]"))
                          .map((link) => ({
                            text: (link.innerText || "").replace(/\\s+/g, " ").trim(),
                            href: link.href
                          }))
                          .filter((link) => link.text && link.href)
                          .slice(0, 40);
                        return { title: document.title, url: location.href, text, links };
                    }"""
                )
            finally:
                browser.close()
    except Exception as exc:
        return f"Rendered page unavailable for {target_url}: {exc}"

    title = str(payload.get("title") or "")
    resolved_url = str(payload.get("url") or target_url)
    text = str(payload.get("text") or "")[:char_limit]
    links = payload.get("links") if isinstance(payload.get("links"), list) else []
    query_note = f"\nQuery\n{query.strip()}\n" if query.strip() else ""
    link_lines = "\n".join(
        f"- {str(link.get('text', ''))[:120]}: {link.get('href')}"
        for link in links[:20]
        if isinstance(link, dict)
    )
    return (
        f"Rendered {resolved_url}\n"
        f"Title\n{title}\n"
        f"{query_note}\n"
        f"Visible text excerpt\n{text or 'No visible text captured.'}\n\n"
        f"Links\n{link_lines or 'No links captured.'}"
    )


def build_langchain_tools(tool_definitions: List[RunnerToolDefinition]):
    try:
        from langchain_core.tools import StructuredTool
        from langchain_core.tools import tool
    except ImportError as exc:
        raise RuntimeError("LangChain tools require langchain-core to be installed.") from exc

    tools = []
    for definition in tool_definitions:
        if definition.status != "approved":
            continue
        if definition.implementation_key in {"open_meteo_weather", "local_weather_fixture"}:

            @tool("get_weather")
            def weather_tool(zip_code: str) -> str:
                """Get current weather for a US ZIP code."""
                return get_weather(zip_code)

            tools.append(weather_tool)
        elif definition.implementation_key == "call_http_api":

            @tool("call_http_api")
            def web_page_tool(url: str) -> str:
                """Fetch a public web page by URL and return a compact response summary."""
                return call_http_api(url)

            tools.append(web_page_tool)
        elif definition.implementation_key == "browse_webpage":

            @tool("browse_webpage")
            def rendered_web_page_tool(url: str, query: str = "", max_chars: int = 4000) -> str:
                """Render a public web page and return visible text and links."""
                return browse_webpage(url, query=query, max_chars=max_chars)

            tools.append(rendered_web_page_tool)
        elif definition.implementation_kind == "mock" or definition.implementation_key.startswith("mock."):
            def make_mock_tool(response: str):
                def mock_tool(**_kwargs: Any) -> str:
                    return response

                return mock_tool

            tools.append(
                StructuredTool.from_function(
                    func=make_mock_tool(definition.mock_response or definition.output_description),
                    name=definition.name,
                    description=definition.description,
                )
            )
    return tools


def build_langfuse_langchain_callbacks():
    if not langfuse_tracing_enabled():
        return []
    try:
        from langfuse import get_client
        from langfuse.langchain import CallbackHandler
    except ImportError:
        return []

    langfuse = get_client()
    trace_id = langfuse.get_current_trace_id()
    if not trace_id:
        return [CallbackHandler()]
    observation_id = langfuse.get_current_observation_id()
    trace_context = {"trace_id": trace_id}
    if observation_id:
        trace_context["parent_span_id"] = observation_id
    return [CallbackHandler(trace_context=trace_context)]


def anthropic_config_from_env() -> AnthropicRunnerConfig:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required for live Anthropic runs.")
    return AnthropicRunnerConfig(
        api_key=api_key,
        model=os.environ.get("EDD_ANTHROPIC_MODEL", "claude-haiku-4-5-20251001").strip() or "claude-haiku-4-5-20251001",
    )


def collect_text_values(value) -> List[str]:
    if isinstance(value, dict):
        values: List[str] = []
        for key, child in value.items():
            if key in {"text", "output_text"} and isinstance(child, str):
                values.append(child)
            else:
                values.extend(collect_text_values(child))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(collect_text_values(item))
        return values
    return []


def extract_response_text(payload: dict) -> str:
    for block in payload.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return ""


def describe_empty_response(payload: dict) -> str:
    stop_reason = payload.get("stop_reason")
    if stop_reason and stop_reason != "end_turn":
        return f"Anthropic response stopped early: {stop_reason}."
    return "Anthropic response did not include output text."


def usage_details_from_anthropic_payload(payload: dict) -> dict[str, Any]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return {}
    details: dict[str, Any] = {}
    for key in ("input_tokens", "output_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            details[key] = value
    return details


def anthropic_generation_context(config: AnthropicRunnerConfig, messages: list):
    if not langfuse_tracing_enabled():
        return None
    try:
        from langfuse import get_client
    except ImportError:
        return None

    try:
        langfuse = get_client()
        return langfuse.start_as_current_observation(
            as_type="generation",
            name="anthropic.messages",
            model=config.model,
            input=messages,
            metadata={
                "provider": "anthropic",
                "endpoint": "/v1/messages",
            },
        )
    except Exception:
        return None


def send_anthropic_messages_request(config: AnthropicRunnerConfig, body: dict) -> dict:
    try:
        import anthropic as anthropic_sdk
    except ImportError as exc:
        raise RuntimeError("anthropic package is required for live runs: pip install anthropic") from exc
    client = anthropic_sdk.Anthropic(api_key=config.api_key)
    try:
        response = client.messages.create(
            model=body["model"],
            max_tokens=body.get("max_tokens", 2000),
            system=body.get("system", ""),
            messages=body["messages"],
        )
        return response.model_dump()
    except anthropic_sdk.APIStatusError as exc:
        raise RuntimeError(f"Anthropic request failed with status {exc.status_code}: {exc.message}") from exc
    except anthropic_sdk.APIConnectionError as exc:
        raise RuntimeError(f"Anthropic request failed: {exc}") from exc


def run_anthropic_agent(
    agent: RunnerAgentDesign,
    scenario: RunnerScenario,
    config: AnthropicRunnerConfig,
    tool_definitions: List[RunnerToolDefinition] | None = None,
) -> RunnerResult:
    """Run a scenario through a LangGraph-backed LangChain agent."""
    if langfuse_tracing_enabled():
        return run_anthropic_agent_with_langfuse(
            agent=agent,
            scenario=scenario,
            config=config,
            tool_definitions=tool_definitions,
        )
    return run_anthropic_agent_core(
        agent=agent,
        scenario=scenario,
        config=config,
        tool_definitions=tool_definitions,
    )


def langfuse_tracing_enabled() -> bool:
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
        and os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    )


def run_anthropic_agent_with_langfuse(
    *,
    agent: RunnerAgentDesign,
    scenario: RunnerScenario,
    config: AnthropicRunnerConfig,
    tool_definitions: List[RunnerToolDefinition] | None = None,
) -> RunnerResult:
    try:
        from langfuse import get_client
    except ImportError:
        return run_anthropic_agent_core(
            agent=agent,
            scenario=scenario,
            config=config,
            tool_definitions=tool_definitions,
        )

    langfuse = get_client()
    with langfuse.start_as_current_observation(
        as_type="agent",
        name=f"edd-agent-run:{agent.name}",
        input={
            "agent_id": agent.id,
            "agent_name": agent.name,
            "intent": agent.intent,
            "scenario": scenario.input,
        },
        metadata={
            "source": "edd-platform",
            "runner_mode": "live",
            "allowed_tools": agent.allowed_tool_names,
        },
    ) as observation:
        result = run_anthropic_agent_core(
            agent=agent,
            scenario=scenario,
            config=config,
            tool_definitions=tool_definitions,
        )
        observation.update(
            output={
                "response": result.response,
                "tool_calls": [tool.model_dump() for tool in result.tool_calls],
            }
        )
        trace_id = langfuse.get_current_trace_id() or observation.trace_id
        trace_url = None
        if trace_id:
            try:
                trace_url = langfuse.get_trace_url(trace_id=trace_id)
            except Exception:
                trace_url = None
    try:
        langfuse.flush()
    except Exception:
        pass
    return result.model_copy(
        update={
            "trace_id": trace_id,
            "trace_url": trace_url,
            "evidence": result.evidence
            + [f"Linked Langfuse trace {trace_id}." if trace_id else "Langfuse trace unavailable."],
        }
    )


def run_anthropic_agent_core(
    *,
    agent: RunnerAgentDesign,
    scenario: RunnerScenario,
    config: AnthropicRunnerConfig,
    tool_definitions: List[RunnerToolDefinition] | None = None,
) -> RunnerResult:
    instructions = (
        "You are the candidate agent being designed in an eval-driven workflow. "
        "Stay inside the design intent, gather or cite relevant evidence from the scenario, "
        "state assumptions clearly, and recommend a safe next action."
    )
    active_tools = build_langchain_tools(tool_definitions or [])
    if active_tools:
        return run_langchain_agent(agent, scenario, config, instructions, active_tools)

    system_prompt = f"{instructions}\n\nAgent name: {agent.name}\nDesign intent: {agent.intent}"
    messages = [{"role": "user", "content": scenario.input}]
    body = {
        "model": config.model,
        "max_tokens": 2000,
        "system": system_prompt,
        "messages": messages,
    }
    generation_context = anthropic_generation_context(config, messages)
    if generation_context is None:
        payload = send_anthropic_messages_request(config, body)
        response_text = extract_response_text(payload)
        if not response_text:
            raise RuntimeError(describe_empty_response(payload))
    else:
        with generation_context as generation:
            payload = send_anthropic_messages_request(config, body)
            response_text = extract_response_text(payload)
            if not response_text:
                raise RuntimeError(describe_empty_response(payload))
            generation.update(
                output=response_text,
                usage_details=usage_details_from_anthropic_payload(payload),
                metadata={
                    "anthropic_message_id": payload.get("id"),
                    "stop_reason": payload.get("stop_reason"),
                },
            )

    return RunnerResult(
        id=f"run_{uuid4().hex[:12]}",
        agent_design_id=agent.id,
        mode="live",
        scenario_input=scenario.input,
        response=response_text,
        tool_calls=[
            RunnerToolCall(
                name="anthropic.messages",
                input=scenario.input,
                output=config.model,
            )
        ],
        evidence=[
            f"Used Anthropic Messages API model {config.model}.",
            "Live provider run; output should be evaluated before promotion.",
        ],
        created_at=datetime.now(timezone.utc),
    )


def message_text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(collect_text_values(content))
    return str(content)


def run_langchain_agent(
    agent: RunnerAgentDesign,
    scenario: RunnerScenario,
    config: AnthropicRunnerConfig,
    instructions: str,
    tools,
) -> RunnerResult:
    try:
        from langchain.agents import create_agent
    except ImportError as exc:
        raise RuntimeError("LangChain agent execution requires langchain to be installed.") from exc

    # Allow up to 5 tool calls per unique tool available — enough for browsing
    # agents that may need to paginate or follow a few links, without unlimited looping.
    # Each call costs 2 graph steps; add 4 for initial + final agent steps.
    max_tool_calls = max(5, len(tools) * 5)
    recursion_limit = 4 + (max_tool_calls * 2)

    graph = create_agent(
        model=f"anthropic:{config.model}",
        tools=tools,
        system_prompt=(
            f"{instructions}\n\n"
            f"Agent name: {agent.name}\n"
            f"Design intent: {agent.intent}\n"
            f"Allowed tools: {', '.join(agent.allowed_tool_names) or 'none'}\n\n"
            f"TOOL CALL BUDGET: You have a budget of up to {max_tool_calls} tool call(s). "
            "Use only as many as needed to answer the user's question. "
            "Once you have enough information, stop calling tools and write your final response. "
            "Do not call a tool again if the result you already have is sufficient."
        ),
    )
    callbacks = build_langfuse_langchain_callbacks()
    invoke_config: dict = {"recursion_limit": recursion_limit}
    if callbacks:
        invoke_config["callbacks"] = callbacks
    result = graph.invoke(
        {"messages": [{"role": "user", "content": scenario.input}]},
        config=invoke_config,
    )
    messages = result.get("messages", [])
    response_text = ""
    tool_calls: List[RunnerToolCall] = []

    for message in messages:
        message_type = getattr(message, "type", "")
        if message_type == "tool":
            tool_calls.append(
                RunnerToolCall(
                    name=getattr(message, "name", None) or "tool",
                    output=message_text(message),
                )
            )
        elif message_type in {"ai", "assistant"}:
            text = message_text(message).strip()
            if text:
                response_text = text

    if not response_text:
        raise RuntimeError("LangGraph agent did not return a final response.")

    return RunnerResult(
        id=f"run_{uuid4().hex[:12]}",
        agent_design_id=agent.id,
        mode="live",
        scenario_input=scenario.input,
        response=response_text,
        tool_calls=tool_calls or [
            RunnerToolCall(
                name="langchain.agent",
                input=scenario.input,
                output=config.model,
            )
        ],
        evidence=[
            f"Used LangChain/LangGraph agent with Anthropic model {config.model}.",
            f"Allowed tools: {', '.join(agent.allowed_tool_names) or 'none'}.",
        ],
        created_at=datetime.now(timezone.utc),
    )


__all__ = [
    "AnthropicRunnerConfig",
    "RunnerAgentDesign",
    "RunnerResult",
    "RunnerScenario",
    "RunnerToolCall",
    "RunnerToolDefinition",
    "anthropic_config_from_env",
    "build_langchain_tools",
    "build_langfuse_langchain_callbacks",
    "langfuse_tracing_enabled",
    "run_anthropic_agent",
    "run_mock_agent",
]
