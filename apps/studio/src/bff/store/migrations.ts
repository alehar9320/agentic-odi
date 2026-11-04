import type { DBSchema, IDBPDatabase } from "idb";

import type { Observation } from "../../types";
import type {
  DrainLease,
  OutboxRecord,
  StoredConversation,
  StoredJob,
  StoredOutcome,
  StoredStep,
  StoredTurn,
} from "./types";

export const DB_NAME = "agentic-odi-studio";

/**
 * The schema version this build opens. Raising it without adding a matching
 * `MIGRATIONS` entry is caught by `migrations.test.ts`, so a release can never
 * ship a bump that would throw `ConstraintError` on an existing database.
 */
export const DB_VERSION = 2;

export type MetaValue = number | DrainLease;

/**
 * The database shape, in one place: the store reads it and the migration
 * registry writes it. Keep this in step with `DB_VERSION` — the equality test
 * compares a fresh database against a migrated one on exactly this list.
 */
export interface StudioDb extends DBSchema {
  meta: { key: string; value: { key: string; value: MetaValue } };
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
  outbox: {
    key: string;
    value: OutboxRecord;
    indexes: { "by-state": string; "by-created": string };
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

/** One step in the ladder. It creates or alters stores; it never clears them. */
export type Migration = (db: IDBPDatabase<StudioDb>) => void;

/**
 * Every migration keyed by the version it produces, so `MIGRATIONS[2]` is what
 * turns a v1 database into a v2 one. The `upgrade` callback runs each step from
 * `oldVersion + 1` to `DB_VERSION`, which is what makes a v1 database upgrade
 * instead of re-running the create-everything body and throwing.
 */
export const MIGRATIONS: Record<number, Migration> = {
  1: (db) => {
    db.createObjectStore("meta", { keyPath: "key" });
    const jobs = db.createObjectStore("jobs", { keyPath: "id" });
    jobs.createIndex("by-seq", "seq");
    const steps = db.createObjectStore("steps", { keyPath: "id" });
    steps.createIndex("by-job", "job_id");
    steps.createIndex("by-seq", "seq");
    const outcomes = db.createObjectStore("outcomes", { keyPath: "id" });
    outcomes.createIndex("by-job", "job_id");
    outcomes.createIndex("by-seq", "seq");
    const observations = db.createObjectStore("observations", {
      keyPath: "id",
    });
    observations.createIndex("by-created", "created_at");
    const conversations = db.createObjectStore("conversations", {
      keyPath: "id",
    });
    conversations.createIndex("by-updated", "updated_at");
    const turns = db.createObjectStore("turns", {
      keyPath: "id",
      autoIncrement: true,
    });
    turns.createIndex("by-conversation", "conversation_id");
  },
  2: (db) => {
    const outbox = db.createObjectStore("outbox", { keyPath: "id" });
    outbox.createIndex("by-state", "state");
    outbox.createIndex("by-created", "created_at");
  },
};

/**
 * The steps a database at `oldVersion` runs to reach `newVersion`, in order.
 * Exported so a test can assert the ladder is complete and gapless: a version
 * with no registered step fails here by name instead of mid-upgrade.
 */
export function migrationSteps(oldVersion: number, newVersion: number): Migration[] {
  const steps: Migration[] = [];
  for (let version = oldVersion + 1; version <= newVersion; version += 1) {
    const step = MIGRATIONS[version];
    if (!step) {
      throw new Error(
        `No migration registered for version ${version}; add MIGRATIONS[${version}] before raising DB_VERSION to ${newVersion}.`,
      );
    }
    steps.push(step);
  }
  return steps;
}
