import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { checkLabel, isRubricCheckType, labelledCheckTypes } from "../../src/checkLabel.ts";

// Every check type the API can put on an eval result: the types its evaluator
// branches on, its rubric check types, plus the type it gives a check that has none.
const evaluator = readFileSync(
  new URL("../../../api/edd_platform_api/eval_checks.py", import.meta.url),
  "utf8",
);
const apiRubricCheckTypes = [
  ...(/^RUBRIC_CHECK_TYPES = \(([^)]*)\)/m.exec(evaluator)?.[1] ?? "").matchAll(/"([a-z_]+)"/g),
].map((match) => match[1]);
const apiCheckTypes = [
  ...new Set([
    ...[...evaluator.matchAll(/check_type == "([a-z_]+)"/g)].map((match) => match[1]),
    ...apiRubricCheckTypes,
    "manual_review_required",
  ]),
];

test("the API's check types are the ones the console labels", () => {
  assert.ok(apiCheckTypes.length >= 6, `found only ${apiCheckTypes.join(", ")}`);
  assert.deepEqual([...apiCheckTypes].sort(), [...labelledCheckTypes].sort());
});

for (const checkType of apiCheckTypes) {
  test(`${checkType} gets a human-readable label, with or without an expected value`, () => {
    for (const expected of ["rollback plan", ""]) {
      const label = checkLabel({ check_id: "satisfies_rubric", check_type: checkType, expected });
      assert.notEqual(label, "satisfies_rubric");
      assert.doesNotMatch(label, /_/);
      assert.match(label, /^[A-Z]/);
    }
  });
}

test("the console's rubric check types are the API's", () => {
  assert.ok(apiRubricCheckTypes.includes("rubric_judge"), `found only ${apiRubricCheckTypes.join(", ")}`);
  for (const checkType of apiCheckTypes) {
    assert.equal(isRubricCheckType(checkType), apiRubricCheckTypes.includes(checkType), checkType);
  }
});

test("labels name what the check expects", () => {
  assert.equal(checkLabel({ check_id: "satisfies_rubric", check_type: "rubric_judge" }), "Rubric judge");
  assert.equal(checkLabel({ check_id: "satisfies_rubric", check_type: "llm_judge" }), "Rubric judge");
  assert.equal(
    checkLabel({ check_id: "rollback_plan", check_type: "output_contains", expected: "rollback plan" }),
    "Includes “rollback plan”",
  );
  assert.equal(
    checkLabel({ check_id: "requires_tool_search", check_type: "tool_called", expected: "search" }),
    "Calls search",
  );
});

test("a wizard output requirement check is labelled with the requirement", () => {
  assert.equal(
    checkLabel({ check_id: "requires_output_2", check_type: "output_contains" }, ["First", "Second"]),
    "Second",
  );
});

test("an unknown check type falls back to a readable form of the ID", () => {
  assert.equal(checkLabel({ check_id: "custom_policy_check", check_type: "something_new" }), "Custom policy check");
  assert.equal(checkLabel({ check_id: "outcome_rubric" }), "Outcome rubric");
});
