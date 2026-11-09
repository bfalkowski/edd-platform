import { expect, test, type APIRequestContext } from "@playwright/test";

const PROJECT = "/api/projects/project_default";

async function postJson<T>(request: APIRequestContext, path: string, data: object): Promise<T> {
  const response = await request.post(`${PROJECT}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

/** An agent with one live run (answered by the stub model) and a deterministic verdict. */
async function seedAgentWithRun(request: APIRequestContext): Promise<{ name: string; id: string }> {
  const name = `Analysis Agent ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const { agent } = await postJson<{ agent: { id: string } }>(request, "/agent-designs", {
    name,
    intent: "Answer support questions with a safe next action.",
  });
  const scenario = await postJson<{ id: string }>(request, "/scenarios", {
    agent_design_id: agent.id,
    name: "Support question",
    input: "A deployment failed. What should I do?",
  });
  const contract = await postJson<{ id: string }>(request, "/eval-contracts", {
    agent_design_id: agent.id,
    name: "Names a rollback",
    scenario_id: scenario.id,
    checks: [{ id: "rollback", type: "output_contains", value: "zz-rollback-zz" }],
  });
  const run = await postJson<{ id: string }>(request, "/runs", {
    agent_design_id: agent.id,
    scenario_id: scenario.id,
    eval_contract_id: contract.id,
    mode: "live",
  });
  await postJson(request, `/runs/${run.id}/evaluate`, { judge_mode: "deterministic" });
  return { name, id: agent.id };
}

test("Error analysis runs end to end with Langfuse offline", async ({ page, request }) => {
  const agent = await seedAgentWithRun(request);
  await page.goto("/");
  await page.getByRole("region", { name: "Agent designs" }).getByText(agent.name).click();
  await page.getByRole("tab", { name: "Error analysis" }).click();

  // 1. Build review set. The stepper uses the same name as the intro box.
  await expect(page.locator(".discovery-step.active")).toHaveText("1Build review set");
  // The intro and side card say "review set" too, never the old word "corpus".
  const intro = page.locator(".error-analysis-intro");
  await expect(intro).toContainText("Start by building a review set of traces and evidence.");
  await expect(intro).toContainText("Create a review set to begin");
  await page.getByRole("button", { name: "Pull in new runs" }).click();
  await expect(page.getByText("Added 1 run to the review set.")).toBeVisible();
  await expect(intro.getByRole("heading", { level: 3 })).toHaveText(`${agent.name} review set`);
  await expect(intro.locator(".analysis-scope-card small")).toContainText("review set ·");
  await expect(intro).not.toContainText(/corpus/i);
  await page.getByRole("button", { name: "Start reviewing" }).click();

  // 2. Review & code: read the run, write a note, name a mode, assign the note.
  // The first item opens on its own.
  const details = page.locator(".discovery-item-details");
  await expect(details).toContainText("A deployment failed. What should I do?");
  await expect(details).toContainText("Judge verdict");
  await expect(details).toContainText("Failed");
  // A long output scrolls inside its box, so the box is in the tab order.
  const output = details.getByRole("region", { name: "Agent output" });
  await expect(output).toHaveAttribute("tabindex", "0");
  // The region sits inside a plain dd, so each dt/dd pair stays a definition,
  // and the region is the element that scrolls.
  await expect(details.getByRole("definition")).toHaveCount(3);
  await expect(output).toHaveCSS("overflow-y", "auto");

  await page.getByRole("textbox", { name: "Note" }).fill("Never suggests rolling back the deploy.");
  await page.getByRole("button", { name: "Add note" }).click();
  const note = page.locator(".discovery-annotation-row");
  await expect(note).toContainText("Never suggests rolling back the deploy.");
  await expect(note).toContainText("In app");

  await page.getByRole("textbox", { name: "Failure mode name" }).fill("Missing rollback");
  await page.getByRole("textbox", { name: "What it looks like" }).fill("No rollback step offered.");
  await page.getByRole("button", { name: "Add failure mode" }).click();
  await expect(page.getByText('Failure mode "Missing rollback" created.')).toBeVisible();
  await note.getByRole("combobox").selectOption({ label: "Missing rollback" });
  await expect(note.getByRole("combobox")).toHaveValue(/failure_mode_/);

  // 3. Confirm modes.
  await page.getByRole("button", { name: "Continue to confirm modes" }).click();
  const modeRow = page.locator(".failure-mode-row").filter({ hasText: "Missing rollback" });
  await expect(modeRow).toContainText("1 notes");
  await page.getByRole("button", { name: "Confirm Missing rollback" }).click();
  await expect(modeRow).toContainText("confirmed");

  // 4. Done.
  await page.getByRole("button", { name: "Finish review" }).click();
  const stats = page.locator(".analysis-stats");
  await expect(stats).toContainText("1items reviewed");
  await expect(stats).toContainText("1notes");
  await expect(stats).toContainText("1modes confirmed");

  // The note and the mode are ordinary review annotations and failure modes.
  const corpora = await (
    await request.get(`${PROJECT}/review-corpora?agent_design_id=${agent.id}`)
  ).json();
  const analysis = await (
    await request.get(`${PROJECT}/review-corpora/${corpora[0].id}/analysis`)
  ).json();
  expect(analysis.failure_mode_counts).toEqual([
    expect.objectContaining({ name: "Missing rollback", accepted_annotations: 1 }),
  ]);
});
