import type { OutboxEntity } from "../bff/store/types";

/**
 * What happened to one canvas write. The words are the same four the outbox
 * already uses for a queued record, so the row chip and the queue never
 * disagree about what "failed" means.
 */
export type ReceiptState = "pending" | "saved" | "failed" | "changed";

/** One durable receipt, keyed by the record it describes. */
export interface WriteReceipt {
  recordId: string;
  kind: OutboxEntity;
  state: ReceiptState;
  attempts: number;
  error: string | null;
  at: string;
}

/** The word a row shows for a state — never a colour alone. */
export const RECEIPT_LABEL: Record<ReceiptState, string> = {
  pending: "Saving…",
  saved: "Saved",
  failed: "Not saved",
  changed: "Changed elsewhere",
};

/**
 * The one sentence a state transition announces, so a burst of writes is a
 * sentence each rather than one per render. `null` means nothing to say: a
 * receipt that only changed its timestamp is not news.
 */
export function receiptAnnouncement(
  previous: WriteReceipt | undefined,
  next: WriteReceipt,
): string | null {
  if (previous && previous.state === next.state) {
    return null;
  }
  const label = RECEIPT_LABEL[next.state];
  switch (next.state) {
    case "pending":
      return `Saving ${next.kind}…`;
    case "saved":
      return `${capitalise(next.kind)} saved.`;
    case "failed":
      return `${capitalise(next.kind)} not saved${next.error ? `: ${next.error}` : ""}.`;
    case "changed":
      return `${capitalise(next.kind)} changed elsewhere.`;
    default:
      return label;
  }
}

/**
 * A receipt found on boot that was still `pending` is not a saved record: the
 * write never settled, so the row says so and offers Retry instead of claiming
 * success. Every other state is already settled and reads back as itself.
 */
export function onBoot<T extends WriteReceipt>(receipt: T): T {
  return receipt.state === "pending"
    ? {
        ...receipt,
        state: "failed",
        error: receipt.error ?? "Interrupted before it saved.",
      }
    : receipt;
}

/** The receipt for a record, or undefined when nothing was ever written. */
export function receiptFor(
  receipts: WriteReceipt[],
  recordId: string,
): WriteReceipt | undefined {
  return receipts.find((receipt) => receipt.recordId === recordId);
}

function capitalise(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
