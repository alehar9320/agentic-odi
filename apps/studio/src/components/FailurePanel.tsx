import type { StudioError } from "../types";
import { useCopyConfirmation } from "../lib/useCopyConfirmation";
import { AlertIcon, CheckIcon, CopyIcon } from "./icons";

/**
 * The failure as plain text for a bug report: the message, the detail, and the
 * request id, each only when it exists. Nothing is invented to fill a line.
 */
function failureText(error: StudioError): string {
  return [error.message, error.detail, error.request_id ? `Request id: ${error.request_id}` : null]
    .filter((line): line is string => Boolean(line))
    .join("\n");
}

/**
 * A failure shown in place of the thing that failed. It says what went wrong,
 * what would fix it, and — when there is something to retry — a button that
 * asks for it again instead of making the user retype the question.
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
  const { copied, copy } = useCopyConfirmation();
  // Nothing beyond the message is worth copying, so the control is absent
  // rather than present and empty.
  const hasDetail = Boolean(error.detail || error.request_id);
  return (
    <div className="failure" role="alert" id={id}>
      <span className="failure__icon" aria-hidden="true">
        <AlertIcon size={16} />
      </span>
      <div className="failure__body">
        <p className="failure__message">{error.message}</p>
        {hasDetail ? (
          <details className="failure__detail">
            <summary>Details</summary>
            {error.detail ? <pre>{error.detail}</pre> : null}
            {error.request_id ? (
              <p className="failure__request">
                Request id: <code>{error.request_id}</code>
              </p>
            ) : null}
          </details>
        ) : null}
        {hasDetail ? (
          <button
            type="button"
            className="quiet-action failure__copy"
            aria-label={copied ? "Details copied" : "Copy details"}
            onClick={() => void copy(failureText(error))}
          >
            {copied ? <CheckIcon size={14} /> : <CopyIcon size={14} />}
            {copied ? "Copied" : "Copy details"}
          </button>
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
