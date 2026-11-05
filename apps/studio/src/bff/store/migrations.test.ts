import { describe, expect, it } from "vitest";

import { DB_VERSION, MIGRATIONS, migrationSteps } from "./migrations";

/**
 * The registry is the contract that keeps a version bump honest. These tests
 * fail the moment `DB_VERSION` is raised without a matching migration, which is
 * the failure the old unconditional `upgrade` body could not report: it would
 * have thrown `ConstraintError` for every existing user instead.
 */
describe("migration registry", () => {
  it("registers a step for every version up to DB_VERSION", () => {
    const missing: number[] = [];
    for (let version = 1; version <= DB_VERSION; version += 1) {
      if (!MIGRATIONS[version]) {
        missing.push(version);
      }
    }
    expect(
      missing,
      `DB_VERSION is ${DB_VERSION} but no migration is registered for: ${missing.join(", ")}.`,
    ).toEqual([]);
  });

  it("has the current version's step", () => {
    expect(typeof MIGRATIONS[DB_VERSION]).toBe("function");
  });

  it("names the missing version when a step is absent", () => {
    const unregistered = DB_VERSION + 1;
    expect(() => migrationSteps(DB_VERSION, unregistered)).toThrow(
      new RegExp(`No migration registered for version ${unregistered}`),
    );
  });

  it("runs the steps from oldVersion + 1 to newVersion in order", () => {
    const steps = migrationSteps(0, DB_VERSION);
    expect(steps).toHaveLength(DB_VERSION);
    expect(steps[0]).toBe(MIGRATIONS[1]);
    expect(steps[DB_VERSION - 1]).toBe(MIGRATIONS[DB_VERSION]);
  });

  it("returns no steps when the database is already current", () => {
    expect(migrationSteps(DB_VERSION, DB_VERSION)).toEqual([]);
  });
});
