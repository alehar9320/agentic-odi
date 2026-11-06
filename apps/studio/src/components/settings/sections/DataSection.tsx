import { useEffect, useRef, useState } from "react";

import { getStudioBff } from "../../../bff/index";
import { storageFacts } from "../../../bff/storageFacts";
import { useStudio } from "../../../state/StudioContext";

export function DataSection() {
  const { refreshCanvas } = useStudio();
  const [facts, setFacts] = useState<Awaited<ReturnType<typeof storageFacts>> | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const bff = await getStudioBff();
      const f = await storageFacts(bff.store);
      if (!cancelled) setFacts(f);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleExport() {
    const bff = await getStudioBff();
    const json = await bff.exportWorkspace();
    const filename = "workspace.json";
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    setStatus(`Exported ${filename}`);
  }

  async function handleImport(file: File) {
    const ok = window.confirm("Replace the current workspace with this file?");
    if (!ok) return;
    const bff = await getStudioBff();
    const text = await file.text();
    await bff.importWorkspace(text);
    await refreshCanvas();
    setStatus("Imported workspace");
  }

  const storeName = facts?.engine === "indexeddb" ? facts.database : "In this browser";
  const bytes = facts?.bytes === "unknown" ? "—" : facts ? `${facts.bytes} bytes` : "—";
  const lastWritten = facts?.lastWrite ?? "—";

  return (
    <div className="settings__section">
      <h3 className="settings__title" id="settings-data-heading">Data</h3>
      <p className="muted">
        On this device · {storeName} · {bytes} · last written {lastWritten}
      </p>
      <p className="muted">
        The export does not include uploads, connector tokens, or provider API keys.
      </p>
      <div className="settings__actions">
        <button type="button" className="button" onClick={() => void handleExport()}>
          Export workspace
        </button>
        <button type="button" className="button button--ghost" onClick={() => fileInput.current?.click()}>
          Import
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="application/json"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void handleImport(f);
            e.target.value = "";
          }}
        />
      </div>
      {status ? <p className="muted">{status}</p> : null}
    </div>
  );
}
