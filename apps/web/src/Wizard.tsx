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

type WizardStep = "describe" | "review" | "run" | "failure" | "fix" | "compare" | "done";

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

type WizardState = {
  step: WizardStep;
  projectId: string;

  // step 1
  description: string;

  // step 2 — generated preview
  preview: GuidedSetupPreview | null;
  previewEdits: GuidedSetupPreview | null; // user-edited version

  // step 3 — confirmed agent
  agent: OutcomeAgentResponse | null;
  runMode: "mock" | "live";

  // step 4 — baseline run + eval
  baselineRun: RunRecord | null;
  baselineEval: EvalResult | null;
  langfuseBaselineUrl: string | null;

  // step 5 — failure naming
  whatWentWrong: string;
  whatShouldHappen: string;

  // step 6 — fix
  fix: FixGenerated | null;
  fixEdited: string; // user-edited instructions

  // step 7 — v1 run + eval + compare
  candidateRun: RunRecord | null;
  candidateEval: EvalResult | null;
  comparison: Comparison | null;
  langfuseCandidateUrl: string | null;
};

function initialState(projectId: string): WizardState {
  return {
    step: "describe",
    projectId,
    description: "",
    preview: null,
    previewEdits: null,
    agent: null,
    runMode: "live",
    baselineRun: null,
    baselineEval: null,
    langfuseBaselineUrl: null,
    whatWentWrong: "",
    whatShouldHappen: "",
    fix: null,
    fixEdited: "",
    candidateRun: null,
    candidateEval: null,
    comparison: null,
    langfuseCandidateUrl: null,
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
): Promise<RunRecord> {
  return apiPost(
    `/projects/${projectId}/runs`,
    {
      agent_design_id: agent.agent.id,
      agent_version_id: agent.version.id,
      scenario_id: agent.scenario.id,
      eval_contract_id: agent.eval_contract.id,
      mode,
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
): Promise<FixGenerated> {
  return apiPost(`/projects/${projectId}/fix-proposals/generate`, {
    agent_design_id: agentId,
    target_version_id: versionId,
    addressed_failure_packet_ids: packetIds,
    validation_contract_id: contractId,
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
): Promise<RunRecord> {
  return apiPost(
    `/projects/${projectId}/runs`,
    {
      agent_design_id: agent.agent.id,
      agent_version_id: candidateVersionId,
      scenario_id: agent.scenario.id,
      eval_contract_id: agent.eval_contract.id,
      mode,
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
};

export function Wizard({ projectId, onAgentCreated, onDone }: Props) {
  const [state, setState] = useState<WizardState>(() => initialState(projectId));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
      setError(err instanceof Error ? err.message : label + " failed.");
      return null;
    } finally {
      setBusy(false);
    }
  }

  // Step 1 → 2: generate preview
  async function handleGenerate() {
    if (!state.description.trim()) return;
    const preview = await go("Generate", () =>
      previewSetup(projectId, state.description),
    );
    if (!preview) return;
    update({ step: "review", preview, previewEdits: { ...preview } });
  }

  // Step 2 → 3: commit agent with reviewed values
  async function handleConfirm() {
    const edits = state.previewEdits;
    if (!edits) return;
    const agent = await go("Confirm", () =>
      commitAgent(projectId, state.description, edits),
    );
    if (!agent) return;
    update({ step: "run", agent });
    onAgentCreated(agent.agent.id);
  }

  // Step 3: run baseline
  async function handleRun() {
    const { agent, runMode } = state;
    if (!agent) return;
    const judgeMode = "live";
    const baselineRun = await go("Run", () => runAgent(projectId, agent, runMode));
    if (!baselineRun) return;
    const baselineEval = await go("Evaluate", () =>
      evaluateRun(projectId, baselineRun.id, agent.eval_contract.id, judgeMode),
    );
    if (!baselineEval) return;
    const langfuseBaselineUrl = await getLangfuseUrl(projectId, baselineRun.id);
    if (baselineEval.passed) {
      update({ step: "done", baselineRun, baselineEval, langfuseBaselineUrl });
    } else {
      update({ step: "failure", baselineRun, baselineEval, langfuseBaselineUrl });
    }
  }

  function agentId(): string {
    return state.agent?.agent.id ?? "";
  }

  // Step 4 → 5: generate fix from failure description
  async function handleGenerateFix() {
    const { agent, baselineEval } = state;
    if (!agent || !baselineEval) return;
    const packets = await go("Load failures", () =>
      listFailurePackets(projectId, agent.agent.id),
    );
    if (!packets) return;
    const fix = await go("Generate fix", () =>
      generateFix(
        projectId,
        agent.agent.id,
        agent.version.id,
        packets.map((p) => p.id),
        agent.eval_contract.id,
      ),
    );
    if (!fix) return;
    update({ step: "fix", fix, fixEdited: fix.proposed_instructions });
  }

  // Step 5 → 6: apply fix and run v1
  async function handleApplyFix() {
    const { agent, fix, fixEdited, baselineRun, runMode } = state;
    if (!agent || !fix || !baselineRun) return;
    const judgeMode = "live";

    const packets = await go("Load failures", () =>
      listFailurePackets(projectId, agent.agent.id),
    );
    if (!packets) return;

    const proposal = await go("Save fix proposal", () =>
      createFixProposal(
        projectId,
        agent.agent.id,
        agent.version.id,
        packets.map((p) => p.id),
        agent.eval_contract.id,
        fixEdited,
        fix.rationale,
      ),
    );
    if (!proposal) return;

    const candidateVersion = await go("Create v1", () =>
      createCandidateVersion(
        projectId,
        agent.agent.id,
        agent.version.id,
        fixEdited,
        proposal.id,
      ),
    );
    if (!candidateVersion) return;

    const candidateRun = await go("Run v1", () =>
      runCandidateVersion(projectId, agent, candidateVersion.id, runMode),
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
    update({ step: "compare", candidateRun, candidateEval, comparison, langfuseCandidateUrl });
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
    const { agent, runMode } = state;
    if (!agent) return null;
    return (
      <div className="wizard-body">
        <p className="wizard-eyebrow">Step 2 of 5 — Run the agent</p>
        <h2 className="wizard-heading">{agent.agent.name}</h2>

        <div className="wizard-test-input">
          <p className="output-label">Test input</p>
          <blockquote className="wizard-blockquote">{agent.scenario.input}</blockquote>
        </div>

        <div className="wizard-run-mode">
          <span className="wizard-label-sub">Run mode</span>
          <div className="run-mode-control">
            <button
              className={runMode === "mock" ? "mode-option active" : "mode-option"}
              type="button"
              onClick={() => update({ runMode: "mock" })}
            >
              Mock
            </button>
            <button
              className={runMode === "live" ? "mode-option active" : "mode-option"}
              type="button"
              onClick={() => update({ runMode: "live" })}
            >
              Live Anthropic
            </button>
          </div>
        </div>

        {busy ? <Spinner label={runMode === "live" ? "Running (this may take a minute)..." : "Running..."} /> : null}

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
    const { baselineRun, baselineEval, langfuseBaselineUrl } = state;
    if (!baselineRun || !baselineEval) return null;
    return (
      <div className="wizard-body">
        <p className="wizard-eyebrow">Step 3 of 5 — Name the failure</p>
        <h2 className="wizard-heading">What went wrong?</h2>

        <EvalSummary evalResult={baselineEval} />
        <OutputBlock output={baselineRun.output} label="Agent output" />

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
    } = state;
    if (!baselineRun || !candidateRun || !candidateEval || !comparison) return null;
    const improved = candidateEval.passed && !baselineEval?.passed;
    const stillFailing = !candidateEval.passed;
    return (
      <div className="wizard-body">
        <p className="wizard-eyebrow">Step 5 of 5 — Compare</p>
        <h2 className="wizard-heading">
          {improved ? "Fixed." : stillFailing ? "Still failing — iterate?" : "Compared."}
        </h2>

        <div className="compare-grid">
          <div>
            <p className="output-label">v0 output</p>
            <pre className="agent-output">{baselineRun.output || "(no output)"}</pre>
            <TraceLink url={langfuseBaselineUrl} label="v0 trace in Langfuse →" />
          </div>
          <div>
            <p className="output-label">v1 output</p>
            <pre className="agent-output">{candidateRun.output || "(no output)"}</pre>
            <TraceLink url={langfuseCandidateUrl} label="v1 trace in Langfuse →" />
          </div>
        </div>

        <div className="compare-verdicts">
          <div className={`verdict-badge ${baselineEval?.passed ? "pass" : "fail"}`}>
            v0: {baselineEval?.passed ? "passed" : "failed"}
          </div>
          <div className={`verdict-badge ${candidateEval.passed ? "pass" : "fail"}`}>
            v1: {candidateEval.passed ? "passed" : "failed"}
          </div>
        </div>

        {comparison.summary ? (
          <div className="compare-summary">
            <p className="output-label">Comparison summary</p>
            <p className="wizard-hint">{comparison.summary}</p>
          </div>
        ) : null}

        <div className="wizard-actions">
          {stillFailing ? (
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
                })
              }
            >
              Iterate — name the failure again →
            </button>
          ) : (
            <button className="primary-button" type="button" onClick={() => onDone(agentId())}>
              View evidence →
            </button>
          )}
        </div>
      </div>
    );
  }

  function renderDone() {
    const { baselineRun, baselineEval, langfuseBaselineUrl } = state;
    return (
      <div className="wizard-body">
        <p className="wizard-eyebrow">Done</p>
        <h2 className="wizard-heading">Passed on the first run.</h2>
        <p className="wizard-hint">No fix needed — the agent already satisfies the criterion.</p>
        {baselineRun && <OutputBlock output={baselineRun.output} label="Agent output" />}
        {baselineEval && <EvalSummary evalResult={baselineEval} />}
        <TraceLink url={langfuseBaselineUrl} label="Open trace in Langfuse →" />
        <div className="wizard-actions">
          <button className="primary-button" type="button" onClick={() => onDone(agentId())}>
            View evidence →
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const showIndicator = state.step !== "describe" && state.step !== "done";

  return (
    <div className="wizard-shell" ref={topRef}>
      {showIndicator ? <StepIndicator step={state.step} /> : null}

      {error ? <div className="wizard-error">{error}</div> : null}

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
