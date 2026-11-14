/**
 * Guards for the mainstage stylesheet (#737).
 *
 * A stylesheet that is never imported styles nothing, and a class renamed in a
 * component but not in the CSS loses its styling silently. Neither shows up in
 * a component test, so both are checked against the source text — the same way
 * the brief lens guards its own sheet.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import mainstageCss from "./mainstage.css?raw";

// Vitest runs with the studio package as its working directory.
const entry = readFileSync(join(process.cwd(), "src/main.tsx"), "utf8");
const chatStage = readFileSync(
  join(process.cwd(), "src/components/chat/ChatStage.tsx"),
  "utf8",
);
const conversation = readFileSync(
  join(process.cwd(), "src/components/chat/Conversation.tsx"),
  "utf8",
);

/** The classes this sheet owns, read from the components that render them. */
function classesUsedIn(source: string): string[] {
  const names = new Set<string>();
  for (const match of source.matchAll(/\bmainstage__[a-z-]+/g)) {
    names.add(match[0]);
  }
  for (const match of source.matchAll(/\bmessage__(?:byline|column--user|avatar--user)\b/g)) {
    names.add(match[0]);
  }
  return [...names];
}

describe("mainstage stylesheet", () => {
  it("is loaded by the studio entry", () => {
    expect(entry).toContain('"./styles/mainstage.css"');
  });

  it("defines a rule for every class the bar and turn anatomy render", () => {
    const used = [...classesUsedIn(chatStage), ...classesUsedIn(conversation)];
    expect(used.length).toBeGreaterThan(0);
    expect(used.filter((name) => !mainstageCss.includes(`.${name}`))).toEqual([]);
  });
});
