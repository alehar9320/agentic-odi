import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { SESSION_KEY, SESSION_SCHEMA_VERSION, clearSession, loadSession, saveSession } from "./session";

function installStorage(storage: Storage | null): () => void {
  const previous = Object.getOwnPropertyDescriptor(window, "localStorage");
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    get: () => storage,
  });
  return () => {
    if (previous) {
      Object.defineProperty(window, "localStorage", previous);
    }
  };
}

describe("studio session", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("has nothing to restore on a first visit", () => {
    expect(loadSession()).toBeNull();
  });

  it("round-trips the last focused subject", () => {
    saveSession({
      schema_version: SESSION_SCHEMA_VERSION,
      job_id: "JOB-1",
      step_id: null,
      outcome_id: null,
    });

    expect(loadSession()).toEqual({
      schema_version: SESSION_SCHEMA_VERSION,
      job_id: "JOB-1",
      step_id: null,
      outcome_id: null,
    });
  });

  it("writes the schema version", () => {
    saveSession({
      schema_version: SESSION_SCHEMA_VERSION,
      job_id: "JOB-1",
      step_id: null,
      outcome_id: null,
    });

    const raw = localStorage.getItem(SESSION_KEY);
    const parsed = JSON.parse(raw!);
    expect(parsed.schema_version).toBe(SESSION_SCHEMA_VERSION);
  });

  it("ignores malformed data instead of throwing", () => {
    localStorage.setItem(SESSION_KEY, "{not json");

    expect(loadSession()).toBeNull();
  });

  it("drops fields that are not strings", () => {
    localStorage.setItem(
      SESSION_KEY,
      JSON.stringify({
        schema_version: SESSION_SCHEMA_VERSION,
        job_id: 42,
        outcome_id: "O-1",
      })
    );

    expect(loadSession()).toEqual({
      schema_version: SESSION_SCHEMA_VERSION,
      job_id: null,
      step_id: null,
      outcome_id: "O-1",
    });
  });

  it("returns null and clears an unknown version", () => {
    localStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ schema_version: 2, job_id: "JOB-1" })
    );

    expect(loadSession()).toBeNull();
    expect(localStorage.getItem(SESSION_KEY)).toBeNull();
  });

  it("reads a legacy object with no version as empty", () => {
    localStorage.setItem(SESSION_KEY, JSON.stringify({ job_id: "JOB-1" }));

    expect(loadSession()).toBeNull();
    expect(localStorage.getItem(SESSION_KEY)).toBeNull();
  });

  it("clears the stored session", () => {
    saveSession({
      schema_version: SESSION_SCHEMA_VERSION,
      job_id: "JOB-1",
      step_id: null,
      outcome_id: null,
    });

    clearSession();

    expect(loadSession()).toBeNull();
  });

  describe("when storage is unavailable", () => {
    let restore: (() => void) | null = null;

    afterEach(() => {
      restore?.();
      restore = null;
    });

    it("returns null when reading storage throws, and never throws when writing", () => {
      restore = installStorage({
        getItem: () => {
          throw new DOMException("denied", "SecurityError");
        },
        setItem: () => {
          throw new DOMException("denied", "SecurityError");
        },
        removeItem: () => {
          throw new DOMException("denied", "SecurityError");
        },
      } as unknown as Storage);

      expect(loadSession()).toBeNull();
      expect(() => saveSession({ schema_version: SESSION_SCHEMA_VERSION, job_id: null, step_id: null, outcome_id: null })).not.toThrow();
      expect(() => clearSession()).not.toThrow();
    });

    it("does not throw when saving to a full quota", () => {
      restore = installStorage({
        getItem: () => null,
        setItem: () => {
          throw new DOMException("full", "QuotaExceededError");
        },
        removeItem: () => {},
      } as unknown as Storage);

      expect(() => saveSession({ schema_version: SESSION_SCHEMA_VERSION, job_id: "JOB-1", step_id: null, outcome_id: null })).not.toThrow();
      expect(loadSession()).toBeNull();
    });
  });

  it("still round-trips a session when storage works", () => {
    saveSession({ schema_version: SESSION_SCHEMA_VERSION, job_id: "JOB-1", step_id: "S-1", outcome_id: "O-1" });

    expect(loadSession()).toEqual({ schema_version: SESSION_SCHEMA_VERSION, job_id: "JOB-1", step_id: "S-1", outcome_id: "O-1" });
  });
});
