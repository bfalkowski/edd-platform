import type { FailurePacket, FixProposal, RunRecord } from "./types";

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
