/** Human-readable labels for eval check results, so the UI never leads with a raw check ID. */

export type CheckRef = {
  check_id: string;
  check_type?: string;
  expected?: string;
};

// One entry per check type the API evaluates (apps/api/edd_platform_api/eval_checks.py).
const typeLabels: Record<string, (expected: string) => string> = {
  output_contains: (expected) => (expected ? `Includes “${expected}”` : "Includes required text"),
  output_not_contains: (expected) => (expected ? `Avoids “${expected}”` : "Avoids forbidden text"),
  tool_called: (expected) => (expected ? `Calls ${expected}` : "Calls the required tool"),
  tool_not_called: (expected) => (expected ? `Does not call ${expected}` : "Does not call the forbidden tool"),
  rubric_judge: () => "Rubric judge",
  manual_review_required: () => "Needs manual review",
};

export const labelledCheckTypes = Object.keys(typeLabels);

/** "rollback_plan" → "Rollback plan", for check types the console does not know yet. */
function humanize(checkId: string): string {
  const words = checkId.replace(/[_-]+/g, " ").trim();
  return words ? words[0].toUpperCase() + words.slice(1) : "Unnamed check";
}

export function checkLabel(check: CheckRef, outputRequirements: string[] = []): string {
  // The wizard's generated checks point at an output requirement by position.
  const outputMatch = /^requires_output_(\d+)$/.exec(check.check_id);
  const requirement = outputMatch ? outputRequirements[Number(outputMatch[1]) - 1] : undefined;
  if (requirement) return requirement;
  const byType = check.check_type ? typeLabels[check.check_type] : undefined;
  if (byType) return byType(check.expected?.trim() ?? "");
  return humanize(check.check_id);
}
