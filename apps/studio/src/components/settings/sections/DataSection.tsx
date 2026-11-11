import { useEffect, useState } from "react";

import { useStudio } from "../../../state/StudioContext";
import { getStorageFacts, exportWorkspace, importWorkspace } from "../../../api/studioApi";
import { exportFilename } from "../../../lib/export";

interface DataSectionProps {
  sidecarReachable: boolean | null;
}

function formatBytes(bytes?: number): string {
  if (bytes === undefined) {
    return "—";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatRelativeTime(dateString?: string): string {
  if (!dateString) {
    return "—";
  }
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) {
    return "just now";
  }
  if (diffMins < 60) {
    return `${diffMins} min ago`;
  }
  if (diffHours < 24) {
    return `${diffHours} h ago`;
  }
  return `${diffDays} d ago`;
}

export function DataSection({ sidecarReachable }: DataSectionProps) {
  const { pushToast } = useStudio();
  const [facts, setFacts] = useState<{
    kind: "sidecar" | "browser";
    path?: string;
    bytes?: number;
    lastWrittenAt?: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadFacts() {
      try {
        const data = await getStorageFacts();
        if (!cancelled) {
          setFacts(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load storage facts");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    loadFacts();
    return () => {
      cancelled = true;
    };
  }, [sidecarReachable]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const json = await exportWorkspace();
      const filename = exportFilename(new Date()).replace(".md", ".json");
      const blob = new Blob([json], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.style.display = "none";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      pushToast("success", `Exported ${filename}`);
    } catch (err) {
      pushToast("error", `Export failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setExporting(false);
    }
  };

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setImporting(true);
    try {
      const text = await file.text();
      await importWorkspace(text);
      pushToast("success", "Imported workspace — reloading canvas");
      window.location.reload();
    } catch (err) {
      pushToast("error", `Import failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setImporting(false);
      event.target.value = "";
    }
  };

  const storeLabel = facts?.kind === "sidecar" ? "On this device (sidecar)" : "In this browser";
  const storePath = facts?.path ? ` · ${facts.path}` : "";
  const storeSize = ` · ${formatBytes(facts?.bytes)}`;

  return (
    <div className="settings__section">
      <h2 className="settings__section-title">Data</h2>
      <p className="settings__section-description">
        Where your work lives and tools to move it.
      </p>

      {loading && <p className="settings__loading">Loading storage facts…</p>}
      {error && <p className="settings__error" role="alert">{error}</p>}

      {!loading && !error && facts && (
        <div className="settings__storage-facts">
          <p className="settings__storage-summary">
            {storeLabel}{storePath}{storeSize}
            {/* Every visible time is a <time>; an unknown one says so plainly
                rather than wearing a relative phrase that reads as a record. */}
            {" · last written "}
            {facts.lastWrittenAt ? (
              <time dateTime={facts.lastWrittenAt}>
                {formatRelativeTime(facts.lastWrittenAt)}
              </time>
            ) : (
              "—"
            )}
          </p>
          <p className="settings__storage-exclusions">
            This file does not contain uploads, connector tokens, or provider API keys.
          </p>
        </div>
      )}

      <div className="settings__actions">
        <button
          type="button"
          className="button"
          onClick={handleExport}
          disabled={exporting || importing || loading || error !== null}
        >
          {exporting ? "Exporting…" : "Export workspace"}
        </button>
        <label className="button button--ghost" htmlFor="import-workspace">
          {importing ? "Importing…" : "Import workspace"}
          <input
            id="import-workspace"
            type="file"
            accept=".json"
            onChange={handleImport}
            disabled={exporting || importing || loading || error !== null}
            style={{ display: "none" }}
          />
        </label>
      </div>
    </div>
  );
}