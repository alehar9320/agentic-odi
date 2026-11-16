import { describe, expect, it } from "vitest";

import "fake-indexeddb/auto";

import { MemoryLocalStore } from "../store/memoryStore";
import { ReceiptService } from "./receiptService";

function service() {
  return new ReceiptService(new MemoryLocalStore());
}

describe("ReceiptService", () => {
  it("stores a receipt keyed by the record it describes", async () => {
    const receipts = service();
    await receipts.record("o-1", "outcome", "saved");
    const list = await receipts.list();
    expect(list).toHaveLength(1);
    expect(list[0].recordId).toBe("o-1");
    expect(list[0].state).toBe("saved");
  });

  it("replaces the receipt for a record rather than duplicating it", async () => {
    const receipts = service();
    await receipts.record("o-1", "outcome", "pending");
    await receipts.record("o-1", "outcome", "saved");
    const list = await receipts.list();
    expect(list).toHaveLength(1);
    expect(list[0].state).toBe("saved");
  });

  it("counts a retry without losing the original attempt count", async () => {
    const receipts = service();
    await receipts.record("o-1", "outcome", "pending");
    await receipts.record("o-1", "outcome", "failed", "offline");
    await receipts.record("o-1", "outcome", "pending");
    const list = await receipts.list();
    expect(list[0].attempts).toBe(2);
  });

  it("reads an interrupted pending write back as failed, not saved", async () => {
    const receipts = service();
    await receipts.record("o-1", "outcome", "pending");
    const list = await receipts.list();
    expect(list[0].state).toBe("failed");
    expect(list[0].error).toBeTruthy();
  });

  it("forgets a receipt on clear", async () => {
    const receipts = service();
    await receipts.record("o-1", "outcome", "saved");
    await receipts.clear("o-1");
    expect(await receipts.list()).toEqual([]);
  });
});
