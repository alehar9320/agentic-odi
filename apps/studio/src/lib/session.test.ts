import { beforeEach, describe, expect, it } from "vitest";

import { SESSION_KEY, clearSession, loadSession, saveSession } from "./session";

describe("studio session", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("has nothing to restore on a first visit", () => {
    expect(loadSession()).toBeNull();
  });

  it("round-trips the last focused subject", () => {
    saveSession({
      job_id: "JOB-1",
      step_id: null,
      outcome_id: null,
      conversation_id: null,
    });

    expect(loadSession()).toEqual({
      job_id: "JOB-1",
      step_id: null,
      outcome_id: null,
      conversation_id: null,
    });
  });

  it("ignores malformed data instead of throwing", () => {
    localStorage.setItem(SESSION_KEY, "{not json");

    expect(loadSession()).toBeNull();
  });

  it("drops fields that are not strings", () => {
    localStorage.setItem(SESSION_KEY, JSON.stringify({ job_id: 42, outcome_id: "O-1" }));

    expect(loadSession()).toEqual({
      job_id: null,
      step_id: null,
      outcome_id: "O-1",
      conversation_id: null,
    });
  });

  it("clears the stored session", () => {
    saveSession({
      job_id: "JOB-1",
      step_id: null,
      outcome_id: null,
      conversation_id: null,
    });

    clearSession();

    expect(loadSession()).toBeNull();
  });
});
