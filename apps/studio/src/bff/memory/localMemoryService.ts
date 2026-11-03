import type {
  Conversation,
  ConversationSummary,
  ConversationTurn,
  LatestConversation,
  Observation,
  ObservationKind,
  ObservationStatus,
} from "../../types";
import { notFound, validation } from "../errors";
import { newId, nowIso } from "../id";
import type { LocalStore, StoredConversation, StoredTurn } from "../store/types";

const OBSERVATION_KINDS = new Set<ObservationKind>([
  "career",
  "opportunity",
  "business",
  "stakeholder",
  "constraint",
  "evidence",
  "preference",
]);
const OBSERVATION_STATUSES = new Set<ObservationStatus>([
  "suggested",
  "confirmed",
  "dismissed",
]);
const TURN_ROLES = new Set<ConversationTurn["role"]>([
  "user",
  "assistant",
  "system",
  "tool",
]);
const MAX_TEXT = 2000;
const MAX_CONTEXT_TEXT = 500;
const MAX_CONTEXT_CHARS = 4000;
const MAX_SUGGESTED_IN_CONTEXT = 10;

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

function cleanKind(kind: string): ObservationKind {
  if (!OBSERVATION_KINDS.has(kind as ObservationKind)) {
    throw validation(`Unknown observation kind: ${kind}.`);
  }
  return kind as ObservationKind;
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
    kind: string;
    text: string;
    data?: Record<string, unknown>;
    confidence?: number;
    confirmed?: boolean;
  }): Promise<Observation> {
    const now = nowIso();
    const observation: Observation = {
      id: newId(),
      kind: cleanKind(input.kind),
      text: cleanText(input.text),
      data: cleanData(input.data),
      status: input.confirmed ? "confirmed" : "suggested",
      confidence: cleanConfidence(input.confidence ?? 0.5),
      source_turn: null,
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

  async createConversation(title = ""): Promise<Conversation> {
    const now = nowIso();
    const conversation: StoredConversation = {
      id: newId(),
      title: title.trim(),
      created_at: now,
      updated_at: now,
      head_id: null,
    };
    await this.store.putConversation(conversation);
    return conversation;
  }

  async getConversation(id: string): Promise<StoredConversation | undefined> {
    return this.store.getConversation(id);
  }

  /** The history list: every thread, most recent touch first, with its size. */
  async listConversations(): Promise<ConversationSummary[]> {
    const conversations = await this.store.listConversations();
    return Promise.all(
      conversations.map(async (conversation) => ({
        ...conversation,
        turn_count: await this.store.countTurns(conversation.id),
      })),
    );
  }

  async setConversationHead(
    id: string,
    headId: string | null,
  ): Promise<Conversation> {
    return this.store.setConversationHead(id, headId);
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
      message_id: messageId ?? null,
      parent_id: parentId ?? null,
    });
    const now = nowIso();
    await this.store.putConversation({
      ...conversation,
      title:
        role === "user" && content.trim() && !conversation.title
          ? content.trim().slice(0, 80)
          : conversation.title,
      head_id: messageId ?? conversation.head_id,
      updated_at: now,
    });
    return turn;
  }

  async memoryContext(): Promise<string> {
    const observations = (await this.listObservations()).filter(
      (observation) => observation.status === "confirmed",
    );
    const suggested = (await this.listObservations()).filter(
      (observation) => observation.status === "suggested",
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
    if (observations.length) {
      add("Confirmed context:");
      for (const observation of observations) {
        add(`- [${observation.kind}] ${observation.text.slice(0, MAX_CONTEXT_TEXT)}`);
      }
    }
    if (suggested.length) {
      add("Suggested context (not yet confirmed):");
      for (const observation of suggested.slice(0, MAX_SUGGESTED_IN_CONTEXT)) {
        add(`- [${observation.kind}] ${observation.text.slice(0, MAX_CONTEXT_TEXT)}`);
      }
    }
    return lines.join("\n");
  }
}
