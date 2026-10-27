import { beforeEach, describe, expect, it } from "vitest";

import {
  CHANGELOG_READ_KEY,
  markReleasesRead,
  readReleaseVersions,
  unreadReleases,
} from "./changelogRead";

const RELEASES = [
  { version: "0.9.0", date: "2026-10-22", categories: [] },
  { version: "0.8.0", date: "2026-10-20", categories: [] },
];

describe("changelog read state", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("starts with nothing acknowledged", () => {
    expect(readReleaseVersions()).toEqual([]);
    expect(unreadReleases(RELEASES, [])).toHaveLength(2);
  });

  it("persists the versions it is given and ignores repeats", () => {
    markReleasesRead(["0.8.0"]);
    expect(markReleasesRead(["0.8.0", "0.9.0"])).toEqual(["0.8.0", "0.9.0"]);

    expect(readReleaseVersions()).toEqual(["0.8.0", "0.9.0"]);
    expect(unreadReleases(RELEASES, readReleaseVersions())).toEqual([]);
  });

  it("treats a damaged value as nothing acknowledged", () => {
    window.localStorage.setItem(CHANGELOG_READ_KEY, "not json");
    expect(readReleaseVersions()).toEqual([]);

    window.localStorage.setItem(CHANGELOG_READ_KEY, JSON.stringify({ version: "0.9.0" }));
    expect(readReleaseVersions()).toEqual([]);

    window.localStorage.setItem(CHANGELOG_READ_KEY, JSON.stringify(["0.9.0", 42]));
    expect(readReleaseVersions()).toEqual(["0.9.0"]);
  });
});
