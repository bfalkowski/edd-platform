import type { EvalContract, FailurePacket, FixProposal, RunRecord, Scenario } from "./types";

/**
 * A scenario's test contract: the given contract when it fits the scenario,
 * else its newest own contract (one naming the scenario), else its default
 * contract. A contract that names another scenario never fits (a run refuses
 * such a contract). `contracts` is one agent's, newest first. Without a given
 * contract this matches `active_tests` in apps/api/edd_platform_api/routers/suites.py.
 */
export function testContract(
  scenario: Scenario | undefined,
  contracts: EvalContract[],
  contractId?: string,
): EvalContract | undefined {
  if (!scenario) {
    return undefined;
  }
  const fits = (item: EvalContract) => !item.scenario_id || item.scenario_id === scenario.id;
  return (
    contracts.find((item) => item.id === contractId && fits(item)) ??
    contracts.find((item) => item.scenario_id === scenario.id) ??
    contracts.find((item) => item.id === scenario.default_eval_contract_id && fits(item))
  );
}

/**
 * One test's failure packets: those from its contract on runs of its scenario.
 * Scenarios can share a default contract, so the contract alone is not enough.
 */
export function testFailurePackets(
  packets: FailurePacket[],
  runs: RunRecord[],
  scenarioId: string | undefined,
  contractId: string | undefined,
): FailurePacket[] {
  const scenarioByRun = new Map(runs.map((run) => [run.id, run.scenario_id]));
  return packets.filter(
    (packet) =>
      packet.eval_contract_id === contractId && scenarioByRun.get(packet.run_id) === scenarioId,
  );
}

/** One test's fix proposal: one validated by its contract that addresses one of its failure packets. */
export function testFixProposal(
  proposals: FixProposal[],
  testPackets: FailurePacket[],
  contractId: string | undefined,
): FixProposal | undefined {
  const packetIds = new Set(testPackets.map((packet) => packet.id));
  return proposals.find(
    (proposal) =>
      contractId !== undefined &&
      proposal.validation_contract_ids.includes(contractId) &&
      proposal.addressed_failure_packet_ids.some((id) => packetIds.has(id)),
  );
}
