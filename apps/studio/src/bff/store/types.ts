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
  listConversations(): Promise<StoredConversation[]>;
  getConversation(id: string): Promise<StoredConversation | undefined>;
  putConversation(conversation: StoredConversation): Promise<void>;
  setConversationHead(id: string, headId: string | null): Promise<StoredConversation>;
  listTurns(conversationId: string): Promise<ConversationTurn[]>;
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
