import { useEffect, useRef, useState } from "react";

import { useFocusTrap } from "../lib/useFocusTrap";

export function DiagnosticsModal({
  json,
  byteCount,
  entryCount,
  engineAvailable,
  onClose,
}: {
  json: string;
  byteCount: number;
  entryCount: number;
  engineAvailable: boolean;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [copyMessage, setCopyMessage] = useState("");
  useFocusTrap(dialogRef, true);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(json);
      setCopyMessage("Diagnostics copied.");
    } catch {
      setCopyMessage("Could not copy diagnostics. You can still save the file.");
    }
  }

  function save() {
    const url = URL.createObjectURL(new Blob([json], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "agentic-odi-diagnostics.json";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="diagnostics-overlay" role="presentation">
      <div
        ref={dialogRef}
        className="diagnostics-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="diagnostics-title"
        aria-describedby="diagnostics-summary"
        tabIndex={-1}
      >
        <header className="diagnostics-modal__header">
          <div>
            <p className="changelog-modal__badge">YOUR FILE, YOUR CHOICE</p>
            <h2 id="diagnostics-title" className="changelog-modal__title">
              Review diagnostics
            </h2>
          </div>
          <button
            type="button"
            className="changelog-modal__close"
            onClick={onClose}
            aria-label="Cancel diagnostics export"
          >
            ✕
          </button>
        </header>
        <p id="diagnostics-summary" className="diagnostics-modal__summary">
          This file stays on this machine. {entryCount} entries, {byteCount.toLocaleString()} bytes.
          {engineAvailable
            ? " Sidecar metadata is included."
            : " The sidecar is unavailable; engine metadata is omitted."}
        </p>
        <div className="diagnostics-modal__lists">
          <section aria-labelledby="diagnostics-included">
            <h3 id="diagnostics-included">Included</h3>
            <ul>
              <li>App version, build, platform, and theme</li>
              <li>Sidecar and capability metadata</li>
              <li>Redacted errors, console warnings, and turn counts/timings</li>
            </ul>
          </section>
          <section aria-labelledby="diagnostics-excluded">
            <h3 id="diagnostics-excluded">Never included</h3>
            <ul>
              <li>Messages, observations, brief, theses, or attachment text</li>
              <li>Canvas entities or customer content</li>
              <li>API keys, URL credentials, or URL query strings</li>
            </ul>
          </section>
        </div>
        <pre role="region" className="diagnostics-modal__preview" aria-label="Exact diagnostics JSON preview" tabIndex={0}>
          {json}
        </pre>
        {copyMessage ? (
          <p role="status" className="muted">
            {copyMessage}
          </p>
        ) : null}
        <footer className="diagnostics-modal__actions">
          <button type="button" className="button button--ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="button button--ghost" onClick={() => void copy()}>
            Copy
          </button>
          <button type="button" className="button" onClick={save}>
            Save .json
          </button>
        </footer>
      </div>
    </div>
  );
}
