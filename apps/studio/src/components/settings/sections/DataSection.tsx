import { useRef, useState } from "react";
import { useStudio } from "../../../state/StudioContext";

export interface StorageFacts {
  kind: "sidecar" | "browser";
  path?: string;
  bytes?: number;
  lastWrittenAt?: string;
}

export function DataSection({ facts }: { facts?: StorageFacts }) {
  const { refreshCanvas, sidecarReachable } = useStudio();
  const [status, setStatus] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const resolved: StorageFacts = facts ?? {
    kind: sidecarReachable ? "sidecar" : "browser",
  };

  const sizeText = resolved.bytes != null ? `${(resolved.bytes / (1024 * 1024)).toFixed(1)} MB` : "—";
  const recency = resolved.lastWrittenAt ?? "—";

  async function exportWorkspace() {
    const { getStudioBff } = await import("../../../bff");
    const bff = await getStudioBff();
    const json = await bff.exportWorkspace();
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "agentic-odi-workspace.json";
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    setStatus("Exported agentic-odi-workspace.json");
  }

  async function importWorkspace(file: File) {
    const text = await file.text();
    const { getStudioBff } = await import("../../../bff");
    const bff = await getStudioBff();
    await bff.importWorkspace(text);
    await refreshCanvas();
    setStatus("Imported workspace");
  }

  return (
    <section className="settings__section" aria-labelledby="settings-data-heading">
      <h3 className="settings__title" id="settings-data-heading">Data</h3>
      <p className="muted">
        {resolved.kind === "sidecar" ? "On this device" : "In this browser"} · {sizeText} · last written {recency}
      </p>
      <p className="muted">
        The file does not contain uploads, connector tokens, or provider API keys.
      </p>
      <div className="settings__actions">
        <button type="button" className="button" onClick={() => void exportWorkspace()}>
          Export workspace
        </button>
        <button type="button" className="button button--ghost" onClick={() => fileInput.current?.click()}>
          Import
        </button>
      </div>
      <input
        ref={fileInput}
        type="file"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void importWorkspace(f);
        }}
      />
      {status ? <p className="muted">{status}</p> : null}
    </section>
  );
}
