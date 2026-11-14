/**
 * One renderer per message part.
 *
 * Each component reads only the scoped part it was mounted for, so a slow or
 * broken surface cannot take the rest of the transcript with it. Nothing here
 * knows where the data came from; the conversion in `convert.ts` already
 * decided what each part means.
 */

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useAuiState, type ToolCallMessagePartProps } from "@assistant-ui/react";

import { formatFileSize, preparedAttachmentById } from "./attachments";
import { CheckIcon, ChevronDownIcon, SparkIcon } from "../components/icons";
import { Markdown } from "../components/chat/Markdown";
import { useStudio } from "../state/StudioContext";
import type { Claim } from "../types";
import type { UiNode } from "../ui/protocol";
import { UiRenderer } from "../ui/UiRenderer";
import {
  buildClaimBlocks,
  citedCount,
  hideMarkers,
  rememberClaimChip,
  type ClaimSegment,
} from "./claims";
import { CLAIMS_PART, SURFACE_PART, isArguments } from "./convert";
import { describeConsequence } from "./consequence";
import { ClaimCitation } from "../components/chat/ClaimCitation";

/** Prose. The existing renderer, so the transcript reads exactly as before. */
export function TextPart() {
  const text = useAuiState((state) => (state.part.type === "text" ? state.part.text : null));
  if (text === null) {
    return null;
  }
  // A marker is syntax, not prose: hide it even while the reply streams.
  return <Markdown source={hideMarkers(text)} />;
}

/**
 * One assistant reply with a chip, a tag, or an underline per sentence.
 *
 * The chip names the record — source and name — never the tool that ran. A
 * sentence the agent could not ground keeps its place and says so.
 */
export function ClaimText({ content, claims }: { content: string; claims: Claim[] }) {
  const { canvas, closePanel, focusEvidence } = useStudio();
  const seeded = canvas?.source === "seed";
  const blocks = useMemo(() => buildClaimBlocks(content, claims), [content, claims]);
  const ordinals = useMemo(() => {
    const order = new Map<number, number>();
    let next = 0;
    for (const block of blocks) {
      for (const item of block.items) {
        for (const segment of item) {
          if (segment.claim?.status === "cited") {
            next += 1;
            order.set(segment.claim.index, next);
          }
        }
      }
    }
    return order;
  }, [blocks]);
  const known = useMemo(() => {
    const evidence = canvas?.evidence;
    return evidence ? new Set(evidence.map((item) => item.id)) : null;
  }, [canvas]);
  const cited = citedCount(claims, seeded);

  const renderSegments = (segments: ClaimSegment[]) =>
    segments.map((segment, index) => {
      const claim = segment.claim;
      if (!claim) {
        return <span key={index}>{segment.text}</span>;
      }
      if (claim.status === "hypothesis") {
        return (
          <span key={index} className="claim claim--hypothesis">
            {claim.text} <span className="claim-tag">Hypothesis</span>
          </span>
        );
      }
      if (claim.status === "uncited") {
        return (
          <span
            key={index}
            className="claim claim--uncited"
            title="No record supports this sentence."
          >
            {claim.text} <span className="sr-only">Uncited claim.</span>
          </span>
        );
      }
      return (
        <span key={index} className="claim claim--cited">
          <ClaimCitation claim={claim} onOpenRecord={focusEvidence} />
          {claim.evidence.map((citation) => {
            const label = citation.source_name
              ? `${citation.source_name} · ${citation.name}`
              : citation.name;
            if (known !== null && !known.has(citation.id)) {
              return (
                <span
                  key={citation.id}
                  className="claim-chip claim-chip--missing"
                  title={`${label} — this record is no longer in the studio.`}
                >
                  <span className="claim-chip__label">{label}</span>
                  <span className="sr-only">This record is no longer in the studio.</span>
                </span>
              );
            }
            return (
              <button
                key={citation.id}
                type="button"
                className="claim-chip"
                title={`${label} — open this record`}
                onClick={(event) => {
                  rememberClaimChip(event.currentTarget);
                  focusEvidence(citation.id);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    closePanel();
                  }
                }}
              >
                <span className="claim-chip__label">{label}</span>
                <sup className="claim-chip__order" aria-hidden="true">
                  {ordinals.get(claim.index) ?? 0}
                </sup>
                {seeded ? <span className="claim-chip__sample">Sample</span> : null}
              </button>
            );
          })}
        </span>
      );
    });

  return (
    <div className="claim-text">
      {blocks.map((block, index) => {
        if (block.kind === "code") {
          return (
            <pre key={index} className="claim-text__code">
              <code>{block.items[0]?.[0]?.text ?? ""}</code>
            </pre>
          );
        }
        if (block.kind === "heading") {
          return (
            <p key={index} className="claim-text__heading">
              {block.items[0]?.[0]?.text}
            </p>
          );
        }
        if (block.kind === "list") {
          return (
            <ul key={index} className="claim-text__list">
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderSegments(item)}</li>
              ))}
            </ul>
          );
        }
        return <p key={index}>{renderSegments(block.items[0] ?? [])}</p>;
      })}
      {claims.length > 0 && cited === 0 && !seeded ? (
        <p className="claim-banner" role="status">
          This reply has no citations
        </p>
      ) : null}
    </div>
  );
}

/** The claim contract as it arrives: validated prose the server stood behind. */
export function ClaimsPart() {
  const data = useAuiState((state) =>
    state.part.type === "data" && state.part.name === CLAIMS_PART
      ? (state.part.data as { content?: string; claims?: Claim[] })
      : null,
  );
  if (!data?.claims?.length) {
    return null;
  }
  return <ClaimText content={data.content ?? ""} claims={data.claims} />;
}

/**
 * The model's thinking, kept out of the answer and out of the way.
 *
 * It opens while it is being written so the reader can watch progress, and
 * stays open afterwards rather than snapping shut mid-read. A reader who
 * closes it keeps it closed: only the transition from running to done can
 * change the state on its own.
 */
export function ReasoningPart() {
  const text = useAuiState((state) =>
    state.part.type === "reasoning" ? state.part.text : null,
  );
  const running = useAuiState((state) => state.part.status?.type === "running");
  const [open, setOpen] = useState(running);
  const [seconds, setSeconds] = useState<number | null>(null);
  const startedAt = useRef<number | null>(null);
  const panelId = useId();

  useEffect(() => {
    if (running) {
      if (startedAt.current === null) {
        startedAt.current = Date.now();
      }
      return;
    }
    const started = startedAt.current;
    if (started === null) {
      return;
    }
    startedAt.current = null;
    // One tick after the run settles, so the duration lands as a settled value
    // rather than writing state during the effect that observed the change.
    const timer = window.setTimeout(() => {
      setSeconds(Math.max(1, Math.round((Date.now() - started) / 1000)));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [running]);

  if (!text) {
    return null;
  }

  const label = running
    ? "Thinking…"
    : seconds === null
      ? "Thought process"
      : `Thought for ${seconds}s`;

  return (
    <div className={`reasoning${running ? " is-thinking" : ""}`}>
      <button
        type="button"
        className="reasoning__summary"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        <SparkIcon size={13} />
        <span>{label}</span>
        <ChevronDownIcon
          className={`reasoning__chevron${open ? " is-open" : ""}`}
          size={12}
        />
      </button>
      <div className="reasoning__body" id={panelId} hidden={!open}>
        <Markdown source={text} />
      </div>
    </div>
  );
}

/** What the turn actually read. A provenance chip, never a fabricated link. */
export function SourcePart() {
  const source = useAuiState((state) => {
    if (state.part.type !== "source") {
      return null;
    }
    return state.part;
  });
  if (!source) {
    return null;
  }
  const title = source.sourceType === "url" ? (source.title ?? source.url) : source.title;
  const filename = source.sourceType === "document" ? source.filename : undefined;
  return (
    <span className="source-chip" title={filename ?? title}>
      <span className="source-chip__label">Source</span>
      <span className="source-chip__title">{title}</span>
    </span>
  );
}

/** An agent-composed ODI surface, validated before it ever reached React. */
export function SurfacePart() {
  const node = useAuiState((state) =>
    state.part.type === "data" && state.part.name === SURFACE_PART
      ? (state.part.data as UiNode)
      : null,
  );
  if (!node) {
    return null;
  }
  // A card is not prose: a selection that spans it is not a quotable passage.
  return (
    <span data-aui-quote-selectable="false">
      <UiRenderer node={node} />
    </span>
  );
}

/**
 * A file the user attached, shown as what it was: an image preview, a name,
 * and its size. The prepared copy has the bytes; a turn restored from history
 * does not, so those fall back to the name alone rather than an empty frame.
 */
export function FilePart() {
  const file = useAuiState((state) => (state.part.type === "file" ? state.part : null));
  if (!file) {
    return null;
  }
  const prepared = preparedAttachmentById(file.data);
  const size = prepared ? formatFileSize(prepared.size) : "";

  return (
    <span className="attachment-chip" data-aui-quote-selectable="false">
      {prepared?.dataUrl ? (
        <img className="attachment-chip__thumb" src={prepared.dataUrl} alt="" />
      ) : null}
      <span className="attachment-chip__meta">
        <span className="attachment-chip__name">{file.filename ?? "Attachment"}</span>
        {size ? <span className="attachment-chip__size">{size}</span> : null}
      </span>
    </span>
  );
}

export const toolLabel = (name: string): string => name.replace(/_/g, " ");

/**
 * The model's arguments as a compact key/value list.
 *
 * Scrolls past six rows rather than truncating: the person is being asked to
 * approve the whole call, so every argument has to stay reachable. The raw
 * JSON stays behind a disclosure for the case where the list is not enough.
 */
function ApprovalArguments({ args }: { args: Record<string, unknown> }) {
  const [rawOpen, setRawOpen] = useState(false);
  const rawId = useId();
  const entries = Object.entries(args);

  return (
    <div className="approval__arguments">
      <dl className="approval__argument-list">
        {entries.map(([key, value]) => (
          <div className="approval__argument" key={key}>
            <dt className="approval__argument-key">{key}</dt>
            <dd className="approval__argument-value">{formatArgument(value)}</dd>
          </div>
        ))}
      </dl>
      <button
        type="button"
        className="approval__raw-toggle"
        aria-expanded={rawOpen}
        aria-controls={rawId}
        onClick={() => setRawOpen((value) => !value)}
      >
        <ChevronDownIcon className={`approval__raw-chevron${rawOpen ? " is-open" : ""}`} size={12} />
        Raw arguments
      </button>
      <pre className="approval__raw" id={rawId} hidden={!rawOpen}>
        {JSON.stringify(args, null, 2)}
      </pre>
    </div>
  );
}

/** One argument value, as a person would read it. */
function formatArgument(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

/** The most a deny reason may hold, matching the sidecar's own cap. */
const MAX_REASON_CHARS = 280;

/**
 * A tool call, and the one question the agent is not allowed to answer itself:
 * whether it may write.
 *
 * The question is about an action, not a tool name: the card states what the
 * call will do, shows the arguments it will do it with, and — when the answer
 * is no — lets the person say why, so the agent can propose something else.
 */
export function ToolPart({
  toolName,
  args,
  approval,
  result,
  isError,
  status,
  respondToApproval,
}: ToolCallMessagePartProps) {
  const [busy, setBusy] = useState(false);
  const [answered, setAnswered] = useState(false);
  const [reasonOpen, setReasonOpen] = useState(false);
  const [reason, setReason] = useState("");
  // Where the card's place went: after an answer the gate is replaced by the
  // trace, and focus must follow the decision rather than drop to the body.
  const traceRef = useRef<HTMLParagraphElement>(null);
  const payload = result as { status?: string; preview?: string } | undefined;
  const pending = approval !== undefined && approval.approved === undefined && !result;
  const running = status?.type === "running";

  useEffect(() => {
    if (answered) {
      traceRef.current?.focus();
    }
  }, [answered]);

  async function answer(approved: boolean) {
    if (!approval || busy) {
      return;
    }
    setBusy(true);
    try {
      await respondToApproval({
        approved,
        ...(!approved && reason.trim() ? { reason: reason.trim() } : {}),
      });
      setAnswered(true);
    } catch {
      // The gate may have expired; the stream reports what happened to the turn.
    } finally {
      setBusy(false);
    }
  }

  if (pending && !answered) {
    const approvalArgs = isArguments(args) ? args : {};
    const hasArgs = Object.keys(approvalArgs).length > 0;
    return (
      <div
        className="approval"
        role="group"
        aria-label="Permission needed"
        data-aui-quote-selectable="false"
      >
        <p className="approval__prompt">{approval.prompt ?? `Run ${toolLabel(toolName)}?`}</p>
        <p className="approval__consequence">This {describeConsequence(toolName)}.</p>
        {hasArgs ? <ApprovalArguments args={approvalArgs} /> : null}
        {reasonOpen ? (
          <div className="approval__reason">
            <label className="approval__reason-label" htmlFor={`${approval.id}-reason`}>
              Why not? (optional)
            </label>
            <textarea
              id={`${approval.id}-reason`}
              className="approval__reason-input"
              value={reason}
              maxLength={MAX_REASON_CHARS}
              rows={2}
              onChange={(event) => setReason(event.target.value)}
            />
            <span className="approval__reason-count">
              {reason.length}/{MAX_REASON_CHARS}
            </span>
          </div>
        ) : null}
        <div className="approval__actions">
          <button
            type="button"
            className="approval__allow"
            disabled={busy}
            onClick={() => void answer(true)}
          >
            <CheckIcon size={14} /> Allow
          </button>
          {reasonOpen ? (
            <button
              type="button"
              className="approval__deny"
              disabled={busy}
              onClick={() => void answer(false)}
            >
              Send refusal
            </button>
          ) : (
            <button
              type="button"
              className="approval__deny"
              disabled={busy}
              onClick={() => setReasonOpen(true)}
            >
              Don't allow
            </button>
          )}
        </div>
      </div>
    );
  }

  const tone = isError || payload?.status === "error" ? " is-error" : "";
  const declined = payload?.status === "declined";
  // The state is named as well as coloured: a red dot alone tells a person
  // nothing about what happened, and nothing at all to a screen reader.
  const stateLabel = running ? "working" : declined ? "declined" : isError ? "failed" : "";
  return (
    <p
      ref={traceRef}
      tabIndex={-1}
      className={`tool-trace${tone}${running ? " is-running" : ""}${declined ? " is-declined" : ""}`}
      data-aui-quote-selectable="false"
    >
      <span className="tool-trace__dot" aria-hidden="true" />
      {toolLabel(toolName)}
      {stateLabel ? <span className="tool-trace__state"> · {stateLabel}</span> : null}
      {payload?.preview ? <span className="tool-trace__preview">{payload.preview}</span> : null}
    </p>
  );
}

/**
 * The activity state before the first token arrives.
 *
 * The phase is announced by the transcript's own status region, outside this
 * message: the message is `aria-busy` while it streams, and a live region
 * nested in a busy subtree would be held back until the reply finished.
 */
export function TypingPart({ label }: { label: string }) {
  const seconds = useElapsedSeconds(true);

  return (
    <div className="thinking" aria-hidden="true">
      <p className="thinking__status">
        <span className="thinking__dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <span className="thinking__label">{label}</span>
      </p>
      {seconds >= 3 ? (
        <span className="thinking__timer" aria-hidden="true">
          {seconds}s
        </span>
      ) : null}
    </div>
  );
}

function useElapsedSeconds(active: boolean): number {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!active) {
      return;
    }
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [active]);

  return seconds;
}

/** The sparkle avatar, shared by every assistant turn. */
export function AssistantAvatar() {
  return (
    <span className="message__avatar" aria-hidden="true">
      <SparkIcon size={15} />
    </span>
  );
}
