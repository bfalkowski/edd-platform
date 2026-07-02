import { expect, test } from "@playwright/test";

test("all 5 workspace tabs render for a selected agent", async ({ page }) => {
  await page.goto("/");

  await page
    .getByRole("region", { name: "Agent designs" })
    .getByText("Apartment Search Agent")
    .click();

  const tablist = page.getByRole("tablist", { name: "Agent workspace" });
  await expect(tablist).toBeVisible();

  // Proof loop tab is selected by default once an agent is chosen.
  await expect(page.getByRole("tab", { name: "Proof loop" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { name: "Test cases" })).toBeVisible();

  await page.getByRole("tab", { name: "Agent" }).click();
  await expect(page.getByRole("tab", { name: "Agent" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Agent design")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Apartment Search Agent" })).toBeVisible();

  await page.getByRole("tab", { name: "Error analysis" }).click();
  await expect(page.getByRole("tab", { name: "Error analysis" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByText("Discovery review")).toBeVisible();

  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.getByRole("tab", { name: /Evidence/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { name: "Proof artifacts" })).toBeVisible();

  await page.getByRole("tab", { name: "Readiness" }).click();
  await expect(page.getByRole("tab", { name: "Readiness" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Promotion readiness")).toBeVisible();
});
