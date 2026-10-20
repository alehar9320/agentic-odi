import { describe, expect, it } from "vitest";

import {
  HELP_TEXT,
  STUDIO_COMMANDS,
  isCommandDraft,
  isSlashCommand,
  matchCommands,
} from "./commands";

describe("slash commands", () => {
  it("shows every command for a bare slash", () => {
    expect(matchCommands("/")).toEqual(STUDIO_COMMANDS);
  });

  it("ranks an exact command first", () => {
    expect(matchCommands("/help")[0].name).toBe("/help");
  });

  it("matches on keywords as well as command names", () => {
    const names = matchCommands("/onboarding").map((command) => command.name);
    expect(names[0]).toBe("/start");
  });

  it("returns nothing for a command that does not exist", () => {
    expect(matchCommands("/nope")).toEqual([]);
  });

  it("only treats the first word as a command", () => {
    expect(isCommandDraft("/")).toBe(true);
    expect(isCommandDraft("/help")).toBe(true);
    expect(isCommandDraft("/help me")).toBe(false);
    expect(isSlashCommand("  /status")).toBe(true);
    expect(isSlashCommand("status")).toBe(false);
  });

  it("documents every command in help", () => {
    for (const command of STUDIO_COMMANDS) {
      expect(HELP_TEXT).toContain(command.name);
    }
  });
});
