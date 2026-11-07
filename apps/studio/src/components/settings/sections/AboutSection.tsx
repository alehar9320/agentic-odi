import { useState } from "react";

import { fetchDiagnostics } from "../../../api/studioApi";
import type { SidecarDiagnostics } from "../../../api/studioApi";
import {
  createDiagnosticsBundle,
  diagnosticsEntryCount,
  startDiagnosticsCapture,
} from "../../../diagnostics/bundle";
import { DiagnosticsModal } from "../../../diagnostics/DiagnosticsModal";
import { PRODUCT_NAME } from "../../../lib/brand";
import { resolveTheme } from "../../../lib/theme";
import { useOnboarding } from "../../../onboarding/context";
import type { StudioConfig } from "../../../types";
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

/**
 * What this build is: the version, commit, build date, platform, and the
 * product essay. Read-only facts, never a control — the updater's state and
 * action live in the Updates section.
 *
 * The version comes from the build-info source injected at build time
 * (`__STUDIO_APP_VERSION__`), so it moves with the release without being
 * invented here.
 */
export function AboutSection({
  settings,
  capabilities,
}: {
  settings: StudioConfig;
  capabilities: unknown[];
}) {
  const platform = detectPlatform();
  const { enabled: tourEnabled, openTour } = useOnboarding();
  const [diagnosticsJson, setDiagnosticsJson] = useState<string | null>(null);
  const version = __STUDIO_APP_VERSION__;
  const commit = __STUDIO_BUILD_COMMIT__;

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
      version,
      build: `${__STUDIO_BUILD_DATE__} (${commit})`,
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
        <dd>{version ? `v${version}` : "—"}</dd>
        <dt>Commit</dt>
        <dd>{commit}</dd>
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
