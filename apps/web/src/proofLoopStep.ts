import type { AgentVersion, EddFlowState, FixProposal } from "./types";

/** Where one proof loop iteration stands. Every step but the two finished ones has an action. */
export type ProofLoopStep =
  | "create_test"
  | "run_baseline"
  | "check_baseline"
  | "baseline_passed"
  | "save_analysis"
  | "generate_fix"
  | "save_fix"
  | "create_version"
  | "run_candidate"
  | "check_candidate"
  | "compare"
  | "candidate_passed"
  | "candidate_failed";

export type ProofLoopStepInput = {
  flow: EddFlowState;
  analysisSaved: boolean;
  fixGenerated: boolean;
};

export function proofLoopStep({ flow, analysisSaved, fixGenerated }: ProofLoopStepInput): ProofLoopStep {
  if (!flow.contract) return "create_test";
  if (!flow.baselineRun) return "run_baseline";
  if (!flow.baselineEval) return "check_baseline";
  if (flow.baselineEval.passed) return "baseline_passed";
  if (!analysisSaved) return "save_analysis";
  if (!flow.fixProposal) return fixGenerated ? "save_fix" : "generate_fix";
  if (!flow.candidateVersion) return "create_version";
  if (!flow.candidateRun) return "run_candidate";
  if (!flow.candidateEval) return "check_candidate";
  if (!flow.comparison) return "compare";
  return flow.candidateEval.passed ? "candidate_passed" : "candidate_failed";
}

/** A version built from a fix other than this test's own, so not this test's candidate. */
export function builtFromAnotherFix(version: AgentVersion, fixProposal: FixProposal | undefined): boolean {
  return Boolean(fixProposal && version.source_fix_proposal_id && version.source_fix_proposal_id !== fixProposal.id);
}
