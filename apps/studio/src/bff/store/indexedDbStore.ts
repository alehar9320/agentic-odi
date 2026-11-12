import { openDB, type IDBPDatabase } from "idb";

import type { Observation } from "../../types";
import { nowIso } from "../id";
import {
  DB_NAME,
  DB_VERSION,
  migrationSteps,
  type MetaValue,
  type StudioDb,
} from "./migrations";
import {
  byCreated,
  bySeq,
  type DrainLease,
  type LocalStore,
  type OutboxRecord,
  type StoredConversation,
  type StoredEvidence,
  type StoredJob,
  type StoredNotice,
  type StoredOutcome,
  type StoredStep,
  type StoredTurn,
  type WorkspaceSnapshot,
} from "./types";

export { DB_NAME };

const DRAIN_LEASE_KEY = "drain_lease";

export class IndexedDbLocalStore implements LocalStore {
  readonly durable = true;
  private readonly db: IDBPDatabase<StudioDb>;
  private reloadNeeded = false;
  private readonly reloadListeners = new Set<(needsReload: boolean) => void>();

  private constructor(db: IDBPDatabase<StudioDb>) {
    this.db = db;
    // Another tab upgrading to a newer schema asks this connection to move
    // aside; the browser also drops the connection on its own (`close`). Either
    // way this page holds a dead handle and must reload before it writes again.
    db.addEventListener("versionchange", () => this.markNeedsReload());
    db.addEventListener("close", () => this.markNeedsReload());
  }

  static async open(): Promise<IndexedDbLocalStore> {
    const db = await openDB<StudioDb>(DB_NAME, DB_VERSION, {
      upgrade(database, oldVersion, newVersion) {
        // Run the registered ladder from the version the person has up to the
        // one this build ships. A v1 database runs only `MIGRATIONS[2]`; a fresh
        // one runs 1 then 2. `migrationSteps` throws by name if a version has no
        // registered step, so a bump without a migration fails loudly here.
        for (const step of migrationSteps(oldVersion, newVersion ?? DB_VERSION)) {
          step(database);
        }
      },
    });
    return new IndexedDbLocalStore(db);
  }

  get needsReload(): boolean {
    return this.reloadNeeded;
  }

  onVersionChange(listener: (needsReload: boolean) => void): () => void {
    this.reloadListeners.add(listener);
    return () => {
      this.reloadListeners.delete(listener);
    };
  }

  private markNeedsReload(): void {
    if (this.reloadNeeded) {
      return;
    }
    this.reloadNeeded = true;
    this.db.close();
    for (const listener of this.reloadListeners) {
      listener(true);
    }
  }

  async nextSeq(): Promise<number> {
    const tx = this.db.transaction("meta", "readwrite");
    const current = (await tx.store.get("seq"))?.value;
    const next = (typeof current === "number" ? current : 0) + 1;
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

  async listEvidence(jobId?: string): Promise<StoredEvidence[]> {
    const evidence = jobId
      ? await this.db.getAllFromIndex("evidence", "by-job", jobId)
      : await this.db.getAll("evidence");
    return evidence.sort(bySeq);
  }

  async getEvidence(id: string): Promise<StoredEvidence | undefined> {
    return this.db.get("evidence", id);
  }

  async putEvidence(evidence: StoredEvidence): Promise<void> {
    await this.db.put("evidence", evidence);
  }

  async deleteEvidence(id: string): Promise<void> {
    await this.db.delete("evidence", id);
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

  async enqueueOutbox(record: OutboxRecord): Promise<void> {
    await this.db.put("outbox", record);
  }

  async getOutbox(id: string): Promise<OutboxRecord | undefined> {
    return this.db.get("outbox", id);
  }

  async putOutbox(record: OutboxRecord): Promise<void> {
    await this.db.put("outbox", record);
  }

  async deleteOutbox(id: string): Promise<void> {
    await this.db.delete("outbox", id);
  }

  async listOutbox(): Promise<OutboxRecord[]> {
    const records = await this.db.getAllFromIndex("outbox", "by-created");
    return records.sort(byCreated);
  }

  async clearOutbox(): Promise<void> {
    await this.db.clear("outbox");
  }

  async claimDrainLease(
    holder: string,
    now: number,
    ttlMs: number,
  ): Promise<DrainLease | null> {
    // One readwrite transaction over `meta` makes read-then-write atomic, so
    // two tabs cannot both see an empty lease and both claim it.
    const tx = this.db.transaction("meta", "readwrite");
    const existing = (await tx.store.get(DRAIN_LEASE_KEY))?.value;
    const lease = isLease(existing) ? existing : null;
    if (lease && lease.holder !== holder && lease.expires_at > now) {
      await tx.done;
      return lease;
    }
    await tx.store.put({
      key: DRAIN_LEASE_KEY,
      value: { holder, expires_at: now + ttlMs },
    });
    await tx.done;
    return null;
  }

  async renewDrainLease(holder: string, now: number, ttlMs: number): Promise<boolean> {
    const tx = this.db.transaction("meta", "readwrite");
    const existing = (await tx.store.get(DRAIN_LEASE_KEY))?.value;
    const lease = isLease(existing) ? existing : null;
    if (!lease || lease.holder !== holder) {
      await tx.done;
      return false;
    }
    await tx.store.put({
      key: DRAIN_LEASE_KEY,
      value: { holder, expires_at: now + ttlMs },
    });
    await tx.done;
    return true;
  }

  async releaseDrainLease(holder: string): Promise<boolean> {
    const tx = this.db.transaction("meta", "readwrite");
    const existing = (await tx.store.get(DRAIN_LEASE_KEY))?.value;
    const lease = isLease(existing) ? existing : null;
    if (!lease || lease.holder !== holder) {
      await tx.done;
      return false;
    }
    await tx.store.delete(DRAIN_LEASE_KEY);
    await tx.done;
    return true;
  }

  async getDrainLease(): Promise<DrainLease | null> {
    const existing = (await this.db.get("meta", DRAIN_LEASE_KEY))?.value;
    return isLease(existing) ? existing : null;
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

  async countTurns(conversationId: string): Promise<number> {
    return this.db.countFromIndex("turns", "by-conversation", conversationId);
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

  async snapshot(): Promise<WorkspaceSnapshot> {
    const [jobs, steps, outcomes, evidence, observations, conversations] =
      await Promise.all([
        this.listJobs(),
        this.listSteps(),
        this.listOutcomes(),
        this.listEvidence(),
        this.listObservations(),
        this.listConversations(),
      ]);
    const turnLists = await Promise.all(
      conversations.map((conversation) => this.listTurns(conversation.id)),
    );
    const turns = turnLists.flat();
    return {
      version: 1,
      jobs,
      steps,
      outcomes,
      evidence,
      observations,
      conversations,
      turns,
    };
  }

  async restore(snapshot: WorkspaceSnapshot): Promise<void> {
    await this.clearAll();
    const tx = this.db.transaction(
      [
        "jobs",
        "steps",
        "outcomes",
        "evidence",
        "observations",
        "conversations",
        "turns",
      ],
      "readwrite",
    );
    await Promise.all([
      ...snapshot.jobs.map((job) => tx.objectStore("jobs").put(job)),
      ...snapshot.steps.map((step) => tx.objectStore("steps").put(step)),
      ...snapshot.outcomes.map((outcome) => tx.objectStore("outcomes").put(outcome)),
      ...(snapshot.evidence ?? []).map((record) =>
        tx.objectStore("evidence").put(record),
      ),
      ...snapshot.observations.map((observation) =>
        tx.objectStore("observations").put(observation),
      ),
      ...snapshot.conversations.map((conversation) =>
        tx.objectStore("conversations").put(conversation),
      ),
      ...snapshot.turns.map((turn) => tx.objectStore("turns").put(turn)),
    ]);
    await tx.done;
  }

  async clearAll(): Promise<void> {
    const tx = this.db.transaction(
      [
        "meta",
        "jobs",
        "steps",
        "outcomes",
        "evidence",
        "observations",
        "outbox",
        "conversations",
        "turns",
        "notices",
      ],
      "readwrite",
    );
    await Promise.all([
      tx.objectStore("meta").clear(),
      tx.objectStore("jobs").clear(),
      tx.objectStore("steps").clear(),
      tx.objectStore("outcomes").clear(),
      tx.objectStore("evidence").clear(),
      tx.objectStore("observations").clear(),
      tx.objectStore("outbox").clear(),
      tx.objectStore("conversations").clear(),
      tx.objectStore("turns").clear(),
      tx.objectStore("notices").clear(),
    ]);
    await tx.done;
  }

  async listNotices(): Promise<StoredNotice[]> {
    const notices = await this.db.getAllFromIndex("notices", "by-at");
    return notices.sort((left, right) => right.at.localeCompare(left.at));
  }

  async getNotice(id: string): Promise<StoredNotice | undefined> {
    return this.db.get("notices", id);
  }

  async putNotice(notice: StoredNotice): Promise<void> {
    await this.db.put("notices", notice);
  }

  async deleteNotice(id: string): Promise<void> {
    await this.db.delete("notices", id);
  }

  async markAllRead(): Promise<void> {
    const notices = await this.listNotices();
    const tx = this.db.transaction("notices", "readwrite");
    for (const notice of notices) {
      if (!notice.read) {
        await tx.objectStore("notices").put({ ...notice, read: true });
      }
    }
    await tx.done;
  }

  close(): void {
    this.db.close();
  }
}

function isLease(value: MetaValue | undefined): value is DrainLease {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as DrainLease).holder === "string" &&
    typeof (value as DrainLease).expires_at === "number"
  );
}
