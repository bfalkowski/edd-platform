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
