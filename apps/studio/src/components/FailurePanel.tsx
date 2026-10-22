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
      {error.detail ? (
        <details className="failure__detail">
          <summary>Details</summary>
          <pre>{error.detail}</pre>
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
