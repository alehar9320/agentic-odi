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
  type WorkspaceSnapshot,
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

  async deleteConversation(id: string): Promise<void> {
    await this.clearTurns(id);
    this.conversations.delete(id);
  }

  async deleteTurnTree(conversationId: string, messageId: string): Promise<void> {
    const turns = this.turns.filter((turn) => turn.conversation_id === conversationId);
    const doomed = new Set<string>([messageId]);
    let grew = true;
    while (grew) {
      grew = false;
      for (const turn of turns) {
        const id = turn.message_id ?? `turn-${turn.id}`;
        if (turn.parent_id && doomed.has(turn.parent_id) && !doomed.has(id)) {
          doomed.add(id);
          grew = true;
        }
      }
    }
    for (let index = this.turns.length - 1; index >= 0; index -= 1) {
      const turn = this.turns[index];
      if (
        turn.conversation_id === conversationId &&
        doomed.has(turn.message_id ?? `turn-${turn.id}`)
      ) {
        this.turns.splice(index, 1);
      }
    }
    const keyOf = (turn: StoredTurn) => turn.message_id ?? `turn-${turn.id}`;
    const conversation = this.conversations.get(conversationId);
    if (conversation && (conversation.head_id === null || doomed.has(conversation.head_id))) {
      // Only a branch that ended on a deleted turn moves, and then it falls
      // back to the question above rather than to another branch's last turn.
      const parent = turns.find((turn) => keyOf(turn) === messageId)?.parent_id ?? null;
      const remaining = this.turns.filter((turn) => turn.conversation_id === conversationId);
      const last = remaining[remaining.length - 1];
      this.conversations.set(conversationId, {
        ...conversation,
        head_id:
          parent && !doomed.has(parent) ? parent : last ? keyOf(last) : null,
      });
    }
  }

  async snapshot(): Promise<WorkspaceSnapshot> {
    const jobs = await this.listJobs();
    const steps = await this.listSteps();
    const outcomes = await this.listOutcomes();
    const observations = await this.listObservations();
    const conversations = await this.listConversations();
    return {
      version: 1,
      jobs,
      steps,
      outcomes,
      observations,
      conversations,
      turns: [...this.turns],
    };
  }

  async restore(snapshot: WorkspaceSnapshot): Promise<void> {
    this.jobs.clear();
    for (const job of snapshot.jobs) {
      this.jobs.set(job.id, job);
    }
    this.steps.clear();
    for (const step of snapshot.steps) {
      this.steps.set(step.id, step);
    }
    this.outcomes.clear();
    for (const outcome of snapshot.outcomes) {
      this.outcomes.set(outcome.id, outcome);
    }
    this.observations.clear();
    for (const observation of snapshot.observations) {
      this.observations.set(observation.id, observation);
    }
    this.conversations.clear();
    for (const conversation of snapshot.conversations) {
      this.conversations.set(conversation.id, conversation);
    }
    this.turns.length = 0;
    this.turns.push(...snapshot.turns);
    this.seq = Math.max(
      0,
      ...snapshot.jobs.map((job) => job.seq),
      ...snapshot.steps.map((step) => step.seq),
      ...snapshot.outcomes.map((outcome) => outcome.seq),
    );
    this.turnId = Math.max(0, ...snapshot.turns.map((turn) => turn.id ?? 0));
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
