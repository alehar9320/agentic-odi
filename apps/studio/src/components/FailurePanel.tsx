import { useState } from "react";

import { copyText, useCopyFeedback } from "../lib/copyFeedback";
import type { StudioError } from "../types";
import { AlertIcon } from "./icons";

/**
 * A failure shown in place of the thing that failed. It says what went wrong,
 * what would fix it, and — when there is something to retry — a button that
 * asks for it again instead of making the user retype the question.
 *
 * When there is more than the message, the whole failure can leave as plain
 * text for a bug report. The control is absent when the message is all there
 * is: copying one line the reader already sees is not a feature.
 */
export function FailurePanel({
  error,
  onRetry,
  retryText,
  id,
}: {
  error: StudioError;
  onRetry?: (text: string) => void;
  retryText?: string;
  id?: string;
}) {
  const { copied, confirm } = useCopyFeedback();
  const [copyFailed, setCopyFailed] = useState(false);

  const details = [
    error.message,
    error.detail ? `\n${error.detail}` : "",
    error.request_id ? `\nRequest id: ${error.request_id}` : "",
  ].join("");

  return (
    <div className="failure" role="alert" id={id}>
      <span className="failure__icon" aria-hidden="true">
        <AlertIcon size={16} />
      </span>
      <div className="failure__body">
        <p className="failure__message">{error.message}</p>
        {error.detail || error.request_id ? (
          <>
            <details className="failure__detail">
              <summary>Details</summary>
              {error.detail ? <pre>{error.detail}</pre> : null}
              {error.request_id ? (
                <p className="failure__request">
                  Request id: <code>{error.request_id}</code>
                </p>
              ) : null}
            </details>
            <button
              type="button"
              className="quiet-action failure__copy"
              aria-label="Copy details"
              onClick={() => {
                void copyText(details).then((ok) => {
                  setCopyFailed(!ok);
                  if (ok) {
                    confirm();
                  }
                });
              }}
            >
              {copied ? "Copied" : copyFailed ? "Copy failed" : "Copy details"}
            </button>
          </>
        ) : null}
        {error.suggestion ? <p className="failure__suggestion">{error.suggestion}</p> : null}
        {onRetry ? (
          <button
            type="button"
            className="quiet-action failure__retry"
            onClick={() => onRetry(retryText ?? "")}
          >
            Retry
          </button>
        ) : null}
      </div>
    </div>
  );
}
