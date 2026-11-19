/**
 * Turning a dropped file into something the model can actually read.
 *
 * The client owns this because only the client has the bytes: the sidecar
 * receives extracted text (or a data URL for an image), never a file handle.
 * Extraction is bounded so one large attachment cannot crowd out the
 * conversation, and a file whose bytes never became content is reported as a
 * failed attachment before the turn is sent rather than as an empty one.
 */

import type {
  AttachmentAdapter,
  CompleteAttachment,
  PendingAttachment,
} from "@assistant-ui/react";

import type { ChatAttachment } from "../types";
import { MAX_EXTRACTED_CHARS, MAX_DOCUMENT_BYTES, ExtractionError } from "./extract/common";
import {
  DOCX_CONTENT_TYPE,
  LEGACY_DOC_REFUSAL,
  extractDocx,
  isDocxLike,
  isLegacyDoc,
} from "./extract/docx";
import { PDF_CONTENT_TYPE, extractPdf, isPdfLike, pdfTooLargeMessage } from "./extract/pdf";

/** How much of a text file the model sees. Shared with the document formats. */
export const MAX_ATTACHMENT_CHARS = MAX_EXTRACTED_CHARS;

/** How many attachments a turn may carry, counting text and images together. */
export const MAX_ATTACHMENTS = 5;

/** The largest document we will try to read, re-exported for the composer. */
export { MAX_DOCUMENT_BYTES } from "./extract/common";

/** A single image, bounded so a data URL cannot bloat the request. */
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

/** What a chip says when the bytes never became content. */
export const ATTACHMENT_READ_FAILURE = "Could not read this file";

/** What a chip says when a text file is longer than the per-file cap. */
export function tooLargeMessage(fileName: string): string {
  return `${fileName} is larger than the ${MAX_ATTACHMENT_CHARS.toLocaleString("en-US")}-character limit`;
}

export const ATTACHMENT_ACCEPT = [
  "text/*",
  ".md",
  ".mdx",
  ".json",
  ".csv",
  ".yaml",
  ".yml",
  ".log",
  ".docx",
  DOCX_CONTENT_TYPE,
  ".pdf",
  PDF_CONTENT_TYPE,
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
  if (isLegacyDoc(file.name, file.type)) {
    return `${file.name}: ${LEGACY_DOC_REFUSAL}`;
  }
  if (isDocxLike(file.name, file.type)) {
    if (file.size > MAX_DOCUMENT_BYTES) {
      return `${file.name} is larger than ${Math.floor(MAX_DOCUMENT_BYTES / (1024 * 1024))} MB.`;
    }
    return null;
  }
  if (isPdfLike(file.name, file.type)) {
    if (file.size > MAX_DOCUMENT_BYTES) {
      return pdfTooLargeMessage(file.name);
    }
    return null;
  }
  if (isTextLike(file.name, file.type)) {
    return null;
  }
  return `${file.name} is not a text, Word, PDF, or image file the studio can read.`;
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
 * A file the studio was handed but could not turn into content.
 *
 * `name` carries the file's name so a chip can say which file failed without
 * reaching for the original. `refused` carries a sentence the reader can act on
 * — an encrypted PDF, a scan with no text layer — where `unreadable` is the
 * generic "we could not read this" and `too_large` names the character limit.
 */
export class AttachmentReadError extends Error {
  readonly code: "unreadable" | "too_large" | "refused";

  constructor(
    fileName: string,
    code: "unreadable" | "too_large" | "refused" = "unreadable",
    sentence?: string,
  ) {
    super(
      sentence ??
        (code === "too_large" ? tooLargeMessage(fileName) : `Could not read ${fileName}.`),
    );
    this.name = fileName;
    this.code = code;
  }
}

/**
 * Prepare one file for a turn.
 *
 * Throws `AttachmentReadError` when the bytes do not become content: a name-only
 * attachment would promise a file the model never receives. A text file longer
 * than the per-file cap is refused rather than silently shortened, because the
 * person would otherwise send an interview transcript believing all of it
 * arrived. `.docx` is capped with the cut announced in the extracted text, the
 * same contract the document formats share.
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
    if (isDocxLike(file.name, base.contentType) && file.size <= MAX_DOCUMENT_BYTES) {
      const { text } = await extractDocx(file);
      return { ...base, text };
    }
    if (isPdfLike(file.name, base.contentType) && file.size <= MAX_DOCUMENT_BYTES) {
      const { text } = await extractPdf(file);
      return { ...base, text };
    }
    if (isTextLike(file.name, base.contentType)) {
      const text = await file.text();
      if (text.length > MAX_ATTACHMENT_CHARS) {
        throw new AttachmentReadError(base.name, "too_large");
      }
      return { ...base, text };
    }
  } catch (error) {
    if (error instanceof AttachmentReadError) {
      throw error;
    }
    if (error instanceof ExtractionError) {
      throw new AttachmentReadError(base.name, "refused", error.sentence);
    }
    throw new AttachmentReadError(base.name);
  }

  throw new AttachmentReadError(base.name);
}

/**
 * The adapter the runtime uses for `ComposerPrimitive.Attachments`.
 *
 * The file is read when it is added, not when the turn is sent, so a file that
 * cannot be read shows as a failed chip instead of an empty attachment. `add` is
 * a generator because that is the form assistant-ui drains into one chip whose
 * status can change; the extraction is cached by the attachment id, so `send`
 * never reads the file a second time.
 */
export function createAttachmentAdapter(): AttachmentAdapter {
  return {
    accept: ATTACHMENT_ACCEPT,

    async *add({ file }): AsyncGenerator<PendingAttachment, void> {
      const id = crypto.randomUUID();
      const chip = (status: PendingAttachment["status"]): PendingAttachment => ({
        id,
        type: isImageLike(file.type) ? "image" : file.type ? "document" : "file",
        name: file.name,
        contentType: file.type || "application/octet-stream",
        file,
        status,
      });

      try {
        ATTACHMENTS.set(id, await prepareAttachment(file));
      } catch (error) {
        if (!(error instanceof AttachmentReadError)) {
          throw error;
        }
        // The chip carries the reason, so an oversized text file says which
        // file and which limit, and a refused PDF says why, rather than the
        // generic read failure.
        yield chip({
          type: "incomplete",
          reason: "error",
          message: error.code === "unreadable" ? ATTACHMENT_READ_FAILURE : error.message,
        });
        return;
      }

      yield chip({ type: "requires-action", reason: "composer-send" });
    },

    async remove(): Promise<void> {
      // Nothing to release: the file never left the browser.
    },

    async send(attachment): Promise<CompleteAttachment> {
      const ready =
        ATTACHMENTS.get(attachment.id) ??
        (attachment.file
          ? await prepareAttachment(attachment.file)
          : {
              id: attachment.id,
              name: attachment.name,
              contentType: attachment.contentType ?? "application/octet-stream",
              size: 0,
            });
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
