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

  const failedResponse = page.waitForResponse(`**/gates?agent_design_id=${oldAgent.id}`);
  releaseOldLoad();
  await failedResponse;
  // Give the rejected load time to reach the page before checking nothing was shown.
  await page.waitForTimeout(500);

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
