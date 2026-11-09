import { request } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { acquireLock } from "./machine-lock.ts";

/**
 * Wait until no other e2e suite is running on this machine, then warm up the
 * API. Several suites at once starve the browsers of CPU, and steps then time
 * out at random (T-107). The lock is released when the run ends.
 */
export default async function globalSetup() {
  const lockPath = join(tmpdir(), "edd-platform-e2e.lock");
  const release = await acquireLock(lockPath, {
    onWait: (holder) =>
      console.log(
        `Another e2e suite is running (pid ${holder.pid} in ${holder.cwd}); waiting for it to finish. ` +
          `If no such run exists, delete ${lockPath}.`,
      ),
  });
  try {
    await warmUpLiveRuns();
  } catch (error) {
    release();
    throw error;
  }
  return release;
}

/**
 * Make one live run before the tests start. The API imports its provider
 * libraries on the first live run, which takes seconds and, under five
 * parallel workers, can push whichever test gets there first past its timeout.
 * The warm-up agent is deleted afterwards so no test sees it. A reused API
 * (EDD_E2E_REUSE_SERVERS=1) is not ours to write to, so it is left alone.
 */
async function warmUpLiveRuns() {
  if (process.env.EDD_E2E_REUSE_SERVERS === "1") return;
  const apiPort = Number(process.env.EDD_E2E_API_PORT ?? 8091);
  const api = await request.newContext({
    baseURL: `http://127.0.0.1:${apiPort}/api/projects/project_default/`,
  });
  async function post<T>(path: string, data: object): Promise<T> {
    const response = await api.post(path, { data });
    if (!response.ok()) throw new Error(`Warm-up ${path}: ${response.status()} ${await response.text()}`);
    return response.json();
  }

  const { agent } = await post<{ agent: { id: string } }>("agent-designs", {
    name: "E2E warm-up agent",
    intent: "Warm up the API before the tests start.",
  });
  try {
    const scenario = await post<{ id: string }>("scenarios", {
      agent_design_id: agent.id,
      name: "Warm-up",
      input: "Warm up.",
    });
    await post("runs", { agent_design_id: agent.id, scenario_id: scenario.id, mode: "live" });
  } finally {
    await api.delete(`agent-designs/${agent.id}`);
    await api.dispose();
  }
}
