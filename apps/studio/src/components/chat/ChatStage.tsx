import { useEffect, useRef, useState } from "react";

import {
  attachmentProblem,
  readAttachment,
  releaseAttachment,
  toPayload,
  type StagedAttachment,
} from "../../lib/attachments";
import {
  HELP_TEXT,
  IMPACT_PROMPT,
  STUDIO_COMMANDS,
  isSlashCommand,
  type StudioCommand,
} from "../../lib/commands";
import { announcementText } from "../../lib/transcript";
import { useStudio } from "../../state/StudioContext";
import type { ChatMessage, WorkspacePanelId } from "../../types";
import { ArrowDownIcon } from "../icons";
import { SetupConversation } from "../setup/SetupConversation";
import { Composer } from "./Composer";
import { Conversation } from "./Conversation";
import { Hero } from "./Hero";
import { OfflineNotice } from "./OfflineNotice";
import { TranscriptAnnouncer, type Announcement } from "./TranscriptAnnouncer";

const VIEW_COMMANDS = new Set<string>(["landscape", "jobmap", "evidence", "settings"]);

/** How close to the bottom still counts as reading the newest turn. */
const PIN_THRESHOLD_PX = 96;

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
  const [attachments, setAttachments] = useState<StagedAttachment[]>([]);
  const [attachError, setAttachError] = useState<string | null>(null);
  const [atBottom, setAtBottom] = useState(true);
  const [announcement, setAnnouncement] = useState<Announcement | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const refocus = useRef(false);
  // Seeded with the turn already on screen so remounting the stage (for
  // example after setup) does not read the last reply again.
  const announcedTurn = useRef<ChatMessage | null>(messages[messages.length - 1] ?? null);
  const announcementToken = useRef(0);

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

  /**
   * Stage the files the reader handed over: read only what the model can read,
   * and say why anything else was refused instead of attaching a filename.
   */
  async function attachFiles(files: File[]) {
    const accepted: StagedAttachment[] = [];
    const problems: string[] = [];
    let staged = attachments.length;

    for (const file of files) {
      const problem = attachmentProblem(file, staged);
      if (problem) {
        problems.push(problem);
        continue;
      }
      try {
        accepted.push(await readAttachment(file));
        staged += 1;
      } catch (error) {
        problems.push((error as Error).message);
      }
    }

    if (accepted.length) {
      setAttachments((current) => [...current, ...accepted]);
    }
    setAttachError(problems[0] ?? null);
  }

  function removeAttachment(id: string) {
    setAttachments((current) => {
      const leaving = current.find((attachment) => attachment.id === id);
      if (leaving) {
        releaseAttachment(leaving);
      }
      return current.filter((attachment) => attachment.id !== id);
    });
    setAttachError(null);
  }

  function submit(text?: string) {
    const value = (text ?? draft).trim();
    if ((!value && !attachments.length) || streaming) {
      return;
    }
    if (text === undefined) {
      setDraft("");
    }
    setAtBottom(true);
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

    const files = attachments.map(toPayload);
    attachments.forEach(releaseAttachment);
    setAttachments([]);
    setAttachError(null);
    void sendMessage(value, files);
  }

  // Keep the transcript pinned to the newest token unless the reader scrolled
  // up. Scrolling up is a reading decision, not an accident: it is honoured
  // until they come back with the jump control or their own scroll.
  useEffect(() => {
    if (!atBottom) {
      return;
    }
    const element = scrollRef.current;
    if (element) {
      element.scrollTop = element.scrollHeight;
    }
  }, [messages, streaming, atBottom]);

  // Announce a turn once it settles. Token-by-token announcements are noise,
  // and the message object only changes when the turn itself changes, so a
  // repeated reply is still spoken.
  useEffect(() => {
    if (streaming) {
      return;
    }
    const last = messages[messages.length - 1];
    if (!last || last === announcedTurn.current) {
      return;
    }
    const text = announcementText(last);
    if (!text) {
      return;
    }
    announcedTurn.current = last;
    announcementToken.current += 1;
    setAnnouncement({ token: announcementToken.current, text });
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
              attachments={attachments}
              onAttachFiles={(files) => void attachFiles(files)}
              onRemoveAttachment={removeAttachment}
              attachmentError={attachError}
            />
          </div>
        </div>
      </section>
    );
  }

  function jumpToLatest() {
    const element = scrollRef.current;
    setAtBottom(true);
    if (!element) {
      return;
    }
    element.scrollTop = element.scrollHeight;
    // The control unmounts as soon as we are back at the bottom; land focus on
    // the transcript itself rather than dropping it on the document.
    element.focus({ preventScroll: true });
  }

  return (
    <section className="chat" aria-label="Studio conversation">
      <OfflineNotice />
      <TranscriptAnnouncer announcement={announcement} />
      {/*
        A focusable log so keyboard readers can scroll history. `aria-live` is
        deliberately off: the announcer speaks each settled turn once, where a
        live log would read every streamed token and re-read re-rendered
        Markdown.
      */}
      <div
        ref={scrollRef}
        className="chat__scroll"
        tabIndex={0}
        role="log"
        aria-label="Conversation transcript"
        aria-live="off"
        aria-busy={streaming}
        onScroll={(event) => {
          const element = event.currentTarget;
          setAtBottom(
            element.scrollHeight - element.scrollTop - element.clientHeight < PIN_THRESHOLD_PX,
          );
        }}
      >
        <div className="chat__thread">
          <Conversation />
        </div>
      </div>
      <div className="chat__dock">
        {!atBottom && messages.length > 0 ? (
          <div className="chat__jump">
            <button type="button" className="chat__jump-button" onClick={jumpToLatest}>
              <ArrowDownIcon size={14} />
              Jump to latest
            </button>
          </div>
        ) : null}
        <Composer
          value={draft}
          onChange={setDraft}
          onSubmit={submit}
          onCommand={runCommand}
          streaming={streaming}
          onStop={stopStreaming}
          inputRef={inputRef}
          attachments={attachments}
          onAttachFiles={(files) => void attachFiles(files)}
          onRemoveAttachment={removeAttachment}
          attachmentError={attachError}
        />
      </div>
    </section>
  );
}
