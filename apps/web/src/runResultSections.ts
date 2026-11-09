/**
 * Reads the response and scenario out of a RUN_RESULT body.
 *
 * The API writes "Response\n<text>\n\nScenario\n<text>\n\nTools\n..." for an agent run and
 * "Response\n<text>\n\nURL\n..." for a URL run. The response and scenario may hold blank lines
 * of their own (a markdown brief does), so the body cannot be split on every blank line.
 * In an agent run the response runs to the last Scenario header and the scenario to the last
 * Tools header after it. In a URL run the response runs to the first URL header, since the
 * body excerpt after it is raw page text that may contain one.
 */
export function runResultSections(body: string): { response: string; scenario: string } | null {
  const responseHeader = "Response\n";
  if (!body.startsWith(responseHeader)) {
    return null;
  }
  const scenarioHeader = "\n\nScenario\n";
  const scenarioStart = body.lastIndexOf(scenarioHeader);
  if (scenarioStart === -1) {
    const urlStart = body.indexOf("\n\nURL\n");
    const responseEnd = urlStart === -1 ? body.length : urlStart;
    return { response: body.slice(responseHeader.length, responseEnd).trim(), scenario: "" };
  }
  const scenarioBody = body.slice(scenarioStart + scenarioHeader.length);
  const toolsStart = scenarioBody.lastIndexOf("\n\nTools\n");
  return {
    response: body.slice(responseHeader.length, scenarioStart).trim(),
    scenario: (toolsStart === -1 ? scenarioBody : scenarioBody.slice(0, toolsStart)).trim(),
  };
}
