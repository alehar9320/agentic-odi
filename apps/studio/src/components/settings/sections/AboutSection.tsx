import { useState } from "react";

import { fetchDiagnostics } from "../../../api/studioApi";
import type { SidecarDiagnostics } from "../../../api/studioApi";
import type { Capability } from "../../../bff/capabilities/registry";
import {
  createDiagnosticsBundle,
  diagnosticsEntryCount,
  startDiagnosticsCapture,
} from "../../../diagnostics/bundle";
import { DiagnosticsModal } from "../../../diagnostics/DiagnosticsModal";
import { PRODUCT_NAME } from "../../../lib/brand";
import { resolveTheme } from "../../../lib/theme";
import type { StudioConfig } from "../../../types";
import { useUpdateService, useUpdateSnapshot } from "../../../updater";
import { detectPlatform } from "../../../updater/platform";

const STUDIO_VERSION = "0.14.0";

const PLATFORM_LABELS: Record<ReturnType<typeof detectPlatform>, string> = {
  macos: "macOS",
  windows: "Windows",
  linux: "Linux",
  unknown: "Desktop",
};

interface AboutSectionProps {
  settings: StudioConfig;
  capabilities: Capability[];
}

/**
 * The honest facts about this build: which version, cut when, for which
 * platform, and what the updater thinks. Read-only — the controls live in
 * the Software update section above.
 */
export function AboutSection({ settings, capabilities }: AboutSectionProps) {
  const service = useUpdateService();
  const snapshot = useUpdateSnapshot();
  const platform = detectPlatform();
  const [diagnosticsJson, setDiagnosticsJson] = useState<string | null>(null);

  async function prepareDiagnostics() {
    startDiagnosticsCapture();
    let reachable = false;
    let engine: SidecarDiagnostics | null = null;
    try {
      const diagnostics = await fetchDiagnostics();
      engine = diagnostics;
      reachable = true;
    } catch {
      // Export remains available when the local sidecar is down.
    }
    const bundle = createDiagnosticsBundle({
      version: snapshot.currentVersion ?? STUDIO_VERSION,
      build: __STUDIO_BUILD_DATE__,
      platform: PLATFORM_LABELS[platform],
      theme: resolveTheme(settings.theme),
      reachable,
      defaults: {
        base_url: settings.base_url,
        api_key: settings.api_key,
        model_name: settings.model_name,
        mcp_url: settings.mcp_url,
      },
      engine,
      capabilities,
      apiKey: settings.api_key,
    });
    setDiagnosticsJson(JSON.stringify(bundle, null, 2));
  }

  return (
    <section className="settings__about" aria-labelledby="settings-about-heading">
      <h3 className="settings__title" id="settings-about-heading">
        About
      </h3>
      <p className="muted">{PRODUCT_NAME} is a local-first workspace for outcome-driven work.</p>
      <dl>
        <dt>Version</dt>
        <dd>{snapshot.currentVersion ? `v${snapshot.currentVersion}` : "—"}</dd>
        <dt>Build</dt>
        <dd>{__STUDIO_BUILD_DATE__}</dd>
        <dt>Platform</dt>
        <dd>{PLATFORM_LABELS[platform]}</dd>
        <dt>Updates</dt>
        <dd>{service.statusLine()}</dd>
      </dl>
      <div className="diagnostics-about">
        <h4>Diagnostics</h4>
        <p className="muted">
          Build a private, redacted snapshot to review before you copy or save it. Nothing is
          uploaded.
        </p>
        <button
          type="button"
          className="button button--ghost"
          onClick={() => void prepareDiagnostics()}
        >
          Create diagnostics bundle
        </button>
      </div>
      {diagnosticsJson !== null ? (
        <DiagnosticsModal
          json={diagnosticsJson}
          byteCount={new TextEncoder().encode(diagnosticsJson).length}
          entryCount={diagnosticsEntryCount(JSON.parse(diagnosticsJson) as Record<string, unknown>)}
          engineAvailable={JSON.parse(diagnosticsJson).engine !== null}
          onClose={() => setDiagnosticsJson(null)}
        />
      ) : null}
    </section>
  );
}
