/**
 * One renderer per message part.
 *
 * Each component reads only the scoped part it was mounted for, so a slow or
 * broken surface cannot take the rest of the transcript with it. Nothing here
 * knows where the data came from; the conversion in `convert.ts` already
 * decided what each part means.
 */

import { useState } from "react";
import { useAuiState, type ToolCallMessagePartProps } from "@assistant-ui/react";

import { CheckIcon, SparkIcon } from "../components/icons";
import { Markdown } from "../components/chat/Markdown";
import type { UiNode } from "../ui/protocol";
import { UiRenderer } from "../ui/UiRenderer";
import { SURFACE_PART } from "./convert";

/** Prose. The existing renderer, so the transcript reads exactly as before. */
export function TextPart() {
  const text = useAuiState((state) => (state.part.type === "text" ? state.part.text : null));
  if (text === null) {
    return null;
  }
  return <Markdown source={text} />;
}

/** The model's thinking, kept out of the answer and out of the way. */
export function ReasoningPart() {
  const text = useAuiState((state) =>
    state.part.type === "reasoning" ? state.part.text : null,
  );
  const running = useAuiState((state) => state.part.status?.type === "running");
  if (!text) {
    return null;
  }
  return (
    <details className="reasoning" open={false}>
      <summary className="reasoning__summary">
        <SparkIcon size={13} />
        {running ? "Thinking…" : "Thought for a moment"}
      </summary>
      <div className="reasoning__body">
        <Markdown source={text} />
      </div>
    </details>
  );
}

/** What the turn actually read. A provenance chip, never a fabricated link. */
export function SourcePart() {
  const source = useAuiState((state) => {
    if (state.part.type !== "source") {
      return null;
    }
    return state.part;
  });
  if (!source) {
    return null;
  }
  const title = source.sourceType === "url" ? (source.title ?? source.url) : source.title;
  const filename = source.sourceType === "document" ? source.filename : undefined;
  return (
    <span className="source-chip" title={filename ?? title}>
      <span className="source-chip__label">Source</span>
      <span className="source-chip__title">{title}</span>
    </span>
  );
}

/** An agent-composed ODI surface, validated before it ever reached React. */
export function SurfacePart() {
  const node = useAuiState((state) =>
    state.part.type === "data" && state.part.name === SURFACE_PART
      ? (state.part.data as UiNode)
      : null,
  );
  if (!node) {
    return null;
  }
  return <UiRenderer node={node} />;
}

/** A file the user attached, shown by name. */
export function FilePart() {
  const file = useAuiState((state) => (state.part.type === "file" ? state.part : null));
  if (!file) {
    return null;
  }
  return (
    <span className="attachment-chip">
      <span className="attachment-chip__name">{file.filename ?? "Attachment"}</span>
    </span>
  );
}

function toolLabel(name: string): string {
  return name.replace(/_/g, " ");
}

/**
 * A tool call, and the one question the agent is not allowed to answer itself:
 * whether it may write.
 */
export function ToolPart({
  toolName,
  approval,
  result,
  isError,
  status,
  respondToApproval,
}: ToolCallMessagePartProps) {
  const [busy, setBusy] = useState(false);
  const [answered, setAnswered] = useState(false);
  const payload = result as { status?: string; preview?: string } | undefined;
  const pending = approval !== undefined && approval.approved === undefined && !result;
  const running = status?.type === "running";

  async function answer(approved: boolean) {
    if (!approval || busy) {
      return;
    }
    setBusy(true);
    try {
      await respondToApproval({ approved });
      setAnswered(true);
    } catch {
      // The gate may have expired; the stream reports what happened to the turn.
    } finally {
      setBusy(false);
    }
  }

  if (pending && !answered) {
    return (
      <div className="approval" role="group" aria-label="Permission needed">
        <p className="approval__prompt">{approval.prompt ?? `Run ${toolLabel(toolName)}?`}</p>
        <div className="approval__actions">
          <button
            type="button"
            className="approval__allow"
            disabled={busy}
            onClick={() => void answer(true)}
          >
            <CheckIcon size={14} /> Allow
          </button>
          <button
            type="button"
            className="approval__deny"
            disabled={busy}
            onClick={() => void answer(false)}
          >
            Don't allow
          </button>
        </div>
      </div>
    );
  }

  const tone = isError || payload?.status === "error" ? " is-error" : "";
  return (
    <p className={`tool-trace${tone}`}>
      <span className="tool-trace__dot" aria-hidden="true" />
      {toolLabel(toolName)}
      {running ? " · working" : payload?.status === "declined" ? " · declined" : ""}
      {payload?.preview ? <span className="tool-trace__preview">{payload.preview}</span> : null}
    </p>
  );
}

/** The typing state before the first token arrives. */
export function TypingPart({ label }: { label: string }) {
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

/** The sparkle avatar, shared by every assistant turn. */
export function AssistantAvatar() {
  return (
    <span className="message__avatar" aria-hidden="true">
      <SparkIcon size={15} />
    </span>
  );
}
