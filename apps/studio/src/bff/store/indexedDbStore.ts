import { openDB, type DBSchema, type IDBPDatabase } from "idb";

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

const DB_NAME = "agentic-odi-studio";
const DB_VERSION = 1;

interface StudioDb extends DBSchema {
  meta: { key: string; value: { key: string; value: number } };
  jobs: { key: string; value: StoredJob; indexes: { "by-seq": number } };
  steps: {
    key: string;
    value: StoredStep;
    indexes: { "by-job": string; "by-seq": number };
  };
  outcomes: {
    key: string;
    value: StoredOutcome;
    indexes: { "by-job": string; "by-seq": number };
  };
  observations: {
    key: string;
    value: Observation;
    indexes: { "by-created": string };
  };
  conversations: {
    key: string;
    value: StoredConversation;
    indexes: { "by-updated": string };
  };
  turns: {
    key: number;
    value: StoredTurn;
    indexes: { "by-conversation": string };
  };
}

export class IndexedDbLocalStore implements LocalStore {
  readonly durable = true;
  private readonly db: IDBPDatabase<StudioDb>;

  private constructor(db: IDBPDatabase<StudioDb>) {
    this.db = db;
  }

  static async open(): Promise<IndexedDbLocalStore> {
    const db = await openDB<StudioDb>(DB_NAME, DB_VERSION, {
      upgrade(database) {
        database.createObjectStore("meta", { keyPath: "key" });
        const jobs = database.createObjectStore("jobs", { keyPath: "id" });
        jobs.createIndex("by-seq", "seq");
        const steps = database.createObjectStore("steps", { keyPath: "id" });
        steps.createIndex("by-job", "job_id");
        steps.createIndex("by-seq", "seq");
        const outcomes = database.createObjectStore("outcomes", { keyPath: "id" });
        outcomes.createIndex("by-job", "job_id");
        outcomes.createIndex("by-seq", "seq");
        const observations = database.createObjectStore("observations", {
          keyPath: "id",
        });
        observations.createIndex("by-created", "created_at");
        const conversations = database.createObjectStore("conversations", {
          keyPath: "id",
        });
        conversations.createIndex("by-updated", "updated_at");
        const turns = database.createObjectStore("turns", {
          keyPath: "id",
          autoIncrement: true,
        });
        turns.createIndex("by-conversation", "conversation_id");
      },
    });
    return new IndexedDbLocalStore(db);
  }

  async nextSeq(): Promise<number> {
    const tx = this.db.transaction("meta", "readwrite");
    const current = (await tx.store.get("seq"))?.value ?? 0;
    const next = current + 1;
    await tx.store.put({ key: "seq", value: next });
    await tx.done;
    return next;
  }

  async listJobs(): Promise<StoredJob[]> {
    const jobs = await this.db.getAll("jobs");
    return jobs.sort(bySeq);
  }

  async getJob(id: string): Promise<StoredJob | undefined> {
    return this.db.get("jobs", id);
  }

  async putJob(job: StoredJob): Promise<void> {
    await this.db.put("jobs", job);
  }

  async deleteJob(id: string): Promise<void> {
    await this.db.delete("jobs", id);
  }

  async listSteps(jobId?: string): Promise<StoredStep[]> {
    const steps = jobId
      ? await this.db.getAllFromIndex("steps", "by-job", jobId)
      : await this.db.getAll("steps");
    return steps.sort((left, right) => left.order - right.order || bySeq(left, right));
  }

  async getStep(id: string): Promise<StoredStep | undefined> {
    return this.db.get("steps", id);
  }

  async putStep(step: StoredStep): Promise<void> {
    await this.db.put("steps", step);
  }

  async deleteStep(id: string): Promise<void> {
    await this.db.delete("steps", id);
  }

  async listOutcomes(jobId?: string): Promise<StoredOutcome[]> {
    const outcomes = jobId
      ? await this.db.getAllFromIndex("outcomes", "by-job", jobId)
      : await this.db.getAll("outcomes");
    return outcomes.sort(bySeq);
  }

  async getOutcome(id: string): Promise<StoredOutcome | undefined> {
    return this.db.get("outcomes", id);
  }

  async putOutcome(outcome: StoredOutcome): Promise<void> {
    await this.db.put("outcomes", outcome);
  }

  async deleteOutcome(id: string): Promise<void> {
    await this.db.delete("outcomes", id);
  }

  async listObservations(): Promise<Observation[]> {
    const observations = await this.db.getAll("observations");
    return observations.sort((left, right) =>
      left.created_at.localeCompare(right.created_at),
    );
  }

  async putObservation(observation: Observation): Promise<void> {
    await this.db.put("observations", observation);
  }

  async deleteObservation(id: string): Promise<void> {
    await this.db.delete("observations", id);
  }

  async clearObservations(): Promise<void> {
    await this.db.clear("observations");
  }

  async listConversations(): Promise<StoredConversation[]> {
    const conversations = await this.db.getAll("conversations");
    return conversations.sort((left, right) =>
      right.updated_at.localeCompare(left.updated_at),
    );
  }

  async getConversation(id: string): Promise<StoredConversation | undefined> {
    return this.db.get("conversations", id);
  }

  async putConversation(conversation: StoredConversation): Promise<void> {
    await this.db.put("conversations", conversation);
  }

  async setConversationHead(
    id: string,
    headId: string | null,
  ): Promise<StoredConversation> {
    const conversation = await this.db.get("conversations", id);
    if (!conversation) {
      throw new Error(`Conversation ${id} not found`);
    }
    const now = nowIso();
    const next: StoredConversation = {
      ...conversation,
      head_id: headId,
      updated_at: now,
    };
    await this.db.put("conversations", next);
    return next;
  }

  async listTurns(conversationId: string): Promise<StoredTurn[]> {
    return this.db.getAllFromIndex("turns", "by-conversation", conversationId);
  }

  async appendTurn(turn: Omit<StoredTurn, "id">): Promise<StoredTurn> {
    const id = await this.db.add("turns", turn as StoredTurn);
    return { ...turn, id: Number(id) };
  }

  async conversationTree(conversationId: string): Promise<{
    conversation: StoredConversation;
    messages: StoredTurn[];
    head_id: string | null;
  }> {
    const conversation = await this.getConversation(conversationId);
    if (!conversation) {
      throw new Error(`Conversation ${conversationId} not found`);
    }
    const turns = await this.listTurns(conversationId);
    let previous: string | null = null;
    const messages = turns.map((turn) => {
      if (!turn.message_id) {
        turn = { ...turn, message_id: `turn-${turn.id}`, parent_id: previous };
      }
      previous = turn.message_id;
      return turn;
    });
    return {
      conversation,
      messages,
      head_id:
        conversation.head_id ?? messages[messages.length - 1]?.message_id ?? null,
    };
  }

  async clearTurns(conversationId: string): Promise<void> {
    const tx = this.db.transaction("turns", "readwrite");
    const keys = await tx.store.index("by-conversation").getAllKeys(conversationId);
    await Promise.all(keys.map((key) => tx.store.delete(key)));
    await tx.done;
  }

  async clearAll(): Promise<void> {
    const tx = this.db.transaction(
      [
        "meta",
        "jobs",
        "steps",
        "outcomes",
        "observations",
        "conversations",
        "turns",
      ],
      "readwrite",
    );
    await Promise.all([
      tx.objectStore("meta").clear(),
      tx.objectStore("jobs").clear(),
      tx.objectStore("steps").clear(),
      tx.objectStore("outcomes").clear(),
      tx.objectStore("observations").clear(),
      tx.objectStore("conversations").clear(),
      tx.objectStore("turns").clear(),
    ]);
    await tx.done;
  }

  close(): void {
    this.db.close();
  }
}
