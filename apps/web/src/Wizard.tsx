/**
 * Guided wizard: describe → review → run → name failure → fix → compare.
 * Each step shows exactly one thing and one action.
 */
import { ExternalLink, Loader } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const apiBase = "/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type WizardStep = "describe" | "review" | "run" | "failure" | "fix" | "compare" | "done";

type GuidedSetupPreview = {
  agent_name: string;
  test_input: string;
  rubric: string;
};

type OutcomeAgentResponse = {
  agent: { id: string; name: string; intent: string; allowed_tool_names: string[] };
  version: { id: string; version_label: string; instructions: string };
  scenario: { id: string; input: string };
  eval_contract: { id: string; checks: Array<{ id: string; type: string; value?: string }> };
};

type RunRecord = {
  id: string;
  status: string;
  output: string;
  artifact_ids: string[];
};

type EvalResult = {
  id: string;
  passed: boolean;
  checks: Array<{ check_id: string; passed: boolean; notes?: string }>;
};

type FixGenerated = {
  proposed_instructions: string;
  rationale: string;
};

type FailurePacket = { id: string };

type Comparison = { id: string; summary: string };

export type WizardState = {
  step: WizardStep;
  projectId: string;

  // step 1
  description: string;

  // step 2 — generated preview
  preview: GuidedSetupPreview | null;
  previewEdits: GuidedSetupPreview | null; // user-edited version

  // model override (set in review step, used for all runs)
  model: string;

  // step 3 — confirmed agent
  agent: OutcomeAgentResponse | null;
  // step 4 — baseline run + eval
  baselineRun: RunRecord | null;
  baselineEval: EvalResult | null;
  langfuseBaselineUrl: string | null;

  // step 5 — failure naming + eval check editing
  whatWentWrong: string;
  whatShouldHappen: string;
  editedChecks: Array<{ id: string; type: string; value?: string }>;

  // step 6 — fix
  fix: FixGenerated | null;
  fixEdited: string; // user-edited instructions

  // step 7 — v1 run + eval + compare
  candidateRun: RunRecord | null;
  candidateEval: EvalResult | null;
  comparison: Comparison | null;
  langfuseCandidateUrl: string | null;

  // iteration tracking
  iterationCount: number;
  acceptedWithFailure: boolean;
  // tracks the most recent version id so v2+ are parented correctly
  currentVersionId: string | null;
};

function initialState(projectId: string): WizardState {
  return {
    step: "describe",
    projectId,
    description: "",
    preview: null,
    previewEdits: null,
    model: "claude-haiku-4-5-20251001",
    agent: null,
    baselineRun: null,
    baselineEval: null,
    langfuseBaselineUrl: null,
    whatWentWrong: "",
    whatShouldHappen: "",
    editedChecks: [],
    fix: null,
    fixEdited: "",
    candidateRun: null,
    candidateEval: null,
    comparison: null,
    langfuseCandidateUrl: null,
    iterationCount: 0,
    acceptedWithFailure: false,
    currentVersionId: null,
  };
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

async function apiPost<T>(path: string, body: unknown, timeout = 120000): Promise<T> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(`${apiBase}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error((detail as { detail?: string }).detail ?? `${res.status} ${res.statusText}`);
    }
    return res.json();
  } finally {
    clearTimeout(id);
  }
}

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${apiBase}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export async function fetchAgentWizardState(projectId: string, agentId: string): Promise<OutcomeAgentResponse> {
  return apiGet(`/projects/${projectId}/agent-designs/${agentId}/wizard-state`);
}

async function previewSetup(projectId: string, description: string): Promise<GuidedSetupPreview> {
  return apiPost(`/projects/${projectId}/guided/setup`, { description });
}

async function commitAgent(
  projectId: string,
  description: string,
  preview: GuidedSetupPreview,
): Promise<OutcomeAgentResponse> {
  return apiPost(`/projects/${projectId}/agent-designs/from-outcome`, {
    outcome: description,
    name: preview.agent_name,
    rubric: preview.rubric,
    test_input: preview.test_input,
  });
}

async function runAgent(
  projectId: string,
  agent: OutcomeAgentResponse,
  mode: "mock" | "live",
  model?: string,
): Promise<RunRecord> {
  return apiPost(
    `/projects/${projectId}/runs`,
    {
      agent_design_id: agent.agent.id,
      agent_version_id: agent.version.id,
      scenario_id: agent.scenario.id,
      eval_contract_id: agent.eval_contract.id,
      mode,
      model: model || undefined,
    },
    180000,
  );
}

async function evaluateRun(
  projectId: string,
  runId: string,
  contractId: string,
  judgeMode: "deterministic" | "live",
): Promise<EvalResult> {
  return apiPost(`/projects/${projectId}/runs/${runId}/evaluate`, {
    eval_contract_id: contractId,
    judge_mode: judgeMode,
  });
}

async function listFailurePackets(projectId: string, agentId: string): Promise<FailurePacket[]> {
  return apiGet(`/projects/${projectId}/failure-packets?agent_design_id=${agentId}`);
}

async function generateFix(
  projectId: string,
  agentId: string,
  versionId: string,
  packetIds: string[],
  contractId: string,
  failureDescription: string,
): Promise<FixGenerated> {
  return apiPost(`/projects/${projectId}/fix-proposals/generate`, {
    agent_design_id: agentId,
    target_version_id: versionId,
    addressed_failure_packet_ids: packetIds,
    validation_contract_id: contractId,
    failure_description: failureDescription || undefined,
  });
}

async function createFixProposal(
  projectId: string,
  agentId: string,
  versionId: string,
  packetIds: string[],
  contractId: string,
  instructions: string,
  rationale: string,
): Promise<{ id: string }> {
  return apiPost(`/projects/${projectId}/fix-proposals`, {
    agent_design_id: agentId,
    target_version_id: versionId,
    title: "Wizard fix",
    rationale,
    proposed_changes: [{ surface: "instructions", change: instructions }],
    addressed_failure_packet_ids: packetIds,
    validation_contract_ids: [contractId],
    status: "proposed",
  });
}

async function createCandidateVersion(
  projectId: string,
  agentId: string,
  parentVersionId: string,
  instructions: string,
  fixProposalId: string,
): Promise<{ id: string; version_label: string }> {
  return apiPost(`/projects/${projectId}/agent-designs/${agentId}/versions`, {
    parent_version_id: parentVersionId,
    instructions,
    source_fix_proposal_id: fixProposalId,
    status: "candidate",
  });
}

async function runCandidateVersion(
  projectId: string,
  agent: OutcomeAgentResponse,
  candidateVersionId: string,
  mode: "mock" | "live",
  model?: string,
): Promise<RunRecord> {
  return apiPost(
    `/projects/${projectId}/runs`,
    {
      agent_design_id: agent.agent.id,
      agent_version_id: candidateVersionId,
      scenario_id: agent.scenario.id,
      eval_contract_id: agent.eval_contract.id,
      mode,
      model: model || undefined,
    },
    180000,
  );
}

async function createComparison(
  projectId: string,
  baselineRunId: string,
  candidateRunId: string,
  contractId: string,
): Promise<Comparison> {
  return apiPost(`/projects/${projectId}/comparisons`, {
    baseline_run_id: baselineRunId,
    candidate_run_id: candidateRunId,
    eval_contract_id: contractId,
  });
}

async function updateContractChecks(
  projectId: string,
  contractId: string,
  checks: Array<{ id: string; type: string; value?: string }>,
): Promise<void> {
  await apiPost(`/projects/${projectId}/eval-contracts/${contractId}/checks`, { checks });
}

async function getLangfuseUrl(projectId: string, runId: string): Promise<string | null> {
  try {
    type TraceRef = { url?: string | null };
    const refs: TraceRef[] = await apiGet(
      `/projects/${projectId}/trace-refs?run_id=${runId}`,
    );
    return refs[0]?.url ?? null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StepIndicator({ step }: { step: WizardStep }) {
  const steps: { key: WizardStep; label: string }[] = [
    { key: "describe", label: "Describe" },
    { key: "review", label: "Review" },
    { key: "run", label: "Run" },
    { key: "failure", label: "Diagnose" },
    { key: "fix", label: "Fix" },
    { key: "compare", label: "Compare" },
  ];
  const currentIdx = steps.findIndex((s) => s.key === step);
  return (
    <div className="wizard-steps">
      {steps.map((s, i) => (
        <div
          key={s.key}
          className={[
            "wizard-step",
            i < currentIdx ? "done" : "",
            i === currentIdx ? "active" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <span className="wizard-step-dot">{i < currentIdx ? "✓" : i + 1}</span>
          <span className="wizard-step-label">{s.label}</span>
        </div>
      ))}
    </div>
  );
}

function TraceLink({ url, label }: { url: string | null; label: string }) {
  if (!url) return null;
  return (
    <a className="trace-link" href={url} target="_blank" rel="noreferrer">
      <ExternalLink size={14} />
      {label}
    </a>
  );
}

function Spinner({ label }: { label: string }) {
  return (
    <div className="wizard-busy">
      <Loader size={18} className="spin" />
      <span>{label}</span>
    </div>
  );
}

function EvalSummary({ evalResult }: { evalResult: EvalResult }) {
  return (
    <div className={`eval-summary ${evalResult.passed ? "passed" : "failed"}`}>
      <strong>{evalResult.passed ? "Passed" : "Failed"}</strong>
      <ul>
        {evalResult.checks.map((c) => (
          <li key={c.check_id} className={c.passed ? "check-pass" : "check-fail"}>
            {c.passed ? "✓" : "✗"} {c.check_id}
            {c.notes ? <span className="check-notes"> — {c.notes}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function OutputBlock({ output, label }: { output: string; label: string }) {
  return (
    <div className="agent-output-block">
      <p className="output-label">{label}</p>
      <pre className="agent-output">{output || "(no output)"}</pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Wizard component
// ---------------------------------------------------------------------------

type Props = {
  projectId: string;
  onAgentCreated: (agentId: string) => void;
  onDone: (agentId: string) => void;
  resumeState?: Partial<WizardState>;
};

export function Wizard({ projectId, onAgentCreated, onDone, resumeState }: Props) {
  const [state, setState] = useState<WizardState>(() => ({
    ...initialState(projectId),
    ...resumeState,
  }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const retryRef = useRef<(() => void) | null>(null);
  const topRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    topRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.step]);

  function update(patch: Partial<WizardState>) {
    setState((s) => ({ ...s, ...patch }));
  }

  async function go<T>(label: string, fn: () => Promise<T>): Promise<T | null> {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${label} failed.`);
      return null;
    } finally {
      setBusy(false);
    }
  }

  // Register the current handler as the retry target — call this at the top
  // of each handler. Does NOT invoke fn; the handler is already running.
  function withRetry(fn: () => void) {
    retryRef.current = fn;
  }

  // Step 1 → 2: generate preview
  async function handleGenerate() {
    withRetry(handleGenerate);
    if (!state.description.trim()) return;
    const preview = await go("Generate", () =>
      previewSetup(projectId, state.description),
    );
    if (!preview) return;
    update({ step: "review", preview, previewEdits: { ...preview } });
  }

  // Step 2 → 3: commit agent with reviewed values
  async function handleConfirm() {
    withRetry(handleConfirm);
    const edits = state.previewEdits;
    if (!edits) return;
    const agent = await go("Confirm", () =>
      commitAgent(projectId, state.description, edits),
    );
    if (!agent) return;
    update({ step: "run", agent, currentVersionId: agent.version.id });
    onAgentCreated(agent.agent.id);
  }

  // Step 3: run baseline
  async function handleRun() {
    withRetry(handleRun);
    const { agent } = state;
    if (!agent) return;
    const judgeMode = "live";
    const baselineRun = await go("Run", () => runAgent(projectId, agent, "live", state.model));
    if (!baselineRun) return;
    const baselineEval = await go("Evaluate", () =>
      evaluateRun(projectId, baselineRun.id, agent.eval_contract.id, judgeMode),
    );
    if (!baselineEval) return;
    const langfuseBaselineUrl = await getLangfuseUrl(projectId, baselineRun.id);
    if (baselineEval.passed) {
      update({ step: "done", baselineRun, baselineEval, langfuseBaselineUrl });
    } else {
      update({
        step: "failure",
        baselineRun,
        baselineEval,
        langfuseBaselineUrl,
        editedChecks: [...agent.eval_contract.checks],
      });
    }
  }

  function agentId(): string {
    return state.agent?.agent.id ?? "";
  }

  // Step 4 → 5: generate fix from failure description
  async function handleGenerateFix() {
    withRetry(handleGenerateFix);
    const { agent, baselineEval, whatWentWrong, whatShouldHappen, currentVersionId, editedChecks } = state;
    if (!agent || !baselineEval) return;

    // Persist any check edits the user made before generating the fix
    const checksChanged =
      JSON.stringify(editedChecks) !== JSON.stringify(agent.eval_contract.checks);
    if (checksChanged && editedChecks.length > 0) {
      const saved = await go("Save check edits", () =>
        updateContractChecks(projectId, agent.eval_contract.id, editedChecks),
      );
      if (saved === null) return; // go() returns null on error
    }

    const packets = await go("Load failures", () =>
      listFailurePackets(projectId, agent.agent.id),
    );
    if (!packets) return;
    const failureDescription = [whatWentWrong, whatShouldHappen].filter(Boolean).join(" — Instead: ");
    const fix = await go("Generate fix", () =>
      generateFix(
        projectId,
        agent.agent.id,
        currentVersionId ?? agent.version.id,
        packets.map((p) => p.id),
        agent.eval_contract.id,
        failureDescription,
      ),
    );
    if (!fix) return;
    update({ step: "fix", fix, fixEdited: fix.proposed_instructions });
  }

  // Step 5 → 6: apply fix and run candidate
  async function handleApplyFix() {
    withRetry(handleApplyFix);
    const { agent, fix, fixEdited, baselineRun, currentVersionId } = state;
    if (!agent || !fix || !baselineRun) return;
    const judgeMode = "live";
    const parentVersionId = currentVersionId ?? agent.version.id;

    const packets = await go("Load failures", () =>
      listFailurePackets(projectId, agent.agent.id),
    );
    if (!packets) return;

    const proposal = await go("Save fix proposal", () =>
      createFixProposal(
        projectId,
        agent.agent.id,
        parentVersionId,
        packets.map((p) => p.id),
        agent.eval_contract.id,
        fixEdited,
        fix.rationale,
      ),
    );
    if (!proposal) return;

    const candidateVersion = await go("Create next version", () =>
      createCandidateVersion(
        projectId,
        agent.agent.id,
        parentVersionId,
        fixEdited,
        proposal.id,
      ),
    );
    if (!candidateVersion) return;

    const candidateRun = await go("Run v1", () =>
      runCandidateVersion(projectId, agent, candidateVersion.id, "live", state.model),
    );
    if (!candidateRun) return;

    const candidateEval = await go("Evaluate v1", () =>
      evaluateRun(projectId, candidateRun.id, agent.eval_contract.id, judgeMode),
    );
    if (!candidateEval) return;

    const comparison = await go("Compare", () =>
      createComparison(projectId, baselineRun.id, candidateRun.id, agent.eval_contract.id),
    );
    if (!comparison) return;

    const langfuseCandidateUrl = await getLangfuseUrl(projectId, candidateRun.id);
    update({ step: "compare", candidateRun, candidateEval, comparison, langfuseCandidateUrl, currentVersionId: candidateVersion.id });
  }

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  function renderDescribe() {
    return (
      <div className="wizard-body">
        <p className="wizard-eyebrow">Step 1 of 5 — Describe your agent</p>
        <h2 className="wizard-heading">What should this agent do?</h2>
        <p className="wizard-hint">
          One sentence is enough. The platform will generate a name, test input, and
          success criterion for you to review.
        </p>
        <textarea
          className="wizard-textarea"
          placeholder="Help a support engineer understand a failed deployment and recommend a safe next action."
          value={state.description}
          onChange={(e) => update({ description: e.target.value })}
          rows={3}
          autoFocus
        />
        <div className="wizard-actions">
          <button
            className="primary-button"
            type="button"
            disabled={!state.description.trim() || busy}
            onClick={handleGenerate}
          >
            {busy ? "Generating..." : "Generate →"}
          </button>
        </div>
      </div>
    );
  }

  function renderReview() {
    const edits = state.previewEdits;
    if (!edits) return null;
    return (
      <div className="wizard-body">
        <p className="wizard-eyebrow">Step 1 of 5 — Review the generated setup</p>
        <h2 className="wizard-heading">Does this look right?</h2>
        <p className="wizard-hint">Edit any field before confirming.</p>

        <label className="wizard-label">
          Agent name
          <input
            className="wizard-input"
            value={edits.agent_name}
            onChange={(e) => update({ previewEdits: { ...edits, agent_name: e.target.value } })}
          />
        </label>

        <label className="wizard-label">
          Test input{" "}
          <span className="wizard-label-sub">— the message your agent will receive</span>
          <textarea
            className="wizard-textarea"
            rows={3}
            value={edits.test_input}
            onChange={(e) => update({ previewEdits: { ...edits, test_input: e.target.value } })}
          />
        </label>

        <label className="wizard-label">
          Success criterion{" "}
          <span className="wizard-label-sub">— what a passing answer looks like</span>
          <textarea
            className="wizard-textarea"
            rows={4}
            value={edits.rubric}
            onChange={(e) => update({ previewEdits: { ...edits, rubric: e.target.value } })}
          />
        </label>

        <div className="wizard-model-row">
          <label className="wizard-label" style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <span style={{ whiteSpace: "nowrap" }}>Model</span>
            <select
              className="wizard-input"
              style={{ width: "auto" }}
              value={state.model}
              onChange={(e) => update({ model: e.target.value })}
            >
              <option value="claude-haiku-4-5-20251001">Haiku (fast, cheap)</option>
              <option value="claude-sonnet-4-6">Sonnet (balanced)</option>
              <option value="claude-opus-4-8">Opus (most capable)</option>
            </select>
          </label>
        </div>

        <div className="wizard-actions">
          <button
            className="primary-button"
            type="button"
            disabled={
              !edits.agent_name.trim() ||
              !edits.test_input.trim() ||
              !edits.rubric.trim() ||
              busy
            }
            onClick={handleConfirm}
          >
            {busy ? "Saving..." : "Looks right — run it →"}
          </button>
          <button
            className="secondary-button"
            type="button"
            disabled={busy}
            onClick={() => update({ step: "describe" })}
          >
            ← Back
          </button>
        </div>
      </div>
    );
  }

  function renderRun() {
    const { agent } = state;
    if (!agent) return null;
    return (
      <div className="wizard-body">
        <p className="wizard-eyebrow">Step 2 of 5 — Run the agent</p>
        <h2 className="wizard-heading">{agent.agent.name}</h2>

        <div className="wizard-test-input">
          <p className="output-label">Test input</p>
          <blockquote className="wizard-blockquote">{agent.scenario.input}</blockquote>
        </div>

        {busy ? <Spinner label="Running (this may take a minute)..." /> : null}

        <div className="wizard-actions">
          <button
            className="primary-button"
            type="button"
            disabled={busy}
            onClick={handleRun}
          >
            {busy ? "Running..." : "Run →"}
          </button>
        </div>
      </div>
    );
  }

  function renderFailure() {
    const { baselineRun, baselineEval, langfuseBaselineUrl, iterationCount, editedChecks, candidateRun, candidateEval } = state;
    if (!baselineRun || !baselineEval) return null;

    function updateCheck(idx: number, value: string) {
      const next = editedChecks.map((c, i) => (i === idx ? { ...c, value } : c));
      update({ editedChecks: next });
    }

    const deterministicChecks = editedChecks.filter((c) => c.type === "keyword_match" || c.type === "contains");

    return (
      <div className="wizard-body">
        <p className="wizard-eyebrow">
          {iterationCount > 0 ? `Iteration ${iterationCount + 1} — Name the failure` : "Step 3 of 5 — Name the failure"}
        </p>
        <h2 className="wizard-heading">What went wrong?</h2>

        {iterationCount > 0 && (
          <div className="wizard-iteration-context">
            <p className="wizard-hint">
              The previous fix didn't fully resolve the failure. The output below is from v{iterationCount}.
              Describe what's still wrong so the next fix can address it specifically.
            </p>
          </div>
        )}

        <EvalSummary evalResult={baselineEval} />
        <OutputBlock output={baselineRun.output} label={iterationCount > 0 ? `v${iterationCount} output` : "Agent output"} />

        {langfuseBaselineUrl ? (
          <div className="trace-row">
            <TraceLink url={langfuseBaselineUrl} label="Open trace in Langfuse →" />
            <p className="wizard-hint">Open the trace to see exactly what the agent did, then come back.</p>
          </div>
        ) : (
          <p className="wizard-hint muted">
            Start Langfuse to see the full trace with tool calls and token counts.
          </p>
        )}

        {deterministicChecks.length > 0 && (
          <div className="wizard-checks-editor">
            <p className="output-label">Eval checks — edit if the criteria need updating</p>
            {editedChecks.map((check, idx) => {
              if (check.type !== "keyword_match" && check.type !== "contains") return null;
              return (
                <label key={check.id} className="wizard-label">
                  <span className="wizard-check-id">{check.id}</span>
                  <span className="wizard-label-sub">{check.type}</span>
                  <input
                    className="wizard-input"
                    type="text"
                    value={check.value ?? ""}
                    onChange={(e) => updateCheck(idx, e.target.value)}
                  />
                </label>
              );
            })}
          </div>
        )}

        <label className="wizard-label">
          What went wrong?{" "}
          <span className="wizard-label-sub">one sentence</span>
          <textarea
            className="wizard-textarea"
            rows={2}
            placeholder="e.g. The agent gave a generic answer instead of using the specific data it fetched."
            value={state.whatWentWrong}
            onChange={(e) => update({ whatWentWrong: e.target.value })}
          />
        </label>

        <label className="wizard-label">
          What should it have done instead?{" "}
          <span className="wizard-label-sub optional">optional</span>
          <textarea
            className="wizard-textarea"
            rows={2}
            placeholder="e.g. Return a concise, specific answer grounded in what the tool actually returned."
            value={state.whatShouldHappen}
            onChange={(e) => update({ whatShouldHappen: e.target.value })}
          />
        </label>

        {busy ? <Spinner label="Generating fix from failure evidence..." /> : null}

        <div className="wizard-actions">
          <button
            className="primary-button"
            type="button"
            disabled={!state.whatWentWrong.trim() || busy}
            onClick={handleGenerateFix}
          >
            {busy ? "Generating..." : "Generate a fix →"}
          </button>
        </div>
      </div>
    );
  }

  function renderFix() {
    const { fix, fixEdited, agent } = state;
    if (!fix || !agent) return null;
    const original = agent.version.instructions;
    return (
      <div className="wizard-body">
        <p className="wizard-eyebrow">Step 4 of 5 — Review the fix</p>
        <h2 className="wizard-heading">Does this fix address the failure?</h2>

        <div className="fix-diff">
          <div className="fix-diff-pane">
            <p className="output-label">Original instructions (v0)</p>
            <pre className="agent-output diff-old">{original}</pre>
          </div>
          <div className="fix-diff-pane">
            <p className="output-label">Proposed instructions (v1)</p>
            <textarea
              className="wizard-textarea diff-new"
              rows={Math.max(8, fixEdited.split("\n").length + 2)}
              value={fixEdited}
              onChange={(e) => update({ fixEdited: e.target.value })}
            />
          </div>
        </div>

        <div className="wizard-rationale">
          <p className="output-label">Rationale</p>
          <p className="wizard-hint">{fix.rationale}</p>
        </div>

        {busy ? <Spinner label="Applying fix and running v1..." /> : null}

        <div className="wizard-actions">
          <button
            className="primary-button"
            type="button"
            disabled={!fixEdited.trim() || busy}
            onClick={handleApplyFix}
          >
            {busy ? "Running v1..." : "Apply and run v1 →"}
          </button>
        </div>
      </div>
    );
  }

  function renderCompare() {
    const {
      baselineRun,
      candidateRun,
      candidateEval,
      comparison,
      baselineEval,
      langfuseBaselineUrl,
      langfuseCandidateUrl,
      agent,
      iterationCount,
    } = state;
    if (!baselineRun || !candidateRun || !candidateEval || !comparison) return null;
    const stillFailing = !candidateEval.passed;

    if (stillFailing) {
      return (
        <div className="wizard-body">
          <p className="wizard-eyebrow">Step 5 of 5 — Compare</p>
          <h2 className="wizard-heading">Still failing.</h2>

          <div className="compare-grid">
            <div>
              <p className="output-label">v{iterationCount} output (before fix)</p>
              <pre className="agent-output">{baselineRun.output || "(no output)"}</pre>
              <TraceLink url={langfuseBaselineUrl} label={`v${iterationCount} trace →`} />
            </div>
            <div>
              <p className="output-label">v{iterationCount + 1} output (after fix)</p>
              <pre className="agent-output">{candidateRun.output || "(no output)"}</pre>
              <TraceLink url={langfuseCandidateUrl} label={`v${iterationCount + 1} trace →`} />
            </div>
          </div>

          <div className="compare-verdicts">
            <div className={`verdict-badge ${baselineEval?.passed ? "pass" : "fail"}`}>
              v{iterationCount}: {baselineEval?.passed ? "passed" : "failed"}
            </div>
            <div className="verdict-badge fail">v{iterationCount + 1}: failed</div>
          </div>

          {comparison.summary ? (
            <div className="compare-summary">
              <p className="output-label">What changed</p>
              <p className="wizard-hint">{comparison.summary}</p>
            </div>
          ) : null}

          <div className="wizard-actions">
            <button
              className="primary-button"
              type="button"
              onClick={() =>
                update({
                  step: "failure",
                  baselineRun: candidateRun,
                  baselineEval: candidateEval,
                  langfuseBaselineUrl: langfuseCandidateUrl,
                  candidateRun: null,
                  candidateEval: null,
                  comparison: null,
                  langfuseCandidateUrl: null,
                  whatWentWrong: "",
                  whatShouldHappen: "",
                  fix: null,
                  fixEdited: "",
                  iterationCount: iterationCount + 1,
                  editedChecks: state.agent ? [...state.agent.eval_contract.checks] : [],
                })
              }
            >
              Iterate again →
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() =>
                update({
                  step: "done",
                  acceptedWithFailure: true,
                  // promote v1 as the final run shown in evidence
                  baselineRun: candidateRun,
                  baselineEval: candidateEval,
                  langfuseBaselineUrl: langfuseCandidateUrl,
                })
              }
            >
              Accept as-is
            </button>
          </div>
        </div>
      );
    }

    return renderEvidenceChain({
      headline: iterationCount === 0 ? "Fixed." : `Fixed after ${iterationCount + 1} iterations.`,
      agent,
      baselineRun,
      baselineEval,
      langfuseBaselineUrl,
      candidateRun,
      candidateEval,
      langfuseCandidateUrl,
      comparisonSummary: comparison.summary,
    });
  }

  function renderDone() {
    const { baselineRun, baselineEval, langfuseBaselineUrl, agent, acceptedWithFailure, iterationCount } = state;
    const headline = acceptedWithFailure
      ? `Accepted with known failures after ${iterationCount + 1} iteration${iterationCount === 0 ? "" : "s"}.`
      : "Passed on the first run.";
    return renderEvidenceChain({
      headline,
      agent,
      baselineRun,
      baselineEval,
      langfuseBaselineUrl,
      candidateRun: null,
      candidateEval: null,
      langfuseCandidateUrl: null,
      comparisonSummary: null,
    });
  }

  function renderEvidenceChain({
    headline,
    agent,
    baselineRun,
    baselineEval,
    langfuseBaselineUrl,
    candidateRun,
    candidateEval,
    langfuseCandidateUrl,
    comparisonSummary,
  }: {
    headline: string;
    agent: OutcomeAgentResponse | null;
    baselineRun: RunRecord | null;
    baselineEval: EvalResult | null;
    langfuseBaselineUrl: string | null;
    candidateRun: RunRecord | null;
    candidateEval: EvalResult | null;
    langfuseCandidateUrl: string | null;
    comparisonSummary: string | null;
  }) {
    const rubric = agent?.eval_contract.checks.find((c) => c.type === "rubric_judge")?.value ?? null;
    return (
      <div className="wizard-body">
        <p className="wizard-eyebrow">Done</p>
        <h2 className="wizard-heading">{headline}</h2>

        <div className="evidence-chain">
          {/* Agent */}
          <div className="evidence-row">
            <span className="evidence-label">Agent</span>
            <span className="evidence-value">{agent?.agent.name ?? "—"}</span>
          </div>

          {/* Test input */}
          <div className="evidence-row">
            <span className="evidence-label">Test input</span>
            <span className="evidence-value">{agent?.scenario.input ?? "—"}</span>
          </div>

          {/* Rubric */}
          {rubric ? (
            <div className="evidence-row">
              <span className="evidence-label">Success criterion</span>
              <span className="evidence-value">{rubric}</span>
            </div>
          ) : null}

          {/* Baseline output */}
          {baselineRun ? (
            <div className="evidence-section">
              <div className="evidence-section-header">
                <span className="evidence-label">v0 output</span>
                {baselineEval ? (
                  <span className={`verdict-badge ${baselineEval.passed ? "pass" : "fail"}`}>
                    {baselineEval.passed ? "passed" : "failed"}
                  </span>
                ) : null}
                <TraceLink url={langfuseBaselineUrl} label="trace →" />
              </div>
              <pre className="agent-output evidence-output">{baselineRun.output || "(no output)"}</pre>
            </div>
          ) : null}

          {/* Candidate output */}
          {candidateRun ? (
            <div className="evidence-section">
              <div className="evidence-section-header">
                <span className="evidence-label">v1 output</span>
                {candidateEval ? (
                  <span className={`verdict-badge ${candidateEval.passed ? "pass" : "fail"}`}>
                    {candidateEval.passed ? "passed" : "failed"}
                  </span>
                ) : null}
                <TraceLink url={langfuseCandidateUrl} label="trace →" />
              </div>
              <pre className="agent-output evidence-output">{candidateRun.output || "(no output)"}</pre>
            </div>
          ) : null}

          {/* Comparison summary */}
          {comparisonSummary ? (
            <div className="evidence-row">
              <span className="evidence-label">What changed</span>
              <span className="evidence-value">{comparisonSummary}</span>
            </div>
          ) : null}
        </div>

        <div className="wizard-actions">
          <button
            className="primary-button"
            type="button"
            onClick={() => {
              onAgentCreated(agentId()); // refresh sidebar
              setState(initialState(projectId));
            }}
          >
            Start new agent
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const showIndicator = !["describe", "done"].includes(state.step);

  return (
    <div className="wizard-shell" ref={topRef}>
      {showIndicator ? <StepIndicator step={state.step} /> : null}

      {error ? (
        <div className="wizard-error">
          <span>{error}</span>
          {retryRef.current ? (
            <button
              className="wizard-retry-button"
              type="button"
              onClick={() => {
                setError(null);
                retryRef.current?.();
              }}
            >
              Try again
            </button>
          ) : null}
        </div>
      ) : null}

      {state.step === "describe" && renderDescribe()}
      {state.step === "review" && renderReview()}
      {state.step === "run" && renderRun()}
      {state.step === "failure" && renderFailure()}
      {state.step === "fix" && renderFix()}
      {state.step === "compare" && renderCompare()}
      {state.step === "done" && renderDone()}
    </div>
  );
}
