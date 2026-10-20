/**
 * Slash commands give the keyboard the reach the drawer has.
 *
 * The Studio handles these locally: a command never costs a model round trip,
 * which is what keeps the surface usable when the model is offline.
 */

import type { WorkspacePanelId } from "../types";

export type CommandId =
  | "help"
  | "new"
  | "home"
  | "jobs"
  | "start"
  | "status"
  | WorkspacePanelId;

export interface StudioCommand {
  id: CommandId;
  /** The typed form, including the slash. */
  name: string;
  label: string;
  description: string;
  keywords?: string[];
}

export const STUDIO_COMMANDS: StudioCommand[] = [
  {
    id: "help",
    name: "/help",
    label: "Help",
    description: "Every command, and what the studio can do by hand.",
    keywords: ["commands", "?"],
  },
  {
    id: "start",
    name: "/start",
    label: "Set your context",
    description: "Product, audience, job, and the problem you are chasing.",
    keywords: ["onboarding", "context", "brief", "setup"],
  },
  {
    id: "new",
    name: "/new",
    label: "New conversation",
    description: "Clear the transcript and start again.",
    keywords: ["clear", "reset"],
  },
  {
    id: "home",
    name: "/home",
    label: "Go home",
    description: "Return to the empty stage.",
    keywords: ["welcome"],
  },
  {
    id: "jobs",
    name: "/jobs",
    label: "Jobs",
    description: "What the studio knows about, then open the job map.",
    keywords: ["summary", "list"],
  },
  {
    id: "landscape",
    name: "/landscape",
    label: "Opportunity landscape",
    description: "Every outcome scored; anything above 10 is underserved.",
    keywords: ["outcomes", "scores", "opportunity"],
  },
  {
    id: "jobmap",
    name: "/jobmap",
    label: "Job map",
    description: "The eight phases, and the steps already captured.",
    keywords: ["steps", "phases"],
  },
  {
    id: "impact",
    name: "/impact",
    label: "Impact simulation",
    description: "Preview the friction collapse for a bet.",
    keywords: ["simulate", "bet"],
  },
  {
    id: "evidence",
    name: "/evidence",
    label: "Evidence",
    description: "The customer signals behind each outcome.",
    keywords: ["signals", "quotes"],
  },
  {
    id: "capture",
    name: "/capture",
    label: "Capture an outcome",
    description: "Record an outcome by hand, with scores.",
    keywords: ["add", "outcome", "manual"],
  },
  {
    id: "settings",
    name: "/settings",
    label: "Settings",
    description: "Point the studio at a model and an MCP server.",
    keywords: ["model", "mcp", "connection"],
  },
  {
    id: "status",
    name: "/status",
    label: "Status",
    description: "Model, MCP, context, and canvas at a glance.",
    keywords: ["connection", "health"],
  },
];

export const HELP_TEXT = [
  "**Commands** — handled here, with or without a model:",
  "",
  ...STUDIO_COMMANDS.map((command) => `- \`${command.name}\` — ${command.description}`),
  "",
  "Anything else is a message to the model. Type `/` to open the palette.",
].join("\n");

/** True while the draft is a bare command (no arguments typed yet). */
export function isCommandDraft(draft: string): boolean {
  return draft.startsWith("/") && !/\s/.test(draft);
}

export function isSlashCommand(text: string): boolean {
  return text.trim().startsWith("/");
}

/**
 * Rank matches: an exact command first, then names that start with the query,
 * then any keyword/description hit. Declared order breaks ties.
 */
export function matchCommands(draft: string): StudioCommand[] {
  const query = draft.trim().replace(/^\//, "").toLowerCase();
  if (!query) {
    return STUDIO_COMMANDS;
  }

  const scored = STUDIO_COMMANDS.map((command, index) => {
    const name = command.name.slice(1).toLowerCase();
    const haystack = [name, command.label, command.description, ...(command.keywords ?? [])]
      .join(" ")
      .toLowerCase();
    let score = -1;
    if (name === query) {
      score = 0;
    } else if (name.startsWith(query)) {
      score = 1;
    } else if (haystack.includes(query)) {
      score = 2;
    }
    return { command, index, score };
  }).filter((entry) => entry.score >= 0);

  scored.sort((a, b) => a.score - b.score || a.index - b.index);
  return scored.map((entry) => entry.command);
}
