/**
 * A quoted passage, carried into the next question.
 *
 * The sidecar persists a turn's text, not a separate quote record, so the quote
 * travels as a Markdown blockquote at the top of the user's message. That keeps
 * it verbatim, names where it came from, survives a reload for the same reason
 * the rest of the turn does, and reaches the model as part of the question — no
 * message-model or sidecar change.
 */

export interface ComposerQuote {
  text: string;
  messageId: string;
}

/** The attribution a quote carries when its reply had no speaker name. */
export const QUOTE_ATTRIBUTION = "the assistant's reply";

export function textWithQuote(text: string, quote?: ComposerQuote | null): string {
  const passage = quote?.text.trim();
  if (!passage) {
    return text;
  }

  const quoted = passage
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => (line ? `> ${line}` : ">"))
    .join("\n");

  const question = text.trim();
  return `${quoted}\n> — ${QUOTE_ATTRIBUTION}${question ? `\n\n${question}` : ""}`;
}
