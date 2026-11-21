/**
 * Reading a PDF in the browser.
 *
 * `pdfjs-dist` is used for its text layer only; a PDF whose text is pixels is
 * refused rather than sent as an empty attachment. Pages are the unit a reader
 * thinks in, so the extracted text carries an explicit `[page N]` marker and a
 * cut is announced in pages, not characters — the same contract `docx.ts` keeps
 * with `common.ts`, so a caller cannot tell which format ran.
 *
 * Nothing here decides how much text is enough: `MAX_EXTRACTED_CHARS` and the
 * truncation sentence come from `common.ts`, so both formats stop at the same
 * cap.
 */

import {
  ExtractionError,
  MAX_DOCUMENT_BYTES,
  MAX_EXTRACTED_CHARS,
  truncationSentence,
  type Extraction,
} from "./common";

/** The content type a browser reports for a `.pdf`, when it reports one. */
export const PDF_CONTENT_TYPE = "application/pdf";

/** What a scanned PDF says, so the reader knows the fix is on their side. */
export const PDF_NO_TEXT_LAYER_REFUSAL =
  "This PDF has no text layer — it looks scanned. Paste the passage or use a text export.";

/**
 * A `.pdf` is recognised by name first, then by the PDF content type.
 *
 * The name is the stronger signal: browsers report PDFs with a handful of
 * types, and a `.pdf` that arrives mislabelled should still be read.
 */
export function isPdfLike(name: string, contentType: string): boolean {
  if (/\.pdf$/i.test(name)) {
    return true;
  }
  return contentType === PDF_CONTENT_TYPE;
}

/** The sentence for a PDF larger than the browser will read, naming the limit. */
export function pdfTooLargeMessage(fileName: string): string {
  return `${fileName} is larger than ${Math.floor(MAX_DOCUMENT_BYTES / (1024 * 1024))} MB — too large to read in the browser.`;
}

/**
 * The text of one PDF, page-marked, capped by whole pages, and announced.
 *
 * Throws `ExtractionError` with a named sentence for each way a PDF cannot
 * become text — encrypted, oversized, corrupt, or scanned with no text layer —
 * rather than returning an empty string that would reach the model as a blank
 * attachment.
 */
export async function extractPdf(file: File): Promise<Extraction> {
  if (file.size > MAX_DOCUMENT_BYTES) {
    throw new ExtractionError(pdfTooLargeMessage(file.name));
  }

  const pdfjs = await loadPdfjs();
  let doc: PdfDocument;
  try {
    doc = await pdfjs.getDocument({
      data: new Uint8Array(await file.arrayBuffer()),
      // No `eval` of embedded JS: a document is untrusted input, and the text
      // layer never needs it.
      isEvalSupported: false,
    }).promise;
  } catch (error) {
    const name = (error as { name?: string } | null)?.name;
    if (name === "PasswordException") {
      throw new ExtractionError(
        `${file.name} is password-protected, so its text cannot be read. Remove the password and attach it again.`,
      );
    }
    throw new ExtractionError(
      `${file.name} could not be read as a PDF. If it opens in a viewer, export it again and try that copy.`,
    );
  }

  const pages: string[] = [];
  let sawText = false;
  for (let number = 1; number <= doc.numPages; number += 1) {
    const page = await doc.getPage(number);
    const content = await page.getTextContent();
    const body = pageText(content.items);
    if (body) {
      sawText = true;
    }
    pages.push(`[page ${number}]\n${body}`);
  }

  const { text, dropped } = keepWholePages(pages);
  if (!sawText) {
    throw new ExtractionError(`${file.name}: ${PDF_NO_TEXT_LAYER_REFUSAL}`);
  }
  if (dropped > 0) {
    return {
      text: `${text}\n\n${truncationSentence(dropped, "pages")}`,
      truncated: true,
    };
  }
  return { text, truncated: false };
}

/** One page's text: items joined, whitespace collapsed, paragraph breaks kept. */
function pageText(items: PdfTextItem[]): string {
  let raw = "";
  for (const item of items) {
    if (typeof item.str !== "string") {
      continue;
    }
    raw += item.str;
    raw += item.hasEOL ? "\n" : " ";
  }
  return raw
    .replace(/[ \t]+/g, " ")
    .replace(/ *\n */g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/**
 * Keep the largest whole-page prefix that fits the shared cap.
 *
 * A page is kept or dropped, never cut in half: a partial page would arrive at
 * the model as a sentence that stops mid-thought with no sign of why. The
 * separator between pages is counted too, so the kept text plus its markers
 * never exceeds the cap.
 */
function keepWholePages(pages: string[]): { text: string; dropped: number } {
  const kept: string[] = [];
  let length = 0;
  for (let index = 0; index < pages.length; index += 1) {
    const addition = (kept.length ? 2 : 0) + pages[index].length;
    if (length + addition > MAX_EXTRACTED_CHARS) {
      return { text: kept.join("\n\n"), dropped: pages.length - index };
    }
    kept.push(pages[index]);
    length += addition;
  }
  return { text: kept.join("\n\n"), dropped: 0 };
}

/**
 * The pdfjs module with its worker configured for the runtime at hand.
 *
 * In a browser the worker is the bundled module URL Vite emits. Under jsdom
 * (the unit suite) there is no `Worker`, so pdfjs falls back to a fake worker
 * that imports `workerSrc` as a module — which only resolves as the bare
 * package specifier, not a served URL. The check is on the environment's
 * capability, not on a test flag.
 */
async function loadPdfjs(): Promise<PdfjsModule> {
  const pdfjs = (await import("pdfjs-dist/legacy/build/pdf.mjs")) as PdfjsModule;
  if (typeof Worker === "undefined") {
    pdfjs.GlobalWorkerOptions.workerSrc = "pdfjs-dist/legacy/build/pdf.worker.min.mjs";
  } else {
    const workerUrl = (await import("pdfjs-dist/legacy/build/pdf.worker.min.mjs?url")).default;
    pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
  }
  return pdfjs;
}

interface PdfTextItem {
  str?: string;
  hasEOL?: boolean;
}

interface PdfPage {
  getTextContent(): Promise<{ items: PdfTextItem[] }>;
}

interface PdfDocument {
  numPages: number;
  getPage(number: number): Promise<PdfPage>;
}

interface PdfjsModule {
  GlobalWorkerOptions: { workerSrc: string };
  getDocument(options: { data: Uint8Array; isEvalSupported: boolean }): {
    promise: Promise<PdfDocument>;
  };
}
