/**
 * The record a person is looking at, as a pointer and as the store's own words.
 *
 * The browser knows which row is selected; only the store knows what that row
 * says. So a turn carries kind and id, the sidecar re-reads the record, and the
 * model hears nothing about a pointer it cannot verify.
 */

import type { CanvasData, FocusPointer, FocusSubject } from "../types";
import { RECORD_SECTIONS, buildRecords, recordTitle, type RecordKind } from "./records";

/**
 * The kinds a pointer may name: exactly the kinds the records table can show,
 * which are the kinds the store is able to read back. Taken from
 * `RECORD_SECTIONS` rather than restated, so the two cannot drift apart.
 */
const READABLE_KINDS: readonly string[] = RECORD_SECTIONS.map((section) => section.kind);

/** The selection as a pointer, or null for a kind the sidecar cannot verify. */
export function focusPointer(focus: FocusSubject | null): FocusPointer | null {
  if (!focus) {
    return null;
  }
  return READABLE_KINDS.includes(focus.kind)
    ? { kind: focus.kind as RecordKind, id: focus.id }
    : null;
}

/**
 * What the snapshot calls the selected record, or null when it does not hold it.
 *
 * Null here means the composer has nothing to admit to: a chip for a record this
 * canvas cannot name would be saying something the store never said.
 */
export function focusLabel(
  canvas: CanvasData | null | undefined,
  focus: FocusSubject | null,
): string | null {
  const pointer = focusPointer(focus);
  if (!pointer || !canvas) {
    return null;
  }
  const row = buildRecords(canvas).find(
    (candidate) => candidate.kind === pointer.kind && candidate.id === pointer.id,
  );
  return row ? recordTitle(row) : null;
}
