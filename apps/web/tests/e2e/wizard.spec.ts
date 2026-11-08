import { expect, test } from "@playwright/test";

test("new agent wizard advances from describe to review step", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "New agent" }).first().click();

  await expect(page.getByText("Step 1 of 5 — Describe your agent")).toBeVisible();
  await page
    .getByPlaceholder(/Help a support engineer understand a failed deployment/)
    .fill("Summarize daily standup notes into three bullet points.");
  await page.getByRole("button", { name: "Generate →" }).click();

  await expect(page.getByText("Step 1 of 5 — Review the generated setup")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByRole("heading", { name: "Review the generated setup" })).toBeVisible();
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

  await page.getByRole("button", { name: "Looks right — run it →" }).click();
  await expect(page.getByText("Step 2 of 5 — Run the agent")).toBeVisible({ timeout: 15_000 });

  const runRequest = page.waitForRequest(
    (request) => request.method() === "POST" && /\/api\/projects\/[^/]+\/runs$/.test(request.url()),
  );
  await page.getByRole("button", { name: "Run →" }).click();
  expect((await runRequest).postDataJSON().model).toBe(chosen.id);
});
