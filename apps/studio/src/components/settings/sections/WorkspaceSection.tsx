import { useEffect, useRef, useState } from "react";

import {
  asStudioError,
  exportWorkspace,
  importWorkspace,
  readWorkspaceSnapshot,
  workspaceSummary,
} from "../../../api/studioApi";
import type { WorkspaceSummary } from "../../../bff/store/types";
import { downloadFile } from "../../../lib/download";
import { useFocusTrap } from "../../../lib/useFocusTrap";

const WORKSPACE_FILENAME = "agentic-odi-workspace.json";

const COUNT_LABELS: Array<[keyof WorkspaceSummary["counts"], string, string]> = [
  ["jobs", "job", "jobs"],
  ["steps", "step", "steps"],
  ["outcomes", "outcome", "outcomes"],
  ["observations", "observation", "observations"],
  ["evidence", "evidence", "evidence"],
  ["conversations", "conversation", "conversations"],
  ["turns", "message", "messages"],
];

/** A plain-language list of what a workspace holds, for the confirmation. */
function describeCounts(summary: WorkspaceSummary): string {
  const parts = COUNT_LABELS.filter(([key]) => summary.counts[key] > 0).map(
    ([key, singular, plural]) => {
      const count = summary.counts[key];
      return `${count} ${count === 1 ? singular : plural}`;
    },
  );
  if (parts.length === 0) {
    return "no records";
  }
  if (parts.length === 1) {
    return parts[0];
  }
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

type Message = { kind: "success" | "error"; text: string };

/**
 * The escape hatch: take the whole local workspace out as one JSON file, and put
 * it back. Export never uploads anything; import never replaces a workspace the
 * person has not confirmed, so the work on this device is never the price of
 * restoring a file.
 */
export function WorkspaceSection() {
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<Message | null>(null);
  const [pending, setPending] = useState<{ json: string; summary: WorkspaceSummary } | null>(
    null,
  );
  useFocusTrap(dialogRef, pending !== null);

  useEffect(() => {
    if (pending === null) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setPending(null);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [pending]);

  async function onExport() {
    setBusy(true);
    setMessage(null);
    try {
      const json = await exportWorkspace();
      downloadFile(json, WORKSPACE_FILENAME, "application/json");
      const summary = await workspaceSummary();
      setMessage({
        kind: "success",
        text: `Exported ${describeCounts(summary)} to ${WORKSPACE_FILENAME}.`,
      });
    } catch (error) {
      setMessage({ kind: "error", text: asStudioError(error).message });
    } finally {
      setBusy(false);
    }
  }

  async function onFileChosen(file: File) {
    setBusy(true);
    setMessage(null);
    try {
      const json = await file.text();
      // Read the file before touching the workspace: a version mismatch is
      // reported here, so a person never confirms replacing work with a file
      // this build cannot read.
      await readWorkspaceSnapshot(json);
      const summary = await workspaceSummary();
      if (summary.empty) {
        await importWorkspace(json);
        const restored = await workspaceSummary();
        setMessage({ kind: "success", text: `Imported ${describeCounts(restored)}.` });
      } else {
        setPending({ json, summary });
      }
    } catch (error) {
      setMessage({ kind: "error", text: asStudioError(error).message });
    } finally {
      setBusy(false);
      // Allow the same file to be chosen again after a refusal.
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  }

  async function confirmImport() {
    if (!pending) {
      return;
    }
    const json = pending.json;
    setBusy(true);
    try {
      await importWorkspace(json);
      const restored = await workspaceSummary();
      setMessage({ kind: "success", text: `Imported ${describeCounts(restored)}.` });
    } catch (error) {
      setMessage({ kind: "error", text: asStudioError(error).message });
    } finally {
      setBusy(false);
      setPending(null);
    }
  }

  return (
    <section className="settings__section" aria-labelledby="settings-workspace-heading">
      <h3 className="settings__title" id="settings-workspace-heading">
        Your workspace
      </h3>
      <p className="muted">
        Everything here lives on this device. Take it out as one readable file, or put a file back.
        Nothing is uploaded.
      </p>
      <div className="settings__actions">
        <button
          type="button"
          className="button button--ghost"
          disabled={busy}
          onClick={() => void onExport()}
        >
          Export my workspace
        </button>
        <label className="button button--ghost">
          Import workspace
          <input
            ref={inputRef}
            className="sr-only"
            type="file"
            accept="application/json,.json"
            disabled={busy}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                void onFileChosen(file);
              }
            }}
          />
        </label>
      </div>
      {message ? (
        <p
          className={message.kind === "error" ? "settings__workspace-error" : "settings__save"}
          role={message.kind === "error" ? "alert" : "status"}
        >
          {message.text}
        </p>
      ) : null}

      {pending ? (
        <div className="diagnostics-overlay" role="presentation">
          <div
            ref={dialogRef}
            className="diagnostics-modal"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="workspace-confirm-title"
            aria-describedby="workspace-confirm-body"
            tabIndex={-1}
          >
            <header className="diagnostics-modal__header">
              <h2 id="workspace-confirm-title" className="changelog-modal__title">
                Replace this workspace?
              </h2>
            </header>
            <p id="workspace-confirm-body" className="diagnostics-modal__summary">
              Importing will replace what is on this device right now —{" "}
              {describeCounts(pending.summary)}. This cannot be undone.
            </p>
            <div className="diagnostics-modal__actions">
              <button
                type="button"
                className="button button--ghost"
                disabled={busy}
                onClick={() => setPending(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button"
                disabled={busy}
                onClick={() => void confirmImport()}
              >
                Replace workspace
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
