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
from edd_platform_api.seed_data import WEATHER_TOOL_ID, build_default_tool_definitions
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

for seeded_tool_definition in build_default_tool_definitions(default_project.id, seeded_at):
    existing_tool_definition = _tool_definitions.get(seeded_tool_definition.id)
    if existing_tool_definition is None or (
        seeded_tool_definition.id == WEATHER_TOOL_ID
        and existing_tool_definition.implementation_key == "local_weather_fixture"
    ):
        _tool_definitions[seeded_tool_definition.id] = seeded_tool_definition
        store.save_record(
            "tool_definitions",
            seeded_tool_definition.id,
            seeded_tool_definition,
        )
