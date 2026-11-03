/**
 * The one extraction contract every document format shares.
 *
 * PDF and DOCX are read by different libraries, but a caller — the composer,
 * the attachment record, the tests — must not be able to tell which one ran.
 * So the cap, the size limit, and the sentence that announces a cut live here
 * and nowhere else; a format module extracts raw text and hands it to
 * `capExtracted`, which returns the same shape for both.
 */

/** How much extracted text the model sees, whatever the source format. */
export const MAX_EXTRACTED_CHARS = 20_000;

/** The largest document we will even try to read. */
export const MAX_DOCUMENT_BYTES = 25 * 1024 * 1024;

/** What one format module returns: text plus whether the source was cut. */
export interface Extraction {
  text: string;
  /** True when the source held more than the cap and `text` is a prefix of it. */
  truncated: boolean;
}

/**
 * One sentence naming what was left out, appended to the extracted text.
 *
 * The unit is the format's own — pages for a PDF, characters for DOCX — so the
 * notice says what the reader lost in the terms of the document they attached.
 */
export function truncationSentence(dropped: number, unit: string): string {
  return `[Truncated: ${dropped.toLocaleString()} ${unit} were left out — the extracted text is capped at ${MAX_EXTRACTED_CHARS.toLocaleString()} characters.]`;
}

/**
 * Bound extracted text to the shared cap.
 *
 * Whole characters, not words, and the notice is part of the returned text, so
 * the model is told it is reading a prefix rather than quietly missing an end.
 */
export function capExtracted(text: string): Extraction {
  if (text.length <= MAX_EXTRACTED_CHARS) {
    return { text, truncated: false };
  }
  const kept = text.slice(0, MAX_EXTRACTED_CHARS);
  const dropped = text.length - kept.length;
  return {
    text: `${kept}\n\n${truncationSentence(dropped, "characters")}`,
    truncated: true,
  };
}
