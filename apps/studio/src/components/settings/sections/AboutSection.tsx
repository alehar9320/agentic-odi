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
import { versionLabel } from "../../../lib/version";
import { useOnboarding } from "../../../onboarding/context";
import type { StudioConfig } from "../../../types";
import { useUpdateSnapshot } from "../../../updater";
import { detectPlatform } from "../../../updater/platform";

const PLATFORM_LABELS: Record<ReturnType<typeof detectPlatform>, string> = {
  macos: "macOS",
  windows: "Windows",
  linux: "Linux",
  unknown: "Desktop",
};

/** The product essay that used to sit behind "How the studio works". */
const PRODUCT_ESSAY =
  "Backlogs and ticket accounting give way to a canvas of human intent. Point at an outcome, " +
  "then talk about it: every bet traces back to evidence, and impact is simulated before code " +
  "gets written.";

interface AboutSectionProps {
  settings: StudioConfig;
  capabilities: Capability[];
}

/**
 * The honest facts about this build: which version, which commit, cut when, and
 * for which platform — plus the essay about what the studio is and the one way
 * to start the tour. Read-only: the updater's state and its action live in
 * Updates, so nothing here repeats them.
 *
 * The version is never a literal. `versionLabel` takes the desktop updater's
 * running version when it has one and falls back to the version baked in from
 * `apps/studio/package.json`, which release-please bumps alongside
 * `_build_info.py`.
 */
export function AboutSection({ settings, capabilities }: AboutSectionProps) {
  const snapshot = useUpdateSnapshot();
  const platform = detectPlatform();
  const { enabled: tourEnabled, openTour } = useOnboarding();
  const label = versionLabel(snapshot.currentVersion);
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
      version: label.version,
      versionSource: label.source,
      build: `${__STUDIO_BUILD_DATE__} (${__STUDIO_BUILD_COMMIT__})`,
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
      <p className="muted">{PRODUCT_ESSAY}</p>
      <dl>
        <dt>Version</dt>
        <dd>v{label.version}</dd>
        <dt>Commit</dt>
        <dd>{__STUDIO_BUILD_COMMIT__}</dd>
        <dt>Build date</dt>
        <dd>{__STUDIO_BUILD_DATE__}</dd>
        <dt>Platform</dt>
        <dd>{PLATFORM_LABELS[platform]}</dd>
      </dl>
      {tourEnabled ? (
        <p className="settings__tour">
          <button type="button" className="settings__tour-link" onClick={openTour}>
            Take the tour
          </button>
        </p>
      ) : null}
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
