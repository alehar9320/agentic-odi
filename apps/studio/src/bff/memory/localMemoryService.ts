import type {
  ChatPart,
  Conversation,
  ConversationTurn,
  LatestConversation,
  Observation,
  ObservationCategory,
  ObservationStatus,
} from "../../types";
import { notFound, validation } from "../errors";
import { newId, nowIso } from "../id";
import type { LocalStore, StoredConversation, StoredTurn } from "../store/types";

/** Mirrors `agentic_odi_core.models.ObservationCategory`. */
const OBSERVATION_CATEGORIES = new Set<ObservationCategory>([
  "career",
  "opportunity",
  "business",
  "customer",
  "constraint",
  "decision",
  "stakeholder",
  "evidence",
  "preference",
  "other",
]);
const OBSERVATION_STATUSES = new Set<ObservationStatus>([
  "proposed",
  "confirmed",
  "dismissed",
]);
const TURN_ROLES = new Set<ConversationTurn["role"]>([
  "user",
  "assistant",
  "system",
  "tool",
]);
/** The core caps an observation at 300 characters; the fallback must agree. */
const MAX_TEXT = 300;
const MAX_CONTEXT_TEXT = 300;
const MAX_CONTEXT_CHARS = 4000;

function cleanText(text: string): string {
  const cleaned = text.trim();
  if (!cleaned) {
    throw validation("Observation text cannot be empty.");
  }
  if (cleaned.length > MAX_TEXT) {
    throw validation(`Observation text cannot exceed ${MAX_TEXT} characters.`);
  }
  return cleaned;
}

function cleanCategory(category: string): ObservationCategory {
  if (!OBSERVATION_CATEGORIES.has(category as ObservationCategory)) {
    throw validation(`Unknown observation category: ${category}.`);
  }
  return category as ObservationCategory;
}

function cleanStatus(status: string): ObservationStatus {
  if (!OBSERVATION_STATUSES.has(status as ObservationStatus)) {
    throw validation(`Unknown observation status: ${status}.`);
  }
  return status as ObservationStatus;
}

function cleanConfidence(confidence: number): number {
  if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) {
    throw validation("Confidence must be between 0 and 1.");
  }
  return confidence;
}

function cleanData(data: Record<string, unknown> | undefined): Record<string, unknown> {
  return data ?? {};
}

export class LocalMemoryService {
  constructor(private readonly store: LocalStore) {}

  async listObservations(includeDismissed = false): Promise<Observation[]> {
    const observations = await this.store.listObservations();
    return includeDismissed
      ? observations
      : observations.filter((observation) => observation.status !== "dismissed");
  }

  async addObservation(input: {
    category?: string;
    text: string;
    data?: Record<string, unknown>;
    confidence?: number;
    confirmed?: boolean;
    conversationId?: string | null;
    sourceMessageId?: string | null;
  }): Promise<Observation> {
    const now = nowIso();
    const observation: Observation = {
      id: newId(),
      category: cleanCategory(input.category ?? "other"),
      text: cleanText(input.text),
      data: cleanData(input.data),
      status: input.confirmed ? "confirmed" : "proposed",
      confidence: cleanConfidence(input.confidence ?? 0.5),
      conversation_id: input.conversationId ?? null,
      source_message_id: input.sourceMessageId ?? null,
      created_at: now,
      updated_at: now,
    };
    await this.store.putObservation(observation);
    return observation;
  }

  async updateObservation(
    observationId: string,
    input: {
      text?: string;
      status?: string;
      category?: string;
      data?: Record<string, unknown>;
      confidence?: number;
    },
  ): Promise<Observation> {
    const existing = (await this.store.listObservations()).find(
      (observation) => observation.id === observationId,
    );
    if (!existing) {
      throw notFound("Observation", observationId);
    }
    const next: Observation = {
      ...existing,
      text: input.text === undefined ? existing.text : cleanText(input.text),
      category:
        input.category === undefined ? existing.category : cleanCategory(input.category),
      status:
        input.status === undefined ? existing.status : cleanStatus(input.status),
      data: input.data === undefined ? existing.data : cleanData(input.data),
      confidence:
        input.confidence === undefined
          ? existing.confidence
          : cleanConfidence(input.confidence),
      updated_at: nowIso(),
    };
    await this.store.putObservation(next);
    return next;
  }

  async deleteObservation(observationId: string): Promise<{ ok: boolean }> {
    const exists = (await this.store.listObservations()).some(
      (observation) => observation.id === observationId,
    );
    if (!exists) {
      throw notFound("Observation", observationId);
    }
    await this.store.deleteObservation(observationId);
    return { ok: true };
  }

  async clearMemory(): Promise<{ ok: boolean }> {
    await this.store.clearObservations();
    const conversations = await this.store.listConversations();
    for (const conversation of conversations) {
      await this.store.clearTurns(conversation.id);
    }
    return { ok: true };
  }

  async createConversation(title?: string | null): Promise<Conversation> {
    const now = nowIso();
    const conversation: StoredConversation = {
      id: newId(),
      title: title && title.trim() ? title.trim().slice(0, 200) : null,
      created_at: now,
      updated_at: now,
      head_id: null,
      archived: false,
    };
    await this.store.putConversation(conversation);
    return conversation;
  }

  async getConversation(id: string): Promise<StoredConversation | undefined> {
    return this.store.getConversation(id);
  }

  async listConversations(): Promise<StoredConversation[]> {
    return this.store.listConversations();
  }

  async setConversationHead(
    id: string,
    headId: string | null,
  ): Promise<Conversation> {
    return this.store.setConversationHead(id, headId);
  }

  /** Archiving keeps the thread readable; only a delete would lose it. */
  async setConversationArchived(id: string, archived: boolean): Promise<Conversation> {
    const conversation = await this.store.getConversation(id);
    if (!conversation) {
      throw notFound("Conversation", id);
    }
    const next: StoredConversation = { ...conversation, archived, updated_at: nowIso() };
    await this.store.putConversation(next);
    return next;
  }

  async deleteConversation(id: string): Promise<{ ok: boolean }> {
    const conversation = await this.store.getConversation(id);
    if (!conversation) {
      throw notFound("Conversation", id);
    }
    await this.store.clearTurns(id);
    await this.store.deleteConversation(id);
    return { ok: true };
  }

  async latestConversation(): Promise<LatestConversation> {
    const conversations = await this.store.listConversations();
    const conversation = conversations[0] ?? null;
    if (!conversation) {
      return { conversation: null, turns: [] };
    }
    return {
      conversation,
      turns: await this.store.listTurns(conversation.id),
    };
  }

  async conversationTree(
    conversationId: string,
  ): Promise<{ conversation: StoredConversation; messages: StoredTurn[]; head_id: string | null }> {
    return this.store.conversationTree(conversationId);
  }

  async listTurns(conversationId: string): Promise<ConversationTurn[]> {
    if (!(await this.store.getConversation(conversationId))) {
      throw notFound("Conversation", conversationId);
    }
    return this.store.listTurns(conversationId);
  }

  async appendTurn(
    conversationId: string,
    role: ConversationTurn["role"],
    content: string,
    messageId?: string | null,
    parentId?: string | null,
    parts?: ChatPart[],
  ): Promise<ConversationTurn> {
    if (!TURN_ROLES.has(role)) {
      throw validation(`Unknown turn role: ${role}.`);
    }
    const conversation = await this.store.getConversation(conversationId);
    if (!conversation) {
      throw notFound("Conversation", conversationId);
    }
    const turn = await this.store.appendTurn({
      conversation_id: conversationId,
      role,
      content,
      created_at: nowIso(),
      ...(messageId ? { id: messageId } : {}),
      parent_id: parentId ?? null,
      parts: parts ?? [],
    });
    await this.store.putConversation({
      ...conversation,
      title:
        role === "user" && content.trim() && !conversation.title
          ? content.trim().slice(0, 80)
          : conversation.title,
      head_id: turn.id,
      updated_at: nowIso(),
    });
    return turn;
  }

  /**
   * Confirmed facts only: a proposed observation is the agent's guess, and a
   * dismissed one must never come back.
   */
  async memoryContext(): Promise<string> {
    const confirmed = (await this.listObservations()).filter(
      (observation) => observation.status === "confirmed",
    );
    const lines: string[] = [];
    let length = 0;
    const add = (line: string): void => {
      if (length + line.length > MAX_CONTEXT_CHARS) {
        return;
      }
      lines.push(line);
      length += line.length + 1;
    };
    if (confirmed.length) {
      add("Confirmed context:");
      for (const observation of confirmed) {
        add(`- [${observation.category}] ${observation.text.slice(0, MAX_CONTEXT_TEXT)}`);
      }
    }
    return lines.join("\n");
  }
}
