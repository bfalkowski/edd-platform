from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from edd_platform_api.schemas import (
    AgentDesign,
    AgentSuggestion,
    AgentVersion,
    ArtifactLink,
    ArtifactRecord,
    Comparison,
    EvalContract,
    EvalResult,
    EvidenceSummary,
    FailureMode,
    FailurePacket,
    FixProposal,
    GateDecision,
    GateDefinition,
    JudgeOutput,
    JudgePromptTemplate,
    Project,
    ReviewAnnotation,
    ReviewCorpus,
    ReviewItem,
    ReviewNote,
    RunRecord,
    Scenario,
    ToolDefinition,
    TraceRef,
)
from edd_platform_api.storage import create_store_from_env

store = create_store_from_env()
seeded_at = datetime.now(timezone.utc)
default_project = Project(
    id="project_default",
    name="EDD Platform",
    description="Local EDD product workspace.",
    created_at=seeded_at,
    updated_at=seeded_at,
)
_projects: Dict[str, Project] = store.load_collection("projects", Project)
_agent_designs: Dict[str, AgentDesign] = store.load_collection("agent_designs", AgentDesign)
_scenarios: Dict[str, Scenario] = store.load_collection("scenarios", Scenario)
_eval_contracts: Dict[str, EvalContract] = store.load_collection("eval_contracts", EvalContract)
_judge_prompt_templates: Dict[str, JudgePromptTemplate] = store.load_collection(
    "judge_prompt_templates",
    JudgePromptTemplate,
)
_gate_definitions: Dict[str, GateDefinition] = store.load_collection(
    "gate_definitions",
    GateDefinition,
)
_gate_decisions: Dict[str, GateDecision] = store.load_collection(
    "gate_decisions",
    GateDecision,
)
_agent_versions: Dict[str, AgentVersion] = store.load_collection("agent_versions", AgentVersion)
_runs: Dict[str, RunRecord] = store.load_collection("runs", RunRecord)
_trace_refs: Dict[str, TraceRef] = store.load_collection("trace_refs", TraceRef)
_review_notes: Dict[str, ReviewNote] = store.load_collection("review_notes", ReviewNote)
_review_corpora: Dict[str, ReviewCorpus] = store.load_collection("review_corpora", ReviewCorpus)
_review_items: Dict[str, ReviewItem] = store.load_collection("review_items", ReviewItem)
_review_annotations: Dict[str, ReviewAnnotation] = store.load_collection(
    "review_annotations",
    ReviewAnnotation,
)
_failure_modes: Dict[str, FailureMode] = store.load_collection("failure_modes", FailureMode)
_agent_suggestions: Dict[str, AgentSuggestion] = store.load_collection(
    "agent_suggestions",
    AgentSuggestion,
)
_eval_results: Dict[str, EvalResult] = store.load_collection("eval_results", EvalResult)
_judge_outputs: Dict[str, JudgeOutput] = store.load_collection("judge_outputs", JudgeOutput)
_failure_packets: Dict[str, FailurePacket] = store.load_collection("failure_packets", FailurePacket)
_fix_proposals: Dict[str, FixProposal] = store.load_collection("fix_proposals", FixProposal)
_comparisons: Dict[str, Comparison] = store.load_collection("comparisons", Comparison)
_artifacts: Dict[str, ArtifactRecord] = store.load_collection("artifacts", ArtifactRecord)
_artifact_links: Dict[str, ArtifactLink] = store.load_collection("artifact_links", ArtifactLink)
_tool_definitions: Dict[str, ToolDefinition] = store.load_collection("tool_definitions", ToolDefinition)
_evidence_summaries: Dict[str, EvidenceSummary] = store.load_collection(
    "evidence_summaries",
    EvidenceSummary,
)

if default_project.id not in _projects:
    _projects[default_project.id] = default_project
    store.save_record("projects", default_project.id, default_project)

default_tool = ToolDefinition(
    id="tool_get_weather",
    project_id=default_project.id,
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
    created_at=seeded_at,
    updated_at=seeded_at,
)
web_page_tool = ToolDefinition(
    id="tool_call_http_api",
    project_id=default_project.id,
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
    created_at=seeded_at,
    updated_at=seeded_at,
)
rendered_page_tool = ToolDefinition(
    id="tool_browse_webpage",
    project_id=default_project.id,
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
    created_at=seeded_at,
    updated_at=seeded_at,
)
for seeded_tool_definition in [default_tool, web_page_tool, rendered_page_tool]:
    existing_tool_definition = _tool_definitions.get(seeded_tool_definition.id)
    if existing_tool_definition is None or (
        seeded_tool_definition.id == default_tool.id
        and existing_tool_definition.implementation_key == "local_weather_fixture"
    ):
        _tool_definitions[seeded_tool_definition.id] = seeded_tool_definition
        store.save_record(
            "tool_definitions",
            seeded_tool_definition.id,
            seeded_tool_definition,
        )
