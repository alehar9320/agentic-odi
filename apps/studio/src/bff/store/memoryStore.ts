import type { Observation } from "../../types";
import { nowIso } from "../id";
import {
  bySeq,
  type LocalStore,
  type StoredConversation,
  type StoredJob,
  type StoredOutcome,
  type StoredStep,
  type StoredTurn,
} from "./types";

/** Session-only fallback for browsers that deny IndexedDB. */
export class MemoryLocalStore implements LocalStore {
  readonly durable = false;
  private seq = 0;
  private turnId = 0;
  private readonly jobs = new Map<string, StoredJob>();
  private readonly steps = new Map<string, StoredStep>();
  private readonly outcomes = new Map<string, StoredOutcome>();
  private readonly observations = new Map<string, Observation>();
  private readonly conversations = new Map<string, StoredConversation>();
  private readonly turns: StoredTurn[] = [];

  async nextSeq(): Promise<number> {
    this.seq += 1;
    return this.seq;
  }

  async listJobs(): Promise<StoredJob[]> {
    return [...this.jobs.values()].sort(bySeq);
  }

  async getJob(id: string): Promise<StoredJob | undefined> {
    return this.jobs.get(id);
  }

  async putJob(job: StoredJob): Promise<void> {
    this.jobs.set(job.id, job);
  }

  async deleteJob(id: string): Promise<void> {
    this.jobs.delete(id);
  }

  async listSteps(jobId?: string): Promise<StoredStep[]> {
    return [...this.steps.values()]
      .filter((step) => !jobId || step.job_id === jobId)
      .sort((left, right) => left.order - right.order || bySeq(left, right));
  }

  async getStep(id: string): Promise<StoredStep | undefined> {
    return this.steps.get(id);
  }

  async putStep(step: StoredStep): Promise<void> {
    this.steps.set(step.id, step);
  }

  async deleteStep(id: string): Promise<void> {
    this.steps.delete(id);
  }

  async listOutcomes(jobId?: string): Promise<StoredOutcome[]> {
    return [...this.outcomes.values()]
      .filter((outcome) => !jobId || outcome.job_id === jobId)
      .sort(bySeq);
  }

  async getOutcome(id: string): Promise<StoredOutcome | undefined> {
    return this.outcomes.get(id);
  }

  async putOutcome(outcome: StoredOutcome): Promise<void> {
    this.outcomes.set(outcome.id, outcome);
  }

  async deleteOutcome(id: string): Promise<void> {
    this.outcomes.delete(id);
  }

  async listObservations(): Promise<Observation[]> {
    return [...this.observations.values()].sort((left, right) =>
      left.created_at.localeCompare(right.created_at),
    );
  }

  async putObservation(observation: Observation): Promise<void> {
    this.observations.set(observation.id, observation);
  }

  async deleteObservation(id: string): Promise<void> {
    this.observations.delete(id);
  }

  async clearObservations(): Promise<void> {
    this.observations.clear();
  }

  async listConversations(): Promise<StoredConversation[]> {
    return [...this.conversations.values()].sort((left, right) =>
      right.updated_at.localeCompare(left.updated_at),
    );
  }

  async getConversation(id: string): Promise<StoredConversation | undefined> {
    return this.conversations.get(id);
  }

  async putConversation(conversation: StoredConversation): Promise<void> {
    this.conversations.set(conversation.id, conversation);
  }

  async setConversationHead(
    id: string,
    headId: string | null,
  ): Promise<StoredConversation> {
    const conversation = this.conversations.get(id);
    if (!conversation) {
      throw new Error(`Conversation ${id} not found`);
    }
    const now = nowIso();
    const next: StoredConversation = {
      ...conversation,
      head_id: headId,
      updated_at: now,
    };
    this.conversations.set(id, next);
    return next;
  }

  async listTurns(conversationId: string): Promise<StoredTurn[]> {
    return this.turns
      .filter((turn) => turn.conversation_id === conversationId)
      .sort((left, right) => left.id - right.id);
  }

  async appendTurn(turn: Omit<StoredTurn, "id">): Promise<StoredTurn> {
    this.turnId += 1;
    const stored = { ...turn, id: this.turnId };
    this.turns.push(stored);
    return stored;
  }

  async conversationTree(conversationId: string): Promise<{
    conversation: StoredConversation;
    messages: StoredTurn[];
    head_id: string | null;
  }> {
    const conversation = this.conversations.get(conversationId);
    if (!conversation) {
      throw new Error(`Conversation ${conversationId} not found`);
    }
    let previous: string | null = null;
    const messages = (await this.listTurns(conversationId)).map((turn) => {
      if (!turn.message_id) {
        turn = { ...turn, message_id: `turn-${turn.id}`, parent_id: previous };
      }
      previous = turn.message_id;
      return turn;
    });
    return {
      conversation,
      messages,
      head_id: conversation.head_id ?? messages[messages.length - 1]?.message_id ?? null,
    };
  }

  async clearTurns(conversationId: string): Promise<void> {
    for (let index = this.turns.length - 1; index >= 0; index -= 1) {
      if (this.turns[index].conversation_id === conversationId) {
        this.turns.splice(index, 1);
      }
    }
  }

  async clearAll(): Promise<void> {
    this.jobs.clear();
    this.steps.clear();
    this.outcomes.clear();
    this.observations.clear();
    this.conversations.clear();
    this.turns.length = 0;
    this.seq = 0;
    this.turnId = 0;
  }

  close(): void {
    /* nothing to release */
  }
}
