import { newId, nowIso } from "./id";
import type { LocalStore, OutboxRecord } from "./store/types";

/**
 * The outbox is shared by every tab in the origin, so two tabs that both drain
 * it would send each record twice. A drain takes a mutual-exclusion guard for
 * the duration of the run: `navigator.locks` where the browser has it, and a
 * lease row in `meta` where it does not (Safari has gaps). Only one of the two
 * is used per run — never both.
 */

/** Lock name shared by every tab in the origin. */
export const DRAIN_LOCK_NAME = "outbox-drain";
/** How long a lease is valid before another drain may reclaim it. */
export const DEFAULT_LEASE_TTL_MS = 15_000;

export type DrainSend = (record: OutboxRecord) => Promise<void> | void;

export interface DrainOptions {
  store: LocalStore;
  send: DrainSend;
  /**
   * Identifies this drain to the lease. Defaults to a fresh id per run, so two
   * runs — in one tab or across tabs — never share a holder.
   */
  holder?: string;
  leaseTtlMs?: number;
  now?: () => number;
  /**
   * The lock manager to use. `undefined` reads `navigator.locks`; `null` forces
   * the lease path, which is how the tests exercise it.
   */
  locks?: LockManager | null;
}

export type DrainSkipReason = "locked" | "lease-held";

export interface DrainOutcome {
  /** False when another tab already held the guard. */
  ran: boolean;
  /** How many records this run sent. */
  sent: number;
  reason?: DrainSkipReason;
}

/**
 * Drain the outbox at most once across the tabs that share it. Returns without
 * sending when another tab holds the guard; the records stay `pending` for that
 * tab, or for this one on the next trigger.
 */
export async function drainOutbox(options: DrainOptions): Promise<DrainOutcome> {
  const locks = resolveLocks(options.locks);
  return locks ? runWithLock(locks, options) : runWithLease(options);
}

async function runWithLock(
  locks: LockManager,
  options: DrainOptions,
): Promise<DrainOutcome> {
  let outcome: DrainOutcome = { ran: false, sent: 0, reason: "locked" };
  let entered = false;
  try {
    await locks.request(DRAIN_LOCK_NAME, { ifAvailable: true }, async (lock) => {
      entered = true;
      if (!lock) {
        return;
      }
      outcome = { ran: true, sent: await drainPending(options) };
    });
  } catch (error) {
    // A context that exposes `navigator.locks` but refuses to grant one is the
    // Safari gap the lease exists for. Fall back only when the callback never
    // ran, so a drain that did hold the lock is never re-run.
    if (!entered) {
      return runWithLease(options);
    }
    throw error;
  }
  return outcome;
}

async function runWithLease(options: DrainOptions): Promise<DrainOutcome> {
  const now = options.now ?? Date.now;
  const ttl = options.leaseTtlMs ?? DEFAULT_LEASE_TTL_MS;
  const holder = options.holder ?? newId();

  const held = await options.store.claimDrainLease(holder, now(), ttl);
  if (held) {
    return { ran: false, sent: 0, reason: "lease-held" };
  }

  // Renew while the drain runs so a slow drain keeps its claim, and so a crash
  // frees the queue no later than one TTL after the last renewal.
  const timer = setInterval(() => {
    void options.store.renewDrainLease(holder, now(), ttl).catch(() => undefined);
  }, Math.max(1, Math.floor(ttl / 2)));

  try {
    return { ran: true, sent: await drainPending(options) };
  } finally {
    clearInterval(timer);
    await options.store.releaseDrainLease(holder).catch(() => undefined);
  }
}

async function drainPending(options: DrainOptions): Promise<number> {
  const records = await options.store.listOutbox();
  let sent = 0;
  for (const record of records) {
    if (record.state !== "pending") {
      continue;
    }
    await options.send(record);
    await options.store.putOutbox({
      ...record,
      state: "acknowledged",
      attempts: record.attempts + 1,
      acknowledged_at: nowIso(),
    });
    sent += 1;
  }
  return sent;
}

function resolveLocks(explicit?: LockManager | null): LockManager | null {
  if (explicit !== undefined) {
    return explicit;
  }
  const candidate = (globalThis.navigator as Navigator | undefined)?.locks;
  return candidate && typeof candidate.request === "function" ? candidate : null;
}
