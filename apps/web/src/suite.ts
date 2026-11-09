import type { Comparison, SavedTest, SuiteResult, SuiteTestOutcome } from "./types";

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

/** Why a test failed to run or be judged in the latest suite run, if it did. */
export function suiteTestError(suite: SuiteResult | undefined, scenarioId: string): string | null {
  return suite?.tests.find((item) => item.scenario_id === scenarioId)?.error ?? null;
}

/**
 * Only a suite run's response has per-test errors; the saved-result read does
 * not. Keep a test's error from the earlier result while the test still has the
 * same eval it had then. A newer eval on that test means the error is old.
 */
export function keepRunErrors(earlier: SuiteResult | undefined, loaded: SuiteResult): SuiteResult {
  if (!earlier) return loaded;
  return {
    ...loaded,
    tests: loaded.tests.map((test) => {
      const before = earlier.tests.find((item) => item.scenario_id === test.scenario_id);
      const sameEval = (before?.eval_result?.id ?? null) === (test.eval_result?.id ?? null);
      return before?.error && sameEval ? { ...test, error: before.error } : test;
    }),
  };
}

/** A suite comparison needs both versions checked on every test. */
export function suiteIsComplete(suite: SuiteResult | undefined): boolean {
  return Boolean(suite && suite.total > 0 && suite.tests.every((test) => test.eval_result));
}

/**
 * A suite comparison is current while it covers exactly the tests the versions
 * have now, judged by the same evals. A test added later, or a rerun after the
 * comparison, makes it out of date. Unknown until both suite results load.
 */
export function suiteComparisonIsCurrent(
  comparison: Comparison,
  baseline: SuiteResult | undefined,
  candidate: SuiteResult | undefined,
): boolean | undefined {
  if (!baseline || !candidate) return undefined;
  const rows = comparison.tests ?? [];
  if (rows.length !== baseline.tests.length || rows.length !== candidate.tests.length) return false;
  return rows.every((row) => {
    const before = baseline.tests.find((test) => test.scenario_id === row.scenario_id);
    const after = candidate.tests.find((test) => test.scenario_id === row.scenario_id);
    return (
      before?.eval_result?.id === row.baseline_eval_result_id &&
      after?.eval_result?.id === row.candidate_eval_result_id
    );
  });
}
