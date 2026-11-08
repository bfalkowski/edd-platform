import { expect, test, type APIRequestContext } from "@playwright/test";

const PROJECT = "/api/projects/project_default";

async function postJson<T>(request: APIRequestContext, path: string, data: object): Promise<T> {
  const response = await request.post(`${PROJECT}${path}`, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy();
  return response.json();
}

/** An agent whose contract the judge passes, evaluated on two runs. */
async function seedJudgedAgent(request: APIRequestContext) {
  const name = `Judged Agent ${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const { agent } = await postJson<{ agent: { id: string } }>(request, "/agent-designs", {
    name,
    intent: "Write one ticket per fix.",
  });
  const scenario = await postJson<{ id: string }>(request, "/scenarios", {
    agent_design_id: agent.id,
    name: "Ticket",
    input: "Write a ticket for the login bug.",
  });
  const contract = await postJson<{ id: string }>(request, "/eval-contracts", {
    agent_design_id: agent.id,
    name: "One fix per ticket",
    scenario_id: scenario.id,
    checks: [{ id: "no_phrase", type: "output_not_contains", value: "purple elephant" }],
  });
  const evalResultIds: string[] = [];
  for (let i = 0; i < 2; i += 1) {
    const run = await postJson<{ id: string }>(request, "/runs", {
      agent_design_id: agent.id,
      scenario_id: scenario.id,
      eval_contract_id: contract.id,
      mode: "mock",
    });
    const evalResult = await postJson<{ id: string; passed: boolean }>(
      request,
      `/runs/${run.id}/evaluate`,
      { judge_mode: "deterministic" },
    );
    expect(evalResult.passed).toBe(true);
    evalResultIds.push(evalResult.id);
  }
  return { name, contractId: contract.id, evalResultIds };
}

test("A reviewer agrees with one judge verdict, overrules another, and sees the agreement rate", async ({
  page,
  request,
}) => {
  const seeded = await seedJudgedAgent(request);
  await page.goto("/");
  await page.getByRole("region", { name: "Agent designs" }).getByText(seeded.name).click();
  await page.getByRole("tab", { name: /Evidence/ }).click();

  const contract = page
    .getByRole("region", { name: "Judge agreement" })
    .getByRole("group", { name: "One fix per ticket" });
  await expect(contract.getByText("No reviews yet")).toBeVisible();
  const rows = contract.getByTestId("judge-review-row");
  await expect(rows).toHaveCount(2);

  const first = rows.nth(0);
  await expect(first.getByRole("button", { name: "Agree" })).toBeDisabled();
  await first.getByLabel("Reason").fill("One fix, clearly scoped.");
  await first.getByRole("button", { name: "Agree" }).click();
  await expect(contract.getByText("1 of 1 agreed (100%)")).toBeVisible();
  await expect(first.getByText("Agreed")).toBeVisible();

  const second = rows.nth(1);
  await second.getByLabel("Reason").fill("Bundles three fixes into one ticket.");
  await second.getByRole("button", { name: "Overrule" }).click();
  await expect(contract.getByText("1 of 2 agreed (50%)")).toBeVisible();
  await expect(second.getByText("Overruled")).toBeVisible();
  await expect(second.getByText("Bundles three fixes into one ticket.")).toBeVisible();

  const agreement = await (
    await request.get(`${PROJECT}/eval-contracts/${seeded.contractId}/judge-agreement`)
  ).json();
  expect(agreement).toMatchObject({ reviewed: 2, agreed: 1, overruled: 1 });
  const results = await Promise.all(
    seeded.evalResultIds.map(async (id) =>
      (await request.get(`${PROJECT}/eval-results/${id}`)).json(),
    ),
  );
  expect(results.filter((result: { passed: boolean }) => !result.passed)).toHaveLength(1);
});
