import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  QUARANTINE_MAX_AGE_DAYS,
  QUARANTINED,
  type QuarantinedSpec,
} from "../../e2e/quarantine";

/**
 * The ratchet on `apps/studio/e2e/quarantine.ts` (#1118, from #1092).
 *
 * A flaky spec has two honest outcomes: it is fixed, or it is parked with an
 * issue and a date. Everything else is how a suite stops being believed — a
 * green retry that hides a race, or a red lane everyone has learned to ignore.
 *
 * This test is the second pair of eyes on the ledger. It reads the specs
 * themselves rather than trusting the list, so a spec cannot be quarantined by
 * editing a comment alone, and an entry cannot outlive its reason.
 */

/**
 * Where the specs are, resolved from the package the runner was started in.
 * `import.meta.url` is not a file URL under vitest's jsdom environment, and a
 * relative `new URL(...)` silently resolves against an http origin there.
 */
function specsDirectory(): string {
  const fromPackage = join(process.cwd(), "e2e");
  return existsSync(fromPackage) ? fromPackage : join(process.cwd(), "apps/studio/e2e");
}
const MARKER = /^\s*\/\/\s*quarantined:\s*#(\d+)\s+(\d{4}-\d{2}-\d{2})\s*$/;
/** The marker has to be near the top so it is read before the spec's own docs. */
const MARKER_WINDOW = 20;

interface MarkedSpec {
  /** The spec, relative to `apps/studio/`, e.g. `e2e/chat.spec.ts`. */
  spec: string;
  issue: number;
  since: string;
}

function specs(directory: string): string[] {
  const entries = readdirSync(directory, { recursive: true, encoding: "utf8" });
  return entries.filter((entry) => entry.endsWith(".spec.ts")).sort();
}

function marked(): MarkedSpec[] {
  const found: MarkedSpec[] = [];
  const directory = specsDirectory();
  for (const relative of specs(directory)) {
    const lines = readFileSync(join(directory, relative), "utf8")
      .split("\n")
      .slice(0, MARKER_WINDOW);
    for (const line of lines) {
      const match = MARKER.exec(line);
      if (match) {
        found.push({ spec: `e2e/${relative}`, issue: Number(match[1]), since: match[2] });
        break;
      }
    }
  }
  return found;
}

function daysSince(iso: string): number {
  return (Date.now() - Date.parse(`${iso}T00:00:00Z`)) / 86_400_000;
}

describe("the end-to-end quarantine ledger", () => {
  it("parks a spec only when the spec says so", () => {
    const markedSpecs = marked();
    const listed = new Set(QUARANTINED.map((entry) => entry.spec));

    expect(markedSpecs.filter((entry) => !listed.has(entry.spec))).toEqual([]);
  });

  it("lists only specs that carry the marker", () => {
    const markedSpecs = new Set(marked().map((entry) => entry.spec));
    const orphans = QUARANTINED.filter((entry) => !markedSpecs.has(entry.spec));

    expect(orphans.map((entry) => entry.spec)).toEqual([]);
  });

  it("agrees with the marker on the issue and the date", () => {
    const disagreements: string[] = [];
    for (const entry of QUARANTINED as readonly QuarantinedSpec[]) {
      const source = marked().find((candidate) => candidate.spec === entry.spec);
      if (!source) {
        continue;
      }
      if (source.issue !== entry.issue || source.since !== entry.since) {
        disagreements.push(
          `${entry.spec}: the spec says #${source.issue} ${source.since}, the ledger says ` +
            `#${entry.issue} ${entry.since}`,
        );
      }
    }

    expect(disagreements).toEqual([]);
  });

  it("gives every parked spec an issue and a reason", () => {
    const vague = QUARANTINED.filter(
      (entry) =>
        !Number.isInteger(entry.issue) ||
        entry.issue <= 0 ||
        entry.reason.trim().length < 20,
    ).map((entry) => entry.spec);

    expect(vague).toEqual([]);
  });

  it("expires a parked spec after thirty days", () => {
    const expired = QUARANTINED.filter((entry) => daysSince(entry.since) > QUARANTINE_MAX_AGE_DAYS)
      .map((entry) => `${entry.spec} has been parked since ${entry.since} (#${entry.issue})`);

    expect(expired).toEqual([]);
  });

  it("does not accept a date in the future", () => {
    const future = QUARANTINED.filter((entry) => daysSince(entry.since) < 0).map(
      (entry) => entry.spec,
    );

    expect(future).toEqual([]);
  });
});
