/**
 * Reading a Word document in the browser.
 *
 * `mammoth` is used through `extractRawText` only. Its HTML converter would
 * reintroduce markup we would then have to sanitise before the model sees it;
 * raw text is the same shape a pasted note arrives in, which is the point.
 *
 * Nothing here decides how much text is enough — that is `capExtracted` in
 * `common.ts`, so DOCX and PDF truncate and announce truncation identically.
 */

import mammoth from "mammoth";

import { capExtracted, type Extraction } from "./common";

/** The OOXML content type a browser reports for a `.docx`, when it reports one. */
export const DOCX_CONTENT_TYPE =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

/** The legacy binary Word type. We name it so we can refuse it in words. */
export const LEGACY_DOC_CONTENT_TYPE = "application/msword";

/**
 * Why a `.doc` cannot be read, in the user's terms.
 *
 * The old binary format is not OOXML, so no amount of unzipping reaches the
 * text; the fix is on the user's side, so the sentence says what to do.
 */
export const LEGACY_DOC_REFUSAL =
  "Save it as .docx or .txt first — the old binary format is not supported.";

/**
 * A `.docx` is recognised by name first, then by the OOXML type.
 *
 * The name is the stronger signal: browsers report Word files with a handful of
 * types, and a `.docx` that arrives mislabelled should still be read. The type
 * is only consulted when the name carries no extension at all.
 */
export function isDocxLike(name: string, contentType: string): boolean {
  if (/\.docx$/i.test(name)) {
    return true;
  }
  if (/\.doc$/i.test(name)) {
    return false;
  }
  return contentType === DOCX_CONTENT_TYPE;
}

/** The legacy format, by name first, then by the type Word registers for it. */
export function isLegacyDoc(name: string, contentType: string): boolean {
  if (/\.docx$/i.test(name)) {
    return false;
  }
  if (/\.doc$/i.test(name)) {
    return true;
  }
  return contentType === LEGACY_DOC_CONTENT_TYPE;
}

/** Extraction failed for a reason the user can act on, named in a sentence. */
export class ExtractionError extends Error {
  constructor(public readonly sentence: string) {
    super(sentence);
    this.name = "ExtractionError";
  }
}

/**
 * The text of one `.docx`, capped and announced through the shared contract.
 *
 * Throws `ExtractionError` with a named sentence when the file cannot be read
 * — a corrupt archive, or a document whose text is empty — rather than
 * returning an empty string that would reach the model as a blank attachment.
 */
export async function extractDocx(file: File): Promise<Extraction> {
  let raw: string;
  try {
    const arrayBuffer = await file.arrayBuffer();
    // Both shapes are passed on purpose. Mammoth's browser build reads
    // `arrayBuffer`; its node build — which vitest resolves — reads `buffer`.
    // Each ignores the other's key, so one call works in both, and the cast
    // names the argument mammoth wants without importing an unexported type.
    const result = await mammoth.extractRawText({
      arrayBuffer,
      buffer: new Uint8Array(arrayBuffer),
    } as unknown as Parameters<typeof mammoth.extractRawText>[0]);
    raw = result.value;
  } catch {
    throw new ExtractionError(
      `${file.name} could not be read as a Word document. If it is open in Word, save a fresh copy and try again.`,
    );
  }

  // Mammoth separates paragraphs with a blank line and leaves headers and
  // footers out of the raw text, so no extra joining or stripping is needed.
  const text = raw.trim();
  if (!text) {
    throw new ExtractionError(
      `${file.name} has no text this studio can read. Save it as .docx or paste the passage instead.`,
    );
  }
  return capExtracted(text);
}
