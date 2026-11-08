export type TestRevisionCalls<S extends { id: string }, C> = {
  createScenario: () => Promise<S>;
  createContract: (scenarioId: string) => Promise<C>;
  setScenarioStatus: (scenarioId: string, status: "draft" | "active" | "superseded") => Promise<unknown>;
};

/**
 * Save a test, or a new revision of one, so at most one revision is active.
 * The previous revision is superseded first; if the new scenario or its eval
 * contract cannot be saved, the previous revision is made active again and a
 * new scenario left without a contract is set back to draft.
 */
export async function saveTestRevision<S extends { id: string }, C>(
  calls: TestRevisionCalls<S, C>,
  previousScenarioId?: string,
): Promise<{ scenario: S; contract: C }> {
  if (previousScenarioId) {
    await calls.setScenarioStatus(previousScenarioId, "superseded");
  }
  try {
    const scenario = await calls.createScenario();
    try {
      return { scenario, contract: await calls.createContract(scenario.id) };
    } catch (err) {
      await calls.setScenarioStatus(scenario.id, "draft").catch(() => undefined);
      throw err;
    }
  } catch (err) {
    if (previousScenarioId) {
      await calls.setScenarioStatus(previousScenarioId, "active").catch(() => undefined);
    }
    throw err;
  }
}
