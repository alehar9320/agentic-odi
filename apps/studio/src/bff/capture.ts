import { newId, nowIso } from "./id";
import { drainOutbox } from "./outbox";
import type { LocalStore, OutboxRecord, StoredOutcome } from "./store/types";

/**
 * The offline capture outbox.
 *
 * A capture made while the sidecar is unreachable is written to the local store
 * and enqueued here instead of being lost. The queue is the same outbox the
 * canvas writes use (`outbox.ts`); a capture is one `outcome` create record, so
 * there is one record of the intent and one drain, not a second store.
 *
 * The idempotency key is minted once, here, at capture time — never at replay —
 * so a capture that is retried after a lost response carries the same key and
 * the sidecar stores exactly one record.
 */

/** What the person typed, before a job or an id is attached. */
export interface CaptureIntent {
  job_id: string;
  statement: string;
  importance: number | null;
  satisfaction: number | null;
  step_id?: string | null;
}

/** One capture waiting to sync, with the count the badge reads. */
export interface QueuedCapture {
  id: string;
  record: OutboxRecord;
}

function isOutcomeCreate(record: OutboxRecord): boolean {
  return record.entity === "outcome" && record.kind === "create";
}

/**
 * Queue one capture. `id` doubles as the idempotency key and is generated here,
 * at capture time, so two replays of the same intent share it.
 */
export async function queueCapture(
  store: LocalStore,
  intent: CaptureIntent,
): Promise<OutboxRecord> {
  const id = newId();
  const record: OutboxRecord = {
    id,
    kind: "create",
    entity: "outcome",
    local_id: id,
    server_id: null,
    payload: {
      job_id: intent.job_id,
      statement: intent.statement,
      importance: intent.importance,
      satisfaction: intent.satisfaction,
      step_id: intent.step_id ?? null,
    },
    depends_on: [],
    state: "pending",
    attempts: 0,
    last_error: null,
    created_at: nowIso(),
    acknowledged_at: null,
  };
  await store.enqueueOutbox(record);
  return record;
}

/** Every capture still waiting to sync, oldest first. */
export async function listQueuedCaptures(store: LocalStore): Promise<OutboxRecord[]> {
  const records = await store.listOutbox();
  return records.filter((record) => isOutcomeCreate(record) && record.state === "pending");
}

/**
 * Every capture the sidecar refused. They are kept, not deleted: a refusal is
 * shown to the person rather than silently dropped, and the record is there if
 * the write is ever retried by hand.
 */
export async function listFailedCaptures(store: LocalStore): Promise<OutboxRecord[]> {
  const records = await store.listOutbox();
  return records.filter((record) => isOutcomeCreate(record) && record.state === "failed");
}

/**
 * Mark a capture the sidecar refused as failed, so the queue stops retrying a
 * request that will not succeed and the UI can say so. A record already moved
 * on is left alone.
 */
export async function failCapture(
  store: LocalStore,
  id: string,
  message: string,
): Promise<void> {
  const record = await store.getOutbox(id);
  if (!record || record.state !== "pending") {
    return;
  }
  await store.putOutbox({
    ...record,
    state: "failed",
    attempts: record.attempts + 1,
    last_error: message,
  });
}

/** How many captures are waiting, which is what the badge shows. */
export async function countQueuedCaptures(store: LocalStore): Promise<number> {
  return (await listQueuedCaptures(store)).length;
}

/** A queued capture's outcome, so the canvas can show it before it syncs. */
export function outcomeFromCapture(record: OutboxRecord): StoredOutcome {
  const payload = record.payload as Partial<CaptureIntent>;
  const importance = payload.importance ?? null;
  const satisfaction = payload.satisfaction ?? null;
  return {
    id: record.id,
    job_id: payload.job_id ?? "",
    step_id: payload.step_id ?? null,
    statement: payload.statement ?? "",
    importance,
    satisfaction,
    opportunity_score:
      importance !== null && satisfaction !== null
        ? importance + Math.max(importance - satisfaction, 0)
        : null,
    seq: 0,
    created_at: record.created_at,
    updated_at: record.created_at,
  };
}

export type CaptureSend = (record: OutboxRecord) => Promise<void> | void;

export interface ReplayOptions {
  store: LocalStore;
  send: CaptureSend;
  holder?: string;
  leaseTtlMs?: number;
  now?: () => number;
  locks?: LockManager | null;
}

/**
 * Replay the queued captures, at most once across the tabs that share the
 * queue. The mutual-exclusion guard is `drainOutbox`'s, narrowed to capture
 * records so a replay never touches an edit queued by another path.
 */
export async function replayCaptures(options: ReplayOptions): Promise<number> {
  const outcome = await drainOutbox({
    store: options.store,
    send: options.send,
    holder: options.holder,
    leaseTtlMs: options.leaseTtlMs,
    now: options.now,
    locks: options.locks,
    select: isOutcomeCreate,
  });
  return outcome.sent;
}
