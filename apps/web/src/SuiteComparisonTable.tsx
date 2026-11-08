import { suiteOutcomeLabels } from "./suite";
import type { Comparison, SavedTest, SuiteTestOutcome } from "./types";

const passedBefore: Record<SuiteTestOutcome, boolean> = {
  fixed: false,
  regressed: true,
  still_passing: true,
  still_failing: false,
};

const passedAfter: Record<SuiteTestOutcome, boolean> = {
  fixed: true,
  regressed: false,
  still_passing: true,
  still_failing: false,
};

type SuiteComparisonTableProps = {
  comparison: Comparison;
  savedTests: SavedTest[];
  baselineLabel: string;
  candidateLabel: string;
  // False once tests or results changed after the comparison; undefined while loading.
  isCurrent: boolean | undefined;
  eyebrow?: string;
};

/** Each test's outcome between two versions, with a warning for any regression. */
export function SuiteComparisonTable({
  comparison,
  savedTests,
  baselineLabel,
  candidateLabel,
  isCurrent,
  eyebrow = "All tests",
}: SuiteComparisonTableProps) {
  const rows = comparison.tests ?? [];
  const totals = comparison.totals;
  const regressed = totals?.regressed ?? rows.filter((row) => row.outcome === "regressed").length;
  const testName = (scenarioId: string) =>
    savedTests.find((test) => test.scenario.id === scenarioId)?.scenario.name ?? scenarioId;
  const result = (passed: boolean) => (
    <span className={`saved-test-result ${passed ? "passed" : "failed"}`}>
      {passed ? "Passed" : "Failed"}
    </span>
  );

  return (
    <section className="suite-comparison" aria-label="Test comparison">
      <div className="suite-comparison-header">
        <p className="artifact-type">
          {eyebrow}: {baselineLabel} → {candidateLabel}
        </p>
        {totals ? (
          <p className="suite-comparison-totals">
            {totals.fixed} fixed · {totals.regressed} regressed · {totals.still_passing} still
            passing · {totals.still_failing} still failing
          </p>
        ) : null}
      </div>
      {isCurrent === false ? (
        <p className="suite-stale-note">
          Out of date: tests or results changed since this comparison. Compare all tests again.
        </p>
      ) : null}
      {regressed > 0 ? (
        <p className="suite-regression-warning" role="alert">
          {regressed === 1 ? "1 test regressed" : `${regressed} tests regressed`}. A regression blocks
          promotion, even if the test you fixed now passes.
        </p>
      ) : null}
      <div className="discovery-corpus-table" role="table" aria-label="Per-test comparison">
        <div className="discovery-corpus-row discovery-corpus-head" role="row">
          <span role="columnheader">Test</span>
          <span role="columnheader">{baselineLabel}</span>
          <span role="columnheader">{candidateLabel}</span>
          <span role="columnheader">Outcome</span>
        </div>
        {rows.map((row) => (
          <div
            className={
              row.outcome === "regressed"
                ? "discovery-corpus-row suite-row-regressed"
                : "discovery-corpus-row"
            }
            role="row"
            key={row.scenario_id}
          >
            <span role="cell">{testName(row.scenario_id)}</span>
            <span role="cell">{result(passedBefore[row.outcome])}</span>
            <span role="cell">{result(passedAfter[row.outcome])}</span>
            <span role="cell">
              <span className={`suite-outcome ${row.outcome}`}>
                {row.outcome === "regressed" ? "⚠ " : ""}
                {suiteOutcomeLabels[row.outcome]}
              </span>
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
