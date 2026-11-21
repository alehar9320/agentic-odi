/**
 * The quarantine list: the only honest way to park a flaky spec.
 *
 * A spec that fails intermittently on `main` is not fixed by a retry. It is
 * either repaired or parked, and parking it means saying so where a reader will
 * see it: the file carries a `// quarantined: #<issue> <YYYY-MM-DD>` line in its
 * first twenty lines, and this list carries the reason.
 *
 * An entry is a debt with an expiry, not an exemption. `e2eQuarantine.test.ts`
 * fails the suite when
 *
 *   - a spec carries the marker and no entry here,
 *   - an entry names a spec that has no marker,
 *   - an entry has no issue, or a date in the future,
 *   - an entry is more than thirty days old.
 *
 * The list is empty on purpose. A quarantined spec still runs (it is not
 * skipped), so a fix is proven by the entry being deleted.
 */
export interface QuarantinedSpec {
  /** The spec file, relative to `apps/studio/`. */
  spec: string;
  /** The issue that owns the fix. */
  issue: number;
  /** The ISO date the spec was parked. */
  since: string;
  /** Why it is parked, so the next reader does not rediscover it. */
  reason: string;
}

export const QUARANTINED: readonly QuarantinedSpec[] = [];

/** How long a quarantined spec may stay parked before the ratchet fails. */
export const QUARANTINE_MAX_AGE_DAYS = 30;
