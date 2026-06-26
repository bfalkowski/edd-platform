from __future__ import annotations

from fastapi import HTTPException

from edd_platform_api.schemas import (
    AgentDesign,
    AgentSuggestion,
    AgentVersion,
    ArtifactRecord,
    Comparison,
    EvalContract,
    EvalResult,
    FailureMode,
    FailurePacket,
    FixProposal,
    GateDecision,
    GateDefinition,
    JudgePromptTemplate,
    Project,
    ReviewAnnotation,
    ReviewCorpus,
    ReviewItem,
    ReviewNote,
    RunRecord,
    Scenario,
    TraceRef,
)
from edd_platform_api.state import (
    _agent_designs,
    _agent_suggestions,
    _agent_versions,
    _artifacts,
    _comparisons,
    _eval_contracts,
    _eval_results,
    _failure_modes,
    _failure_packets,
    _fix_proposals,
    _gate_decisions,
    _gate_definitions,
    _judge_prompt_templates,
    _projects,
    _review_annotations,
    _review_corpora,
    _review_items,
    _review_notes,
    _runs,
    _scenarios,
    _trace_refs,
)


def get_project_or_404(project_id: str) -> Project:
    project = _projects.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def get_artifact_or_404(project_id: str, artifact_id: str) -> ArtifactRecord:
    artifact = _artifacts.get(artifact_id)
    if artifact is None or artifact.project_id != project_id:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return artifact


def get_agent_design_or_404(project_id: str, agent_id: str) -> AgentDesign:
    agent = _agent_designs.get(agent_id)
    if agent is None or agent.project_id != project_id:
        raise HTTPException(status_code=404, detail="Agent design not found.")
    return agent


def get_scenario_or_404(project_id: str, scenario_id: str) -> Scenario:
    scenario = _scenarios.get(scenario_id)
    if scenario is None or scenario.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    return scenario


def get_eval_contract_or_404(project_id: str, contract_id: str) -> EvalContract:
    contract = _eval_contracts.get(contract_id)
    if contract is None or contract.project_id != project_id:
        raise HTTPException(status_code=404, detail="Eval contract not found.")
    return contract


def get_judge_prompt_template_or_404(
    project_id: str,
    judge_prompt_template_id: str,
) -> JudgePromptTemplate:
    template = _judge_prompt_templates.get(judge_prompt_template_id)
    if template is None or template.project_id != project_id:
        raise HTTPException(status_code=404, detail="Judge prompt template not found.")
    return template


def get_gate_definition_or_404(project_id: str, gate_id: str) -> GateDefinition:
    gate = _gate_definitions.get(gate_id)
    if gate is None or gate.project_id != project_id:
        raise HTTPException(status_code=404, detail="Gate definition not found.")
    return gate


def get_gate_decision_or_404(project_id: str, decision_id: str) -> GateDecision:
    decision = _gate_decisions.get(decision_id)
    if decision is None or decision.project_id != project_id:
        raise HTTPException(status_code=404, detail="Gate decision not found.")
    return decision


def get_agent_version_or_404(project_id: str, version_id: str) -> AgentVersion:
    version = _agent_versions.get(version_id)
    if version is None or version.project_id != project_id:
        raise HTTPException(status_code=404, detail="Agent version not found.")
    return version


def get_eval_result_or_404(project_id: str, eval_result_id: str) -> EvalResult:
    eval_result = _eval_results.get(eval_result_id)
    if eval_result is None or eval_result.project_id != project_id:
        raise HTTPException(status_code=404, detail="Eval result not found.")
    return eval_result


def get_trace_ref_or_404(project_id: str, trace_ref_id: str) -> TraceRef:
    trace_ref = _trace_refs.get(trace_ref_id)
    if trace_ref is None or trace_ref.project_id != project_id:
        raise HTTPException(status_code=404, detail="Trace reference not found.")
    return trace_ref


def get_review_note_or_404(project_id: str, review_note_id: str) -> ReviewNote:
    review_note = _review_notes.get(review_note_id)
    if review_note is None or review_note.project_id != project_id:
        raise HTTPException(status_code=404, detail="Review note not found.")
    return review_note


def get_review_corpus_or_404(project_id: str, corpus_id: str) -> ReviewCorpus:
    corpus = _review_corpora.get(corpus_id)
    if corpus is None or corpus.project_id != project_id:
        raise HTTPException(status_code=404, detail="Review corpus not found.")
    return corpus


def get_review_item_or_404(project_id: str, review_item_id: str) -> ReviewItem:
    item = _review_items.get(review_item_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(status_code=404, detail="Review item not found.")
    return item


def get_review_annotation_or_404(
    project_id: str,
    annotation_id: str,
) -> ReviewAnnotation:
    annotation = _review_annotations.get(annotation_id)
    if annotation is None or annotation.project_id != project_id:
        raise HTTPException(status_code=404, detail="Review annotation not found.")
    return annotation


def get_failure_mode_or_404(project_id: str, failure_mode_id: str) -> FailureMode:
    failure_mode = _failure_modes.get(failure_mode_id)
    if failure_mode is None or failure_mode.project_id != project_id:
        raise HTTPException(status_code=404, detail="Failure mode not found.")
    return failure_mode


def get_agent_suggestion_or_404(
    project_id: str,
    suggestion_id: str,
) -> AgentSuggestion:
    suggestion = _agent_suggestions.get(suggestion_id)
    if suggestion is None or suggestion.project_id != project_id:
        raise HTTPException(status_code=404, detail="Agent suggestion not found.")
    return suggestion


def get_failure_packet_or_404(project_id: str, failure_packet_id: str) -> FailurePacket:
    failure_packet = _failure_packets.get(failure_packet_id)
    if failure_packet is None or failure_packet.project_id != project_id:
        raise HTTPException(status_code=404, detail="Failure packet not found.")
    return failure_packet


def get_fix_proposal_or_404(project_id: str, fix_proposal_id: str) -> FixProposal:
    fix_proposal = _fix_proposals.get(fix_proposal_id)
    if fix_proposal is None or fix_proposal.project_id != project_id:
        raise HTTPException(status_code=404, detail="Fix proposal not found.")
    return fix_proposal


def get_comparison_or_404(project_id: str, comparison_id: str) -> Comparison:
    comparison = _comparisons.get(comparison_id)
    if comparison is None or comparison.project_id != project_id:
        raise HTTPException(status_code=404, detail="Comparison not found.")
    return comparison


def get_run_or_404(project_id: str, run_id: str) -> RunRecord:
    run = _runs.get(run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run
