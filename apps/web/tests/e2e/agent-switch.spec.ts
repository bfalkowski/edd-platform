import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

async function createAgent(request: APIRequestContext, label: string) {
  const name = `${label} ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const response = await request.post("/api/projects/project_default/agent-designs", {
    data: { name, intent: "Answer support questions with a safe next action." },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  const { agent } = (await response.json()) as { agent: { id: string } };
  return { id: agent.id, name };
}

test("a failed load for a previously selected agent shows no error on the new one", async ({
  page,
  request,
}) => {
  const oldAgent = await createAgent(request, "Superseded Agent");
  const newAgent = await createAgent(request, "Current Agent");

  // Hold the old agent's gate request until the person has moved on, then fail it.
  let releaseOldLoad: () => void = () => {};
  const oldLoadReleased = new Promise<void>((resolve) => {
    releaseOldLoad = resolve;
  });
  let oldLoadStarted: () => void = () => {};
  const oldLoadSeen = new Promise<void>((resolve) => {
    oldLoadStarted = resolve;
  });
  await page.route(`**/gates?agent_design_id=${oldAgent.id}`, async (route) => {
    oldLoadStarted();
    await oldLoadReleased;
    await route.fulfill({ status: 500, json: { detail: "Old agent load failed" } });
  });

  await page.goto("/");
  const agents = page.getByRole("region", { name: "Agent designs" });
  await agents.getByText(oldAgent.name).click();
  await oldLoadSeen;

  await agents.getByText(newAgent.name).click();
  await page.getByRole("tab", { name: "Agent" }).click();
  await expect(page.getByRole("heading", { name: newAgent.name })).toBeVisible();

  releaseOldLoad();
  // Wait until the page has handled (and dropped) every one of the old agent's loads.
  await expect(page.locator(`main[data-settled-stale-agent-id="${oldAgent.id}"]`)).toHaveCount(1);

  await expect(page.getByRole("heading", { name: newAgent.name })).toBeVisible();
  await expect(page.locator(".error-text")).toHaveCount(0);
});

test("an error shown for one agent is cleared when switching to another", async ({ page, request }) => {
  const failingAgent = await createAgent(request, "Failing Agent");
  const otherAgent = await createAgent(request, "Other Agent");

  await page.route(`**/gates?agent_design_id=${failingAgent.id}`, (route) =>
    route.fulfill({ status: 500, json: { detail: "Failing agent load failed" } }),
  );

  await page.goto("/");
  const agents = page.getByRole("region", { name: "Agent designs" });
  // Pick the tab first: changing tabs clears the error on its own.
  await agents.getByText(otherAgent.name).click();
  await page.getByRole("tab", { name: "Agent" }).click();
  await agents.getByText(failingAgent.name).click();
  await expect(page.getByRole("heading", { name: failingAgent.name })).toBeVisible();
  await expect(page.locator(".error-text")).toContainText("Failing agent load failed");

  await agents.getByText(otherAgent.name).click();
  await expect(page.getByRole("heading", { name: otherAgent.name })).toBeVisible();
  await expect(page.locator(".error-text")).toHaveCount(0);
});

test("a failed saved-tests load for a previously selected agent shows no error on the new one", async ({
  page,
  request,
}) => {
  const oldAgent = await createAgent(request, "Superseded Tests Agent");
  const newAgent = await createAgent(request, "Current Tests Agent");

  // Hold the old agent's eval contract requests (the saved-tests list needs them)
  // until the person has moved on, then fail them.
  let releaseOldLoad: () => void = () => {};
  const oldLoadReleased = new Promise<void>((resolve) => {
    releaseOldLoad = resolve;
  });
  let oldLoadStarted: () => void = () => {};
  const oldLoadSeen = new Promise<void>((resolve) => {
    oldLoadStarted = resolve;
  });
  await page.route(`**/eval-contracts?agent_design_id=${oldAgent.id}`, async (route) => {
    oldLoadStarted();
    await oldLoadReleased;
    await route.fulfill({ status: 500, json: { detail: "Old saved tests load failed" } });
  });

  await page.goto("/");
  const agents = page.getByRole("region", { name: "Agent designs" });
  await agents.getByText(oldAgent.name).click();
  await oldLoadSeen;

  await agents.getByText(newAgent.name).click();
  await page.getByRole("tab", { name: "Agent" }).click();
  await expect(page.getByRole("heading", { name: newAgent.name })).toBeVisible();

  releaseOldLoad();
  // Wait until the page has handled (and dropped) every one of the old agent's loads.
  await expect(page.locator(`main[data-settled-stale-agent-id="${oldAgent.id}"]`)).toHaveCount(1);

  await expect(page.getByRole("heading", { name: newAgent.name })).toBeVisible();
  await expect(page.locator(".error-text")).toHaveCount(0);
});

test("suite results never ask for the last agent's versions while the new agent's load", async ({
  page,
  request,
}) => {
  const oldAgent = await createAgent(request, "Suite Old Agent");
  const newAgent = await createAgent(request, "Suite New Agent");
  const versionIds: Record<string, string> = {};
  for (const agent of [oldAgent, newAgent]) {
    const response = await request.post(
      `/api/projects/project_default/agent-designs/${agent.id}/versions`,
      {
        data: {
          version_label: "v0",
          instructions: "Answer support questions with a safe next action.",
          status: "baseline",
        },
      },
    );
    expect(response.ok(), await response.text()).toBeTruthy();
    versionIds[agent.id] = ((await response.json()) as { id: string }).id;
  }

  const suiteRequests: string[] = [];
  page.on("request", (req) => {
    if (req.url().endsWith("/suite-result")) {
      suiteRequests.push(new URL(req.url()).pathname);
    }
  });

  // Hold the new agent's version list so the page sits between the two agents.
  let releaseNewVersions: () => void = () => {};
  const newVersionsReleased = new Promise<void>((resolve) => {
    releaseNewVersions = resolve;
  });
  await page.route(`**/agent-designs/${newAgent.id}/versions`, async (route) => {
    await newVersionsReleased;
    await route.continue();
  });

  await page.goto("/");
  const agents = page.getByRole("region", { name: "Agent designs" });
  const oldSuiteLoaded = page.waitForResponse(
    `**/agent-designs/${oldAgent.id}/versions/${versionIds[oldAgent.id]}/suite-result`,
  );
  await agents.getByText(oldAgent.name).click();
  await page.getByRole("tab", { name: "Proof loop" }).click();
  await oldSuiteLoaded;

  await agents.getByText(newAgent.name).click();
  // Give any request built from the last agent's versions time to go out.
  await page.waitForTimeout(500);
  const newSuiteLoaded = page.waitForResponse(
    `**/agent-designs/${newAgent.id}/versions/${versionIds[newAgent.id]}/suite-result`,
  );
  releaseNewVersions();
  await newSuiteLoaded;

  const crossed = suiteRequests.filter(
    (path) =>
      path.includes(`/agent-designs/${newAgent.id}/`) && path.includes(versionIds[oldAgent.id]),
  );
  expect(crossed).toEqual([]);
  await expect(page.locator(".error-text")).toHaveCount(0);
});

/** An agent with one gate, and one review set holding one item. */
async function createAgentWithGateAndReviewSet(request: APIRequestContext, label: string) {
  const agent = await createAgent(request, label);
  const post = async (path: string, data: object) => {
    const response = await request.post(`/api/projects/project_default${path}`, { data });
    expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
    return (await response.json()) as { id: string };
  };
  await post("/gates", { agent_design_id: agent.id, name: `${agent.name} gate` });
  const corpus = await post("/review-corpora", {
    agent_design_id: agent.id,
    name: `${agent.name} review set`,
  });
  await post("/review-items", {
    corpus_id: corpus.id,
    source_kind: "trace",
    source_id: `trace-${agent.id}`,
    langfuse_ref: { trace_id: `trace-${agent.id}` },
    title: `${agent.name} review item`,
  });
  return agent;
}

/** Hold (or fail) the agent's gate and review set requests. Returns a release for held ones. */
async function stallReadinessAndReview(page: Page, agentId: string, mode: "hold" | "fail") {
  let release: () => void = () => {};
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  for (const path of [`**/gates?agent_design_id=${agentId}`, `**/review-corpora?agent_design_id=${agentId}`]) {
    await page.route(path, async (route) => {
      if (mode === "fail") {
        await route.fulfill({ status: 500, json: { detail: "Agent context unavailable" } });
        return;
      }
      await released;
      await route.continue();
    });
  }
  return release;
}

async function showOtherAgentThenSwitch(
  page: Page,
  other: { id: string; name: string },
  agent: { name: string },
  tab: "Readiness" | "Error analysis",
) {
  await page.goto(`/?agent=${other.id}`);
  await expect(page.locator(".agent-row.selected")).toHaveText(other.name);
  await page.getByRole("tab", { name: tab }).click();
  if (tab === "Readiness") {
    await expect(page.getByRole("heading", { name: "Gate ready" })).toBeVisible();
  } else {
    await expect(page.getByRole("heading", { name: `${other.name} review set` })).toBeVisible();
    await expect(page.getByText(`${other.name} review item`)).toBeVisible();
  }
  await page.getByRole("region", { name: "Agent designs" }).getByText(agent.name).click();
  await expect(page.locator(".agent-row.selected")).toHaveText(agent.name);
  await page.getByRole("tab", { name: tab }).click();
}

for (const mode of ["hold", "fail"] as const) {
  const when = mode === "hold" ? "while the selected agent's load is pending" : "when the selected agent's load fails";

  test(`Readiness tab shows no other agent's gate ${when}`, async ({ page, request }) => {
    const other = await createAgentWithGateAndReviewSet(request, "Gate Other Agent");
    const agent = await createAgent(request, "Gate Current Agent");
    const release = await stallReadinessAndReview(page, agent.id, mode);

    await showOtherAgentThenSwitch(page, other, agent, "Readiness");
    await expect(page.getByRole("heading", { name: "No gate yet" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Gate ready" })).toHaveCount(0);

    release();
    await expect(page.getByRole("heading", { name: "No gate yet" })).toBeVisible();
  });

  test(`Error analysis tab shows no other agent's review set ${when}`, async ({ page, request }) => {
    const other = await createAgentWithGateAndReviewSet(request, "Review Other Agent");
    const agent = await createAgent(request, "Review Current Agent");
    const release = await stallReadinessAndReview(page, agent.id, mode);

    await showOtherAgentThenSwitch(page, other, agent, "Error analysis");
    await expect(page.getByRole("heading", { name: "Discovery review" })).toBeVisible();
    await expect(page.getByText(`${other.name} review set`)).toHaveCount(0);
    await expect(page.getByText(`${other.name} review item`)).toHaveCount(0);

    release();
    await expect(page.getByRole("heading", { name: "Discovery review" })).toBeVisible();
    await expect(page.getByText(`${other.name} review item`)).toHaveCount(0);
  });
}
