import { useStudio } from "../../state/StudioContext";
import { useUpdateSnapshot } from "../../updater";
import { BellIcon, PlusIcon, SettingsIcon, SparkIcon } from "../icons";

/**
 * The only persistent chrome: where you are, how to start again, whether the
 * studio can hear you, and the way out to settings. No navigation lives here —
 * the artifacts above the conversation carry that.
 */
export function StudioBar({
  onHome,
  onNew,
  onChangelog,
}: {
  onHome: () => void;
  onNew: () => void;
  onChangelog: () => void;
}) {
  const { llmHealth, unreadNotificationCount, openPanel } = useStudio();
  const update = useUpdateSnapshot();

  const status =
    llmHealth.healthy === null ? "Connecting" : llmHealth.healthy ? "Live" : "Local mode";
  const updateReady = update.phase === "ready";
  const versionLabel = updateReady
    ? "Update ready"
    : update.currentVersion
      ? `v${update.currentVersion}`
      : null;

  return (
    <header className="bar">
      <div className="bar__left">
        <button
          type="button"
          className="brand brand--home"
          onClick={onHome}
          aria-label="Go to home"
          title="Home"
        >
          <span className="brand__mark" aria-hidden="true">
            <OdiMascot size={32} />
          </span>
          <span className="brand__wordmark">Living Studio</span>
        </button>
      </div>

      <div className="bar__right">
        <button
          type="button"
          className="studio-pill pill-changelog"
          onClick={onChangelog}
          aria-label="Open What's New changelog"
        >
          ✨ What's New
        </button>

        <button
          type="button"
          className="icon-button"
          aria-label="New conversation"
          title="New conversation"
          onClick={onNew}
        >
          <PlusIcon size={17} />
        </button>

        <button
          type="button"
          className="icon-button bar__bell"
          aria-label="Catch up notifications"
          title="Activity & Catch Up"
          onClick={() => openPanel("catchup")}
        >
          <BellIcon size={17} />
          {unreadNotificationCount > 0 && (
            <span className="bell-badge" aria-hidden="true">
              {unreadNotificationCount}
            </span>
          )}
        </button>

        <button
          type="button"
          className="bar__health"
          onClick={() => openPanel("settings")}
          title={llmHealth.message}
        >
          <span
            className={`status-dot${llmHealth.healthy === false ? " is-warn" : ""}${
              llmHealth.healthy === null ? " is-unknown" : ""
            }`}
          />
          {status}
        </button>

        {versionLabel && (
          <button
            type="button"
            className={`bar__version${updateReady ? " is-accent" : ""}`}
            onClick={() => openPanel("settings")}
            title={
              update.currentVersion
                ? `Living Studio ${update.currentVersion} — open software update settings`
                : "Open software update settings"
            }
          >
            {versionLabel}
          </button>
        )}

        <button
          type="button"
          className="icon-button"
          aria-label="Open settings"
          title="Settings"
          onClick={() => openPanel("settings")}
        >
          <SettingsIcon size={17} />
        </button>
      </div>
    </header>
  );
}
