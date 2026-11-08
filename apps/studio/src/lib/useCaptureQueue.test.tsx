import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { OutboxRecord } from "../bff/store/types";
import type { Outcome } from "../types";
import { useCaptureQueue } from "./useCaptureQueue";
import { StudioApiError } from "../api/studioApi";

const bff = {
  listQueuedCaptures: vi.fn<() => Promise<Outcome[]>>(),
  listFailedCaptures: vi.fn<() => Promise<Outcome[]>>(),
  failQueuedCapture: vi.fn<(id: string, message: string) => Promise<void>>(),
  discardQueuedCapture: vi.fn<(id: string) => Promise<void>>(),
  replayCaptures: vi.fn<(send: (record: OutboxRecord) => Promise<void> | void) => Promise<number>>(),
};

vi.mock("../bff/index", () => ({
  getStudioBff: vi.fn(() => Promise.resolve(bff)),
}));

const sendQueuedCapture = vi.fn<(record: OutboxRecord, mcpUrl: string) => Promise<Outcome>>();

vi.mock("../api/studioApi", async () => {
  const actual = await vi.importActual<typeof import("../api/studioApi")>("../api/studioApi");
  return {
    ...actual,
    sendQueuedCapture: (record: OutboxRecord, mcpUrl: string) => sendQueuedCapture(record, mcpUrl),
  };
});

function outcome(overrides: Partial<Outcome> = {}): Outcome {
  return {
    id: "cap-1",
    job_id: "JOB-1",
    statement: "Minimize the time it takes to ship",
    importance: 8,
    satisfaction: 3,
    opportunity_score: 13,
    ...overrides,
  };
}

function record(id = "cap-1"): OutboxRecord {
  return {
    id,
    kind: "create",
    entity: "outcome",
    local_id: id,
    server_id: null,
    payload: {},
    depends_on: [],
    state: "pending",
    attempts: 0,
    last_error: null,
    created_at: "2026-01-01T00:00:00.000Z",
    acknowledged_at: null,
  };
}

const original = Object.getOwnPropertyDescriptor(window.navigator, "onLine");

function setOnLine(value: boolean) {
  Object.defineProperty(window.navigator, "onLine", { value, configurable: true });
}

beforeEach(() => {
  setOnLine(true);
  bff.listQueuedCaptures.mockReset().mockResolvedValue([]);
  bff.listFailedCaptures.mockReset().mockResolvedValue([]);
  bff.failQueuedCapture.mockReset().mockResolvedValue(undefined);
  bff.discardQueuedCapture.mockReset().mockResolvedValue(undefined);
  bff.replayCaptures.mockReset().mockResolvedValue(0);
  sendQueuedCapture.mockReset().mockResolvedValue(outcome());
});

afterEach(() => {
  if (original) {
    Object.defineProperty(window.navigator, "onLine", original);
  }
  vi.unstubAllGlobals();
});

describe("useCaptureQueue", () => {
  it("reads the waiting captures on mount", async () => {
    bff.listQueuedCaptures.mockResolvedValue([outcome()]);
    const { result } = renderHook(() => useCaptureQueue("http://mcp/mcp"));

    await waitFor(() => expect(result.current.waiting).toBe(1));
    expect(result.current.queued).toHaveLength(1);
  });

  it("surfaces refused captures so they are not silently dropped", async () => {
    bff.listFailedCaptures.mockResolvedValue([outcome({ id: "cap-refused" })]);
    const { result } = renderHook(() => useCaptureQueue("http://mcp/mcp"));

    await waitFor(() => expect(result.current.failed).toHaveLength(1));
    expect(result.current.failed[0].id).toBe("cap-refused");
  });

  it("replays the queue when the browser comes back online", async () => {
    setOnLine(false);
    const { result } = renderHook(() => useCaptureQueue("http://mcp/mcp"));
    // The mount read runs even while offline; the replay waits for the signal.
    await waitFor(() => expect(bff.listQueuedCaptures).toHaveBeenCalled());
    expect(bff.replayCaptures).not.toHaveBeenCalled();

    act(() => {
      setOnLine(true);
      window.dispatchEvent(new Event("online"));
    });

    await waitFor(() => expect(bff.replayCaptures).toHaveBeenCalledTimes(1));
    void result;
  });

  it("keeps a transport failure queued for the next attempt", async () => {
    // A replay hands the send to the BFF; the hook wires the real transport.
    bff.replayCaptures.mockImplementation(async (send) => {
      await send(record());
      return 0;
    });
    sendQueuedCapture.mockRejectedValue(new TypeError("Failed to fetch"));

    const { result } = renderHook(() => useCaptureQueue("http://mcp/mcp"));
    await waitFor(() => expect(bff.listQueuedCaptures).toHaveBeenCalled());
    await act(async () => {
      await expect(result.current.replay()).rejects.toThrow();
    });

    // A transport failure is rethrown so the drain leaves the record pending.
    expect(bff.failQueuedCapture).not.toHaveBeenCalled();
  });

  it("marks a refused capture failed rather than retrying it forever", async () => {
    bff.replayCaptures.mockImplementation(async (send) => {
      await send(record());
      return 0;
    });
    sendQueuedCapture.mockRejectedValue(
      new StudioApiError({ code: "validation", message: "Refused.", retryable: false }, 422, true),
    );

    const { result } = renderHook(() => useCaptureQueue("http://mcp/mcp"));
    await waitFor(() => expect(bff.listQueuedCaptures).toHaveBeenCalled());
    await act(async () => {
      await result.current.replay();
    });

    expect(bff.failQueuedCapture).toHaveBeenCalledWith("cap-1", "Refused.");
  });

  it("drops a queued capture and refreshes the count", async () => {
    bff.listQueuedCaptures.mockResolvedValue([outcome()]);
    const { result } = renderHook(() => useCaptureQueue("http://mcp/mcp"));
    await waitFor(() => expect(result.current.waiting).toBe(1));

    bff.listQueuedCaptures.mockResolvedValue([]);
    await act(async () => {
      await result.current.discard("cap-1");
    });

    expect(bff.discardQueuedCapture).toHaveBeenCalledWith("cap-1");
    expect(result.current.waiting).toBe(0);
  });
});
