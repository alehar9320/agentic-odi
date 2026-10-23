import { useState } from "react";

import { useStudio } from "../../state/StudioContext";
import type { ChatPart, StudioError } from "../../types";
import { UiActionContext } from "../../ui/actions";
import { UiRenderer } from "../../ui/UiRenderer";
import { FailurePanel } from "../FailurePanel";
import { CheckIcon, CopyIcon, SparkIcon } from "../icons";
import { Markdown } from "./Markdown";

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

function toolLabel(name: string): string {
  return name.replace(/_/g, " ");
}

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
  label,
  tools,
  offline,
  error,
  retryText,
}: {
  content: string;
  parts: ChatPart[];
  streaming: boolean;
  label: string;
  tools: { name: string; status: string; preview?: string }[];
  offline?: boolean;
  error?: StudioError;
  retryText?: string;
}) {
  const { pushToast, sendMessage } = useStudio();
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      pushToast("error", "Could not copy to the clipboard.");
    }
  }

  if (!content && !streaming && parts.length === 0 && !error) {
    return null;
  }

  return (
    <article className="message message--assistant">
      <span className="message__avatar" aria-hidden="true">
        <SparkIcon size={15} />
      </span>
      <div className="message__body">
        {offline && content ? <span className="message__tag">Local guidance</span> : null}
        {parts.length > 0 ? (
          <MessageParts parts={parts} />
        ) : content ? (
          <Markdown source={content} />
        ) : !error ? (
          <Typing label={label} />
        ) : null}
        {error ? (
          <FailurePanel
            error={error}
            retryText={retryText}
            onRetry={(text) => void sendMessage(text)}
          />
        ) : null}
        {streaming && content && <span className="caret" aria-hidden="true" />}

        {tools.length > 0 && (
          <ul className="traces" aria-label="Tools used">
            {tools.map((tool, index) => (
              <li className="trace" key={`${tool.name}-${index}`}>
                <span className="trace__dot" aria-hidden="true" />
                {toolLabel(tool.name)}
                {tool.status && tool.status !== "ok" ? ` · ${tool.status}` : ""}
                {tool.preview ? <span className="trace__preview">{tool.preview}</span> : null}
              </li>
            ))}
          </ul>
        )}

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
  const { messages, streaming, thinkingPhase, toolActivity, offlineReply, sendMessage } = useStudio();
  const lastIndex = messages.length - 1;

  return (
    <UiActionContext.Provider value={{ onIntent: (intent) => void sendMessage(intent), busy: streaming }}>
      <div className="conversation" role="log" aria-live="polite" aria-label="Conversation">
        {messages.map((message, index) => {
          const isLast = index === lastIndex;
          if (message.role === "user") {
            return (
              <article className="message message--user" key={index}>
                <div className="message__bubble">{message.content}</div>
              </article>
            );
          }
          if (message.role === "notice") {
            return (
              <article className="message message--notice" key={index}>
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
              label={phaseLabel(thinkingPhase)}
              tools={isLast ? toolActivity : []}
              offline={isLast && offlineReply}
              error={message.error}
              retryText={message.retryText}
            />
          );
        })}
      </div>
    </UiActionContext.Provider>
  );
}
