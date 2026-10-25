import {
  ActionBarPrimitive,
  AssistantRuntimeProvider,
  AuiIf,
  ComposerPrimitive,
  ThreadPrimitive,
  useAuiState,
  useExternalStoreRuntime,
} from "@assistant-ui/react";

import { activityLabel } from "../../lib/run";
import { metaOf, textOf, toThreadMessage, turnFromAppend } from "../../lib/thread";
import { useStudio } from "../../state/StudioContext";
import type { ChatAttachmentPayload, ChatMessage, ChatPart, StudioError } from "../../types";
import { UiActionContext } from "../../ui/actions";
import type { UiNode } from "../../ui/protocol";
import { UiRenderer } from "../../ui/UiRenderer";
import { FailurePanel } from "../FailurePanel";
import { CheckIcon, CopyIcon, FileIcon, SparkIcon } from "../icons";
import { Markdown } from "./Markdown";
import { RunActivity } from "./RunActivity";

function Typing({ label }: { label: string }) {
  return (
    <p className="typing" role="status">
      <span className="typing__dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      {label}…
    </p>
  );
}

/**
 * Prose and surfaces in the order the agent produced them. A text part is
 * markdown; a `ui` part is a validated node tree rendered by the catalog.
 */
function MessageParts({ parts }: { parts: ChatPart[] }) {
  return (
    <>
      {parts.map((part, index) =>
        part.kind === "text" ? (
          <Markdown source={part.text} key={index} />
        ) : (
          <UiRenderer node={part.node} key={part.id || index} />
        ),
      )}
    </>
  );
}

function AssistantMessage({
  content,
  parts,
  streaming,
  phase,
  tools,
  stopped,
  offline,
  error,
  retryText,
  retryAttachments,
}: {
  content: string;
  parts: ChatPart[];
  streaming: boolean;
  /** The sidecar's stage while this turn is live. */
  phase: string | null;
  tools: ChatMessage["tools"];
  stopped?: boolean;
  offline?: boolean;
  error?: StudioError;
  retryText?: string;
  retryAttachments?: ChatAttachmentPayload[];
}) {
  const { sendMessage } = useStudio();
  const steps = tools ?? [];
  const label = activityLabel(phase, []);
  const retry = (text: string) =>
    retryAttachments?.length ? void sendMessage(text, retryAttachments) : void sendMessage(text);

  const empty = !content && parts.length === 0;
  if (empty && !streaming && !error && !stopped && !steps.length) {
    return null;
  }

  return (
    <article className="message message--assistant">
      <span className="message__avatar" aria-hidden="true">
        <SparkIcon size={15} />
      </span>
      <div className="message__body">
        <span className="sr-only">Studio said: </span>
        {offline && content ? <span className="message__tag">Local guidance</span> : null}
        {parts.length > 0 ? (
          <MessageParts parts={parts} />
        ) : content ? (
          <Markdown source={content} />
        ) : !error && !stopped && !steps.length ? (
          <Typing label={label} />
        ) : null}
        {error ? (
          <FailurePanel error={error} retryText={retryText} onRetry={retry} />
        ) : null}
        {streaming && content && <span className="caret" aria-hidden="true" />}

        <RunActivity steps={steps} live={streaming} phase={phase} />

        {stopped ? (
          <div className="stopped">
            <span className="stopped__text">Stopped by you.</span>
            {retryText || retryAttachments?.length ? (
              <button
                type="button"
                className="quiet-action"
                onClick={() => retry(retryText ?? "")}
                disabled={streaming}
              >
                Ask again
              </button>
            ) : null}
          </div>
        ) : null}

        {/* A stopped or failed turn already offers its own re-ask. */}
        {content && !streaming && !stopped && !error ? (
          <ActionBarPrimitive.Root className="message__actions">
            <ActionBarPrimitive.Copy className="quiet-action" aria-label="Copy reply">
              <AuiIf condition={(state) => state.message.isCopied}>
                <CheckIcon size={14} />
                <span aria-hidden="true">Copied</span>
              </AuiIf>
              <AuiIf condition={(state) => !state.message.isCopied}>
                <CopyIcon size={14} />
                <span aria-hidden="true">Copy</span>
              </AuiIf>
            </ActionBarPrimitive.Copy>
            <ActionBarPrimitive.Reload className="quiet-action">
              <SparkIcon size={14} />
              <span>Answer again</span>
            </ActionBarPrimitive.Reload>
          </ActionBarPrimitive.Root>
        ) : null}
      </div>
    </article>
  );
}

/** An assistant turn, rebuilt from the runtime's copy of it. */
function AssistantTurn() {
  const message = useAuiState((state) => state.message);
  const meta = metaOf(message);
  const parts: ChatPart[] = message.content.map((part, index) =>
    part.type === "data" && part.name === "ui"
      ? {
          kind: "ui",
          id: part.id ?? `ui-${index}`,
          node: (part.data as { node: UiNode }).node,
        }
      : { kind: "text", text: (part as { text: string }).text },
  );

  return (
    <AssistantMessage
      content={textOf(message)}
      parts={message.content.some((part) => part.type === "data") ? parts : []}
      streaming={message.status?.type === "running"}
      phase={meta.phase ?? null}
      tools={meta.tools}
      stopped={meta.stopped}
      offline={meta.offline}
      error={meta.error}
      retryText={meta.retryText}
      retryAttachments={meta.retryAttachments}
    />
  );
}

/** The reader's own turn, with the files it carried. */
function UserTurn() {
  const message = useAuiState((state) => state.message);
  const text = textOf(message);

  return (
    <article className="message message--user">
      <div className="message__bubble">
        <span className="sr-only">You said: </span>
        {message.content.some((part) => part.type === "image" || part.type === "file") ? (
          <ul className="attach-sent" aria-label="Files you sent">
            {message.content.map((part, index) => {
              if (part.type === "image") {
                return (
                  <li className="attach-sent__item" key={part.id ?? index}>
                    <img className="attach-sent__thumb" src={part.image} alt="" />
                    <span>{part.filename ?? "image"}</span>
                  </li>
                );
              }
              if (part.type === "file") {
                return (
                  <li className="attach-sent__item" key={part.id ?? index}>
                    <FileIcon size={12} />
                    <span>{part.filename ?? "file"}</span>
                  </li>
                );
              }
              return null;
            })}
          </ul>
        ) : null}
        {text}
        <ActionBarPrimitive.Root className="message__actions">
          <ActionBarPrimitive.Edit className="quiet-action">
            <span>Edit</span>
          </ActionBarPrimitive.Edit>
        </ActionBarPrimitive.Root>
      </div>
    </article>
  );
}

/**
 * Editing a question, in place, with the composer the runtime already knows.
 * Sending replaces that turn and every later one — the same operation as
 * **Answer again**, which is why both end in one store call.
 */
function UserEdit() {
  return (
    <article className="message message--user">
      <ComposerPrimitive.Root className="message__bubble message__bubble--edit">
        <ComposerPrimitive.Input
          className="message__edit-input"
          aria-label="Edit your message"
          autoFocus
        />
        <div className="message__actions message__actions--pinned">
          <ComposerPrimitive.Cancel className="quiet-action">Cancel</ComposerPrimitive.Cancel>
          <ComposerPrimitive.Send className="quiet-action">Send</ComposerPrimitive.Send>
        </div>
      </ComposerPrimitive.Root>
    </article>
  );
}

/** A local notice (a command's answer, a failure) is a system turn. */
function NoticeTurn() {
  const message = useAuiState((state) => state.message);

  return (
    <article className="message message--notice">
      <span className="sr-only">Studio notice: </span>
      <Markdown source={textOf(message)} />
    </article>
  );
}

/**
 * The transcript, powered by assistant-ui's thread runtime.
 *
 * Our store stays the source of truth — the sidecar writes it and memory
 * restores it — and the runtime is fed a mapped copy each render. What that
 * buys is the thread machinery a bespoke list has to rebuild: stable message
 * identity, an action bar that knows what can be copied or re-asked, and the
 * primitives the rest of the chat surface can grow into.
 */
export function Conversation() {
  const { messages, streaming, thinkingPhase, offlineReply, sendMessage, stopStreaming } =
    useStudio();
  const lastIndex = messages.length - 1;

  const runtime = useExternalStoreRuntime<ChatMessage>({
    messages,
    convertMessage: (message, index) =>
      toThreadMessage(message, index, lastIndex, {
        streaming,
        phase: thinkingPhase,
        offline: offlineReply,
      }),
    isRunning: streaming,
    isSendDisabled: streaming,
    onNew: async (append) => {
      const { text, attachments } = turnFromAppend(append);
      await sendMessage(text, attachments);
    },
    onReload: async (parentId) => {
      const parent = messages.find((message) => message.id === parentId);
      if (!parent) {
        return;
      }
      await sendMessage(parent.content, parent.attachments ?? [], { from: parentId ?? undefined });
    },
    onEdit: async (append) => {
      const { text, attachments } = turnFromAppend(append);
      await sendMessage(text, attachments, { from: append.sourceId ?? undefined });
    },
    onCancel: async () => stopStreaming(),
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <UiActionContext.Provider
        value={{ onIntent: (intent) => void sendMessage(intent), busy: streaming }}
      >
        {/*
          The transcript itself is not a live region; the shell announces settled
          turns through `TranscriptAnnouncer`. Speaker labels are hidden text so
          navigating turn by turn has an author even when the avatar is decorative.
        */}
        <ThreadPrimitive.Root className="conversation">
          <ThreadPrimitive.Messages
            components={{
              UserMessage: UserTurn,
              AssistantMessage: AssistantTurn,
              SystemMessage: NoticeTurn,
              UserEditComposer: UserEdit,
            }}
          />
        </ThreadPrimitive.Root>
      </UiActionContext.Provider>
    </AssistantRuntimeProvider>
  );
}
