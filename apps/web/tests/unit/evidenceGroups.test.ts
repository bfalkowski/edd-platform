import assert from "node:assert/strict";
import { test } from "node:test";
import { evidenceRunIndex, groupEvidence } from "../../src/evidenceGroups.ts";
import type { ArtifactRecord, EvalResult, FailurePacket, RunRecord } from "../../src/types.ts";

function artifact(
  id: string,
  artifact_type: string,
  created_at: string,
  extra: Partial<ArtifactRecord> = {},
): ArtifactRecord {
  return { id, artifact_type, artifact_id: `${id}_record`, body: "", created_at, ...extra } as ArtifactRecord;
}

// Two runs as the API saves them: run output, tool call/result and trace, then eval, judge and failure.
const artifacts = [
  artifact("scenario", "SCENARIO", "2026-11-01T00:00:00Z"),
  artifact("contract", "EVAL_CONTRACT", "2026-11-01T00:00:01Z"),
  artifact("run_a", "RUN_RESULT", "2026-11-02T00:00:00Z", { artifact_id: "run_a_id" }),
  artifact("call_a", "TOOL_CALL", "2026-11-02T00:00:00Z"),
  artifact("result_a", "TOOL_RESULT", "2026-11-02T00:00:00Z"),
  artifact("judge_a", "JUDGE_OUTPUT", "2026-11-02T00:00:02Z"),
  artifact("eval_a", "EVAL_RESULT", "2026-11-02T00:00:01Z"),
  artifact("failure_a", "FAILURE_PACKET", "2026-11-02T00:00:03Z", { artifact_id: "packet_a" }),
  artifact("run_b", "RUN_RESULT", "2026-11-03T00:00:00Z", { artifact_id: "run_b_id" }),
  // Added later through /trace-refs, so only its body names the run.
  artifact("trace_b", "TRACE_REF", "2026-11-03T00:00:05Z", {
    body: "Provider\nlangfuse\n\nRun\nrun_b_id\n\nURL\nhttp://trace",
  }),
  artifact("design", "AGENT_DESIGN", "2026-11-01T00:00:02Z"),
];

const runs = [
  { id: "run_a_id", artifact_ids: ["run_a", "call_a", "result_a"] },
  { id: "run_b_id", artifact_ids: ["run_b"] },
] as RunRecord[];
const evalResults = [{ run_id: "run_a_id", artifact_ids: ["eval_a", "judge_a"] }] as EvalResult[];
const failurePackets = [{ id: "packet_a", run_id: "run_a_id" }] as FailurePacket[];

const ids = (rows: ArtifactRecord[]) => rows.map((row) => row.id);

test("agent-level artifacts stay in their own section, in the order given", () => {
  const grouped = groupEvidence(artifacts, evidenceRunIndex(runs, evalResults, failurePackets));
  assert.deepEqual(ids(grouped.agentArtifacts), ["scenario", "contract", "design"]);
});

test("each run groups its output with its tool, eval, judge, failure and trace rows, newest run first", () => {
  const grouped = groupEvidence(artifacts, evidenceRunIndex(runs, evalResults, failurePackets));
  assert.deepEqual(
    grouped.runGroups.map((group) => [group.runId, ids(group.artifacts)]),
    [
      ["run_b_id", ["run_b", "trace_b"]],
      ["run_a_id", ["run_a", "call_a", "result_a", "eval_a", "judge_a", "failure_a"]],
    ],
  );
});

test("before the run records load, run outputs and Run lines still group by run", () => {
  const grouped = groupEvidence(artifacts, new Map());
  assert.deepEqual(
    grouped.runGroups.map((group) => [group.runId, ids(group.artifacts)]),
    [
      ["run_b_id", ["run_b", "trace_b"]],
      ["run_a_id", ["run_a"]],
    ],
  );
});

test("before the eval and failure records load, judge and failure rows join the run of the eval saved with them", () => {
  const evaluatedAt = "2026-11-04T00:00:00Z";
  const rows = [
    artifact("run_c", "RUN_RESULT", "2026-11-04T00:00:00Z", { artifact_id: "run_c_id" }),
    artifact("eval_c", "EVAL_RESULT", evaluatedAt, { body: "Contract\nNames a next action\n\nRun\nrun_c_id" }),
    artifact("judge_c", "JUDGE_OUTPUT", evaluatedAt),
    artifact("failure_c", "FAILURE_PACKET", evaluatedAt),
    artifact("judge_orphan", "JUDGE_OUTPUT", "2026-11-05T00:00:00Z"),
  ];
  const grouped = groupEvidence(rows, new Map());
  assert.deepEqual(
    grouped.runGroups.map((group) => [group.runId, ids(group.artifacts)]),
    [["run_c_id", ["run_c", "eval_c", "judge_c", "failure_c"]]],
  );
  assert.deepEqual(ids(grouped.agentArtifacts), ["judge_orphan"]);
});

test("before the failure records load, a failure saved later joins the run its Run line names", () => {
  const rows = [
    artifact("run_d", "RUN_RESULT", "2026-11-06T00:00:00Z", { artifact_id: "run_d_id" }),
    artifact("eval_d", "EVAL_RESULT", "2026-11-06T00:00:01Z", { body: "Contract\nOne fix\n\nRun\nrun_d_id" }),
    // A reviewer overrule saves its failure later, with its own timestamp.
    artifact("failure_d", "FAILURE_PACKET", "2026-11-06T00:05:00Z", {
      body: "Run\nrun_d_id\n\nDiagnosis\nReviewer overruled the judge.",
    }),
  ];
  const grouped = groupEvidence(rows, new Map());
  assert.deepEqual(
    grouped.runGroups.map((group) => [group.runId, ids(group.artifacts)]),
    [["run_d_id", ["run_d", "eval_d", "failure_d"]]],
  );
  assert.deepEqual(ids(grouped.agentArtifacts), []);
});
