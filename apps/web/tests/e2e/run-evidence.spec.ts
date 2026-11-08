import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const PROJECT = "/api/projects/project_default";

async function postJson<T>(request: APIRequestContext, path: string, data: object): Promise<T> {
  const response = await request.post(`${PROJECT}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

/** Create an agent with a scenario and contract, then seed runs through the API. */
async function seedAgent(
  request: APIRequestContext,
  runs: { live: number; mock: number },
): Promise<{ name: string; id: string; liveRunIds: string[] }> {
  const name = `Evidence Agent ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const { agent } = await postJson<{ agent: { id: string } }>(request, "/agent-designs", {
    name,
    intent: "Answer support questions with a safe next action.",
  });
  const scenario = await postJson<{ id: string }>(request, "/scenarios", {
    agent_design_id: agent.id,
    name: "Support question",
    input: "A deployment failed. What should I do?",
  });
  const contract = await postJson<{ id: string }>(request, "/eval-contracts", {
    agent_design_id: agent.id,
    name: "Names a next action",
    scenario_id: scenario.id,
    checks: [{ id: "next_action", type: "output_contains", value: "next action" }],
  });
  const modes = [...Array(runs.live).fill("live"), ...Array(runs.mock).fill("mock")];
  const liveRunIds: string[] = [];
  for (const mode of modes) {
    const run = await postJson<{ id: string }>(request, "/runs", {
      agent_design_id: agent.id,
      scenario_id: scenario.id,
      eval_contract_id: contract.id,
      mode,
    });
    await postJson(request, `/runs/${run.id}/evaluate`, { judge_mode: "deterministic" });
    if (mode === "live") liveRunIds.push(run.id);
  }
  return { name, id: agent.id, liveRunIds };
}

async function openAgent(page: Page, name: string) {
  await page.goto("/");
  await page.getByRole("region", { name: "Agent designs" }).getByText(name).click();
  await expect(page.getByRole("tablist", { name: "Agent workspace" })).toBeVisible();
}

function evidenceRows(page: Page, label: string) {
  return page.locator(".workflow-evidence-item > span").filter({ hasText: new RegExp(`^${label}$`) });
}

test("Evidence tab lists every run output, eval result and judge output", async ({ page, request }) => {
  const agent = await seedAgent(request, { live: 3, mock: 0 });
  await openAgent(page, agent.name);

  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(evidenceRows(page, "Run output")).toHaveCount(3);
  await expect(evidenceRows(page, "Eval result")).toHaveCount(3);
  await expect(evidenceRows(page, "Judge output")).toHaveCount(3);
});

test("Pull in new runs adds one review item per live run, once", async ({ page, request }) => {
  const agent = await seedAgent(request, { live: 3, mock: 1 });
  // A Langfuse-traced run: the trace link lives on a separate TRACE_REF artifact.
  const tracedRunId = agent.liveRunIds[0];
  await postJson(request, "/trace-refs", {
    provider: "langfuse",
    external_trace_id: "trace-e2e-1",
    run_id: tracedRunId,
    url: "http://langfuse.local/trace/trace-e2e-1",
  });
  await openAgent(page, agent.name);

  await page.getByRole("tab", { name: "Error analysis" }).click();
  await page.getByRole("button", { name: "Pull in new runs" }).click();
  await expect(page.getByText("Added 3 runs to the review set.")).toBeVisible();
  await expect(page.getByText("3 items")).toBeVisible();

  await page.getByRole("button", { name: "Pull in new runs" }).click();
  await expect(page.getByText("All live runs are already in the review set.")).toBeVisible();
  await expect(page.getByText("3 items")).toBeVisible();

  const corpora = await (
    await request.get(`${PROJECT}/review-corpora?agent_design_id=${agent.id}`)
  ).json();
  const items = await (
    await request.get(`${PROJECT}/review-items?corpus_id=${corpora[0].id}`)
  ).json();
  expect(items).toHaveLength(3);
  const traced = items.filter(
    (item: { langfuse_ref: { trace_id: string } | null }) => item.langfuse_ref !== null,
  );
  expect(traced).toHaveLength(1);
  expect(traced[0].langfuse_ref.trace_id).toBe("trace-e2e-1");
  expect(traced[0].langfuse_ref.url).toBe("http://langfuse.local/trace/trace-e2e-1");
});

test("No live runs: the message shows on Error analysis only", async ({ page, request }) => {
  const agent = await seedAgent(request, { live: 0, mock: 1 });
  await openAgent(page, agent.name);

  await page.getByRole("tab", { name: "Error analysis" }).click();
  await page.getByRole("button", { name: "Pull in new runs" }).click();
  const message = page.getByText(/This agent has no live runs yet\. Run a test with a live model/);
  await expect(message).toBeVisible();
  await expect(page.getByText("0 items")).toBeVisible();

  await page.getByRole("tab", { name: "Agent", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Agent", exact: true })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(message).toHaveCount(0);
});
