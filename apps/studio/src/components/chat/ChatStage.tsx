import { ThreadPrimitive, useAui, useThreadViewport } from "@assistant-ui/react";
import { useRef } from "react";

import { attachmentText } from "../../assistant/attachments";
import { asStudioError } from "../../api/studioApi";
import {
  HELP_TEXT,
  IMPACT_PROMPT,
  STUDIO_COMMANDS,
  isSlashCommand,
  planInterview,
  type StudioCommand,
  type TranscriptFile,
} from "../../lib/commands";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { useStudio } from "../../state/StudioContext";
import type { WorkspacePanelId } from "../../types";
import { SetupConversation } from "../setup/SetupConversation";
import { Conversation } from "./Conversation";
import { GuidanceHint } from "./GuidanceHint";
import { Hero } from "./Hero";
import { ThreadComposer } from "./ThreadComposer";

const VIEW_COMMANDS = new Set<string>(["landscape", "jobmap", "coverage", "evidence", "settings"]);

function LatestMessageButton() {
  const isAtBottom = useThreadViewport((state) => state.isAtBottom);
  const scrollToBottom = useThreadViewport((state) => state.scrollToBottom);
  // A reader who asked for less motion should land on the newest reply, not
  // watch the transcript animate past everything in between.
  const reducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");

  if (isAtBottom) {
    return null;
  }

  return (
    <button
      type="button"
      className="chat__latest"
      onClick={() => scrollToBottom({ behavior: reducedMotion ? "auto" : "smooth" })}
    >
      Latest message
    </button>
  );
}

export function ChatStage() {
  const {
    messages,
    sendMessage,
    pushNotice,
    openPanel,
    closePanel,
    clearChat,
    openSetup,
    setupOpen,
    canvas,
    brief,
    settings,
    mcpReachable,
    llmHealth,
    importInterview,
  } = useStudio();
  const aui = useAui();
  // Guards a double-run: a second `/interview` while the first is in flight
  // would import the same transcript twice.
  const importing = useRef(false);

  const empty = messages.length === 0;

  async function importFromComposer() {
    if (importing.current) {
      return;
    }
    const attachments = aui.composer.getState().attachments;
    const files: TranscriptFile[] = await Promise.all(
      attachments.map(async (attachment) => ({
        name: attachment.name,
        contentType: attachment.contentType,
        text: attachment.file ? await attachmentText(attachment.file).catch(() => undefined) : undefined,
      })),
    );
    const plan = planInterview(files);
    if (plan.kind === "refuse") {
      pushNotice(plan.reason);
      return;
    }

    const [attachment] = attachments;
    const [file] = files;
    importing.current = true;
    pushNotice(`Importing **${attachment.name}**…`);
    try {
      const result = await importInterview({
        text: file.text ?? "",
        title: plan.title,
        participant: "Participant",
        ...(plan.format ? { format: plan.format } : {}),
        filename: attachment.name,
        ...(brief?.job_id ? { job_id: brief.job_id } : {}),
      });
      await aui.composer.clearAttachments();
      pushNotice(
        `Imported **${result.interview.title}** as an interview with ` +
          `${result.quote_count} quote${result.quote_count === 1 ? "" : "s"}.`,
      );
    } catch (error) {
      // The importer's refusal names the file and the reason; show it as-is
      // rather than a generic failure.
      pushNotice(`Could not import **${attachment.name}**: ${asStudioError(error).message}`);
    } finally {
      importing.current = false;
    }
  }

  function runCommand(command: StudioCommand) {
    if (VIEW_COMMANDS.has(command.id)) {
      openPanel(command.id as WorkspacePanelId);
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
        openPanel("jobmap");
        return;
      }
      case "impact":
        void sendMessage(IMPACT_PROMPT);
        return;
      case "interview":
        // The transcript goes to the importer, never to the model: this is the
        // one command that writes without a chat turn.
        void importFromComposer();
        return;
      case "capture":
        // With a model, capture is a sentence. Without one, the offline form
        // is the only honest path that still writes to the repository.
        if (llmHealth.healthy === false) {
          openPanel("capture");
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
  }

  function submitCommand(text: string) {
    if (!isSlashCommand(text)) {
      return false;
    }
    const token = text.split(/\s+/)[0].toLowerCase();
    const command = STUDIO_COMMANDS.find((entry) => entry.name === token);
    if (command) {
      runCommand(command);
    } else {
      pushNotice(`Unknown command: \`${token}\`. Type \`/help\` for the full list.`);
    }
    return true;
  }

  if (setupOpen) {
    return <SetupConversation />;
  }

  if (empty) {
    return (
      <section className="chat chat--empty" aria-label="Studio conversation">
        <div className="chat__welcome">
          <div className="chat__welcome-inner">
            <Hero />
            <ThreadComposer
              onCommand={(command) => runCommand(command)}
              onSlashCommand={submitCommand}
              autoFocus
            />
          </div>
        </div>
      </section>
    );
  }

  return (
    <ThreadPrimitive.Root className="chat" aria-label="Studio conversation">
      <div className="chat__transcript">
        <ThreadPrimitive.Viewport className="chat__scroll" autoScroll>
          <div className="chat__thread">
            <Conversation />
          </div>
        </ThreadPrimitive.Viewport>
        <LatestMessageButton />
      </div>
      <div className="chat__dock">
        <GuidanceHint />
        <ThreadComposer
          onCommand={(command) => runCommand(command)}
          onSlashCommand={submitCommand}
        />
      </div>
    </ThreadPrimitive.Root>
  );
}
