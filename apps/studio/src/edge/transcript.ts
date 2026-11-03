/**
 * The transcript of what this browser answered.
 *
 * A turn produced by the local model never reaches the server's conversation
 * tree — no key was configured, so there is no server request to carry it. The
 * browser's own memory store is therefore the only place that exchange can
 * exist. Record it here or the person loses their work when the tab closes.
 */

import type { StoredConversation, StoredTurn } from "../bff/store/types";
import type { ConversationTurn, ReplyProvenance, TurnNode } from "../types";

/** The slice of local memory this module uses — `LocalMemoryService` fits it. */
export interface EdgeTranscriptMemory {
  ensureConversation(id: string, title?: string): Promise<StoredConversation>;
  getConversation(id: string): Promise<StoredConversation | undefined>;
  appendTurn(
    conversationId: string,
    role: ConversationTurn["role"],
    content: string,
    messageId?: string | null,
    parentId?: string | null,
    provenance?: ReplyProvenance,
  ): Promise<ConversationTurn>;
  conversationTree(conversationId: string): Promise<{
    conversation: StoredConversation;
    messages: StoredTurn[];
    head_id: string | null;
  }>;
}

/** One exchange this tab streamed, with the ids the thread already uses. */
export interface EdgeExchange {
  conversationId: string;
  question: { id: string; text: string; parentId: string | null };
  answer: { id: string; text: string };
}

export async function recordEdgeTurn(
  memory: EdgeTranscriptMemory,
  exchange: EdgeExchange,
): Promise<void> {
  await memory.ensureConversation(exchange.conversationId);
  await memory.appendTurn(
    exchange.conversationId,
    "user",
    exchange.question.text,
    exchange.question.id,
    exchange.question.parentId,
  );
  await memory.appendTurn(
    exchange.conversationId,
    "assistant",
    exchange.answer.text,
    exchange.answer.id,
    exchange.question.id,
    "edge",
  );
}

/**
 * Everything this browser recorded for a conversation, oldest first — the turns
 * the server never saw, including the ones answered before a model existed.
 */
export async function readEdgeTurns(
  memory: EdgeTranscriptMemory,
  conversationId: string,
): Promise<TurnNode[]> {
  if (!(await memory.getConversation(conversationId))) {
    return [];
  }
  const { messages } = await memory.conversationTree(conversationId);
  return messages.map((turn) => ({
    id: turn.message_id ?? `turn-${turn.id}`,
    parent_id: turn.parent_id ?? null,
    role: turn.role,
    content: turn.content,
    created_at: turn.created_at,
    ...(turn.provenance ? { provenance: turn.provenance } : {}),
  }));
}
