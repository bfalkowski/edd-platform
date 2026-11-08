import { expect, test } from "@playwright/test";

test("new agent wizard advances from describe to review step", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "New agent" }).first().click();

  await expect(page.getByText("Step 1 of 6 — Describe your agent")).toBeVisible();
  await page
    .getByPlaceholder(/Help a support engineer understand a failed deployment/)
    .fill("Summarize daily standup notes into three bullet points.");
  await page.getByRole("button", { name: "Generate →" }).click();

  await expect(page.getByText("Step 2 of 6 — Review the generated setup")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByRole("heading", { name: "Review the generated setup" })).toBeVisible();
  // The step indicator above the heading agrees: six steps, Review is the second.
  await expect(page.locator(".wizard-step")).toHaveCount(6);
  await expect(page.locator(".wizard-step.active")).toHaveText(/2\s*Review/);
  await expect(page.getByLabel("Agent name")).not.toHaveValue("");
});

test("wizard sends the model chosen on the review step with the run", async ({ page }) => {
  const catalog = await (await page.request.get("/api/models")).json();
  const chosen = catalog.models.find((model: { id: string }) => model.id !== catalog.default_model);

  await page.goto("/");
  await page.getByRole("button", { name: "New agent" }).first().click();
  await page
    .getByPlaceholder(/Help a support engineer understand a failed deployment/)
    .fill("Summarize daily standup notes into three bullet points.");
  await page.getByRole("button", { name: "Generate →" }).click();
  await expect(page.getByRole("heading", { name: "Review the generated setup" })).toBeVisible({
    timeout: 15_000,
  });

  const modelPicker = page.getByLabel("Model");
  await expect(modelPicker).toHaveValue(catalog.default_model);
  await modelPicker.selectOption(chosen.id);

  await page.getByRole("button", { name: "Looks right — save agent →" }).click();
  await expect(page.getByText("Step 3 of 6 — Run the agent")).toBeVisible({ timeout: 15_000 });

  const runRequest = page.waitForRequest(
    (request) => request.method() === "POST" && /\/api\/projects\/[^/]+\/runs$/.test(request.url()),
  );
  await page.getByRole("button", { name: "Run →" }).click();
  expect((await runRequest).postDataJSON().model).toBe(chosen.id);
});

test("a first-run pass suggests more tests and opens the Proof loop", async ({ page }) => {
  // The stub model's answers do not pass a live rubric judge, so report this run as passed.
  await page.route(/\/api\/projects\/[^/]+\/runs\/[^/]+\/evaluate$/, async (route) => {
    const response = await route.fetch();
    const result = await response.json();
    const checks = result.checks.map((check: object) => ({ ...check, passed: true }));
    await route.fulfill({ response, json: { ...result, passed: true, checks } });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "New agent" }).first().click();
  await page
    .getByPlaceholder(/Help a support engineer understand a failed deployment/)
    .fill("Summarize daily standup notes into three bullet points.");
  await page.getByRole("button", { name: "Generate →" }).click();
  const agentName = page.getByLabel("Agent name");
  await expect(agentName).not.toHaveValue("", { timeout: 15_000 });
  const name = `First Pass Agent ${Date.now()}`;
  await agentName.fill(name);
  await page.getByRole("button", { name: "Looks right — save agent →" }).click();
  await page.getByRole("button", { name: "Run →" }).click();

  await expect(page.getByRole("heading", { name: "Passed on the first run." })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText("One passing test does not show the agent is ready.")).toBeVisible();
  await page.getByRole("button", { name: "Add more tests in the Proof loop →" }).click();

  await expect(page.getByRole("tab", { name: "Proof loop" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("region", { name: "Agent designs" }).getByText(name)).toBeVisible();
});
