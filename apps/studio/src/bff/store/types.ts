import type {
  Conversation,
  ConversationTurn,
  Job,
  Observation,
  Outcome,
  Step,
} from "../../types";

export interface StoredJob extends Job {
  id: string;
  name: string;
  description: string;
  seq: number;
  created_at: string;
  updated_at: string;
}

export interface StoredStep extends Step {
  id: string;
  job_id: string;
  name: string;
  order: number;
  seq: number;
  created_at: string;
  updated_at: string;
}

export interface StoredOutcome extends Outcome {
  id: string;
  job_id: string;
  statement: string;
  importance: number | null;
  satisfaction: number | null;
  opportunity_score: number | null;
  step_id: string | null;
  seq: number;
  created_at: string;
  updated_at: string;
}

export interface StoredConversation extends Conversation {
  head_id: string | null;
}

export interface StoredTurn extends ConversationTurn {
  message_id: string | null;
  parent_id: string | null;
}

export type OutboxKind = "create" | "update" | "delete";
export type OutboxEntity = "job" | "step" | "outcome" | "evidence";
export type OutboxState =
  | "pending"
  | "sending"
  | "acknowledged"
  | "failed"
  | "conflict";

/**
 * One queued write. `id` doubles as the idempotency key so a retry replays the
 * same intent; `local_id`/`server_id` let the drain rewrite a child's parent
 * reference once the parent is acknowledged.
 */
export interface OutboxRecord {
  id: string;
  kind: OutboxKind;
  entity: OutboxEntity;
  local_id: string | null;
  server_id: string | null;
  payload: unknown;
  depends_on: string[];
  state: OutboxState;
  attempts: number;
  last_error: string | null;
  created_at: string;
  acknowledged_at: string | null;
}

/** The single-holder claim a drain takes when `navigator.locks` is missing. */
export interface DrainLease {
  holder: string;
  expires_at: number;
}

export function byCreated<T extends { created_at: string; id: string }>(
  left: T,
  right: T,
): number {
  return left.created_at.localeCompare(right.created_at) || left.id.localeCompare(right.id);
}

export interface WorkspaceSnapshot {
  version: number;
  jobs: StoredJob[];
  steps: StoredStep[];
  outcomes: StoredOutcome[];
  observations: Observation[];
  conversations: StoredConversation[];
  turns: StoredTurn[];
}

/**
 * The persistence boundary for local-first studio data.
 *
 * Implementations own ordering metadata (`seq`) so the service can mirror the
 * insertion order the Python repository guarantees without knowing whether the
 * bytes live in IndexedDB or a test-only Map.
 */
export interface LocalStore {
  readonly durable: boolean;
  nextSeq(): Promise<number>;
  listJobs(): Promise<StoredJob[]>;
  getJob(id: string): Promise<StoredJob | undefined>;
  putJob(job: StoredJob): Promise<void>;
  deleteJob(id: string): Promise<void>;
  listSteps(jobId?: string): Promise<StoredStep[]>;
  getStep(id: string): Promise<StoredStep | undefined>;
  putStep(step: StoredStep): Promise<void>;
  deleteStep(id: string): Promise<void>;
  listOutcomes(jobId?: string): Promise<StoredOutcome[]>;
  getOutcome(id: string): Promise<StoredOutcome | undefined>;
  putOutcome(outcome: StoredOutcome): Promise<void>;
  deleteOutcome(id: string): Promise<void>;
  listObservations(): Promise<Observation[]>;
  putObservation(observation: Observation): Promise<void>;
  deleteObservation(id: string): Promise<void>;
  clearObservations(): Promise<void>;
  enqueueOutbox(record: OutboxRecord): Promise<void>;
  getOutbox(id: string): Promise<OutboxRecord | undefined>;
  putOutbox(record: OutboxRecord): Promise<void>;
  deleteOutbox(id: string): Promise<void>;
  listOutbox(): Promise<OutboxRecord[]>;
  clearOutbox(): Promise<void>;
  /**
   * Claim the drain for `holder`, or return the live lease when someone else
   * holds it. A lease past `now` is stale and is replaced. The read and the
   * write happen in one transaction so two tabs cannot both claim it.
   */
  claimDrainLease(holder: string, now: number, ttlMs: number): Promise<DrainLease | null>;
  /** Extend a lease this holder owns; false when it was reclaimed or released. */
  renewDrainLease(holder: string, now: number, ttlMs: number): Promise<boolean>;
  /** Release a lease this holder owns; false when it was already gone. */
  releaseDrainLease(holder: string): Promise<boolean>;
  getDrainLease(): Promise<DrainLease | null>;
  listConversations(): Promise<StoredConversation[]>;
  getConversation(id: string): Promise<StoredConversation | undefined>;
  putConversation(conversation: StoredConversation): Promise<void>;
  setConversationHead(id: string, headId: string | null): Promise<StoredConversation>;
  listTurns(conversationId: string): Promise<ConversationTurn[]>;
  /** How much a conversation holds, without reading every turn. */
  countTurns(conversationId: string): Promise<number>;
  appendTurn(turn: Omit<StoredTurn, "id">): Promise<StoredTurn>;
  clearTurns(conversationId: string): Promise<void>;
  conversationTree(conversationId: string): Promise<{
    conversation: StoredConversation;
    messages: StoredTurn[];
    head_id: string | null;
  }>;
  /** Serialize every stored workspace record for export. */
  snapshot(): Promise<WorkspaceSnapshot>;
  /** Replace every stored workspace record with the imported snapshot. */
  restore(snapshot: WorkspaceSnapshot): Promise<void>;
  clearAll(): Promise<void>;
  close(): void;
}

export function bySeq<T extends { seq: number }>(left: T, right: T): number {
  return left.seq - right.seq;
}
