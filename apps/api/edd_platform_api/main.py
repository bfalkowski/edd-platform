from __future__ import annotations

import json
import os
import sys

from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv(raise_error_if_not_found=False))
load_dotenv(find_dotenv(".env.local", raise_error_if_not_found=False), override=True)
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Response

from edd_platform_api.service_status import ServiceStatusResponse, service_status_response
from edd_platform_api.polars_analysis import (
    materialize_review_corpus_snapshot,
    review_corpus_analysis,
    review_corpus_analysis_from_snapshot,
)
from edd_platform_api.tool_adapters import tool_adapter_contract
from edd_platform_api.seed_data import (
    APARTMENT_SEARCH_AGENT_INTENT,
    PREVIOUS_SENTIMENT_OBSERVER_INTENT,
    SENTIMENT_OBSERVER_INTENT,
    build_sentiment_observer_tools,
)
from edd_platform_api.evidence_context import (
    build_deterministic_evidence_summary,
    build_evidence_summary_prompt,
    context_pack_cache_key,
)
from edd_platform_api.eval_checks import (
    contract_generated_checks,
    evaluate_contract_check,
    evaluate_run_text,
)
from edd_platform_api.lookups import (
    get_agent_design_or_404,
    get_agent_suggestion_or_404,
    get_agent_version_or_404,
    get_artifact_or_404,
    get_comparison_or_404,
    get_eval_contract_or_404,
    get_eval_result_or_404,
    get_failure_mode_or_404,
    get_failure_packet_or_404,
    get_fix_proposal_or_404,
    get_gate_decision_or_404,
    get_gate_definition_or_404,
    get_judge_prompt_template_or_404,
    get_project_or_404,
    get_review_annotation_or_404,
    get_review_corpus_or_404,
    get_review_item_or_404,
    get_review_note_or_404,
    get_run_or_404,
    get_scenario_or_404,
    get_trace_ref_or_404,
)
from edd_platform_api.schemas import (
    AgentDesignCreate,
    AgentDesignUpdate,
    Project,
    AgentDesign,
    ScenarioCreate,
    Scenario,
    EvalContractCreate,
    EvalContract,
    EvalContractChecksUpdate,
    EvalContractRubricUpdate,
    JudgePromptTemplateCreate,
    JudgePromptTemplate,
    GateDefinitionCreate,
    GateDefinition,
    GateDecisionCreate,
    GateDecision,
    AgentVersionCreate,
    AgentVersion,
    ExternalArtifactRef,
    ArtifactRecord,
    ArtifactLinkCreate,
    ArtifactLink,
    ToolDefinition,
    ToolDefinitionCreate,
    ToolDefinitionUpdate,
    ToolAdapterContract,
    AgentRunCreate,
    RunCreate,
    RunRecord,
    TraceRefCreate,
    TraceRef,
    ReviewNoteCreate,
    ReviewNote,
    ReviewCorpusCreate,
    ReviewCorpusUpdate,
    ReviewCorpus,
    ReviewItemCreate,
    ReviewItemUpdate,
    ReviewItem,
    LangfuseReviewItemsImportCreate,
    LangfuseReviewItemsImportResult,
    ReviewAnnotationCreate,
    ReviewAnnotationUpdate,
    ReviewAnnotation,
    LangfuseAnnotationsImportCreate,
    LangfuseAnnotationsImportResult,
    FailureModeCreate,
    FailureModeUpdate,
    FailureMode,
    AgentSuggestionCreate,
    AgentSuggestionUpdate,
    AgentSuggestion,
    AnalysisSnapshotMetadata,
    ReviewCoverageSummary,
    ReviewSamplingCandidate,
    ReviewSamplingPlan,
    ReviewCorpusAnalysis,
    DiscoveryPromotionCreate,
    DiscoveryPromotionResult,
    AgentRunResult,
    EvalCheck,
    EvalCheckResult,
    RunEvaluateCreate,
    EvalResult,
    JudgeOutput,
    FailurePacketCreate,
    FailurePacketUpdate,
    FailurePacket,
    FailureDiagnosisRequest,
    FailureDiagnosis,
    FixProposalCreate,
    FixProposalGenerateRequest,
    FixProposalGenerated,
    FixProposalUpdate,
    FixProposal,
    ComparisonCreate,
    Comparison,
    EvalRunResult,
    AgentDesignCreated,
    OutcomeAgentCreate,
    OutcomeAgentCreated,
    GuidedSetupRequest,
    GuidedSetupPreview,
    ContextPackCreate,
    ContextPack,
    EvidenceSummaryCreate,
    EvidenceSummary,
)
from edd_platform_api.state import (
    _agent_designs,
    _agent_suggestions,
    _agent_versions,
    _artifact_links,
    _artifacts,
    _comparisons,
    _eval_contracts,
    _eval_results,
    _evidence_summaries,
    _failure_modes,
    _failure_packets,
    _fix_proposals,
    _gate_decisions,
    _gate_definitions,
    _judge_outputs,
    _judge_prompt_templates,
    _projects,
    _review_annotations,
    _review_corpora,
    _review_items,
    _review_notes,
    _runs,
    _scenarios,
    _tool_definitions,
    _trace_refs,
    default_project,
    seeded_at,
    store,
)

ROOT = Path(__file__).resolve().parents[3]
RUNNER_ROOT = ROOT / "packages" / "runner"
if str(RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNNER_ROOT))

from edd_runner import (  # noqa: E402
    RunnerAgentDesign,
    RunnerScenario,
    RunnerToolDefinition,
    anthropic_config_from_env,
    describe_empty_response,
    extract_response_text,
    foundry_config_from_env,
    run_anthropic_agent,
    run_foundry_agent,
    run_mock_agent,
)


try:
    from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
    AnthropicInstrumentor().instrument()
except Exception:
    pass

app = FastAPI(title="EDD Platform API")

from edd_platform_api.routers import core as _core_router  # noqa: E402
from edd_platform_api.routers import trace_refs as _trace_refs_router  # noqa: E402
from edd_platform_api.routers import judge_prompt_templates as _judge_prompt_templates_router  # noqa: E402
from edd_platform_api.routers import comparisons as _comparisons_router  # noqa: E402
from edd_platform_api.routers import scenarios as _scenarios_router  # noqa: E402
from edd_platform_api.routers import artifacts as _artifacts_router  # noqa: E402
from edd_platform_api.routers import tools as _tools_router  # noqa: E402
from edd_platform_api.routers import eval_contracts as _eval_contracts_router  # noqa: E402
from edd_platform_api.routers import gates as _gates_router  # noqa: E402
from edd_platform_api.routers import agent_designs as _agent_designs_router  # noqa: E402
from edd_platform_api.routers import runs as _runs_router  # noqa: E402
from edd_platform_api.routers import fix_proposals as _fix_proposals_router  # noqa: E402
from edd_platform_api.routers import error_analysis as _error_analysis_router  # noqa: E402
app.include_router(_core_router.router)
app.include_router(_trace_refs_router.router)
app.include_router(_judge_prompt_templates_router.router)
app.include_router(_comparisons_router.router)
app.include_router(_scenarios_router.router)
app.include_router(_artifacts_router.router)
app.include_router(_tools_router.router)
app.include_router(_eval_contracts_router.router)
app.include_router(_gates_router.router)
app.include_router(_agent_designs_router.router)
app.include_router(_runs_router.router)
app.include_router(_fix_proposals_router.router)
app.include_router(_error_analysis_router.router)




def find_agent_design_artifact(agent_id: str) -> Optional[ArtifactRecord]:
    for artifact in _artifacts.values():
        if artifact.artifact_type == "AGENT_DESIGN" and artifact.artifact_id == agent_id:
            return artifact
    return None


def agent_design_artifact_body(agent: AgentDesign) -> str:
    tools = ", ".join(agent.allowed_tool_names) if agent.allowed_tool_names else "none"
    prompt = langfuse_prompt_display(
        name=agent.langfuse_prompt_name,
        version=agent.langfuse_prompt_version,
        label=agent.langfuse_prompt_label,
    )
    return f"{agent.intent}\n\nAllowed tools: {tools}\n\nLangfuse prompt\n{prompt}"


def langfuse_prompt_display(
    *,
    name: Optional[str],
    version: Optional[str],
    label: Optional[str],
) -> str:
    if not name:
        return "None"
    details = [f"name={name}"]
    if version:
        details.append(f"version={version}")
    if label:
        details.append(f"label={label}")
    return ", ".join(details)


def langfuse_prompt_external_id(
    *,
    name: str,
    version: Optional[str],
    label: Optional[str],
) -> str:
    if version:
        return f"{name}:version:{version}"
    if label:
        return f"{name}:label:{label}"
    return name


def langfuse_prompt_refs(
    *,
    name: Optional[str],
    version: Optional[str],
    label: Optional[str],
    prompt_role: str,
    source_id: str,
) -> List[ExternalArtifactRef]:
    if not name:
        return []
    return [
        ExternalArtifactRef(
            provider="langfuse",
            ref_type="prompt",
            external_id=langfuse_prompt_external_id(
                name=name,
                version=version,
                label=label,
            ),
            label="Langfuse prompt",
            metadata={
                "prompt_name": name,
                "prompt_version": version,
                "prompt_label": label,
                "prompt_role": prompt_role,
                "source_id": source_id,
            },
        )
    ]


def prompt_refs_from_metadata(metadata: Dict[str, object]) -> List[ExternalArtifactRef]:
    prompt_refs = metadata.get("prompt_refs", [])
    if not isinstance(prompt_refs, list):
        return []
    refs: List[ExternalArtifactRef] = []
    for prompt_ref in prompt_refs:
        if isinstance(prompt_ref, dict):
            refs.append(ExternalArtifactRef.model_validate(prompt_ref))
    return refs


def sync_agent_design_artifact(agent: AgentDesign, now: datetime) -> ArtifactRecord:
    artifact = find_agent_design_artifact(agent.id)
    if artifact is None:
        artifact = ArtifactRecord(
            id=f"artifact_{uuid4().hex[:12]}",
            project_id=agent.project_id,
            artifact_type="AGENT_DESIGN",
            artifact_id=agent.id,
            title=agent.name,
            body=agent_design_artifact_body(agent),
            source="intent",
            agent_design_id=agent.id,
            external_refs=langfuse_prompt_refs(
                name=agent.langfuse_prompt_name,
                version=agent.langfuse_prompt_version,
                label=agent.langfuse_prompt_label,
                prompt_role="agent",
                source_id=agent.id,
            ),
            created_at=now,
            updated_at=now,
        )
    else:
        artifact = artifact.model_copy(
            update={
                "title": agent.name,
                "body": agent_design_artifact_body(agent),
                "external_refs": langfuse_prompt_refs(
                    name=agent.langfuse_prompt_name,
                    version=agent.langfuse_prompt_version,
                    label=agent.langfuse_prompt_label,
                    prompt_role="agent",
                    source_id=agent.id,
                ),
                "updated_at": now,
            }
        )
    _artifacts[artifact.id] = artifact
    store.save_record("artifacts", artifact.id, artifact)
    return artifact


def find_artifact_by_type_and_artifact_id(
    artifact_type: str,
    artifact_id: str,
) -> Optional[ArtifactRecord]:
    for artifact in _artifacts.values():
        if artifact.artifact_type == artifact_type and artifact.artifact_id == artifact_id:
            return artifact
    return None


def create_artifact(
    *,
    project_id: str,
    artifact_type: str,
    artifact_id: str,
    title: str,
    body: str,
    source: str,
    agent_design_id: Optional[str],
    now: datetime,
    external_refs: Optional[List[ExternalArtifactRef]] = None,
) -> ArtifactRecord:
    artifact = ArtifactRecord(
        id=f"artifact_{uuid4().hex[:12]}",
        project_id=project_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        title=title,
        body=body,
        source=source,
        agent_design_id=agent_design_id,
        external_refs=external_refs or [],
        created_at=now,
        updated_at=now,
    )
    _artifacts[artifact.id] = artifact
    store.save_record("artifacts", artifact.id, artifact)
    return artifact


def get_langfuse_client() -> object:
    from langfuse import get_client

    return get_client()


def langfuse_credentials_configured() -> bool:
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
        and os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    )


def tool_definition_artifact_body(tool: ToolDefinition) -> str:
    return (
        f"Description\n{tool.description}\n\n"
        f"Status\n{tool.status}\n\n"
        f"Implementation kind\n{tool.implementation_kind}\n\n"
        f"Implementation key\n{tool.implementation_key}\n\n"
        f"Input schema\n{json.dumps(tool.input_schema, indent=2, sort_keys=True)}\n\n"
        f"Output schema\n{json.dumps(tool.output_schema or {}, indent=2, sort_keys=True)}\n\n"
        f"Output description\n{tool.output_description}\n\n"
        f"Config schema\n{json.dumps(tool.config_schema, indent=2, sort_keys=True)}\n\n"
        f"Mock response\n{tool.mock_response or ''}"
    )


def upsert_tool_definition_artifact(tool: ToolDefinition, now: datetime) -> ArtifactRecord:
    existing = find_artifact_by_type_and_artifact_id("TOOL_DEFINITION", tool.id)
    if existing is not None:
        updated = existing.model_copy(
            update={
                "title": tool.name,
                "body": tool_definition_artifact_body(tool),
                "updated_at": now,
            }
        )
        _artifacts[updated.id] = updated
        store.save_record("artifacts", updated.id, updated)
        return updated
    return create_artifact(
        project_id=tool.project_id,
        artifact_type="TOOL_DEFINITION",
        artifact_id=tool.id,
        title=tool.name,
        body=tool_definition_artifact_body(tool),
        source="tool-registry",
        agent_design_id=None,
        now=now,
    )


def seed_sentiment_observer_defaults() -> None:
    now = seeded_at
    tools = build_sentiment_observer_tools(default_project.id, now)
    for tool in tools:
        existing = _tool_definitions.get(tool.id)
        seeded_tool = tool if existing is None else tool.model_copy(
            update={
                "created_at": existing.created_at,
                "updated_at": now,
            }
        )
        _tool_definitions[seeded_tool.id] = seeded_tool
        store.save_record("tool_definitions", seeded_tool.id, seeded_tool)
        upsert_tool_definition_artifact(seeded_tool, now)

    tool_names = [tool.name for tool in tools]
    existing_agent = _agent_designs.get("agent_sentiment_observer")
    if existing_agent is None:
        agent = AgentDesign(
            id="agent_sentiment_observer",
            project_id=default_project.id,
            name="Sentiment Observer",
            intent=SENTIMENT_OBSERVER_INTENT,
            status="designing",
            allowed_tool_names=tool_names,
            created_at=now,
            updated_at=now,
        )
    else:
        allowed_tool_names = list(dict.fromkeys(existing_agent.allowed_tool_names + tool_names))
        intent = (
            SENTIMENT_OBSERVER_INTENT
            if existing_agent.intent == PREVIOUS_SENTIMENT_OBSERVER_INTENT
            else existing_agent.intent
        )
        agent = existing_agent.model_copy(
            update={
                "intent": intent,
                "allowed_tool_names": allowed_tool_names,
                "updated_at": existing_agent.updated_at,
            }
        )
    _agent_designs[agent.id] = agent
    store.save_record("agent_designs", agent.id, agent)
    sync_agent_design_artifact(agent, now)


seed_sentiment_observer_defaults()


def seed_apartment_search_agent_defaults() -> None:
    now = seeded_at
    tool_names = ["call_http_api", "browse_webpage"]
    existing_agent = _agent_designs.get("agent_apartment_search")
    if existing_agent is None:
        agent = AgentDesign(
            id="agent_apartment_search",
            project_id=default_project.id,
            name="Apartment Search Agent",
            intent=APARTMENT_SEARCH_AGENT_INTENT,
            status="designing",
            allowed_tool_names=tool_names,
            created_at=now,
            updated_at=now,
        )
    else:
        agent = existing_agent.model_copy(
            update={
                "allowed_tool_names": list(dict.fromkeys(existing_agent.allowed_tool_names + tool_names)),
                "updated_at": existing_agent.updated_at,
            }
        )
    _agent_designs[agent.id] = agent
    store.save_record("agent_designs", agent.id, agent)
    sync_agent_design_artifact(agent, now)


seed_apartment_search_agent_defaults()


def link_artifacts(
    *,
    project_id: str,
    source_artifact_id: str,
    target_artifact_id: str,
    relationship_type: str,
    now: datetime,
) -> ArtifactLink:
    link = ArtifactLink(
        id=f"link_{uuid4().hex[:12]}",
        project_id=project_id,
        source_artifact_id=source_artifact_id,
        target_artifact_id=target_artifact_id,
        relationship_type=relationship_type,
        created_at=now,
    )
    _artifact_links[link.id] = link
    store.save_record("artifact_links", link.id, link)
    return link


def link_to_agent_design(
    *,
    project_id: str,
    agent_design_id: str,
    artifact: ArtifactRecord,
    now: datetime,
) -> None:
    design_artifact = find_agent_design_artifact(agent_design_id)
    if design_artifact is not None:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=design_artifact.id,
            relationship_type="GENERATED_FROM",
            now=now,
        )





def usage_details_from_anthropic_payload(payload: Dict[str, object]) -> Dict[str, Any]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return {}
    details: Dict[str, Any] = {}
    for key in ("input_tokens", "output_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            details[key] = value
    return details


def live_judge_generation_context(
    *,
    model: str,
    messages: List[Dict[str, object]],
    trace_id: Optional[str],
):
    if not langfuse_credentials_configured():
        return None
    try:
        langfuse = get_langfuse_client()
        return langfuse.start_as_current_observation(
            trace_context={"trace_id": trace_id} if trace_id else None,
            as_type="generation",
            name="anthropic.messages.judge",
            model=model,
            input=messages,
            metadata={
                "provider": "anthropic",
                "endpoint": "/v1/messages",
                "purpose": "eval_judge",
            },
        )
    except Exception:
        return None


def flush_langfuse_client() -> None:
    try:
        langfuse = get_langfuse_client()
        flush = getattr(langfuse, "flush", None)
        if callable(flush):
            flush()
    except Exception:
        pass


def _anthropic_client(config) -> "anthropic.Anthropic":
    import anthropic as anthropic_sdk
    return anthropic_sdk.Anthropic(api_key=config.api_key)


def run_live_judge(
    prompt: str,
    trace_id: Optional[str] = None,
) -> tuple[str, str, Dict[str, object]]:
    import anthropic as anthropic_sdk
    config = anthropic_config_from_env()
    messages: List[Dict[str, object]] = [{"role": "user", "content": prompt}]

    def _call() -> Dict[str, object]:
        try:
            response = _anthropic_client(config).messages.create(
                model=config.model,
                max_tokens=1200,
                system="You are an eval judge for an eval-driven design platform.",
                messages=messages,
            )
            return response.model_dump()
        except anthropic_sdk.APIStatusError as exc:
            raise RuntimeError(f"Anthropic judge request failed with status {exc.status_code}: {exc.message}") from exc
        except anthropic_sdk.APIConnectionError as exc:
            raise RuntimeError(f"Anthropic judge request failed: {exc}") from exc

    generation_context = live_judge_generation_context(
        model=config.model,
        messages=messages,
        trace_id=trace_id,
    )
    payload = _call()
    response_text = extract_response_text(payload)
    if not response_text:
        raise RuntimeError(describe_empty_response(payload))
    token_usage = payload.get("usage", {})
    if not isinstance(token_usage, dict):
        token_usage = {}
    if generation_context is not None:
        with generation_context as generation:
            generation.update(
                output=response_text,
                usage_details=token_usage,
                metadata={
                    "anthropic_message_id": payload.get("id"),
                    "stop_reason": payload.get("stop_reason"),
                },
            )
    flush_langfuse_client()
    return response_text, config.model, token_usage


def run_live_evidence_summary(prompt: str) -> tuple[str, str, Dict[str, object]]:
    import anthropic as anthropic_sdk
    config = anthropic_config_from_env()
    try:
        response = _anthropic_client(config).messages.create(
            model=config.model,
            max_tokens=900,
            system="You summarize bounded evidence for an eval-driven design platform.",
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic_sdk.APIStatusError as exc:
        raise RuntimeError(
            f"Anthropic evidence summary request failed with status {exc.status_code}: {exc.message}"
        ) from exc
    except anthropic_sdk.APIConnectionError as exc:
        raise RuntimeError(f"Anthropic evidence summary request failed: {exc}") from exc
    payload = response.model_dump()
    response_text = extract_response_text(payload)
    if not response_text:
        raise RuntimeError(describe_empty_response(payload))
    token_usage = payload.get("usage", {})
    if not isinstance(token_usage, dict):
        token_usage = {}
    return response_text, config.model, token_usage


def _draft_agent_plan_from_llm(
    outcome: str,
    available_tools: List[str],
) -> Dict[str, object]:
    """Ask the LLM to plan an agent from a user outcome. Returns a dict with
    name, intent, output_focus, output_requirements, allowed_tools, required_tools."""
    import json as _json
    from datetime import date as _date

    tool_list = ", ".join(available_tools) if available_tools else "none"
    today = _date.today().isoformat()

    prompt = (
        f"Today is {today}.\n\n"
        f"A user wants an AI agent that does this:\n{outcome}\n\n"
        f"Available tools in the project: {tool_list}\n\n"
        "Design a minimal agent to satisfy this outcome. Respond with JSON only:\n"
        "{\n"
        '  "name": "Short agent name (2-4 words, title case)",\n'
        '  "intent": "One paragraph describing what the agent does, how it uses its tools, '
        'and what a good response looks like. Be specific about tool use order.",\n'
        '  "output_focus": "One sentence describing the key output requirement.",\n'
        '  "output_requirements": ["keyword1", "keyword2"],\n'
        '  "allowed_tools": ["tool_name"],\n'
        '  "required_tools": ["tool_name"]\n'
        "}\n\n"
        "Rules:\n"
        "- allowed_tools and required_tools must only contain names from the available tools list.\n"
        "- If a tool is in required_tools it must also be in allowed_tools.\n"
        "- If no available tool fits, use empty lists.\n"
        "- For web/SPA tasks (job boards, real estate, JS-heavy sites) prefer browse_webpage over call_http_api.\n"
        "- output_requirements should be short keywords that must appear in a passing response."
    )

    try:
        config = anthropic_config_from_env()
        response = _anthropic_client(config).messages.create(
            model=config.model,
            max_tokens=800,
            system="You design AI agents. Respond with valid JSON only, no markdown fences.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw = block.text.strip()
                break
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = _json.loads(raw)
        valid_tools = set(available_tools)
        allowed = [t for t in data.get("allowed_tools", []) if t in valid_tools]
        required = [t for t in data.get("required_tools", []) if t in valid_tools]
        return {
            "name": str(data.get("name", "Outcome Agent")),
            "intent": str(data.get("intent", outcome)),
            "output_focus": str(data.get("output_focus", "Return the requested outcome.")),
            "output_requirements": [str(r) for r in data.get("output_requirements", ["outcome"])],
            "allowed_tools": allowed,
            "required_tools": required,
        }
    except Exception:
        return {
            "name": "Outcome Agent",
            "intent": outcome,
            "output_focus": "Return the requested outcome directly.",
            "output_requirements": ["outcome"],
            "allowed_tools": [],
            "required_tools": [],
        }



def create_failure_packet_record(
    *,
    project_id: str,
    agent_design_id: str,
    agent_version_id: Optional[str],
    run_id: str,
    eval_result_id: str,
    eval_contract_id: str,
    failed_check_ids: List[str],
    title: str,
    diagnosis: str,
    severity: str,
    evidence_artifact_ids: List[str],
    recommended_fix: str,
    status: str,
    now: datetime,
) -> FailurePacket:
    failure_packet = FailurePacket(
        id=f"failure_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=agent_design_id,
        agent_version_id=agent_version_id,
        run_id=run_id,
        eval_result_id=eval_result_id,
        eval_contract_id=eval_contract_id,
        failed_check_ids=failed_check_ids,
        title=title,
        diagnosis=diagnosis,
        severity=severity,
        evidence_artifact_ids=evidence_artifact_ids,
        recommended_fix=recommended_fix,
        status=status,
        created_at=now,
        updated_at=now,
    )
    _failure_packets[failure_packet.id] = failure_packet
    store.save_record("failure_packets", failure_packet.id, failure_packet)

    body = (
        f"Diagnosis\n{failure_packet.diagnosis}\n\n"
        f"Failed checks\n"
        + "\n".join(f"- {check_id}" for check_id in failure_packet.failed_check_ids)
        + f"\n\nRecommended fix\n{failure_packet.recommended_fix or 'Needs review'}"
    )
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="FAILURE_PACKET",
        artifact_id=failure_packet.id,
        title=failure_packet.title,
        body=body,
        source="failure-packet",
        agent_design_id=agent_design_id,
        now=now,
    )
    for evidence_artifact_id in evidence_artifact_ids:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=evidence_artifact_id,
            relationship_type="SUPPORTED_BY",
            now=now,
        )
    return failure_packet



