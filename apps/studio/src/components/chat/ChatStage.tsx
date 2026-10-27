import { useEffect, useRef, useState } from "react";

import {
  HELP_TEXT,
  IMPACT_PROMPT,
  STUDIO_COMMANDS,
  isSlashCommand,
  type StudioCommand,
} from "../../lib/commands";
import { useStudio } from "../../state/StudioContext";
import type { WorkspacePanelId } from "../../types";
import { SetupConversation } from "../setup/SetupConversation";
import { Composer } from "./Composer";
import { Conversation } from "./Conversation";
import { Hero } from "./Hero";
import { OfflineNotice } from "./OfflineNotice";

const VIEW_COMMANDS = new Set<string>(["landscape", "jobmap", "evidence", "settings"]);

export function ChatStage() {
  const {
    messages,
    streaming,
    sendMessage,
    stopStreaming,
    openPanel,
    closePanel,
    clearChat,
    pushNotice,
    openSetup,
    setupOpen,
    canvas,
    brief,
    settings,
    mcpReachable,
    llmHealth,
  } = useStudio();
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const pinned = useRef(true);
  const refocus = useRef(false);

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

  function submit(text?: string) {
    const value = (text ?? draft).trim();
    if (!value || streaming) {
      return;
    }
    if (text === undefined) {
      setDraft("");
    }
    pinned.current = true;
    refocus.current = true;

    if (isSlashCommand(value)) {
      const token = value.split(/\s+/)[0].toLowerCase();
      const command = STUDIO_COMMANDS.find((entry) => entry.name === token);
      if (command) {
        runCommand(command);
      } else {
        pushNotice(`Unknown command: \`${token}\`. Type \`/help\` for the full list.`);
      }
      return;
    }

    void sendMessage(value);
  }

  // Keep the transcript pinned to the newest token unless the reader scrolled up.
  useEffect(() => {
    if (!pinned.current) {
      return;
    }
    const element = scrollRef.current;
    if (element) {
      element.scrollTop = element.scrollHeight;
    }
  }, [messages, streaming]);

  // The composer moves from the hero into the dock when the conversation starts.
  useEffect(() => {
    if (!empty && refocus.current) {
      refocus.current = false;
      inputRef.current?.focus();
    }
  }, [empty]);

  if (setupOpen) {
    return <SetupConversation />;
  }

  if (empty) {
    return (
      <section className="chat chat--empty" aria-label="Studio conversation">
        <OfflineNotice />
        <div className="chat__welcome">
          <div className="chat__welcome-inner">
            <Hero onSubmit={submit} />
            <Composer
              value={draft}
              onChange={setDraft}
              onSubmit={submit}
              onCommand={runCommand}
              streaming={streaming}
              onStop={stopStreaming}
              inputRef={inputRef}
              autoFocus
            />
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="chat" aria-label="Studio conversation">
      <OfflineNotice />
      <div
        ref={scrollRef}
        className="chat__scroll"
        onScroll={(event) => {
          const element = event.currentTarget;
          pinned.current =
            element.scrollHeight - element.scrollTop - element.clientHeight < 96;
        }}
      >
        <div className="chat__thread">
          <Conversation />
        </div>
      </div>
      <div className="chat__dock">
        <Composer
          value={draft}
          onChange={setDraft}
          onSubmit={submit}
          onCommand={runCommand}
          streaming={streaming}
          onStop={stopStreaming}
          inputRef={inputRef}
        />
      </div>
    </section>
  );
}
