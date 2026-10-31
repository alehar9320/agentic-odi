/**
 * Reading a reply that carries claims.
 *
 * The sidecar sends prose with `[[ev:…]]` / `[[hypothesis]]` markers plus a
 * validated claim list. Markers are syntax, never something a reader should
 * see, so this module hides them — including a marker split across two streamed
 * chunks — and slices the prose so each sentence keeps its own chip.
 */

import type { Claim } from "../types";

const COMPLETE_MARKER = /\[\[(?:ev:[^\]]*|hypothesis)\]\]/gi;

/** A marker name we might be halfway through receiving. */
const PARTIAL_MARKER =
  /^(?:e|ev|ev:[A-Za-z0-9_., -]*|h|hy|hyp|hypo|hypot|hypoth|hypothe|hypothes|hypothesi|hypothesis)$/;

function stripMarkers(text: string, allowPartial: boolean): string {
  const stripped = text.replace(COMPLETE_MARKER, "");
  if (!allowPartial) {
    return stripped;
  }
  const open = stripped.lastIndexOf("[[");
  if (open === -1) {
    return stripped;
  }
  const tail = stripped.slice(open + 2);
  if (tail.includes("]]") || tail.includes("\n") || !PARTIAL_MARKER.test(tail)) {
    return stripped;
  }
  return stripped.slice(0, open);
}

/**
 * Remove claim markers from display text, keeping a half-arrived one hidden.
 *
 * A marker inside inline code or a fence is literal, and so is the rest of a
 * fence: only prose is syntax.
 */
export function hideMarkers(text: string): string {
  const lines = text.split("\n");
  let fenced = false;
  return lines
    .map((line, lineIndex) => {
      if (line.trim().startsWith("```")) {
        fenced = !fenced;
        return line;
      }
      if (fenced) {
        return line;
      }
      const parts = line.split("`");
      return parts
        .map((part, partIndex) => {
          // Odd segments sit between backticks: inline code, not prose.
          if (partIndex % 2 === 1) {
            return part;
          }
          const last = lineIndex === lines.length - 1 && partIndex === parts.length - 1;
          return stripMarkers(part, last);
        })
        .join("`");
    })
    .join("\n");
}

export type ClaimBlockKind = "paragraph" | "heading" | "code" | "list";

/** One run of text, and the claim it belongs to when it is a declarative sentence. */
export interface ClaimSegment {
  text: string;
  claim: Claim | null;
}

/** A rendered block: a paragraph, a heading, a code fence, or a list item. */
export interface ClaimBlock {
  kind: ClaimBlockKind;
  items: ClaimSegment[][];
}

interface RawBlock {
  kind: ClaimBlockKind;
  items: string[];
}

const LIST_ITEM = /^\s*(?:[-*+]|\d+[.)])\s+/;
const HEADING = /^\s*#{1,6}\s+/;

/** Split prose into blocks the renderer can mount without a Markdown pass. */
export function splitBlocks(content: string): RawBlock[] {
  const blocks: RawBlock[] = [];
  let buffer: string[] = [];
  let fence: string[] | null = null;

  const flush = () => {
    const text = buffer.join("\n").trim();
    buffer = [];
    if (text) {
      blocks.push({ kind: "paragraph", items: [text] });
    }
  };

  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (fence) {
      if (trimmed.startsWith("```")) {
        blocks.push({ kind: "code", items: [fence.join("\n")] });
        fence = null;
      } else {
        fence.push(line);
      }
      continue;
    }
    if (trimmed.startsWith("```")) {
      flush();
      fence = [];
      continue;
    }
    if (!trimmed) {
      flush();
      continue;
    }
    if (HEADING.test(line)) {
      flush();
      blocks.push({ kind: "heading", items: [line.replace(HEADING, "")] });
      continue;
    }
    if (LIST_ITEM.test(line)) {
      flush();
      const item = line.replace(LIST_ITEM, "");
      const last = blocks[blocks.length - 1];
      if (last?.kind === "list") {
        last.items.push(item);
      } else {
        blocks.push({ kind: "list", items: [item] });
      }
      continue;
    }
    buffer.push(line);
  }

  if (fence) {
    blocks.push({ kind: "code", items: [fence.join("\n")] });
  }
  flush();
  return blocks;
}

function collapseWithMap(text: string): { collapsed: string; map: number[] } {
  let collapsed = "";
  const map: number[] = [];
  let lastWasSpace = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (/\s/.test(character)) {
      if (!lastWasSpace) {
        collapsed += " ";
        map.push(index);
      }
      lastWasSpace = true;
      continue;
    }
    collapsed += character;
    map.push(index);
    lastWasSpace = false;
  }
  return { collapsed, map };
}

/**
 * Where a claim's sentence sits in a block.
 *
 * A marker removed from the middle of a sentence leaves a double space, so a
 * direct match is tried first and a whitespace-insensitive one second.
 */
function locate(item: string, needle: string, from: number): [number, number] | null {
  const direct = item.indexOf(needle, from);
  if (direct !== -1) {
    return [direct, direct + needle.length];
  }
  const target = needle.replace(/\s+/g, " ").trim();
  if (!target) {
    return null;
  }
  const { collapsed, map } = collapseWithMap(item);
  let searchFrom = 0;
  while (searchFrom < map.length && map[searchFrom] < from) {
    searchFrom += 1;
  }
  const found = collapsed.indexOf(target, searchFrom);
  if (found === -1) {
    return null;
  }
  return [map[found], map[found + target.length - 1] + 1];
}

function segmentItem(
  item: string,
  claims: Claim[],
  state: { next: number },
): ClaimSegment[] {
  const segments: ClaimSegment[] = [];
  let cursor = 0;

  while (state.next < claims.length) {
    const claim = claims[state.next];
    const found = locate(item, claim.text, cursor);
    if (!found) {
      break;
    }
    const [start, end] = found;
    if (start > cursor) {
      const plain = item.slice(cursor, start);
      segments.push({ text: plain.trim() ? plain : " ", claim: null });
    }
    segments.push({ text: claim.text, claim });
    cursor = end;
    state.next += 1;
  }

  const tail = item.slice(cursor);
  if (tail.trim()) {
    segments.push({ text: tail, claim: null });
  }
  return segments;
}

/** The reply, cut so every claim's chip lands after its own sentence. */
export function buildClaimBlocks(content: string, claims: Claim[]): ClaimBlock[] {
  const state = { next: 0 };
  return splitBlocks(hideMarkers(content)).map((block) => ({
    kind: block.kind,
    items: block.items.map((item) =>
      block.kind === "code" || block.kind === "heading"
        ? [{ text: item, claim: null }]
        : segmentItem(item, claims, state),
    ),
  }));
}

/** How many chips a reader can count: a seeded demo reply never counts. */
export function citedCount(claims: Claim[], seeded: boolean): number {
  if (seeded) {
    return 0;
  }
  return claims.filter((claim) => claim.status === "cited").length;
}

// -- returning focus after a panel closes ---------------------------------

let lastClaimChip: HTMLElement | null = null;

/** Remember the chip that opened a record, so Escape can come back to it. */
export function rememberClaimChip(element: HTMLElement | null): void {
  lastClaimChip = element;
}

/** Put focus back where the reader left it. */
export function focusLastClaimChip(): void {
  lastClaimChip?.focus();
}
