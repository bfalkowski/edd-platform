import assert from "node:assert/strict";
import { test } from "node:test";
import { proofLoopStep, type ProofLoopStep, type ProofLoopStepInput } from "../../src/proofLoopStep.ts";
import type { EddFlowState } from "../../src/types.ts";

// Only presence and `passed` matter to the step logic, so records are stubs.
const record = {} as never;
const evalResult = (passed: boolean) => ({ passed }) as never;

const failed: EddFlowState = {
  contract: record,
  baselineRun: record,
  baselineEval: evalResult(false),
  failurePackets: [],
};

const cases: [ProofLoopStep, ProofLoopStepInput][] = [
  ["create_test", { flow: { failurePackets: [] }, analysisSaved: false, fixGenerated: false }],
  ["run_baseline", { flow: { contract: record, failurePackets: [] }, analysisSaved: false, fixGenerated: false }],
  [
    "check_baseline",
    { flow: { contract: record, baselineRun: record, failurePackets: [] }, analysisSaved: false, fixGenerated: false },
  ],
  ["baseline_passed", { flow: { ...failed, baselineEval: evalResult(true) }, analysisSaved: false, fixGenerated: false }],
  ["save_analysis", { flow: failed, analysisSaved: false, fixGenerated: false }],
  // The dead end this guards: no failure packets loaded must still offer Generate fix.
  ["generate_fix", { flow: failed, analysisSaved: true, fixGenerated: false }],
  ["save_fix", { flow: failed, analysisSaved: true, fixGenerated: true }],
  ["create_version", { flow: { ...failed, fixProposal: record }, analysisSaved: true, fixGenerated: true }],
  [
    "run_candidate",
    { flow: { ...failed, fixProposal: record, candidateVersion: record }, analysisSaved: true, fixGenerated: true },
  ],
  [
    "check_candidate",
    {
      flow: { ...failed, fixProposal: record, candidateVersion: record, candidateRun: record },
      analysisSaved: true,
      fixGenerated: true,
    },
  ],
  [
    "compare",
    {
      flow: {
        ...failed,
        fixProposal: record,
        candidateVersion: record,
        candidateRun: record,
        candidateEval: evalResult(true),
      },
      analysisSaved: true,
      fixGenerated: true,
    },
  ],
  [
    "candidate_passed",
    {
      flow: {
        ...failed,
        fixProposal: record,
        candidateVersion: record,
        candidateRun: record,
        candidateEval: evalResult(true),
        comparison: record,
      },
      analysisSaved: true,
      fixGenerated: true,
    },
  ],
  [
    "candidate_failed",
    {
      flow: {
        ...failed,
        fixProposal: record,
        candidateVersion: record,
        candidateRun: record,
        candidateEval: evalResult(false),
        comparison: record,
      },
      analysisSaved: true,
      fixGenerated: true,
    },
  ],
];

for (const [expected, input] of cases) {
  test(`proof loop step: ${expected}`, () => {
    assert.equal(proofLoopStep(input), expected);
  });
}

test("every step is covered", () => {
  const all: Record<ProofLoopStep, true> = {
    create_test: true,
    run_baseline: true,
    check_baseline: true,
    baseline_passed: true,
    save_analysis: true,
    generate_fix: true,
    save_fix: true,
    create_version: true,
    run_candidate: true,
    check_candidate: true,
    compare: true,
    candidate_passed: true,
    candidate_failed: true,
  };
  assert.deepEqual(new Set(cases.map(([step]) => step)), new Set(Object.keys(all)));
});
