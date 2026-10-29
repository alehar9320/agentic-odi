/**
 * Turning a dropped file into something the model can actually read.
 *
 * The client owns this because only the client has the bytes: the sidecar
 * receives extracted text (or a data URL for an image), never a file handle.
 * Extraction is bounded so one large attachment cannot crowd out the
 * conversation, and it is silent about failure — a file we cannot read is shown
 * as a name, not dressed up as content.
 */

import type { AttachmentAdapter, CompleteAttachment, PendingAttachment } from "@assistant-ui/react";

import type { ChatAttachment } from "../types";

/** How much of a text file the model sees. */
export const MAX_ATTACHMENT_CHARS = 20_000;

/** A single image, bounded so a data URL cannot bloat the request. */
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

export const ATTACHMENT_ACCEPT = [
  "text/*",
  ".md",
  ".mdx",
  ".json",
  ".csv",
  ".yaml",
  ".yml",
  ".log",
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/gif",
].join(",");

const TEXT_LIKE = /^(text\/|application\/(json|yaml|x-yaml)$)/;
const SUPPORTED_IMAGE_TYPES = new Set(
  ATTACHMENT_ACCEPT.split(",").filter((type) => type.startsWith("image/")),
);

export function isTextLike(name: string, contentType: string): boolean {
  if (TEXT_LIKE.test(contentType)) {
    return true;
  }
  return /\.(md|mdx|json|csv|ya?ml|txt|log)$/i.test(name);
}

export function isImageLike(contentType: string): boolean {
  return contentType.startsWith("image/");
}

/**
 * Why a dropped or pasted file cannot become an attachment, or null if it can.
 *
 * The file input already honours `accept`; a drop bypasses it, so the same
 * rule is applied here rather than letting an unreadable file become a chip
 * that promises content the model will never see.
 */
export function attachmentRejection(file: File): string | null {
  if (isImageLike(file.type)) {
    if (!SUPPORTED_IMAGE_TYPES.has(file.type)) {
      return `${file.name} is not an image the studio can read (PNG, JPEG, WebP, GIF).`;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      return `${file.name} is larger than ${Math.floor(MAX_IMAGE_BYTES / (1024 * 1024))} MB.`;
    }
    return null;
  }
  if (isTextLike(file.name, file.type)) {
    return null;
  }
  return `${file.name} is not a text or image file the studio can read.`;
}

/** A short size for an attachment chip; empty when there is nothing to say. */
export function formatFileSize(bytes: number): string {
  if (!bytes || bytes < 0) {
    return "";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error ?? new Error("Could not read the file."));
    reader.readAsDataURL(file);
  });
}

/**
 * Prepare one file for a turn. Never throws: an unreadable file becomes a
 * name-only attachment so the user can still see what they attached.
 */
export async function prepareAttachment(file: File): Promise<ChatAttachment> {
  const base: ChatAttachment = {
    id: crypto.randomUUID(),
    name: file.name,
    contentType: file.type || "application/octet-stream",
    size: file.size,
  };

  try {
    if (isImageLike(base.contentType) && file.size <= MAX_IMAGE_BYTES) {
      return { ...base, dataUrl: await readAsDataUrl(file) };
    }
    if (isTextLike(file.name, base.contentType)) {
      const text = await file.text();
      return { ...base, text: text.slice(0, MAX_ATTACHMENT_CHARS) };
    }
  } catch {
    /* a file we cannot read is still an attachment the user chose */
  }

  return base;
}

/**
 * The adapter the runtime uses for `ComposerPrimitive.Attachments`.
 *
 * Prepared attachments are kept by id so `onNew` can hand the turn the same
 * extraction the composer showed.
 */
export function createAttachmentAdapter(): AttachmentAdapter {
  return {
    accept: ATTACHMENT_ACCEPT,

    async add({ file }): Promise<PendingAttachment> {
      return {
        id: crypto.randomUUID(),
        type: isImageLike(file.type) ? "image" : file.type ? "document" : "file",
        name: file.name,
        contentType: file.type || "application/octet-stream",
        file,
        status: { type: "requires-action", reason: "composer-send" },
      };
    },

    async remove(): Promise<void> {
      // Nothing to release: the file never left the browser.
    },

    async send(attachment): Promise<CompleteAttachment> {
      const file = attachment.file;
      const ready = file
        ? await prepareAttachment(file)
        : {
            id: attachment.id,
            name: attachment.name,
            contentType: attachment.contentType ?? "application/octet-stream",
            size: 0,
          };
      ATTACHMENTS.set(attachment.id, ready);
      return {
        ...attachment,
        status: { type: "complete" },
        content: [
          {
            type: "file",
            data: attachment.id,
            mimeType: ready.contentType,
            filename: ready.name,
          },
        ],
      };
    },
  };
}

/** Process-wide, because the runtime adapter outlives a render. */
const ATTACHMENTS = new Map<string, ChatAttachment>();

/** The extraction for one attachment, for showing what was actually sent. */
export function preparedAttachmentById(id: string): ChatAttachment | undefined {
  return ATTACHMENTS.get(id);
}

/** The extraction for the attachments the runtime handed back on a send. */
export function preparedAttachments(
  attachments: readonly { id: string }[] | undefined,
): ChatAttachment[] {
  if (!attachments?.length) {
    return [];
  }
  return attachments.flatMap((attachment) => {
    const ready = ATTACHMENTS.get(attachment.id);
    return ready ? [ready] : [];
  });
}
