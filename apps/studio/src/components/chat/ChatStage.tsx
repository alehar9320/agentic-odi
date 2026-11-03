import { useState } from "react";

import { ThreadPrimitive, useThreadViewport } from "@assistant-ui/react";

import { isFeatureEnabled } from "../../features/flags";
import { arrivalAnnouncement, arrivalLabel, arrivedSince } from "./arrivalCount";
import {
  HELP_TEXT,
  IMPACT_PROMPT,
  STUDIO_COMMANDS,
  isSlashCommand,
  type StudioCommand,
} from "../../lib/commands";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { useStudio } from "../../state/StudioContext";
import type { WorkspacePanelId } from "../../types";
import { IntroConversation } from "../setup/IntroConversation";
import { SetupConversation } from "../setup/SetupConversation";
import { Conversation } from "./Conversation";
import { GuidanceHint } from "./GuidanceHint";
import { Hero } from "./Hero";
import { SelectionToolbar } from "./SelectionToolbar";
import { ThreadComposer } from "./ThreadComposer";

const VIEW_COMMANDS = new Set<string>([
  "records",
  "landscape",
  "jobmap",
  "segments",
  "evidence",
  "settings",
]);

/**
 * The one scroll control.
 *
 * assistant-ui owns the viewport: `ThreadPrimitive.Viewport autoScroll` follows
 * the bottom and stops when a person scrolls up, and `useThreadViewport` exposes
 * that as `isAtBottom`. This component only adds the signal the viewport lacks —
 * how much arrived while the reader was away — and the way back, so there is
 * still exactly one authority over `scrollTop`.
 *
 * `messageCount` counts messages, not tokens: the tail assistant message exists
 * from the first frame and only its content grows, so a long stream announces
 * once, not per delta.
 */
function LatestMessageButton({ messageCount }: { messageCount: number }) {
  const isAtBottom = useThreadViewport((state) => state.isAtBottom);
  const scrollToBottom = useThreadViewport((state) => state.scrollToBottom);
  // A reader who asked for less motion should land on the newest reply, not
  // watch the transcript animate past everything in between.
  const reducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");

  // The transcript length last seen from the bottom. It only advances while the
  // reader is at the bottom, so a scroll up freezes it and the difference is
  // what arrived in their absence. Adjusting it during render (not in an effect)
  // is React's documented pattern and keeps the count out of a second commit.
  const [seen, setSeen] = useState(messageCount);
  if (isAtBottom && seen !== messageCount) {
    setSeen(messageCount);
  }
  const arrived = isAtBottom ? 0 : arrivedSince(seen, messageCount);

  return (
    <>
      {!isAtBottom && (
        <button
          type="button"
          className="chat__latest"
          onClick={() => scrollToBottom({ behavior: reducedMotion ? "auto" : "smooth" })}
        >
          {arrivalLabel(arrived)}
        </button>
      )}
      {/* Always mounted, and updated only when the count changes, so a screen
          reader hears it once per arrival and never once per streamed token. */}
      <p className="sr-only" role="status" aria-live="polite" aria-label="New replies">
        {arrivalAnnouncement(arrived)}
      </p>
    </>
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
  } = useStudio();

  const empty = messages.length === 0;

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
    return isFeatureEnabled("firstRunIntro") ? <IntroConversation /> : <SetupConversation />;
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
      {/* Outside the viewport, so the toolbar is never clipped by the scroll
          frame; absent on the empty stage because there is nothing to quote. */}
      <SelectionToolbar />
      <div className="chat__transcript">
        <ThreadPrimitive.Viewport className="chat__scroll" autoScroll>
          <div className="chat__thread">
            <Conversation />
          </div>
        </ThreadPrimitive.Viewport>
        <LatestMessageButton messageCount={messages.length} />
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
