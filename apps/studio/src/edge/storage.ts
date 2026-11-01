/**
 * Durable state for the edge ladder, in its own IndexedDB so it never couples
 * to the canvas store. This metadata — not WebLLM's internal caches — is the
 * source of truth for "tier N is fetched": if the browser evicts the weight
 * files, the honest recovery is a re-download, and we say so.
 */

import { openDB, type DBSchema, type IDBPDatabase } from "idb";

import type { ConsentState, EdgeTierId, EdgeUsage, TierState } from "./types";
import { EDGE_TIERS } from "./ladder";

export interface EdgeStateService {
  getTierStates(): Promise<Record<EdgeTierId, TierState>>;
  setTierState(id: EdgeTierId, state: TierState): Promise<void>;
  getUsage(): Promise<EdgeUsage>;
  recordEdgeTurn(streamedSeconds: number): Promise<EdgeUsage>;
  getConsent(): Promise<ConsentState>;
  setConsent(state: ConsentState): Promise<void>;
  reset(): Promise<void>;
}

/** Session-scoped fallback for environments without IndexedDB; mirrors
 * `bff/store/openStore.ts`, which keeps the deterministic assistant alive
 * the same way. */
class MemoryEdgeState implements EdgeStateService {
  private tiers = new Map<EdgeTierId, TierState>();
  private usage: EdgeUsage = { edgeTurns: 0, streamedSeconds: 0 };
  private consent: ConsentState = "unset";

  async getTierStates(): Promise<Record<EdgeTierId, TierState>> {
    const states = {} as Record<EdgeTierId, TierState>;
    for (const tier of EDGE_TIERS) {
      states[tier.id] = this.tiers.get(tier.id) ?? { status: "empty", cachedAt: null };
    }
    return states;
  }

  async setTierState(id: EdgeTierId, state: TierState): Promise<void> {
    this.tiers.set(id, state);
  }

  async getUsage(): Promise<EdgeUsage> {
    return { ...this.usage };
  }

  async recordEdgeTurn(streamedSeconds: number): Promise<EdgeUsage> {
    this.usage = {
      edgeTurns: this.usage.edgeTurns + 1,
      streamedSeconds: this.usage.streamedSeconds + Math.max(0, streamedSeconds),
    };
    return { ...this.usage };
  }

  async getConsent(): Promise<ConsentState> {
    return this.consent;
  }

  async setConsent(state: ConsentState): Promise<void> {
    this.consent = state;
  }

  async reset(): Promise<void> {
    this.tiers.clear();
    this.usage = { edgeTurns: 0, streamedSeconds: 0 };
    this.consent = "unset";
  }
}

export async function openEdgeState(): Promise<EdgeStateService> {
  try {
    return await EdgeStateStore.open();
  } catch {
    return new MemoryEdgeState();
  }
}

const DB_NAME = "agentic-odi-edge";
const DB_VERSION = 1;

export const ENGINE_LOCK = "agentic-odi-edge-engine";

interface EdgeDb extends DBSchema {
  tiers: { key: string; value: { id: EdgeTierId; state: TierState } };
  usage: { key: string; value: { id: "usage"; edgeTurns: number; streamedSeconds: number } };
  consent: { key: string; value: { id: "consent"; state: ConsentState } };
}

const EMPTY_STATE: TierState = { status: "empty", cachedAt: null };

export class EdgeStateStore {
  private readonly db: IDBPDatabase<EdgeDb>;

  private constructor(db: IDBPDatabase<EdgeDb>) {
    this.db = db;
  }

  static async open(): Promise<EdgeStateStore> {
    const db = await openDB<EdgeDb>(DB_NAME, DB_VERSION, {
      upgrade(database) {
        database.createObjectStore("tiers", { keyPath: "id" });
        database.createObjectStore("usage", { keyPath: "id" });
        database.createObjectStore("consent", { keyPath: "id" });
      },
    });
    return new EdgeStateStore(db);
  }

  async getTierStates(): Promise<Record<EdgeTierId, TierState>> {
    const states = {} as Record<EdgeTierId, TierState>;
    for (const tier of EDGE_TIERS) {
      states[tier.id] = EMPTY_STATE;
    }
    const rows = await this.db.getAll("tiers");
    for (const row of rows) {
      if (row.id in states) {
        states[row.id] = row.state;
      }
    }
    return states;
  }

  async setTierState(id: EdgeTierId, state: TierState): Promise<void> {
    await this.db.put("tiers", { id, state });
  }

  async getUsage(): Promise<EdgeUsage> {
    const row = await this.db.get("usage", "usage");
    return {
      edgeTurns: row?.edgeTurns ?? 0,
      streamedSeconds: row?.streamedSeconds ?? 0,
    };
  }

  /** One served edge turn plus the wall-clock seconds it streamed. */
  async recordEdgeTurn(streamedSeconds: number): Promise<EdgeUsage> {
    const current = await this.getUsage();
    const next: EdgeUsage = {
      edgeTurns: current.edgeTurns + 1,
      streamedSeconds: current.streamedSeconds + Math.max(0, streamedSeconds),
    };
    await this.db.put("usage", { id: "usage", ...next });
    return next;
  }

  async getConsent(): Promise<ConsentState> {
    const row = await this.db.get("consent", "consent");
    return row?.state ?? "unset";
  }

  async setConsent(state: ConsentState): Promise<void> {
    await this.db.put("consent", { id: "consent", state });
  }

  /** Forget our metadata (e.g. after the user frees the model storage). */
  async reset(): Promise<void> {
    const tx = this.db.transaction(["tiers", "usage", "consent"], "readwrite");
    await Promise.all([
      tx.objectStore("tiers").clear(),
      tx.objectStore("usage").clear(),
      tx.objectStore("consent").clear(),
      tx.done,
    ]);
  }

  close(): void {
    this.db.close();
  }
}

export interface LockOutcome<T> {
  acquired: boolean;
  value: T | null;
}

let localLockHeld = false;

/** The slice of `LockManager` we use, typed structurally to stay off the DOM
 * lib's callback variance debates. */
interface EngineLockRequester {
  request<R>(
    name: string,
    options: { ifAvailable?: boolean },
    callback: (lock: unknown) => Promise<R>,
  ): Promise<R>;
}

/**
 * Run `task` while holding the single-engine lock so two tabs can't fight
 * over the GPU. Browsers without `navigator.locks` (and tests) fall back to a
 * same-page mutex — across tabs the second tab simply proceeds, which was the
 * status quo before the lock existed.
 */
export async function withEngineLock<T>(task: () => Promise<T>): Promise<LockOutcome<T>> {
  const locks = (navigator as unknown as { locks?: EngineLockRequester }).locks;
  if (locks?.request) {
    return locks.request<LockOutcome<T>>(ENGINE_LOCK, { ifAvailable: true }, async (lock) => {
      if (!lock) {
        return { acquired: false, value: null };
      }
      return { acquired: true, value: await task() };
    });
  }
  if (localLockHeld) {
    return { acquired: false, value: null };
  }
  localLockHeld = true;
  try {
    return { acquired: true, value: await task() };
  } finally {
    localLockHeld = false;
  }
}
