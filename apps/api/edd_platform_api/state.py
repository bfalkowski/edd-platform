from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Type, TypeVar

from pydantic import BaseModel

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

ModelT = TypeVar("ModelT", bound=BaseModel)


class SnapshotDict(dict):
    """A dict whose loops run over a copy of its keys, values or items.

    FastAPI runs the sync routes on a thread pool, so one request can add or
    remove a record while another request loops over the same collection. A
    plain dict then fails that loop with "dictionary changed size during
    iteration". Copying in C first takes the snapshot without letting another
    thread run in between.
    """

    def __iter__(self):
        return iter(list(dict.keys(self)))

    def keys(self):
        return list(dict.keys(self))

    def values(self):
        return list(dict.values(self))

    def items(self):
        return list(dict.items(self))


def _load_shared_collection(collection: str, model: Type[ModelT]) -> Dict[str, ModelT]:
    return SnapshotDict(store.load_collection(collection, model))

seeded_at = datetime.now(timezone.utc)
default_project = Project(
    id="project_default",
    name="EDD Platform",
    description="Local EDD product workspace.",
    created_at=seeded_at,
    updated_at=seeded_at,
)
_projects: Dict[str, Project] = _load_shared_collection("projects", Project)
_agent_designs: Dict[str, AgentDesign] = _load_shared_collection("agent_designs", AgentDesign)
_scenarios: Dict[str, Scenario] = _load_shared_collection("scenarios", Scenario)
_eval_contracts: Dict[str, EvalContract] = _load_shared_collection("eval_contracts", EvalContract)
_judge_prompt_templates: Dict[str, JudgePromptTemplate] = _load_shared_collection(
    "judge_prompt_templates",
    JudgePromptTemplate,
)
_gate_definitions: Dict[str, GateDefinition] = _load_shared_collection(
    "gate_definitions",
    GateDefinition,
)
_gate_decisions: Dict[str, GateDecision] = _load_shared_collection(
    "gate_decisions",
    GateDecision,
)
_agent_versions: Dict[str, AgentVersion] = _load_shared_collection("agent_versions", AgentVersion)
_runs: Dict[str, RunRecord] = _load_shared_collection("runs", RunRecord)
_trace_refs: Dict[str, TraceRef] = _load_shared_collection("trace_refs", TraceRef)
_review_notes: Dict[str, ReviewNote] = _load_shared_collection("review_notes", ReviewNote)
_review_corpora: Dict[str, ReviewCorpus] = _load_shared_collection("review_corpora", ReviewCorpus)
_review_items: Dict[str, ReviewItem] = _load_shared_collection("review_items", ReviewItem)
_review_annotations: Dict[str, ReviewAnnotation] = _load_shared_collection(
    "review_annotations",
    ReviewAnnotation,
)
_failure_modes: Dict[str, FailureMode] = _load_shared_collection("failure_modes", FailureMode)
_agent_suggestions: Dict[str, AgentSuggestion] = _load_shared_collection(
    "agent_suggestions",
    AgentSuggestion,
)
_eval_results: Dict[str, EvalResult] = _load_shared_collection("eval_results", EvalResult)
_judge_outputs: Dict[str, JudgeOutput] = _load_shared_collection("judge_outputs", JudgeOutput)
_failure_packets: Dict[str, FailurePacket] = _load_shared_collection("failure_packets", FailurePacket)
_fix_proposals: Dict[str, FixProposal] = _load_shared_collection("fix_proposals", FixProposal)
_comparisons: Dict[str, Comparison] = _load_shared_collection("comparisons", Comparison)
_artifacts: Dict[str, ArtifactRecord] = _load_shared_collection("artifacts", ArtifactRecord)
_artifact_links: Dict[str, ArtifactLink] = _load_shared_collection("artifact_links", ArtifactLink)
_tool_definitions: Dict[str, ToolDefinition] = _load_shared_collection("tool_definitions", ToolDefinition)
_evidence_summaries: Dict[str, EvidenceSummary] = _load_shared_collection(
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
