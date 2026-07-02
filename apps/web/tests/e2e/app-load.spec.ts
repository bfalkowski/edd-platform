import { expect, test } from "@playwright/test";

test("app loads with sidebar, services, and seeded agents", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });

  await page.goto("/");

  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Service status" })).toBeVisible();

  const agentList = page.getByRole("region", { name: "Agent designs" });
  await expect(agentList).toBeVisible();
  await expect(agentList.getByText("Sentiment Observer")).toBeVisible();
  await expect(agentList.getByText("Apartment Search Agent")).toBeVisible();

  expect(errors).toEqual([]);
});
