/**
 * A deliberately small Markdown subset for assistant messages.
 *
 * Models answer in Markdown (headings, bullets, bold, inline code, fenced
 * code), and rendering it as raw text was the single biggest visual gap in the
 * chat surface. This parser covers exactly what the studio needs so the app
 * stays dependency-free.
 */

export type MdInline =
  | { type: "text"; text: string }
  | { type: "strong"; text: string }
  | { type: "em"; text: string }
  | { type: "code"; text: string }
  | { type: "link"; text: string; href: string };

export type MdBlock =
  | { type: "paragraph"; spans: MdInline[] }
  | { type: "heading"; level: 1 | 2 | 3; spans: MdInline[] }
  | { type: "list"; ordered: boolean; start: number; items: MdInline[][] }
  | { type: "code"; language: string; code: string }
  | { type: "quote"; spans: MdInline[] }
  | { type: "rule" };

const HEADING = /^(#{1,3})\s+(.*)$/;
const RULE = /^\s*(-{3,}|\*{3,}|_{3,})\s*$/;
const FENCE = /^\s*```(\S*)\s*$/;
const QUOTE = /^\s*>\s?(.*)$/;
const ORDERED_ITEM = /^\s*(\d+)[.)]\s+(.*)$/;
const UNORDERED_ITEM = /^\s*[-*+]\s+(.*)$/;

const INLINE_PATTERN =
  /`([^`]+)`|\*\*([^*]+)\*\*|__([^_]+)__|\*([^*\n]+)\*|_([^_\n]+)_|\[([^\]]+)\]\(([^)\s]+)\)/g;

function pushText(spans: MdInline[], text: string): void {
  if (!text) {
    return;
  }
  const previous = spans[spans.length - 1];
  if (previous?.type === "text") {
    previous.text += text;
    return;
  }
  spans.push({ type: "text", text });
}

export function parseInline(source: string): MdInline[] {
  const spans: MdInline[] = [];
  let cursor = 0;

  INLINE_PATTERN.lastIndex = 0;
  for (let match = INLINE_PATTERN.exec(source); match; match = INLINE_PATTERN.exec(source)) {
    pushText(spans, source.slice(cursor, match.index));
    cursor = match.index + match[0].length;

    const [, code, strongStar, strongUnderscore, emStar, emUnderscore, linkText, href] = match;
    if (code !== undefined) {
      spans.push({ type: "code", text: code });
    } else if (strongStar !== undefined || strongUnderscore !== undefined) {
      spans.push({ type: "strong", text: strongStar ?? strongUnderscore ?? "" });
    } else if (emStar !== undefined || emUnderscore !== undefined) {
      spans.push({ type: "em", text: emStar ?? emUnderscore ?? "" });
    } else if (linkText !== undefined && href !== undefined) {
      spans.push({ type: "link", text: linkText, href });
    }
  }

  pushText(spans, source.slice(cursor));
  return spans;
}

function isBlockStart(line: string): boolean {
  return (
    FENCE.test(line) ||
    HEADING.test(line) ||
    RULE.test(line) ||
    QUOTE.test(line) ||
    ORDERED_ITEM.test(line) ||
    UNORDERED_ITEM.test(line)
  );
}

export function parseMarkdown(source: string): MdBlock[] {
  const blocks: MdBlock[] = [];
  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    if (!line.trim()) {
      index += 1;
      continue;
    }

    const fence = FENCE.exec(line);
    if (fence) {
      const language = fence[1] ?? "";
      const body: string[] = [];
      index += 1;
      while (index < lines.length && !/^\s*```\s*$/.test(lines[index])) {
        body.push(lines[index]);
        index += 1;
      }
      index += 1;
      blocks.push({ type: "code", language, code: body.join("\n") });
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      const level = Math.min(heading[1].length, 3) as 1 | 2 | 3;
      blocks.push({ type: "heading", level, spans: parseInline(heading[2]) });
      index += 1;
      continue;
    }

    if (RULE.test(line)) {
      blocks.push({ type: "rule" });
      index += 1;
      continue;
    }

    if (QUOTE.test(line)) {
      const parts: string[] = [];
      while (index < lines.length) {
        const quoted = QUOTE.exec(lines[index]);
        if (!quoted) {
          break;
        }
        parts.push(quoted[1]);
        index += 1;
      }
      blocks.push({ type: "quote", spans: parseInline(parts.join(" ")) });
      continue;
    }

    const ordered = ORDERED_ITEM.exec(line);
    const unordered = ordered ? null : UNORDERED_ITEM.exec(line);
    if (ordered || unordered) {
      const isOrdered = Boolean(ordered);
      const start = ordered ? Number(ordered[1]) : 1;
      const items: MdInline[][] = [];
      while (index < lines.length) {
        const current = lines[index];
        const nextOrdered = ORDERED_ITEM.exec(current);
        const nextUnordered = nextOrdered ? null : UNORDERED_ITEM.exec(current);
        if (isOrdered ? !nextOrdered : !nextUnordered) {
          break;
        }
        const text = (isOrdered ? nextOrdered?.[2] : nextUnordered?.[1]) ?? "";
        items.push(parseInline(text));
        index += 1;
      }
      blocks.push({ type: "list", ordered: isOrdered, start, items });
      continue;
    }

    const paragraph: string[] = [line.trim()];
    index += 1;
    while (index < lines.length && lines[index].trim() && !isBlockStart(lines[index])) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ type: "paragraph", spans: parseInline(paragraph.join(" ")) });
  }

  return blocks;
}
