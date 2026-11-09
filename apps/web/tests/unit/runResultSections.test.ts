import assert from "node:assert/strict";
import { test } from "node:test";
import { runResultSections } from "../../src/runResultSections.ts";

// The RUN_RESULT body the API writes for an agent run (apps/api/edd_platform_api/routers/runs.py).
const brief = [
  "Here is the complete triage brief:",
  "",
  "## Summary",
  "Customer cannot log in after the password reset.",
  "",
  "## Priority",
  "High",
].join("\n");

test("keeps a multi-paragraph response whole", () => {
  const body = `Response\n${brief}\n\nScenario\nA customer is locked out.\n\nTools\n- lookup: ok`;
  assert.deepEqual(runResultSections(body), {
    response: brief,
    scenario: "A customer is locked out.",
  });
});

test("keeps a multi-paragraph scenario whole", () => {
  const body = "Response\nDone.\n\nScenario\nFirst line.\n\nSecond paragraph.\n\nTools\n";
  assert.deepEqual(runResultSections(body), {
    response: "Done.",
    scenario: "First line.\n\nSecond paragraph.",
  });
});

test("reads a URL run, which has no scenario", () => {
  const body = "Response\nGET returned 200.\n\nURL\nhttps://example.com\n\nStatus\n200";
  assert.deepEqual(runResultSections(body), { response: "GET returned 200.", scenario: "" });
});

test("returns null for a body that is not a run result", () => {
  assert.equal(runResultSections("Just some text."), null);
});
