import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const PROJECT = "/api/projects/project_default";

async function postJson<T>(request: APIRequestContext, path: string, data: object): Promise<T> {
  const response = await request.post(`${PROJECT}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

type SeedTest = {
  name?: string;
  input: string;
  shape: string;
  status: string;
  // The stub model answers "Stub live answer. Recommend a safe next action."
  expectPhrase: string;
  evaluate: boolean;
};

/** Create an agent and its tests through the API, running and judging some of them. */
async function seedAgent(request: APIRequestContext, tests: SeedTest[]) {
  const name = `Saved Tests Agent ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const { agent } = await postJson<{ agent: { id: string } }>(request, "/agent-designs", {
    name,
    intent: "Answer support questions with a safe next action.",
  });
  for (const seed of tests) {
    const scenario = await postJson<{ id: string }>(request, "/scenarios", {
      agent_design_id: agent.id,
      name: seed.name ?? "",
      input: seed.input,
      setup_context: `test_shape:${seed.shape}`,
      status: seed.status,
    });
    const contract = await postJson<{ id: string }>(request, "/eval-contracts", {
      agent_design_id: agent.id,
      name: "Required phrase",
      scenario_id: scenario.id,
      checks: [{ id: "includes_required_phrase", type: "output_contains", value: seed.expectPhrase }],
    });
    if (seed.evaluate) {
      const run = await postJson<{ id: string }>(request, "/runs", {
        agent_design_id: agent.id,
        scenario_id: scenario.id,
        eval_contract_id: contract.id,
        mode: "live",
      });
      await postJson(request, `/runs/${run.id}/evaluate`, { judge_mode: "deterministic" });
    }
  }
  return name;
}

async function openAgent(page: Page, name: string) {
  await page.goto("/");
  await page.getByRole("region", { name: "Agent designs" }).getByText(name).click();
  await expect(page.getByRole("tablist", { name: "Agent workspace" })).toBeVisible();
}

const threeTests: SeedTest[] = [
  {
    name: "Deploy rollback",
    input: "A deployment failed. What should I do?",
    shape: "single_turn",
    status: "active",
    expectPhrase: "next action",
    evaluate: true,
  },
  {
    input: "Customer: The rollout says image pull backoff.\nAgent: Checking.",
    shape: "conversation",
    status: "active",
    expectPhrase: "image pull backoff",
    evaluate: true,
  },
  {
    name: "Billing question",
    input: "Why was I charged twice?",
    shape: "single_turn",
    status: "active",
    expectPhrase: "refund",
    evaluate: false,
  },
  // Left in draft by an earlier edit: not a separate test.
  {
    name: "Old draft",
    input: "An abandoned draft prompt.",
    shape: "single_turn",
    status: "draft",
    expectPhrase: "anything",
    evaluate: false,
  },
];

function testRows(page: Page) {
  return page.getByRole("list", { name: "Saved tests" }).getByRole("button");
}

test("Proof loop lists every active test and switches the selected test", async ({ page, request }) => {
  const agentName = await seedAgent(request, threeTests);
  await openAgent(page, agentName);

  const rows = testRows(page);
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText("Deploy rollback");
  await expect(rows.nth(0)).toContainText("Single turn");
  await expect(rows.nth(0)).toContainText("Passed");
  // No name given: named after the start of the prompt.
  await expect(rows.nth(1)).toContainText("Customer: The rollout says image pull backoff.");
  await expect(rows.nth(1)).toContainText("Conversation");
  await expect(rows.nth(1)).toContainText("Failed");
  await expect(rows.nth(2)).toContainText("Billing question");
  await expect(rows.nth(2)).toContainText("Not run");
  await expect(page.getByText("Old draft")).toHaveCount(0);

  // The newest test starts selected.
  await expect(rows.nth(2)).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("heading", { name: "Run current" })).toBeVisible();

  await rows.nth(0).click();
  await expect(rows.nth(0)).toHaveAttribute("aria-pressed", "true");
  await expect(rows.nth(2)).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByRole("heading", { level: 4, name: "Deploy rollback" })).toBeVisible();
  await expect(page.locator(".scenario-test-summary dl")).toContainText("Passed");
});

test("New test starts blank and adds a test without replacing the others", async ({ page, request }) => {
  const agentName = await seedAgent(request, threeTests);
  await openAgent(page, agentName);
  await expect(testRows(page)).toHaveCount(3);
  const nextAction = page.locator(".next-action-panel h4");
  await expect(nextAction).toHaveText("Run current");

  await page.getByRole("button", { name: "New test" }).click();
  const editor = page.getByRole("complementary", { name: "Test case editor" });
  await expect(editor.getByRole("heading", { name: "New test" })).toBeVisible();
  const prompt = editor.locator("textarea").first();
  await expect(prompt).toHaveValue("");
  await expect(editor.locator("textarea").nth(1)).toHaveValue(/directly answer the user request/);

  // A draft does not change the next action for the saved, selected test.
  await prompt.fill("Where is my order? It was due yesterday.");
  await editor.getByRole("button", { name: "Exact text" }).click();
  await expect(nextAction).toHaveText("Run current");

  await editor.getByRole("button", { name: "Rubric judge" }).click();
  await editor.getByRole("button", { name: "Save test" }).click();
  await expect(editor).toHaveCount(0);

  const rows = testRows(page);
  await expect(rows).toHaveCount(4);
  await expect(rows.nth(3)).toContainText("Where is my order? It was due yesterday.");
  await expect(rows.nth(3)).toHaveAttribute("aria-pressed", "true");
  await expect(rows.nth(0)).toContainText("Deploy rollback");
});

test("Editing a test replaces its entry instead of adding one", async ({ page, request }) => {
  const agentName = await seedAgent(request, threeTests);
  await openAgent(page, agentName);
  const rows = testRows(page);
  await rows.nth(0).click();
  await expect(page.getByRole("heading", { level: 4, name: "Deploy rollback" })).toBeVisible();

  await page.getByRole("button", { name: "Edit test" }).click();
  const editor = page.getByRole("complementary", { name: "Test case editor" });
  await expect(editor.getByRole("heading", { name: "Edit test" })).toBeVisible();
  await expect(editor.getByLabel("Name")).toHaveValue("Deploy rollback");
  await editor.getByLabel("Name").fill("Deploy rollback advice");
  await editor.getByRole("button", { name: "Save test" }).click();

  await expect(rows).toHaveCount(3);
  await expect(page.getByRole("list", { name: "Saved tests" })).toContainText("Deploy rollback advice");
  await expect(rows.filter({ hasText: "Deploy rollback advice" })).toHaveAttribute("aria-pressed", "true");
});

test("An agent whose passed test was saved as a draft opens the workspace, not the wizard", async ({
  page,
  request,
}) => {
  // The old console saved every test as a draft scenario.
  const name = `Legacy Agent ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const { agent } = await postJson<{ agent: { id: string } }>(request, "/agent-designs", {
    name,
    intent: "Answer support questions with a safe next action.",
  });
  const version = await postJson<{ id: string }>(request, `/agent-designs/${agent.id}/versions`, {
    version_label: "v0",
    instructions: "Answer support questions with a safe next action.",
    status: "baseline",
  });
  const scenario = await postJson<{ id: string }>(request, "/scenarios", {
    agent_design_id: agent.id,
    name: "Legacy test",
    input: "A deployment failed. What should I do?",
  });
  const contract = await postJson<{ id: string }>(request, "/eval-contracts", {
    agent_design_id: agent.id,
    name: "Required phrase",
    scenario_id: scenario.id,
    checks: [{ id: "includes_required_phrase", type: "output_contains", value: "next action" }],
  });
  const run = await postJson<{ id: string }>(request, "/runs", {
    agent_design_id: agent.id,
    agent_version_id: version.id,
    scenario_id: scenario.id,
    eval_contract_id: contract.id,
    mode: "live",
  });
  const verdict = await postJson<{ passed: boolean }>(request, `/runs/${run.id}/evaluate`, {
    judge_mode: "deterministic",
  });
  expect(verdict.passed).toBe(true);

  await openAgent(page, name);
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".wizard-heading")).toHaveCount(0);
});

test("An agent whose wizard test was edited opens the workspace, not the wizard", async ({
  page,
  request,
}) => {
  const name = `Edited Wizard Agent ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const drafted = await postJson<{ agent: { id: string }; scenario: { id: string } }>(
    request,
    "/agent-designs/from-outcome",
    { outcome: "Answer support questions with a safe next action.", name },
  );
  // Same as saving "Edit test" in the workspace: a new active revision, the old one superseded.
  const revision = await postJson<{ id: string }>(request, "/scenarios", {
    agent_design_id: drafted.agent.id,
    input: "A deployment failed. What should I do?",
    setup_context: "test_shape:single_turn",
    status: "active",
  });
  await postJson(request, "/eval-contracts", {
    agent_design_id: drafted.agent.id,
    name: "Required phrase",
    scenario_id: revision.id,
    checks: [{ id: "includes_required_phrase", type: "output_contains", value: "next action" }],
  });
  const patched = await request.patch(`${PROJECT}/scenarios/${drafted.scenario.id}`, {
    data: { status: "superseded" },
  });
  expect(patched.ok()).toBeTruthy();

  await openAgent(page, name);
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".wizard-heading")).toHaveCount(0);
  await expect(testRows(page)).toHaveCount(1);
});

test("Scenarios sharing a default contract each show their own latest result", async ({ page, request }) => {
  const name = `Shared Contract Agent ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const { agent } = await postJson<{ agent: { id: string } }>(request, "/agent-designs", {
    name,
    intent: "Answer support questions with a safe next action.",
  });
  const shared = await postJson<{ id: string }>(request, "/eval-contracts", {
    agent_design_id: agent.id,
    name: "Shared contract",
    checks: [{ id: "includes_required_phrase", type: "output_contains", value: "next action" }],
  });
  const scenarioIds: string[] = [];
  for (const scenarioName of ["Judged once", "Never run"]) {
    const scenario = await postJson<{ id: string }>(request, "/scenarios", {
      agent_design_id: agent.id,
      name: scenarioName,
      input: "A deployment failed. What should I do?",
      setup_context: "test_shape:single_turn",
      default_eval_contract_id: shared.id,
      status: "active",
    });
    scenarioIds.push(scenario.id);
  }
  const run = await postJson<{ id: string }>(request, "/runs", {
    agent_design_id: agent.id,
    scenario_id: scenarioIds[0],
    eval_contract_id: shared.id,
    mode: "live",
  });
  await postJson(request, `/runs/${run.id}/evaluate`, { judge_mode: "deterministic" });
  await openAgent(page, name);

  const rows = testRows(page);
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText("Judged once");
  await expect(rows.nth(0)).toContainText("Passed");
  // The other scenario's eval of the shared contract is not this one's result.
  await expect(rows.nth(1)).toContainText("Never run");
  await expect(rows.nth(1)).toContainText("Not run");
});
