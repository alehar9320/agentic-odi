/**
 * One tool call, opened.
 *
 * The collapsed row is the line the transcript has always shown; underneath it
 * sits the exchange itself — what the model asked for and what actually came
 * back. Which calls are open lives in this component and nowhere else, so a
 * restored transcript starts with every call collapsed.
 */

import { useEffect, useId, useRef, useState } from "react";

import { ChevronDownIcon, CopyIcon } from "../icons";
import type { JsonValue, ToolStatus } from "../../types";

export type ToolCallCardProps = {
  /** Pairs the card with its call: two calls to one tool are two cards. */
  callId: string;
  /** The name as the sidecar sent it, which is what the copy carries. */
  name: string;
  /** The same name in the transcript's own words. */
  label: string;
  status: ToolStatus;
  /** What the model asked the tool for. */
  input?: Record<string, JsonValue>;
  /** The first characters of the answer, for the collapsed line. */
  preview?: string;
  /** The whole answer: structure when the tool returned JSON, text when it did not. */
  output?: unknown;
  isError?: boolean;
};

/** Long enough to read, short enough not to claim a second copy worked. */
const COPIED_MS = 2000;

/** Text stays the text it arrived as; anything else is shown as the JSON it is. */
function pretty(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

export function ToolCallCard({
  callId,
  name,
  label,
  status,
  input,
  preview,
  output,
  isError,
}: ToolCallCardProps) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);
  const panelId = `${useId()}-${callId}`;

  useEffect(
    () => () => {
      if (timer.current !== null) {
        window.clearTimeout(timer.current);
      }
    },
    [],
  );

  const running = status === "running";
  const failed = isError === true || status === "error";

  async function copy() {
    try {
      await navigator.clipboard.writeText(
        JSON.stringify({ name, arguments: input ?? {}, result: output ?? null }, null, 2),
      );
      setCopied(true);
      if (timer.current !== null) {
        window.clearTimeout(timer.current);
      }
      timer.current = window.setTimeout(() => setCopied(false), COPIED_MS);
    } catch {
      // The JSON is on screen either way; a clipboard that refuses is not worth a message.
    }
  }

  return (
    <div className={`tool-call${open ? " is-open" : ""}`} data-aui-quote-selectable="false">
      <button
        type="button"
        className={`tool-trace${failed ? " is-error" : ""}${running ? " is-running" : ""}`}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="tool-trace__dot" aria-hidden="true" />
        <span>
          {label}
          {running ? " · working" : status === "declined" ? " · declined" : ""}
        </span>
        {preview ? <span className="tool-trace__preview">{preview}</span> : null}
        <ChevronDownIcon className={`tool-call__chevron${open ? " is-open" : ""}`} size={12} />
      </button>
      {open ? (
        <div className="tool-call__body" id={panelId}>
          <div className="tool-call__section">
            <span className="tool-call__label">Input</span>
            <pre className="tool-call__json">{pretty(input ?? {})}</pre>
          </div>
          <div className="tool-call__section">
            <span className="tool-call__label">Output</span>
            {output === undefined ? (
              <p className="tool-call__waiting">
                {running ? "Waiting for the tool to answer." : "This call got no answer."}
              </p>
            ) : (
              <pre className="tool-call__json">{pretty(output)}</pre>
            )}
          </div>
          <div className="tool-call__actions">
            <button type="button" className="quiet-action" onClick={() => void copy()}>
              <CopyIcon size={14} /> Copy JSON
            </button>
            {copied ? <span className="tool-call__copied">Copied</span> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
