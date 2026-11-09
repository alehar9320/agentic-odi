/// <reference types="node" />
import { readFileSync, readdirSync } from "node:fs";

import { describe, expect, it } from "vitest";

/**
 * Rule 3 of `docs/architecture/vendor.md`: every vendored file carries a
 * provenance header *and* a ledger entry, so the licence is auditable and a
 * re-copy diff stays possible. Until now the ledger half was promised and
 * absent, which is how a copy silently becomes unsourced code.
 *
 * The lock lives one directory out (`apps/studio/vendor.lock.json`), because a
 * ledger that sits inside the tree it describes gets copied over by the next
 * `add` command.
 */

const vendorDir = "src/vendor";
const lockPath = "vendor.lock.json";

type VendoredEntry = {
  source: string;
  retrieved: string;
  licence: string;
  integrity: string;
  localEdits: string;
};

type Lock = {
  vendored: Record<string, VendoredEntry>;
  firstParty: Record<string, string>;
};

const lock = JSON.parse(readFileSync(lockPath, "utf8")) as Lock;

const ledgerPath = (file: string): string => file.slice(`${vendorDir}/`.length);

/** Copied or authored — the extensions a copy-in can arrive with. */
const trackedSources = (): string[] =>
  readdirSync(vendorDir, { recursive: true })
    .map(String)
    .filter((path) => /\.(ts|tsx|css|md)$/.test(path))
    .filter((path) => !/\.test\.tsx?$/.test(path))
    .map((path) => `${vendorDir}/${path}`);

/**
 * `// vendored: <source> — <SPDX> — retrieved <date> … — local edits: <what>`,
 * or the `<!-- vendored: … -->` form a copied document uses. The em-dash split
 * keeps the shape checkable without a parser: a header that does not split into
 * those parts is not a provenance record.
 */
const headerParts = (source: string): string[] | null => {
  const first = source.split("\n").find((line) => line.trim() !== "");
  const marker = first?.match(/^(?:\/\/|<!--)\s+vendored: (.+?)(?:\s-->)?$/);

  return marker ? marker[1].split(" — ") : null;
};

describe("vendor ledger", () => {
  it("lists every copied and authored file in the tree, in one place only", () => {
    const tracked = trackedSources().map(ledgerPath);
    const declared = [...Object.keys(lock.vendored), ...Object.keys(lock.firstParty)];

    expect(tracked.length).toBeGreaterThan(0);
    expect(declared.filter((path) => !tracked.includes(path))).toEqual([]);
    for (const path of tracked) {
      expect(declared.filter((candidate) => candidate === path)).toHaveLength(1);
    }
  });

  it("requires a canonical provenance header on every copied file", () => {
    for (const path of Object.keys(lock.vendored)) {
      const parts = headerParts(readFileSync(`${vendorDir}/${path}`, "utf8"));

      expect(parts, path).not.toBeNull();
      expect(parts?.[0], path).toBe(lock.vendored[path].source);
      expect(parts?.[1], path).toBe(lock.vendored[path].licence);
      expect(parts?.[2], path).toMatch(/^retrieved \d{4}-\d{2}-\d{2}/);
      expect(parts?.at(-1), path).toMatch(/^local edits: \S/);
    }
  });

  it("keeps a first-party file free of a provenance header", () => {
    for (const path of Object.keys(lock.firstParty)) {
      const source = readFileSync(`${vendorDir}/${path}`, "utf8");

      expect(headerParts(source), path).toBeNull();
    }
  });

  it("records a fetchable source, a licence, a date, and an integrity handle", () => {
    for (const [path, entry] of Object.entries(lock.vendored)) {
      expect(entry.source, path).toMatch(/^https:\/\//);
      expect(entry.licence, path).toMatch(/^[A-Za-z0-9][A-Za-z0-9.\-+]*$/);
      expect(entry.retrieved, path).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(entry.integrity, path).toMatch(/^sha256-[0-9a-f]{64}$/);
      expect(entry.localEdits, path).not.toMatch(/^(unknown|none|n\/a)$/i);
    }
  });

  it("says what drifted, so the next copy-in does not lose the fix", () => {
    const button = lock.vendored["components/ui/button.tsx"];
    const edits = headerParts(readFileSync(`${vendorDir}/components/ui/button.tsx`, "utf8"))?.at(-1);

    expect(button.localEdits).toMatch(/lib\/utils/);
    expect(edits).toMatch(/lib\/utils/);
  });

  it("explains the boundary that lint cannot see", () => {
    for (const surface of ["components/ui", "components/assistant"]) {
      const readme = readFileSync(`${vendorDir}/${surface}/README.md`, "utf8");

      expect(readme).toMatch(/vendor\.lock\.json/);
    }
  });
});
