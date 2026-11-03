import { afterEach, beforeEach, describe, expect, it } from "vitest";

import "fake-indexeddb/auto";

import { IndexedDbLocalStore } from "./store/indexedDbStore";
import { MemoryLocalStore } from "./store/memoryStore";
import {
  APP_STORAGE_KEYS,
  APP_STORAGE_PREFIXES,
  localStorageFacts,
  storageFacts,
} from "./storageFacts";

async function makeDbStore() {
  return IndexedDbLocalStore.open();
}

async function dropDb() {
  await indexedDB.deleteDatabase("agentic-odi-studio");
}

const job = {
  id: "j-1",
  name: "Activation",
  description: "",
  seq: 1,
  created_at: "2026-01-01T00:00:00.000Z",
  updated_at: "2026-04-01T09:00:00.000Z",
};

const step = {
  id: "s-1",
  job_id: "j-1",
  name: "First run",
  order: 1,
  seq: 2,
  created_at: "2026-01-02T00:00:00.000Z",
  updated_at: "2026-03-01T00:00:00.000Z",
};

const outcome = {
  id: "o-1",
  job_id: "j-1",
  statement: "Minimize the time it takes to reach first value",
  importance: 8,
  satisfaction: 2,
  opportunity_score: 14,
  step_id: null,
  seq: 3,
  created_at: "2026-01-03T00:00:00.000Z",
  updated_at: "2026-05-06T07:08:09.000Z",
};

describe("storageFacts of the local store", () => {
  beforeEach(async () => {
    await dropDb();
  });

  afterEach(async () => {
    await dropDb();
  });

  it("names the engine and the database a person's work actually sits in", async () => {
    const store = await makeDbStore();
    await store.putJob(job);

    const facts = await storageFacts(store);
    store.close();

    expect(facts.engine).toBe("indexeddb");
    expect(facts.database).toBe("agentic-odi-studio");
    expect(facts.persistent).not.toBe(false);
  });

  it("counts every stored record, turns included, from the store itself", async () => {
    const store = await makeDbStore();
    await store.putJob(job);
    await store.putStep(step);
    await store.putOutcome(outcome);
    await store.putConversation({
      id: "c-1",
      title: "Activation",
      created_at: "2026-05-01T00:00:00.000Z",
      updated_at: "2026-05-01T00:00:00.000Z",
      head_id: null,
    });
    await store.appendTurn({
      conversation_id: "c-1",
      role: "user",
      content: "Where does this land?",
      created_at: "2026-05-02T00:00:00.000Z",
      message_id: null,
      parent_id: null,
    });

    const facts = await storageFacts(store);
    store.close();

    expect(facts.records).toBe(5);
  });

  it("reports the newest write the records themselves carry", async () => {
    const store = await makeDbStore();
    await store.putJob(job);
    await store.putOutcome(outcome);

    const facts = await storageFacts(store);
    store.close();

    expect(facts.lastWrite).toBe("2026-05-06T07:08:09.000Z");
  });

  it("says nothing was written when the store is empty", async () => {
    const store = await makeDbStore();

    const facts = await storageFacts(store);
    store.close();

    expect(facts.records).toBe(0);
    expect(facts.lastWrite).toBeNull();
  });

  it("reports the memory store as session-only, with no database behind it", async () => {
    const store = new MemoryLocalStore();
    await store.putJob(job);

    const facts = await storageFacts(store);

    expect(facts.engine).toBe("memory");
    expect(facts.database).toBeNull();
    expect(facts.persistent).toBe(false);
    expect(facts.records).toBe(1);
  });

  it("reports unknown bytes rather than zero when the browser offers no estimate", async () => {
    const store = new MemoryLocalStore();

    const facts = await storageFacts(store);

    expect(facts.bytes).toBe("unknown");
    expect(facts.bytes).not.toBe(0);
  });

  it("reports the usage the browser measures when it answers", async () => {
    const store = new MemoryLocalStore();
    const original = Object.getOwnPropertyDescriptor(navigator, "storage");
    Object.defineProperty(navigator, "storage", {
      configurable: true,
      value: { estimate: async () => ({ usage: 1234 }) },
    });

    const facts = await storageFacts(store);
    if (original) {
      Object.defineProperty(navigator, "storage", original);
    } else {
      Object.defineProperty(navigator, "storage", {
        configurable: true,
        writable: true,
        value: undefined,
      });
    }

    expect(facts.bytes).toBe(1234);
  });
});

describe("localStorage facts", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("lists every key the app writes with the size it holds", () => {
    localStorage.setItem("studio.displayName", "Ada");
    localStorage.setItem("studio.settings", JSON.stringify({ api_key: "x" }));

    const facts = localStorageFacts();

    expect(facts).toContainEqual({ key: "studio.displayName", bytes: 21 });
    expect(facts).toHaveLength(2);
  });

  it("carries a flag key written under the flags prefix", () => {
    localStorage.setItem("studio.flags.firstRunIntro", "on");

    expect(localStorageFacts()).toContainEqual({
      key: "studio.flags.firstRunIntro",
      bytes: 28,
    });
  });

  it("ignores a key the app did not write", () => {
    localStorage.setItem("someone-elses-key", "value");

    expect(localStorageFacts()).toEqual([]);
  });

  it("names keys and sizes and never touches a stored value", () => {
    localStorage.setItem("studio.settings", JSON.stringify({ api_key: "sk-DO-NOT-LEAK" }));

    const rendered = JSON.stringify(localStorageFacts());

    expect(rendered).toContain("studio.settings");
    expect(rendered).not.toContain("sk-DO-NOT-LEAK");
  });

  it("reports nothing for a browser that has never stored anything", () => {
    expect(localStorageFacts()).toEqual([]);
  });

  it("lists every key literal the app's own writers use", () => {
    const sources = import.meta.glob("../**/*.{ts,tsx}", {
      query: "?raw",
      import: "default",
      eager: true,
    }) as Record<string, string>;

    const writers = Object.entries(sources).filter(
      ([path, text]) =>
        !path.endsWith(".test.tsx") && !path.endsWith(".test.ts") && text.includes("localStorage"),
    );
    expect(writers.length).toBeGreaterThan(0);

    const listed = [...APP_STORAGE_KEYS, ...APP_STORAGE_PREFIXES];
    const unlisted: string[] = [];
    for (const [path, text] of writers) {
      for (const literal of text.match(/"(?:studio|agentic-odi)\.[a-zA-Z][^"]*"/g) ?? []) {
        const key = literal.slice(1, -1);
        // A literal with `<` in it is a placeholder in prose, not a key.
        if (key.includes("<") || listed.some((entry) => key.startsWith(entry))) {
          continue;
        }
        unlisted.push(`${path} writes ${key}`);
      }
    }
    expect(unlisted, `written but not inventoried: ${unlisted.join("; ")}`).toEqual([]);
  });

  it("holds no duplicate key in the inventory", () => {
    const duplicates = APP_STORAGE_KEYS.filter(
      (key, index) => APP_STORAGE_KEYS.indexOf(key) !== index,
    );
    expect(duplicates).toEqual([]);
  });
});
