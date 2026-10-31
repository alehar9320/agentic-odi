import { useEffect, useRef, useState } from "react";

import { conversationToMarkdown, downloadMarkdown, exportFilename } from "../../lib/export";
import { useStudio } from "../../state/StudioContext";
import { useUpdateSnapshot } from "../../updater";
import type { Conversation } from "../../types";
import {
  BellIcon,
  MenuIcon,
  MoonIcon,
  PlugIcon,
  PlusIcon,
  SettingsIcon,
  SunIcon,
  ThreadsIcon,
} from "../icons";
import { OdiMascot } from "../OdiMascot";

/** A thread is named by the first thing said in it; until then, by when it was left. */
function threadTitle(conversation: Conversation): string {
  const title = conversation.title?.trim();
  if (title) {
    return title;
  }
  const when = new Date(conversation.updated_at);
  return Number.isNaN(when.getTime())
    ? "Untitled conversation"
    : `Conversation, ${when.toLocaleString()}`;
}

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
    unreadSignalCount,
    openPanel,
    openCustomize,
    pushToast,
    saveSettings,
    settings,
    conversations,
    conversationId,
    openConversation,
    deleteConversation,
    refreshConversations,
  } = useStudio();
  const update = useUpdateSnapshot();
  const theme = settings.theme === "light" ? "light" : "dark";
  const nextTheme = theme === "dark" ? "light" : "dark";
  const [menuOpen, setMenuOpen] = useState(false);
  const [threadsOpen, setThreadsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const threadsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen && !threadsOpen) {
      return;
    }
    function onPointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (menuRef.current && !menuRef.current.contains(target)) {
        setMenuOpen(false);
      }
      if (threadsRef.current && !threadsRef.current.contains(target)) {
        setThreadsOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenuOpen(false);
        setThreadsOpen(false);
      }
    }
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen, threadsOpen]);

  function exportConversation() {
    const exportedAt = new Date();
    downloadMarkdown(conversationToMarkdown(messages, exportedAt), exportFilename(exportedAt));
    setMenuOpen(false);
    pushToast("success", "Conversation exported as Markdown.");
  }

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

        <div className="bar__menu" ref={threadsRef}>
          <button
            type="button"
            className="icon-button"
            aria-label="Open stored conversations"
            title="Stored conversations"
            aria-haspopup="menu"
            aria-expanded={threadsOpen}
            onClick={() => {
              setThreadsOpen((open) => !open);
              void refreshConversations();
            }}
          >
            <ThreadsIcon size={17} />
          </button>
          {threadsOpen && (
            <div
              className="bar__menu-list bar__threads"
              role="menu"
              aria-label="Stored conversations"
            >
              {conversations.length === 0 && (
                <p className="bar__threads-empty">Nothing stored yet.</p>
              )}
              {conversations.map((conversation) => (
                <div
                  key={conversation.id}
                  className={`bar__thread${
                    conversation.id === conversationId ? " is-current" : ""
                  }`}
                >
                  <button
                    type="button"
                    role="menuitem"
                    className="bar__menu-item bar__thread-open"
                    onClick={() => {
                      setThreadsOpen(false);
                      void openConversation(conversation.id);
                    }}
                  >
                    <span className="bar__thread-title">{threadTitle(conversation)}</span>
                    {conversation.archived && (
                      <span className="bar__thread-tag">archived</span>
                    )}
                  </button>
                  <button
                    type="button"
                    className="bar__thread-delete"
                    aria-label={`Delete ${threadTitle(conversation)}`}
                    title="Delete this conversation"
                    onClick={() => {
                      void deleteConversation(conversation.id);
                    }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

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
