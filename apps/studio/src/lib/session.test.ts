import { beforeEach, describe, expect, it } from "vitest";

import { SESSION_KEY, SESSION_SCHEMA_VERSION, clearSession, loadSession, saveSession } from "./session";

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
});
