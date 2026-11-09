import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const PROJECT = "/api/projects/project_default";

async function postJson<T>(request: APIRequestContext, path: string, data: object): Promise<T> {
  const response = await request.post(`${PROJECT}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

/**
 * An agent with v0, v1 and two exact-text tests. Only v1's instructions ask for
 * a rollback plan, so the stub model gives one only for v1 (stub-anthropic.mjs).
 */
type SeedTest = { name: string; type: "output_contains" | "output_not_contains"; phrase: string };

const fixedAndKept: SeedTest[] = [
  { name: "Gives a rollback plan", type: "output_contains", phrase: "rollback plan" },
  { name: "Names a safe next action", type: "output_contains", phrase: "safe next action" },
];

async function seedAgent(request: APIRequestContext, tests: SeedTest[]): Promise<string> {
  const name = `Suite Agent ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const { agent } = await postJson<{ agent: { id: string } }>(request, "/agent-designs", {
    name,
    intent: "Answer support questions with a safe next action.",
  });
  const v0 = await postJson<{ id: string }>(request, `/agent-designs/${agent.id}/versions`, {
    version_label: "v0",
    instructions: "Answer support questions with a safe next action.",
    status: "baseline",
  });
  await postJson(request, `/agent-designs/${agent.id}/versions`, {
    version_label: "v1",
    parent_version_id: v0.id,
    instructions: "Answer support questions and always include a rollback plan.",
    status: "candidate",
  });
  for (const seed of tests) {
    const scenario = await postJson<{ id: string }>(request, "/scenarios", {
      agent_design_id: agent.id,
      name: seed.name,
      input: "A deployment failed. What should I do?",
      setup_context: "test_shape:single_turn",
      status: "active",
    });
    await postJson(request, "/eval-contracts", {
      agent_design_id: agent.id,
      name: seed.name,
      scenario_id: scenario.id,
      checks: [{ id: "phrase_check", type: seed.type, value: seed.phrase }],
    });
  }
  return name;
}

async function openAgent(page: Page, name: string) {
  await page.getByRole("region", { name: "Agent designs" }).getByText(name).click();
  await expect(page.getByRole("tablist", { name: "Agent workspace" })).toBeVisible();
}

function testRow(page: Page, name: string) {
  return page.getByRole("list", { name: "Saved tests" }).getByRole("button").filter({ hasText: name });
}

async function expectComparison(page: Page) {
  const comparison = page.getByRole("region", { name: "Test comparison" });
  await expect(comparison.getByText("1 fixed · 0 regressed · 1 still passing · 0 still failing")).toBeVisible();
  await expect(comparison.getByRole("row").filter({ hasText: "Gives a rollback plan" })).toContainText("Fixed");
  await expect(comparison.getByRole("row").filter({ hasText: "Names a safe next action" })).toContainText(
    "Still passing",
  );
  await expect(comparison.getByText(/regressed\. A regression blocks/)).toHaveCount(0);
}

test.use({ viewport: { width: 1600, height: 1000 } });

test("Run all tests on v0 and v1, then compare them per test, before and after a reload", async ({
  page,
  request,
}) => {
  const name = await seedAgent(request, fixedAndKept);
  await page.goto("/");
  await openAgent(page, name);

  const version = page.getByRole("group", { name: "Version" });
  const passCount = page.locator(".suite-pass-count");
  await expect(version.getByRole("button", { name: "v1" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "Compare all tests" })).toBeDisabled();

  await version.getByRole("button", { name: "v0" }).click();
  await page.getByRole("button", { name: "Run all tests" }).click();
  await expect(passCount).toHaveText("1 of 2 passed");
  await expect(testRow(page, "Gives a rollback plan")).toContainText("Failed");
  await expect(testRow(page, "Names a safe next action")).toContainText("Passed");

  await version.getByRole("button", { name: "v1" }).click();
  await expect(passCount).toHaveText("0 of 2 passed");
  await expect(testRow(page, "Gives a rollback plan")).toContainText("Not run");
  await page.getByRole("button", { name: "Run all tests" }).click();
  await expect(passCount).toHaveText("2 of 2 passed");
  await expect(testRow(page, "Gives a rollback plan")).toContainText("Passed");

  await page.getByRole("button", { name: "Compare all tests" }).click();
  await expectComparison(page);

  // Everything above is rebuilt from saved records.
  await page.reload();
  await openAgent(page, name);
  await expect(passCount).toHaveText("2 of 2 passed");
  await expect(testRow(page, "Gives a rollback plan")).toContainText("Passed");
  await version.getByRole("button", { name: "v0" }).click();
  await expect(passCount).toHaveText("1 of 2 passed");
  await expect(testRow(page, "Gives a rollback plan")).toContainText("Failed");
  await expectComparison(page);

  // The gate decision uses the same comparison, shown beside it.
  await page.getByRole("tab", { name: "Readiness" }).click();
  await expectComparison(page);
  await page.getByRole("button", { name: "Create gate" }).click();
  await page.getByRole("button", { name: "Run gate" }).click();
  await expect(page.getByRole("heading", { name: "Ready" })).toBeVisible();
  await expect(page.getByText("Gate evidence: v0 → v1")).toBeVisible();

  // A rerun after the comparison makes it out of date; the gate waits for a new one.
  await page.getByRole("tab", { name: "Proof loop" }).click();
  await page.getByRole("button", { name: "Run all tests" }).click();
  const stale = "Out of date: tests or results changed since this comparison. Compare all tests again.";
  await expect(page.getByText(stale)).toBeVisible();
  await page.getByRole("tab", { name: "Readiness" }).click();
  await expect(page.getByText(stale)).toBeVisible();
  await expect(page.getByRole("button", { name: "Run again" })).toBeDisabled();
  await expect(page.getByText("Decided before the latest results.", { exact: false })).toBeVisible();
  await page.getByRole("tab", { name: "Proof loop" }).click();
  await page.getByRole("button", { name: "Compare all tests" }).click();
  await expect(page.getByText(stale)).toHaveCount(0);
  await page.getByRole("tab", { name: "Readiness" }).click();
  await expect(page.getByRole("button", { name: "Run again" })).toBeEnabled();
  await expect(page.getByText("Decided before the latest results.", { exact: false })).toHaveCount(0);
});

test("A test that passed on v0 and fails on v1 is marked as a regression and blocks the gate", async ({
  page,
  request,
}) => {
  const name = await seedAgent(request, [
    fixedAndKept[0],
    { name: "Never mentions a rollback", type: "output_not_contains", phrase: "rollback" },
  ]);
  await page.goto("/");
  await openAgent(page, name);

  const version = page.getByRole("group", { name: "Version" });
  await version.getByRole("button", { name: "v0" }).click();
  await page.getByRole("button", { name: "Run all tests" }).click();
  await expect(page.locator(".suite-pass-count")).toHaveText("1 of 2 passed");
  await version.getByRole("button", { name: "v1" }).click();
  await page.getByRole("button", { name: "Run all tests" }).click();
  await expect(page.locator(".suite-pass-count")).toHaveText("1 of 2 passed");
  await page.getByRole("button", { name: "Compare all tests" }).click();

  // The fixed test now passes, and the regression is still a warning.
  const comparison = page.getByRole("region", { name: "Test comparison" });
  await expect(comparison.getByText("1 fixed · 1 regressed · 0 still passing · 0 still failing")).toBeVisible();
  await expect(comparison.getByRole("alert")).toHaveText(
    "1 test regressed. A regression blocks promotion, even if the test you fixed now passes.",
  );
  await expect(comparison.getByRole("row").filter({ hasText: "Gives a rollback plan" })).toContainText("Fixed");
  const regressed = comparison.getByRole("row").filter({ hasText: "Never mentions a rollback" });
  await expect(regressed).toContainText("⚠ Regressed");
  await expect(regressed).toHaveClass(/suite-row-regressed/);

  await page.getByRole("tab", { name: "Readiness" }).click();
  await expect(page.getByRole("region", { name: "Test comparison" }).getByRole("alert")).toBeVisible();
  await page.getByRole("button", { name: "Create gate" }).click();
  await page.getByRole("button", { name: "Run gate" }).click();
  await expect(page.getByRole("heading", { name: "Blocked" })).toBeVisible();
});

test("A test whose run failed shows the error next to it after a suite run", async ({ page, request }) => {
  const name = await seedAgent(request, fixedAndKept);
  await page.goto("/");
  await openAgent(page, name);

  // The stub provider cannot fail one test, so the real run response gets one
  // test's error added. Its eval stays as saved, as the API leaves it on an error.
  const message = "Judge request failed with status 529: Overloaded";
  await page.route("**/suite-runs", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.tests[0].error = message;
    await route.fulfill({ response, json: body });
  });

  const failedRow = testRow(page, "Gives a rollback plan");
  const list = page.getByRole("list", { name: "Saved tests" });
  await page.getByRole("button", { name: "Run all tests" }).click();
  await expect(page.locator(".suite-pass-count")).toHaveText("2 of 2 passed");
  await expect(testRow(page, "Names a safe next action")).toContainText("Passed");
  await expect(failedRow).toContainText("Error");
  await expect(failedRow).not.toContainText("Passed");
  await expect(list.getByText(message)).toBeVisible();

  // The saved results reload after the run; the error stays, on that version only.
  const version = page.getByRole("group", { name: "Version" });
  await version.getByRole("button", { name: "v0" }).click();
  await expect(failedRow).toContainText("Not run");
  await expect(list.getByText(message)).toHaveCount(0);
  await version.getByRole("button", { name: "v1" }).click();
  await expect(list.getByText(message)).toBeVisible();

  // A later run that gives the test a new eval clears its error.
  await page.unroute("**/suite-runs");
  await page.getByRole("button", { name: "Run all tests" }).click();
  await expect(failedRow).toContainText("Passed");
  await expect(list.getByText(message)).toHaveCount(0);
});

test("Scenarios sharing a default contract are tests in both the saved-test list and the suite run", async ({
  page,
  request,
}) => {
  // Three active scenarios that name no contract share one as their default.
  // A fourth active scenario has no contract at all, so it is not a test.
  const name = await seedAgent(request, []);
  const agents = await (await request.get(`${PROJECT}/agent-designs`)).json();
  const agent = agents.find((item: { name: string }) => item.name === name);
  const shared = await postJson<{ id: string }>(request, "/eval-contracts", {
    agent_design_id: agent.id,
    name: "Shared contract",
    checks: [{ id: "phrase_check", type: "output_contains", value: "rollback plan" }],
  });
  const sharedNames = ["Shared one", "Shared two", "Shared three"];
  for (const scenarioName of [...sharedNames, "No contract"]) {
    await postJson(request, "/scenarios", {
      agent_design_id: agent.id,
      name: scenarioName,
      input: "A deployment failed. What should I do?",
      setup_context: "test_shape:single_turn",
      default_eval_contract_id: scenarioName === "No contract" ? null : shared.id,
      status: "active",
    });
  }
  await page.goto("/");
  await openAgent(page, name);

  const rows = page.getByRole("list", { name: "Saved tests" }).getByRole("button");
  await expect(rows).toHaveCount(3);
  for (const [index, scenarioName] of sharedNames.entries()) {
    await expect(rows.nth(index)).toContainText(scenarioName);
  }
  await expect(rows.filter({ hasText: "No contract" })).toHaveCount(0);

  const version = page.getByRole("group", { name: "Version" });
  const passCount = page.locator(".suite-pass-count");
  await version.getByRole("button", { name: "v0" }).click();
  await page.getByRole("button", { name: "Run all tests" }).click();
  await expect(passCount).toHaveText("0 of 3 passed");
  await version.getByRole("button", { name: "v1" }).click();
  await page.getByRole("button", { name: "Run all tests" }).click();
  await expect(passCount).toHaveText("3 of 3 passed");
  for (const scenarioName of sharedNames) {
    await expect(testRow(page, scenarioName)).toContainText("Passed");
  }

  await page.getByRole("button", { name: "Compare all tests" }).click();
  await expect(
    page.getByRole("region", { name: "Test comparison" }).getByText("3 fixed · 0 regressed · 0 still passing · 0 still failing"),
  ).toBeVisible();
});
