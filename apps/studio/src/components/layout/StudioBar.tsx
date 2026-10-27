import { useEffect, useRef, useState } from "react";

import { conversationToMarkdown, downloadMarkdown, exportFilename } from "../../lib/export";
import { useStudio } from "../../state/StudioContext";
import { BellIcon, MenuIcon, MoonIcon, PlusIcon, SettingsIcon, SunIcon } from "../icons";
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
    unreadNotificationCount,
    markAllNotificationsAsRead,
    openPanel,
    pushToast,
    saveSettings,
    settings,
  } = useStudio();
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

  const status =
    llmHealth.healthy === null ? "Connecting" : llmHealth.healthy ? "Live" : "Local mode";

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
          aria-label="Catch up notifications"
          title="Activity & Catch Up"
          onClick={() => {
            markAllNotificationsAsRead();
            openPanel("catchup");
          }}
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
          aria-label={`Model status: ${status}. ${llmHealth.message}`}
          title={llmHealth.message}
        >
          <span
            className={`status-dot${llmHealth.healthy === false ? " is-warn" : ""}${
              llmHealth.healthy === null ? " is-unknown" : ""
            }`}
          />
          {status}
        </button>

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
    </header>
  );
}
