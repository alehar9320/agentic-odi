import { useEffect, useRef, useState } from "react";

import { conversationToMarkdown, downloadMarkdown, exportFilename } from "../../lib/export";
import { isEndpointConfiguredForSettings } from "../../lib/modelEndpoint";
import { useStudio } from "../../state/StudioContext";
import { useUpdateSnapshot } from "../../updater";
import { BellIcon, MenuIcon, MoonIcon, PlugIcon, PlusIcon, SettingsIcon, SunIcon } from "../icons";
import { OdiMascot } from "../OdiMascot";

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
  const {
    llmHealth,
    messages,
    sidecarReachable,
    unreadSignalCount,
    openPanel,
    openCustomize,
    pushToast,
    saveSettings,
    settings,
  } = useStudio();
  const update = useUpdateSnapshot();
  const theme = settings.theme === "light" ? "light" : "dark";
  const nextTheme = theme === "dark" ? "light" : "dark";
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }
    function onPointerDown(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    }
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen]);

  function exportConversation() {
    const exportedAt = new Date();
    downloadMarkdown(conversationToMarkdown(messages, exportedAt), exportFilename(exportedAt));
    setMenuOpen(false);
    pushToast("success", "Conversation exported as Markdown.");
  }

  // A measured answer outranks an inference from the settings. The shipped desktop
  // default points at the sidecar's own proxy — a loopback address the browser cannot
  // talk model-to — so guessing from the endpoint alone would read "no model connected"
  // forever on a machine where the model is in fact answering. "Connecting" is for a
  // connection somebody is trying to make and has not yet heard back from.
  const endpointConfigured = isEndpointConfiguredForSettings({
    base_url: settings.base_url,
    api_key: settings.api_key,
    model_name: settings.model_name,
  });
  const status =
    llmHealth.healthy === true
      ? "Live"
      : llmHealth.healthy === false
        ? "Local mode"
        : endpointConfigured || sidecarReachable === true
          ? "Connecting"
          : "Local";
  const statusDetail =
    status === "Local" ? "Answering from your device. No model connected." : llmHealth.message;
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
          className="studio-pill pill-customize"
          onClick={() => openCustomize()}
          aria-label="Customize connectors"
          title="Customize connectors"
        >
          <PlugIcon size={15} />
          Customize
        </button>

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
          className="icon-button"
          aria-label={`Switch to ${nextTheme} theme`}
          title={`Switch to ${nextTheme} theme`}
          onClick={() => saveSettings({ ...settings, theme: nextTheme })}
        >
          {theme === "dark" ? <SunIcon size={17} /> : <MoonIcon size={17} />}
        </button>

        <button
          type="button"
          className="icon-button bar__bell"
          aria-label={
            unreadSignalCount > 0
              ? `Signal inbox: ${unreadSignalCount} unread`
              : "Signal inbox: no unread signals"
          }
          title="Signals from the store"
          onClick={() => openPanel("catchup")}
        >
          <BellIcon size={17} />
          {unreadSignalCount > 0 && <span className="bell-badge">{unreadSignalCount}</span>}
        </button>

        <button
          type="button"
          className="bar__health"
          onClick={() => openPanel("settings")}
          aria-label={`Model status: ${status}. ${statusDetail}`}
          title={statusDetail}
        >
          <span
            className={`status-dot${status === "Local mode" ? " is-warn" : ""}${
              status === "Connecting" ? " is-unknown" : ""
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

        <div className="bar__menu" ref={menuRef}>
          <button
            type="button"
            className="icon-button"
            aria-label="More actions"
            title="More actions"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <MenuIcon size={17} />
          </button>
          {menuOpen && (
            <div className="bar__menu-list" role="menu" aria-label="More actions">
              <button
                type="button"
                role="menuitem"
                className="bar__menu-item"
                onClick={exportConversation}
                disabled={messages.length === 0}
              >
                Export → Markdown
              </button>
            </div>
          )}
        </div>
      </div>

      {/* The bell's label carries the current count; this announces changes. */}
      <p className="sr-only" role="status" aria-live="polite">
        {unreadSignalCount > 0
          ? `${unreadSignalCount} new ${unreadSignalCount === 1 ? "notification" : "notifications"}`
          : ""}
      </p>
    </header>
  );
}
