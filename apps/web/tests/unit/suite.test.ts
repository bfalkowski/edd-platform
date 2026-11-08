import assert from "node:assert/strict";
import { test } from "node:test";
import { suiteIsComplete, suiteTestResult } from "../../src/suite.ts";
import type { EvalResult, SuiteResult } from "../../src/types.ts";

function suite(results: (boolean | null)[]): SuiteResult {
  return {
    agent_design_id: "agent",
    agent_version_id: "v1",
    passed: results.filter((passed) => passed === true).length,
    total: results.length,
    tests: results.map((passed, index) => ({
      scenario_id: `scenario_${index}`,
      eval_contract_id: `contract_${index}`,
      eval_result: passed === null ? null : ({ passed } as EvalResult),
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
