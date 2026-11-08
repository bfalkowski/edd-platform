// Minimal stand-in for the Anthropic Messages API so e2e tests can make
// live-mode runs without a provider key. The API reaches it through
// ANTHROPIC_BASE_URL (see playwright.config.ts).
import { createServer } from "node:http";

const port = Number(process.env.STUB_ANTHROPIC_PORT ?? 8092);

// The proof loop e2e test fixes a missing "rollback plan": a diagnosis names
// it, a fix request gets instructions that ask for one, and a run with those
// instructions gives one.
const fixedInstructions = "Answer support questions and always include a rollback plan.";

function answerFor(body) {
  if (String(body.system ?? "").includes("You diagnose AI agent evaluation failures")) {
    return JSON.stringify({
      failure_mode: "missing rollback plan",
      severity: "high",
      review_note: "The answer never gives a rollback plan.",
    });
  }
  if (String(body.system ?? "").includes("You write precise AI agent instructions")) {
    return fixedInstructions;
  }
  if (JSON.stringify(body).includes(fixedInstructions)) {
    return "Stub live answer. Recommend a safe next action. Rollback plan: revert the deploy.";
  }
  return "Stub live answer. Recommend a safe next action.";
}

createServer((request, response) => {
  if (request.method === "POST" && request.url?.startsWith("/v1/messages")) {
    let raw = "";
    request.on("data", (chunk) => {
      raw += chunk;
    });
    request.on("end", () => {
      let body = {};
      try {
        body = JSON.parse(raw);
      } catch {
        // Answer with the default text.
      }
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(
        JSON.stringify({
          id: `msg_stub_${Date.now()}`,
          type: "message",
          role: "assistant",
          model: "stub-model",
          content: [{ type: "text", text: answerFor(body) }],
          stop_reason: "end_turn",
          stop_sequence: null,
          usage: { input_tokens: 10, output_tokens: 10 },
        }),
      );
    });
    return;
  }
  // Playwright polls this port to know the server is up.
  response.writeHead(200, { "Content-Type": "text/plain" });
  response.end("ok");
}).listen(port, "127.0.0.1");
