import { describe, expect, it } from "vitest";

import { announcementText, spokenText } from "./transcript";

describe("spokenText", () => {
  it("flattens Markdown into speech", () => {
    expect(spokenText("## Scored **three** outcomes\n\n- one\n- two")).toBe(
      "Scored three outcomes. one. two",
    );
  });

  it("keeps code readable and drops rules", () => {
    expect(spokenText("Run this:\n\n```\nodi list\n```\n\n---")).toBe("Run this:. odi list");
  });
});

describe("announcementText", () => {
  it("names the speaker for a reply", () => {
    expect(announcementText({ role: "assistant", content: "Ready." })).toBe(
      "Studio replied: Ready.",
    );
  });

  it("names notices", () => {
    expect(announcementText({ role: "notice", content: "**Studio status**" })).toBe(
      "Notice: Studio status",
    );
  });

  it("stays silent for the user's own turn and for empty prose", () => {
    expect(announcementText({ role: "user", content: "Hi" })).toBeNull();
    expect(announcementText({ role: "assistant", content: "" })).toBeNull();
  });

  it("never claims a reply for a turn the reader stopped", () => {
    expect(
      announcementText({ role: "assistant", content: "Here is what I have so", stopped: true }),
    ).toBe("Studio stopped early: Here is what I have so");
    expect(announcementText({ role: "assistant", content: "", stopped: true })).toBe(
      "Studio stopped before answering.",
    );
  });

  it("speaks for a turn that only posted a card", () => {
    expect(
      announcementText({
        role: "assistant",
        content: "",
        parts: [{ kind: "ui", id: "ui-1", node: {} as never }],
      }),
    ).toBe("Studio posted a card to the transcript.");
  });
});
