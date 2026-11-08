import type { ArtifactRecord, EvalResult, FailurePacket, RunRecord } from "./types";

export type RunEvidenceGroup = {
  runId: string;
  artifacts: ArtifactRecord[];
};

export type GroupedEvidence = {
  agentArtifacts: ArtifactRecord[];
  runGroups: RunEvidenceGroup[];
};

/** How many runs the Evidence tab shows at first, and how many more each "show older" adds. */
export const RUN_PAGE_SIZE = 5;

// Order of rows inside one run: the output first, then what the run did, then how it was judged.
const RUN_ROW_ORDER = [
  "RUN_RESULT",
  "TOOL_CALL",
  "TOOL_RESULT",
  "TRACE_REF",
  "EVAL_RESULT",
  "JUDGE_OUTPUT",
  "FAILURE_PACKET",
];

// Artifact types whose body names their run on a "Run" line.
const RUN_LINE_TYPES = new Set(["TOOL_CALL", "TOOL_RESULT", "TRACE_REF", "EVAL_RESULT"]);

/** Map each artifact id that belongs to a run onto that run's id, from the run-owned records. */
export function evidenceRunIndex(
  runs: RunRecord[],
  evalResults: EvalResult[],
  failurePackets: FailurePacket[],
): Map<string, string> {
  const index = new Map<string, string>();
  for (const run of runs) {
    for (const artifactId of run.artifact_ids) index.set(artifactId, run.id);
  }
  for (const evalResult of evalResults) {
    for (const artifactId of evalResult.artifact_ids) index.set(artifactId, evalResult.run_id);
  }
  // A failure artifact records its packet's id as artifact_id; keyed apart so ids cannot collide.
  for (const packet of failurePackets) index.set(`FAILURE_PACKET:${packet.id}`, packet.run_id);
  return index;
}

function runIdOf(artifact: ArtifactRecord, runIndex: Map<string, string>): string | null {
  const indexed =
    runIndex.get(artifact.id) ?? runIndex.get(`${artifact.artifact_type}:${artifact.artifact_id}`);
  if (indexed) return indexed;
  // A run output artifact records its run's id as artifact_id.
  if (artifact.artifact_type === "RUN_RESULT") return artifact.artifact_id;
  if (RUN_LINE_TYPES.has(artifact.artifact_type)) {
    const match = artifact.body.match(/(?:^|\n)Run\n(.+)/);
    if (match) return match[1].trim();
  }
  return null;
}

/**
 * Split an agent's evidence into agent-level artifacts and one group per run.
 * Runs come newest first, by when their first artifact was saved.
 */
export function groupEvidence(
  artifacts: ArtifactRecord[],
  runIndex: Map<string, string>,
): GroupedEvidence {
  const agentArtifacts: ArtifactRecord[] = [];
  const byRun = new Map<string, ArtifactRecord[]>();
  for (const artifact of artifacts) {
    const runId = runIdOf(artifact, runIndex);
    if (runId === null) {
      agentArtifacts.push(artifact);
      continue;
    }
    byRun.set(runId, [...(byRun.get(runId) ?? []), artifact]);
  }
  const rank = (artifact: ArtifactRecord) => {
    const position = RUN_ROW_ORDER.indexOf(artifact.artifact_type);
    return position === -1 ? RUN_ROW_ORDER.length : position;
  };
  const startedAt = (group: ArtifactRecord[]) =>
    group.map((artifact) => artifact.created_at).sort()[0];
  const runGroups = [...byRun.entries()]
    .sort(([, a], [, b]) => startedAt(b).localeCompare(startedAt(a)))
    .map(([runId, group]) => ({
      runId,
      artifacts: [...group].sort(
        (a, b) => rank(a) - rank(b) || a.created_at.localeCompare(b.created_at),
      ),
    }));
  return { agentArtifacts, runGroups };
}
