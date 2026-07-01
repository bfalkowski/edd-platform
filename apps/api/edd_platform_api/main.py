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
    run_anthropic_agent,
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


def find_review_item_for_langfuse_import(
    *,
    project_id: str,
    corpus_id: str,
    review_item_id: Optional[str],
    source_id: Optional[str],
    trace_id: Optional[str],
    observation_id: Optional[str],
) -> Optional[ReviewItem]:
    if review_item_id:
        item = _review_items.get(review_item_id)
        if item and item.project_id == project_id and item.corpus_id == corpus_id:
            return item
        return None
    for item in _review_items.values():
        if item.project_id != project_id or item.corpus_id != corpus_id:
            continue
        if source_id and item.source_id == source_id:
            return item
        if item.langfuse_ref is None:
            continue
        if trace_id and item.langfuse_ref.trace_id == trace_id:
            return item
        if observation_id and item.langfuse_ref.observation_id == observation_id:
            return item
    return None


def find_failure_mode_by_name(
    *,
    project_id: str,
    agent_design_id: str,
    name: str,
) -> Optional[FailureMode]:
    normalized_name = name.strip().lower()
    for failure_mode in _failure_modes.values():
        if (
            failure_mode.project_id == project_id
            and failure_mode.agent_design_id == agent_design_id
            and failure_mode.name.lower() == normalized_name
        ):
            return failure_mode
    return None


def review_item_search_text(item: ReviewItem) -> str:
    return " ".join(
        [
            item.title,
            item.content,
            json.dumps(item.metadata, sort_keys=True),
            json.dumps(item.langfuse_ref.model_dump(mode="json"), sort_keys=True)
            if item.langfuse_ref
            else "",
        ]
    ).lower()


def failure_mode_terms(failure_mode: FailureMode) -> List[str]:
    raw_terms = " ".join(
        [
            failure_mode.name.replace("_", " "),
            failure_mode.description,
            failure_mode.root_cause,
            failure_mode.langfuse_score_name or "",
        ]
    )
    terms = []
    for term in raw_terms.lower().replace("-", " ").split():
        normalized = term.strip(".,:;()[]{}")
        if len(normalized) >= 5 and normalized not in terms:
            terms.append(normalized)
    return terms[:8]


def review_sampling_plan_for_corpus(
    *,
    project_id: str,
    corpus: ReviewCorpus,
    create_suggestions: bool,
) -> ReviewSamplingPlan:
    items = sorted(
        [
            item
            for item in _review_items.values()
            if item.project_id == project_id and item.corpus_id == corpus.id
        ],
        key=lambda item: item.updated_at,
        reverse=True,
    )
    annotations = [
        annotation
        for annotation in _review_annotations.values()
        if annotation.project_id == project_id and annotation.corpus_id == corpus.id
    ]
    failure_modes = [
        failure_mode
        for failure_mode in _failure_modes.values()
        if failure_mode.project_id == project_id
        and failure_mode.agent_design_id == corpus.agent_design_id
    ]
    pending_suggestions = [
        suggestion
        for suggestion in _agent_suggestions.values()
        if suggestion.project_id == project_id
        and suggestion.corpus_id == corpus.id
        and suggestion.status == "pending"
    ]
    accepted_annotations = [
        annotation for annotation in annotations if annotation.status == "accepted"
    ]
    annotations_by_item: Dict[str, List[ReviewAnnotation]] = {}
    for annotation in annotations:
        annotations_by_item.setdefault(annotation.review_item_id, []).append(annotation)

    breadth_candidates: List[ReviewSamplingCandidate] = []
    for item in items:
        item_annotations = annotations_by_item.get(item.id, [])
        if item.status == "reviewed" and any(
            annotation.status == "accepted" for annotation in item_annotations
        ):
            continue
        reason = "Unreviewed item expands corpus breadth."
        score = 80
        if item.source_kind == "trace":
            reason = "Unreviewed trace keeps sampling from overfitting to saved EDD artifacts."
            score += 10
        if item.langfuse_ref and item.langfuse_ref.object_type == "OBSERVATION":
            reason = "Generation observation has direct model input/output for open coding."
            score += 10
        breadth_candidates.append(
            ReviewSamplingCandidate(
                review_item_id=item.id,
                title=item.title,
                reason=reason,
                source_kind=item.source_kind,
                status=item.status,
                score=score,
            )
        )
    breadth_candidates = sorted(
        breadth_candidates,
        key=lambda candidate: (-candidate.score, candidate.title.lower()),
    )[:5]

    depth_candidates: List[ReviewSamplingCandidate] = []
    recoding_prompts: List[ReviewSamplingCandidate] = []
    for failure_mode in failure_modes:
        terms = failure_mode_terms(failure_mode)
        if not terms:
            continue
        for item in items:
            item_annotations = annotations_by_item.get(item.id, [])
            has_mode = any(
                annotation.failure_mode_id == failure_mode.id
                for annotation in item_annotations
            )
            if has_mode:
                continue
            text = review_item_search_text(item)
            matched_terms = [term for term in terms if term in text]
            if matched_terms:
                depth_candidates.append(
                    ReviewSamplingCandidate(
                        review_item_id=item.id,
                        title=item.title,
                        reason=(
                            "Matches known failure-mode terms: "
                            + ", ".join(matched_terms[:3])
                        ),
                        source_kind=item.source_kind,
                        status=item.status,
                        failure_mode_id=failure_mode.id,
                        score=70 + min(len(matched_terms), 5) * 5,
                    )
                )
            if item_annotations and all(
                annotation.created_at < failure_mode.created_at
                for annotation in item_annotations
            ):
                recoding_prompts.append(
                    ReviewSamplingCandidate(
                        review_item_id=item.id,
                        title=item.title,
                        reason=f"Reviewed before failure mode {failure_mode.name} existed.",
                        source_kind=item.source_kind,
                        status=item.status,
                        failure_mode_id=failure_mode.id,
                        score=65,
                    )
                )
    depth_candidates = sorted(
        depth_candidates,
        key=lambda candidate: (-candidate.score, candidate.title.lower()),
    )[:5]
    recoding_prompts = sorted(
        recoding_prompts,
        key=lambda candidate: (-candidate.score, candidate.title.lower()),
    )[:5]

    generated_suggestions: List[AgentSuggestion] = []
    if create_suggestions:
        now = datetime.now(timezone.utc)
        suggestion_candidates = [*depth_candidates, *recoding_prompts]
        for candidate in suggestion_candidates[:5]:
            duplicate = any(
                suggestion.review_item_id == candidate.review_item_id
                and suggestion.failure_mode_id == candidate.failure_mode_id
                and suggestion.status == "pending"
                for suggestion in _agent_suggestions.values()
            )
            if duplicate:
                continue
            suggestion = AgentSuggestion(
                id=f"agent_suggestion_{uuid4().hex[:12]}",
                project_id=project_id,
                agent_design_id=corpus.agent_design_id,
                corpus_id=corpus.id,
                review_item_id=candidate.review_item_id,
                failure_mode_id=candidate.failure_mode_id,
                body=candidate.reason,
                quote="",
                span_start=None,
                span_end=None,
                rationale="Generated by deterministic breadth/depth review planning.",
                confidence=min(candidate.score / 100, 0.95),
                source="sampling-plan",
                status="pending",
                metadata={"candidate_type": "depth_or_recoding"},
                created_at=now,
                updated_at=now,
            )
            _agent_suggestions[suggestion.id] = suggestion
            store.save_record("agent_suggestions", suggestion.id, suggestion)
            generated_suggestions.append(suggestion)

    coverage = ReviewCoverageSummary(
        total_items=len(items),
        reviewed_items=len([item for item in items if item.status == "reviewed"]),
        unreviewed_items=len([item for item in items if item.status != "reviewed"]),
        accepted_annotations=len(accepted_annotations),
        failure_modes=len(failure_modes),
        pending_suggestions=len(pending_suggestions) + len(generated_suggestions),
    )
    rationale = (
        "Review breadth first when uncoded items remain; scan depth when known "
        "failure modes have likely matches; recode earlier notes when the taxonomy "
        "changed after they were reviewed."
    )
    return ReviewSamplingPlan(
        corpus_id=corpus.id,
        project_id=project_id,
        agent_design_id=corpus.agent_design_id,
        coverage=coverage,
        breadth_candidates=breadth_candidates,
        depth_candidates=depth_candidates,
        recoding_prompts=recoding_prompts,
        generated_suggestions=generated_suggestions,
        rationale=rationale,
    )


def review_corpus_analysis_for_corpus(
    *,
    project_id: str,
    corpus: ReviewCorpus,
) -> ReviewCorpusAnalysis:
    items = [
        item
        for item in _review_items.values()
        if item.project_id == project_id and item.corpus_id == corpus.id
    ]
    annotations = [
        annotation
        for annotation in _review_annotations.values()
        if annotation.project_id == project_id and annotation.corpus_id == corpus.id
    ]
    failure_modes = [
        failure_mode
        for failure_mode in _failure_modes.values()
        if failure_mode.project_id == project_id
        and failure_mode.agent_design_id == corpus.agent_design_id
    ]
    pending_suggestions = len(
        [
            suggestion
            for suggestion in _agent_suggestions.values()
            if suggestion.project_id == project_id
            and suggestion.corpus_id == corpus.id
            and suggestion.status == "pending"
        ]
    )
    snapshot_dir = analysis_snapshot_dir_for_corpus(project_id=project_id, corpus_id=corpus.id)
    snapshot_error = None
    if snapshot_dir is not None:
        try:
            materialize_review_corpus_snapshot(
                snapshot_dir=snapshot_dir,
                items=items,
                annotations=annotations,
                failure_modes=failure_modes,
            )
            snapshot_analysis = review_corpus_analysis_from_snapshot(
                project_id=project_id,
                corpus_id=corpus.id,
                agent_design_id=corpus.agent_design_id,
                pending_suggestions=pending_suggestions,
                snapshot_dir=snapshot_dir,
            )
            if snapshot_analysis is not None:
                return snapshot_analysis
        except Exception as exc:
            snapshot_error = AnalysisSnapshotMetadata(
                status="unavailable",
                directory=str(snapshot_dir),
                error=str(exc),
            )
    return review_corpus_analysis(
        project_id=project_id,
        corpus_id=corpus.id,
        agent_design_id=corpus.agent_design_id,
        items=items,
        annotations=annotations,
        failure_modes=failure_modes,
        pending_suggestions=pending_suggestions,
        snapshot=snapshot_error,
    )


def analysis_snapshot_dir_for_corpus(*, project_id: str, corpus_id: str) -> Optional[Path]:
    root = os.getenv("EDD_PLATFORM_ANALYSIS_SNAPSHOT_DIR")
    if not root:
        return None
    return Path(root) / "projects" / project_id / "review-corpora" / corpus_id


def discovery_evidence_artifacts(
    *,
    project_id: str,
    item: ReviewItem,
    failure_mode: Optional[FailureMode],
) -> List[str]:
    artifact_ids: List[str] = []
    if item.source_kind == "artifact":
        source_artifact = _artifacts.get(item.source_id)
        if source_artifact and source_artifact.project_id == project_id:
            artifact_ids.append(source_artifact.id)
    if failure_mode is not None:
        failure_mode_artifact = find_artifact_by_type_and_artifact_id(
            "FAILURE_MODE",
            failure_mode.id,
        )
        if failure_mode_artifact is not None:
            artifact_ids.append(failure_mode_artifact.id)
    return list(dict.fromkeys(artifact_ids))


def create_discovery_finding_artifact(
    *,
    project_id: str,
    annotation: ReviewAnnotation,
    item: ReviewItem,
    failure_mode: Optional[FailureMode],
    now: datetime,
) -> ArtifactRecord:
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="DISCOVERY_FINDING",
        artifact_id=annotation.id,
        title=f"Discovery finding: {item.title}",
        body=(
            f"Review item\n{item.title}\n\n"
            f"Finding\n{annotation.body}\n\n"
            f"Failure mode\n{failure_mode.name if failure_mode else 'None'}\n\n"
            f"Source\n{item.source_kind}: {item.source_id}"
        ),
        source="discovery-promotion",
        agent_design_id=item.agent_design_id,
        now=now,
    )
    for evidence_artifact_id in discovery_evidence_artifacts(
        project_id=project_id,
        item=item,
        failure_mode=failure_mode,
    ):
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=evidence_artifact_id,
            relationship_type="SUPPORTED_BY",
            now=now,
        )
    return artifact


def create_discovery_run_and_eval(
    *,
    project_id: str,
    annotation: ReviewAnnotation,
    item: ReviewItem,
    scenario: Scenario,
    contract: EvalContract,
    finding_artifact: ArtifactRecord,
    now: datetime,
) -> tuple[RunRecord, EvalResult]:
    run = RunRecord(
        id=f"run_discovery_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=item.agent_design_id,
        agent_version_id=None,
        scenario_id=scenario.id,
        eval_contract_id=contract.id,
        mode="discovery",
        provider=None,
        model=None,
        input=scenario.input,
        output=item.content or annotation.body,
        status="completed",
        artifact_ids=[],
        started_at=now,
        completed_at=now,
    )
    run_artifact = create_artifact(
        project_id=project_id,
        artifact_type="RUN_RESULT",
        artifact_id=run.id,
        title=f"Discovery replay seed: {item.title}",
        body=(
            f"Input\n{run.input}\n\n"
            f"Observed output\n{run.output}\n\n"
            f"Discovery finding\n{annotation.body}"
        ),
        source="discovery-promotion",
        agent_design_id=item.agent_design_id,
        now=now,
    )
    link_artifacts(
        project_id=project_id,
        source_artifact_id=run_artifact.id,
        target_artifact_id=finding_artifact.id,
        relationship_type="GENERATED_FROM",
        now=now,
    )
    run = run.model_copy(update={"artifact_ids": [run_artifact.id]})
    _runs[run.id] = run
    store.save_record("runs", run.id, run)

    check = EvalCheckResult(
        check_id=f"discovery_{annotation.id}",
        check_type="manual_review_required",
        passed=False,
        observed=annotation.body,
        expected=contract.expected_behavior[0] if contract.expected_behavior else "",
        evidence_artifact_ids=[finding_artifact.id, run_artifact.id],
        comment="Promoted from accepted discovery analysis.",
    )
    eval_result = EvalResult(
        id=f"eval_discovery_{uuid4().hex[:12]}",
        project_id=project_id,
        run_id=run.id,
        eval_contract_id=contract.id,
        judge_prompt_template_id=None,
        mode="discovery",
        score=0,
        passed=False,
        checks=[check],
        judge_output_ids=[],
        artifact_ids=[],
        created_at=now,
    )
    eval_artifact = create_artifact(
        project_id=project_id,
        artifact_type="EVAL_RESULT",
        artifact_id=eval_result.id,
        title=f"Discovery eval: {item.title}",
        body=(
            "Result\nFailed by accepted discovery finding.\n\n"
            f"Finding\n{annotation.body}\n\n"
            f"Contract\n{contract.name}"
        ),
        source="discovery-promotion",
        agent_design_id=item.agent_design_id,
        now=now,
    )
    link_artifacts(
        project_id=project_id,
        source_artifact_id=eval_artifact.id,
        target_artifact_id=run_artifact.id,
        relationship_type="GENERATED_FROM",
        now=now,
    )
    link_artifacts(
        project_id=project_id,
        source_artifact_id=eval_artifact.id,
        target_artifact_id=finding_artifact.id,
        relationship_type="SUPPORTED_BY",
        now=now,
    )
    eval_result = eval_result.model_copy(update={"artifact_ids": [eval_artifact.id]})
    _eval_results[eval_result.id] = eval_result
    store.save_record("eval_results", eval_result.id, eval_result)
    return run, eval_result


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


def langfuse_comment_sync_enabled() -> bool:
    return os.environ.get("EDD_PLATFORM_LANGFUSE_COMMENT_SYNC", "").strip().lower() == "live"


def langfuse_base_url() -> str:
    return (
        os.environ.get("LANGFUSE_HOST", "").strip()
        or os.environ.get("LANGFUSE_BASE_URL", "").strip()
        or "https://cloud.langfuse.com"
    ).rstrip("/")


def langfuse_basic_auth_header() -> str:
    credentials = (
        f"{os.environ.get('LANGFUSE_PUBLIC_KEY', '').strip()}:"
        f"{os.environ.get('LANGFUSE_SECRET_KEY', '').strip()}"
    )
    return "Basic " + b64encode(credentials.encode("utf-8")).decode("ascii")


def langfuse_comment_object_ref(target_artifact: ArtifactRecord) -> Optional[ExternalArtifactRef]:
    for ref in target_artifact.external_refs:
        if ref.provider == "langfuse" and ref.ref_type in {"trace", "prompt"}:
            return ref
    return None


def langfuse_comment_object_type(ref: ExternalArtifactRef) -> str:
    if ref.ref_type == "trace":
        return "TRACE"
    if ref.ref_type == "prompt":
        return "PROMPT"
    return ref.ref_type.upper()


def get_langfuse_comments(object_type: str, object_id: str) -> List[Dict[str, object]]:
    url = (
        f"{langfuse_base_url()}/api/public/comments"
        f"?objectType={object_type}&objectId={object_id}"
    )
    request = Request(
        url,
        headers={"Authorization": langfuse_basic_auth_header()},
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError):
        return []
    data = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, list):
        return []
    return data


def create_langfuse_comment(
    *,
    object_type: str,
    object_id: str,
    content: str,
) -> Dict[str, object]:
    request = Request(
        f"{langfuse_base_url()}/api/public/comments",
        data=json.dumps(
            {
                "objectType": object_type,
                "objectId": object_id,
                "content": content,
            }
        ).encode("utf-8"),
        headers={
            "Authorization": langfuse_basic_auth_header(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Langfuse comment request failed with status {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Langfuse comment request failed: {exc.reason}") from exc
    if not isinstance(payload, dict):
        return {}
    return payload


def sync_langfuse_comment_ref(
    *,
    target_artifact: ArtifactRecord,
    review_note_id: str,
    body: str,
) -> List[ExternalArtifactRef]:
    target_ref = langfuse_comment_object_ref(target_artifact)
    if target_ref is None:
        return []

    object_type = langfuse_comment_object_type(target_ref)
    metadata: Dict[str, object] = {
        "sync_requested": "live",
        "object_type": object_type,
        "object_id": target_ref.external_id,
        "review_note_id": review_note_id,
        "target_artifact_id": target_artifact.id,
    }
    planned_ref = ExternalArtifactRef(
        provider="langfuse",
        ref_type="comment",
        external_id=f"comment:{review_note_id}",
        label="Langfuse comment",
        metadata={**metadata, "sync_mode": "planned"},
    )
    if not langfuse_comment_sync_enabled():
        return []
    if not langfuse_credentials_configured():
        return [
            planned_ref.model_copy(
                update={"metadata": {**planned_ref.metadata, "sync_error": "missing_langfuse_credentials"}}
            )
        ]

    try:
        response = create_langfuse_comment(
            object_type=object_type,
            object_id=target_ref.external_id,
            content=body,
        )
    except Exception as exc:
        return [
            planned_ref.model_copy(
                update={"metadata": {**planned_ref.metadata, "sync_error": str(exc)}}
            )
        ]

    comment_id = str(response.get("id") or response.get("commentId") or f"comment:{review_note_id}")
    return [
        ExternalArtifactRef(
            provider="langfuse",
            ref_type="comment",
            external_id=comment_id,
            label="Langfuse comment",
            metadata={**metadata, "sync_mode": "live"},
        )
    ]



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


previous_sentiment_observer_intent = (
    "Monitor conversations, score sentiment, identify escalation risk, "
    "summarize emotional trajectory, and produce concise observer notes "
    "without taking over the conversation."
)
sentiment_observer_intent = (
    "Run as a long-running observer for conversations. Maintain a running "
    "model of the emotional arc, score sentiment and escalation movement, "
    "summarize trajectory changes, and produce concise observer notes "
    "that downstream APIs can use without taking over the conversation."
)

sentiment_observer_tools = [
    ToolDefinition(
        id="tool_score_conversation_sentiment",
        project_id=default_project.id,
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
        created_at=seeded_at,
        updated_at=seeded_at,
    ),
    ToolDefinition(
        id="tool_detect_escalation_risk",
        project_id=default_project.id,
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
        created_at=seeded_at,
        updated_at=seeded_at,
    ),
    ToolDefinition(
        id="tool_summarize_conversation_signals",
        project_id=default_project.id,
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
        created_at=seeded_at,
        updated_at=seeded_at,
    ),
]


def seed_sentiment_observer_defaults() -> None:
    now = seeded_at
    for tool in sentiment_observer_tools:
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

    tool_names = [tool.name for tool in sentiment_observer_tools]
    existing_agent = _agent_designs.get("agent_sentiment_observer")
    if existing_agent is None:
        agent = AgentDesign(
            id="agent_sentiment_observer",
            project_id=default_project.id,
            name="Sentiment Observer",
            intent=sentiment_observer_intent,
            status="designing",
            allowed_tool_names=tool_names,
            created_at=now,
            updated_at=now,
        )
    else:
        allowed_tool_names = list(dict.fromkeys(existing_agent.allowed_tool_names + tool_names))
        intent = (
            sentiment_observer_intent
            if existing_agent.intent == previous_sentiment_observer_intent
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


apartment_search_agent_intent = (
    "Find rental listings for a requested location and return a concrete list of homes or apartments. "
    "Use call_http_api first for simple pages. If the fetched page looks like a JavaScript app shell, "
    "use browse_webpage on the same URL to inspect visible listings. For Zillow-style searches, return "
    "listing name or address, visible rent, bedrooms when shown, and a source link. Do not mark the task "
    "complete with only a limitation explanation unless both static fetch and rendered page inspection fail."
)


def seed_apartment_search_agent_defaults() -> None:
    now = seeded_at
    tool_names = ["call_http_api", "browse_webpage"]
    existing_agent = _agent_designs.get("agent_apartment_search")
    if existing_agent is None:
        agent = AgentDesign(
            id="agent_apartment_search",
            project_id=default_project.id,
            name="Apartment Search Agent",
            intent=apartment_search_agent_intent,
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



@app.get("/api/projects/{project_id}/review-notes")
def list_review_notes(
    project_id: str,
    target_artifact_id: Optional[str] = None,
) -> List[ReviewNote]:
    get_project_or_404(project_id)
    review_notes = [
        review_note
        for review_note in _review_notes.values()
        if review_note.project_id == project_id
        and (
            target_artifact_id is None
            or review_note.target_artifact_id == target_artifact_id
        )
    ]
    return sorted(review_notes, key=lambda review_note: review_note.created_at, reverse=True)


@app.post("/api/projects/{project_id}/review-notes", status_code=201)
def create_review_note(
    project_id: str,
    payload: ReviewNoteCreate,
) -> ReviewNote:
    get_project_or_404(project_id)
    target_artifact = get_artifact_or_404(project_id, payload.target_artifact_id)
    now = datetime.now(timezone.utc)
    review_note_id = f"review_note_{uuid4().hex[:12]}"
    external_refs = sync_langfuse_comment_ref(
        target_artifact=target_artifact,
        review_note_id=review_note_id,
        body=payload.body.strip(),
    )
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="REVIEW_NOTE",
        artifact_id=review_note_id,
        title=f"Review note: {target_artifact.title}",
        body=(
            f"Author\n{payload.author.strip()}\n\n"
            f"Target artifact\n{target_artifact.id}\n\n"
            f"Note\n{payload.body.strip()}\n\n"
            f"Metadata\n{json.dumps(payload.metadata, sort_keys=True)}"
        ),
        source="review-note",
        agent_design_id=target_artifact.agent_design_id,
        now=now,
        external_refs=external_refs,
    )
    link_artifacts(
        project_id=project_id,
        source_artifact_id=artifact.id,
        target_artifact_id=target_artifact.id,
        relationship_type="COMMENTS_ON",
        now=now,
    )
    review_note = ReviewNote(
        id=review_note_id,
        project_id=project_id,
        target_artifact_id=target_artifact.id,
        body=payload.body.strip(),
        author=payload.author.strip(),
        metadata=payload.metadata,
        artifact_ids=[artifact.id],
        created_at=now,
    )
    _review_notes[review_note.id] = review_note
    store.save_record("review_notes", review_note.id, review_note)
    return review_note


@app.get("/api/projects/{project_id}/review-notes/{review_note_id}")
def get_review_note(project_id: str, review_note_id: str) -> ReviewNote:
    get_project_or_404(project_id)
    return get_review_note_or_404(project_id, review_note_id)


@app.get("/api/projects/{project_id}/review-corpora")
def list_review_corpora(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[ReviewCorpus]:
    get_project_or_404(project_id)
    corpora = [
        corpus
        for corpus in _review_corpora.values()
        if corpus.project_id == project_id
        and (agent_design_id is None or corpus.agent_design_id == agent_design_id)
    ]
    return sorted(corpora, key=lambda corpus: corpus.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/review-corpora", status_code=201)
def create_review_corpus(
    project_id: str,
    payload: ReviewCorpusCreate,
) -> ReviewCorpus:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, payload.agent_design_id)
    now = datetime.now(timezone.utc)
    corpus = ReviewCorpus(
        id=f"review_corpus_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        source=payload.source,
        langfuse_queue_id=payload.langfuse_queue_id,
        langfuse_score_config_ids=payload.langfuse_score_config_ids,
        status=payload.status.strip(),
        artifact_ids=[],
        created_at=now,
        updated_at=now,
    )
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="REVIEW_CORPUS",
        artifact_id=corpus.id,
        title=corpus.name,
        body=(
            f"Description\n{corpus.description or 'No description'}\n\n"
            f"Source\n{corpus.source}\n\n"
            f"Langfuse queue\n{corpus.langfuse_queue_id or 'None'}\n\n"
            f"Langfuse score configs\n"
            + "\n".join(f"- {score_id}" for score_id in corpus.langfuse_score_config_ids)
        ),
        source="review-corpus",
        agent_design_id=corpus.agent_design_id,
        now=now,
    )
    corpus = corpus.model_copy(update={"artifact_ids": [artifact.id]})
    _review_corpora[corpus.id] = corpus
    store.save_record("review_corpora", corpus.id, corpus)
    return corpus


@app.get("/api/projects/{project_id}/review-corpora/{corpus_id}")
def get_review_corpus(project_id: str, corpus_id: str) -> ReviewCorpus:
    get_project_or_404(project_id)
    return get_review_corpus_or_404(project_id, corpus_id)


@app.patch("/api/projects/{project_id}/review-corpora/{corpus_id}")
def update_review_corpus(
    project_id: str,
    corpus_id: str,
    payload: ReviewCorpusUpdate,
) -> ReviewCorpus:
    get_project_or_404(project_id)
    existing = get_review_corpus_or_404(project_id, corpus_id)
    updated = existing.model_copy(
        update={
            "name": payload.name.strip() if payload.name is not None else existing.name,
            "description": (
                payload.description.strip()
                if payload.description is not None
                else existing.description
            ),
            "langfuse_queue_id": (
                payload.langfuse_queue_id
                if payload.langfuse_queue_id is not None
                else existing.langfuse_queue_id
            ),
            "langfuse_score_config_ids": (
                payload.langfuse_score_config_ids
                if payload.langfuse_score_config_ids is not None
                else existing.langfuse_score_config_ids
            ),
            "status": payload.status.strip() if payload.status is not None else existing.status,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    _review_corpora[updated.id] = updated
    store.save_record("review_corpora", updated.id, updated)
    return updated


@app.get("/api/projects/{project_id}/review-corpora/{corpus_id}/sampling-plan")
def get_review_sampling_plan(
    project_id: str,
    corpus_id: str,
    create_suggestions: bool = False,
) -> ReviewSamplingPlan:
    get_project_or_404(project_id)
    corpus = get_review_corpus_or_404(project_id, corpus_id)
    return review_sampling_plan_for_corpus(
        project_id=project_id,
        corpus=corpus,
        create_suggestions=create_suggestions,
    )


@app.get("/api/projects/{project_id}/review-corpora/{corpus_id}/analysis")
def get_review_corpus_analysis(
    project_id: str,
    corpus_id: str,
) -> ReviewCorpusAnalysis:
    get_project_or_404(project_id)
    corpus = get_review_corpus_or_404(project_id, corpus_id)
    return review_corpus_analysis_for_corpus(project_id=project_id, corpus=corpus)


@app.post("/api/projects/{project_id}/review-corpora/{corpus_id}/sync-langfuse-comments")
def sync_langfuse_comments_to_corpus(
    project_id: str,
    corpus_id: str,
) -> LangfuseAnnotationsImportResult:
    if not langfuse_credentials_configured():
        raise HTTPException(status_code=400, detail="Langfuse credentials not configured.")
    get_project_or_404(project_id)
    corpus = get_review_corpus_or_404(project_id, corpus_id)
    items = [
        item
        for item in _review_items.values()
        if item.project_id == project_id and item.corpus_id == corpus_id
    ]
    existing_comment_ids: set[str] = set()
    for annotation in _review_annotations.values():
        if annotation.corpus_id == corpus_id:
            cid = annotation.metadata.get("langfuse_comment_id")
            if isinstance(cid, str):
                existing_comment_ids.add(cid)
    imported_annotations: List[ReviewAnnotation] = []
    skipped_count = 0
    now = datetime.now(timezone.utc)
    for item in items:
        ref = item.langfuse_ref
        if not ref or not ref.trace_id:
            skipped_count += 1
            continue
        comments = get_langfuse_comments("TRACE", ref.trace_id)
        for comment in comments:
            comment_id = str(comment.get("id") or "")
            if not comment_id or comment_id in existing_comment_ids:
                skipped_count += 1
                continue
            body = str(comment.get("content") or "").strip()
            if not body:
                skipped_count += 1
                continue
            author = str(comment.get("authorUserId") or "langfuse")
            annotation = ReviewAnnotation(
                id=f"review_annotation_{uuid4().hex[:12]}",
                project_id=project_id,
                agent_design_id=corpus.agent_design_id,
                corpus_id=corpus_id,
                review_item_id=item.id,
                body=body,
                quote="",
                span_start=None,
                span_end=None,
                author=author,
                failure_mode_id=None,
                suggestion_id=None,
                langfuse_score_id=None,
                status="accepted",
                metadata={
                    "langfuse_comment_id": comment_id,
                    "import_source": "langfuse_comment_sync",
                },
                created_at=now,
                updated_at=now,
            )
            _review_annotations[annotation.id] = annotation
            store.save_record("review_annotations", annotation.id, annotation)
            existing_comment_ids.add(comment_id)
            imported_annotations.append(annotation)
            updated_item = item.model_copy(update={"status": "reviewed", "updated_at": now})
            _review_items[updated_item.id] = updated_item
            store.save_record("review_items", updated_item.id, updated_item)
    return LangfuseAnnotationsImportResult(
        annotations=imported_annotations,
        failure_modes=[],
        imported_count=len(imported_annotations),
        skipped_count=skipped_count,
    )


@app.get("/api/projects/{project_id}/review-items")
def list_review_items(
    project_id: str,
    corpus_id: Optional[str] = None,
    agent_design_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[ReviewItem]:
    get_project_or_404(project_id)
    items = [
        item
        for item in _review_items.values()
        if item.project_id == project_id
        and (corpus_id is None or item.corpus_id == corpus_id)
        and (agent_design_id is None or item.agent_design_id == agent_design_id)
        and (status is None or item.status == status)
    ]
    return sorted(items, key=lambda item: item.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/review-items", status_code=201)
def create_review_item(project_id: str, payload: ReviewItemCreate) -> ReviewItem:
    get_project_or_404(project_id)
    corpus = get_review_corpus_or_404(project_id, payload.corpus_id)
    if payload.source_kind == "artifact":
        get_artifact_or_404(project_id, payload.source_id)
    elif payload.source_kind == "run":
        get_run_or_404(project_id, payload.source_id)
    elif payload.source_kind == "eval_result":
        get_eval_result_or_404(project_id, payload.source_id)
    elif payload.source_kind == "trace":
        if payload.langfuse_ref is None or not (
            payload.langfuse_ref.trace_id or payload.langfuse_ref.observation_id
        ):
            raise HTTPException(
                status_code=400,
                detail="Trace review items require a Langfuse trace or observation reference.",
            )
    now = datetime.now(timezone.utc)
    item = ReviewItem(
        id=f"review_item_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=corpus.agent_design_id,
        corpus_id=corpus.id,
        source_kind=payload.source_kind,
        source_id=payload.source_id,
        title=payload.title.strip(),
        content=payload.content,
        langfuse_ref=payload.langfuse_ref,
        metadata=payload.metadata,
        status=payload.status.strip(),
        created_at=now,
        updated_at=now,
    )
    _review_items[item.id] = item
    store.save_record("review_items", item.id, item)
    return item


@app.get("/api/projects/{project_id}/review-items/{review_item_id}")
def get_review_item(project_id: str, review_item_id: str) -> ReviewItem:
    get_project_or_404(project_id)
    return get_review_item_or_404(project_id, review_item_id)


@app.patch("/api/projects/{project_id}/review-items/{review_item_id}")
def update_review_item(
    project_id: str,
    review_item_id: str,
    payload: ReviewItemUpdate,
) -> ReviewItem:
    get_project_or_404(project_id)
    existing = get_review_item_or_404(project_id, review_item_id)
    updated = existing.model_copy(
        update={
            "title": payload.title.strip() if payload.title is not None else existing.title,
            "content": payload.content if payload.content is not None else existing.content,
            "metadata": payload.metadata if payload.metadata is not None else existing.metadata,
            "status": payload.status.strip() if payload.status is not None else existing.status,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    _review_items[updated.id] = updated
    store.save_record("review_items", updated.id, updated)
    return updated


@app.post(
    "/api/projects/{project_id}/review-corpora/{corpus_id}/langfuse-items",
    status_code=201,
)
def import_langfuse_review_items(
    project_id: str,
    corpus_id: str,
    payload: LangfuseReviewItemsImportCreate,
) -> LangfuseReviewItemsImportResult:
    get_project_or_404(project_id)
    corpus = get_review_corpus_or_404(project_id, corpus_id)
    imported: List[ReviewItem] = []
    skipped_count = 0
    now = datetime.now(timezone.utc)
    for item_payload in payload.items:
        if not (item_payload.trace_id or item_payload.observation_id):
            skipped_count += 1
            continue
        existing = find_review_item_for_langfuse_import(
            project_id=project_id,
            corpus_id=corpus.id,
            review_item_id=None,
            source_id=item_payload.source_id,
            trace_id=item_payload.trace_id,
            observation_id=item_payload.observation_id,
        )
        if existing is not None:
            skipped_count += 1
            continue
        item = ReviewItem(
            id=f"review_item_{uuid4().hex[:12]}",
            project_id=project_id,
            agent_design_id=corpus.agent_design_id,
            corpus_id=corpus.id,
            source_kind="trace",
            source_id=item_payload.source_id,
            title=item_payload.title.strip(),
            content=item_payload.content,
            langfuse_ref={
                "trace_id": item_payload.trace_id,
                "observation_id": item_payload.observation_id,
                "object_type": item_payload.object_type,
                "url": item_payload.url,
                "queue_id": item_payload.queue_id or corpus.langfuse_queue_id,
                "score_ids": item_payload.score_ids,
                "metadata": item_payload.metadata,
            },
            metadata={
                **item_payload.metadata,
                "import_source": "langfuse",
                "langfuse_queue_id": item_payload.queue_id or corpus.langfuse_queue_id,
            },
            status="unreviewed",
            created_at=now,
            updated_at=now,
        )
        _review_items[item.id] = item
        store.save_record("review_items", item.id, item)
        imported.append(item)
    return LangfuseReviewItemsImportResult(
        review_items=imported,
        imported_count=len(imported),
        skipped_count=skipped_count,
    )


@app.post(
    "/api/projects/{project_id}/review-corpora/{corpus_id}/langfuse-annotations",
    status_code=201,
)
def import_langfuse_review_annotations(
    project_id: str,
    corpus_id: str,
    payload: LangfuseAnnotationsImportCreate,
) -> LangfuseAnnotationsImportResult:
    get_project_or_404(project_id)
    corpus = get_review_corpus_or_404(project_id, corpus_id)
    imported_annotations: List[ReviewAnnotation] = []
    imported_failure_modes: Dict[str, FailureMode] = {}
    skipped_count = 0
    now = datetime.now(timezone.utc)
    for annotation_payload in payload.annotations:
        item = find_review_item_for_langfuse_import(
            project_id=project_id,
            corpus_id=corpus.id,
            review_item_id=annotation_payload.review_item_id,
            source_id=annotation_payload.source_id,
            trace_id=annotation_payload.trace_id,
            observation_id=annotation_payload.observation_id,
        )
        if item is None:
            skipped_count += 1
            continue

        failure_mode_id: Optional[str] = None
        failure_mode_name = (annotation_payload.failure_mode_name or "").strip()
        if failure_mode_name:
            failure_mode = find_failure_mode_by_name(
                project_id=project_id,
                agent_design_id=corpus.agent_design_id,
                name=failure_mode_name,
            )
            if failure_mode is None:
                failure_mode = FailureMode(
                    id=f"failure_mode_{uuid4().hex[:12]}",
                    project_id=project_id,
                    agent_design_id=corpus.agent_design_id,
                    name=failure_mode_name,
                    description=(
                        annotation_payload.failure_mode_description.strip()
                        or f"Imported from Langfuse open-coding label {failure_mode_name}."
                    ),
                    root_cause="",
                    severity="medium",
                    status="candidate",
                    langfuse_score_name=failure_mode_name,
                    example_annotation_ids=[],
                    created_at=now,
                    updated_at=now,
                )
                _failure_modes[failure_mode.id] = failure_mode
                store.save_record("failure_modes", failure_mode.id, failure_mode)
                create_artifact(
                    project_id=project_id,
                    artifact_type="FAILURE_MODE",
                    artifact_id=failure_mode.id,
                    title=failure_mode.name,
                    body=(
                        f"Definition\n{failure_mode.description}\n\n"
                        "Root cause\nNeeds analysis\n\n"
                        f"Langfuse score\n{failure_mode.langfuse_score_name or 'None'}"
                    ),
                    source="langfuse-error-analysis",
                    agent_design_id=failure_mode.agent_design_id,
                    now=now,
                )
                imported_failure_modes[failure_mode.id] = failure_mode
            failure_mode_id = failure_mode.id

        annotation = ReviewAnnotation(
            id=f"review_annotation_{uuid4().hex[:12]}",
            project_id=project_id,
            agent_design_id=corpus.agent_design_id,
            corpus_id=corpus.id,
            review_item_id=item.id,
            body=annotation_payload.open_coding.strip(),
            quote="",
            span_start=None,
            span_end=None,
            author="human",
            failure_mode_id=failure_mode_id,
            suggestion_id=None,
            langfuse_score_id=annotation_payload.langfuse_score_id,
            status="accepted",
            metadata={
                **annotation_payload.metadata,
                "import_source": "langfuse",
                "pass_fail": annotation_payload.pass_fail,
            },
            created_at=now,
            updated_at=now,
        )
        _review_annotations[annotation.id] = annotation
        store.save_record("review_annotations", annotation.id, annotation)
        imported_annotations.append(annotation)

        item_status = "reviewed" if annotation_payload.pass_fail != "unknown" else item.status
        updated_item = item.model_copy(update={"status": item_status, "updated_at": now})
        _review_items[updated_item.id] = updated_item
        store.save_record("review_items", updated_item.id, updated_item)

    return LangfuseAnnotationsImportResult(
        annotations=imported_annotations,
        failure_modes=list(imported_failure_modes.values()),
        imported_count=len(imported_annotations),
        skipped_count=skipped_count,
    )


@app.get("/api/projects/{project_id}/failure-modes")
def list_failure_modes(
    project_id: str,
    agent_design_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[FailureMode]:
    get_project_or_404(project_id)
    failure_modes = [
        failure_mode
        for failure_mode in _failure_modes.values()
        if failure_mode.project_id == project_id
        and (agent_design_id is None or failure_mode.agent_design_id == agent_design_id)
        and (status is None or failure_mode.status == status)
    ]
    return sorted(failure_modes, key=lambda failure_mode: failure_mode.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/failure-modes", status_code=201)
def create_failure_mode(
    project_id: str,
    payload: FailureModeCreate,
) -> FailureMode:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, payload.agent_design_id)
    for annotation_id in payload.example_annotation_ids:
        annotation = get_review_annotation_or_404(project_id, annotation_id)
        if annotation.agent_design_id != payload.agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Failure mode examples must belong to the same agent design.",
            )
    now = datetime.now(timezone.utc)
    failure_mode = FailureMode(
        id=f"failure_mode_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        root_cause=payload.root_cause.strip(),
        severity=payload.severity.strip(),
        status=payload.status.strip(),
        langfuse_score_name=payload.langfuse_score_name,
        example_annotation_ids=payload.example_annotation_ids,
        created_at=now,
        updated_at=now,
    )
    create_artifact(
        project_id=project_id,
        artifact_type="FAILURE_MODE",
        artifact_id=failure_mode.id,
        title=failure_mode.name,
        body=(
            f"Definition\n{failure_mode.description}\n\n"
            f"Root cause\n{failure_mode.root_cause or 'Needs analysis'}\n\n"
            f"Langfuse score\n{failure_mode.langfuse_score_name or 'None'}"
        ),
        source="failure-mode",
        agent_design_id=failure_mode.agent_design_id,
        now=now,
    )
    _failure_modes[failure_mode.id] = failure_mode
    store.save_record("failure_modes", failure_mode.id, failure_mode)
    return failure_mode


@app.get("/api/projects/{project_id}/failure-modes/{failure_mode_id}")
def get_failure_mode(project_id: str, failure_mode_id: str) -> FailureMode:
    get_project_or_404(project_id)
    return get_failure_mode_or_404(project_id, failure_mode_id)


@app.patch("/api/projects/{project_id}/failure-modes/{failure_mode_id}")
def update_failure_mode(
    project_id: str,
    failure_mode_id: str,
    payload: FailureModeUpdate,
) -> FailureMode:
    get_project_or_404(project_id)
    existing = get_failure_mode_or_404(project_id, failure_mode_id)
    example_annotation_ids = (
        payload.example_annotation_ids
        if payload.example_annotation_ids is not None
        else existing.example_annotation_ids
    )
    for annotation_id in example_annotation_ids:
        annotation = get_review_annotation_or_404(project_id, annotation_id)
        if annotation.agent_design_id != existing.agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Failure mode examples must belong to the same agent design.",
            )
    updated = existing.model_copy(
        update={
            "name": payload.name.strip() if payload.name is not None else existing.name,
            "description": (
                payload.description.strip()
                if payload.description is not None
                else existing.description
            ),
            "root_cause": (
                payload.root_cause.strip()
                if payload.root_cause is not None
                else existing.root_cause
            ),
            "severity": (
                payload.severity.strip() if payload.severity is not None else existing.severity
            ),
            "status": payload.status.strip() if payload.status is not None else existing.status,
            "langfuse_score_name": (
                payload.langfuse_score_name
                if payload.langfuse_score_name is not None
                else existing.langfuse_score_name
            ),
            "example_annotation_ids": example_annotation_ids,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    _failure_modes[updated.id] = updated
    store.save_record("failure_modes", updated.id, updated)
    return updated


@app.get("/api/projects/{project_id}/review-annotations")
def list_review_annotations(
    project_id: str,
    corpus_id: Optional[str] = None,
    review_item_id: Optional[str] = None,
    failure_mode_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[ReviewAnnotation]:
    get_project_or_404(project_id)
    annotations = [
        annotation
        for annotation in _review_annotations.values()
        if annotation.project_id == project_id
        and (corpus_id is None or annotation.corpus_id == corpus_id)
        and (review_item_id is None or annotation.review_item_id == review_item_id)
        and (failure_mode_id is None or annotation.failure_mode_id == failure_mode_id)
        and (status is None or annotation.status == status)
    ]
    return sorted(annotations, key=lambda annotation: annotation.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/review-annotations", status_code=201)
def create_review_annotation(
    project_id: str,
    payload: ReviewAnnotationCreate,
) -> ReviewAnnotation:
    get_project_or_404(project_id)
    item = get_review_item_or_404(project_id, payload.review_item_id)
    if payload.failure_mode_id is not None:
        failure_mode = get_failure_mode_or_404(project_id, payload.failure_mode_id)
        if failure_mode.agent_design_id != item.agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Failure mode must belong to the same agent design as the review item.",
            )
    if payload.suggestion_id is not None:
        suggestion = get_agent_suggestion_or_404(project_id, payload.suggestion_id)
        if suggestion.review_item_id != item.id:
            raise HTTPException(
                status_code=400,
                detail="Suggestion must belong to the same review item as the annotation.",
            )
    now = datetime.now(timezone.utc)
    annotation = ReviewAnnotation(
        id=f"review_annotation_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=item.agent_design_id,
        corpus_id=item.corpus_id,
        review_item_id=item.id,
        body=payload.body.strip(),
        quote=payload.quote,
        span_start=payload.span_start,
        span_end=payload.span_end,
        author=payload.author,
        failure_mode_id=payload.failure_mode_id,
        suggestion_id=payload.suggestion_id,
        langfuse_score_id=payload.langfuse_score_id,
        status=payload.status,
        metadata=payload.metadata,
        created_at=now,
        updated_at=now,
    )
    _review_annotations[annotation.id] = annotation
    store.save_record("review_annotations", annotation.id, annotation)
    return annotation


@app.get("/api/projects/{project_id}/review-annotations/{annotation_id}")
def get_review_annotation(project_id: str, annotation_id: str) -> ReviewAnnotation:
    get_project_or_404(project_id)
    return get_review_annotation_or_404(project_id, annotation_id)


@app.post(
    "/api/projects/{project_id}/review-annotations/{annotation_id}/promote",
    status_code=201,
)
def promote_review_annotation(
    project_id: str,
    annotation_id: str,
    payload: DiscoveryPromotionCreate,
) -> DiscoveryPromotionResult:
    get_project_or_404(project_id)
    annotation = get_review_annotation_or_404(project_id, annotation_id)
    if annotation.status != "accepted":
        raise HTTPException(
            status_code=400,
            detail="Only accepted review annotations can be promoted.",
        )
    item = get_review_item_or_404(project_id, annotation.review_item_id)
    failure_mode = (
        get_failure_mode_or_404(project_id, annotation.failure_mode_id)
        if annotation.failure_mode_id
        else None
    )
    now = datetime.now(timezone.utc)
    finding_artifact = create_discovery_finding_artifact(
        project_id=project_id,
        annotation=annotation,
        item=item,
        failure_mode=failure_mode,
        now=now,
    )

    scenario: Optional[Scenario] = None
    contract: Optional[EvalContract] = None
    failure_packet: Optional[FailurePacket] = None
    artifact_ids = [finding_artifact.id]
    if payload.create_eval_case or payload.create_failure_packet:
        scenario = _scenarios_router.create_scenario(
            project_id,
            ScenarioCreate(
                agent_design_id=item.agent_design_id,
                name=f"Discovery case: {item.title}",
                input=item.content or annotation.body,
                setup_context=(
                    f"Promoted from review item {item.id} in corpus {item.corpus_id}.\n\n"
                    f"Original source: {item.source_kind} {item.source_id}."
                ),
                fixture_refs=[finding_artifact.id],
                status="active",
            ),
        )
        scenario_artifact = find_artifact_by_type_and_artifact_id("SCENARIO", scenario.id)
        if scenario_artifact is not None:
            artifact_ids.append(scenario_artifact.id)
            link_artifacts(
                project_id=project_id,
                source_artifact_id=scenario_artifact.id,
                target_artifact_id=finding_artifact.id,
                relationship_type="GENERATED_FROM",
                now=now,
            )
        expected_behavior = (
            failure_mode.description
            if failure_mode is not None
            else "Avoid the behavior described by the accepted discovery finding."
        )
        contract = _eval_contracts_router.create_eval_contract(
            project_id,
            EvalContractCreate(
                agent_design_id=item.agent_design_id,
                name=(
                    f"Discovery contract: {failure_mode.name}"
                    if failure_mode is not None
                    else f"Discovery contract: {item.title}"
                ),
                description=annotation.body,
                scenario_id=scenario.id,
                expected_behavior=[expected_behavior],
                required_evidence=["Accepted discovery finding"],
                forbidden_behavior=[annotation.body],
                checks=[
                    {
                        "id": f"avoid_{failure_mode.name if failure_mode else 'discovery_failure'}",
                        "type": "manual_review_required",
                        "value": annotation.body,
                    }
                ],
                status="active",
            ),
        )
        contract_artifact = find_artifact_by_type_and_artifact_id(
            "EVAL_CONTRACT",
            contract.id,
        )
        if contract_artifact is not None:
            artifact_ids.append(contract_artifact.id)
            link_artifacts(
                project_id=project_id,
                source_artifact_id=contract_artifact.id,
                target_artifact_id=finding_artifact.id,
                relationship_type="GENERATED_FROM",
                now=now,
            )
        if payload.create_failure_packet:
            run, eval_result = create_discovery_run_and_eval(
                project_id=project_id,
                annotation=annotation,
                item=item,
                scenario=scenario,
                contract=contract,
                finding_artifact=finding_artifact,
                now=now,
            )
            artifact_ids.extend(run.artifact_ids)
            artifact_ids.extend(eval_result.artifact_ids)
            failure_packet = create_failure_packet_record(
                project_id=project_id,
                agent_design_id=item.agent_design_id,
                agent_version_id=None,
                run_id=run.id,
                eval_result_id=eval_result.id,
                eval_contract_id=contract.id,
                failed_check_ids=[f"discovery_{annotation.id}"],
                title=(
                    f"Discovery failure: {failure_mode.name}"
                    if failure_mode is not None
                    else f"Discovery failure: {item.title}"
                ),
                diagnosis=annotation.body,
                severity=failure_mode.severity if failure_mode is not None else "medium",
                evidence_artifact_ids=[finding_artifact.id, *eval_result.artifact_ids],
                recommended_fix=(
                    "Create a bounded fix and validate it against the promoted discovery contract."
                ),
                status=payload.failure_packet_status.strip(),
                now=now,
            )
            failure_artifact = find_artifact_by_type_and_artifact_id(
                "FAILURE_PACKET",
                failure_packet.id,
            )
            if failure_artifact is not None:
                artifact_ids.append(failure_artifact.id)
                link_artifacts(
                    project_id=project_id,
                    source_artifact_id=failure_artifact.id,
                    target_artifact_id=finding_artifact.id,
                    relationship_type="GENERATED_FROM",
                    now=now,
                )

    return DiscoveryPromotionResult(
        annotation=annotation,
        review_item=item,
        failure_mode=failure_mode,
        scenario=scenario,
        eval_contract=contract,
        failure_packet=failure_packet,
        artifact_ids=list(dict.fromkeys(artifact_ids)),
    )


@app.patch("/api/projects/{project_id}/review-annotations/{annotation_id}")
def update_review_annotation(
    project_id: str,
    annotation_id: str,
    payload: ReviewAnnotationUpdate,
) -> ReviewAnnotation:
    get_project_or_404(project_id)
    existing = get_review_annotation_or_404(project_id, annotation_id)
    if payload.failure_mode_id is not None:
        failure_mode = get_failure_mode_or_404(project_id, payload.failure_mode_id)
        if failure_mode.agent_design_id != existing.agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Failure mode must belong to the same agent design as the annotation.",
            )
    updated = existing.model_copy(
        update={
            "body": payload.body.strip() if payload.body is not None else existing.body,
            "quote": payload.quote if payload.quote is not None else existing.quote,
            "span_start": payload.span_start if payload.span_start is not None else existing.span_start,
            "span_end": payload.span_end if payload.span_end is not None else existing.span_end,
            "failure_mode_id": (
                payload.failure_mode_id
                if payload.failure_mode_id is not None
                else existing.failure_mode_id
            ),
            "langfuse_score_id": (
                payload.langfuse_score_id
                if payload.langfuse_score_id is not None
                else existing.langfuse_score_id
            ),
            "status": payload.status if payload.status is not None else existing.status,
            "metadata": payload.metadata if payload.metadata is not None else existing.metadata,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    _review_annotations[updated.id] = updated
    store.save_record("review_annotations", updated.id, updated)
    return updated


@app.get("/api/projects/{project_id}/agent-suggestions")
def list_agent_suggestions(
    project_id: str,
    corpus_id: Optional[str] = None,
    review_item_id: Optional[str] = None,
    failure_mode_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[AgentSuggestion]:
    get_project_or_404(project_id)
    suggestions = [
        suggestion
        for suggestion in _agent_suggestions.values()
        if suggestion.project_id == project_id
        and (corpus_id is None or suggestion.corpus_id == corpus_id)
        and (review_item_id is None or suggestion.review_item_id == review_item_id)
        and (failure_mode_id is None or suggestion.failure_mode_id == failure_mode_id)
        and (status is None or suggestion.status == status)
    ]
    return sorted(suggestions, key=lambda suggestion: suggestion.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/agent-suggestions", status_code=201)
def create_agent_suggestion(
    project_id: str,
    payload: AgentSuggestionCreate,
) -> AgentSuggestion:
    get_project_or_404(project_id)
    item = get_review_item_or_404(project_id, payload.review_item_id)
    if payload.failure_mode_id is not None:
        failure_mode = get_failure_mode_or_404(project_id, payload.failure_mode_id)
        if failure_mode.agent_design_id != item.agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Failure mode must belong to the same agent design as the review item.",
            )
    now = datetime.now(timezone.utc)
    suggestion = AgentSuggestion(
        id=f"agent_suggestion_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=item.agent_design_id,
        corpus_id=item.corpus_id,
        review_item_id=item.id,
        failure_mode_id=payload.failure_mode_id,
        body=payload.body.strip(),
        quote=payload.quote,
        span_start=payload.span_start,
        span_end=payload.span_end,
        rationale=payload.rationale.strip(),
        confidence=payload.confidence,
        source=payload.source.strip(),
        status=payload.status,
        metadata=payload.metadata,
        created_at=now,
        updated_at=now,
    )
    _agent_suggestions[suggestion.id] = suggestion
    store.save_record("agent_suggestions", suggestion.id, suggestion)
    return suggestion


@app.get("/api/projects/{project_id}/agent-suggestions/{suggestion_id}")
def get_agent_suggestion(project_id: str, suggestion_id: str) -> AgentSuggestion:
    get_project_or_404(project_id)
    return get_agent_suggestion_or_404(project_id, suggestion_id)


@app.patch("/api/projects/{project_id}/agent-suggestions/{suggestion_id}")
def update_agent_suggestion(
    project_id: str,
    suggestion_id: str,
    payload: AgentSuggestionUpdate,
) -> AgentSuggestion:
    get_project_or_404(project_id)
    existing = get_agent_suggestion_or_404(project_id, suggestion_id)
    if payload.failure_mode_id is not None:
        failure_mode = get_failure_mode_or_404(project_id, payload.failure_mode_id)
        if failure_mode.agent_design_id != existing.agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Failure mode must belong to the same agent design as the suggestion.",
            )
    updated = existing.model_copy(
        update={
            "failure_mode_id": (
                payload.failure_mode_id
                if payload.failure_mode_id is not None
                else existing.failure_mode_id
            ),
            "body": payload.body.strip() if payload.body is not None else existing.body,
            "quote": payload.quote if payload.quote is not None else existing.quote,
            "span_start": payload.span_start if payload.span_start is not None else existing.span_start,
            "span_end": payload.span_end if payload.span_end is not None else existing.span_end,
            "rationale": (
                payload.rationale.strip()
                if payload.rationale is not None
                else existing.rationale
            ),
            "confidence": payload.confidence if payload.confidence is not None else existing.confidence,
            "status": payload.status if payload.status is not None else existing.status,
            "metadata": payload.metadata if payload.metadata is not None else existing.metadata,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    _agent_suggestions[updated.id] = updated
    store.save_record("agent_suggestions", updated.id, updated)
    return updated




