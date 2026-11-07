import { beforeEach, describe, expect, it } from "vitest";

import {
  CONVERSATION_KEY,
  SESSION_KEY,
  clearSession,
  loadConversationId,
  loadSession,
  saveConversationId,
  saveSession,
} from "./session";

describe("studio session", () => {
  beforeEach(() => {
    localStorage.clear();
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

  it("round-trips the thread the person was last in", () => {
    saveConversationId("C-7");

    expect(loadConversationId()).toBe("C-7");
  });

  it("has no thread to restore on a first visit", () => {
    expect(loadConversationId()).toBeNull();
  });

  it("writes off the thread when the active one goes away", () => {
    saveConversationId("C-7");

    saveConversationId(null);

    expect(localStorage.getItem(CONVERSATION_KEY)).toBeNull();
    expect(loadConversationId()).toBeNull();
  });

  it("ignores a stored thread that is blank", () => {
    localStorage.setItem(CONVERSATION_KEY, "   ");

    expect(loadConversationId()).toBeNull();
  });

  it("clears the thread with the rest of the session", () => {
    saveConversationId("C-7");

    clearSession();

    expect(loadConversationId()).toBeNull();
  });
});
