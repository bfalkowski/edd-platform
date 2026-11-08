import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const PROJECT = "/api/projects/project_default";

async function postJson<T>(request: APIRequestContext, path: string, data: object): Promise<T> {
  const response = await request.post(`${PROJECT}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

/** Create an agent with a scenario and contract, then seed runs through the API. */
async function seedAgent(
  request: APIRequestContext,
  runs: { live: number; mock: number },
): Promise<{ name: string; id: string; liveRunIds: string[] }> {
  const name = `Evidence Agent ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
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
    name: "Names a next action",
    scenario_id: scenario.id,
    checks: [{ id: "next_action", type: "output_contains", value: "next action" }],
  });
  const modes = [...Array(runs.live).fill("live"), ...Array(runs.mock).fill("mock")];
  const liveRunIds: string[] = [];
  for (const mode of modes) {
    const run = await postJson<{ id: string }>(request, "/runs", {
      agent_design_id: agent.id,
      scenario_id: scenario.id,
      eval_contract_id: contract.id,
      mode,
    });
    await postJson(request, `/runs/${run.id}/evaluate`, { judge_mode: "deterministic" });
    if (mode === "live") liveRunIds.push(run.id);
  }
  return { name, id: agent.id, liveRunIds };
}

async function openAgent(page: Page, name: string) {
  await page.goto("/");
  await page.getByRole("region", { name: "Agent designs" }).getByText(name).click();
  await expect(page.getByRole("tablist", { name: "Agent workspace" })).toBeVisible();
}

function evidenceRows(page: Page, label: string) {
  return page.locator(".workflow-evidence-item > span").filter({ hasText: new RegExp(`^${label}$`) });
}

test("Evidence tab lists every run output, eval result and judge output", async ({ page, request }) => {
  const agent = await seedAgent(request, { live: 3, mock: 0 });
  await openAgent(page, agent.name);

  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(evidenceRows(page, "Run output")).toHaveCount(3);
  await expect(evidenceRows(page, "Eval result")).toHaveCount(3);
  await expect(evidenceRows(page, "Judge output")).toHaveCount(3);
  // Each live run output names the model that answered and how long it took.
  await expect(page.locator(".workflow-evidence-meta")).toHaveCount(3);
  await expect(page.locator(".workflow-evidence-meta").first()).toHaveText(/^stub-model · \d+\.\ds$/);
});

test("Evidence tab groups rows by run and pages older runs", async ({ page, request }) => {
  const agent = await seedAgent(request, { live: 7, mock: 0 });
  await openAgent(page, agent.name);

  await page.getByRole("tab", { name: /Evidence/ }).click();
  const agentSection = page.getByRole("region", { name: "Agent artifacts" });
  await expect(agentSection.getByText("Scenario", { exact: true })).toBeVisible();
  await expect(
    agentSection.locator(".workflow-evidence-item > span", {
      hasText: /^(Run output|Eval result|Judge output|Failure)$/,
    }),
  ).toHaveCount(0);

  // The five newest runs show, each with its own run output, eval and judge rows.
  const runSections = page.getByRole("region", { name: "Run evidence" });
  await expect(runSections).toHaveCount(5);
  for (const section of await runSections.all()) {
    await expect(section.locator(".workflow-evidence-item > span").first()).toHaveText("Run output");
    await expect(section.locator(".workflow-evidence-item > span", { hasText: /^Eval result$/ })).toHaveCount(1);
    await expect(section.locator(".workflow-evidence-item > span", { hasText: /^Judge output$/ })).toHaveCount(1);
  }

  await page.getByRole("button", { name: "Show older runs (2 more)" }).click();
  await expect(runSections).toHaveCount(7);
  await expect(page.getByRole("button", { name: /Show older runs/ })).toHaveCount(0);
});

test("Pull in new runs adds one review item per live run, once", async ({ page, request }) => {
  const agent = await seedAgent(request, { live: 3, mock: 1 });
  // A Langfuse-traced run: the trace link lives on a separate TRACE_REF artifact.
  const tracedRunId = agent.liveRunIds[0];
  await postJson(request, "/trace-refs", {
    provider: "langfuse",
    external_trace_id: "trace-e2e-1",
    run_id: tracedRunId,
    url: "http://langfuse.local/trace/trace-e2e-1",
  });
  await openAgent(page, agent.name);

  await page.getByRole("tab", { name: "Error analysis" }).click();
  await page.getByRole("button", { name: "Pull in new runs" }).click();
  await expect(page.getByText("Added 3 runs to the review set.")).toBeVisible();
  await expect(page.getByText("3 items")).toBeVisible();

  await page.getByRole("button", { name: "Pull in new runs" }).click();
  await expect(page.getByText("All live runs are already in the review set.")).toBeVisible();
  await expect(page.getByText("3 items")).toBeVisible();

  const corpora = await (
    await request.get(`${PROJECT}/review-corpora?agent_design_id=${agent.id}`)
  ).json();
  const items = await (
    await request.get(`${PROJECT}/review-items?corpus_id=${corpora[0].id}`)
  ).json();
  expect(items).toHaveLength(3);
  const traced = items.filter(
    (item: { langfuse_ref: { trace_id: string } | null }) => item.langfuse_ref !== null,
  );
  expect(traced).toHaveLength(1);
  expect(traced[0].langfuse_ref.trace_id).toBe("trace-e2e-1");
  expect(traced[0].langfuse_ref.url).toBe("http://langfuse.local/trace/trace-e2e-1");
});

test("Pull in new runs takes langfuse_ref only from Langfuse trace refs", async ({ page, request }) => {
  const agent = await seedAgent(request, { live: 2, mock: 0 });
  const [otherOnlyRunId, mixedRunId] = agent.liveRunIds;
  // A run traced only by another provider gets no langfuse_ref.
  await postJson(request, "/trace-refs", {
    provider: "otel",
    external_trace_id: "otel-only-1",
    run_id: otherOnlyRunId,
    url: "http://otel.local/trace/otel-only-1",
  });
  // A run with a Langfuse trace and a later trace from another provider keeps the Langfuse one.
  await postJson(request, "/trace-refs", {
    provider: "langfuse",
    external_trace_id: "trace-e2e-mixed",
    run_id: mixedRunId,
    url: "http://langfuse.local/trace/trace-e2e-mixed",
  });
  await postJson(request, "/trace-refs", {
    provider: "otel",
    external_trace_id: "otel-mixed-1",
    run_id: mixedRunId,
    url: "http://otel.local/trace/otel-mixed-1",
  });
  await openAgent(page, agent.name);

  await page.getByRole("tab", { name: "Error analysis" }).click();
  await page.getByRole("button", { name: "Pull in new runs" }).click();
  await expect(page.getByText("Added 2 runs to the review set.")).toBeVisible();

  const corpora = await (
    await request.get(`${PROJECT}/review-corpora?agent_design_id=${agent.id}`)
  ).json();
  const items: { title: string; content: string; langfuse_ref: { trace_id: string; url: string } | null }[] =
    await (await request.get(`${PROJECT}/review-items?corpus_id=${corpora[0].id}`)).json();
  expect(items).toHaveLength(2);
  const traced = items.filter((item) => item.langfuse_ref !== null);
  expect(traced).toHaveLength(1);
  expect(traced[0].langfuse_ref?.trace_id).toBe("trace-e2e-mixed");
  expect(traced[0].langfuse_ref?.url).toBe("http://langfuse.local/trace/trace-e2e-mixed");
});

test("No live runs: the message shows on Error analysis only", async ({ page, request }) => {
  const agent = await seedAgent(request, { live: 0, mock: 1 });
  await openAgent(page, agent.name);

  await page.getByRole("tab", { name: "Error analysis" }).click();
  await page.getByRole("button", { name: "Pull in new runs" }).click();
  const message = page.getByText(/This agent has no live runs yet\. Run a test with a live model/);
  await expect(message).toBeVisible();
  await expect(page.getByText("0 items")).toBeVisible();

  await page.getByRole("tab", { name: "Agent", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Agent", exact: true })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(message).toHaveCount(0);
});

test("A live run output shows the system prompt sent; a mock run output shows none", async ({
  page,
  request,
}) => {
  const agent = await seedAgent(request, { live: 1, mock: 1 });
  await openAgent(page, agent.name);

  await page.getByRole("tab", { name: /Evidence/ }).click();
  const runOutputs = page.locator(".workflow-evidence-item", { hasText: "Run output" });
  await expect(runOutputs).toHaveCount(2);
  const review = page.getByRole("complementary", { name: "Artifact review" });

  // Newest run first: the mock run, which sent no system prompt.
  await runOutputs.nth(0).click();
  await expect(review).toBeVisible();
  await expect(review.getByRole("heading", { name: "System prompt" })).toHaveCount(0);

  // The live run sent the agent's intent as its system prompt.
  await runOutputs.nth(1).click();
  const prompt = review.getByRole("region", { name: "System prompt" });
  await expect(prompt).toBeVisible();
  await expect(prompt.locator("pre")).toHaveText("Answer support questions with a safe next action.");
  // The prompt shows once, in its own section, not inside the run output body.
  await expect(review.getByText("Answer support questions with a safe next action.")).toHaveCount(1);
});

test("An ad hoc run result, which has no run record, still opens in the review panel", async ({
  page,
  request,
}) => {
  const agent = await seedAgent(request, { live: 0, mock: 0 });
  await openAgent(page, agent.name);

  await page.getByRole("button", { name: `Open actions for ${agent.name}` }).click();
  await page.getByRole("menuitem", { name: /Try scenario/ }).click();
  const scratch = page.getByRole("complementary", { name: "Try scenario" });
  await scratch.getByRole("button", { name: "Run ad hoc" }).click();
  await scratch.getByRole("button", { name: "View result" }).click();

  const review = page.getByRole("complementary", { name: "Artifact review" });
  await expect(review).toBeVisible();
  await expect(review.getByText("Run output", { exact: true })).toBeVisible();
  await expect(review.getByRole("heading", { name: "System prompt" })).toHaveCount(0);
});

test("A run lookup that fails for a reason other than 404 says the prompt could not load", async ({
  page,
  request,
}) => {
  const agent = await seedAgent(request, { live: 1, mock: 0 });
  await openAgent(page, agent.name);
  await page.route(/\/runs\/[^/?]+$/, (route) =>
    route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"Boom."}' }),
  );

  await page.getByRole("tab", { name: /Evidence/ }).click();
  await page.locator(".workflow-evidence-item", { hasText: "Run output" }).click();
  const prompt = page
    .getByRole("complementary", { name: "Artifact review" })
    .getByRole("region", { name: "System prompt" });
  await expect(prompt).toContainText("Could not load the system prompt: Boom. (HTTP 500)");
  await expect(prompt.locator("pre")).toHaveCount(0);
});

test("Evidence tab shows the error when an artifact fails to load", async ({ page, request }) => {
  const agent = await seedAgent(request, { live: 1, mock: 0 });
  await openAgent(page, agent.name);

  await page.getByRole("tab", { name: /Evidence/ }).click();
  // Fail only the artifact GET, not its /links call.
  await page.route(/\/artifacts\/[^/?]+$/, (route) =>
    route.request().method() === "GET"
      ? route.fulfill({ status: 500, body: "Internal Server Error" })
      : route.continue(),
  );
  await evidenceRows(page, "Run output").click();

  await expect(page.getByText("Unable to load artifact. (HTTP 500)")).toBeVisible();
  await expect(page.locator(".review-panel")).toHaveCount(0);
});

test("An artifact load error shows once when the tools panel is open on the Evidence tab", async ({
  page,
  request,
}) => {
  const agent = await seedAgent(request, { live: 1, mock: 0 });
  await openAgent(page, agent.name);

  await page.getByRole("tab", { name: "Agent", exact: true }).click();
  await page.getByRole("button", { name: "Manage tools" }).click();
  await expect(page.getByRole("complementary", { name: "Tool marketplace" })).toBeVisible();
  await page.getByRole("tab", { name: /Evidence/ }).click();
  await page.route(/\/artifacts\/[^/?]+$/, (route) =>
    route.request().method() === "GET"
      ? route.fulfill({ status: 500, body: "Internal Server Error" })
      : route.continue(),
  );
  await evidenceRows(page, "Run output").click();

  await expect(page.getByText("Unable to load artifact. (HTTP 500)")).toHaveCount(1);
  await expect(
    page.getByRole("complementary", { name: "Tool marketplace" }).getByText("Unable to load artifact. (HTTP 500)"),
  ).toBeVisible();
});

test("Readiness tab shows the error when creating a gate fails, and clears it on tab switch", async ({
  page,
  request,
}) => {
  const agent = await seedAgent(request, { live: 0, mock: 0 });
  await openAgent(page, agent.name);

  await page.getByRole("tab", { name: "Readiness" }).click();
  await page.route(/\/gates$/, (route) =>
    route.request().method() === "POST"
      ? route.fulfill({ status: 500, json: { detail: "Gate store unavailable" } })
      : route.continue(),
  );
  await page.getByRole("button", { name: "Create gate" }).click();
  await expect(page.getByText("Gate store unavailable (HTTP 500)")).toBeVisible();

  await page.getByRole("tab", { name: /Evidence/ }).click();
  await expect(page.locator(".error-text")).toHaveCount(0);
});
