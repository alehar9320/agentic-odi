import { useRef, useState } from "react";

import {
  asStudioError,
  exportWorkspace,
  importWorkspace,
  readWorkspaceSnapshot,
  workspaceSummary,
} from "../../../api/studioApi";
import type { WorkspaceSummary } from "../../../bff/store/types";
import { downloadFile } from "../../../lib/download";

const WORKSPACE_FILENAME = "agentic-odi-workspace.json";

const COUNT_LABELS: Array<[keyof WorkspaceSummary["counts"], string]> = [
  ["jobs", "jobs"],
  ["steps", "steps"],
  ["outcomes", "outcomes"],
  ["observations", "observations"],
  ["evidence", "evidence"],
  ["conversations", "conversations"],
  ["turns", "messages"],
];

/** A plain-language list of what a workspace holds, for the confirmation. */
function describeCounts(summary: WorkspaceSummary): string {
  const parts = COUNT_LABELS.filter(([key]) => summary.counts[key] > 0).map(
    ([key, label]) => `${summary.counts[key]} ${label}`,
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
 * The escape hatch: take the whole local workspace out as one JSON file, and
 * put it back. Export never uploads anything; import never replaces a workspace
 * the person has not confirmed, so the work on this device is never the price of
 * restoring a file.
 */
export function WorkspaceSection() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<Message | null>(null);
  const [pending, setPending] = useState<{ json: string; summary: WorkspaceSummary } | null>(
    null,
  );

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
        setMessage({
          kind: "success",
          text: `Imported ${describeCounts(restored)}.`,
        });
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
      setMessage({
        kind: "success",
        text: `Imported ${describeCounts(restored)}.`,
      });
    } catch (error) {
      setMessage({ kind: "error", text: asStudioError(error).message });
    } finally {
      setBusy(false);
      setPending(null);
    }
  }

  return (
    <section
      className="settings__section"
      aria-labelledby="settings-workspace-heading"
    >
      <h3 className="settings__title" id="settings-workspace-heading">
        Your workspace
      </h3>
      <p className="muted">
        Export everything on this device as one readable JSON file, or import a file to
        restore it. Nothing is uploaded.
      </p>
      <div className="settings__workspace-actions">
        <button
          type="button"
          className="button button--ghost"
          onClick={() => void onExport()}
          disabled={busy}
        >
          Export my workspace
        </button>
        <label className="button button--ghost settings__workspace-import">
          Import workspace
          <input
            ref={inputRef}
            type="file"
            accept="application/json,.json"
            className="settings__workspace-input"
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
          role={message.kind === "error" ? "alert" : "status"}
          className={message.kind === "error" ? "settings__workspace-error" : "muted"}
        >
          {message.text}
        </p>
      ) : null}

      {pending ? (
        <div className="diagnostics-overlay" role="presentation">
          <div
            className="diagnostics-modal"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="workspace-import-title"
            aria-describedby="workspace-import-body"
          >
            <h2 id="workspace-import-title" className="changelog-modal__title">
              Replace this workspace?
            </h2>
            <p id="workspace-import-body" className="diagnostics-modal__summary">
              Importing replaces the {describeCounts(pending.summary)} already on this device
              with the contents of the file. This cannot be undone.
            </p>
            <footer className="diagnostics-modal__actions">
              <button
                type="button"
                className="button button--ghost"
                onClick={() => setPending(null)}
                disabled={busy}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button"
                onClick={() => void confirmImport()}
                disabled={busy}
              >
                Replace workspace
              </button>
            </footer>
          </div>
        </div>
      ) : null}
    </section>
  );
}
