import type { SavedTest, SuiteResult, SuiteTestOutcome } from "./types";

export const suiteOutcomeLabels: Record<SuiteTestOutcome, string> = {
  fixed: "Fixed",
  regressed: "Regressed",
  still_passing: "Still passing",
  still_failing: "Still failing",
};

/** One test's result on the version a suite result belongs to. */
export function suiteTestResult(
  suite: SuiteResult | undefined,
  scenarioId: string,
): SavedTest["latestResult"] | undefined {
  if (!suite) return undefined;
  const test = suite.tests.find((item) => item.scenario_id === scenarioId);
  if (!test) return undefined;
  if (!test.eval_result) return "not_run";
  return test.eval_result.passed ? "passed" : "failed";
}

/** A suite comparison needs both versions checked on every test. */
export function suiteIsComplete(suite: SuiteResult | undefined): boolean {
  return Boolean(suite && suite.total > 0 && suite.tests.every((test) => test.eval_result));
}
