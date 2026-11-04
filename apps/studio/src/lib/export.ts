import {
  buildClaimBlocks,
  hideMarkers,
  type ClaimBlock,
  type ClaimSegment,
} from "../assistant/claims";
import type { ChatMessage, Claim, ClaimCitation } from "../types";
import {
  SCORE_FORMULA,
  SEED_WATERMARK,
  type DecisionBrief,
} from "./brief";
import { formatOpportunityScore } from "./odi";

const SPEAKER: Record<ChatMessage["role"], string> = {
  user: "User",
  assistant: "Assistant",
  notice: "Notice",
};

/** `Source · record name, record id`, built only from fields the reply holds. */
function recordLabel(citation: ClaimCitation): string {
  const name =
    citation.source_name && citation.name
      ? `${citation.source_name} · ${citation.name}`
      : citation.name || citation.source_name;
  if (name && citation.id) {
    return `${name}, record ${citation.id}`;
  }
  return name || (citation.id ? `record ${citation.id}` : "");
}

/** The same three distinctions the transcript draws, in the same words. */
function claimSuffix(claim: Claim): string {
  if (claim.status === "hypothesis") {
    return " (Hypothesis)";
  }
  if (claim.status === "uncited") {
    return " (Uncited)";
  }
  const records = claim.evidence.map(recordLabel).filter(Boolean);
  if (records.length === 0) {
    return " (cited, no record named)";
  }
  return ` (per ${records.join("; ")})`;
}

function segmentText(segment: ClaimSegment): string {
  if (!segment.claim) {
    return segment.text;
  }
  return `${segment.text}${claimSuffix(segment.claim)}`;
}

/** One parsed block, written back as the Markdown the transcript rendered. */
function blockLines(block: ClaimBlock): string[] {
  const items = block.items.map((item) => item.map(segmentText).join(""));
  if (block.kind === "code") {
    return ["```", ...items, "```", ""];
  }
  if (block.kind === "heading") {
    return [...items.map((item) => `### ${item.trim()}`), ""];
  }
  if (block.kind === "list") {
    return [...items.map((item) => `- ${item.trim()}`), ""];
  }
  return [...items.map((item) => item.trim()), ""];
}

/**
 * A claim-bearing reply, with every sentence carrying what it carried on screen.
 *
 * The prose arrives as syntax: markers around nothing a reader should see, and a
 * validated claim list beside it. `buildClaimBlocks` is the parser the transcript
 * itself uses, so the file cannot drift from what the person read.
 */
function claimsLines(content: string, claims: Claim[]): string[] {
  const blocks = buildClaimBlocks(content, claims);
  const emitted = new Set<number>();
  const lines: string[] = [];
  for (const block of blocks) {
    for (const item of block.items) {
      for (const segment of item) {
        if (segment.claim) {
          emitted.add(segment.claim.index);
        }
      }
    }
    lines.push(...blockLines(block));
  }
  // A claim the prose does not contain still has to reach the file. Losing an
  // answer is the failure this export exists to fix, so it travels as its own
  // line rather than vanishing with the sentence it could not be matched to —
  // but a sentence already on the page is not printed twice over a label that
  // would not attach.
  const printed = lines.join(" ").replace(/\s+/g, " ");
  for (const claim of claims) {
    if (emitted.has(claim.index)) {
      continue;
    }
    const sentence = claim.text
      .replace(/\s+/g, " ")
      .replace(/[.!?]+$/, "")
      .trim();
    if (sentence && printed.includes(sentence)) {
      continue;
    }
    lines.push(`${claim.text}${claimSuffix(claim)}`, "");
  }
  return lines;
}

/**
 * A conversation as Markdown.
 *
 * Threads die with the session, so the export has to stand on its own: every
 * speaker is labelled, prose keeps its Markdown, a cited sentence keeps its
 * citation, and an agent-composed surface travels as a fenced JSON block rather
 * than disappearing with the UI that rendered it.
 */
export function conversationToMarkdown(
  messages: ChatMessage[],
  exportedAt: Date = new Date(),
): string {
  const cites = messages.some((message) =>
    (message.parts ?? []).some((part) => part.kind === "claims"),
  );
  const lines: string[] = [
    "# Agentic ODI conversation",
    "",
    `_Exported ${exportedAt.toISOString().slice(0, 10)}._`,
    "",
  ];
  if (cites) {
    // A label is a snapshot of what the turn read, not a promise that the
    // record is still in the studio.
    lines.push(
      "_Citation labels name the record as it stood when the reply was written._",
      "",
    );
  }

  for (const message of messages) {
    lines.push(`## ${SPEAKER[message.role]}`, "");

    if (
      message.role === "assistant" &&
      message.parts &&
      message.parts.length > 0
    ) {
      const before = lines.length;
      const claimProse = new Set<string>();
      for (const part of message.parts) {
        if (part.kind === "claims") {
          claimProse.add(hideMarkers(part.content).trim());
        }
      }
      for (const part of message.parts) {
        if (part.kind === "text") {
          // Markers are syntax, and the finished claim list replaces the prose
          // it was streamed with — printing both would say the same thing twice.
          const prose = hideMarkers(part.text);
          if (prose.trim() && !claimProse.has(prose.trim())) {
            lines.push(prose, "");
          }
          continue;
        }
        if (part.kind === "claims") {
          lines.push(...claimsLines(part.content, part.claims));
          continue;
        }
        if (part.kind !== "ui") {
          // Reasoning and tool activity are the runtime's own; the transcript
          // carries what the user was shown.
          continue;
        }
        lines.push(
          `**Surface: \`${part.node.type}\`**`,
          "",
          "```json",
          JSON.stringify(part.node, null, 2),
          "```",
          "",
        );
      }
      if (lines.length === before && message.content.trim()) {
        lines.push(hideMarkers(message.content), "");
      }
    } else if (message.content.trim()) {
      lines.push(message.content, "");
    }

    if (message.error) {
      lines.push(`**Error:** ${message.error.message}`, "");
    }
  }

  return `${lines
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trimEnd()}\n`;
}

export function exportFilename(exportedAt: Date = new Date()): string {
  return `agentic-odi-conversation-${exportedAt.toISOString().slice(0, 10)}.md`;
}

const NOT_RECORDED = "Not recorded.";

const LOCAL_DATE = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

function plural(noun: string, count: number): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

/** A section always prints. A reader cannot tell an empty section from a lost one. */
function section(title: string, lines: string[]): string[] {
  return [`## ${title}`, "", ...(lines.length > 0 ? lines : [NOT_RECORDED]), ""];
}

const SOURCE_LABEL: Record<string, string> = {
  mcp: "your MCP server",
  seed: "the sample board shipped with the studio",
  local: "records captured in this studio",
};

function provenanceLines(brief: DecisionBrief): string[] {
  const { provenance } = brief;
  const lines: string[] = [];
  if (provenance.sample) {
    lines.push(`> ${SEED_WATERMARK}`, "");
  }
  lines.push(
    `- Source: ${
      provenance.source ? SOURCE_LABEL[provenance.source] ?? provenance.source : "not recorded"
    }.`,
    `- Counted for this brief: ${plural("outcome", provenance.counted_rows.outcomes)}, ${plural(
      "evidence record",
      provenance.counted_rows.evidence,
    )}.`,
  );
  const counts = provenance.record_counts;
  if (counts) {
    lines.push(
      `- The canvas reports: ${counts.jobs} jobs, ${counts.steps} steps, ${counts.outcomes} outcomes, ${counts.evidence} evidence records.`,
    );
  }
  if (provenance.cached) {
    lines.push(
      "- Built from a cached copy on this device; the snapshot may be stale.",
    );
  }
  if (provenance.sample) {
    lines.push(
      `- Sample rows are excluded from every number above: ${plural(
        "outcome",
        provenance.excluded_sample_rows.outcomes,
      )}, ${plural("evidence record", provenance.excluded_sample_rows.evidence)}.`,
    );
  }
  return lines;
}

function opportunityLine(id: string, statement: string, score: number | null): string {
  return `**${id || "unidentified"}** — ${statement || "no statement recorded"} (score ${formatOpportunityScore(score)})`;
}

function opportunityLines(brief: DecisionBrief): string[] {
  return brief.opportunities.flatMap((entry) => [
    `- ${opportunityLine(entry.id, entry.statement, entry.score)}`,
    `  - importance ${formatOpportunityScore(entry.importance)}, satisfaction ${formatOpportunityScore(
      entry.satisfaction,
    )}, ${plural("linked record", entry.evidence_count)}`,
  ]);
}

/** Records are quoted, not reproduced, and a deep link travels as a footnote. */
function evidenceLines(brief: DecisionBrief): string[] {
  const lines: string[] = [];
  const footnotes: string[] = [];

  for (const entry of brief.opportunities) {
    const head = opportunityLine(entry.id, entry.statement, entry.score);
    const shown = brief.evidence.filter((item) => item.outcome_id === entry.id);
    if (shown.length === 0) {
      lines.push(`- ${head} — no linked records.`);
      continue;
    }
    lines.push(`- ${head}`);
    for (const record of shown) {
      const marker = record.url
        ? ` [${footnotes.push(`- [${record.source_name}](${record.url})`)}]`
        : "";
      lines.push(
        `  - ${record.source_name} · ${record.item_type} · ${record.name} — "${record.excerpt}${
          record.truncated ? "…" : ""
        }"${marker}`,
      );
    }
    const hidden = entry.evidence_count - shown.length;
    if (hidden > 0) {
      lines.push(`  - ${plural("more linked record", hidden)} not shown`);
    }
  }

  if (footnotes.length > 0) {
    lines.push("", "**Footnotes**", "", ...footnotes.map((line, index) => `${index + 1}. ${line.slice(2)}`));
  }
  return lines;
}

function dissentLines(brief: DecisionBrief): string[] {
  if (brief.dissent.length === 0) {
    return ["No dissent recorded. This brief argues one side.", ""];
  }
  return brief.dissent.map((entry) => {
    const suffix =
      entry.source === "author"
        ? " (author-supplied)"
        : entry.stale
          ? " (no longer on the landscape)"
          : entry.source === "unlinked-evidence"
            ? " (not linked to a job)"
            : "";
    return `- ${entry.text}${suffix}`;
  });
}

function nextEvidenceLines(brief: DecisionBrief): string[] {
  const next = brief.next_evidence;
  if (!next) {
    return [];
  }
  const lines = [
    `- **${next.outcome_id}** — ${next.statement || "no statement recorded"} rests on ${plural(
      "record",
      next.evidence_count,
    )}.`,
  ];
  if (next.needs_connection) {
    lines.push("- No matching source in the catalog: connect a source to fill this.");
    return lines;
  }
  for (const preset of next.presets) {
    lines.push(`- Go and look at: ${preset.label} — ${preset.summary}`);
  }
  return lines;
}

/**
 * The decision brief as the document a review reads.
 *
 * One serializer on purpose: the sheet previews this exact string through the
 * same Markdown component the transcript uses, so what a person approves is what
 * the file contains. Sections never disappear — an empty one says "Not
 * recorded." so a reader can tell a gap from a loss.
 */
export function briefToMarkdown(brief: DecisionBrief): string {
  const generatedAt = new Date(brief.generated_at);
  const lines: string[] = [
    `# ${brief.product_name}`,
    "",
    `_Decision brief — ${LOCAL_DATE.format(
      Number.isNaN(generatedAt.getTime()) ? new Date() : generatedAt,
    )}_`,
    "",
    ...section("Provenance", provenanceLines(brief)),
    ...(brief.vision
      ? section("Vision", [brief.vision])
      : section("Vision", ["No vision recorded.", "", "Set it with `/start`."])),
    ...section(
      "The decision",
      brief.decision
        ? [
            `- ${opportunityLine(brief.decision.id, brief.decision.statement, brief.decision.score)}`,
            ...(brief.decision.rationale
              ? [`- Why this bet: "${brief.decision.rationale}"`]
              : []),
          ]
        : [],
    ),
    ...section("Top opportunities", opportunityLines(brief)),
    ...section("Evidence", evidenceLines(brief)),
    ...section("Dissent", dissentLines(brief)),
    ...section("Next evidence", nextEvidenceLines(brief)),
    ...section("Method", [
      `- Scores use \`${SCORE_FORMULA}\` and come from the \`Outcome\` records on the canvas, not from the model.`,
      "- Every number above counts records; nothing here is generated prose.",
    ]),
  ];

  return `${lines
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trimEnd()}\n`;
}

export function briefFilename(exportedAt: Date = new Date()): string {
  return `agentic-odi-decision-brief-${exportedAt.toISOString().slice(0, 10)}.md`;
}

/** Hand a Markdown file to the browser's save dialog. */
export function downloadMarkdown(markdown: string, filename: string): void {
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
