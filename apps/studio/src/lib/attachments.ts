/**
 * Files the reader hands the studio.
 *
 * A file is only worth attaching if the model can actually read it, so the same
 * rules the sidecar enforces are applied here first, in words the reader can act
 * on. Nothing is ever sent as a filename alone: the bytes travel with the turn.
 */

import type { ChatAttachmentPayload } from "../types";

/** One turn's upload must stay bounded; base64 adds a third to every byte. */
export const MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024;
export const MAX_ATTACHMENTS = 6;

/** Text-bearing types with no `text/` prefix that are still safe to inline. */
export const INLINE_MEDIA_TYPES = new Set([
  "application/json",
  "application/xml",
  "application/yaml",
  "application/x-yaml",
  "application/toml",
  "application/csv",
  "application/x-ndjson",
  "application/sql",
]);

/** A file waiting to be sent, with what the transcript needs to show it. */
export interface StagedAttachment extends ChatAttachmentPayload {
  id: string;
  size: number;
  /** An object URL for an image, so the reader can check it before sending. */
  preview_url?: string;
}

export function mediaTypeOf(file: { type: string }): string {
  return (file.type || "").split(";")[0].trim().toLowerCase();
}

export function isImage(attachment: { media_type: string }): boolean {
  return (attachment.media_type || "").split(";")[0].trim().toLowerCase().startsWith("image/");
}

export function isReadable(file: { type: string }): boolean {
  const media = mediaTypeOf(file);
  return media.startsWith("image/") || media.startsWith("text/") || INLINE_MEDIA_TYPES.has(media);
}

/**
 * Why this file cannot be attached, or null when it can. `staged` is how many
 * files are already waiting, so the count limit is enforced before reading.
 */
export function attachmentProblem(
  file: { name: string; type: string; size: number },
  staged: number,
): string | null {
  if (staged >= MAX_ATTACHMENTS) {
    return `Attach up to ${MAX_ATTACHMENTS} files at a time.`;
  }
  if (!isReadable(file)) {
    const media = mediaTypeOf(file) || "unknown";
    return `${file.name} is ${media === "unknown" ? "an untyped file" : `a ${media} file`}. Attach an image or a text file.`;
  }
  if (file.size === 0) {
    return `${file.name} is empty.`;
  }
  if (file.size > MAX_ATTACHMENT_BYTES) {
    return `${file.name} is larger than ${MAX_ATTACHMENT_BYTES / (1024 * 1024)} MB.`;
  }
  return null;
}

let sequence = 0;

/**
 * Read a file into the shape the sidecar expects: base64 bytes plus the media
 * type, never a path. Images keep an object URL for the preview; the caller owns
 * revoking it.
 */
export function readAttachment(file: File): Promise<StagedAttachment> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`));
    reader.onload = () => {
      const result = String(reader.result ?? "");
      const comma = result.indexOf(",");
      const data = comma === -1 ? "" : result.slice(comma + 1);
      if (!data) {
        reject(new Error(`Could not read ${file.name}.`));
        return;
      }
      sequence += 1;
      const media_type = mediaTypeOf(file);
      resolve({
        id: `${file.name}-${file.lastModified}-${sequence}`,
        name: file.name,
        media_type,
        data,
        size: file.size,
        ...(media_type.startsWith("image/") ? { preview_url: URL.createObjectURL(file) } : {}),
      });
    };
    reader.readAsDataURL(file);
  });
}

/** Drop the preview, and nothing else, when a staged file leaves the tray. */
export function releaseAttachment(attachment: StagedAttachment): void {
  if (attachment.preview_url) {
    URL.revokeObjectURL(attachment.preview_url);
  }
}

/** What goes on the wire: no ids, no previews, no sizes. */
export function toPayload(attachment: StagedAttachment): ChatAttachmentPayload {
  return {
    name: attachment.name,
    media_type: attachment.media_type,
    data: attachment.data,
  };
}

/** A short, human size for a chip. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
