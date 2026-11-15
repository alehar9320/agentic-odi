import { useState } from "react";

import { useThreadViewport } from "@assistant-ui/react";

import { isFeatureEnabled } from "../../features/flags";
import { canvasStatus } from "../../lib/canvasProvenance";
import { arrivalAnnouncement, arrivalLabel, arrivedSince } from "./arrivalCount";
import { STUDIO_COMMANDS, isSlashCommand } from "../../lib/commands";
import { useReducedMotion } from "../../lib/useReducedMotion";
import { useStudioCommands } from "../../lib/useStudioCommands";
import { useStudio } from "../../state/StudioContext";
import { IntroConversation } from "../setup/IntroConversation";
import { SetupConversation } from "../setup/SetupConversation";
import { ThreadElement } from "../../vendor/components/assistant/thread";
import { Conversation } from "./Conversation";
import { GuidanceHint } from "./GuidanceHint";
import { Hero } from "./Hero";
import { SelectionToolbar } from "./SelectionToolbar";
import { ThreadComposer } from "./ThreadComposer";

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
  const reducedMotion = useReducedMotion();

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
  const { messages, pushNotice, setupOpen, canvas, brief } = useStudio();
  const runCommand = useStudioCommands();

  const empty = messages.length === 0;
  // The provenance chip the rail already shows, reused here so the inquiry's
  // own bar says whether the board it describes is real or a sample (#737).
  const provenance = canvasStatus(canvas);

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

  const composer = (autoFocus = false) => (
    <ThreadComposer
      onCommand={(command) => runCommand(command)}
      onSlashCommand={submitCommand}
      {...(autoFocus ? { autoFocus: true } : {})}
    />
  );

  // One assistant-ui thread frame for both states: the Element owns the root,
  // the viewport, and the footer the composer docks into, so an empty stage and
  // a running thread share the same layout instead of two hand-built ones.
  if (empty) {
    return (
      <ThreadElement
        empty
        className="chat--empty"
        aria-label="Studio conversation"
        welcome={
          <>
            <Hero />
            {composer(true)}
          </>
        }
        composer={null}
      />
    );
  }

  return (
    <ThreadElement
      aria-label="Studio conversation"
      header={
        <>
          {/* Outside the viewport, so the toolbar is never clipped by the scroll
              frame; absent on the empty stage because there is nothing to quote. */}
          <SelectionToolbar />
          <header className="mainstage__bar">
            <h2 className="mainstage__title">
              {brief?.product_name || brief?.job_statement || "This conversation"}
            </h2>
            {provenance ? (
              <span
                className={`mainstage__provenance${provenance.label === "OFFLINE" ? " is-offline" : ""}`}
                title={provenance.detail}
              >
                {provenance.label}
              </span>
            ) : null}
          </header>
        </>
      }
      messages={<Conversation />}
      float={<LatestMessageButton messageCount={messages.length} />}
      composer={
        <>
          <GuidanceHint />
          {composer()}
        </>
      }
    />
  );
}
