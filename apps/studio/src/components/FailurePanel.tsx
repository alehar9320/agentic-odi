import type { StudioError } from "../types";

/**
 * A failure shown in place of the thing that failed. It says what went wrong,
 * what would fix it, and — when there is something to retry — a button that
 * asks for it again instead of making the user retype the question.
 */
export function FailurePanel({
  error,
  onRetry,
  retryText,
}: {
  error: StudioError;
  onRetry?: (text: string) => void;
  retryText?: string;
}) {
  return (
    <div className="failure" role="alert">
      <p className="failure__message">{error.message}</p>
      {error.detail || error.request_id ? (
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
  );
}
