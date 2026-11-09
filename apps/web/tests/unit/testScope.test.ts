import assert from "node:assert/strict";
import { test } from "node:test";
import { testContract, testFailurePackets, testFixProposal } from "../../src/testScope.ts";
import type { EvalContract, FailurePacket, FixProposal, RunRecord, Scenario } from "../../src/types.ts";

// Scenarios A and B share contract C. A failed on run_a, and fix_a addresses A's packet.
const runs = [
  { id: "run_a", scenario_id: "scenario_a" },
  { id: "run_b", scenario_id: "scenario_b" },
] as RunRecord[];
const packetA = { id: "packet_a", run_id: "run_a", eval_contract_id: "contract_c" } as FailurePacket;
const packetB = { id: "packet_b", run_id: "run_b", eval_contract_id: "contract_c" } as FailurePacket;
const otherContract = { id: "packet_x", run_id: "run_b", eval_contract_id: "contract_x" } as FailurePacket;
const fixA = {
  id: "fix_a",
  addressed_failure_packet_ids: ["packet_a"],
  validation_contract_ids: ["contract_c"],
} as FixProposal;

test("a test's failure packets come only from runs of its scenario on its contract", () => {
  const packets = [packetA, packetB, otherContract];
  assert.deepEqual(testFailurePackets(packets, runs, "scenario_a", "contract_c"), [packetA]);
  assert.deepEqual(testFailurePackets(packets, runs, "scenario_b", "contract_c"), [packetB]);
  assert.deepEqual(testFailurePackets(packets, runs, undefined, undefined), []);
});

test("a scenario sharing a contract does not inherit another scenario's fix", () => {
  assert.equal(testFixProposal([fixA], [packetA], "contract_c"), fixA);
  assert.equal(testFixProposal([fixA], [], "contract_c"), undefined);
  assert.equal(testFixProposal([fixA], [packetB], "contract_c"), undefined);
});

test("a fix validated by another contract is not the test's fix", () => {
  assert.equal(testFixProposal([fixA], [packetA], "contract_x"), undefined);
  assert.equal(testFixProposal([fixA], [packetA], undefined), undefined);
});

// An older console saved two contracts on scenario S; the list is newest first.
const scenarioS = { id: "scenario_s", default_eval_contract_id: null } as Scenario;
const newerContract = { id: "contract_new", scenario_id: "scenario_s" } as EvalContract;
const olderContract = { id: "contract_old", scenario_id: "scenario_s" } as EvalContract;

test("a test's contract is the one asked for, so wizard resume reads the wizard's own contract", () => {
  const contracts = [newerContract, olderContract];
  assert.equal(testContract(scenarioS, contracts, "contract_old"), olderContract);
  assert.equal(testContract(scenarioS, contracts), newerContract);
  assert.equal(testContract(scenarioS, contracts, "contract_missing"), newerContract);
});
