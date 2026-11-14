/**
 * A notice is what a banner leaves behind.
 *
 * A banner is a statement about the present and it leaves the screen when the
 * condition clears or the toast expires. A notice is the record of that
 * statement: what happened, when, how bad. The severity vocabulary is the
 * banner catalog's, reused rather than reinvented, so a new banner kind never
 * needs a new notice kind.
 */

import type { BannerSeverity } from "../banners/types";

export type NoticeSeverity = BannerSeverity;

export interface Notice {
  id: string;
  severity: NoticeSeverity;
  title: string;
  /** The banner's body, kept verbatim. */
  detail: string;
  /** Where the notice came from, for the row's disclosure. */
  context: string;
  /** Epoch milliseconds the notice was first raised. */
  at: number;
  read: boolean;
}

/** What a caller passes; the recorder assigns the id and the read flag. */
export interface NoticeInput {
  severity: NoticeSeverity;
  title: string;
  detail: string;
  context: string;
  at: number;
}
