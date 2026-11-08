import assert from "node:assert/strict";
import { test } from "node:test";
import { saveTestRevision, type TestRevisionCalls } from "../../src/saveTestRevision.ts";

type Fail = "scenario" | "contract" | "supersede" | undefined;

/** Fake API that tracks scenario statuses, failing the named call. */
function fakeApi(fail: Fail) {
  const statuses = new Map<string, string>([["old", "active"]]);
  const calls: TestRevisionCalls<{ id: string }, { id: string }> = {
    createScenario: async () => {
      if (fail === "scenario") throw new Error("scenario failed");
      statuses.set("new", "active");
      return { id: "new" };
    },
    createContract: async () => {
      if (fail === "contract") throw new Error("contract failed");
      return { id: "contract" };
    },
    setScenarioStatus: async (id, status) => {
      if (fail === "supersede" && status === "superseded") throw new Error("supersede failed");
      statuses.set(id, status);
    },
  };
  const active = () => [...statuses].filter(([, status]) => status === "active").map(([id]) => id);
  return { calls, active };
}

test("an edit leaves only the new revision active", async () => {
  const api = fakeApi(undefined);
  const saved = await saveTestRevision(api.calls, "old");
  assert.equal(saved.scenario.id, "new");
  assert.deepEqual(api.active(), ["new"]);
});

for (const fail of ["scenario", "contract", "supersede"] as const) {
  test(`a failed ${fail} call during an edit leaves only the old revision active`, async () => {
    const api = fakeApi(fail);
    await assert.rejects(saveTestRevision(api.calls, "old"), new RegExp(`${fail} failed`));
    assert.deepEqual(api.active(), ["old"]);
  });
}

test("a failed contract call on a new test does not leave the new scenario active", async () => {
  const api = fakeApi("contract");
  await assert.rejects(saveTestRevision(api.calls), /contract failed/);
  assert.deepEqual(api.active(), ["old"]);
});
