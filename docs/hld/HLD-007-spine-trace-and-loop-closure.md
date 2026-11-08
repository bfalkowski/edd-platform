# HLD-007: Spine Trace from Run to GateDecision, and the Smallest Loop Closure

## Status

Draft — a plan. No product code changes with this doc.

Traced against `main` at `4dea77f`. Facts marked **verified** were reproduced
against the API with the in-memory store. Facts marked **read** come from the
code alone and were not run.

## Problem

The product promises one loop: a run fails, the user names the failure, a fix
becomes a new version, the new version is compared with the old one, and a
gate decision says whether it is ready. Every object in that loop exists in the
API and is saved. A user still cannot complete the loop in the console:

1. The Proof loop dead-ends after "Save analysis" (T-6).
2. After a page reload it forgets where the user was (T-5).
3. If the user gets past both, the gate still says **blocked**: the v0 failure
   packet stays `open` forever, and the gate counts every open packet for the
   agent. **Verified.** No ticket covered this; it is now T-16.
4. The loop proves one version against one test. Nothing compares versions
   across all saved tests (T-10).

This doc traces each spine object, names where the loop's state lives, checks
error analysis without Langfuse, and orders the smallest set of changes that
closes the loop.

## Goals

- For each object from Run to GateDecision and EvidenceContext: is it built in
  the API, reachable from the UI, saved across a reload, and tested?
- Say where Proof loop state lives and whether it should be a saved object.
- Check the claim that error analysis works without Langfuse.
- Give an ordered plan from a failed run to a gate decision over the saved
  tests, and map T-4, T-5, T-6, T-7, T-8 and T-10 onto it.

## Non-goals

- New spine objects. The plan adds none.
- Background queues, parallel suite runs, score trends (T-10 already excludes
  them).
- Redesigning the wizard or the Error analysis tab.

## 1. Spine trace

"Saved" has two halves. **Server**: the record is written to the platform store
(`platform_records` in Postgres by default, `apps/api/edd_platform_api/storage.py`),
so it survives a page reload and an API restart. **UI restores**: after a
reload, the console shows it again without the user redoing the step.

| Object | Built in API | Reachable from UI | Saved: server | Saved: UI restores | Tested |
|---|---|---|---|---|---|
| Run | Yes. `POST/GET /runs`, list by agent. | Proof loop "Run v0" / "Run version"; wizard. The console always sends `mode: "live"` (`main.tsx:103`). | Yes | Should. `hydrateEddFlow` finds the latest run matching version + scenario + contract. T-5 reports "Not run" after reload; cause not confirmed (see §2). | API: yes (`test_project_scoped_run_*`, live runs with stubbed providers). Browser: no. |
| EvalResult | Yes. `POST /runs/{id}/evaluate`, list by run. | Proof loop "Check answer" / "Check version". | Yes | Yes, through the run it belongs to. | API: yes (`test_contract_driven_run_evaluation_*`). Browser: no. |
| JudgeOutput | Yes. Written by evaluate; `GET /judge-outputs`. | Partly. Judge reasoning shows inside the failure card. Not on the Evidence tab (T-7). | Yes | No. `judgeOutputText` lives in memory (`ProofLoopCtx`) and is only filled by Auto-diagnose. | API: yes (live judge with stubbed client). Browser: no. |
| FailurePacket | Yes. Created by evaluate when a check fails, status `open` (`routers/runs.py:1115`). CRUD routes exist. | Indirectly. It gates "Generate fix", but the console never refreshes packets after evaluate (cause of T-6). Nothing in the console or API ever changes a packet's status. | Yes | Yes, loaded once when the agent is selected. | API: yes. Browser: no. |
| ReviewNote (the Proof loop's "analysis") | Yes. `POST /review-notes`, list by target artifact. | Proof loop "Save analysis". | Yes | No. `analysisNote` lives in memory (`ProofLoopCtx`) and is reset on agent select and reload. | API: yes. Browser: no. |
| FixProposal | Yes. `POST /fix-proposals/generate` (always calls Anthropic, no deterministic mode), `POST /fix-proposals`, `PATCH`. | Proof loop "Generate fix" / "Save fix proposal", unreachable after "Save analysis" (T-6). | Saved proposal: yes. Generated text before "Save": no. | Saved: yes. Generated-but-unsaved text: no. | Create: API yes. Generate: no API test; only `scripts/outcome_agent_lifecycle_e2e.py` (live). |
| AgentVersion (candidate) | Yes. `POST /agent-designs/{id}/versions`, `source_fix_proposal_id`, `parent_version_id`. | Proof loop "Create version". | Yes | Yes, chosen by heuristics (`source_fix_proposal_id`, then status, then label `v1`). | API: yes. Browser: no. |
| Comparison | Yes, one run pair per comparison, same scenario and contract. | Proof loop "Compare". | Yes | Yes (`comparisons[0]`, newest). | API: yes, fixed and mismatched cases. No suite comparison exists. |
| GateDecision | Yes. `POST /gates`, `POST /gates/{id}/decisions`. | Readiness tab, after a candidate eval and a comparison exist. | Yes | Yes (`listGateDecisions`). | API: pass with no failures; block on an open packet. **No test for "pass after a fix", and that case is broken (verified, T-16).** |
| EvidenceContext | `POST /context-packs` assembles a view and is not stored, which matches the spine ("artifacts are the memory"). `EvidenceSummary` is stored as a cache. | Evidence tab and the Error analysis review-set builder. Both read a pack built with purpose `AGENT_PROMPT_REVIEW`, which excludes `RUN_RESULT`, `EVAL_RESULT` and `JUDGE_OUTPUT` (`routers/runs.py` `CONTEXT_PACK_ARTIFACT_TYPES`). This is the root cause of T-7. | Not stored (by design). The artifacts behind it are stored. | Rebuilt on every agent select. | API: purpose filtering is tested. Browser: no. |

Browser end-to-end coverage today is three specs (app loads, tabs render,
wizard reaches its review step). None of them enters the Proof loop. CI does
not run them (T-13).

### Other verified facts

- **Wizard state returns 500 for every agent that has a baseline,** whether it
  came from "New agent" or was created by hand, even before its first run. The
  route looks for `artifact_type == "agent_design"`, but artifacts are stored
  as `AGENT_DESIGN`. The fallback `ArtifactRecord` it builds lacks required
  fields, so Pydantic raises (`routers/agent_designs.py:499`). The lookup also
  ignores `agent_design_id`, so after the casing fix it could return another
  agent's artifact. `handleSelectAgent` swallows the error, so today the wizard
  never resumes for any agent. (T-4.)
- **The deterministic judge always fails rubric checks** ("Live judge required
  for rubric checks", `eval_checks.py:121`). Every "New agent" contract
  includes a rubric check, so without provider keys a "New agent" agent can
  never pass.
- **The mock runner echoes the version's instructions** into its output
  (`edd_runner.run_mock_agent` puts `instructions` into "Design intent"). So
  with an `output_contains` test, a v1 whose instructions contain the phrase
  passes deterministically. That gives a no-key path through the whole loop.

## 2. Where the Proof loop's state lives

Today the loop's position is held in three client-side places, rebuilt from
the API with guesses:

| State | Where | Rebuilt on reload? |
|---|---|---|
| `eddFlow: EddFlowState` (baseline/candidate version, scenario, contract, runs, evals, packets, fix proposal, comparison) | React state in `main.tsx`. Filled by `hydrateEddFlow` on agent select from seven list calls, then patched by each Proof loop handler. | Yes, but with heuristics: `contracts[0]` (most recently updated), `comparisons[0]`, version found by status or label. |
| `proofLoopCtx: ProofLoopCtx` (saved analysis note, analysis form, generated fix text, judge text) | React state in `main.tsx`. | **No.** Reset on every agent select. |
| `WizardState` | `Wizard.tsx`, resumed from `/wizard-state` + `hydrateEddFlow`. | **No**, because `/wizard-state` returns 500. |
| Which agent is open | `selectedId` in `main.tsx`; set to the first agent on load. | **No.** A reload opens the first agent, not the one the user had. |

The server holds every object the loop creates, and the links between them
already describe an iteration:

```text
EvalResult (failed) -> FailurePacket.eval_result_id
FailurePacket       -> FixProposal.addressed_failure_packet_ids
FixProposal         -> AgentVersion.source_fix_proposal_id (+ parent_version_id)
AgentVersion x2     -> Comparison.baseline_version_id / candidate_version_id
Comparison          -> GateDecision.comparison_id
ReviewNote          -> target_artifact_id = the failed eval's artifact
```

**Decision: do not add a saved ProofLoop or Iteration object.** Every step of
the loop is already a saved record, and the links above identify the current
iteration. A separate loop record would be a second source of truth that can
disagree with the evidence. The bugs come from the client patching memory
instead of re-reading what it saved. The fix is one rule:

> The Proof loop shows only what it can derive from saved records, and it
> re-derives after every write.

Two small additions make that rule hold without schema changes:

1. Restore the saved analysis by listing `review-notes` for the failed eval's
   artifact (the route already filters by `target_artifact_id`).
2. Save a generated fix right away as a `FixProposal` with `status: "draft"`.
   The field exists. "Save fix proposal" then moves it to `proposed`. A
   generated fix costs a live call, so it should survive a reload.

Remembering which agent was open is a per-viewer convenience. It belongs in
the URL or `localStorage`, not in the API.

Why T-5 showed "Not run" after a reload is **not confirmed**. Two causes fit
the code: the reload opened the first agent rather than the one in progress,
or `contracts[0]` picked a newer contract (an edited or draft test, see T-9)
than the one the run used. The developer on step 2 should reproduce it first.

## 3. Does error analysis work without Langfuse?

`docs/ARCHITECTURE.md` says Langfuse failures must not "block the core evidence
loop". The README says "Langfuse is required for error analysis."

- **API: yes.** Review corpora, review items with `source_kind` `artifact`,
  `run` or `eval_result` (no Langfuse ref required), annotations
  (`POST /review-annotations`), failure modes (`POST /failure-modes`), and the
  Polars corpus analysis all work with Langfuse off.
  `test_review_corpus_trace_annotation_failure_mode_and_suggestion_flow`
  covers it.
- **UI: no.** Three gaps, in the order a user hits them:
  1. "Pull in new runs" reads the same context pack as the Evidence tab, which
     excludes run outputs and eval results, so it adds nothing (T-7).
  2. The Review step has no in-app note field. The only ways to get an
     annotation are "Sync Langfuse comments" and accepting an agent
     suggestion. With no annotations, it says "No comments synced yet — add a
     comment in Langfuse then sync."
  3. No UI creates a failure mode. `createFailureMode` exists in `api.ts`, but
     nothing calls it. The only other server path that creates one is the
     Langfuse annotation import. With Langfuse off, the "Assign failure mode"
     list and the Confirm step are always empty.

Error analysis is not on the path from a failed run to a gate decision. The
Proof loop names failures through `ReviewNote` and uses the `FailurePacket`
that evaluate creates. So the gaps above matter, but they do not block loop
closure. Note that the Proof loop records the failure mode as free text in
`ReviewNote.metadata.failure_mode`, not as a `FailureMode` record, so the two
tabs do not share a vocabulary yet. Linking them is out of scope here.

## 4. The smallest ordered plan

Target: a user, in the console, goes from a failed run to a fix, a new version,
a comparison across the agent's saved tests, and a gate decision. Each step
keeps working after a reload.

### Shared test approach (applies to steps 2 and 4)

The browser tests for this loop must run without provider keys, but the
console always sends live runs. Generate fix always calls Anthropic, and the
deterministic judge always fails rubric checks. The smallest approach that
needs no product code:

- Use a test with an `output_contains` check, not a rubric. The mock output
  also echoes the agent name and the scenario input, so the expected phrase
  must appear in neither of them. It may appear only in v1's instructions;
  otherwise v0 passes too and the test proves nothing.
- In Playwright, rewrite `POST /runs` and `POST /runs/{id}/evaluate` request
  bodies to `mode: "mock"` / `judge_mode: "deterministic"`, and answer
  `POST /fix-proposals/generate` with fixed instructions that contain the
  expected phrase.
- The mock runner echoes the instructions, so v0 fails and v1 passes, and the
  whole loop runs for real against the API.

Decide this once in step 2 and reuse it in step 4. Do not add a mock mode to
the console.

### Step 1 — Wizard state stops returning 500 (T-4)

Match `AGENT_DESIGN` and filter by `agent_design_id`. Add the API test T-4
describes. Small and independent.

### Step 2 — The Proof loop derives its state from saved records (T-6, with T-5 merged in)

- After every write (run, evaluate, save analysis, generate, save fix, create
  version, compare), re-derive the loop state from the API instead of patching
  memory. This alone removes the T-6 dead end: evaluate creates the packet,
  and the next derivation sees it.
- Restore the saved analysis note and the draft fix proposal (§2).
- Choose the baseline/candidate chain by its links (§2), not by `[0]` and label
  guesses.
- Remember the open agent across reload (URL or `localStorage`).
- Add a unit test over every next-action state, so no state falls through to an
  actionless "Continue the proof loop" card.
- Add one browser test that goes from a failed v0 to "Iteration complete —
  passed", reloading mid-loop after "Save analysis" and again after "Compare".

T-4 must land first so a reload of a wizard-made agent does not hit the 500.

### Step 3 — The gate judges the version being promoted (T-16, new)

Rule: every open packet for the agent blocks, except the packets that the
referenced comparison lists as fixed. So the candidate's own failures and the
comparison's new failures block. Open packets on any other version that no
comparison has shown fixed also block, for example a sibling version from
another fix attempt. The gate never drops a packet just because it belongs to
a different version.
API tests: "fixed → passed", "candidate still fails → blocked", and "an
unfixed open packet on a sibling version → blocked". This is the
step that lets the single-test loop end in a **passed** gate decision. API
only, and independent of steps 1–2.

At this point the loop is closed for one test.

### Step 4 — Suite runs and a suite comparison (T-9, then T-10)

- **API (not blocked by T-9):** "Run all tests" for a version runs and
  evaluates every active scenario/contract pair for the agent, one at a time.
  The **suite result** for a version is the latest eval per (version, scenario,
  contract). No new `SuiteRun` object.
- **Comparison:** add optional per-test rows to `Comparison` (scenario,
  contract, both run and eval ids, outcome `fixed | regressed | still_passing |
  still_failing`) plus totals, created from two version ids. The existing
  single-pair fields stay, so the change is additive and can be rolled back.
- **Gate:** with a suite comparison, any `regressed` or `still_failing` row
  blocks. This extends T-16's rule.
- **UI (needs T-9's test list):** pass count on the test list, the per-test
  comparison, and a regression warning, as T-10 describes.
- Live suites cost one provider call per test, or two with a live judge. Show
  the count before running.

### Step 5 — The Evidence tab shows run outputs and verdicts (T-7)

Build the console's context pack with an allow-list that includes
`RUN_RESULT`, `EVAL_RESULT` and `JUDGE_OUTPUT`, or with no purpose filter. Then
"Pull in new runs" sees live runs too. The gate does not depend on this,
because it reads artifacts on the server. But without it, a user cannot open
the evidence behind a gate decision. It can be done in parallel at any time.
Its acceptance criteria stand.

### Step 6 — Error analysis without Langfuse (T-8)

Off the loop's critical path. Do it after T-7, as planned, and add creating a
failure mode in the app (§3, gap 3) to its scope.

### Order and parallelism

```text
T-4 ──> T-6 (+T-5) ──┐
                     ├──> T-10 (API) ──> T-10 (UI)
T-16 ────────────────┘                      ▲
T-9 ────────────────────────────────────────┘
T-7 ──> T-8          (parallel, off the critical path)
```

T-4, T-16, T-9 and T-7 can start now. T-6 and T-7 both touch `main.tsx`
(`refreshContext` / `buildContextPack`). Expect a small merge, not a
conflict in logic.

## 5. Ticket mapping

| Ticket | Verdict | Change |
|---|---|---|
| T-4 Wizard state 500 | **Keep** | Root cause named in §1. Add: filter the artifact lookup by `agent_design_id`. Also affects manually created agents, not only "New agent". |
| T-5 Reload forgets the loop | **Merge into T-6** | Same root cause: loop state patched in memory instead of derived from saved records. Its acceptance criteria move into T-6. Close T-5 when that PR lands. Still needs T-4 first. |
| T-6 Dead end after Save analysis | **Keep, widened** | Cause confirmed in code: `failurePackets` is never refreshed after evaluate, and "Generate fix" requires it. Absorbs T-5. The no-key browser test uses the shared test approach in §4. |
| T-7 Evidence tab misses runs | **Keep** | Root cause named in §1 (context pack purpose filter). Not on the critical path, so schedule it beside the loop work, not ahead of it. |
| T-8 Error analysis without Langfuse | **Re-scope** | Add in-app failure-mode creation; without it the Confirm step stays empty. Still blocked by T-7. Off the critical path. |
| T-10 Suite runs and comparison | **Re-scope** | Suite result = latest eval per (version, scenario, contract), no new object. Suite comparison = additive rows on `Comparison`. Gate rule extends T-16. Blocked by T-6 and T-16. Only its UI half needs T-9. |
| T-16 (new) Gate blocks after a fix | **New, filed** | Step 3. Without it, the loop cannot end in a passed gate. |

## Risks

- **Re-deriving after every write adds list calls.** There are seven per
  derivation. That is fine at current data sizes. If it becomes slow, add a
  per-agent loop read endpoint later. Do not add a stored loop object.
- **Choosing the chain by links can still be ambiguous** after several fix
  attempts on one version. Pick the newest fix proposal for the failed eval's
  packets, and say so in the UI.
- **Deterministic tests cannot cover rubric checks.** The loop is proven
  without keys only for `output_contains` tests. Rubric behavior stays covered
  by API tests with a stubbed judge client.
- **Changing the gate rule** must not hide failures. Under step 3's rule, the
  gate ignores a packet only when the referenced comparison lists it as fixed.
  T-16's sibling-version test guards this.

## Success criteria

- One browser test, without provider keys, goes from a failed v0 through a
  fix, v1, a comparison, and a **passed** gate decision, with a reload in the
  middle.
- After T-10, the same test runs over at least two saved tests and shows one
  fixed and none regressed. An API test shows a regression that blocks the
  gate.
- No Proof loop state that matters after a reload lives only in React memory,
  apart from unsaved form text.

## How this was checked

- Read the routers, schemas, store, runner and console code listed above.
- Ran two scripts against the API with `EDD_PLATFORM_STORAGE_BACKEND=memory`
  (not committed), which showed:
  - `/wizard-state` returns 500 for a "New agent" agent before and after its
    first run, and for a manually created agent.
  - A "New agent" contract has a rubric check, so a deterministic v1 fails
    even when its output has the phrase.
  - With an `output_contains` contract: v0 fails, v1 passes, the comparison
    says "fixed 1 failure packet(s), left 0 remaining", the v0 packet stays
    `open`, and the gate decision is
    `blocked | Blocking failure packets remain: <v0 packet>`.
- Not run: the console in a browser. The T-5 "Not run" cause and the T-6
  sequence come from the code and the ticket reports, not from a browser
  session.
