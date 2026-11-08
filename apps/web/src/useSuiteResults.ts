import { useEffect, useState } from "react";
import { getSuiteResult } from "./api";
import type { AgentVersion, SavedTest, SuiteResult } from "./types";

/**
 * Each version's latest result on every test, read from saved runs. Refetched
 * when the saved-test list reloads, which happens after every run and check.
 * Old results stay until new ones arrive, so the counts do not flicker.
 */
export function useSuiteResults(
  projectId: string,
  agentId: string,
  versions: AgentVersion[],
  savedTests: SavedTest[],
  setError: (message: string | null) => void,
): [Record<string, SuiteResult>, (result: SuiteResult) => void] {
  const [results, setResults] = useState<Record<string, SuiteResult>>({});
  const versionKey = versions.map((version) => version.id).join(",");

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
          setResults(Object.fromEntries(loaded.map((result) => [result.agent_version_id, result])));
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

  return [results, setResult];
}
