import { useEffect, useState } from "react";
import {
  getJudgeAgreement,
  listEvalContracts,
  listEvalResultsForContract,
  listJudgeOutputs,
  reviewJudgeOutput,
} from "./api";
import { RUN_PAGE_SIZE } from "./evidenceGroups";
import type { EvalContract, EvalResult, JudgeAgreement, JudgeOutput } from "./types";

type ContractReviews = {
  contract: EvalContract;
  agreement: JudgeAgreement;
  rows: { evalResult: EvalResult; judgeOutput: JudgeOutput }[];
};

type JudgeReviewPanelProps = {
  projectId: string;
  agentId: string;
  onReviewed: () => Promise<void>;
};

function agreementLabel(agreement: JudgeAgreement): string {
  if (agreement.agreement_rate === null) {
    return "No reviews yet";
  }
  return `${agreement.agreed} of ${agreement.reviewed} agreed (${Math.round(agreement.agreement_rate * 100)}%)`;
}

function VerdictBadge({ passed }: { passed: boolean }) {
  return (
    <span className={`judge-verdict-badge ${passed ? "pass" : "fail"}`}>
      {passed ? "Pass" : "Fail"}
    </span>
  );
}

export function JudgeReviewPanel({ projectId, agentId, onReviewed }: JudgeReviewPanelProps) {
  const [groups, setGroups] = useState<ContractReviews[]>([]);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // How many verdicts each contract shows; eval results come newest first, one per run.
  const [shownCounts, setShownCounts] = useState<Record<string, number>>({});
  const shownCount = (contractId: string) => shownCounts[contractId] ?? RUN_PAGE_SIZE;

  async function load() {
    const [contracts, judgeOutputs] = await Promise.all([
      listEvalContracts(projectId, agentId),
      listJudgeOutputs(projectId),
    ]);
    const judgeByEval = new Map(judgeOutputs.map((output) => [output.eval_result_id, output]));
    const loaded = await Promise.all(
      contracts.map(async (contract) => {
        const [evalResults, agreement] = await Promise.all([
          listEvalResultsForContract(projectId, contract.id),
          getJudgeAgreement(projectId, contract.id),
        ]);
        const rows = evalResults.flatMap((evalResult) => {
          const judgeOutput = judgeByEval.get(evalResult.id);
          return judgeOutput ? [{ evalResult, judgeOutput }] : [];
        });
        return { contract, agreement, rows };
      }),
    );
    setGroups(loaded.filter((group) => group.rows.length > 0));
  }

  useEffect(() => {
    setShownCounts({});
    load().catch((caught: Error) => setError(caught.message));
  }, [projectId, agentId]);

  async function submit(judgeOutputId: string, verdict: "agree" | "overrule") {
    setSavingId(judgeOutputId);
    setError(null);
    try {
      await reviewJudgeOutput(projectId, judgeOutputId, {
        verdict,
        reason: (reasons[judgeOutputId] ?? "").trim(),
      });
      setReasons((current) => ({ ...current, [judgeOutputId]: "" }));
      await Promise.all([load(), onReviewed()]);
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setSavingId(null);
    }
  }

  if (groups.length === 0 && !error) {
    return null;
  }

  return (
    <div className="judge-review-panel" role="region" aria-label="Judge agreement">
      <h4>Judge agreement</h4>
      {error ? <p className="error-text">{error}</p> : null}
      {groups.map(({ contract, agreement, rows }) => (
        <div className="judge-review-contract" key={contract.id} aria-label={contract.name} role="group">
          <div className="workflow-evidence-header">
            <strong>{contract.name}</strong>
            <span className="judge-agreement-rate">{agreementLabel(agreement)}</span>
          </div>
          {rows.slice(0, shownCount(contract.id)).map(({ evalResult, judgeOutput }) => {
            const review = judgeOutput.review;
            const judgePassed = review ? review.judge_passed : evalResult.passed;
            const reason = reasons[judgeOutput.id] ?? "";
            const saving = savingId === judgeOutput.id;
            return (
              <div className="judge-review-row" key={judgeOutput.id} data-testid="judge-review-row">
                <div className="judge-review-verdicts">
                  <span>
                    Judge <VerdictBadge passed={judgePassed} />
                  </span>
                  {review ? (
                    <span>
                      {review.verdict === "agree" ? "Agreed" : "Overruled"} · Result{" "}
                      <VerdictBadge passed={evalResult.passed} />
                    </span>
                  ) : (
                    <span className="muted-copy">Not reviewed</span>
                  )}
                </div>
                {review ? <p className="judge-review-reason">{review.reason}</p> : null}
                <details className="judge-output-details">
                  <summary>Judge reasoning</summary>
                  <p className="judge-output-text">{judgeOutput.output}</p>
                </details>
                <div className="judge-review-actions">
                  <input
                    aria-label="Reason"
                    placeholder="Reason"
                    value={reason}
                    onChange={(event) =>
                      setReasons((current) => ({ ...current, [judgeOutput.id]: event.target.value }))
                    }
                  />
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={saving || reason.trim() === ""}
                    onClick={() => submit(judgeOutput.id, "agree")}
                  >
                    Agree
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={saving || reason.trim() === ""}
                    onClick={() => submit(judgeOutput.id, "overrule")}
                  >
                    Overrule
                  </button>
                </div>
              </div>
            );
          })}
          {rows.length > shownCount(contract.id) ? (
            <button
              className="secondary-button"
              type="button"
              onClick={() =>
                setShownCounts((current) => ({
                  ...current,
                  [contract.id]: shownCount(contract.id) + RUN_PAGE_SIZE,
                }))
              }
            >
              Show older verdicts ({rows.length - shownCount(contract.id)} more)
            </button>
          ) : null}
        </div>
      ))}
    </div>
  );
}
