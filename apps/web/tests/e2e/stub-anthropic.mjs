// Minimal stand-in for the Anthropic Messages API so e2e tests can make
// live-mode runs without a provider key. The API reaches it through
// ANTHROPIC_BASE_URL (see playwright.config.ts).
import { createServer } from "node:http";

const port = Number(process.env.STUB_ANTHROPIC_PORT ?? 8092);

createServer((request, response) => {
  if (request.method === "POST" && request.url?.startsWith("/v1/messages")) {
    request.resume();
    request.on("end", () => {
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(
        JSON.stringify({
          id: `msg_stub_${Date.now()}`,
          type: "message",
          role: "assistant",
          model: "stub-model",
          content: [{ type: "text", text: "Stub live answer. Recommend a safe next action." }],
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
