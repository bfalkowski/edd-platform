import assert from "node:assert/strict";
import { test } from "node:test";
import {
  dropRunError,
  keepRunErrors,
  suiteComparisonIsCurrent,
  suiteIsComplete,
  suiteTestResult,
} from "../../src/suite.ts";
import type { Comparison, EvalResult, SuiteResult } from "../../src/types.ts";

function suite(results: (boolean | null)[], version = "v1"): SuiteResult {
  return {
    agent_design_id: "agent",
    agent_version_id: version,
    passed: results.filter((passed) => passed === true).length,
    total: results.length,
    tests: results.map((passed, index) => ({
      scenario_id: `scenario_${index}`,
      eval_contract_id: `contract_${index}`,
      eval_result: passed === null ? null : ({ id: `${version}_eval_${index}`, passed } as EvalResult),
    })),
  };
}

test("a test's result on the suite's version", () => {
  const result = suite([true, false, null]);
  assert.equal(suiteTestResult(result, "scenario_0"), "passed");
  assert.equal(suiteTestResult(result, "scenario_1"), "failed");
  assert.equal(suiteTestResult(result, "scenario_2"), "not_run");
  assert.equal(suiteTestResult(result, "scenario_missing"), undefined);
  assert.equal(suiteTestResult(undefined, "scenario_0"), undefined);
});

test("a suite is complete only when every test has a result", () => {
  assert.equal(suiteIsComplete(suite([true, false])), true);
  assert.equal(suiteIsComplete(suite([true, null])), false);
  assert.equal(suiteIsComplete(suite([])), false);
  assert.equal(suiteIsComplete(undefined), false);
});

function comparisonOf(baseline: SuiteResult, candidate: SuiteResult): Comparison {
  return {
    tests: baseline.tests.map((test, index) => ({
      scenario_id: test.scenario_id,
      eval_contract_id: test.eval_contract_id,
      baseline_run_id: "run",
      candidate_run_id: "run",
      baseline_eval_result_id: test.eval_result?.id ?? "",
      candidate_eval_result_id: candidate.tests[index].eval_result?.id ?? "",
      outcome: "still_passing",
    })),
  } as Comparison;
}

test("a suite comparison is current only for the same tests and the same evals", () => {
  const v0 = suite([true, false], "v0");
  const v1 = suite([true, true], "v1");
  const comparison = comparisonOf(v0, v1);
  assert.equal(suiteComparisonIsCurrent(comparison, v0, v1), true);
  assert.equal(suiteComparisonIsCurrent(comparison, v0, undefined), undefined);

  // A test added after the comparison.
  assert.equal(suiteComparisonIsCurrent(comparison, suite([true, false, null], "v0"), v1), false);

  // A rerun after the comparison: a newer eval on one test.
  const rerun = suite([true, true], "v1");
  rerun.tests[1] = { ...rerun.tests[1], eval_result: { id: "v1_eval_rerun", passed: true } as EvalResult };
  assert.equal(suiteComparisonIsCurrent(comparison, v0, rerun), false);
});

test("a run error stays after a reload of the suite result until that test gets a new eval", () => {
  const run = suite([true, null, false]);
  run.tests[1] = { ...run.tests[1], error: "Provider timed out." };
  run.tests[2] = { ...run.tests[2], error: "Judge timed out." };

  // The saved-result read never has errors; the run's errors are kept.
  const loaded = keepRunErrors(run, suite([true, null, false]));
  assert.deepEqual(
    loaded.tests.map((test) => test.error ?? null),
    [null, "Provider timed out.", "Judge timed out."],
  );

  // A later eval on a test clears its error; the other test keeps its own.
  const rerun = suite([true, true, false]);
  rerun.tests[1] = { ...rerun.tests[1], eval_result: { id: "v1_eval_new", passed: true } as EvalResult };
  assert.deepEqual(
    keepRunErrors(loaded, rerun).tests.map((test) => test.error ?? null),
    [null, null, "Judge timed out."],
  );

  // Nothing to keep without an earlier result.
  assert.deepEqual(
    keepRunErrors(undefined, suite([null])).tests.map((test) => test.error ?? null),
    [null],
  );
});

test("a single-test run or check drops that test's suite-run error only", () => {
  const run = suite([null, false]);
  run.tests[0] = { ...run.tests[0], error: "Provider timed out." };
  run.tests[1] = { ...run.tests[1], error: "Judge timed out." };

  const dropped = dropRunError(run, "scenario_0");
  assert.deepEqual(
    dropped.tests.map((test) => test.error ?? null),
    [null, "Judge timed out."],
  );
  // A reload of the saved result does not bring the dropped error back.
  assert.deepEqual(
    keepRunErrors(dropped, suite([null, false])).tests.map((test) => test.error ?? null),
    [null, "Judge timed out."],
  );
});
