import { useCallback } from "react";

import { useStudio } from "../state/StudioContext";
import type { WorkspacePanelId } from "../types";
import { HELP_TEXT, IMPACT_PROMPT, type StudioCommand } from "./commands";

/**
 * The Studio's slash commands, in one place.
 *
 * They were a function inside `ChatStage`. Quick jump needs the same meanings,
 * so the function moved here rather than being copied — a second copy is how
 * `/capture` would drift from the sheet's row of the same name.
 */

export const VIEW_COMMANDS = new Set<string>([
  "records",
  "landscape",
  "brief",
  "jobmap",
  "segments",
  "evidence",
  "settings",
]);

export function useStudioCommands(): (command: StudioCommand) => void {
  const {
    sendMessage,
    pushNotice,
    openDetail,
    closePanel,
    clearChat,
    openSetup,
    canvas,
    brief,
    settings,
    mcpReachable,
    llmHealth,
  } = useStudio();

  return useCallback(
    (command: StudioCommand) => {
      if (VIEW_COMMANDS.has(command.id)) {
        // `openDetail` is the single entry to the right region (#735).
        openDetail(command.id as WorkspacePanelId);
        return;
      }
      switch (command.id) {
        case "help":
          pushNotice(HELP_TEXT);
          return;
        case "new":
        case "home":
          clearChat();
          closePanel();
          return;
        case "start":
          openSetup();
          return;
        case "jobs": {
          const jobs = canvas?.jobs ?? [];
          const lines = jobs.length
            ? jobs.map((job) => `- **${job.id}** — ${job.name ?? "Untitled job"}`)
            : ["- Nothing captured yet. Use `/start` to name the job."];
          pushNotice(
            [
              `**${jobs.length} job${jobs.length === 1 ? "" : "s"} on the canvas**`,
              ...lines,
              "",
              brief?.job_statement ? `Working job: ${brief.job_statement}` : "",
            ]
              .filter(Boolean)
              .join("\n"),
          );
          openDetail("jobmap");
          return;
        }
        case "impact":
          void sendMessage(IMPACT_PROMPT);
          return;
        case "capture":
          // With a model, capture is a sentence. Without one, the offline form
          // is the only honest path that still writes to the repository.
          if (llmHealth.healthy === false) {
            openDetail("capture");
            return;
          }
          void sendMessage(
            "I want to capture an outcome I heard from a customer. Ask me what they said.",
          );
          return;
        case "status":
          pushNotice(
            [
              "**Studio status**",
              `- Model: ${settings.model_name} at ${settings.base_url} — ${
                llmHealth.healthy === null
                  ? "checking"
                  : llmHealth.healthy
                    ? "reachable"
                    : "offline"
              }`,
              `- MCP: ${mcpReachable ? "connected" : "offline"} (${settings.mcp_url})`,
              `- Context: ${
                brief ? `${brief.product_name || "named job"} — ${brief.job_statement}` : "not set"
              }`,
              `- Canvas: ${canvas?.jobs.length ?? 0} jobs, ${canvas?.outcomes.length ?? 0} outcomes`,
            ].join("\n"),
          );
          return;
        default:
          return;
      }
    },
    [
      brief,
      canvas,
      clearChat,
      closePanel,
      llmHealth,
      mcpReachable,
      openDetail,
      openSetup,
      pushNotice,
      sendMessage,
      settings,
    ],
  );
}
