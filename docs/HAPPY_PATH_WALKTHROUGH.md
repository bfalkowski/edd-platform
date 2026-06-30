# Happy Path Walkthrough

This is the canonical manual walkthrough for the EDD Platform guided flow.
It should stay aligned with the UI and API as the product changes.

Langfuse is a first-class dependency. Every live run links to a Langfuse trace.
The wizard will prompt you to start Langfuse if it is not running.

## Preconditions

Start the local platform:

```bash
./scripts/dev.sh
```

Start Langfuse:

```bash
./scripts/dev_langfuse.sh
```

Open:

```text
http://localhost:5173
```

Credentials required in `.env.local` (not committed):

```text
ANTHROPIC_API_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
```

---

## Happy Path: Prove One Agent Improvement

The guided wizard walks through five steps. Each step shows exactly one thing
to look at and one action to take.

### Step 1 — Describe your agent

Click **New agent** or open the guided flow.

Enter one sentence:

```text
What should this agent do?
```

Example:

```text
Help a support engineer understand a failed deployment and recommend a safe next action.
```

Click **Generate**.

Expected result:

- The platform generates an agent name, a test input, and a rubric.
- All three are shown in editable fields.
- Review and adjust any of them.

*Human decision: Does the rubric capture what you actually care about?*

Click **Looks right — run it**.

Expected result:

- Agent, version, scenario, and eval contract are created.
- The wizard advances to Step 2.

---

### Step 2 — Run

The agent runs live against the generated test input.

Expected result:

- The agent's output appears.
- A **"Open trace in Langfuse →"** link appears.
- A pass / fail verdict appears with a one-line judge summary.

Open the Langfuse trace to see what the agent actually did — tool calls,
message sequence, token counts, latency.

- If the answer **passed** → the wizard shows a done state. No fix needed.
- If the answer **failed** → the wizard advances to Step 3.

---

### Step 3 — Name the failure

The judge verdict and failed checks are shown.

A **"Open trace in Langfuse →"** link is shown again.

Open the trace. Find the moment it went wrong. Come back and answer:

```text
What went wrong? (one sentence)
What should it have done instead? (optional)
```

Example:

```text
What went wrong: The agent recommended redeploying immediately without checking logs.
What should it have done: Ask for the error logs before recommending any action.
```

*Human decision: Name the failure. One sentence. That's the only required input.*

Click **Generate a fix**.

Expected result:

- The platform reads your failure description, the rubric, the run output,
  and the original instructions.
- A fix proposal is generated.
- The wizard advances to Step 4.

---

### Step 4 — Review the fix

A diff of the old instructions vs the proposed new instructions is shown.

Review the changes. Edit inline if needed.

*Human decision: Does this fix address what you named in Step 3?*

Click **Run v1**.

Expected result:

- A candidate version is created from the new instructions.
- The candidate runs against the same test input.
- The wizard advances to Step 5.

---

### Step 5 — Compare

The v0 and v1 outputs are shown side by side.

The before / after verdict is shown.

A **"Open v1 trace in Langfuse →"** link is shown.

- If v1 **passed** → "Fixed. Evidence saved." The full evidence chain is
  available: scenario, eval contract, baseline run, failure description,
  fix proposal, candidate run, comparison.
- If v1 **still fails** → "Still failing — what's different now?" The wizard
  returns to Step 3 with the new run's context.

---

## Pass Criteria

The happy path is healthy when a user can:

1. Describe an agent in one sentence.
2. Review and confirm a generated rubric and test input.
3. Run the agent and open its Langfuse trace.
4. See a clear pass or fail verdict.
5. Name the failure in one sentence after reviewing the trace.
6. Review a generated fix as a before/after diff.
7. Run v1 and see a side-by-side comparison.
8. See the full evidence chain when v1 passes.
9. Return to Step 3 and iterate when v1 still fails.

If any step fails or requires the user to navigate outside the wizard,
update this document and the product. Do not let the walkthrough drift
from the actual UI.

---

## Automated Smoke

The full proof loop E2E exercises the backend plumbing for all wizard steps:

```bash
uv run scripts/outcome_agent_lifecycle_e2e.py
```

Expected result:

- All cases pass through: draft → baseline run → evaluate → diagnose →
  generate fix → create v1 → run v1 → compare.
- 5 passed, 0 failed.

The Anthropic jobs E2E exercises live browsing and single-call discipline:

```bash
uv run scripts/anthropic_jobs_e2e.py
```

Expected result:

- Agent finds relevant Anthropic jobs in one browse_webpage call.
- Judge confirms specific titles, grounded in page content.
- PASS.
