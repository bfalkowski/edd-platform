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

test("a failed saved-tests load for a previously selected agent shows no error on the new one", async ({
  page,
  request,
}) => {
  const oldAgent = await createAgent(request, "Superseded Tests Agent");
  const newAgent = await createAgent(request, "Current Tests Agent");

  // Hold the old agent's scenario requests (the saved-test list reads them) until the
  // person has moved on, then fail them.
  let releaseOldLoad: () => void = () => {};
  const oldLoadReleased = new Promise<void>((resolve) => {
    releaseOldLoad = resolve;
  });
  let oldLoadStarted: () => void = () => {};
  const oldLoadSeen = new Promise<void>((resolve) => {
    oldLoadStarted = resolve;
  });
  await page.route(`**/scenarios?agent_design_id=${oldAgent.id}`, async (route) => {
    oldLoadStarted();
    await oldLoadReleased;
    await route.fulfill({ status: 500, json: { detail: "Old agent saved tests failed" } });
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
