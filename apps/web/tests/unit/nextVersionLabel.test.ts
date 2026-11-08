import assert from "node:assert/strict";
import { test } from "node:test";
import { nextVersionLabel } from "../../src/nextVersionLabel.ts";

test("adds one to the version number instead of appending a digit", () => {
  assert.equal(nextVersionLabel("v0"), "v1");
  assert.equal(nextVersionLabel("v9"), "v10");
});

test("treats a label with no number as v0", () => {
  assert.equal(nextVersionLabel("baseline"), "v1");
});
