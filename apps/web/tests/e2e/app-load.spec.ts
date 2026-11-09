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
  await expect(agentList.getByText("Apartment Search Agent")).toBeVisible();

  expect(errors).toEqual([]);
});

test("?agent=<id> opens that agent without loading the newest one first", async ({ page, request }) => {
  const createAgent = async (label: string) => {
    const name = `${label} ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const response = await request.post("/api/projects/project_default/agent-designs", {
      data: { name, intent: "Answer support questions with a safe next action." },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    const { agent } = (await response.json()) as { agent: { id: string } };
    return { id: agent.id, name };
  };
  const wanted = await createAgent("Linked Agent");
  const newest = await createAgent("Newer Agent");

  const newestRequests: string[] = [];
  page.on("request", (req) => {
    if (req.url().includes(newest.id)) newestRequests.push(req.url());
  });

  await page.goto(`/?agent=${wanted.id}`);
  await page.getByRole("tab", { name: "Agent" }).click();
  await expect(page.getByRole("heading", { name: wanted.name })).toBeVisible();
  await expect(page.locator(".agent-row.selected")).toHaveText(wanted.name);
  expect(newestRequests).toEqual([]);
});

test("an unknown ?agent=<id> falls back to the newest agent", async ({ page }) => {
  await page.goto("/?agent=agent_does_not_exist");
  await expect(page.getByRole("tablist", { name: "Agent workspace" })).toBeVisible();
  await expect(page.locator(".agent-row").first()).toHaveClass(/selected/);
});
