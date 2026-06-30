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
    AnthropicRunnerConfig,
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


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/services", response_model=ServiceStatusResponse)
def get_service_status() -> ServiceStatusResponse:
    return service_status_response()


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


def planned_langfuse_scenario_refs(
    *,
    project_id: str,
    scenario: Scenario,
    metadata: Optional[Dict[str, object]] = None,
) -> List[ExternalArtifactRef]:
    base_metadata: Dict[str, object] = {"sync_mode": "planned"}
    if metadata is not None:
        base_metadata.update(metadata)
    return [
        ExternalArtifactRef(
            provider="langfuse",
            ref_type="dataset",
            external_id=f"dataset:{project_id}:{scenario.agent_design_id}",
            label="Langfuse dataset",
            metadata=base_metadata,
        ),
        ExternalArtifactRef(
            provider="langfuse",
            ref_type="dataset_item",
            external_id=f"dataset_item:{scenario.id}",
            label="Langfuse dataset item",
            metadata=base_metadata,
        ),
    ]


def langfuse_dataset_sync_enabled() -> bool:
    return os.environ.get("EDD_PLATFORM_LANGFUSE_DATASET_SYNC", "").strip().lower() == "live"


def langfuse_credentials_configured() -> bool:
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
        and os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    )


def object_field(value: object, field_name: str, fallback: str) -> str:
    field_value = getattr(value, field_name, None)
    if field_value is None and isinstance(value, dict):
        field_value = value.get(field_name)
    return str(field_value or fallback)


def sync_langfuse_scenario_dataset_refs(
    *,
    project_id: str,
    scenario: Scenario,
) -> List[ExternalArtifactRef]:
    if not langfuse_dataset_sync_enabled():
        return planned_langfuse_scenario_refs(project_id=project_id, scenario=scenario)
    if not langfuse_credentials_configured():
        return planned_langfuse_scenario_refs(
            project_id=project_id,
            scenario=scenario,
            metadata={"sync_requested": "live", "sync_error": "missing_langfuse_credentials"},
        )

    dataset_name = f"edd:{project_id}:{scenario.agent_design_id}:scenarios"
    dataset_metadata: Dict[str, object] = {
        "project_id": project_id,
        "agent_design_id": scenario.agent_design_id,
        "source": "edd-platform",
    }
    item_metadata: Dict[str, object] = {
        **dataset_metadata,
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "setup_context": scenario.setup_context,
        "fixture_refs": scenario.fixture_refs,
        "default_eval_contract_id": scenario.default_eval_contract_id,
    }
    try:
        langfuse = get_langfuse_client()
        dataset = langfuse.create_dataset(
            name=dataset_name,
            description=f"EDD scenarios for agent design {scenario.agent_design_id}.",
            metadata=dataset_metadata,
        )
        dataset_item = langfuse.create_dataset_item(
            dataset_name=dataset_name,
            input=scenario.input,
            expected_output=None,
            metadata=item_metadata,
            id=scenario.id,
        )
    except Exception as exc:
        return planned_langfuse_scenario_refs(
            project_id=project_id,
            scenario=scenario,
            metadata={"sync_requested": "live", "sync_error": str(exc)},
        )

    return [
        ExternalArtifactRef(
            provider="langfuse",
            ref_type="dataset",
            external_id=object_field(dataset, "id", dataset_name),
            label="Langfuse dataset",
            metadata={
                **dataset_metadata,
                "sync_mode": "live",
                "dataset_name": dataset_name,
            },
        ),
        ExternalArtifactRef(
            provider="langfuse",
            ref_type="dataset_item",
            external_id=object_field(dataset_item, "id", scenario.id),
            label="Langfuse dataset item",
            metadata={
                **item_metadata,
                "sync_mode": "live",
                "dataset_name": dataset_name,
            },
        ),
    ]


def langfuse_score_sync_enabled() -> bool:
    return os.environ.get("EDD_PLATFORM_LANGFUSE_SCORE_SYNC", "").strip().lower() == "live"


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


def find_langfuse_trace_ref_for_run(project_id: str, run_id: str) -> Optional[TraceRef]:
    trace_refs = [
        trace_ref
        for trace_ref in _trace_refs.values()
        if trace_ref.project_id == project_id
        and trace_ref.run_id == run_id
        and trace_ref.provider == "langfuse"
    ]
    return sorted(trace_refs, key=lambda trace_ref: trace_ref.created_at, reverse=True)[0] if trace_refs else None


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
    if not langfuse_credentials_configured():
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
        langfuse = get_langfuse_client()
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
        call_artifact = create_artifact(
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
        link_artifacts(
            project_id=project_id,
            source_artifact_id=call_artifact.id,
            target_artifact_id=run_artifact.id,
            relationship_type="GENERATED_FROM",
            now=now,
        )
        result_artifact = create_artifact(
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
        link_artifacts(
            project_id=project_id,
            source_artifact_id=result_artifact.id,
            target_artifact_id=call_artifact.id,
            relationship_type="GENERATED_FROM",
            now=now,
        )
        artifacts.extend([call_artifact, result_artifact])
    return artifacts


def artifacts_for_agent_by_type(
    *,
    project_id: str,
    agent_design_id: str,
    artifact_type: str,
) -> List[ArtifactRecord]:
    return [
        artifact
        for artifact in _artifacts.values()
        if artifact.project_id == project_id
        and artifact.agent_design_id == agent_design_id
        and artifact.artifact_type == artifact_type
    ]


def create_gate_decision_record(
    *,
    project_id: str,
    gate: GateDefinition,
    payload: GateDecisionCreate,
    now: datetime,
) -> GateDecision:
    evidence_artifact_ids: List[str] = []
    missing_artifact_types: List[str] = []
    for artifact_type in gate.required_artifact_types:
        matching_artifacts = artifacts_for_agent_by_type(
            project_id=project_id,
            agent_design_id=gate.agent_design_id,
            artifact_type=artifact_type,
        )
        if matching_artifacts:
            evidence_artifact_ids.extend(artifact.id for artifact in matching_artifacts)
        else:
            missing_artifact_types.append(artifact_type)

    if payload.eval_result_id is not None:
        eval_result = get_eval_result_or_404(project_id, payload.eval_result_id)
        if eval_result.run_id:
            run = get_run_or_404(project_id, eval_result.run_id)
            if run.agent_design_id != gate.agent_design_id:
                raise HTTPException(
                    status_code=400,
                    detail="Gate decision eval result must belong to the same agent design.",
                )
        evidence_artifact_ids.extend(eval_result.artifact_ids)

    if payload.comparison_id is not None:
        comparison = get_comparison_or_404(project_id, payload.comparison_id)
        if comparison.agent_design_id != gate.agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Gate decision comparison must belong to the same agent design.",
            )
        evidence_artifact_ids.extend(comparison.artifact_ids)

    blocking_failure_packet_ids = [
        failure.id
        for failure in _failure_packets.values()
        if failure.project_id == project_id
        and failure.agent_design_id == gate.agent_design_id
        and failure.status in gate.blocking_failure_statuses
    ]
    for failure_id in blocking_failure_packet_ids:
        failure_artifact = find_artifact_by_type_and_artifact_id("FAILURE_PACKET", failure_id)
        if failure_artifact is not None:
            evidence_artifact_ids.append(failure_artifact.id)

    evidence_artifact_ids = sorted(set(evidence_artifact_ids))
    passed = not missing_artifact_types and not blocking_failure_packet_ids
    decision_value: Literal["passed", "blocked"] = "passed" if passed else "blocked"
    rationale_parts = []
    if missing_artifact_types:
        rationale_parts.append(f"Missing required artifacts: {', '.join(missing_artifact_types)}.")
    if blocking_failure_packet_ids:
        rationale_parts.append(
            f"Blocking failure packets remain: {', '.join(blocking_failure_packet_ids)}."
        )
    if not rationale_parts:
        rationale_parts.append("Required evidence is present and no blocking failures remain.")
    decision = GateDecision(
        id=f"gate_decision_{uuid4().hex[:12]}",
        project_id=project_id,
        gate_id=gate.id,
        agent_design_id=gate.agent_design_id,
        eval_result_id=payload.eval_result_id,
        comparison_id=payload.comparison_id,
        decision=decision_value,
        rationale=" ".join(rationale_parts),
        missing_artifact_types=missing_artifact_types,
        blocking_failure_packet_ids=blocking_failure_packet_ids,
        evidence_artifact_ids=evidence_artifact_ids,
        decided_by=payload.decided_by.strip(),
        created_at=now,
    )
    _gate_decisions[decision.id] = decision
    store.save_record("gate_decisions", decision.id, decision)

    gate_artifact = find_artifact_by_type_and_artifact_id("GATE", gate.id)
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="GATE_DECISION",
        artifact_id=decision.id,
        title=f"Gate decision: {gate.name}",
        body=(
            f"Decision\n{decision.decision}\n\n"
            f"Rationale\n{decision.rationale}\n\n"
            f"Missing artifacts\n"
            + ("\n".join(f"- {item}" for item in missing_artifact_types) or "None")
            + "\n\nBlocking failures\n"
            + ("\n".join(f"- {item}" for item in blocking_failure_packet_ids) or "None")
        ),
        source="gate-decision",
        agent_design_id=gate.agent_design_id,
        now=now,
    )
    if gate_artifact is not None:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=gate_artifact.id,
            relationship_type="GENERATED_FROM",
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
    return decision


def create_trace_ref_record(
    *,
    project_id: str,
    payload: TraceRefCreate,
    now: datetime,
) -> TraceRef:
    run = get_run_or_404(project_id, payload.run_id)
    related_artifacts = [
        get_artifact_or_404(project_id, artifact_id)
        for artifact_id in payload.related_artifact_ids
    ]
    trace_ref = TraceRef(
        id=f"trace_ref_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=run.agent_design_id,
        provider=payload.provider.strip(),
        external_trace_id=payload.external_trace_id.strip(),
        run_id=run.id,
        url=payload.url.strip(),
        metadata=payload.metadata,
        artifact_ids=[],
        created_at=now,
    )
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="TRACE_REF",
        artifact_id=trace_ref.id,
        title=f"{trace_ref.provider} trace: {trace_ref.external_trace_id}",
        body=(
            f"Provider\n{trace_ref.provider}\n\n"
            f"External trace id\n{trace_ref.external_trace_id}\n\n"
            f"Run\n{trace_ref.run_id}\n\n"
            f"URL\n{trace_ref.url}\n\n"
            f"Metadata\n{json.dumps(trace_ref.metadata, sort_keys=True)}"
        ),
        source=f"trace-ref:{trace_ref.provider}",
        agent_design_id=run.agent_design_id,
        now=now,
        external_refs=[
            ExternalArtifactRef(
                provider=trace_ref.provider,
                ref_type="trace",
                external_id=trace_ref.external_trace_id,
                url=trace_ref.url,
                label="Langfuse trace" if trace_ref.provider == "langfuse" else "Trace",
                metadata=trace_ref.metadata,
            )
        ]
        + prompt_refs_from_metadata(trace_ref.metadata),
    )
    trace_ref = trace_ref.model_copy(update={"artifact_ids": [artifact.id]})
    _trace_refs[trace_ref.id] = trace_ref
    store.save_record("trace_refs", trace_ref.id, trace_ref)

    for run_artifact_id in run.artifact_ids:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=run_artifact_id,
            relationship_type="OBSERVES",
            now=now,
        )
    for related_artifact in related_artifacts:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=related_artifact.id,
            relationship_type="SUPPORTS",
            now=now,
        )
    link_to_agent_design(
        project_id=project_id,
        agent_design_id=run.agent_design_id,
        artifact=artifact,
        now=now,
    )
    return trace_ref


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
    artifact = create_artifact(
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
        + prompt_refs_from_metadata(metadata),
    )
    for related_artifact_id in related_artifact_ids:
        if related_artifact_id in _artifacts:
            link_artifacts(
                project_id=project_id,
                source_artifact_id=artifact.id,
                target_artifact_id=related_artifact_id,
                relationship_type="OBSERVES",
                now=now,
            )
    link_to_agent_design(
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


def find_project_tool_by_name(project_id: str, name: str) -> Optional[ToolDefinition]:
    normalized = name.strip()
    return next(
        (
            tool
            for tool in _tool_definitions.values()
            if tool.project_id == project_id and tool.name == normalized
        ),
        None,
    )


def approve_generated_tool(tool: ToolDefinition, mock_response: str) -> ToolDefinition:
    now = datetime.now(timezone.utc)
    updated = tool.model_copy(
        update={
            "implementation_kind": "mock",
            "implementation_key": f"mock.{tool.name}",
            "mock_response": mock_response,
            "status": "approved",
            "updated_at": now,
        }
    )
    _tool_definitions[updated.id] = updated
    store.save_record("tool_definitions", updated.id, updated)
    upsert_tool_definition_artifact(updated, now)
    return updated


def validate_allowed_tool_names(project_id: str, allowed_tool_names: List[str]) -> None:
    approved_tool_names = {
        tool.name
        for tool in _tool_definitions.values()
        if tool.project_id == project_id and tool.status == "approved"
    }
    unknown_tools = sorted(set(allowed_tool_names) - approved_tool_names)
    if unknown_tools:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown or unapproved tools: {', '.join(unknown_tools)}.",
        )


def validate_json_schema_object(schema: Dict[str, object], field_name: str) -> None:
    schema_type = schema.get("type")
    if schema_type is not None and schema_type != "object":
        raise HTTPException(status_code=400, detail=f"{field_name} must be an object schema.")
    properties = schema.get("properties")
    if properties is not None and not isinstance(properties, dict):
        raise HTTPException(status_code=400, detail=f"{field_name}.properties must be an object.")
    required = schema.get("required")
    if required is not None:
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise HTTPException(status_code=400, detail=f"{field_name}.required must be a list of strings.")


_LIVE_JUDGE_CHECK_TYPES = {"outcome_rubric", "rubric_judge", "llm_judge"}

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


def _generate_rubric(outcome: str, output_focus: str, has_live_tools: bool = False) -> str:
    _FALLBACK_RUBRIC = (
        "Pass if the response directly satisfies the requested outcome "
        "with specific, concrete details. Fail if the response is generic, "
        "refuses to complete the task, or provides no actionable result."
    )
    try:
        config = anthropic_config_from_env()
        if has_live_tools:
            tool_instruction = (
                "The agent CAN fetch live data — it has web tools. "
                "NEVER include 'notes limitations', 'acknowledges inability', or similar clauses. "
                "Focus ONLY on whether the fetched data is specific and complete for the outcome."
            )
        else:
            tool_instruction = (
                "The agent has no live tools. "
                "Pass if it provides the best available answer and is clear about what it cannot verify."
            )
        response = _anthropic_client(config).messages.create(
            model=config.model,
            max_tokens=150,
            system=(
                "You write eval rubrics for AI agent outputs. "
                "Return ONLY one sentence starting with 'Pass if'. Max 50 words. "
                "No preamble. No extra sentences. No 'and explicitly notes limitations'."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Outcome: {outcome}\n"
                    f"Expected approach: {output_focus}\n"
                    f"Constraint: {tool_instruction}\n"
                    "Rubric:"
                ),
            }],
        )
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text.strip()
                break
        if not text:
            return _FALLBACK_RUBRIC
        # When agent has live tools, strip any clause about noting limitations
        if has_live_tools:
            for bad_phrase in [
                ", and explicitly notes any limitations",
                ", explicitly noting any limitations",
                " and notes any limitations",
                " while noting limitations",
                ", noting any limitations",
            ]:
                text = text.replace(bad_phrase, "")
        return text
    except Exception:
        return _FALLBACK_RUBRIC


def _generate_test_input(outcome: str, intent: str) -> str:
    """Generate a concrete test input sentence that exercises the agent's intent."""
    _FALLBACK = outcome
    try:
        config = anthropic_config_from_env()
        response = _anthropic_client(config).messages.create(
            model=config.model,
            max_tokens=100,
            system=(
                "You write realistic test inputs for AI agents. "
                "Return ONLY one sentence a real user would type. No preamble. No quotes."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Agent purpose: {intent}\n"
                    f"User goal: {outcome}\n"
                    "Write one realistic user message that would trigger this agent:"
                ),
            }],
        )
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text.strip().strip('"').strip("'")
                return text if text else _FALLBACK
        return _FALLBACK
    except Exception:
        return _FALLBACK


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
            langfuse_prompt_refs(
                name=version.langfuse_prompt_name,
                version=version.langfuse_prompt_version,
                label=version.langfuse_prompt_label,
                prompt_role="agent_version",
                source_id=version.id,
            )
        )
    else:
        refs.extend(
            langfuse_prompt_refs(
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
                langfuse_prompt_refs(
                    name=template.langfuse_prompt_name,
                    version=template.langfuse_prompt_version,
                    label=template.langfuse_prompt_label,
                    prompt_role="judge",
                    source_id=template.id,
                )
            )
    return refs


def run_agent_with_runner(
    *,
    project_id: str,
    agent: AgentDesign,
    instructions: str,
    scenario_input: str,
    mode: Literal["mock", "live"],
    prompt_refs: Optional[List[ExternalArtifactRef]] = None,
    model_override: Optional[str] = None,
) -> tuple[object, ArtifactRecord, List[ArtifactRecord]]:
    runner_agent = RunnerAgentDesign(
        id=agent.id,
        name=agent.name,
        intent=instructions,
        allowed_tool_names=agent.allowed_tool_names,
    )
    runner_scenario = RunnerScenario(input=scenario_input.strip())
    if mode == "live":
        try:
            config = anthropic_config_from_env()
            if model_override:
                config = config.__class__(**{**config.__dict__, "model": model_override})
            runner_result = run_anthropic_agent(
                runner_agent,
                runner_scenario,
                config,
                approved_tools_for_agent(project_id, agent),
            )
        except RuntimeError as exc:
            detail = str(exc)
            status_code = 400 if "ANTHROPIC_API_KEY" in detail else 502
            raise HTTPException(status_code=status_code, detail=detail) from exc
    else:
        runner_result = run_mock_agent(runner_agent, runner_scenario)

    now = datetime.now(timezone.utc)
    tool_summary = "\n".join(
        f"- {tool.name}: {tool.output}" for tool in runner_result.tool_calls
    )
    artifact = create_artifact(
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
    link_to_agent_design(
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
    return runner_result, artifact, tool_artifacts


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
            with urlopen(request, timeout=10) as response:
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

    if langfuse_credentials_configured():
        try:
            langfuse = get_langfuse_client()
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

    artifact = create_artifact(
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
    link_to_agent_design(
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
    elif not langfuse_credentials_configured():
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


def validate_fix_proposal_references(
    *,
    project_id: str,
    agent_design_id: str,
    target_version_id: Optional[str],
    addressed_failure_packet_ids: List[str],
    validation_contract_ids: List[str],
) -> None:
    get_agent_design_or_404(project_id, agent_design_id)
    if target_version_id is not None:
        target_version = get_agent_version_or_404(project_id, target_version_id)
        if target_version.agent_design_id != agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Fix proposal target version must belong to the same agent design.",
            )

    for failure_packet_id in addressed_failure_packet_ids:
        failure_packet = get_failure_packet_or_404(project_id, failure_packet_id)
        if failure_packet.agent_design_id != agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Fix proposal failure packets must belong to the same agent design.",
            )

    for contract_id in validation_contract_ids:
        contract = get_eval_contract_or_404(project_id, contract_id)
        if contract.agent_design_id != agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Fix proposal validation contracts must belong to the same agent design.",
            )


def fix_proposal_artifact_body(fix_proposal: FixProposal) -> str:
    change_lines = "\n".join(
        f"- {change.get('surface', 'change')}: {change.get('change', change)}"
        for change in fix_proposal.proposed_changes
    )
    return (
        f"Rationale\n{fix_proposal.rationale}\n\n"
        f"Target version\n{fix_proposal.target_version_id or 'None'}\n\n"
        f"Addressed failures\n"
        + "\n".join(
            f"- {failure_id}" for failure_id in fix_proposal.addressed_failure_packet_ids
        )
        + "\n\nValidation contracts\n"
        + "\n".join(
            f"- {contract_id}" for contract_id in fix_proposal.validation_contract_ids
        )
        + f"\n\nProposed changes\n{change_lines or 'Needs review'}"
    )


def create_fix_proposal_record(
    *,
    project_id: str,
    agent_design_id: str,
    target_version_id: Optional[str],
    title: str,
    rationale: str,
    proposed_changes: List[Dict[str, object]],
    addressed_failure_packet_ids: List[str],
    validation_contract_ids: List[str],
    status: str,
    now: datetime,
) -> FixProposal:
    fix_proposal = FixProposal(
        id=f"fix_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=agent_design_id,
        target_version_id=target_version_id,
        title=title,
        rationale=rationale,
        proposed_changes=proposed_changes,
        addressed_failure_packet_ids=addressed_failure_packet_ids,
        validation_contract_ids=validation_contract_ids,
        status=status,
        created_at=now,
        updated_at=now,
    )

    artifact = create_artifact(
        project_id=project_id,
        artifact_type="FIX_PROPOSAL",
        artifact_id=fix_proposal.id,
        title=fix_proposal.title,
        body=fix_proposal_artifact_body(fix_proposal),
        source="fix-proposal",
        agent_design_id=agent_design_id,
        now=now,
    )
    fix_proposal = fix_proposal.model_copy(update={"artifact_ids": [artifact.id]})
    _fix_proposals[fix_proposal.id] = fix_proposal
    store.save_record("fix_proposals", fix_proposal.id, fix_proposal)

    for failure_packet_id in addressed_failure_packet_ids:
        failure_artifact = find_artifact_by_type_and_artifact_id(
            "FAILURE_PACKET",
            failure_packet_id,
        )
        if failure_artifact is not None:
            link_artifacts(
                project_id=project_id,
                source_artifact_id=artifact.id,
                target_artifact_id=failure_artifact.id,
                relationship_type="ADDRESSES",
                now=now,
            )
    link_to_agent_design(
        project_id=project_id,
        agent_design_id=agent_design_id,
        artifact=artifact,
        now=now,
    )
    return fix_proposal


def find_eval_result_for_run(
    *,
    project_id: str,
    run_id: str,
    eval_contract_id: str,
) -> Optional[EvalResult]:
    for eval_result in _eval_results.values():
        if (
            eval_result.project_id == project_id
            and eval_result.run_id == run_id
            and eval_result.eval_contract_id == eval_contract_id
        ):
            return eval_result
    return None


def failure_packets_for_eval(
    *,
    project_id: str,
    eval_result_id: str,
) -> List[FailurePacket]:
    return [
        failure_packet
        for failure_packet in _failure_packets.values()
        if failure_packet.project_id == project_id
        and failure_packet.eval_result_id == eval_result_id
    ]


def create_comparison_record(
    *,
    project_id: str,
    baseline_run: RunRecord,
    candidate_run: RunRecord,
    eval_contract_id: str,
    baseline_eval_result: EvalResult,
    candidate_eval_result: EvalResult,
    now: datetime,
) -> Comparison:
    baseline_packets = failure_packets_for_eval(
        project_id=project_id,
        eval_result_id=baseline_eval_result.id,
    )
    candidate_packets = failure_packets_for_eval(
        project_id=project_id,
        eval_result_id=candidate_eval_result.id,
    )
    candidate_failed_check_ids = {
        check.check_id for check in candidate_eval_result.checks if not check.passed
    }
    baseline_failed_check_ids = {
        check.check_id for check in baseline_eval_result.checks if not check.passed
    }
    fixed_failure_packet_ids = [
        packet.id
        for packet in baseline_packets
        if not set(packet.failed_check_ids) & candidate_failed_check_ids
    ]
    remaining_failure_packet_ids = [
        packet.id
        for packet in baseline_packets
        if set(packet.failed_check_ids) & candidate_failed_check_ids
    ]
    new_failure_packet_ids = [
        packet.id
        for packet in candidate_packets
        if bool(set(packet.failed_check_ids) - baseline_failed_check_ids)
    ]
    summary = (
        f"Comparison fixed {len(fixed_failure_packet_ids)} failure packet(s), "
        f"left {len(remaining_failure_packet_ids)} remaining, "
        f"and introduced {len(new_failure_packet_ids)} new failure packet(s)."
    )
    comparison_id = f"comparison_{uuid4().hex[:12]}"
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="COMPARISON",
        artifact_id=comparison_id,
        title="Version comparison",
        body=(
            f"Baseline run\n{baseline_run.id}\n\n"
            f"Candidate run\n{candidate_run.id}\n\n"
            f"Eval contract\n{eval_contract_id}\n\n"
            f"Summary\n{summary}\n\n"
            f"Fixed failures\n"
            + "\n".join(f"- {failure_id}" for failure_id in fixed_failure_packet_ids)
            + "\n\nRemaining failures\n"
            + "\n".join(f"- {failure_id}" for failure_id in remaining_failure_packet_ids)
            + "\n\nNew failures\n"
            + "\n".join(f"- {failure_id}" for failure_id in new_failure_packet_ids)
        ),
        source="comparison",
        agent_design_id=baseline_run.agent_design_id,
        now=now,
    )
    for artifact_id in baseline_run.artifact_ids + candidate_run.artifact_ids:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=artifact_id,
            relationship_type="SUPPORTED_BY",
            now=now,
        )

    comparison = Comparison(
        id=comparison_id,
        project_id=project_id,
        agent_design_id=baseline_run.agent_design_id,
        baseline_version_id=baseline_run.agent_version_id,
        candidate_version_id=candidate_run.agent_version_id,
        baseline_run_id=baseline_run.id,
        candidate_run_id=candidate_run.id,
        baseline_eval_result_id=baseline_eval_result.id,
        candidate_eval_result_id=candidate_eval_result.id,
        fixed_failure_packet_ids=fixed_failure_packet_ids,
        new_failure_packet_ids=new_failure_packet_ids,
        remaining_failure_packet_ids=remaining_failure_packet_ids,
        summary=summary,
        artifact_ids=[artifact.id],
        created_at=now,
    )
    _comparisons[comparison.id] = comparison
    store.save_record("comparisons", comparison.id, comparison)
    return comparison


def delete_agent_design_records(project_id: str, agent_id: str) -> None:
    artifact_ids = [
        artifact.id
        for artifact in _artifacts.values()
        if artifact.project_id == project_id and artifact.agent_design_id == agent_id
    ]
    for artifact_id in artifact_ids:
        _artifacts.pop(artifact_id, None)
        store.delete_record("artifacts", artifact_id)

    link_ids = [
        link.id
        for link in _artifact_links.values()
        if link.project_id == project_id
        and (
            link.source_artifact_id in artifact_ids
            or link.target_artifact_id in artifact_ids
        )
    ]
    for link_id in link_ids:
        _artifact_links.pop(link_id, None)
        store.delete_record("artifact_links", link_id)

    for scenario_id, scenario in list(_scenarios.items()):
        if scenario.project_id == project_id and scenario.agent_design_id == agent_id:
            _scenarios.pop(scenario_id, None)
            store.delete_record("scenarios", scenario_id)

    for contract_id, contract in list(_eval_contracts.items()):
        if contract.project_id == project_id and contract.agent_design_id == agent_id:
            _eval_contracts.pop(contract_id, None)
            store.delete_record("eval_contracts", contract_id)

    for gate_id, gate in list(_gate_definitions.items()):
        if gate.project_id == project_id and gate.agent_design_id == agent_id:
            _gate_definitions.pop(gate_id, None)
            store.delete_record("gate_definitions", gate_id)

    for decision_id, decision in list(_gate_decisions.items()):
        if decision.project_id == project_id and decision.agent_design_id == agent_id:
            _gate_decisions.pop(decision_id, None)
            store.delete_record("gate_decisions", decision_id)

    for version_id, version in list(_agent_versions.items()):
        if version.project_id == project_id and version.agent_design_id == agent_id:
            _agent_versions.pop(version_id, None)
            store.delete_record("agent_versions", version_id)

    deleted_run_ids: List[str] = []
    for run_id, run in list(_runs.items()):
        if run.project_id == project_id and run.agent_design_id == agent_id:
            deleted_run_ids.append(run_id)
            _runs.pop(run_id, None)
            store.delete_record("runs", run_id)

    for trace_ref_id, trace_ref in list(_trace_refs.items()):
        if trace_ref.project_id == project_id and trace_ref.agent_design_id == agent_id:
            _trace_refs.pop(trace_ref_id, None)
            store.delete_record("trace_refs", trace_ref_id)

    deleted_eval_result_ids: List[str] = []
    for eval_result_id, eval_result in list(_eval_results.items()):
        if eval_result.project_id == project_id and eval_result.run_id in deleted_run_ids:
            deleted_eval_result_ids.append(eval_result_id)
            _eval_results.pop(eval_result_id, None)
            store.delete_record("eval_results", eval_result_id)

    for judge_output_id, judge_output in list(_judge_outputs.items()):
        if (
            judge_output.project_id == project_id
            and judge_output.eval_result_id in deleted_eval_result_ids
        ):
            _judge_outputs.pop(judge_output_id, None)
            store.delete_record("judge_outputs", judge_output_id)

    for failure_packet_id, failure_packet in list(_failure_packets.items()):
        if failure_packet.project_id == project_id and failure_packet.run_id in deleted_run_ids:
            _failure_packets.pop(failure_packet_id, None)
            store.delete_record("failure_packets", failure_packet_id)

    for fix_proposal_id, fix_proposal in list(_fix_proposals.items()):
        if fix_proposal.project_id == project_id and fix_proposal.agent_design_id == agent_id:
            _fix_proposals.pop(fix_proposal_id, None)
            store.delete_record("fix_proposals", fix_proposal_id)

    for comparison_id, comparison in list(_comparisons.items()):
        if comparison.project_id == project_id and comparison.agent_design_id == agent_id:
            _comparisons.pop(comparison_id, None)
            store.delete_record("comparisons", comparison_id)

    _agent_designs.pop(agent_id, None)
    store.delete_record("agent_designs", agent_id)


@app.get("/api/projects")
def list_projects() -> List[Project]:
    return sorted(_projects.values(), key=lambda project: project.updated_at, reverse=True)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> Project:
    return get_project_or_404(project_id)


@app.get("/api/projects/{project_id}/agent-designs")
def list_agent_designs(project_id: str) -> List[AgentDesign]:
    get_project_or_404(project_id)
    agents = [agent for agent in _agent_designs.values() if agent.project_id == project_id]
    return sorted(agents, key=lambda agent: agent.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/agent-designs", status_code=201)
def create_agent_design(project_id: str, payload: AgentDesignCreate) -> AgentDesignCreated:
    get_project_or_404(project_id)
    now = datetime.now(timezone.utc)
    agent = AgentDesign(
        id=f"agent_{uuid4().hex[:12]}",
        project_id=project_id,
        name=payload.name.strip(),
        intent=payload.intent.strip(),
        status="designing",
        allowed_tool_names=payload.allowed_tool_names or [
            t.name for t in _tool_definitions.values()
            if t.project_id == project_id and t.status == "approved"
        ],
        langfuse_prompt_name=(
            payload.langfuse_prompt_name.strip()
            if payload.langfuse_prompt_name is not None
            else None
        ),
        langfuse_prompt_version=(
            payload.langfuse_prompt_version.strip()
            if payload.langfuse_prompt_version is not None
            else None
        ),
        langfuse_prompt_label=(
            payload.langfuse_prompt_label.strip()
            if payload.langfuse_prompt_label is not None
            else None
        ),
        created_at=now,
        updated_at=now,
    )
    _agent_designs[agent.id] = agent
    store.save_record("agent_designs", agent.id, agent)

    artifact = sync_agent_design_artifact(agent, now)

    return AgentDesignCreated(agent=agent, artifact=artifact)


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


def draft_agent_from_outcome(
    project_id: str,
    outcome: str,
    agent_name: Optional[str] = None,
    rubric_override: Optional[str] = None,
    test_input_override: Optional[str] = None,
) -> OutcomeAgentCreated:
    normalized = " ".join(outcome.strip().split())

    all_project_tools = [
        t for t in _tool_definitions.values()
        if t.project_id == project_id and t.status == "approved"
    ]
    available_tool_names = [t.name for t in all_project_tools]

    plan = _draft_agent_plan_from_llm(normalized, available_tool_names)

    name = plan["name"]
    intent = plan["intent"]
    output_focus = plan["output_focus"]
    output_requirements = plan["output_requirements"]
    allowed_tools = list(plan["allowed_tools"])
    required_tools = list(plan["required_tools"])

    draft_tools: List[ToolDefinition] = []

    lowered = normalized.lower()
    _motorsport_terms = ["grand prix", "formula 1", "formula one", "formula1", "f1", "nexgt 1", "nxt 1"]
    _is_motorsport = any(term in lowered for term in _motorsport_terms) or (
        "race" in lowered and any(term in lowered for term in ["nexgt", "nxt"])
    )
    is_schedule_task = _is_motorsport and any(
        term in lowered for term in ["next", "upcoming", "schedule", "when", "nexgt", "nxt"]
    )
    is_result_task = _is_motorsport and any(
        term in lowered for term in ["last", "latest", "won", "winner", "result"]
    )

    schedule_tool = find_project_tool_by_name(project_id, "lookup_event_schedule")
    result_tool = find_project_tool_by_name(project_id, "lookup_event_result")
    schedule_tool = find_project_tool_by_name(project_id, "lookup_event_schedule")
    result_tool = find_project_tool_by_name(project_id, "lookup_event_result")
    schedule_tool_response = (
        "Race: Austrian Grand Prix. Date: 2026-06-28. Venue: Red Bull Ring, "
        "Spielberg, Austria. Source: Formula 1 calendar."
    )
    result_tool_response = (
        "Race: Barcelona-Catalunya Grand Prix. Date: 2026-06-14. "
        "Winner: Lewis Hamilton. Source: Formula 1 race results."
    )
    if is_schedule_task:
        if schedule_tool is None:
            schedule_tool = create_tool_definition(
                project_id,
                ToolDefinitionCreate(
                    name="lookup_event_schedule",
                    description=(
                        "Find the next scheduled event for a sport, series, or calendar "
                        "after a reference date."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "series": {
                                "type": "string",
                                "description": "Competition or event series, such as Formula 1.",
                            },
                            "reference_date": {
                                "type": "string",
                                "format": "date",
                                "description": "Date used to decide what counts as next.",
                            },
                            "query": {
                                "type": "string",
                                "description": "Original user schedule question.",
                            },
                        },
                        "required": ["series", "reference_date"],
                    },
                    output_schema={
                        "type": "object",
                        "properties": {
                            "event_name": {"type": "string"},
                            "event_date": {"type": "string", "format": "date"},
                            "venue": {"type": "string"},
                            "source_url": {"type": "string"},
                            "retrieved_at": {"type": "string", "format": "date-time"},
                        },
                        "required": ["event_name", "event_date", "source_url"],
                    },
                    output_description="Next scheduled event with date, venue, and source.",
                    implementation_kind="mock",
                    implementation_key="mock.lookup_event_schedule",
                    config_schema={"type": "object", "properties": {}},
                    mock_response=schedule_tool_response,
                    status="approved",
                ),
            )
        elif schedule_tool.status != "approved":
            schedule_tool = approve_generated_tool(schedule_tool, schedule_tool_response)
        if schedule_tool.status != "approved":
            draft_tools.append(schedule_tool)
    if is_result_task:
        if result_tool is None:
            result_tool = create_tool_definition(
                project_id,
                ToolDefinitionCreate(
                    name="lookup_event_result",
                    description=(
                        "Find the latest completed event result for a sport or series, "
                        "including winner and source."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "series": {
                                "type": "string",
                                "description": "Competition or event series, such as Formula 1.",
                            },
                            "query": {
                                "type": "string",
                                "description": "Original user result question.",
                            },
                            "reference_date": {
                                "type": "string",
                                "format": "date",
                                "description": "Date used to decide the latest completed event.",
                            },
                        },
                        "required": ["series", "query"],
                    },
                    output_schema={
                        "type": "object",
                        "properties": {
                            "event_name": {"type": "string"},
                            "event_date": {"type": "string", "format": "date"},
                            "winner": {"type": "string"},
                            "source_url": {"type": "string"},
                            "retrieved_at": {"type": "string", "format": "date-time"},
                        },
                        "required": ["event_name", "winner", "source_url"],
                    },
                    output_description="Latest completed event winner with source.",
                    implementation_kind="mock",
                    implementation_key="mock.lookup_event_result",
                    config_schema={"type": "object", "properties": {}},
                    mock_response=result_tool_response,
                    status="approved",
                ),
            )
        elif result_tool.status != "approved":
            result_tool = approve_generated_tool(result_tool, result_tool_response)
        if result_tool.status != "approved":
            draft_tools.append(result_tool)
    seen_tools: set[str] = set(allowed_tools)
    if is_schedule_task and schedule_tool is not None:
        if schedule_tool.name not in seen_tools:
            allowed_tools.append(schedule_tool.name)
            seen_tools.add(schedule_tool.name)
        if schedule_tool.name not in required_tools:
            required_tools.append(schedule_tool.name)
    if is_result_task and result_tool is not None:
        if result_tool.name not in seen_tools:
            allowed_tools.append(result_tool.name)
            seen_tools.add(result_tool.name)
        if result_tool.name not in required_tools:
            required_tools.append(result_tool.name)

    validate_allowed_tool_names(project_id, allowed_tools)

    live_tool_keys = {"call_http_api", "browse_webpage", "open_meteo_weather"}
    has_live_tools = bool(set(allowed_tools) & live_tool_keys)
    rubric = rubric_override.strip() if rubric_override and rubric_override.strip() else _generate_rubric(normalized, output_focus, has_live_tools=has_live_tools)

    created = create_agent_design(
        project_id,
        AgentDesignCreate(name=agent_name.strip() if agent_name and agent_name.strip() else name, intent=intent, allowed_tool_names=allowed_tools),
    )
    now = datetime.now(timezone.utc)
    if created.agent.allowed_tool_names != allowed_tools:
        agent = created.agent.model_copy(
            update={
                "allowed_tool_names": allowed_tools,
                "updated_at": now,
            }
        )
        _agent_designs[agent.id] = agent
        store.save_record("agent_designs", agent.id, agent)
        artifact = sync_agent_design_artifact(agent, now)
        created = AgentDesignCreated(agent=agent, artifact=artifact)
    for draft_tool in draft_tools:
        tool_artifact = find_artifact_by_type_and_artifact_id("TOOL_DEFINITION", draft_tool.id)
        if tool_artifact is not None:
            link_to_agent_design(
                project_id=project_id,
                agent_design_id=created.agent.id,
                artifact=tool_artifact,
                now=now,
            )
    version = create_agent_version(
        project_id,
        created.agent.id,
        AgentVersionCreate(
            version_label="v0",
            instructions=intent,
            tool_policy={"allowed_tool_names": created.agent.allowed_tool_names},
            status="baseline",
        ),
    )
    scenario = create_scenario(
        project_id,
        ScenarioCreate(
            agent_design_id=created.agent.id,
            name="Outcome request",
            input=test_input_override.strip() if test_input_override and test_input_override.strip() else normalized,
            setup_context="test_shape:single_turn\norigin:outcome_draft",
            status="active",
        ),
    )
    contract = create_eval_contract(
        project_id,
        EvalContractCreate(
            agent_design_id=created.agent.id,
            name="Outcome satisfaction",
            description="Checks the first draft against the user-requested outcome.",
            scenario_id=scenario.id,
            version="v0",
            expected_behavior=[
                f"Address the requested outcome: {normalized}",
                output_focus,
                *(
                    [
                        "Use or implement the proposed lookup tool before treating the design as complete."
                    ]
                    if draft_tools
                    else []
                ),
                "Do not mark the task complete when the response lacks the requested result.",
            ],
            required_tools=required_tools,
            forbidden_behavior=(
                [
                    "I don",
                    "real-time access",
                    "If you provide",
                    "guide you to check",
                    "check a current source",
                ]
                if is_schedule_task or is_result_task
                else []
            ),
            output_requirements=output_requirements,
            checks=[
                {
                    "id": "outcome_rubric",
                    "type": "rubric_judge",
                    "value": rubric,
                }
            ],
            pass_criteria="all_checks_pass",
            status="active",
        ),
    )

    return OutcomeAgentCreated(
        agent=created.agent,
        artifact=created.artifact,
        version=version,
        scenario=scenario,
        eval_contract=contract,
        draft_tools=draft_tools,
    )


@app.post("/api/projects/{project_id}/agent-designs/from-outcome", status_code=201)
def create_agent_design_from_outcome(
    project_id: str,
    payload: OutcomeAgentCreate,
) -> OutcomeAgentCreated:
    get_project_or_404(project_id)
    return draft_agent_from_outcome(
        project_id,
        payload.outcome,
        agent_name=payload.name,
        rubric_override=payload.rubric,
        test_input_override=payload.test_input,
    )


@app.post("/api/projects/{project_id}/guided/setup")
def guided_setup_preview(
    project_id: str,
    payload: GuidedSetupRequest,
) -> GuidedSetupPreview:
    """Preview-only: generate agent name, test input, and rubric from a description.
    No data is persisted. The client uses the result to populate the wizard Step 1
    review screen, then calls from-outcome with overrides to commit."""
    get_project_or_404(project_id)
    normalized = " ".join(payload.description.strip().split())

    all_project_tools = [
        t for t in _tool_definitions.values()
        if t.project_id == project_id and t.status == "approved"
    ]
    available_tool_names = [t.name for t in all_project_tools]

    plan = _draft_agent_plan_from_llm(normalized, available_tool_names)

    live_tool_keys = {"call_http_api", "browse_webpage", "open_meteo_weather"}
    has_live_tools = bool(set(plan["allowed_tools"]) & live_tool_keys)
    rubric = _generate_rubric(normalized, plan["output_focus"], has_live_tools=has_live_tools)
    test_input = _generate_test_input(normalized, plan["intent"])

    return GuidedSetupPreview(
        agent_name=plan["name"],
        test_input=test_input,
        rubric=rubric,
    )


@app.get("/api/projects/{project_id}/agent-designs/{agent_id}")
def get_agent_design(project_id: str, agent_id: str) -> AgentDesign:
    get_project_or_404(project_id)
    return get_agent_design_or_404(project_id, agent_id)


@app.get("/api/projects/{project_id}/agent-designs/{agent_id}/wizard-state")
def get_agent_wizard_state(project_id: str, agent_id: str) -> OutcomeAgentCreated:
    """Return the agent in OutcomeAgentCreated shape so the wizard can resume."""
    get_project_or_404(project_id)
    agent = get_agent_design_or_404(project_id, agent_id)

    versions = sorted(
        [v for v in _agent_versions.values() if v.agent_design_id == agent_id],
        key=lambda v: v.created_at,
    )
    version = next((v for v in versions if v.status == "baseline"), None) or (versions[0] if versions else None)

    contracts = sorted(
        [c for c in _eval_contracts.values() if c.agent_design_id == agent_id],
        key=lambda c: c.created_at,
    )
    contract = contracts[0] if contracts else None

    scenario = _scenarios.get(contract.scenario_id) if contract and contract.scenario_id else None

    if not version or not contract or not scenario:
        raise HTTPException(status_code=404, detail="Agent has no baseline version, scenario, or eval contract yet.")

    artifact = next(
        (a for a in _artifacts.values() if a.artifact_type == "agent_design" and a.project_id == project_id),
        ArtifactRecord(id="", project_id=project_id, artifact_type="agent_design", content={}, created_at=agent.created_at),
    )

    return OutcomeAgentCreated(
        agent=agent,
        artifact=artifact,
        version=version,
        scenario=scenario,
        eval_contract=contract,
        draft_tools=[],
    )


@app.patch("/api/projects/{project_id}/agent-designs/{agent_id}")
def update_agent_design(
    project_id: str,
    agent_id: str,
    payload: AgentDesignUpdate,
) -> AgentDesign:
    get_project_or_404(project_id)
    existing = get_agent_design_or_404(project_id, agent_id)
    allowed_tool_names = existing.allowed_tool_names
    if payload.allowed_tool_names is not None:
        validate_allowed_tool_names(project_id, payload.allowed_tool_names)
        allowed_tool_names = payload.allowed_tool_names

    updated = existing.model_copy(
        update={
            "name": payload.name.strip() if payload.name is not None else existing.name,
            "intent": payload.intent.strip() if payload.intent is not None else existing.intent,
            "allowed_tool_names": allowed_tool_names,
            "status": payload.status.strip() if payload.status is not None else existing.status,
            "langfuse_prompt_name": (
                payload.langfuse_prompt_name.strip()
                if payload.langfuse_prompt_name is not None
                else existing.langfuse_prompt_name
            ),
            "langfuse_prompt_version": (
                payload.langfuse_prompt_version.strip()
                if payload.langfuse_prompt_version is not None
                else existing.langfuse_prompt_version
            ),
            "langfuse_prompt_label": (
                payload.langfuse_prompt_label.strip()
                if payload.langfuse_prompt_label is not None
                else existing.langfuse_prompt_label
            ),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    _agent_designs[updated.id] = updated
    store.save_record("agent_designs", updated.id, updated)
    sync_agent_design_artifact(updated, updated.updated_at)
    return updated


@app.delete("/api/projects/{project_id}/agent-designs/{agent_id}", status_code=204)
def delete_agent_design(project_id: str, agent_id: str) -> Response:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, agent_id)
    delete_agent_design_records(project_id, agent_id)
    return Response(status_code=204)


@app.get("/api/projects/{project_id}/scenarios")
def list_scenarios(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[Scenario]:
    get_project_or_404(project_id)
    scenarios = [
        scenario
        for scenario in _scenarios.values()
        if scenario.project_id == project_id
        and (agent_design_id is None or scenario.agent_design_id == agent_design_id)
    ]
    return sorted(scenarios, key=lambda scenario: scenario.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/scenarios", status_code=201)
def create_scenario(project_id: str, payload: ScenarioCreate) -> Scenario:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, payload.agent_design_id)
    if payload.default_eval_contract_id is not None:
        get_eval_contract_or_404(project_id, payload.default_eval_contract_id)

    now = datetime.now(timezone.utc)
    scenario = Scenario(
        id=f"scenario_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        name=payload.name.strip(),
        input=payload.input.strip(),
        setup_context=payload.setup_context.strip(),
        fixture_refs=payload.fixture_refs,
        default_eval_contract_id=payload.default_eval_contract_id,
        status=payload.status.strip(),
        created_at=now,
        updated_at=now,
    )
    _scenarios[scenario.id] = scenario
    store.save_record("scenarios", scenario.id, scenario)

    artifact = create_artifact(
        project_id=project_id,
        artifact_type="SCENARIO",
        artifact_id=scenario.id,
        title=scenario.name,
        body=(
            f"Input\n{scenario.input}\n\n"
            f"Setup context\n{scenario.setup_context or 'None'}\n\n"
            f"Default eval contract\n{scenario.default_eval_contract_id or 'None'}"
        ),
        source="scenario",
        agent_design_id=scenario.agent_design_id,
        now=now,
        external_refs=sync_langfuse_scenario_dataset_refs(
            project_id=project_id,
            scenario=scenario,
        ),
    )
    link_to_agent_design(
        project_id=project_id,
        agent_design_id=scenario.agent_design_id,
        artifact=artifact,
        now=now,
    )
    return scenario


@app.get("/api/projects/{project_id}/scenarios/{scenario_id}")
def get_scenario(project_id: str, scenario_id: str) -> Scenario:
    get_project_or_404(project_id)
    return get_scenario_or_404(project_id, scenario_id)


@app.get("/api/projects/{project_id}/judge-prompt-templates")
def list_judge_prompt_templates(project_id: str) -> List[JudgePromptTemplate]:
    get_project_or_404(project_id)
    templates = [
        template
        for template in _judge_prompt_templates.values()
        if template.project_id == project_id
    ]
    return sorted(templates, key=lambda template: template.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/judge-prompt-templates", status_code=201)
def create_judge_prompt_template(
    project_id: str,
    payload: JudgePromptTemplateCreate,
) -> JudgePromptTemplate:
    get_project_or_404(project_id)
    now = datetime.now(timezone.utc)
    template = JudgePromptTemplate(
        id=f"judge_prompt_{uuid4().hex[:12]}",
        project_id=project_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        template=payload.template.strip(),
        version=payload.version.strip(),
        status=payload.status.strip(),
        langfuse_prompt_name=(
            payload.langfuse_prompt_name.strip()
            if payload.langfuse_prompt_name is not None
            else None
        ),
        langfuse_prompt_version=(
            payload.langfuse_prompt_version.strip()
            if payload.langfuse_prompt_version is not None
            else None
        ),
        langfuse_prompt_label=(
            payload.langfuse_prompt_label.strip()
            if payload.langfuse_prompt_label is not None
            else None
        ),
        created_at=now,
        updated_at=now,
    )
    _judge_prompt_templates[template.id] = template
    store.save_record("judge_prompt_templates", template.id, template)
    create_artifact(
        project_id=project_id,
        artifact_type="JUDGE_PROMPT_TEMPLATE",
        artifact_id=template.id,
        title=template.name,
        body=(
            f"Description\n{template.description or 'None'}\n\n"
            f"Version\n{template.version}\n\n"
            f"Langfuse prompt\n"
            + langfuse_prompt_display(
                name=template.langfuse_prompt_name,
                version=template.langfuse_prompt_version,
                label=template.langfuse_prompt_label,
            )
            + "\n\n"
            f"Template\n{template.template}"
        ),
        source="judge-prompt-template",
        agent_design_id=None,
        now=now,
        external_refs=langfuse_prompt_refs(
            name=template.langfuse_prompt_name,
            version=template.langfuse_prompt_version,
            label=template.langfuse_prompt_label,
            prompt_role="judge",
            source_id=template.id,
        ),
    )
    return template


@app.get("/api/projects/{project_id}/judge-prompt-templates/{judge_prompt_template_id}")
def get_judge_prompt_template(
    project_id: str,
    judge_prompt_template_id: str,
) -> JudgePromptTemplate:
    get_project_or_404(project_id)
    return get_judge_prompt_template_or_404(project_id, judge_prompt_template_id)


@app.get("/api/projects/{project_id}/gates")
def list_gate_definitions(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[GateDefinition]:
    get_project_or_404(project_id)
    gates = [
        gate
        for gate in _gate_definitions.values()
        if gate.project_id == project_id
        and (agent_design_id is None or gate.agent_design_id == agent_design_id)
    ]
    return sorted(gates, key=lambda gate: gate.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/gates", status_code=201)
def create_gate_definition(project_id: str, payload: GateDefinitionCreate) -> GateDefinition:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, payload.agent_design_id)
    now = datetime.now(timezone.utc)
    gate = GateDefinition(
        id=f"gate_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        name=payload.name.strip(),
        criteria=payload.criteria,
        required_artifact_types=payload.required_artifact_types,
        threshold=payload.threshold.strip(),
        blocking_failure_statuses=payload.blocking_failure_statuses,
        approval_mode=payload.approval_mode,
        status=payload.status.strip(),
        created_at=now,
        updated_at=now,
    )
    _gate_definitions[gate.id] = gate
    store.save_record("gate_definitions", gate.id, gate)
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="GATE",
        artifact_id=gate.id,
        title=gate.name,
        body=(
            "Criteria\n"
            + ("\n".join(f"- {criterion}" for criterion in gate.criteria) or "None")
            + "\n\nRequired artifacts\n"
            + (
                "\n".join(f"- {artifact_type}" for artifact_type in gate.required_artifact_types)
                or "None"
            )
            + f"\n\nThreshold\n{gate.threshold}\n\nApproval mode\n{gate.approval_mode}"
        ),
        source="gate-definition",
        agent_design_id=gate.agent_design_id,
        now=now,
    )
    link_to_agent_design(
        project_id=project_id,
        agent_design_id=gate.agent_design_id,
        artifact=artifact,
        now=now,
    )
    return gate


@app.get("/api/projects/{project_id}/gates/{gate_id}")
def get_gate_definition(project_id: str, gate_id: str) -> GateDefinition:
    get_project_or_404(project_id)
    return get_gate_definition_or_404(project_id, gate_id)


@app.get("/api/projects/{project_id}/gate-decisions")
def list_gate_decisions(
    project_id: str,
    agent_design_id: Optional[str] = None,
    gate_id: Optional[str] = None,
) -> List[GateDecision]:
    get_project_or_404(project_id)
    decisions = [
        decision
        for decision in _gate_decisions.values()
        if decision.project_id == project_id
        and (agent_design_id is None or decision.agent_design_id == agent_design_id)
        and (gate_id is None or decision.gate_id == gate_id)
    ]
    return sorted(decisions, key=lambda decision: decision.created_at, reverse=True)


@app.post("/api/projects/{project_id}/gates/{gate_id}/decisions", status_code=201)
def create_gate_decision(
    project_id: str,
    gate_id: str,
    payload: GateDecisionCreate,
) -> GateDecision:
    get_project_or_404(project_id)
    gate = get_gate_definition_or_404(project_id, gate_id)
    return create_gate_decision_record(
        project_id=project_id,
        gate=gate,
        payload=payload,
        now=datetime.now(timezone.utc),
    )


@app.get("/api/projects/{project_id}/gate-decisions/{decision_id}")
def get_gate_decision(project_id: str, decision_id: str) -> GateDecision:
    get_project_or_404(project_id)
    return get_gate_decision_or_404(project_id, decision_id)


@app.get("/api/projects/{project_id}/eval-contracts")
def list_eval_contracts(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[EvalContract]:
    get_project_or_404(project_id)
    contracts = [
        contract
        for contract in _eval_contracts.values()
        if contract.project_id == project_id
        and (agent_design_id is None or contract.agent_design_id == agent_design_id)
    ]
    return sorted(contracts, key=lambda contract: contract.updated_at, reverse=True)


@app.post("/api/projects/{project_id}/eval-contracts", status_code=201)
def create_eval_contract(project_id: str, payload: EvalContractCreate) -> EvalContract:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, payload.agent_design_id)
    if payload.scenario_id is not None:
        scenario = get_scenario_or_404(project_id, payload.scenario_id)
        if scenario.agent_design_id != payload.agent_design_id:
            raise HTTPException(
                status_code=400,
                detail="Eval contract scenario must belong to the same agent design.",
            )
    if payload.judge_prompt_template_id is not None:
        get_judge_prompt_template_or_404(project_id, payload.judge_prompt_template_id)

    now = datetime.now(timezone.utc)
    checks = contract_generated_checks(payload)
    contract = EvalContract(
        id=f"contract_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        scenario_id=payload.scenario_id,
        version=payload.version.strip(),
        expected_behavior=payload.expected_behavior,
        required_evidence=payload.required_evidence,
        required_tools=payload.required_tools,
        forbidden_tools=payload.forbidden_tools,
        forbidden_behavior=payload.forbidden_behavior,
        output_requirements=payload.output_requirements,
        checks=checks,
        judge_prompt_template_id=payload.judge_prompt_template_id,
        pass_criteria=payload.pass_criteria.strip(),
        status=payload.status.strip(),
        created_at=now,
        updated_at=now,
    )
    _eval_contracts[contract.id] = contract
    store.save_record("eval_contracts", contract.id, contract)

    check_lines = "\n".join(
        f"- {check.get('id', 'unnamed_check')}: {check.get('type', 'unspecified')}"
        for check in contract.checks
    )
    artifact = create_artifact(
        project_id=project_id,
        artifact_type="EVAL_CONTRACT",
        artifact_id=contract.id,
        title=contract.name,
        body=(
            f"Description\n{contract.description or 'None'}\n\n"
            f"Expected behavior\n"
            + "\n".join(f"- {item}" for item in contract.expected_behavior)
            + "\n\nRequired tools\n"
            + "\n".join(f"- {tool}" for tool in contract.required_tools)
            + "\n\nChecks\n"
            + (check_lines or "None")
            + f"\n\nPass criteria\n{contract.pass_criteria}"
        ),
        source="eval-contract",
        agent_design_id=contract.agent_design_id,
        now=now,
    )
    link_to_agent_design(
        project_id=project_id,
        agent_design_id=contract.agent_design_id,
        artifact=artifact,
        now=now,
    )
    if contract.judge_prompt_template_id is not None:
        prompt_artifact = find_artifact_by_type_and_artifact_id(
            "JUDGE_PROMPT_TEMPLATE",
            contract.judge_prompt_template_id,
        )
        if prompt_artifact is not None:
            link_artifacts(
                project_id=project_id,
                source_artifact_id=artifact.id,
                target_artifact_id=prompt_artifact.id,
                relationship_type="USES",
                now=now,
            )
    return contract


@app.get("/api/projects/{project_id}/eval-contracts/{contract_id}")
def get_eval_contract(project_id: str, contract_id: str) -> EvalContract:
    get_project_or_404(project_id)
    return get_eval_contract_or_404(project_id, contract_id)


@app.patch("/api/projects/{project_id}/eval-contracts/{contract_id}/rubric")
def update_eval_contract_rubric(
    project_id: str,
    contract_id: str,
    payload: EvalContractRubricUpdate,
) -> EvalContract:
    get_project_or_404(project_id)
    contract = get_eval_contract_or_404(project_id, contract_id)
    updated_checks = []
    for check in contract.checks:
        if check.get("type") == "rubric_judge":
            updated_checks.append({**check, "value": payload.rubric.strip()})
        else:
            updated_checks.append(check)
    updated = contract.model_copy(
        update={"checks": updated_checks, "updated_at": datetime.now(timezone.utc)}
    )
    _eval_contracts[contract_id] = updated
    store.save_record("eval_contracts", contract_id, updated)
    return updated


@app.patch("/api/projects/{project_id}/eval-contracts/{contract_id}/checks")
def update_eval_contract_checks(
    project_id: str,
    contract_id: str,
    payload: EvalContractChecksUpdate,
) -> EvalContract:
    get_project_or_404(project_id)
    contract = get_eval_contract_or_404(project_id, contract_id)
    updated = contract.model_copy(
        update={"checks": payload.checks, "updated_at": datetime.now(timezone.utc)}
    )
    _eval_contracts[contract_id] = updated
    store.save_record("eval_contracts", contract_id, updated)
    return updated


@app.get("/api/projects/{project_id}/agent-designs/{agent_id}/versions")
def list_agent_versions(project_id: str, agent_id: str) -> List[AgentVersion]:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, agent_id)
    versions = [
        version
        for version in _agent_versions.values()
        if version.project_id == project_id and version.agent_design_id == agent_id
    ]
    return sorted(versions, key=lambda version: version.created_at)


@app.post("/api/projects/{project_id}/agent-designs/{agent_id}/versions", status_code=201)
def create_agent_version(
    project_id: str,
    agent_id: str,
    payload: AgentVersionCreate,
) -> AgentVersion:
    get_project_or_404(project_id)
    agent = get_agent_design_or_404(project_id, agent_id)
    if payload.parent_version_id is not None:
        parent = get_agent_version_or_404(project_id, payload.parent_version_id)
        if parent.agent_design_id != agent_id:
            raise HTTPException(
                status_code=400,
                detail="Parent version must belong to the same agent design.",
            )

    now = datetime.now(timezone.utc)
    existing_count = len(
        [
            version
            for version in _agent_versions.values()
            if version.project_id == project_id and version.agent_design_id == agent_id
        ]
    )
    version_label = payload.version_label or f"v{existing_count}"
    version = AgentVersion(
        id=f"version_{uuid4().hex[:12]}",
        project_id=project_id,
        agent_design_id=agent.id,
        version_label=version_label.strip(),
        parent_version_id=payload.parent_version_id,
        instructions=(payload.instructions or agent.intent).strip(),
        tool_policy=payload.tool_policy or {"allowed_tool_names": agent.allowed_tool_names},
        source_fix_proposal_id=payload.source_fix_proposal_id,
        status=payload.status.strip(),
        langfuse_prompt_name=(
            payload.langfuse_prompt_name.strip()
            if payload.langfuse_prompt_name is not None
            else agent.langfuse_prompt_name
        ),
        langfuse_prompt_version=(
            payload.langfuse_prompt_version.strip()
            if payload.langfuse_prompt_version is not None
            else agent.langfuse_prompt_version
        ),
        langfuse_prompt_label=(
            payload.langfuse_prompt_label.strip()
            if payload.langfuse_prompt_label is not None
            else agent.langfuse_prompt_label
        ),
        created_at=now,
        updated_at=now,
    )
    _agent_versions[version.id] = version
    store.save_record("agent_versions", version.id, version)

    artifact = create_artifact(
        project_id=project_id,
        artifact_type="AGENT_VERSION",
        artifact_id=version.id,
        title=f"{agent.name} {version.version_label}",
        body=(
            f"Instructions\n{version.instructions}\n\n"
            f"Parent version\n{version.parent_version_id or 'None'}\n\n"
            f"Status\n{version.status}\n\n"
            f"Langfuse prompt\n"
            + langfuse_prompt_display(
                name=version.langfuse_prompt_name,
                version=version.langfuse_prompt_version,
                label=version.langfuse_prompt_label,
            )
        ),
        source="agent-version",
        agent_design_id=agent.id,
        now=now,
        external_refs=langfuse_prompt_refs(
            name=version.langfuse_prompt_name,
            version=version.langfuse_prompt_version,
            label=version.langfuse_prompt_label,
            prompt_role="agent_version",
            source_id=version.id,
        ),
    )
    link_to_agent_design(
        project_id=project_id,
        agent_design_id=agent.id,
        artifact=artifact,
        now=now,
    )
    return version


@app.get("/api/projects/{project_id}/agent-designs/{agent_id}/versions/{version_id}")
def get_agent_version(project_id: str, agent_id: str, version_id: str) -> AgentVersion:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, agent_id)
    version = get_agent_version_or_404(project_id, version_id)
    if version.agent_design_id != agent_id:
        raise HTTPException(status_code=404, detail="Agent version not found.")
    return version


@app.get("/api/projects/{project_id}/runs")
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


@app.post("/api/projects/{project_id}/runs", status_code=201)
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
    runner_result, artifact, tool_artifacts = run_agent_with_runner(
        project_id=project_id,
        agent=agent,
        instructions=instructions,
        scenario_input=scenario.input,
        mode=payload.mode,
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
        provider="anthropic" if runner_result.mode == "live" else "mock",
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
        create_trace_ref_record(
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


@app.get("/api/projects/{project_id}/runs/{run_id}")
def get_run(project_id: str, run_id: str) -> RunRecord:
    get_project_or_404(project_id)
    return get_run_or_404(project_id, run_id)


@app.get("/api/projects/{project_id}/trace-refs")
def list_trace_refs(
    project_id: str,
    agent_design_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> List[TraceRef]:
    get_project_or_404(project_id)
    trace_refs = [
        trace_ref
        for trace_ref in _trace_refs.values()
        if trace_ref.project_id == project_id
        and (agent_design_id is None or trace_ref.agent_design_id == agent_design_id)
        and (run_id is None or trace_ref.run_id == run_id)
    ]
    return sorted(trace_refs, key=lambda trace_ref: trace_ref.created_at, reverse=True)


@app.post("/api/projects/{project_id}/trace-refs", status_code=201)
def create_trace_ref(project_id: str, payload: TraceRefCreate) -> TraceRef:
    get_project_or_404(project_id)
    return create_trace_ref_record(
        project_id=project_id,
        payload=payload,
        now=datetime.now(timezone.utc),
    )


@app.get("/api/projects/{project_id}/trace-refs/{trace_ref_id}")
def get_trace_ref(project_id: str, trace_ref_id: str) -> TraceRef:
    get_project_or_404(project_id)
    return get_trace_ref_or_404(project_id, trace_ref_id)


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
        scenario = create_scenario(
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
        contract = create_eval_contract(
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


@app.post("/api/projects/{project_id}/runs/{run_id}/evaluate", status_code=201)
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
            judge_output_text, judge_model, token_usage = run_live_judge(
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
    artifact = create_artifact(
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
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=evidence_artifact_id,
            relationship_type="GENERATED_FROM",
            now=now,
        )
    contract_artifact = find_artifact_by_type_and_artifact_id("EVAL_CONTRACT", contract.id)
    if contract_artifact is not None:
        link_artifacts(
            project_id=project_id,
            source_artifact_id=artifact.id,
            target_artifact_id=contract_artifact.id,
            relationship_type="SUPPORTED_BY",
            now=now,
        )

    judge_artifact = create_artifact(
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
    link_artifacts(
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
        create_failure_packet_record(
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


@app.get("/api/projects/{project_id}/eval-results/{eval_result_id}")
def get_eval_result(project_id: str, eval_result_id: str) -> EvalResult:
    get_project_or_404(project_id)
    return get_eval_result_or_404(project_id, eval_result_id)


@app.get("/api/projects/{project_id}/eval-results")
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


@app.get("/api/projects/{project_id}/judge-outputs")
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


@app.post("/api/projects/{project_id}/failure-diagnosis")
def diagnose_failure(
    project_id: str,
    payload: FailureDiagnosisRequest,
) -> FailureDiagnosis:
    get_project_or_404(project_id)
    eval_result = get_eval_result_or_404(project_id, payload.eval_result_id)
    contract = _eval_contracts.get(eval_result.eval_contract_id)
    run = _runs.get(eval_result.run_id)

    judge_output = next(
        (j for j in _judge_outputs.values() if j.eval_result_id == eval_result.id),
        None,
    )
    judge_text = judge_output.output if judge_output else ""

    failed_check_summaries = []
    for check_result in eval_result.checks:
        if not check_result.passed:
            summary = f"- {check_result.check_id} ({check_result.check_type})"
            if check_result.comment:
                summary += f": {check_result.comment}"
            elif check_result.observed:
                summary += f": observed={check_result.observed}"
            failed_check_summaries.append(summary)

    rubric = ""
    if contract:
        for check in contract.checks:
            if check.get("type") == "rubric_judge" and check.get("value"):
                rubric = check["value"]
                break

    run_output = run.output if run else ""

    prompt = (
        "You are helping a developer debug why an AI agent failed an evaluation.\n\n"
        f"Agent run output:\n{run_output[:1500]}\n\n"
        f"Success criteria (rubric): {rubric or 'Not specified.'}\n\n"
        f"Failed checks:\n" + ("\n".join(failed_check_summaries) or "None listed.") + "\n\n"
        f"Judge verdict:\n{judge_text[:1500]}\n\n"
        "Based on this evidence, provide:\n"
        "1. failure_mode: a short phrase naming what went wrong (e.g. 'missed rollback step', 'hallucinated tool call')\n"
        "2. severity: one of low / medium / high\n"
        "3. review_note: one or two sentences explaining why the response failed and what specifically needs to change\n\n"
        "Respond as JSON only: {\"failure_mode\": \"...\", \"severity\": \"...\", \"review_note\": \"...\"}"
    )

    try:
        config = anthropic_config_from_env()
        response = _anthropic_client(config).messages.create(
            model=config.model,
            max_tokens=400,
            system="You diagnose AI agent evaluation failures. Respond with JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw = block.text.strip()
                break
        import json as _json
        data = _json.loads(raw)
        return {
            "failure_mode": str(data.get("failure_mode", "")),
            "severity": str(data.get("severity", "medium")),
            "review_note": str(data.get("review_note", "")),
            "judge_output": judge_text,
        }
    except Exception as exc:
        return {
            "failure_mode": "",
            "severity": "medium",
            "review_note": "",
            "judge_output": judge_text,
        }


@app.get("/api/projects/{project_id}/failure-packets")
def list_failure_packets(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[FailurePacket]:
    get_project_or_404(project_id)
    failure_packets = [
        failure_packet
        for failure_packet in _failure_packets.values()
        if failure_packet.project_id == project_id
        and (
            agent_design_id is None
            or failure_packet.agent_design_id == agent_design_id
        )
    ]
    return sorted(
        failure_packets,
        key=lambda failure_packet: failure_packet.updated_at,
        reverse=True,
    )


@app.post("/api/projects/{project_id}/failure-packets", status_code=201)
def create_failure_packet(
    project_id: str,
    payload: FailurePacketCreate,
) -> FailurePacket:
    get_project_or_404(project_id)
    get_agent_design_or_404(project_id, payload.agent_design_id)
    run = _runs.get(payload.run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found.")
    eval_result = get_eval_result_or_404(project_id, payload.eval_result_id)
    contract = get_eval_contract_or_404(project_id, payload.eval_contract_id)
    if (
        run.agent_design_id != payload.agent_design_id
        or eval_result.run_id != run.id
        or contract.agent_design_id != payload.agent_design_id
    ):
        raise HTTPException(
            status_code=400,
            detail="Failure packet references must belong to the same evaluated run.",
        )
    for evidence_artifact_id in payload.evidence_artifact_ids:
        get_artifact_or_404(project_id, evidence_artifact_id)

    return create_failure_packet_record(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        agent_version_id=payload.agent_version_id,
        run_id=payload.run_id,
        eval_result_id=payload.eval_result_id,
        eval_contract_id=payload.eval_contract_id,
        failed_check_ids=payload.failed_check_ids,
        title=payload.title.strip(),
        diagnosis=payload.diagnosis.strip(),
        severity=payload.severity.strip(),
        evidence_artifact_ids=payload.evidence_artifact_ids,
        recommended_fix=payload.recommended_fix.strip(),
        status=payload.status.strip(),
        now=datetime.now(timezone.utc),
    )


@app.get("/api/projects/{project_id}/failure-packets/{failure_packet_id}")
def get_failure_packet(project_id: str, failure_packet_id: str) -> FailurePacket:
    get_project_or_404(project_id)
    return get_failure_packet_or_404(project_id, failure_packet_id)


@app.patch("/api/projects/{project_id}/failure-packets/{failure_packet_id}")
def update_failure_packet(
    project_id: str,
    failure_packet_id: str,
    payload: FailurePacketUpdate,
) -> FailurePacket:
    get_project_or_404(project_id)
    existing = get_failure_packet_or_404(project_id, failure_packet_id)
    updated = existing.model_copy(
        update={
            "title": payload.title.strip() if payload.title is not None else existing.title,
            "diagnosis": (
                payload.diagnosis.strip()
                if payload.diagnosis is not None
                else existing.diagnosis
            ),
            "severity": (
                payload.severity.strip()
                if payload.severity is not None
                else existing.severity
            ),
            "recommended_fix": (
                payload.recommended_fix.strip()
                if payload.recommended_fix is not None
                else existing.recommended_fix
            ),
            "status": payload.status.strip() if payload.status is not None else existing.status,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    _failure_packets[updated.id] = updated
    store.save_record("failure_packets", updated.id, updated)
    return updated


@app.get("/api/projects/{project_id}/fix-proposals")
def list_fix_proposals(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[FixProposal]:
    get_project_or_404(project_id)
    fix_proposals = [
        fix_proposal
        for fix_proposal in _fix_proposals.values()
        if fix_proposal.project_id == project_id
        and (
            agent_design_id is None
            or fix_proposal.agent_design_id == agent_design_id
        )
    ]
    return sorted(
        fix_proposals,
        key=lambda fix_proposal: fix_proposal.updated_at,
        reverse=True,
    )


@app.post("/api/projects/{project_id}/fix-proposals/generate")
def generate_fix_proposal(
    project_id: str,
    payload: FixProposalGenerateRequest,
) -> FixProposalGenerated:
    get_project_or_404(project_id)
    agent = get_agent_design_or_404(project_id, payload.agent_design_id)
    version = _agent_versions.get(payload.target_version_id)
    if version is None or version.project_id != project_id:
        raise HTTPException(status_code=404, detail="Agent version not found.")
    packets = [
        _failure_packets[pid]
        for pid in payload.addressed_failure_packet_ids
        if pid in _failure_packets and _failure_packets[pid].project_id == project_id
    ]
    contract = _eval_contracts.get(payload.validation_contract_id) if payload.validation_contract_id else None

    rubric_text = ""
    if contract:
        for check in contract.checks:
            if check.get("type") == "rubric_judge" and check.get("value"):
                rubric_text = check["value"]
                break

    failure_lines = []
    for p in packets:
        failure_lines.append(f"- Failure: {p.title}")
        failure_lines.append(f"  Diagnosis: {p.diagnosis}")
        failure_lines.append(f"  Severity: {p.severity}")
        if p.recommended_fix:
            failure_lines.append(f"  Suggested fix direction: {p.recommended_fix}")
    failure_summary = "\n".join(failure_lines) or "No failure packets provided."

    human_note = (payload.failure_description or "").strip()
    prompt = (
        f"You are improving an AI agent's instructions after a failed evaluation.\n\n"
        f"Agent name: {agent.name}\n"
        f"Agent intent: {agent.intent}\n"
        f"Allowed tools: {', '.join(agent.allowed_tool_names) or 'none'}\n\n"
        f"Current instructions ({version.version_label}):\n{version.instructions}\n\n"
        f"What failed:\n{failure_summary}\n\n"
        + (f"Human diagnosis: {human_note}\n\n" if human_note else "")
        + f"Success criteria (rubric): {rubric_text or 'Not specified.'}\n\n"
        f"Write improved instructions for the next version that directly address the failure. "
        f"Prioritise the human diagnosis above all else if provided. "
        f"Keep everything that worked. Fix only what caused the failure. "
        f"If tools are available, be explicit about when and how to use them. "
        f"Return only the instructions text — no preamble, no explanation, no headers."
    )

    try:
        config = anthropic_config_from_env()
        response = _anthropic_client(config).messages.create(
            model=config.model,
            max_tokens=1200,
            system="You write precise AI agent instructions. Return only the instruction text.",
            messages=[{"role": "user", "content": prompt}],
        )
        proposed_instructions = ""
        for block in response.content:
            if hasattr(block, "text"):
                proposed_instructions = block.text.strip()
                break
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM fix generation failed: {exc}") from exc

    rationale = (
        f"Generated fix addressing: {'; '.join(p.title for p in packets)}."
        if packets else "Generated fix from failure context."
    )
    return {"proposed_instructions": proposed_instructions, "rationale": rationale}


@app.post("/api/projects/{project_id}/fix-proposals", status_code=201)
def create_fix_proposal(
    project_id: str,
    payload: FixProposalCreate,
) -> FixProposal:
    get_project_or_404(project_id)
    validate_fix_proposal_references(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        target_version_id=payload.target_version_id,
        addressed_failure_packet_ids=payload.addressed_failure_packet_ids,
        validation_contract_ids=payload.validation_contract_ids,
    )
    return create_fix_proposal_record(
        project_id=project_id,
        agent_design_id=payload.agent_design_id,
        target_version_id=payload.target_version_id,
        title=payload.title.strip(),
        rationale=payload.rationale.strip(),
        proposed_changes=payload.proposed_changes,
        addressed_failure_packet_ids=payload.addressed_failure_packet_ids,
        validation_contract_ids=payload.validation_contract_ids,
        status=payload.status.strip(),
        now=datetime.now(timezone.utc),
    )


@app.get("/api/projects/{project_id}/fix-proposals/{fix_proposal_id}")
def get_fix_proposal(project_id: str, fix_proposal_id: str) -> FixProposal:
    get_project_or_404(project_id)
    return get_fix_proposal_or_404(project_id, fix_proposal_id)


@app.patch("/api/projects/{project_id}/fix-proposals/{fix_proposal_id}")
def update_fix_proposal(
    project_id: str,
    fix_proposal_id: str,
    payload: FixProposalUpdate,
) -> FixProposal:
    get_project_or_404(project_id)
    existing = get_fix_proposal_or_404(project_id, fix_proposal_id)
    target_version_id = existing.target_version_id
    addressed_failure_packet_ids = existing.addressed_failure_packet_ids
    validation_contract_ids = existing.validation_contract_ids
    if payload.addressed_failure_packet_ids is not None:
        addressed_failure_packet_ids = payload.addressed_failure_packet_ids
    if payload.validation_contract_ids is not None:
        validation_contract_ids = payload.validation_contract_ids
    validate_fix_proposal_references(
        project_id=project_id,
        agent_design_id=existing.agent_design_id,
        target_version_id=target_version_id,
        addressed_failure_packet_ids=addressed_failure_packet_ids,
        validation_contract_ids=validation_contract_ids,
    )
    updated = existing.model_copy(
        update={
            "title": payload.title.strip() if payload.title is not None else existing.title,
            "rationale": (
                payload.rationale.strip()
                if payload.rationale is not None
                else existing.rationale
            ),
            "proposed_changes": (
                payload.proposed_changes
                if payload.proposed_changes is not None
                else existing.proposed_changes
            ),
            "addressed_failure_packet_ids": addressed_failure_packet_ids,
            "validation_contract_ids": validation_contract_ids,
            "status": payload.status.strip() if payload.status is not None else existing.status,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    _fix_proposals[updated.id] = updated
    store.save_record("fix_proposals", updated.id, updated)
    for artifact_id in updated.artifact_ids:
        artifact = _artifacts.get(artifact_id)
        if artifact is not None:
            updated_artifact = artifact.model_copy(
                update={
                    "title": updated.title,
                    "body": fix_proposal_artifact_body(updated),
                    "updated_at": updated.updated_at,
                }
            )
            _artifacts[updated_artifact.id] = updated_artifact
            store.save_record("artifacts", updated_artifact.id, updated_artifact)
    return updated


@app.post("/api/projects/{project_id}/comparisons", status_code=201)
def create_comparison(
    project_id: str,
    payload: ComparisonCreate,
) -> Comparison:
    get_project_or_404(project_id)
    baseline_run = get_run_or_404(project_id, payload.baseline_run_id)
    candidate_run = get_run_or_404(project_id, payload.candidate_run_id)
    contract = get_eval_contract_or_404(project_id, payload.eval_contract_id)
    if baseline_run.agent_design_id != candidate_run.agent_design_id:
        raise HTTPException(
            status_code=400,
            detail="Comparison runs must belong to the same agent design.",
        )
    if contract.agent_design_id != baseline_run.agent_design_id:
        raise HTTPException(
            status_code=400,
            detail="Comparison eval contract must belong to the same agent design.",
        )
    if baseline_run.scenario_id != candidate_run.scenario_id:
        raise HTTPException(
            status_code=400,
            detail="Comparison runs must use the same scenario.",
        )
    if contract.scenario_id is not None and contract.scenario_id != baseline_run.scenario_id:
        raise HTTPException(
            status_code=400,
            detail="Comparison eval contract must match the compared scenario.",
        )

    baseline_eval_result = find_eval_result_for_run(
        project_id=project_id,
        run_id=baseline_run.id,
        eval_contract_id=contract.id,
    )
    candidate_eval_result = find_eval_result_for_run(
        project_id=project_id,
        run_id=candidate_run.id,
        eval_contract_id=contract.id,
    )
    if baseline_eval_result is None or candidate_eval_result is None:
        raise HTTPException(
            status_code=400,
            detail="Comparison requires both runs to be evaluated against the contract.",
        )

    return create_comparison_record(
        project_id=project_id,
        baseline_run=baseline_run,
        candidate_run=candidate_run,
        eval_contract_id=contract.id,
        baseline_eval_result=baseline_eval_result,
        candidate_eval_result=candidate_eval_result,
        now=datetime.now(timezone.utc),
    )


@app.get("/api/projects/{project_id}/comparisons")
def list_comparisons(
    project_id: str,
    agent_design_id: Optional[str] = None,
) -> List[Comparison]:
    get_project_or_404(project_id)
    comparisons = [
        comparison
        for comparison in _comparisons.values()
        if comparison.project_id == project_id
        and (
            agent_design_id is None
            or comparison.agent_design_id == agent_design_id
        )
    ]
    return sorted(comparisons, key=lambda comparison: comparison.created_at, reverse=True)


@app.get("/api/projects/{project_id}/comparisons/{comparison_id}")
def get_comparison(project_id: str, comparison_id: str) -> Comparison:
    get_project_or_404(project_id)
    return get_comparison_or_404(project_id, comparison_id)


@app.post("/api/projects/{project_id}/agent-designs/{agent_id}/runs", status_code=201)
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
    runner_result, artifact, tool_artifacts = run_agent_with_runner(
        project_id=project_id,
        agent=agent,
        instructions=agent.intent,
        scenario_input=payload.scenario_input,
        mode=payload.mode,
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
                "provider": "anthropic" if runner_result.mode == "live" else "mock",
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


@app.get("/api/projects/{project_id}/tools")
def list_tool_definitions(project_id: str) -> List[ToolDefinition]:
    get_project_or_404(project_id)
    tools = [tool for tool in _tool_definitions.values() if tool.project_id == project_id]
    return sorted(tools, key=lambda tool: tool.name)


@app.post("/api/projects/{project_id}/tools", status_code=201)
def create_tool_definition(project_id: str, payload: ToolDefinitionCreate) -> ToolDefinition:
    get_project_or_404(project_id)
    name = payload.name.strip()
    existing_names = {
        tool.name
        for tool in _tool_definitions.values()
        if tool.project_id == project_id
    }
    if name in existing_names:
        raise HTTPException(status_code=409, detail="Tool name already exists.")
    validate_json_schema_object(payload.input_schema, "input_schema")
    if payload.output_schema is not None:
        validate_json_schema_object(payload.output_schema, "output_schema")
    validate_json_schema_object(payload.config_schema, "config_schema")

    now = datetime.now(timezone.utc)
    tool = ToolDefinition(
        id=f"tool_{uuid4().hex[:12]}",
        project_id=project_id,
        name=name,
        description=payload.description.strip(),
        input_schema=payload.input_schema or {"type": "object", "properties": {}},
        output_schema=payload.output_schema,
        output_description=payload.output_description.strip(),
        implementation_kind=payload.implementation_kind,
        implementation_key=payload.implementation_key.strip(),
        config_schema=payload.config_schema,
        mock_response=payload.mock_response,
        status=payload.status,
        created_at=now,
        updated_at=now,
    )
    _tool_definitions[tool.id] = tool
    store.save_record("tool_definitions", tool.id, tool)
    upsert_tool_definition_artifact(tool, now)
    return tool


@app.patch("/api/projects/{project_id}/tools/{tool_id}")
def update_tool_definition(
    project_id: str,
    tool_id: str,
    payload: ToolDefinitionUpdate,
) -> ToolDefinition:
    get_project_or_404(project_id)
    existing = _tool_definitions.get(tool_id)
    if existing is None or existing.project_id != project_id:
        raise HTTPException(status_code=404, detail="Tool not found.")
    if payload.status is None:
        return existing

    now = datetime.now(timezone.utc)
    updated = existing.model_copy(update={"status": payload.status, "updated_at": now})
    _tool_definitions[updated.id] = updated
    store.save_record("tool_definitions", updated.id, updated)
    upsert_tool_definition_artifact(updated, now)
    return updated


@app.delete("/api/projects/{project_id}/tools/{tool_id}", status_code=204, response_model=None)
def delete_tool_definition(project_id: str, tool_id: str) -> None:
    get_project_or_404(project_id)
    existing = _tool_definitions.get(tool_id)
    if existing is None or existing.project_id != project_id:
        raise HTTPException(status_code=404, detail="Tool not found.")
    del _tool_definitions[tool_id]
    store.delete_record("tool_definitions", tool_id)
    # Remove this tool from any agent's allowlist
    for agent in list(_agent_designs.values()):
        if agent.project_id == project_id and existing.name in agent.allowed_tool_names:
            updated_names = [n for n in agent.allowed_tool_names if n != existing.name]
            now = datetime.now(timezone.utc)
            updated_agent = agent.model_copy(update={"allowed_tool_names": updated_names, "updated_at": now})
            _agent_designs[agent.id] = updated_agent
            store.save_record("agent_designs", agent.id, updated_agent)


@app.get("/api/projects/{project_id}/tools/{tool_id}/adapter-contracts")
def get_tool_adapter_contracts(
    project_id: str,
    tool_id: str,
) -> ToolAdapterContract:
    get_project_or_404(project_id)
    tool = _tool_definitions.get(tool_id)
    if tool is None or tool.project_id != project_id:
        raise HTTPException(status_code=404, detail="Tool not found.")
    return tool_adapter_contract(tool)


@app.post("/api/projects/{project_id}/artifacts/{artifact_id}/evaluate", status_code=201)
def evaluate_run_artifact(project_id: str, artifact_id: str) -> EvalRunResult:
    get_project_or_404(project_id)
    run_artifact = get_artifact_or_404(project_id, artifact_id)
    if run_artifact.artifact_type != "RUN_RESULT" or run_artifact.agent_design_id is None:
        raise HTTPException(status_code=400, detail="Only run result artifacts can be evaluated.")

    checks = evaluate_run_text(run_artifact.body)
    score = sum(1 for check in checks if check.passed)
    passed = score == len(checks)
    now = datetime.now(timezone.utc)
    eval_id = f"eval_{uuid4().hex[:12]}"
    check_lines = "\n".join(
        f"- {check.id}: {'pass' if check.passed else 'fail'} - {check.comment}"
        for check in checks
    )
    artifact = ArtifactRecord(
        id=f"artifact_{uuid4().hex[:12]}",
        project_id=project_id,
        artifact_type="EVAL_RESULT",
        artifact_id=eval_id,
        title=f"Eval: {run_artifact.title.replace('Run: ', '')}",
        body=f"Score\n{score}/{len(checks)}\n\nResult\n{'Passed' if passed else 'Failed'}\n\nChecks\n{check_lines}",
        source="judge:mock",
        agent_design_id=run_artifact.agent_design_id,
        created_at=now,
        updated_at=now,
    )
    _artifacts[artifact.id] = artifact
    store.save_record("artifacts", artifact.id, artifact)

    link = ArtifactLink(
        id=f"link_{uuid4().hex[:12]}",
        project_id=project_id,
        source_artifact_id=artifact.id,
        target_artifact_id=run_artifact.id,
        relationship_type="GENERATED_FROM",
        created_at=now,
    )
    _artifact_links[link.id] = link
    store.save_record("artifact_links", link.id, link)

    return EvalRunResult(
        id=eval_id,
        project_id=project_id,
        agent_design_id=run_artifact.agent_design_id,
        run_artifact_id=run_artifact.id,
        mode="mock",
        score=score,
        passed=passed,
        checks=checks,
        artifact=artifact,
        created_at=now,
    )


@app.get("/api/projects/{project_id}/artifacts")
def list_project_artifacts(
    project_id: str,
    agent_design_id: Optional[str] = None,
    artifact_type: Optional[str] = None,
) -> List[ArtifactRecord]:
    get_project_or_404(project_id)
    artifacts = [
        artifact
        for artifact in _artifacts.values()
        if artifact.project_id == project_id
        and (agent_design_id is None or artifact.agent_design_id == agent_design_id)
        and (artifact_type is None or artifact.artifact_type == artifact_type)
    ]
    return sorted(artifacts, key=lambda artifact: artifact.updated_at, reverse=True)


@app.get("/api/projects/{project_id}/artifacts/search")
def search_project_artifacts(
    project_id: str,
    q: str = "",
    artifact_type: Optional[str] = None,
) -> List[ArtifactRecord]:
    get_project_or_404(project_id)
    query = q.strip().lower()
    artifacts = list_project_artifacts(project_id=project_id, artifact_type=artifact_type)
    if not query:
        return artifacts
    return [
        artifact
        for artifact in artifacts
        if query in artifact.title.lower() or query in artifact.body.lower()
    ]


@app.get("/api/projects/{project_id}/artifacts/{artifact_id}")
def get_project_artifact(project_id: str, artifact_id: str) -> ArtifactRecord:
    get_project_or_404(project_id)
    return get_artifact_or_404(project_id, artifact_id)


@app.post("/api/projects/{project_id}/artifact-links", status_code=201)
def create_artifact_link(project_id: str, payload: ArtifactLinkCreate) -> ArtifactLink:
    get_project_or_404(project_id)
    get_artifact_or_404(project_id, payload.source_artifact_id)
    get_artifact_or_404(project_id, payload.target_artifact_id)

    link = ArtifactLink(
        id=f"link_{uuid4().hex[:12]}",
        project_id=project_id,
        source_artifact_id=payload.source_artifact_id,
        target_artifact_id=payload.target_artifact_id,
        relationship_type=payload.relationship_type.strip().upper(),
        created_at=datetime.now(timezone.utc),
    )
    _artifact_links[link.id] = link
    store.save_record("artifact_links", link.id, link)
    return link


@app.get("/api/projects/{project_id}/artifacts/{artifact_id}/links")
def list_artifact_links(project_id: str, artifact_id: str) -> List[ArtifactLink]:
    get_project_or_404(project_id)
    get_artifact_or_404(project_id, artifact_id)
    links = [
        link
        for link in _artifact_links.values()
        if link.project_id == project_id
        and (
            link.source_artifact_id == artifact_id
            or link.target_artifact_id == artifact_id
        )
    ]
    return sorted(links, key=lambda link: link.created_at, reverse=True)


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
    artifacts = list_project_artifacts(
        project_id=project_id,
        agent_design_id=agent_design_id,
    )
    allowed_types = CONTEXT_PACK_ARTIFACT_TYPES.get(purpose.strip().upper())
    if allowed_types is None:
        return artifacts
    return [artifact for artifact in artifacts if artifact.artifact_type in allowed_types]


@app.post("/api/projects/{project_id}/context-packs")
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


@app.post("/api/projects/{project_id}/evidence-summaries", status_code=201)
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
            summary, model, token_usage = run_live_evidence_summary(prompt)
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
