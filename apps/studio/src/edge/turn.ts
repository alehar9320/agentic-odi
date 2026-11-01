/**
 * One conversation turn, answered by the browser's own model. It speaks in the
 * exact frames the sidecar's SSE stream uses (`status`, `delta`, terminal
 * `message`), because the transcript reducer is the contract — producers are
 * interchangeable behind it. That's the same trick `bff/chat/orchestrator.ts`
 * already plays for the deterministic assistant.
 */

import type { RawSseEvent } from "../api/sse";
import type { ChatStreamRequest, StudioError } from "../types";
import { buildEdgeMessages } from "./prompt";
import type { EdgeLLMEngine } from "./types";

export interface EdgeTurnDeps {
  engine: EdgeLLMEngine;
  /** The web-llm model id of the tier that is loaded and active. */
  modelId: string;
  /** Optional compact canvas digest for grounding. */
  canvasDigest?: string;
}

function edgeFailure(error: unknown): StudioError {
  const message = error instanceof Error ? error.message : "The browser model stopped.";
  return {
    code: "edge_stream_failed",
    message: "The in-browser model couldn't finish this reply.",
    detail: message,
    suggestion: "Try again, or check the model section in Settings.",
    retryable: true,
    request_id: null,
  };
}

export async function edgeTurn(
  request: ChatStreamRequest,
  deps: EdgeTurnDeps,
  onEvent: (event: RawSseEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  // `phase: "edge"` rather than `"model"`: the transcript names the brain that
  // answered from this frame, and a reply earned its label honestly or not at all.
  onEvent({ event: "status", data: { phase: "edge" } });
  const messages = buildEdgeMessages(request, deps.canvasDigest);
  let content = "";
  try {
    for await (const delta of deps.engine.stream(messages, {}, signal)) {
      if (signal?.aborted) {
        break;
      }
      content += delta;
      onEvent({ event: "delta", data: { text: delta } });
    }
  } catch (error) {
    if (!signal?.aborted) {
      onEvent({ event: "error", data: { error: edgeFailure(error) } });
    }
    return;
  }
  // The user stopping a reply is their own doing: no terminal frame, matching
  // how the sidecar stream is treated when the abort wins the race.
  if (!signal?.aborted) {
    onEvent({ event: "message", data: { content } });
  }
}
