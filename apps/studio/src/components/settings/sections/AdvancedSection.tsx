import { useOnboarding } from "../../../onboarding/context";
import { UpdateSettings, useUpdateService, useUpdateSnapshot } from "../../../updater";
import { detectPlatform } from "../../../updater/platform";

const PLATFORM_LABELS: Record<ReturnType<typeof detectPlatform>, string> = {
  macos: "macOS",
  windows: "Windows",
  linux: "Linux",
  unknown: "Desktop",
};

export function AdvancedSection({
  headingId = "settings-advanced-heading",
  sectionId,
}: {
  headingId?: string;
  sectionId?: string;
}) {
  const { enabled: tourEnabled, restart: restartTour } = useOnboarding();
  const service = useUpdateService();
  const snapshot = useUpdateSnapshot();
  const platform = detectPlatform();

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
      <section className="settings__about" aria-labelledby={`${headingId}-about`}>
        <h4 className="settings__title" id={`${headingId}-about`}>About</h4>
        <dl>
          <dt>Build</dt>
          <dd>{__STUDIO_BUILD_DATE__}</dd>
          <dt>Platform</dt>
          <dd>{PLATFORM_LABELS[platform]}</dd>
          <dt>Version</dt>
          <dd>{snapshot.currentVersion ? `v${snapshot.currentVersion}` : "—"}</dd>
          <dt>Updates</dt>
          <dd>{service.statusLine()}</dd>
        </dl>
      </section>
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
