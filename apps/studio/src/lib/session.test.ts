import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { refusingStorage } from "../test/storage";
import { SESSION_KEY, clearSession, loadSession, saveSession } from "./session";

describe("studio session", () => {
  let refusing: ReturnType<typeof refusingStorage> | null = null;

  beforeEach(() => {
    refusing?.restore();
    refusing = null;
    localStorage.clear();
  });

  afterEach(() => {
    refusing?.restore();
    refusing = null;
  });

  it("has nothing to restore on a first visit", () => {
    expect(loadSession()).toBeNull();
  });

  it("round-trips the last focused subject", () => {
    saveSession({ job_id: "JOB-1", step_id: null, outcome_id: null });

    expect(loadSession()).toEqual({ job_id: "JOB-1", step_id: null, outcome_id: null });
  });

  it("ignores malformed data instead of throwing", () => {
    localStorage.setItem(SESSION_KEY, "{not json");

    expect(loadSession()).toBeNull();
  });

  it("drops fields that are not strings", () => {
    localStorage.setItem(SESSION_KEY, JSON.stringify({ job_id: 42, outcome_id: "O-1" }));

    expect(loadSession()).toEqual({ job_id: null, step_id: null, outcome_id: "O-1" });
  });

  it("clears the stored session", () => {
    saveSession({ job_id: "JOB-1", step_id: null, outcome_id: null });

    clearSession();

    expect(loadSession()).toBeNull();
  });

  it("has nothing to restore when the browser refuses the read", () => {
    refusing = refusingStorage("getItem");

    expect(loadSession()).toBeNull();
    expect(refusing.attempts()).toBeGreaterThan(0);
  });

  it("carries no error to its caller when the store refuses the write", () => {
    refusing = refusingStorage("setItem");

    saveSession({ job_id: "JOB-1", step_id: null, outcome_id: null });
    clearSession();

    // Neither call reached the store, and neither threw at its caller.
    expect(refusing.attempts()).toBe(1);
  });
});
