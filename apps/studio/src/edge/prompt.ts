/**
 * The edge model's voice. It runs alone in the browser: no MCP tools, no
 * server memory, no citations to real stored records. The prompt says so —
 * an assistant that pretends to have tools it can't call is worse than one
 * that plainly explains what it can do here.
 */

import type { ChatStreamRequest, ChatMessage } from "../types";
import type { EdgeChatMessage } from "./types";

const PERSONA = [
  "You are the Agentic ODI studio assistant, running locally in this person's browser.",
  "The work here is Jobs To Be Done research: a job statement, the steps a person",
  "takes, and the outcomes they need — described in the customer's own words.",
  "Never invent numbers, scores, customer names, or evidence. If a request needs",
  "opportunity scoring, say the studio computes it on the outcome's importance and",
  "satisfaction inputs rather than guessing. If the data needed isn't below, say",
  "what's missing instead of filling the gap.",
  "You cannot add, change, or fetch stored data: no connectors, no file imports,",
  "no writes to the canvas. When asked to do one of those, say which panel or",
  "command in the studio does it, briefly, and move on.",
  "Answer in short, plain prose. No markdown tables, no tool-call role-play.",
].join(" ");

function briefDigest(request: ChatStreamRequest): string {
  const brief = request.brief;
  if (!brief) {
    return "";
  }
  const lines = [
    `The job under study: ${brief.job_statement}`,
    `Product: ${brief.product_name} for ${brief.target_user}.`,
    `Core problem as they told it: ${brief.core_problem}`,
  ];
  if (brief.role) {
    lines.push(`The person's role: ${brief.role}.`);
  }
  if (brief.team) {
    lines.push(`Their team: ${brief.team}.`);
  }
  if (brief.evidence_at_hand?.length) {
    lines.push(`Evidence they have to work from: ${brief.evidence_at_hand.join("; ")}.`);
  }
  return lines.join("\n");
}

export function edgeSystemPrompt(request: ChatStreamRequest, canvasDigest?: string): string {
  const parts = [PERSONA];
  const brief = briefDigest(request);
  if (brief) {
    parts.push(`Context from this study:\n${brief}`);
  }
  if (canvasDigest) {
    parts.push(`Canvas as it stands right now:\n${canvasDigest}`);
  }
  return parts.join("\n\n");
}

/** Keep the transcript lean: tiny models pay hardest for long histories. */
const HISTORY_WINDOW = 12;

export function buildEdgeMessages(
  request: ChatStreamRequest,
  canvasDigest?: string,
): EdgeChatMessage[] {
  const conversation = request.messages
    .filter((message: ChatMessage) => message.role === "user" || message.role === "assistant")
    .map((message) => ({
      role: message.role as "user" | "assistant",
      content: message.content,
    }))
    .slice(-HISTORY_WINDOW);
  return [
    { role: "system", content: edgeSystemPrompt(request, canvasDigest) },
    ...conversation,
  ];
}
