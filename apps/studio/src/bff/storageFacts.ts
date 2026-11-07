import { DB_NAME, IndexedDbLocalStore } from "./store/indexedDbStore";
import type { LocalStore } from "./store/types";

/**
 * What the browser can be asked about this browser's storage, and nothing more.
 *
 * `lastWrite` is derived from the timestamps the records already carry — the `meta` store holds
 * only a sequence counter, so no write time is stored anywhere to read. `bytes` is the origin's
 * usage as the browser measures it, not this database's share of it, which is why an absent
 * `estimate()` is reported as `unknown` rather than as zero. No value is ever read out of
 * storage here: `studio.settings` holds an API key, and a size costs nothing to show.
 */

export type ByteTotal = number | "unknown";

export interface StorageFacts {
  engine: "indexeddb" | "memory";
  database: string | null;
  bytes: ByteTotal;
  records: number;
  lastWrite: string | null;
  persistent: boolean | "unknown";
}

export interface KeyFacts {
  key: string;
  bytes: number;
}

/** Every key the app writes, read from the writers rather than from memory. */
export const APP_STORAGE_KEYS: readonly string[] = [
  "agentic-odi.changelog.read",
  "agentic-odi.evidence-order",
  "studio.apiKey",
  "studio.brief",
  "studio.conversationId",
  "studio.canvas",
  "studio.displayName",
  "studio.guidance",
  "studio.intro",
  "studio.onboarding",
  "studio.session",
  "studio.settings",
  "studio.setupDraft",
  "studio.setupStep",
  "studio.sidecarNoticeDismissed",
  "studio.install.dismissed",
  "studio.theses",
  "studio.update.autoCheck",
  "studio.update.skippedVersion",
];

/** Keys the app writes under a namespace it does not enumerate in advance. */
export const APP_STORAGE_PREFIXES: readonly string[] = ["studio.flags."];

function isAppKey(key: string): boolean {
  return (
    APP_STORAGE_KEYS.includes(key) ||
    APP_STORAGE_PREFIXES.some((prefix) => key.startsWith(prefix))
  );
}

function newest(stamps: string[]): string | null {
  let winner: string | null = null;
  let winnerTime = Number.NaN;
  for (const stamp of stamps) {
    const time = Date.parse(stamp);
    if (Number.isNaN(time)) {
      continue;
    }
    if (winner === null || time > winnerTime) {
      winner = stamp;
      winnerTime = time;
    }
  }
  return winner;
}

async function estimateBytes(): Promise<ByteTotal> {
  const storage = globalThis.navigator?.storage;
  if (typeof storage?.estimate !== "function") {
    return "unknown";
  }
  try {
    const usage = (await storage.estimate()).usage;
    return typeof usage === "number" ? usage : "unknown";
  } catch {
    return "unknown";
  }
}

async function isPersistent(store: LocalStore): Promise<boolean | "unknown"> {
  if (!store.durable) {
    return false;
  }
  const storage = globalThis.navigator?.storage;
  if (typeof storage?.persisted !== "function") {
    return "unknown";
  }
  try {
    return await storage.persisted();
  } catch {
    return "unknown";
  }
}

export async function storageFacts(store: LocalStore): Promise<StorageFacts> {
  const snapshot = await store.snapshot();
  const records = [
    snapshot.jobs,
    snapshot.steps,
    snapshot.outcomes,
    snapshot.observations,
    snapshot.conversations,
    snapshot.turns,
  ];
  const stamps = [
    ...snapshot.jobs,
    ...snapshot.steps,
    ...snapshot.outcomes,
    ...snapshot.observations,
    ...snapshot.conversations,
  ].map((record) => record.updated_at);
  const durable = store instanceof IndexedDbLocalStore;

  return {
    engine: durable ? "indexeddb" : "memory",
    database: durable ? DB_NAME : null,
    bytes: await estimateBytes(),
    records: records.reduce((total, list) => total + list.length, 0),
    lastWrite: newest([...stamps, ...snapshot.turns.map((turn) => turn.created_at)]),
    persistent: await isPersistent(store),
  };
}

export function localStorageFacts(): KeyFacts[] {
  const store = globalThis.localStorage;
  const facts: KeyFacts[] = [];
  for (let index = 0; index < store.length; index += 1) {
    const key = store.key(index);
    if (!key || !isAppKey(key)) {
      continue;
    }
    facts.push({ key, bytes: key.length + (store.getItem(key)?.length ?? 0) });
  }
  return facts;
}
