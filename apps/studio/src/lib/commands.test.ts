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

  it("renames the destination without renaming the command", () => {
    const byName = new Map(STUDIO_COMMANDS.map((command) => [command.name, command]));

    expect(byName.get("/landscape")?.label).toBe("Where to focus");
    expect(byName.get("/jobmap")?.label).toBe("Steps in the job");
    expect(byName.get("/segments")?.label).toBe("Who this is for");
    expect(byName.get("/evidence")?.label).toBe("What customers said");
    expect(byName.get("/capture")?.label).toBe("Add what you heard");
  });

  it("still finds a renamed destination by the words people used before", () => {
    const names = (draft: string) => matchCommands(draft).map((command) => command.name);

    expect(names("/landscape")).toContain("/landscape");
    expect(names("/job map")).toContain("/jobmap");
    expect(names("/verdict")).toContain("/segments");
    expect(names("/quotes")).toContain("/evidence");
    expect(names("/outcome")).toContain("/capture");
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
