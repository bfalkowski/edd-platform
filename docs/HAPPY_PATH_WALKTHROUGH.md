# Happy Path Walkthrough

This is the canonical manual walkthrough for proving the EDD Platform happy path.
It should stay aligned with the UI and API as the product changes.

The walkthrough has two modes:

- **Mock mode:** deterministic, no provider key required, suitable for local checks and CI-adjacent validation.
- **Live mode:** uses OpenAI for agent or judge calls and local Langfuse for trace visibility when configured.

## Preconditions

Start the local platform:

```bash
./scripts/dev.sh
```

Open:

```text
http://localhost:5173
```

Optional live tracing setup:

```bash
./scripts/dev_langfuse.sh
```

Then restart `./scripts/dev.sh` so the API loads the Langfuse environment.

## Happy Path: Prove One Agent Improvement

### 1. Create The Agent

In the left navigation, choose **New agent**.

Use a simple initial behavior that is likely to fail the target contract:

```text
Agent name: Customer Support Escalation Agent
Agent intent: Help support engineers understand an escalation and recommend a safe next action.
```

Expected result:

- The agent appears in the left navigation.
- The main workspace shows the created agent.
- An `AGENT_DESIGN` evidence artifact exists.

### 2. Set The Run Mode

Use the top run mode control.

For the default walkthrough, choose:

```text
Mock
```

Expected result:

- The header says the platform is local.
- Mock mode copy explains that deterministic local behavior is used.

### 3. Define The Test

In **Proof loop**, define a scenario and success criteria.

Example scenario:

```text
A customer reports that a production deployment failed after a permissions migration.
The customer is blocked and asks what to do next.
```

Example success criteria:

```text
safe rollback plan
```

Click **Define test**.

Expected result:

- A scenario is stored.
- An eval contract is stored.
- Evidence artifacts appear for the scenario and contract.
- The next action advances to running the original agent.

### 4. Run The Original Agent

Click **Run original**.

Expected result:

- A baseline agent version is created if one does not already exist.
- A baseline run is created.
- A `RUN_RESULT` evidence artifact appears.
- The next action advances to checking the original run.

### 5. Check The Original Run

Click **Check original**.

Expected result:

- An eval result is created against the contract.
- A judge output is created.
- If the run does not satisfy the success criteria, a failure packet is created.
- The next action advances to proposing a fix.

### 6. Propose One Fix

Click **Propose fix**.

Expected result:

- A bounded fix proposal appears.
- The fix proposal is linked to the failure packet.
- The next action advances to creating the candidate.

### 7. Create The Candidate

Click **Create candidate**.

Expected result:

- A candidate agent version is created.
- The candidate references the fix proposal.
- The next action advances to running the candidate.

### 8. Run The Candidate

Click **Run candidate**.

Expected result:

- The same scenario is run against the candidate version.
- A second run artifact appears.
- The next action advances to checking the candidate.

### 9. Check The Candidate

Click **Check candidate**.

Expected result:

- A candidate eval result is created against the same contract.
- A judge output is created.
- The next action advances to comparing original vs candidate.

### 10. Compare Improvement

Click **Compare**.

Expected result:

- A comparison artifact is created.
- The comparison shows whether the candidate improved, regressed, or stayed flat.
- The workspace shows the evidence chain:
  - scenario
  - eval contract
  - baseline version
  - baseline run
  - baseline eval
  - failure packet
  - fix proposal
  - candidate version
  - candidate run
  - candidate eval
  - comparison

## Tool Registry Happy Path

Tools are platform-owned. Draft tools are not assignable until approved.

### 1. Open Tool Management

In the agent workspace, click **Manage tools**.

Expected result:

- The right panel opens to **Available tools**.
- Draft tools appear above the tool creation form.
- Approved tools appear under **Assigned to this agent**.

### 2. Create A Draft Tool

Use the **Define tool schema** form.

Example:

```text
Tool name: lookup_ticket
Description: Look up a support ticket by id.
Output description: Ticket status and summary.
Mock response: Ticket is open and awaiting customer logs.
```

The default schemas include examples for strings, dates, integers, numbers,
booleans, enums, and arrays.

Click **Create draft**.

Expected result:

- The tool appears under **Draft tools**.
- A `TOOL_DEFINITION` artifact is created.
- The tool is not yet assigned to the agent.

### 3. Approve And Assign The Tool

Click the draft row action:

```text
Approve and assign
```

Expected result:

- The tool status changes to `approved`.
- The tool moves into the approved/assigned area.
- The selected agent allowlist includes the tool.

Current limitation:

- Approval and assignment do not guarantee execution for every custom tool yet.
- The runner must still add adapters for each implementation kind, such as
  `mock`, `http`, `mcp`, `python`, or `builtin`.

## Ad Hoc Run Happy Path

Use ad hoc runs to try an agent without advancing the proof loop.

### 1. Open The Agent Menu

In the left navigation, open the agent row menu.

Choose:

```text
Try scenario
```

Expected result:

- The right panel opens an **Ad hoc run** surface.

### 2. Run A Scenario

Enter scenario text and click:

```text
Run ad hoc
```

Expected result:

- The run is stored as evidence.
- In live mode, a trace link appears when Langfuse is configured.
- The result can be opened from the right panel.

## Live Mode Happy Path

Live mode requires:

```bash
OPENAI_API_KEY=...
```

The key should be stored in `.env.local`, not committed.

Run:

```bash
./scripts/dev_langfuse.sh
./scripts/dev.sh
```

Then choose **Live OpenAI** in the UI.

Expected result:

- Agent runs use OpenAI.
- Local Langfuse traces are linked when Langfuse is running.
- Platform evidence remains the source of truth.

## Automated Smoke

The live Langfuse smoke script exercises agent creation, live run, live eval,
and trace lookup:

```bash
python scripts/live_langfuse_e2e.py
```

Expected result:

- The script creates a live E2E agent.
- The platform stores run and eval evidence.
- The run has a trace reference when local Langfuse is available.

## Pass Criteria

The happy path is healthy when a user can:

1. Create an agent.
2. Define a scenario and success criteria.
3. Run the original behavior.
4. Evaluate the original behavior.
5. Produce a failure packet.
6. Produce one bounded fix.
7. Create a candidate version.
8. Run and evaluate the candidate.
9. Compare original vs candidate.
10. Inspect all generated evidence artifacts.
11. Create a draft tool.
12. Approve and assign the tool to the selected agent.
13. Run an ad hoc scenario.
14. In live mode, open a linked Langfuse trace.

If any step fails, update this document or the product. Do not let the
walkthrough drift from the actual UI.
