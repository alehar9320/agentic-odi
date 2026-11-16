import { nowIso } from "../id";
import type { LocalStore, OutboxEntity, StoredReceipt } from "../store/types";
import { onBoot, type ReceiptState } from "../../lib/receipts";

/**
 * The durable side of a write receipt: one row per record, so a failed save is
 * recoverable after the toast that announced it has gone. The words and the
 * boot rule live in `lib/receipts.ts`; this only stores them.
 */
export class ReceiptService {
  constructor(private readonly store: LocalStore) {}

  /** Write or replace the receipt for a record. `seq` keeps read order stable. */
  async record(
    recordId: string,
    kind: OutboxEntity,
    state: ReceiptState,
    error: string | null = null,
  ): Promise<StoredReceipt> {
    const existing = await this.store.getReceipt(recordId);
    const attempts = state === "pending" ? (existing?.attempts ?? 0) + 1 : existing?.attempts ?? 0;
    const receipt: StoredReceipt = {
      recordId,
      kind,
      state,
      attempts,
      error,
      at: nowIso(),
      seq: existing?.seq ?? (await this.store.nextSeq()),
    };
    await this.store.putReceipt(receipt);
    return receipt;
  }

  /**
   * Every receipt, oldest first. A `pending` receipt is one whose write never
   * settled — an interrupted save — so it reads back as failed and offers
   * Retry rather than passing itself off as saved.
   */
  async list(): Promise<StoredReceipt[]> {
    const receipts = await this.store.listReceipts();
    return receipts.map(onBoot);
  }

  async clear(recordId: string): Promise<void> {
    await this.store.deleteReceipt(recordId);
  }
}
