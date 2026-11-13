import { describe, expect, it } from "vitest";

import {
  onBoot,
  receiptAnnouncement,
  receiptFor,
  RECEIPT_LABEL,
  type WriteReceipt,
} from "./receipts";

function receipt(overrides: Partial<WriteReceipt> = {}): WriteReceipt {
  return {
    recordId: "o-1",
    kind: "outcome",
    state: "pending",
    attempts: 0,
    error: null,
    at: "2026-11-13T00:00:00.000Z",
    ...overrides,
  };
}

describe("receipt labels", () => {
  it("names every state in words, never a colour alone", () => {
    expect(RECEIPT_LABEL.pending).toBe("Saving…");
    expect(RECEIPT_LABEL.saved).toBe("Saved");
    expect(RECEIPT_LABEL.failed).toBe("Not saved");
    expect(RECEIPT_LABEL.changed).toBe("Changed elsewhere");
  });
});

describe("receiptAnnouncement", () => {
  it("says one sentence when a write starts", () => {
    expect(receiptAnnouncement(undefined, receipt())).toBe("Saving outcome…");
  });

  it("says one sentence when a write settles", () => {
    expect(receiptAnnouncement(receipt(), receipt({ state: "saved" }))).toBe(
      "Outcome saved.",
    );
  });

  it("carries the reason a write failed", () => {
    expect(
      receiptAnnouncement(
        receipt({ state: "pending" }),
        receipt({ state: "failed", error: "offline" }),
      ),
    ).toBe("Outcome not saved: offline.");
  });

  it("stays silent when a receipt only changed its timestamp", () => {
    expect(
      receiptAnnouncement(
        receipt({ state: "saved", at: "2026-11-13T00:00:00.000Z" }),
        receipt({ state: "saved", at: "2026-11-13T00:01:00.000Z" }),
      ),
    ).toBeNull();
  });
});

describe("onBoot", () => {
  it("never claims an interrupted write succeeded", () => {
    const booted = onBoot(receipt({ state: "pending" }));
    expect(booted.state).toBe("failed");
    expect(booted.error).toBeTruthy();
  });

  it("reads a settled receipt back as itself", () => {
    const saved = receipt({ state: "saved" });
    expect(onBoot(saved)).toBe(saved);
  });
});

describe("receiptFor", () => {
  it("finds the receipt for a record, or nothing", () => {
    const list = [receipt({ recordId: "o-1" }), receipt({ recordId: "o-2" })];
    expect(receiptFor(list, "o-2")?.recordId).toBe("o-2");
    expect(receiptFor(list, "o-3")).toBeUndefined();
  });
});
