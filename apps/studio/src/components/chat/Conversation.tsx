/**
 * The transcript.
 *
 * assistant-ui owns the message list, the message parts, and the branch picker;
 * this file decides what each of those looks like in the Studio. Everything it
 * renders comes from one place — `assistant/convert.ts` — so a new part type is
 * added in exactly two files.
 */

import { createContext, useContext, useMemo } from "react";

import {
  ActionBarPrimitive,
  AuiIf,
  BranchPickerPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAuiState,
} from "@assistant-ui/react";

import { formatFileSize, preparedAttachmentById } from "../../assistant/attachments";
import { CLAIMS_PART, SURFACE_PART } from "../../assistant/convert";
import {
  AssistantAvatar,
  ClaimsPart,
  FilePart,
  ReasoningPart,
  SourcePart,
  SurfacePart,
  TextPart,
  ToolPart,
  TypingPart,
} from "../../assistant/parts";
import { formatClockTime, formatDayHeading, startsNewDay } from "../../lib/relativeTime";
import { useStudio } from "../../state/StudioContext";
import type { ChatMessage, StudioError } from "../../types";
import { UiActionContext } from "../../ui/actions";
import { FailurePanel } from "../FailurePanel";
import { CheckIcon, CopyIcon } from "../icons";
import { Markdown } from "./Markdown";
import { StallNotice } from "./StallNotice";

const PHASE_LABEL: Record<string, string> = {
  health_check: "Waking the model",
  mcp_tools: "Opening your studio tools",
  model: "Thinking",
};

function phaseLabel(phase: string | null): string {
  if (!phase) {
    return "Thinking";
  }
  return PHASE_LABEL[phase] ?? "Thinking";
}

/**
 * Where each turn sits in the studio's own list, so a message can read its own
 * timestamp and the one before it. The runtime draws the turns but keeps no
 * clock of its own; the model that does is the one the transcript came from.
 */
const TranscriptClockContext = createContext<{
  order: Map<string, number>;
  messages: ChatMessage[];
} | null>(null);

interface MessageStamp {
  iso: string;
  clock: string;
  previousIso?: string;
}

function useMessageStamp(): MessageStamp | null {
  const transcript = useContext(TranscriptClockContext);
  const id = useAuiState((state) => state.message.id);
  const index = transcript?.order.get(id);
  if (!transcript || index === undefined) {
    return null;
  }
  const iso = transcript.messages[index]?.createdAt;
  if (!iso) {
    return null;
  }
  return { iso, clock: formatClockTime(iso), previousIso: transcript.messages[index - 1]?.createdAt };
}

/**
 * The line between two calendar days: Today and Yesterday are said in words,
 * anything older is dated. Only drawn where the day actually changes.
 */
function DayDivider() {
  const stamp = useMessageStamp();
  if (!stamp || !startsNewDay(stamp.iso, stamp.previousIso)) {
    return null;
  }
  const heading = formatDayHeading(stamp.iso);
  return (
    <div className="conversation__day" role="separator" aria-label={heading}>
      {heading}
    </div>
  );
}

function AssistantMessage() {
  const { thinkingPhase, offlineReplyFor, sendMessage, openPanel } = useStudio();
  const id = useAuiState((state) => state.message.id);
  const stamp = useMessageStamp();
  const running = useAuiState((state) => state.message.status?.type === "running");
  const copied = useAuiState((state) => state.message.isCopied);
  const hasText = useAuiState((state) =>
    state.message.content.some((part) => part.type === "text" && part.text.trim().length > 0),
  );
  const error = useAuiState(
    (state) => state.message.metadata.custom?.error as StudioError | undefined,
  );
  const retryText = useAuiState(
    (state) => state.message.metadata.custom?.retryText as string | undefined,
  );

  return (
    <>
      <DayDivider />
      {/* `aria-busy` keeps a screen reader from announcing every streamed token;
          it reads the reply once the turn settles. */}
      <article className="message message--assistant" aria-busy={running}>
      <AssistantAvatar />
      <div className="message__body">
        {/* Named on the reply it describes, never on every reply on screen, and
            said once instead of warned about in a strip above the work. */}
        {offlineReplyFor === id ? (
          <button
            type="button"
            className="message__tag"
            onClick={() => openPanel("settings")}
          >
            Local draft, no model connected
          </button>
        ) : null}

        <MessagePrimitive.Parts
          components={{
            Text: TextPart,
            Reasoning: ReasoningPart,
            Source: SourcePart,
            File: FilePart,
            data: { by_name: { [SURFACE_PART]: SurfacePart, [CLAIMS_PART]: ClaimsPart } },
            tools: { Fallback: ToolPart },
          }}
        />

        {running && !hasText ? <TypingPart label={phaseLabel(thinkingPhase)} /> : null}
        {running && hasText ? <span className="caret" aria-hidden="true" /> : null}

        {/* Silence is not failure: a long tool call gets one honest line, and
            a dropped run falls through to the failure panel instead. */}
        <StallNotice />

        {error ? (
          <FailurePanel
            error={error}
            retryText={retryText}
            onRetry={(text) => void sendMessage(text)}
          />
        ) : null}

        <AuiIf condition={(state) => state.message.branchCount > 1}>
          {/* The group carries the name. Putting an aria-label on the position
              text instead would replace "2 of 2" for screen readers with the
              label, hiding the one thing the control exists to state. */}
          <BranchPickerPrimitive.Root
            className="branch-picker"
            role="group"
            aria-label="Reply alternatives"
          >
            <BranchPickerPrimitive.Previous
              className="branch-picker__step"
              aria-label="Previous alternative"
            >
              ‹
            </BranchPickerPrimitive.Previous>
            <span className="branch-picker__label">
              Alternative <BranchPickerPrimitive.Number /> of <BranchPickerPrimitive.Count />
            </span>
            <BranchPickerPrimitive.Next
              className="branch-picker__step"
              aria-label="Next alternative"
            >
              ›
            </BranchPickerPrimitive.Next>
          </BranchPickerPrimitive.Root>
        </AuiIf>

        {!running ? (
          // The exact time rides with the actions: visible on hover or focus,
          // and spoken as part of the group's name for touch and for readers
          // who never see a hover at all.
          <ActionBarPrimitive.Root
            className="message__actions"
            role="group"
            aria-label={stamp ? `Reply actions, ${stamp.clock}` : "Reply actions"}
            hideWhenRunning
          >
            {stamp ? (
              <time className="message__time" dateTime={stamp.iso}>
                {stamp.clock}
              </time>
            ) : null}
            <ActionBarPrimitive.Copy
              className="quiet-action"
              aria-label={copied ? "Reply copied" : "Copy reply"}
            >
              {copied ? <CheckIcon size={14} /> : <CopyIcon size={14} />}
              {copied ? "Copied" : "Copy"}
            </ActionBarPrimitive.Copy>
            <ActionBarPrimitive.Reload className="quiet-action" aria-label="Regenerate reply">
              Regenerate
            </ActionBarPrimitive.Reload>
          </ActionBarPrimitive.Root>
        ) : null}
      </div>
      </article>
    </>
  );
}

function UserMessage() {
  const copied = useAuiState((state) => state.message.isCopied);
  const stamp = useMessageStamp();

  return (
    <>
      <DayDivider />
      <article className="message message--user">
      <div className="message__bubble">
        <MessagePrimitive.Parts components={{ Text: TextPart }} />
      </div>
      <MessagePrimitive.Attachments>
        {({ attachment }) => {
          // The turn owns the id; the prepared copy (if this session still has
          // it) supplies the preview and size the composer showed.
          const ready = attachment.content
            ?.map((part) => (part.type === "file" ? preparedAttachmentById(part.data) : null))
            .find((candidate) => candidate !== null);
          const size = ready ? formatFileSize(ready.size) : "";

          return (
            <span className="attachment-chip" data-aui-quote-selectable="false">
              {ready?.dataUrl ? (
                <img className="attachment-chip__thumb" src={ready.dataUrl} alt="" />
              ) : null}
              <span className="attachment-chip__meta">
                <span className="attachment-chip__name">{attachment.name}</span>
                {size ? <span className="attachment-chip__size">{size}</span> : null}
              </span>
            </span>
          );
        }}
      </MessagePrimitive.Attachments>
      <ActionBarPrimitive.Root
        className="message__actions message__actions--user"
        role="group"
        aria-label={stamp ? `Message actions, ${stamp.clock}` : "Message actions"}
      >
        {stamp ? (
          <time className="message__time" dateTime={stamp.iso}>
            {stamp.clock}
          </time>
        ) : null}
        <ActionBarPrimitive.Edit className="quiet-action" aria-label="Edit message">
          Edit
        </ActionBarPrimitive.Edit>
        <ActionBarPrimitive.Copy
          className="quiet-action"
          aria-label={copied ? "Message copied" : "Copy message"}
        >
          {copied ? "Copied" : "Copy"}
        </ActionBarPrimitive.Copy>
      </ActionBarPrimitive.Root>
      </article>
    </>
  );
}

function SystemMessage() {
  return (
    <>
      <DayDivider />
      <article className="message message--notice">
        <MessagePrimitive.Parts components={{ Text: TextPart }} />
      </article>
    </>
  );
}

/** Editing a message in place: same verb, same place, no second surface. */
function EditComposer() {
  return (
    <ComposerPrimitive.Root className="composer composer--edit">
      <ComposerPrimitive.Input
        className="composer__input"
        submitMode="enter"
        aria-label="Edit message"
      />
      <div className="composer__actions">
        <ComposerPrimitive.Cancel className="quiet-action">Cancel</ComposerPrimitive.Cancel>
        <ComposerPrimitive.Send className="composer__send composer__send--text" aria-label="Save edit">
          Save
        </ComposerPrimitive.Send>
      </div>
    </ComposerPrimitive.Root>
  );
}

export function Conversation() {
  const { sendMessage, streaming, thinkingPhase, messages } = useStudio();

  // Only the newest reply is announcement-worthy. Keeping it out of the log
  // means a reader can move through history without every delta replaying it.
  const latestReply = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const message = messages[index];
      if (message.role !== "assistant") {
        continue;
      }
      const prose = (message.parts ?? [])
        .flatMap((part) => (part.kind === "text" ? [part.text] : []))
        .join(" ");
      return prose || message.content;
    }
    return "";
  }, [messages]);

  // The clock the transcript reads from, kept beside the turn list it describes.
  const clock = useMemo(
    () => ({
      order: new Map(messages.map((message, index) => [message.id, index])),
      messages,
    }),
    [messages],
  );

  return (
    <UiActionContext.Provider
      value={{ onIntent: (intent) => void sendMessage(intent), busy: streaming }}
    >
      {/* The phase lives outside the log: the streaming reply is `aria-busy`,
          and a status message inside it would not be announced until the
          answer finished — the one moment it is no longer useful. The region
          holds the newest reply while it streams, then settles on it. */}
      <p className="sr-only" role="status" aria-live="polite" aria-busy={streaming}>
        {streaming ? phaseLabel(thinkingPhase) : latestReply}
      </p>
      <TranscriptClockContext.Provider value={clock}>
        <div className="conversation" role="log" aria-label="Conversation">
          <ThreadPrimitive.Messages
            components={{
              UserMessage,
              AssistantMessage,
              SystemMessage,
              EditComposer,
            }}
          />
        </div>
      </TranscriptClockContext.Provider>
    </UiActionContext.Provider>
  );
}

export { Markdown };
