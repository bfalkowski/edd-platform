import { useEffect, useState } from "react";
import { getSuiteResult } from "./api";
import { dropRunError, keepRunErrors } from "./suite";
import type { AgentVersion, SavedTest, SuiteResult } from "./types";

/**
 * Each version's latest result on every test, read from saved runs. Refetched
 * when the saved-test list reloads, which happens after every run and check.
 * Old results stay until new ones arrive, so the counts do not flicker.
 * A suite run's per-test errors are kept across the refetch (see keepRunErrors)
 * until a run or check of that one test drops them (clearRunError).
 */
export function useSuiteResults(
  projectId: string,
  agentId: string,
  versions: AgentVersion[],
  savedTests: SavedTest[],
  setError: (message: string | null) => void,
): [
  Record<string, SuiteResult>,
  (result: SuiteResult) => void,
  (versionId: string | null, scenarioId: string) => void,
] {
  const [results, setResults] = useState<Record<string, SuiteResult>>({});
  // Right after an agent switch the versions can still be the last agent's,
  // until the new agent's context loads; asking for those would 404.
  const versionKey = versions
    .filter((version) => version.agent_design_id === agentId)
    .map((version) => version.id)
    .join(",");

  useEffect(() => {
    let isCurrent = true;
    const versionIds = versionKey ? versionKey.split(",") : [];
    // Fetched even with no saved tests: an empty suite marks an old comparison out of date.
    if (versionIds.length === 0) {
      setResults({});
      return;
    }
    Promise.all(versionIds.map((versionId) => getSuiteResult(projectId, agentId, versionId)))
      .then((loaded) => {
        if (isCurrent) {
          setResults((items) =>
            Object.fromEntries(
              loaded.map((result) => [
                result.agent_version_id,
                keepRunErrors(items[result.agent_version_id], result),
              ]),
            ),
          );
        }
      })
      .catch((err: Error) => {
        if (isCurrent) {
          setError(err.message);
        }
      });
    return () => {
      isCurrent = false;
    };
    // setError is a state setter from the parent and never changes.
  }, [projectId, agentId, versionKey, savedTests]);

  function setResult(result: SuiteResult) {
    setResults((items) => ({ ...items, [result.agent_version_id]: result }));
  }

  function clearRunError(versionId: string | null, scenarioId: string) {
    if (!versionId) return;
    setResults((items) =>
      items[versionId] ? { ...items, [versionId]: dropRunError(items[versionId], scenarioId) } : items,
    );
  }

  return [results, setResult, clearRunError];
}
