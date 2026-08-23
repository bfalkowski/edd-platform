from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from edd_platform_api import main as api_main
from edd_platform_api.eval_checks import evaluate_contract_check
from edd_platform_api.evidence_context import (
    build_deterministic_evidence_summary,
    build_evidence_summary_prompt,
    context_pack_cache_key,
)
from edd_platform_api.lookups import (
    get_agent_design_or_404,
    get_agent_version_or_404,
    get_artifact_or_404,
    get_eval_contract_or_404,
    get_eval_result_or_404,
    get_judge_prompt_template_or_404,
    get_project_or_404,
    get_run_or_404,
    get_scenario_or_404,
)
from edd_platform_api.routers import artifacts as _artifacts_router
from edd_platform_api.routers import trace_refs as _trace_refs_router
from edd_platform_api.schemas import (
    AgentDesign,
    AgentRunCreate,
    AgentRunResult,
    AgentVersion,
    ArtifactRecord,
    ContextPack,
    ContextPackCreate,
    EvalCheckResult,
    EvalContract,
    EvalResult,
    EvidenceSummary,
    EvidenceSummaryCreate,
    ExternalArtifactRef,
    JudgeOutput,
    JudgePromptTemplate,
    RunCreate,
    RunEvaluateCreate,
    RunRecord,
    TraceRef,
    TraceRefCreate,
)
from edd_platform_api.state import (
    _agent_designs,
    _artifacts,
    _eval_results,
    _evidence_summaries,
    _judge_outputs,
    _runs,
    _tool_definitions,
    _trace_refs,
    store,
)
from edd_runner import RunnerAgentDesign, RunnerScenario, RunnerToolDefinition, run_mock_agent

router = APIRouter()

_LIVE_JUDGE_CHECK_TYPES = {"outcome_rubric", "rubric_judge", "llm_judge"}


def create_runner_trace_artifact(
    *,
    project_id: str,
    agent_design_id: str,
    provider: str,
    trace_id: str,
    trace_url: str,
    run_id: str,
    metadata: Dict[str, object],
    related_artifact_ids: List[str],
    now: datetime,
) -> ArtifactRecord:
    artifact = api_main.create_artifact(
        project_id=project_id,
        artifact_type="TRACE_REF",
        artifact_id=f"trace_ref_{uuid4().hex[:12]}",
        title=f"{provider} trace: {trace_id}",
        body=(
            f"Provider\n{provider}\n\n"
            f"External trace id\n{trace_id}\n\n"
            f"Run\n{run_id}\n\n"
            f"URL\n{trace_url}\n\n"
            f"Metadata\n{json.dumps(metadata, sort_keys=True)}"
        ),
        source=f"trace-ref:{provider}",
        agent_design_id=agent_design_id,
        now=now,
        external_refs=[
            ExternalArtifactRef(
                provider=provider,
                ref_type="trace",
                external_id=trace_id,
                url=trace_url,
                label="Langfuse trace" if provider == "langfuse" else "Trace",
                metadata=metadata,
            )
        ]
        + api_main.prompt_refs_from_metadata(metadata),
    )
    for related_artifact_id in related_artifact_ids:
        if related_artifact_id in _artifacts:
            api_main.link_artifacts(
                project_id=project_id,
                source_artifact_id=artifact.id,
                target_artifact_id=related_artifact_id,
                relationship_type="OBSERVES",
                now=now,
            )
    api_main.link_to_agent_design(
        project_id=project_id,
        agent_design_id=agent_design_id,
        artifact=artifact,
        now=now,
    )
    return artifact


def approved_tools_for_agent(project_id: str, agent: AgentDesign) -> List[RunnerToolDefinition]:
    allowed = set(agent.allowed_tool_names)
    return [
        RunnerToolDefinition(
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
            output_schema=tool.output_schema,
            output_description=tool.output_description,
            implementation_kind=tool.implementation_kind,
            implementation_key=tool.implementation_key,
            config_schema=tool.config_schema,
            mock_response=tool.mock_response,
            status=tool.status,
        )
        for tool in _tool_definitions.values()
        if tool.project_id == project_id and tool.status == "approved" and tool.name in allowed
    ]


def build_live_judge_prompt(
    *,
    contract: EvalContract,
    run: RunRecord,
    checks: List[EvalCheckResult],
    template: Optional[JudgePromptTemplate],
) -> str:
    # Only include deterministic checks in the prompt — rubric/LLM checks are
    # evaluated by the live judge itself and their stub results ("live judge required")
    # would pollute the evidence context.
    deterministic_checks = [
        c for c in checks if c.check_id not in _LIVE_JUDGE_CHECK_TYPES
    ]
    check_lines = "\n".join(
        f"- {check.check_id}: {'pass' if check.passed else 'fail'}; "
        f"expected={check.expected}; observed={check.observed}; comment={check.comment}"
        for check in deterministic_checks
    )
    template_text = (
        template.template
        if template is not None
        else "Explain whether the response satisfies the eval contract. Cite the provided evidence only."
    )
    rubric_check = next(
        (c for c in contract.checks if c.get("type") in ("rubric_judge", "llm_judge")), None
    )
    rubric = (rubric_check.get("value") or "" if rubric_check else "").strip()
    rubric_section = f"Rubric:\n{rubric}\n\n" if rubric else ""
    deterministic_section = (
        f"Deterministic check results:\n{check_lines}\n\n" if check_lines else ""
    )
    return (
        f"{template_text}\n\n"
        f"Eval contract: {contract.name}\n"
        f"Expected behavior:\n" + "\n".join(f"- {item}" for item in contract.expected_behavior)
        + "\n\n"
        f"{rubric_section}"
        f"Run input:\n{run.input}\n\n"
        f"Run output:\n{run.output}\n\n"
        f"{deterministic_section}"
        "Put PASS or FAIL as the first word of your response, "
        "then give a concise explanation citing only the evidence above."
    )


def token_count(token_usage: Dict[str, object], key: str) -> int:
    value = token_usage.get(key, 0)
    return value if isinstance(value, int) else 0


def estimate_live_judge_cost(token_usage: Dict[str, object]) -> Optional[float]:
    input_rate = os.environ.get("EDD_ANTHROPIC_INPUT_COST_PER_1M", "").strip()
    output_rate = os.environ.get("EDD_ANTHROPIC_OUTPUT_COST_PER_1M", "").strip()
    if not input_rate or not output_rate:
        return None
    try:
        input_cost_per_1m = float(input_rate)
        output_cost_per_1m = float(output_rate)
    except ValueError:
        return None

    input_tokens = token_count(token_usage, "input_tokens")
    output_tokens = token_count(token_usage, "output_tokens")
    return round(
        (input_tokens / 1_000_000 * input_cost_per_1m)
        + (output_tokens / 1_000_000 * output_cost_per_1m),
        8,
    )


def active_prompt_refs_for_run(
    *,
    project_id: str,
    agent: AgentDesign,
    version: Optional[AgentVersion],
    contract_id: Optional[str],
) -> List[ExternalArtifactRef]:
    refs: List[ExternalArtifactRef] = []
    if version is not None:
        refs.extend(
            api_main.langfuse_prompt_refs(
                name=version.langfuse_prompt_name,
                version=version.langfuse_prompt_version,
                label=version.langfuse_prompt_label,
                prompt_role="agent_version",
                source_id=version.id,
            )
        )
    else:
        refs.extend(
            api_main.langfuse_prompt_refs(
                name=agent.langfuse_prompt_name,
                version=agent.langfuse_prompt_version,
                label=agent.langfuse_prompt_label,
                prompt_role="agent",
                source_id=agent.id,
            )
        )

    if contract_id is not None:
        contract = get_eval_contract_or_404(project_id, contract_id)
        if contract.judge_prompt_template_id is not None:
            template = get_judge_prompt_template_or_404(
                project_id,
                contract.judge_prompt_template_id,
            )
            refs.extend(
                api_main.langfuse_prompt_refs(
                    name=template.langfuse_prompt_name,
                    version=template.langfuse_prompt_version,
                    label=template.langfuse_prompt_label,
                    prompt_role="judge",
                    source_id=template.id,
                )
            )
    return refs


def create_tool_evidence_artifacts(
    *,
    project_id: str,
    agent_design_id: str,
    run_artifact: ArtifactRecord,
    runner_result: object,
    now: datetime,
) -> List[ArtifactRecord]:
    artifacts: List[ArtifactRecord] = []
    for index, tool_call in enumerate(runner_result.tool_calls, start=1):
        call_artifact = api_main.create_artifact(
            project_id=project_id,
            artifact_type="TOOL_CALL",
            artifact_id=f"{runner_result.id}:tool-call:{index}",
            title=f"Tool call: {tool_call.name}",
            body=(
                f"Run\n{runner_result.id}\n\n"
                f"Tool\n{tool_call.name}\n\n"
                f"Input\n{tool_call.input or 'not captured'}"
            ),
            source=f"runner:{runner_result.mode}",
            agent_design_id=agent_design_id,
            now=now,
        )
        api_main.link_artifacts(
            project_id=project_id,
            source_artifact_id=call_artifact.id,
            target_artifact_id=run_artifact.id,
            relationship_type="GENERATED_FROM",
            now=now,
        )
        result_artifact = api_main.create_artifact(
            project_id=project_id,
            artifact_type="TOOL_RESULT",
            artifact_id=f"{runner_result.id}:tool-result:{index}",
            title=f"Tool result: {tool_call.name}",
            body=(
                f"Run\n{runner_result.id}\n\n"
                f"Tool\n{tool_call.name}\n\n"
                f"Output\n{tool_call.output}"
            ),
            source=f"runner:{runner_result.mode}",
            agent_design_id=agent_design_id,
            now=now,
        )
        api_main.link_artifacts(
            project_id=project_id,
            source_artifact_id=result_artifact.id,
            target_artifact_id=call_artifact.id,
            relationship_type="GENERATED_FROM",
            now=now,
        )
        artifacts.extend([call_artifact, result_artifact])
    return artifacts


_LIVE_PROVIDER_MISSING_CONFIG_MARKERS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "foundry": "AZURE_AI_FOUNDRY_PROJECT_ENDPOINT",
}


def run_agent_with_runner(
    *,
    project_id: str,
    agent: AgentDesign,
    instructions: str,
    scenario_input: str,
    mode: Literal["mock", "live"],
    provider: Optional[Literal["anthropic", "foundry"]] = None,
    prompt_refs: Optional[List[ExternalArtifactRef]] = None,
    model_override: Optional[str] = None,
) -> tuple[object, ArtifactRecord, List[ArtifactRecord], str]:
    runner_agent = RunnerAgentDesign(
        id=agent.id,
        name=agent.name,
        intent=instructions,
        allowed_tool_names=agent.allowed_tool_names,
    )
    runner_scenario = RunnerScenario(input=scenario_input.strip())
    resolved_provider = provider or "anthropic"
    if mode == "live":
        try:
            if resolved_provider == "foundry":
                config = api_main.foundry_config_from_env()
                if model_override:
                    config = config.__class__(**{**config.__dict__, "model": model_override})
                runner_result = api_main.run_foundry_agent(
                    runner_agent,
                    runner_scenario,
                    config,
                    approved_tools_for_agent(project_id, agent),
                )
            else:
                config = api_main.anthropic_config_from_env()
                if model_override:
                    config = config.__class__(**{**config.__dict__, "model": model_override})
                runner_result = api_main.run_anthropic_agent(
                    runner_agent,
                    runner_scenario,
                    config,
                    approved_tools_for_agent(project_id, agent),
                )
        except RuntimeError as exc:
            detail = str(exc)
            marker = _LIVE_PROVIDER_MISSING_CONFIG_MARKERS[resolved_provider]
            status_code = 400 if marker in detail else 502
            raise HTTPException(status_code=status_code, detail=detail) from exc
    else:
        runner_result = run_mock_agent(runner_agent, runner_scenario)
        resolved_provider = "mock"

    now = datetime.now(timezone.utc)
    tool_summary = "\n".join(
        f"- {tool.name}: {tool.output}" for tool in runner_result.tool_calls
    )
    artifact = api_main.create_artifact(
        project_id=project_id,
        artifact_type="RUN_RESULT",
        artifact_id=runner_result.id,
        title=f"Run: {agent.name}",
        body=(
            f"Response\n{runner_result.response}\n\n"
            f"Scenario\n{runner_result.scenario_input}\n\n"
            f"Tools\n{tool_summary}"
        ),
        source=f"runner:{runner_result.mode}",
        agent_design_id=agent.id,
        now=now,
        external_refs=prompt_refs if runner_result.mode == "live" else [],
    )
    api_main.link_to_agent_design(
        project_id=project_id,
        agent_design_id=agent.id,
        artifact=artifact,
        now=now,
    )
    tool_artifacts = create_tool_evidence_artifacts(
        project_id=project_id,
        agent_design_id=agent.id,
        run_artifact=artifact,
        runner_result=runner_result,
        now=now,
    )
    return runner_result, artifact, tool_artifacts, resolved_provider


def validate_website_url(url: Optional[str]) -> str:
    if url is None or not url.strip():
        raise HTTPException(status_code=422, detail="URL is required when target is url.")
    target_url = url.strip()
    parsed = urlparse(target_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=422, detail="URL must use http or https.")
    return target_url


def call_website_for_agent(
    *,
    project_id: str,
    agent: AgentDesign,
    url: str,
) -> AgentRunResult:
    target_url = validate_website_url(url)
    run_id = f"run_{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    request = Request(target_url, headers={"User-Agent": "edd-platform-url-trace/1.0"})
    trace_id: Optional[str] = None
    trace_url: Optional[str] = None
    status_code: Optional[int] = None
    headers: Dict[str, str] = {}
    body_bytes = b""
    error: Optional[str] = None
    request_attempted = False

    def execute_request() -> None:
        nonlocal status_code, headers, body_bytes, error, request_attempted
        request_attempted = True
        try:
            with api_main.urlopen(request, timeout=10) as response:
                status_code = response.getcode()
                headers = {key: value for key, value in response.headers.items()}
                body_bytes = response.read(4096)
        except HTTPError as exc:
            status_code = exc.code
            headers = {key: value for key, value in exc.headers.items()} if exc.headers else {}
            body_bytes = exc.read(4096)
            error = f"HTTP {exc.code}"
        except URLError as exc:
            error = str(exc.reason)

    if api_main.langfuse_credentials_configured():
        try:
            langfuse = api_main.get_langfuse_client()
            with langfuse.start_as_current_observation(
                as_type="span",
                name="edd-url-call",
                input={"method": "GET", "url": target_url},
                metadata={
                    "source": "edd-platform",
                    "runner_mode": "url",
                    "agent_design_id": agent.id,
                    "ad_hoc": True,
                },
            ) as observation:
                execute_request()
                observation.update(
                    output={
                        "status_code": status_code,
                        "content_type": headers.get("Content-Type"),
                        "bytes_captured": len(body_bytes),
                        "error": error,
                    }
                )
                trace_id = langfuse.get_current_trace_id() or observation.trace_id
                if trace_id:
                    try:
                        trace_url = langfuse.get_trace_url(trace_id=trace_id)
                    except Exception:
                        trace_url = None
            try:
                langfuse.flush()
            except Exception:
                pass
        except Exception as exc:
            error = f"Langfuse trace unavailable: {exc}"
            if not request_attempted:
                execute_request()
    else:
        execute_request()

    decoded_body = body_bytes.decode("utf-8", errors="replace")
    content_type = headers.get("Content-Type", "unknown")
    result_summary = (
        f"GET {target_url} returned "
        f"{status_code if status_code is not None else 'no status'} "
        f"with {content_type}."
    )
    if error is not None:
        result_summary = f"{result_summary} Error: {error}."

    artifact = api_main.create_artifact(
        project_id=project_id,
        artifact_type="RUN_RESULT",
        artifact_id=run_id,
        title=f"URL call: {target_url}",
        body=(
            f"Response\n{result_summary}\n\n"
            f"URL\n{target_url}\n\n"
            f"Status\n{status_code if status_code is not None else 'unavailable'}\n\n"
            f"Content type\n{content_type}\n\n"
            f"Bytes captured\n{len(body_bytes)}\n\n"
            f"Body excerpt\n{decoded_body[:1000]}"
        ),
        source="runner:url",
        agent_design_id=agent.id,
        now=now,
    )
    api_main.link_to_agent_design(
        project_id=project_id,
        agent_design_id=agent.id,
        artifact=artifact,
        now=now,
    )
    trace_artifact: Optional[ArtifactRecord] = None
    artifact_ids = [artifact.id]
    if trace_id and trace_url:
        trace_artifact = create_runner_trace_artifact(
            project_id=project_id,
            agent_design_id=agent.id,
            provider="langfuse",
            trace_id=trace_id,
            trace_url=trace_url,
            run_id=run_id,
            metadata={
                "runner_mode": "url",
                "provider": "http",
                "ad_hoc": True,
                "url": target_url,
                "status_code": status_code,
            },
            related_artifact_ids=artifact_ids,
            now=now,
        )
        artifact_ids.append(trace_artifact.id)

    evidence = [
        "Called the URL directly without an agent or model provider.",
        f"Captured HTTP status {status_code if status_code is not None else 'unavailable'}.",
    ]
    if trace_id:
        evidence.append(f"Linked Langfuse trace {trace_id}.")
    elif not api_main.langfuse_credentials_configured():
        evidence.append("Langfuse trace not created because credentials are not configured.")

    return AgentRunResult(
        id=run_id,
        project_id=project_id,
        agent_design_id=agent.id,
        mode="url",
        scenario_input=target_url,
        response=result_summary,
        tool_calls=[
            {
                "name": "http_get",
                "input": target_url,
                "output": result_summary,
            }
        ],
        evidence=evidence,
        trace_id=trace_id,
        trace_url=trace_url,
        artifact=artifact,
        trace_artifact=trace_artifact,
        artifact_ids=artifact_ids,
        created_at=now,
    )


def find_langfuse_trace_ref_for_run(project_id: str, run_id: str) -> Optional[TraceRef]:
    trace_refs = [
        trace_ref
        for trace_ref in _trace_refs.values()
        if trace_ref.project_id == project_id
        and trace_ref.run_id == run_id
        and trace_ref.provider == "langfuse"
    ]
    return sorted(trace_refs, key=lambda trace_ref: trace_ref.created_at, reverse=True)[0] if trace_refs else None


def langfuse_score_sync_enabled() -> bool:
    return os.environ.get("EDD_PLATFORM_LANGFUSE_SCORE_SYNC", "").strip().lower() == "live"


def sync_langfuse_eval_score_refs(
    *,
    project_id: str,
    run: RunRecord,
    contract: EvalContract,
    eval_id: str,
    judge_output_id: str,
    judge_mode: str,
    score: int,
    check_count: int,
    passed: bool,
) -> List[ExternalArtifactRef]:
    if not langfuse_score_sync_enabled() or run.mode != "live":
        return []

    score_id = f"score_{eval_id}"
    metadata: Dict[str, object] = {
        "project_id": project_id,
        "agent_design_id": run.agent_design_id,
        "agent_version_id": run.agent_version_id,
        "run_id": run.id,
        "scenario_id": run.scenario_id,
        "eval_contract_id": contract.id,
        "eval_result_id": eval_id,
        "judge_output_id": judge_output_id,
        "judge_mode": judge_mode,
        "raw_score": score,
        "check_count": check_count,
        "passed": passed,
        "source": "edd-platform",
    }
    if not api_main.langfuse_credentials_configured():
        return [
            ExternalArtifactRef(
                provider="langfuse",
                ref_type="score",
                external_id=score_id,
                label="Langfuse score",
                metadata={
                    **metadata,
                    "sync_mode": "planned",
                    "sync_requested": "live",
                    "sync_error": "missing_langfuse_credentials",
                },
            )
        ]

    trace_ref = find_langfuse_trace_ref_for_run(project_id, run.id)
    if trace_ref is None:
        return [
            ExternalArtifactRef(
                provider="langfuse",
                ref_type="score",
                external_id=score_id,
                label="Langfuse score",
                metadata={
                    **metadata,
                    "sync_mode": "planned",
                    "sync_requested": "live",
                    "sync_error": "missing_langfuse_trace_ref",
                },
            )
        ]

    normalized_score = score / check_count if check_count else (1.0 if passed else 0.0)
    try:
        langfuse = api_main.get_langfuse_client()
        langfuse.create_score(
            name="edd_eval_pass_rate",
            value=normalized_score,
            trace_id=trace_ref.external_trace_id,
            score_id=score_id,
            data_type="NUMERIC",
            comment=f"EDD eval {eval_id}: {score}/{check_count} checks passed.",
            metadata=metadata,
        )
        flush = getattr(langfuse, "flush", None)
        if callable(flush):
            flush()
    except Exception as exc:
        return [
            ExternalArtifactRef(
                provider="langfuse",
                ref_type="score",
                external_id=score_id,
                label="Langfuse score",
                metadata={
                    **metadata,
                    "sync_mode": "planned",
                    "sync_requested": "live",
                    "trace_id": trace_ref.external_trace_id,
                    "sync_error": str(exc),
                },
            )
        ]

    return [
        ExternalArtifactRef(
            provider="langfuse",
            ref_type="score",
            external_id=score_id,
            label="Langfuse score",
            metadata={
                **metadata,
                "sync_mode": "live",
                "trace_id": trace_ref.external_trace_id,
                "score_name": "edd_eval_pass_rate",
                "score_value": normalized_score,
            },
        )
    ]


CONTEXT_PACK_ARTIFACT_TYPES: Dict[str, set[str]] = {
    "AGENT_PROMPT_REVIEW": {
        "AGENT_DESIGN",
        "AGENT_VERSION",
        "EVAL_CONTRACT",
        "JUDGE_PROMPT_TEMPLATE",
        "GATE",
        "TRACE_REF",
    },
    "SIDE_BY_SIDE_VERSION_COMPARISON": {
        "COMPARISON",
        "EVAL_RESULT",
        "JUDGE_OUTPUT",
        "FAILURE_PACKET",
        "FIX_PROPOSAL",
        "RUN_RESULT",
        "SCENARIO",
        "TRACE_REF",
    },
    "FIX_PROPOSAL_GENERATION": {
        "FAILURE_PACKET",
        "EVAL_RESULT",
        "JUDGE_OUTPUT",
        "FIX_PROPOSAL",
        "EVAL_CONTRACT",
        "RUN_RESULT",
        "SCENARIO",
        "TRACE_REF",
    },
    "GATE_DECISION_REVIEW": {
        "GATE",
        "GATE_DECISION",
        "COMPARISON",
        "EVAL_RESULT",
        "JUDGE_OUTPUT",
        "FAILURE_PACKET",
        "SCENARIO",
        "TRACE_REF",
    },
}


def assemble_context_pack_artifacts(
    *,
    project_id: str,
    agent_design_id: Optional[str],
    purpose: str,
) -> List[ArtifactRecord]:
    artifacts = _artifacts_router.list_project_artifacts(
        project_id=project_id,
        agent_design_id=agent_design_id,
    )
    allowed_types = CONTEXT_PACK_ARTIFACT_TYPES.get(purpose.strip().upper())
    if allowed_types is None:
        return artifacts
    return [artifact for artifact in artifacts if artifact.artifact_type in allowed_types]


@router.get("/api/projects/{project_id}/runs")
def list_runs(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[RunRecord]:
    get_project_or_404(project_id)
    runs = [
        run
        for run in _runs.values()
        if run.project_id == project_id
        and (agent_design_id is None or run.agent_design_id == agent_design_id)
    ]
    return sorted(runs, key=lambda run: run.completed_at, reverse=True)


@router.post("/api/projects/{project_id}/runs", status_code=201)
def create_run(project_id: str, payload: RunCreate) -> RunRecord:
    get_project_or_404(project_id)
    agent = get_agent_design_or_404(project_id, payload.agent_design_id)
    scenario = get_scenario_or_404(project_id, payload.scenario_id)
    if scenario.agent_design_id != agent.id:
        raise HTTPException(
            status_code=400,
            detail="Run scenario must belong to the selected agent design.",
        )

    version: Optional[AgentVersion] = None
    if payload.agent_version_id is not None:
        version = get_agent_version_or_404(project_id, payload.agent_version_id)
        if version.agent_design_id != agent.id:
            raise HTTPException(
                status_code=400,
                detail="Run version must belong to the selected agent design.",
            )

    if payload.eval_contract_id is not None:
        contract = get_eval_contract_or_404(project_id, payload.eval_contract_id)
        if contract.agent_design_id != agent.id:
            raise HTTPException(
                status_code=400,
                detail="Run eval contract must belong to the selected agent design.",
            )
        if contract.scenario_id is not None and contract.scenario_id != scenario.id:
            raise HTTPException(
                status_code=400,
                detail="Run eval contract must match the selected scenario.",
            )

    instructions = version.instructions if version is not None else agent.intent
    prompt_refs = active_prompt_refs_for_run(
        project_id=project_id,
        agent=agent,
        version=version,
        contract_id=payload.eval_contract_id,
    )
    runner_result, artifact, tool_artifacts, provider = run_agent_with_runner(
        project_id=project_id,
        agent=agent,
        instructions=instructions,
        scenario_input=scenario.input,
        mode=payload.mode,
        provider=payload.provider,
        prompt_refs=prompt_refs,
        model_override=payload.model or None,
    )
    run = RunRecord(
        id=runner_result.id,
        project_id=project_id,
        agent_design_id=agent.id,
        agent_version_id=version.id if version is not None else None,
        scenario_id=scenario.id,
        eval_contract_id=payload.eval_contract_id,
        mode=runner_result.mode,
        provider=provider,
        model=None,
        input=runner_result.scenario_input,
        output=runner_result.response,
        status="completed",
        artifact_ids=[artifact.id] + [tool_artifact.id for tool_artifact in tool_artifacts],
        started_at=runner_result.created_at,
        completed_at=runner_result.created_at,
    )
    _runs[run.id] = run
    store.save_record("runs", run.id, run)
    if runner_result.trace_id and runner_result.trace_url:
        _trace_refs_router.create_trace_ref_record(
            project_id=project_id,
            payload=TraceRefCreate(
                provider="langfuse",
                external_trace_id=runner_result.trace_id,
                run_id=run.id,
                url=runner_result.trace_url,
                metadata={
                    "runner_mode": run.mode,
                    "provider": run.provider,
                    "agent_version_id": run.agent_version_id,
                    "scenario_id": run.scenario_id,
                    "eval_contract_id": run.eval_contract_id,
                    "prompt_refs": [ref.model_dump(mode="json") for ref in prompt_refs],
                },
                related_artifact_ids=run.artifact_ids,
            ),
            now=datetime.now(timezone.utc),
        )
    return run


@router.get("/api/projects/{project_id}/runs/{run_id}")
def get_run(project_id: str, run_id: str) -> RunRecord:
    get_project_or_404(project_id)
    return get_run_or_404(project_id, run_id)


@router.post("/api/projects/{project_id}/runs/{run_id}/evaluate", status_code=201)
def evaluate_run(
    project_id: str,
    run_id: str,
    payload: RunEvaluateCreate,
) -> EvalResult:
    get_project_or_404(project_id)
    run = get_run_or_404(project_id, run_id)

    contract_id = payload.eval_contract_id or run.eval_contract_id
    if contract_id is None:
        raise HTTPException(status_code=400, detail="Run evaluation requires an eval contract.")
    contract = get_eval_contract_or_404(project_id, contract_id)
    if contract.agent_design_id != run.agent_design_id:
        raise HTTPException(
            status_code=400,
            detail="Eval contract must belong to the same agent design as the run.",
        )
    if contract.scenario_id is not None and contract.scenario_id != run.scenario_id:
        raise HTTPException(
            status_code=400,
            detail="Eval contract must match the run scenario.",
        )

    run_artifact = (
        get_artifact_or_404(project_id, run.artifact_ids[0])
        if run.artifact_ids
        else None
    )
    evidence_artifact_ids = [
        artifact_id
        for artifact_id in run.artifact_ids
        if _artifacts.get(artifact_id) is not None
    ]
    evidence_bodies = [
        _artifacts[artifact_id].body
        for artifact_id in evidence_artifact_ids
        if artifact_id in _artifacts
    ]
    run_artifact_body = "\n\n".join(evidence_bodies) if evidence_bodies else run.output
    checks = [
        evaluate_contract_check(
            check=check,
            run=run,
            evidence_artifact_ids=evidence_artifact_ids,
            run_artifact_body=run_artifact_body,
        )
        for check in contract.checks
    ]
    score = sum(1 for check in checks if check.passed)
    passed = score == len(checks)
    now = datetime.now(timezone.utc)
    eval_id = f"eval_{uuid4().hex[:12]}"
    check_lines = "\n".join(
        f"- {check.check_id}: {'pass' if check.passed else 'fail'} - {check.comment}"
        for check in checks
    )
    judge_output_id = f"judge_{uuid4().hex[:12]}"
    judge_output_text = "\n".join(
        f"{check.check_id}: {'pass' if check.passed else 'fail'} ({check.comment})"
        for check in checks
    ) or "No deterministic checks defined."
    judge_model: Optional[str] = None
    token_usage: Dict[str, object] = {}
    cost_estimate: Optional[float] = None
    if payload.judge_mode == "live":
        template = (
            get_judge_prompt_template_or_404(project_id, contract.judge_prompt_template_id)
            if contract.judge_prompt_template_id is not None
            else None
        )
        prompt = build_live_judge_prompt(
            contract=contract,
            run=run,
            checks=checks,
            template=template,
        )
        trace_ref = find_langfuse_trace_ref_for_run(project_id, run.id)
        try:
            judge_output_text, judge_model, token_usage = api_main.run_live_judge(
                prompt,
                trace_id=trace_ref.external_trace_id if trace_ref is not None else None,
            )
        except RuntimeError as exc:
            detail = str(exc)
            status_code = 400 if "ANTHROPIC_API_KEY" in detail else 502
            raise HTTPException(status_code=status_code, detail=detail) from exc
        cost_estimate = estimate_live_judge_cost(token_usage)
        if any(check.check_type == "rubric_judge" for check in checks):
            judge_passed = judge_output_text.strip().lower().startswith("pass")
            checks = [
                check.model_copy(
                    update={
                        "passed": judge_passed,
                        "observed": run.output,
                        "comment": (
                            "Live judge marked the rubric as passed."
                            if judge_passed
                            else "Live judge marked the rubric as failed."
                        ),
                    }
                )
                if check.check_type == "rubric_judge"
                else check
                for check in checks
            ]
            score = sum(1 for check in checks if check.passed)
            passed = score == len(checks)
            check_lines = "\n".join(
                f"- {check.check_id}: {'pass' if check.passed else 'fail'} - {check.comment}"
                for check in checks
            )

    score_refs = sync_langfuse_eval_score_refs(
        project_id=project_id,
        run=run,
        contract=contract,
        eval_id=eval_id,
        judge_output_id=judge_output_id,
        judge_mode=payload.judge_mode,
        score=score,
        check_count=len(checks),
        passed=passed,
    )
    artifact = api_main.create_artifact(
        project_id=project_id,
        artifact_type="EVAL_RESULT",
        artifact_id=eval_id,
        title=f"Eval: {contract.name}",
        body=(
            f"Contract\n{contract.name}\n\n"
            f"Run\n{run.id}\n\n"
            f"Score\n{score}/{len(checks)}\n\n"
            f"Result\n{'Passed' if passed else 'Failed'}\n\n"
            f"Checks\n{check_lines or 'No checks defined'}"
        ),
        source=f"judge:{payload.judge_mode}",
        agent_design_id=run.agent_design_id,
        now=now,
        external_refs=score_refs,
    )
    for evidence_artifact_id in evidence_artifact_ids:
        api_main.link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=evidence_artifact_id,
            relationship_type="GENERATED_FROM",
            now=now,
        )
    contract_artifact = api_main.find_artifact_by_type_and_artifact_id("EVAL_CONTRACT", contract.id)
    if contract_artifact is not None:
        api_main.link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=contract_artifact.id,
            relationship_type="SUPPORTED_BY",
            now=now,
        )

    judge_artifact = api_main.create_artifact(
        project_id=project_id,
        artifact_type="JUDGE_OUTPUT",
        artifact_id=judge_output_id,
        title=f"Judge: {contract.name}",
        body=judge_output_text,
        source=f"judge:{payload.judge_mode}",
        agent_design_id=run.agent_design_id,
        now=now,
        external_refs=score_refs,
    )
    api_main.link_artifacts(
        project_id=project_id,
        source_artifact_id=artifact.id,
        target_artifact_id=judge_artifact.id,
        relationship_type="SUPPORTED_BY",
        now=now,
    )
    judge_output = JudgeOutput(
        id=judge_output_id,
        project_id=project_id,
        eval_result_id=eval_id,
        judge_prompt_template_id=contract.judge_prompt_template_id,
        mode=payload.judge_mode,
        model=judge_model,
        input_summary=f"Run {run.id} evaluated against {contract.id}.",
        output=judge_output_text,
        token_usage=token_usage,
        cost_estimate=cost_estimate,
        artifact_ids=[judge_artifact.id],
        created_at=now,
    )
    _judge_outputs[judge_output.id] = judge_output
    store.save_record("judge_outputs", judge_output.id, judge_output)

    eval_result = EvalResult(
        id=eval_id,
        project_id=project_id,
        run_id=run.id,
        eval_contract_id=contract.id,
        judge_prompt_template_id=contract.judge_prompt_template_id,
        mode=payload.judge_mode,
        score=score,
        passed=passed,
        checks=checks,
        judge_output_ids=[judge_output.id],
        artifact_ids=[artifact.id, judge_artifact.id],
        created_at=now,
    )
    _eval_results[eval_result.id] = eval_result
    store.save_record("eval_results", eval_result.id, eval_result)
    failed_check_ids = [check.check_id for check in checks if not check.passed]
    if failed_check_ids:
        api_main.create_failure_packet_record(
            project_id=project_id,
            agent_design_id=run.agent_design_id,
            agent_version_id=run.agent_version_id,
            run_id=run.id,
            eval_result_id=eval_result.id,
            eval_contract_id=contract.id,
            failed_check_ids=failed_check_ids,
            title=f"Failed eval: {contract.name}",
            diagnosis=(
                "The run failed one or more eval contract checks: "
                + ", ".join(failed_check_ids)
            ),
            severity="medium",
            evidence_artifact_ids=eval_result.artifact_ids,
            recommended_fix="Review the failed checks and propose a bounded agent change.",
            status="open",
            now=now,
        )
    return eval_result


@router.get("/api/projects/{project_id}/eval-results/{eval_result_id}")
def get_eval_result(project_id: str, eval_result_id: str) -> EvalResult:
    get_project_or_404(project_id)
    return get_eval_result_or_404(project_id, eval_result_id)


@router.get("/api/projects/{project_id}/eval-results")
def list_eval_results(
    project_id: str,
    run_id: Optional[str] = None,
    eval_contract_id: Optional[str] = None,
) -> List[EvalResult]:
    get_project_or_404(project_id)
    eval_results = [
        eval_result
        for eval_result in _eval_results.values()
        if eval_result.project_id == project_id
        and (run_id is None or eval_result.run_id == run_id)
        and (
            eval_contract_id is None
            or eval_result.eval_contract_id == eval_contract_id
        )
    ]
    return sorted(eval_results, key=lambda eval_result: eval_result.created_at, reverse=True)


@router.get("/api/projects/{project_id}/judge-outputs")
def list_judge_outputs(
    project_id: str,
    eval_result_id: Optional[str] = None,
) -> List[JudgeOutput]:
    get_project_or_404(project_id)
    return [
        j for j in _judge_outputs.values()
        if j.project_id == project_id
        and (eval_result_id is None or j.eval_result_id == eval_result_id)
    ]


@router.post("/api/projects/{project_id}/agent-designs/{agent_id}/runs", status_code=201)
def run_agent_design(
    project_id: str,
    agent_id: str,
    payload: AgentRunCreate,
) -> AgentRunResult:
    get_project_or_404(project_id)
    agent = get_agent_design_or_404(project_id, agent_id)
    if payload.target == "url":
        return call_website_for_agent(
            project_id=project_id,
            agent=agent,
            url=payload.url or payload.scenario_input,
        )

    prompt_refs = active_prompt_refs_for_run(
        project_id=project_id,
        agent=agent,
        version=None,
        contract_id=None,
    )
    runner_result, artifact, tool_artifacts, provider = run_agent_with_runner(
        project_id=project_id,
        agent=agent,
        instructions=agent.intent,
        scenario_input=payload.scenario_input,
        mode=payload.mode,
        provider=payload.provider,
        prompt_refs=prompt_refs,
    )
    artifact_ids = [artifact.id] + [tool_artifact.id for tool_artifact in tool_artifacts]
    trace_artifact: Optional[ArtifactRecord] = None
    if runner_result.trace_id and runner_result.trace_url:
        trace_artifact = create_runner_trace_artifact(
            project_id=project_id,
            agent_design_id=agent.id,
            provider="langfuse",
            trace_id=runner_result.trace_id,
            trace_url=runner_result.trace_url,
            run_id=runner_result.id,
            metadata={
                "runner_mode": runner_result.mode,
                "provider": provider,
                "ad_hoc": True,
                "prompt_refs": [ref.model_dump(mode="json") for ref in prompt_refs],
            },
            related_artifact_ids=artifact_ids,
            now=datetime.now(timezone.utc),
        )
        artifact_ids.append(trace_artifact.id)

    return AgentRunResult(
        id=runner_result.id,
        project_id=project_id,
        agent_design_id=agent.id,
        mode=runner_result.mode,
        scenario_input=runner_result.scenario_input,
        response=runner_result.response,
        tool_calls=[tool.model_dump(exclude_none=True) for tool in runner_result.tool_calls],
        evidence=runner_result.evidence,
        trace_id=runner_result.trace_id,
        trace_url=runner_result.trace_url,
        artifact=artifact,
        trace_artifact=trace_artifact,
        artifact_ids=artifact_ids,
        created_at=runner_result.created_at,
    )


@router.post("/api/projects/{project_id}/context-packs")
def build_context_pack(project_id: str, payload: ContextPackCreate) -> ContextPack:
    get_project_or_404(project_id)
    agent = _agent_designs.get(payload.agent_design_id) if payload.agent_design_id else None
    if payload.agent_design_id is not None and (
        agent is None or agent.project_id != project_id
    ):
        raise HTTPException(status_code=404, detail="Agent design not found.")

    purpose = payload.purpose.strip().upper()
    artifacts = assemble_context_pack_artifacts(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        purpose=purpose,
    )
    return ContextPack(
        id=f"context_{uuid4().hex[:12]}",
        project_id=project_id,
        purpose=purpose,
        agent_design_id=payload.agent_design_id,
        artifacts=artifacts,
        created_at=datetime.now(timezone.utc),
    )


@router.post("/api/projects/{project_id}/evidence-summaries", status_code=201)
def create_evidence_summary(
    project_id: str,
    payload: EvidenceSummaryCreate,
) -> EvidenceSummary:
    get_project_or_404(project_id)
    agent = _agent_designs.get(payload.agent_design_id) if payload.agent_design_id else None
    if payload.agent_design_id is not None and (
        agent is None or agent.project_id != project_id
    ):
        raise HTTPException(status_code=404, detail="Agent design not found.")

    purpose = payload.purpose.strip().upper()
    summary_type = payload.summary_type.strip().upper()
    artifacts = assemble_context_pack_artifacts(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        purpose=purpose,
    )
    cache_key = context_pack_cache_key(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        purpose=purpose,
        summary_type=summary_type,
        mode=payload.mode,
        artifacts=artifacts,
    )
    cached_summary = _evidence_summaries.get(cache_key)
    if cached_summary is not None:
        return cached_summary.model_copy(update={"cache_hit": True})

    provider = "platform"
    model = "deterministic-evidence-summary"
    token_usage: Dict[str, object] = {}
    cost_estimate: Optional[float] = None
    if payload.mode == "live":
        prompt = build_evidence_summary_prompt(
            purpose=purpose,
            summary_type=summary_type,
            artifacts=artifacts,
        )
        try:
            summary, model, token_usage = api_main.run_live_evidence_summary(prompt)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        provider = "anthropic"
        cost_estimate = estimate_live_judge_cost(token_usage)
    else:
        summary = build_deterministic_evidence_summary(
            purpose=purpose,
            artifacts=artifacts,
        )

    evidence_summary = EvidenceSummary(
        id=f"summary_{uuid4().hex[:12]}",
        project_id=project_id,
        purpose=purpose,
        agent_design_id=payload.agent_design_id,
        summary_type=summary_type,
        mode=payload.mode,
        provider=provider,
        model=model,
        summary=summary,
        supporting_artifact_ids=[artifact.id for artifact in artifacts],
        token_usage=token_usage,
        cost_estimate=cost_estimate,
        cache_key=cache_key,
        cache_hit=False,
        created_at=datetime.now(timezone.utc),
    )
    _evidence_summaries[cache_key] = evidence_summary
    store.save_record("evidence_summaries", cache_key, evidence_summary)
    return evidence_summary
