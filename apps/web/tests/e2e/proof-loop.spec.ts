import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const PROJECT = "/api/projects/project_default";

async function postJson<T>(request: APIRequestContext, path: string, data: object): Promise<T> {
  const response = await request.post(`${PROJECT}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

/** An agent with one test the stub model fails until its instructions ask for a rollback plan. */
async function seedAgent(request: APIRequestContext, checkFirst = false): Promise<string> {
  const name = `Proof Loop Agent ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const { agent } = await postJson<{ agent: { id: string } }>(request, "/agent-designs", {
    name,
    intent: "Answer support questions with a safe next action.",
  });
  // The console creates v0 with an agent's first test; seeding through the API has to do it too.
  const v0 = await postJson<{ id: string }>(request, `/agent-designs/${agent.id}/versions`, {
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
  const contract = await postJson<{ id: string }>(request, "/eval-contracts", {
    agent_design_id: agent.id,
    name: "Gives a rollback plan",
    scenario_id: scenario.id,
    checks: [{ id: "rollback_plan", type: "output_contains", value: "rollback plan" }],
  });
  if (checkFirst) {
    const run = await postJson<{ id: string }>(request, "/runs", {
      agent_design_id: agent.id,
      agent_version_id: v0.id,
      scenario_id: scenario.id,
      eval_contract_id: contract.id,
      mode: "live",
    });
    await postJson(request, `/runs/${run.id}/evaluate`, { judge_mode: "deterministic" });
  }
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
  // The answer being judged sits above the form, and the failed check is named, not shown by ID.
  await expect(analysis.locator(".agent-output")).toHaveText("Stub live answer. Recommend a safe next action.");
  await expect(analysis.locator(".failed-check-list strong")).toHaveText("Includes “rollback plan”");
  await expect(analysis.getByText("rollback_plan", { exact: true })).toHaveCount(0);
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

test("A failed test checked in an earlier session still reaches Generate fix", async ({ page, request }) => {
  const name = await seedAgent(request, true);
  await openAgent(page, name);

  const analysis = page.locator(".failure-analysis-panel");
  await analysis.getByLabel("Failure mode").fill("missing rollback plan");
  await analysis.getByLabel(/Review note/).fill("The answer never gives a rollback plan.");
  await analysis.getByRole("button", { name: "Save analysis" }).click();

  await clickNext(page, "Generate fix");
  await expect(nextAction(page).getByRole("heading", { name: "Confirm and save fix" })).toBeVisible();
});

test("A failed check stays saved when the packet reload fails", async ({ page, request }) => {
  const name = await seedAgent(request);
  await openAgent(page, name);
  await clickNext(page, "Run current");

  // Fail only the next failure-packet reload, the one Check makes after saving its eval.
  let failed = false;
  await page.route("**/failure-packets?*", (route) => {
    if (failed) return route.continue();
    failed = true;
    return route.fulfill({ status: 500, body: "{}" });
  });
  await clickNext(page, "Check answer");

  await expect(page.locator(".failure-analysis-panel").getByRole("heading", { name: "Name this failure" })).toBeVisible();
  await expect(nextAction(page).getByRole("button", { name: "Check answer", exact: true })).toHaveCount(0);
});

test("A fix proposal names the failure packet when the Check reload failed", async ({ page, request }) => {
  const name = await seedAgent(request);
  await openAgent(page, name);
  await clickNext(page, "Run current");

  // Fail only the failure-packet reload Check makes after saving its eval.
  let failed = false;
  await page.route("**/failure-packets?*", (route) => {
    if (failed) return route.continue();
    failed = true;
    return route.fulfill({ status: 500, body: "{}" });
  });
  await clickNext(page, "Check answer");

  const analysis = page.locator(".failure-analysis-panel");
  await analysis.getByLabel("Failure mode").fill("missing rollback plan");
  await analysis.getByLabel(/Review note/).fill("The answer never gives a rollback plan.");
  await analysis.getByRole("button", { name: "Save analysis" }).click();

  await clickNext(page, "Generate fix");
  await expect(page.getByLabel("Proposed instructions")).toHaveValue(/rollback plan/);
  const saved = page.waitForResponse(
    (response) => response.request().method() === "POST" && /\/fix-proposals$/.test(new URL(response.url()).pathname),
  );
  await clickNext(page, "Save fix proposal");
  const proposal = await (await saved).json();
  expect(proposal.addressed_failure_packet_ids).toHaveLength(1);
});

test("The fix message never names a version label other than the one created", async ({ page, request }) => {
  const name = await seedAgent(request);
  // An extra version that is neither the baseline nor a candidate: the server's next label skips past it.
  const agentId = (await (await request.get(`${PROJECT}/agent-designs`)).json()).find(
    (agent: { name: string }) => agent.name === name,
  ).id;
  await postJson(request, `/agent-designs/${agentId}/versions`, { version_label: "draft", status: "draft" });
  await openAgent(page, name);
  await clickNext(page, "Run current");
  await clickNext(page, "Check answer");

  const analysis = page.locator(".failure-analysis-panel");
  await analysis.getByLabel("Failure mode").fill("missing rollback plan");
  await analysis.getByLabel(/Review note/).fill("The answer never gives a rollback plan.");
  await analysis.getByRole("button", { name: "Save analysis" }).click();

  await clickNext(page, "Generate fix");
  const message = page.locator(".activity-text").filter({ hasText: "Fix generated" }).first();
  await expect(message).toHaveText("Fix generated. Review and confirm to create a new version.");
  const text = (await message.textContent()) ?? "";

  await clickNext(page, "Save fix proposal");
  const created = page.waitForResponse(
    (response) => response.request().method() === "POST" && /\/versions$/.test(new URL(response.url()).pathname),
  );
  await clickNext(page, "Create version");
  const version = await (await created).json();
  for (const label of text.match(/\bv\d+\b/g) ?? []) {
    expect(label).toBe(version.version_label);
  }
  await expect(page.locator(".activity-text").filter({ hasText: `${version.version_label} is ready to run.` }).first()).toBeVisible();
});

test("A second test's fix gets its own version, not the first test's", async ({ page, request }) => {
  const name = await seedAgent(request);
  const agentId = (await (await request.get(`${PROJECT}/agent-designs`)).json()).find(
    (agent: { name: string }) => agent.name === name,
  ).id;
  // A second test, saved after the first, so the agent opens on it.
  const scenario = await postJson<{ id: string }>(request, "/scenarios", {
    agent_design_id: agentId,
    name: "Failed migration",
    input: "A database migration failed. What should I do?",
    setup_context: "test_shape:single_turn",
    status: "active",
  });
  await postJson(request, "/eval-contracts", {
    agent_design_id: agentId,
    name: "Gives a rollback plan for the migration",
    scenario_id: scenario.id,
    checks: [{ id: "rollback_plan", type: "output_contains", value: "rollback plan" }],
  });
  await openAgent(page, name);

  /** Run and check the open test, then save its analysis and fix, and create a version from the fix. */
  async function fixOpenTest() {
    await clickNext(page, "Run current");
    await clickNext(page, "Check answer");
    const analysis = page.locator(".failure-analysis-panel");
    await analysis.getByRole("button", { name: "Auto-diagnose" }).click();
    await expect(analysis.getByLabel("Failure mode")).toHaveValue("missing rollback plan");
    await analysis.getByRole("button", { name: "Save analysis" }).click();
    await clickNext(page, "Generate fix");
    const saved = page.waitForResponse(
      (response) => response.request().method() === "POST" && /\/fix-proposals$/.test(new URL(response.url()).pathname),
    );
    await clickNext(page, "Save fix proposal");
    const proposal = await (await saved).json();
    const created = page.waitForResponse(
      (response) => response.request().method() === "POST" && /\/versions$/.test(new URL(response.url()).pathname),
    );
    await clickNext(page, "Create version");
    const version = await (await created).json();
    expect(version.source_fix_proposal_id).toBe(proposal.id);
    return version;
  }

  const first = await fixOpenTest();
  // Running every test on the first fix's version gives the second test a run and a check on it too.
  await page.getByRole("group", { name: "Version" }).getByRole("button", { name: first.version_label }).click();
  await page.getByRole("button", { name: "Run all tests" }).click();
  await expect(page.locator(".suite-pass-count")).toHaveText("2 of 2 passed");

  await page.getByRole("list", { name: "Saved tests" }).getByRole("button").filter({ hasText: "Failed deploy" }).click();
  await expect(nextAction(page).getByRole("button", { name: "Run current", exact: true })).toBeVisible();
  const second = await fixOpenTest();
  expect(second.id).not.toBe(first.id);
  // The new version has no run yet, so the first fix's run and check are not reused for it.
  await expect(nextAction(page).getByRole("heading", { name: `Run ${second.version_label}` })).toBeVisible();
  await expect(nextAction(page).getByRole("button", { name: "Run version", exact: true })).toBeVisible();
});

test("A saved fix with blank instructions leaves Create version disabled", async ({ page, request }) => {
  const name = await seedAgent(request, true);
  // A fix saved earlier whose instructions are only whitespace.
  const agentId = (await (await request.get(`${PROJECT}/agent-designs`)).json()).find(
    (agent: { name: string }) => agent.name === name,
  ).id;
  const [contract] = await (await request.get(`${PROJECT}/eval-contracts?agent_design_id=${agentId}`)).json();
  // Like the console's, the fix names the failure it addresses, so it is this test's fix.
  const packets = await (await request.get(`${PROJECT}/failure-packets?agent_design_id=${agentId}`)).json();
  await postJson(request, "/fix-proposals", {
    agent_design_id: agentId,
    title: "Blank fix",
    rationale: "Instructions left blank.",
    proposed_changes: [{ surface: "instructions", change: "   " }],
    addressed_failure_packet_ids: packets.map((packet: { id: string }) => packet.id),
    validation_contract_ids: [contract.id],
  });
  await openAgent(page, name);

  const analysis = page.locator(".failure-analysis-panel");
  await analysis.getByLabel("Failure mode").fill("missing rollback plan");
  await analysis.getByLabel(/Review note/).fill("The answer never gives a rollback plan.");
  await analysis.getByRole("button", { name: "Save analysis" }).click();

  await expect(nextAction(page).getByRole("heading", { name: "Create the next version" })).toBeVisible();
  await expect(nextAction(page).getByRole("button", { name: "Create version", exact: true })).toBeDisabled();
});

test("A test sharing a default contract does not inherit another test's failure or fix", async ({ page, request }) => {
  const name = `Shared Contract Proof Agent ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const { agent } = await postJson<{ agent: { id: string } }>(request, "/agent-designs", {
    name,
    intent: "Answer support questions with a safe next action.",
  });
  const v0 = await postJson<{ id: string }>(request, `/agent-designs/${agent.id}/versions`, {
    version_label: "v0",
    instructions: "Answer support questions with a safe next action.",
    status: "baseline",
  });
  const shared = await postJson<{ id: string }>(request, "/eval-contracts", {
    agent_design_id: agent.id,
    name: "Gives a rollback plan",
    checks: [{ id: "rollback_plan", type: "output_contains", value: "rollback plan" }],
  });
  const scenarioIds: string[] = [];
  for (const scenarioName of ["First deploy", "Second deploy"]) {
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
  // The first test failed, and a fix for its failure is saved.
  const run = await postJson<{ id: string }>(request, "/runs", {
    agent_design_id: agent.id,
    agent_version_id: v0.id,
    scenario_id: scenarioIds[0],
    eval_contract_id: shared.id,
    mode: "live",
  });
  await postJson(request, `/runs/${run.id}/evaluate`, { judge_mode: "deterministic" });
  const packets = await (
    await request.get(`${PROJECT}/failure-packets`, { params: { agent_design_id: agent.id } })
  ).json();
  expect(packets).toHaveLength(1);
  await postJson(request, "/fix-proposals", {
    agent_design_id: agent.id,
    target_version_id: v0.id,
    title: "Add a rollback plan",
    rationale: "The first test's answer has no rollback plan.",
    addressed_failure_packet_ids: [packets[0].id],
    validation_contract_ids: [shared.id],
  });

  // The second, newest test opens selected and starts its own proof loop.
  await openAgent(page, name);
  await clickNext(page, "Run current");
  await clickNext(page, "Check answer");
  const analysis = page.locator(".failure-analysis-panel");
  await expect(analysis.getByRole("heading", { name: "Name this failure" })).toBeVisible();
  await analysis.getByLabel("Failure mode").fill("missing rollback plan");
  await analysis.getByLabel(/Review note/).fill("The answer never gives a rollback plan.");
  await analysis.getByRole("button", { name: "Save analysis" }).click();

  await expect(nextAction(page).getByRole("heading", { name: "Generate a fix" })).toBeVisible();
  await expect(nextAction(page).getByRole("button", { name: "Create version", exact: true })).toHaveCount(0);
});
