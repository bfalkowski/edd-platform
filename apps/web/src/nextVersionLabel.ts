/** The label of the version a confirmed fix creates: the base version's number plus one. */
export function nextVersionLabel(baseLabel: string): string {
  return "v" + (Number(baseLabel.match(/\d+/)?.[0] ?? 0) + 1);
}
