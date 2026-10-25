/**
 * The bridge between our transcript and assistant-ui's thread runtime.
 *
 * The studio owns the conversation: the sidecar writes it, memory restores it,
 * and every turn carries fields a generic chat message has no room for (run
 * steps, a failure, a stopped run, the agent's surfaces). So the runtime is fed
 * a mapped copy rather than being asked to hold the state: assistant-ui gets a
 * thread it understands, and our store keeps being the one place a turn lives.
 *
 * This module is deliberately pure — no React, no clipboard, no network — so
 * the mapping is testable without a DOM.
 */

import type {
  AppendMessage,
  FileMessagePart,
  ImageMessagePart,
  MessageState,
  ThreadMessageLike,
} from "@assistant-ui/react";

import type { ChatAttachmentPayload, ChatMessage, StudioError } from "../types";
import type { RunStep } from "./run";

/** Everything the runtime needs to know about the run that produced a turn. */
export interface ThreadContext {
  streaming: boolean;
  phase: string | null;
  offline: boolean;
}

/** What a turn carries in `metadata.custom`, read back when it renders. */
export interface TurnMeta {
  tools?: RunStep[];
  stopped?: boolean;
  error?: StudioError;
  retryText?: string;
  retryAttachments?: ChatAttachmentPayload[];
  phase?: string | null;
  offline?: boolean;
}

/** A stable id for a turn the studio creates itself. */
let sequence = 0;
export function newTurnId(): string {
  sequence += 1;
  return `turn-${sequence.toString(36)}-${Date.now().toString(36)}`;
}

export function messageIdOf(message: ChatMessage, index: number): string {
  return message.id ?? `turn-${index}`;
}

function isImage(mediaType: string): boolean {
  return mediaType.split(";")[0].trim().toLowerCase().startsWith("image/");
}

/** A stored file as a thread part the runtime can reason about. */
function attachmentPart(file: ChatAttachmentPayload, index: number): ImageMessagePart | FileMessagePart {
  if (isImage(file.media_type)) {
    return {
      type: "image",
      id: `file-${index}`,
      image: `data:${file.media_type};base64,${file.data}`,
      filename: file.name,
    };
  }
  return {
    type: "file",
    id: `file-${index}`,
    filename: file.name,
    data: file.data,
    mimeType: file.media_type,
  };
}

function contentOf(message: ChatMessage): ThreadMessageLike["content"] {
  if (message.role === "user") {
    const text = message.content ? [{ type: "text" as const, text: message.content }] : [];
    return [...text, ...(message.attachments ?? []).map(attachmentPart)];
  }

  if (message.role === "assistant") {
    if (message.parts?.length) {
      return message.parts.map((part) =>
        part.kind === "ui"
          ? { type: "data", name: "ui", id: part.id, data: { id: part.id, node: part.node } }
          : { type: "text", text: part.text },
      );
    }
    return message.content ? [{ type: "text", text: message.content }] : [];
  }

  return message.content;
}

function statusOf(
  message: ChatMessage,
  index: number,
  lastIndex: number,
  ctx: ThreadContext,
): ThreadMessageLike["status"] {
  if (message.role !== "assistant") {
    return undefined;
  }
  if (message.stopped) {
    return { type: "incomplete", reason: "cancelled" };
  }
  if (message.error) {
    return { type: "incomplete", reason: "error" };
  }
  if (ctx.streaming && index === lastIndex) {
    return { type: "running" };
  }
  return { type: "complete", reason: "stop" };
}

/**
 * Our transcript as a thread the runtime can render and act on.
 *
 * Only the newest turn learns the live phase and whether the model answered
 * from its offline guidance: an older turn is history, and history does not get
 * to look like it is still happening.
 */
export function toThreadMessage(
  message: ChatMessage,
  index: number,
  lastIndex: number,
  ctx: ThreadContext,
): ThreadMessageLike {
  const isLast = index === lastIndex;
  const meta: TurnMeta = {
    ...(message.tools?.length ? { tools: message.tools } : {}),
    ...(message.stopped ? { stopped: true } : {}),
    ...(message.error ? { error: message.error } : {}),
    ...(message.retryText ? { retryText: message.retryText } : {}),
    ...(message.retryAttachments?.length
      ? { retryAttachments: message.retryAttachments }
      : {}),
    ...(isLast && ctx.phase ? { phase: ctx.phase } : {}),
    ...(isLast && ctx.offline ? { offline: true } : {}),
  };

  return {
    id: messageIdOf(message, index),
    role: message.role === "notice" ? "system" : message.role,
    content: contentOf(message),
    status: statusOf(message, index, lastIndex, ctx),      ...(Object.keys(meta).length
        ? { metadata: { custom: meta as unknown as Record<string, unknown> } }
        : {}),
  };
}

export function toThreadMessages(
  messages: readonly ChatMessage[],
  ctx: ThreadContext,
): ThreadMessageLike[] {
  const lastIndex = messages.length - 1;
  return messages.map((message, index) => toThreadMessage(message, index, lastIndex, ctx));
}

/** Read a turn's studio fields back out of the runtime's message. */
export function metaOf(message: {
  metadata?: { custom?: Record<string, unknown> } | undefined;
}): TurnMeta {
  return (message.metadata?.custom ?? {}) as TurnMeta;
}

/** The prose in a message the runtime is holding. */
export function textOf(
  message: Pick<MessageState, "content">,
): string {
  return message.content
    .filter((part) => part.type === "text")
    .map((part) => (part as { text: string }).text)
    .join("");
}

function payloadFromImage(part: { image: string; filename?: string }): ChatAttachmentPayload | null {
  const match = /^data:([^;,]+);base64,(.*)$/.exec(part.image);
  if (!match) {
    return null;
  }
  return { name: part.filename ?? "image", media_type: match[1], data: match[2] };
}

/**
 * What the reader just sent, in the shape the sidecar takes.
 *
 * The runtime hands over parts and files; the studio sends text plus base64
 * bytes, and nothing here is allowed to invent an attachment it cannot read.
 */
export function turnFromAppend(append: AppendMessage): {
  text: string;
  attachments: ChatAttachmentPayload[];
} {
  const text = append.content
    .filter((part) => part.type === "text")
    .map((part) => (part as { text: string }).text)
    .join("");

  const attachments: ChatAttachmentPayload[] = [];
  for (const part of append.content) {
    if (part.type === "image") {
      const payload = payloadFromImage(part);
      if (payload) {
        attachments.push(payload);
      }
    } else if (part.type === "file") {
      attachments.push({
        name: part.filename ?? "file",
        media_type: part.mimeType,
        data: part.data,
      });
    }
  }

  return { text, attachments };
}
