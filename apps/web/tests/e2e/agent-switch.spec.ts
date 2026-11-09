import { expect, test, type APIRequestContext } from "@playwright/test";

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
