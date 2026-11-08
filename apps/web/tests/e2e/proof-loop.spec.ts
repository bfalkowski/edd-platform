import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const PROJECT = "/api/projects/project_default";

async function postJson<T>(request: APIRequestContext, path: string, data: object): Promise<T> {
  const response = await request.post(`${PROJECT}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

/** An agent with one test the stub model fails until its instructions ask for a rollback plan. */
async function seedAgent(request: APIRequestContext): Promise<string> {
  const name = `Proof Loop Agent ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const { agent } = await postJson<{ agent: { id: string } }>(request, "/agent-designs", {
    name,
    intent: "Answer support questions with a safe next action.",
  });
  // The console creates v0 with an agent's first test; seeding through the API has to do it too.
  await postJson(request, `/agent-designs/${agent.id}/versions`, {
    version_label: "v0",
    instructions: "Answer support questions with a safe next action.",
    status: "baseline",
  });
  const scenario = await postJson<{ id: string }>(request, "/scenarios", {
    agent_design_id: agent.id,
    name: "Failed deploy",
    input: "A deployment failed. What should I do?",
    setup_context: "test_shape:single_turn",
    status: "active",
  });
  await postJson(request, "/eval-contracts", {
    agent_design_id: agent.id,
    name: "Gives a rollback plan",
    scenario_id: scenario.id,
    checks: [{ id: "rollback_plan", type: "output_contains", value: "rollback plan" }],
  });
  return name;
}

async function openAgent(page: Page, name: string) {
  await page.goto("/");
  await page.getByRole("region", { name: "Agent designs" }).getByText(name).click();
  await expect(page.getByRole("tablist", { name: "Agent workspace" })).toBeVisible();
}

function nextAction(page: Page) {
  return page.locator(".next-action-panel");
}

async function clickNext(page: Page, label: string) {
  const button = nextAction(page).getByRole("button", { name: label, exact: true });
  await expect(button).toBeEnabled();
  await button.click();
}

// Wide enough that the artifact review panel sits beside the proof loop, not over it.
test.use({ viewport: { width: 1600, height: 1000 } });

test("A failed test goes from Save analysis to a compared new version", async ({ page, request }) => {
  const name = await seedAgent(request);
  await openAgent(page, name);
  await expect(page.getByRole("tab", { name: "Proof loop" })).toHaveAttribute("aria-selected", "true");

  await clickNext(page, "Run current");
  await clickNext(page, "Check answer");

  const analysis = page.locator(".failure-analysis-panel");
  await expect(analysis.getByRole("heading", { name: "Name this failure" })).toBeVisible();
  await analysis.getByRole("button", { name: "Auto-diagnose" }).click();
  await expect(analysis.getByLabel("Failure mode")).toHaveValue("missing rollback plan");
  await analysis.getByRole("button", { name: "Save analysis" }).click();

  // The saved analysis stays on screen, read-only.
  await expect(analysis.getByText("✓ Analysis saved")).toBeVisible();
  await expect(analysis.getByLabel("Failure mode")).toHaveValue("missing rollback plan");
  await expect(analysis.getByLabel("Failure mode")).toBeDisabled();
  await expect(analysis.getByLabel("Severity")).toHaveValue("high");
  await expect(analysis.getByLabel(/Review note/)).toHaveValue("The answer never gives a rollback plan.");
  await expect(analysis.getByLabel(/Review note/)).toBeDisabled();

  await expect(nextAction(page).getByRole("heading", { name: "Generate a fix" })).toBeVisible();
  await clickNext(page, "Generate fix");
  await expect(page.getByLabel("Proposed instructions")).toHaveValue(/rollback plan/);
  await clickNext(page, "Save fix proposal");
  await clickNext(page, "Create version");
  await clickNext(page, "Run version");
  await clickNext(page, "Check version");
  await clickNext(page, "Compare");

  await expect(nextAction(page).getByText("Iteration complete — passed")).toBeVisible();
});
