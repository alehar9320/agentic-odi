import { useState } from "react";

import { fetchDiagnostics } from "../../../api/studioApi";
import type { SidecarDiagnostics } from "../../../api/studioApi";
import {
  createDiagnosticsBundle,
  diagnosticsEntryCount,
  startDiagnosticsCapture,
} from "../../../diagnostics/bundle";
import { DiagnosticsModal } from "../../../diagnostics/DiagnosticsModal";
import { useOnboarding } from "../../../onboarding/context";
import type { StudioConfig } from "../../../types";
import { UpdateSettings, useUpdateService, useUpdateSnapshot } from "../../../updater";
import { detectPlatform } from "../../../updater/platform";

const STUDIO_VERSION = "0.14.0";

const PLATFORM_LABELS: Record<ReturnType<typeof detectPlatform>, string> = {
  macos: "macOS",
  windows: "Windows",
  linux: "Linux",
  unknown: "Desktop",
};

/**
 * The honest facts about this build: which version, cut when, for which
 * platform, and what the updater thinks. Read-only — the controls live in
 * the Software update section above.
 */
function AboutSection({
  settings,
  capabilities,
}: {
  settings: StudioConfig;
  capabilities: unknown[];
}) {
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
      theme: settings.theme === "light" ? "light" : "dark",
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
    <section className="settings__about" aria-labelledby={`${"settings-advanced-heading"}-about`}>
      <h4 className="settings__title" id="settings-advanced-heading-about">
        About
      </h4>
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

export function AdvancedSection({
  headingId = "settings-advanced-heading",
  sectionId,
  settings,
  capabilities,
}: {
  headingId?: string;
  sectionId?: string;
  settings: StudioConfig;
  capabilities: unknown[];
}) {
  const { enabled: tourEnabled, restart: restartTour } = useOnboarding();

  return (
    <section id={sectionId} className="settings__section" aria-labelledby={headingId} tabIndex={sectionId ? -1 : undefined}>
      <h3 className="settings__title" id={headingId}>Advanced</h3>
      {tourEnabled ? (
        <div className="settings__tour">
          <h4 className="settings__title">Getting started</h4>
          <p className="muted">A four-step product tour, when you want one. It never opens by itself.</p>
          <button type="button" className="button button--ghost" onClick={restartTour}>Replay the tour</button>
        </div>
      ) : null}
      <UpdateSettings />
      <AboutSection settings={settings} capabilities={capabilities} />
      <details className="disclosure">
        <summary>How the studio works</summary>
        <p>
          The Living Studio replaces backlogs and ticket accounting with a canvas of human intent.
          Point at an outcome, then talk about it: every bet traces back to evidence, and impact is
          simulated before code gets written.
        </p>
      </details>
    </section>
  );
}
