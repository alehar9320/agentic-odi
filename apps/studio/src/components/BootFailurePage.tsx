import type { StudioError } from "../types";

/**
 * The page the Studio shows when the database failed its integrity check on
 * boot.
 *
 * The database is the only copy, so there is nothing honest to render in its
 * place — an empty board would read as "you have no work" when the truth is
 * "your work is still on disk, and it is damaged". This page says which file
 * failed, names the last backup, and offers a recheck for after the person has
 * restored it. It never offers to delete or overwrite the file: that decision
 * belongs to the person, and the sidecar has already left the file untouched.
 */
export function BootFailurePage({
  error,
  onRecheck,
}: {
  error: StudioError;
  onRecheck: () => void;
}) {
  return (
    <div className="error-page">
      <div className="error-page__card" role="alert">
        <p className="hero__eyebrow">The database did not pass its check</p>
        <h1 className="error-page__title">Your database failed its integrity check.</h1>
        <p className="hero__sub">{error.message}</p>
        {error.suggestion ? (
          <p className="hero__sub error-page__suggestion">{error.suggestion}</p>
        ) : null}
        {error.detail ? (
          <details className="failure__detail">
            <summary>What the check reported</summary>
            <pre>{error.detail}</pre>
          </details>
        ) : null}
        <button type="button" className="button" onClick={onRecheck}>
          Recheck the database
        </button>
      </div>
    </div>
  );
}
