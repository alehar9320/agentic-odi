import { describe, expect, it } from "vitest";

import {
  HELP_TEXT,
  STUDIO_COMMANDS,
  isCommandDraft,
  isSlashCommand,
  matchCommands,
  planInterview,
  transcriptFormatFor,
  transcriptTitleFor,
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

  it("finds the transcript import by its own words", () => {
    expect(matchCommands("/interview")[0].name).toBe("/interview");
    expect(matchCommands("/transcript").map((command) => command.name)).toContain("/interview");
  });
});

describe("/interview planning", () => {
  it("plans one readable text file as an import, titled from its name", () => {
    const plan = planInterview([
      { name: "ana-onboarding.md", contentType: "text/markdown", text: "Ana: hello" },
    ]);
    expect(plan).toEqual({ kind: "import", title: "ana-onboarding", format: "md" });
  });

  it("names the format from the extension so a .vtt is parsed as WebVTT", () => {
    expect(transcriptFormatFor("session.vtt")).toBe("vtt");
    expect(transcriptFormatFor("Session.SRT")).toBe("srt");
    expect(transcriptFormatFor("notes.txt")).toBe("txt");
  });

  it("leaves the format to the importer when the extension is not one it names", () => {
    expect(transcriptFormatFor("pasted")).toBeUndefined();
    expect(transcriptFormatFor("transcript.docx")).toBeUndefined();
  });

  it("derives a human title from the filename, falling back when there is none", () => {
    expect(transcriptTitleFor("customer call.md")).toBe("customer call");
    expect(transcriptTitleFor(".md")).toBe("Attached transcript");
  });

  it("refuses when nothing is attached", () => {
    const plan = planInterview([]);
    expect(plan).toEqual({
      kind: "refuse",
      reason: "Attach a transcript first, then run `/interview`.",
    });
  });

  it("refuses more than one file rather than guessing which is the transcript", () => {
    const plan = planInterview([
      { name: "a.md", text: "a" },
      { name: "b.md", text: "b" },
    ]);
    expect(plan.kind).toBe("refuse");
    expect(plan).toHaveProperty("reason", expect.stringContaining("one transcript at a time"));
  });

  it("refuses an image, naming the file", () => {
    const plan = planInterview([{ name: "shot.png", contentType: "image/png" }]);
    expect(plan.kind).toBe("refuse");
    expect(plan).toHaveProperty("reason", expect.stringContaining("shot.png is an image"));
  });

  it("refuses a file whose text could not be read", () => {
    const plan = planInterview([{ name: "notes.md", contentType: "text/markdown" }]);
    expect(plan.kind).toBe("refuse");
    expect(plan).toHaveProperty("reason", expect.stringContaining("could not be read as text"));
  });
});
