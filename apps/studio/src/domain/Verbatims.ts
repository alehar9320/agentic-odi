/**
 * The customer words behind a finding.
 *
 * There is no session or verbatim layer in the store today (see the gap
 * analysis in #741): "quotes" are `Evidence.content` strings. This module
 * names the shape those strings will take, mapped straight onto the existing
 * `Evidence` fields, so when the store fills up this becomes real with no UI
 * change.
 *
 * The count is the honest part. It is the real `record_counts.evidence` when a
 * canvas provenance exists, and `null` — hidden, never estimated — when it does
 * not.
 */

import type { CanvasProvenance } from "../types";

/** A subject a session-evidence lookup can be keyed on. */
export interface SessionSubject {
  kind: string;
  id: string;
}

/**
 * One quote, mapped straight onto the `Evidence` fields it will come from.
 *
 * These three fields are the whole shape: when `Evidence` records arrive, a
 * `SessionQuote` is a projection of one, not a new record.
 */
export interface SessionQuote {
  content: string;
  source_name: string;
  source_kind: string;
}

export interface SessionEvidence {
  quotes: SessionQuote[];
  /** The real evidence count, or `null` when no provenance says what it is. */
  count: number | null;
  /** `"real"` when the store produced these quotes, `"illustrative"` for a mock. */
  basis: "real" | "illustrative";
}

/** The one illustrative quote the mock returns, labelled as such. */
const ILLUSTRATIVE_QUOTES: SessionQuote[] = [
  {
    content:
      "We keep the spreadsheet open beside the tool because we don't trust the numbers in it yet.",
    source_name: "Interview — operations lead",
    source_kind: "interview",
  },
];

/**
 * The session evidence behind a subject.
 *
 * `provenance` is the canvas provenance, when the caller has one. Its
 * `record_counts.evidence` is the only source for `count`: this function never
 * estimates it, and returns `null` so the caller hides the number instead of
 * inventing one.
 */
export function getSessionEvidence(
  _subject: SessionSubject,
  provenance?: CanvasProvenance | null,
): SessionEvidence {
  const evidenceCount = provenance?.record_counts?.evidence;
  return {
    quotes: ILLUSTRATIVE_QUOTES.map((quote) => ({ ...quote })),
    count: typeof evidenceCount === "number" ? evidenceCount : null,
    basis: "illustrative",
  };
}
