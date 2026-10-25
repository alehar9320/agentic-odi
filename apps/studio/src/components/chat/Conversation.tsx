import { useState } from "react";

import { isImage } from "../../lib/attachments";
import { activityLabel } from "../../lib/run";
import { useStudio } from "../../state/StudioContext";
import type { ChatAttachmentPayload, ChatMessage, ChatPart, StudioError } from "../../types";
import { UiActionContext } from "../../ui/actions";
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
  const { pushToast, sendMessage } = useStudio();
  const [copied, setCopied] = useState(false);
  const steps = tools ?? [];
  const label = activityLabel(phase, []);
  const retry = (text: string) =>
    retryAttachments?.length ? void sendMessage(text, retryAttachments) : void sendMessage(text);

  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      pushToast("error", "Could not copy to the clipboard.");
    }
  }

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

        {content && !streaming && (
          <div className="message__actions">
            <button
              type="button"
              className="quiet-action"
              onClick={() => void copy()}
              aria-label="Copy reply"
            >
              {copied ? <CheckIcon size={14} /> : <CopyIcon size={14} />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        )}
      </div>
    </article>
  );
}

export function Conversation() {
  const { messages, streaming, thinkingPhase, offlineReply, sendMessage } = useStudio();
  const lastIndex = messages.length - 1;

  return (
    <UiActionContext.Provider value={{ onIntent: (intent) => void sendMessage(intent), busy: streaming }}>
      {/*
        The transcript itself is not a live region; the shell announces settled
        turns through `TranscriptAnnouncer`. Speaker labels are hidden text so
        navigating turn by turn has an author even when the avatar is decorative.
      */}
      <div className="conversation">
        {messages.map((message, index) => {
          const isLast = index === lastIndex;
          if (message.role === "user") {
            return (
              <article className="message message--user" key={index}>
                <div className="message__bubble">
                  <span className="sr-only">You said: </span>
                  {message.attachments?.length ? (
                    <ul className="attach-sent" aria-label="Files you sent">
                      {message.attachments.map((file, fileIndex) => (
                        <li className="attach-sent__item" key={`${file.name}-${fileIndex}`}>
                          {isImage(file) ? (
                            <img
                              className="attach-sent__thumb"
                              src={`data:${file.media_type};base64,${file.data}`}
                              alt=""
                            />
                          ) : (
                            <FileIcon size={12} />
                          )}
                          <span>{file.name}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  {message.content}
                </div>
              </article>
            );
          }
          if (message.role === "notice") {
            return (
              <article className="message message--notice" key={index}>
                <span className="sr-only">Studio notice: </span>
                <Markdown source={message.content} />
              </article>
            );
          }
          return (
            <AssistantMessage
              key={index}
              content={message.content}
              parts={message.parts ?? []}
              streaming={streaming && isLast}
              phase={thinkingPhase ?? null}
              tools={message.tools}
              stopped={message.stopped}
              offline={isLast && offlineReply}
              error={message.error}
              retryText={message.retryText}
              retryAttachments={message.retryAttachments}
            />
          );
        })}
      </div>
    </UiActionContext.Provider>
  );
}
