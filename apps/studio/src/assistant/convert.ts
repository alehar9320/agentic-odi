/**
 * The one mapping between the Studio's message model and assistant-ui's.
 *
 * Kept in one place and pure, so the thread can be tested without a runtime and
 * the runtime can be swapped without touching the transcript. Anything the
 * conversion does not understand is dropped rather than rendered as raw JSON:
 * an unknown part must never reach the screen as machine text.
 */

import type { ThreadMessage, ThreadMessageLike } from "@assistant-ui/react";

import type { ChatAttachment, ChatMessage, ChatPart, StudioError } from "../types";
import type { UiNode } from "../ui/protocol";

/** The name our generated-surface parts travel under. */
export const SURFACE_PART = "odi-surface";

type LikePart = Exclude<ThreadMessageLike["content"], string>[number];

const TOOL_RESULT: Record<string, Record<string, unknown>> = {
  ok: { status: "ok" },
  error: { status: "error", isError: true },
  declined: { status: "declined" },
};

function toPart(part: ChatPart): LikePart | null {
  switch (part.kind) {
    case "text":
      return { type: "text", text: part.text };

    case "reasoning":
      return { type: "reasoning", text: part.text };

    case "ui":
      return { type: "data", name: SURFACE_PART, id: part.id, data: part.node };

    case "source":
      return {
        type: "source",
        sourceType: "document",
        id: part.id,
        title: part.title,
        mediaType: part.mediaType,
        ...(part.filename ? { filename: part.filename } : {}),
      };

    case "tool": {
      const approval = part.approval;
      if (approval) {
        // A pending write is a question, not a result: the runtime keeps the
        // message in `requires-action` until the user answers.
        return {
          type: "tool-call",
          toolCallId: part.id,
          toolName: part.name,
          args: {},
          argsText: "{}",
          approval: { id: approval.id, prompt: approval.prompt },
        };
      }
      return {
        type: "tool-call",
        toolCallId: part.id,
        toolName: part.name,
        args: {},
        argsText: "{}",
        result: { ...(TOOL_RESULT[part.status] ?? {}), preview: part.preview ?? "" },
        isError: part.status === "error",
      };
    }

    default:
      return null;
  }
}

function attachmentParts(attachments: ChatAttachment[]) {
  return attachments.map((attachment) => ({
    id: attachment.id,
    type: attachment.contentType.startsWith("image/") ? ("image" as const) : ("document" as const),
    name: attachment.name,
    contentType: attachment.contentType,
    status: { type: "complete" as const },
    content: [
      {
        type: "file" as const,
        data: attachment.id,
        mimeType: attachment.contentType,
        filename: attachment.name,
      },
    ],
  }));
}

/**
 * A Studio turn as the runtime renders it.
 *
 * `content` stays the concatenated prose so history replays byte-identically;
 * `parts` is what the thread shows.
 */
export function toThreadMessageLike(message: ChatMessage): ThreadMessageLike {
  if (message.role === "notice") {
    return {
      id: message.id,
      role: "system",
      content: [{ type: "text", text: message.content }],
    };
  }

  const parts = (message.parts ?? []).flatMap((part) => {
    const converted = toPart(part);
    return converted ? [converted] : [];
  });

  const content: readonly LikePart[] =
    parts.length > 0
      ? parts
      : message.content
        ? [{ type: "text", text: message.content }]
        : [];

  const failed = message.error !== undefined;

  return {
    id: message.id,
    role: message.role,
    content,
    ...(message.role === "user" && message.attachments?.length
      ? { attachments: attachmentParts(message.attachments) }
      : {}),
    ...(failed
      ? {
          status: {
            type: "incomplete" as const,
            reason: "error" as const,
            error: message.error as never,
          },
        }
      : {}),
    ...(failed || message.retryText
      ? {
          metadata: {
            custom: {
              ...(message.error ? { error: message.error } : {}),
              ...(message.retryText ? { retryText: message.retryText } : {}),
            },
          },
        }
      : {}),
  };
}

function readCustom(message: ThreadMessage): Record<string, unknown> {
  return (message.metadata?.custom ?? {}) as Record<string, unknown>;
}

/**
 * The inverse: a runtime message back in the Studio's own model.
 *
 * The runtime hands a branch switch back as the originals it was given, so this
 * is only needed when a message arrives from somewhere else — an import, or a
 * future remote thread.
 */
export function toChatMessage(
  message: ThreadMessage,
  parentId: string | null = null,
): ChatMessage {
  const text = message.content
    .filter((part) => part.type === "text")
    .map((part) => (part as unknown as { text: string }).text)
    .join("");

  const custom = readCustom(message);
  const parts: ChatPart[] = [];

  for (const part of message.content) {
    switch (part.type) {
      case "text":
        parts.push({ kind: "text", text: part.text });
        break;

      case "reasoning":
        parts.push({ kind: "reasoning", text: part.text });
        break;

      case "source":
        parts.push({
          kind: "source",
          id: part.id,
          title: part.sourceType === "url" ? (part.title ?? part.url) : part.title,
          mediaType: part.sourceType === "document" ? part.mediaType : "text/html",
          ...(part.sourceType === "document" && part.filename
            ? { filename: part.filename }
            : {}),
        });
        break;

      case "tool-call": {
        const result = part.result as { status?: string; preview?: string } | undefined;
        const approval = part.approval;
        const awaiting = approval !== undefined && approval.approved === undefined && !part.result;
        parts.push({
          kind: "tool",
          id: part.toolCallId,
          name: part.toolName,
          status: awaiting
            ? "running"
            : part.isError
              ? "error"
              : result?.status === "declined"
                ? "declined"
                : "ok",
          ...(result?.preview ? { preview: result.preview } : {}),
          ...(awaiting ? { approval: { id: approval.id, prompt: approval.prompt ?? "" } } : {}),
        });
        break;
      }

      case "data":
        if (part.name === SURFACE_PART) {
          parts.push({
            kind: "ui",
            id: part.id ?? `ui-${parts.length}`,
            node: part.data as UiNode,
          });
        }
        break;

      default:
        break;
    }
  }

  const attachments: ChatAttachment[] | undefined = message.attachments?.length
    ? message.attachments.map((attachment) => ({
        id: attachment.id,
        name: attachment.name,
        contentType: attachment.contentType ?? "application/octet-stream",
        size: 0,
      }))
    : undefined;

  const role = message.role === "system" ? "notice" : message.role;

  return {
    id: message.id,
    parentId,
    role,
    content: text,
    ...(parts.length ? { parts } : {}),
    ...(attachments ? { attachments } : {}),
    ...(custom.error ? { error: custom.error as StudioError } : {}),
    ...(custom.retryText ? { retryText: String(custom.retryText) } : {}),
  };
}

/** The readable text of one appended message, for the Studio's send path. */
export function textOf(message: { content: string | readonly { type: string }[] }): string {
  if (typeof message.content === "string") {
    return message.content.trim();
  }
  return message.content
    .filter((part) => part.type === "text")
    .map((part) => (part as unknown as { text: string }).text)
    .join("\n")
    .trim();
}
// refresh
