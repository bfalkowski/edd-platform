import type { TestShape } from "./types";

export const defaultScenarioInput = "What's the weather in Boston today?";
export const defaultConversationInput = `Customer: My deployment failed after the release.
Agent: What error are you seeing?
Customer: The rollout says image pull backoff.`;
export const defaultTraceReplayInput =
  "Paste the prior trace spans, messages, or evidence that should set up the next agent response.";
export const defaultRubricText =
  "A good answer should directly answer the user request, avoid unsupported claims, and ask for missing details only when they are required.";
export const defaultConversationRubricText =
  "A good observer output should review the latest customer turn in context, identify that sentiment or escalation risk is worsening, mention the image pull backoff blocker, avoid claiming the issue is fixed, and produce concise downstream-safe observer notes.";
export const defaultTraceReplayRubricText =
  "A good answer should use the replayed evidence, preserve important context from the trace, and avoid inventing facts not present in the replay.";
export const testShapeLabels: Record<TestShape, string> = {
  single_turn: "Single turn",
  conversation: "Conversation",
  trace_replay: "Trace replay",
};
export const testShapeInputLabels: Record<TestShape, string> = {
  single_turn: "Prompt",
  conversation: "Conversation",
  trace_replay: "Replay context",
};
export const testShapeInputHelp: Record<TestShape, string> = {
  single_turn: "Test one user request in isolation.",
  conversation: "Include prior messages plus the next user turn.",
  trace_replay: "Start from selected prior spans, messages, or evidence.",
};
export function defaultInputForTestShape(shape: TestShape): string {
  if (shape === "conversation") {
    return defaultConversationInput;
  }
  if (shape === "trace_replay") {
    return defaultTraceReplayInput;
  }
  return defaultScenarioInput;
}
export function conversationTurnsFromText(input: string): Array<{ speaker: string; text: string }> {
  const matches = Array.from(input.matchAll(/\b(Customer|Agent):\s*/g));
  if (matches.length === 0) {
    return [];
  }
  return matches
    .map((match, index) => {
      const start = (match.index ?? 0) + match[0].length;
      const end = matches[index + 1]?.index ?? input.length;
      return {
        speaker: match[1],
        text: input.slice(start, end).trim(),
      };
    })
    .filter((turn) => turn.text.length > 0);
}
export function renderScenarioInput(input: string | undefined) {
  const text = input?.trim();
  if (!text) {
    return null;
  }
  const turns = conversationTurnsFromText(text);
  if (turns.length < 2) {
    return <p className="scenario-test-text">{text}</p>;
  }
  return (
    <div className="scenario-turns">
      {turns.map((turn, index) => (
        <p key={`${turn.speaker}-${index}`} className="scenario-turn">
          <strong>{turn.speaker}:</strong> {turn.text}
        </p>
      ))}
    </div>
  );
}
export function defaultRubricForTestShape(shape: TestShape): string {
  if (shape === "conversation") {
    return defaultConversationRubricText;
  }
  if (shape === "trace_replay") {
    return defaultTraceReplayRubricText;
  }
  return defaultRubricText;
}
export function isDefaultTestInput(input: string): boolean {
  return [defaultScenarioInput, defaultConversationInput, defaultTraceReplayInput].includes(input);
}
export function isDefaultRubricText(rubric: string): boolean {
  return [defaultRubricText, defaultConversationRubricText, defaultTraceReplayRubricText].includes(rubric);
}
export function setupContextFromTestShape(shape: TestShape): string {
  return `test_shape:${shape}`;
}
export function testShapeFromSetupContext(setupContext?: string): TestShape {
  if (setupContext?.includes("test_shape:conversation")) {
    return "conversation";
  }
  if (setupContext?.includes("test_shape:trace_replay")) {
    return "trace_replay";
  }
  return "single_turn";
}
export const defaultToolInputSchema = `{
  "type": "object",
  "properties": {
    "ticket_id": {
      "type": "string",
      "description": "External ticket identifier."
    },
    "customer_since": {
      "type": "string",
      "format": "date",
      "description": "ISO date, for example 2026-06-04."
    },
    "retry_count": {
      "type": "integer",
      "minimum": 0
    },
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "priority": {
      "type": "string",
      "enum": ["low", "medium", "high"]
    },
    "include_history": {
      "type": "boolean"
    }
  },
  "required": ["ticket_id"]
}`;
export const defaultToolOutputSchema = `{
  "type": "object",
  "properties": {
    "summary": {
      "type": "string"
    },
    "status": {
      "type": "string",
      "enum": ["open", "blocked", "resolved"]
    },
    "age_days": {
      "type": "integer"
    },
    "last_updated": {
      "type": "string",
      "format": "date-time"
    },
    "recommended_actions": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": ["summary", "status"]
}`;
