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
  | "impact"
  | "interview"
  | WorkspacePanelId;

export interface StudioCommand {
  id: CommandId;
  /** The typed form, including the slash. */
  name: string;
  label: string;
  description: string;
  /** The palette groups commands under this heading. */
  category: string;
  keywords?: string[];
}

/**
 * The first thing the studio says when a simulation is asked for. Shared by
 * the `/impact` command and the first-run tour so both open the same
 * conversation.
 */
export const IMPACT_PROMPT =
  "Simulate the impact of a bet on my most underserved opportunity. " +
  "Ask me what the bet is, then show me what changes before and after.";

export const STUDIO_COMMANDS: StudioCommand[] = [
  {
    id: "help",
    name: "/help",
    label: "Help",
    description: "Every command, and what the studio can do by hand.",
    category: "Start",
    keywords: ["commands", "?"],
  },
  {
    id: "start",
    name: "/start",
    label: "Set your context",
    description: "Product, audience, job, and the problem you are chasing.",
    category: "Start",
    keywords: ["onboarding", "context", "brief", "setup"],
  },
  {
    id: "new",
    name: "/new",
    label: "New conversation",
    description: "Clear the transcript and start again.",
    category: "Start",
    keywords: ["clear", "reset"],
  },
  {
    id: "home",
    name: "/home",
    label: "Go home",
    description: "Return to the empty stage.",
    category: "Start",
    keywords: ["welcome"],
  },
  {
    id: "jobs",
    name: "/jobs",
    label: "Jobs",
    description: "What the studio knows about, then open the job map.",
    category: "Explore",
    keywords: ["summary", "list"],
  },
  {
    id: "landscape",
    name: "/landscape",
    label: "Opportunity landscape",
    description: "Every outcome scored; anything above 10 is underserved.",
    category: "Explore",
    keywords: ["outcomes", "scores", "opportunity"],
  },
  {
    id: "jobmap",
    name: "/jobmap",
    label: "Job map",
    description: "The eight phases, and the steps already captured.",
    category: "Explore",
    keywords: ["steps", "phases"],
  },
  {
    id: "coverage",
    name: "/coverage",
    label: "Coverage",
    description: "What the research covers, stage by stage, and the gaps it leaves.",
    category: "Explore",
    keywords: ["gaps", "stages", "measured"],
  },
  {
    id: "impact",
    name: "/impact",
    label: "Simulate a bet",
    description: "Ask the studio to simulate what a bet would change.",
    category: "Act",
    keywords: ["simulate", "bet"],
  },
  {
    id: "interview",
    name: "/interview",
    label: "Import a transcript",
    description: "Turn an attached transcript into an interview and its quotes.",
    category: "Act",
    keywords: ["transcript", "import", "interview", "quotes", "vtt", "srt"],
  },
  {
    id: "evidence",
    name: "/evidence",
    label: "Evidence",
    description: "The customer signals behind each outcome.",
    category: "Explore",
    keywords: ["signals", "quotes"],
  },
  {
    id: "capture",
    name: "/capture",
    label: "Capture an outcome",
    description: "Tell the studio what you heard. Falls back to the offline form.",
    category: "Act",
    keywords: ["add", "outcome", "manual"],
  },
  {
    id: "settings",
    name: "/settings",
    label: "Settings",
    description: "Point the studio at a model and an MCP server.",
    category: "Studio",
    keywords: ["model", "mcp", "connection"],
  },
  {
    id: "status",
    name: "/status",
    label: "Status",
    description: "Model, MCP, context, and canvas at a glance.",
    category: "Studio",
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

/** The transcript formats the shared importer accepts, by extension. */
export const TRANSCRIPT_EXTENSIONS = ["md", "mdx", "txt", "vtt", "srt"] as const;

/** One composer attachment, reduced to what the import decision needs. */
export interface TranscriptFile {
  name: string;
  contentType?: string;
  /** The file's text, read in the browser; absent when it could not be read. */
  text?: string;
}

/**
 * What `/interview` should do with the composer's attachments.
 *
 * The import decision is pure so it can be tested without a composer: a
 * transcript is one readable text file, and anything else — none, several, an
 * image, or a file whose text could not be read — is refused with the reason
 * the thread shows beside the filename.
 */
export type InterviewPlan =
  | { kind: "import"; title: string; format?: string }
  | { kind: "refuse"; reason: string };

/** The importer format for a filename, or undefined to let the importer detect it. */
export function transcriptFormatFor(filename: string): string | undefined {
  const suffix = filename.split(".").pop()?.toLowerCase() ?? "";
  return (TRANSCRIPT_EXTENSIONS as readonly string[]).includes(suffix) ? suffix : undefined;
}

/** A short, human title for an imported transcript, derived from its filename. */
export function transcriptTitleFor(filename: string): string {
  const stem = filename.replace(/\.[^./\\]+$/, "").trim();
  return stem || "Attached transcript";
}

export function planInterview(attachments: readonly TranscriptFile[]): InterviewPlan {
  if (attachments.length === 0) {
    return { kind: "refuse", reason: "Attach a transcript first, then run `/interview`." };
  }
  if (attachments.length > 1) {
    return {
      kind: "refuse",
      reason: `Attach one transcript at a time — ${attachments.length} files are attached.`,
    };
  }
  const [attachment] = attachments;
  if (attachment.contentType?.startsWith("image/")) {
    return { kind: "refuse", reason: `${attachment.name} is an image, not a transcript.` };
  }
  if (attachment.text === undefined) {
    return {
      kind: "refuse",
      reason: `${attachment.name} could not be read as text. Attach a .md, .txt, .vtt, or .srt file.`,
    };
  }
  return {
    kind: "import",
    title: transcriptTitleFor(attachment.name),
    format: transcriptFormatFor(attachment.name),
  };
}

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
