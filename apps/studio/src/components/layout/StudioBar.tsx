import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";

import { LOCAL_MODE_LABEL, PRODUCT_NAME, versionLabel } from "../../lib/brand";
import { conversationToMarkdown, downloadMarkdown, exportFilename } from "../../lib/export";
import { isEndpointConfiguredForSettings } from "../../lib/modelEndpoint";
import { formatRelativeTime } from "../../lib/relativeTime";
import { resolveTheme } from "../../lib/theme";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { useStudio } from "../../state/StudioContext";
import { useUpdateSnapshot } from "../../updater";
import {
  BellIcon,
  HistoryIcon,
  MenuIcon,
  MoonIcon,
  PlugIcon,
  PlusIcon,
  SettingsIcon,
  SunIcon,
} from "../icons";
import { OdiMascot } from "../OdiMascot";
import { StatusDot } from "../status/StatusDot";

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
  onNew: (options?: { stop?: boolean }) => void;
  onChangelog: () => void;
}) {
  const {
    conversationId,
    conversations,
    llmHealth,
    messages,
    openConversation,
    refreshConversations,
    sidecarReachable,
    streaming,
    unreadSignalCount,
    openPanel,
    activePanel,
    customizeOpen,
    setupOpen,
    openCustomize,
    pushToast,
    saveSettings,
    settings,
  } = useStudio();
  const update = useUpdateSnapshot();
  const theme = resolveTheme(settings.theme);
  const nextTheme = theme === "dark" ? "light" : "dark";
  const [menuOpen, setMenuOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const wide = useMediaQuery("(min-width: 720px)");
  const [askOpen, setAskOpen] = useState(false);
  const askRef = useRef<HTMLDivElement>(null);
  const keepWritingRef = useRef<HTMLButtonElement>(null);
  const historyRef = useRef<HTMLDivElement>(null);
  // An empty transcript is only nothing to lose when nothing is on screen to
  // leave: the plus is the documented way out of the first-run setup, and a
  // disabled control there would strand the person in it.
  const nothingToLeave =
    messages.length === 0 && !streaming && !setupOpen && !customizeOpen && activePanel === null;

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

  useEffect(() => {
    if (!askOpen) {
      return;
    }
    // The ask is an interruption, not a mode: focus lands on the choice that
    // changes nothing, so an accidental Enter keeps the reply.
    keepWritingRef.current?.focus();
    function onPointerDown(event: MouseEvent) {
      if (askRef.current && !askRef.current.contains(event.target as Node)) {
        setAskOpen(false);
      }
    }
    window.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
    };
  }, [askOpen]);

  function startThread() {
    if (streaming) {
      setAskOpen((open) => !open);
      return;
    }
    onNew();
  }

  function onAskKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Escape" || !askOpen) {
      return;
    }
    // Stop the keystroke before the shell's global Escape hears it: closing the
    // ask is not the same as cancelling the reply still streaming behind it.
    event.stopPropagation();
    setAskOpen(false);
  }

  // The history list is read when it opens, not polled: a thread created by a
  // turn is added to the list by the turn itself.
  useEffect(() => {
    if (!historyOpen) {
      return;
    }
    function onPointerDown(event: MouseEvent) {
      if (historyRef.current && !historyRef.current.contains(event.target as Node)) {
        setHistoryOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setHistoryOpen(false);
      }
    }
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [historyOpen]);

  function toggleHistory() {
    setHistoryOpen((open) => {
      if (!open) {
        void refreshConversations();
      }
      return !open;
    });
  }

  function selectConversation(id: string) {
    setHistoryOpen(false);
    if (id !== conversationId) {
      void openConversation(id).catch(() =>
        pushToast("error", "I couldn't open that conversation."),
      );
    }
  }

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
        ? LOCAL_MODE_LABEL
        : endpointConfigured || sidecarReachable === true
          ? "Connecting"
          : "Local";
  const statusDetail =
    status === "Local" ? "Answering from your device. No model connected." : llmHealth.message;
  const updateReady = update.phase === "ready";
  const versionText = updateReady
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
          aria-label={`${PRODUCT_NAME}, go to home`}
          title="Home"
        >
          <span className="brand__mark" aria-hidden="true">
            <OdiMascot size={32} />
          </span>
          <span className="brand__wordmark">{PRODUCT_NAME}</span>
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

        <div className="bar__new-wrap" ref={askRef} onKeyDown={onAskKeyDown}>
          <button
            type="button"
            className="bar__new"
            onClick={startThread}
            disabled={nothingToLeave}
            aria-label="Start a new thread"
            aria-describedby={nothingToLeave ? "bar-new-reason" : undefined}
            aria-haspopup={streaming ? "dialog" : undefined}
            aria-expanded={streaming ? askOpen : undefined}
            title="New thread. Your jobs, outcomes, and evidence stay."
          >
            <PlusIcon size={17} />
            {wide && <span>New thread</span>}
          </button>

          {nothingToLeave && (
            <span id="bar-new-reason" className="sr-only">
              This thread is already new.
            </span>
          )}

          {askOpen && (
            <div className="bar__new-ask" role="dialog" aria-label="Stop the reply and start a new thread?">
              <p>A reply is still coming. Stop it and start a new thread?</p>
              <button
                type="button"
                ref={keepWritingRef}
                className="bar__new-choice"
                onClick={() => setAskOpen(false)}
              >
                Keep writing
              </button>
              <button
                type="button"
                className="bar__new-choice bar__new-choice--stop"
                onClick={() => {
                  setAskOpen(false);
                  onNew({ stop: true });
                }}
              >
                Stop and start
              </button>
            </div>
          )}
        </div>
        <div className="bar__menu" ref={historyRef}>
          <button
            type="button"
            className="icon-button"
            aria-label="Conversation history"
            title="Conversation history"
            aria-haspopup="menu"
            aria-expanded={historyOpen}
            onClick={toggleHistory}
          >
            <HistoryIcon size={17} />
          </button>
          {historyOpen && (
            <div
              className="bar__menu-list bar__history"
              role="menu"
              aria-label="Recent conversations"
            >
              {conversations.length === 0 ? (
                <p className="bar__history-empty">No conversations yet.</p>
              ) : (
                conversations.map((conversation) => {
                  const current = conversation.id === conversationId;
                  return (
                    <button
                      key={conversation.id}
                      type="button"
                      role="menuitem"
                      className="bar__menu-item bar__history-item"
                      aria-current={current ? "true" : undefined}
                      onClick={() => selectConversation(conversation.id)}
                    >
                      <span className="bar__history-title">
                        {conversation.title.trim() || "New conversation"}
                      </span>
                      <span className="bar__history-meta">
                        {formatRelativeTime(conversation.updated_at)}
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          )}
        </div>


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
          <StatusDot
            tone={status === "Local mode" ? "warn" : status === "Connecting" ? "unknown" : "ok"}
          />
          {status}
        </button>

        {versionText && (
          <button
            type="button"
            className={`bar__version${updateReady ? " is-accent" : ""}`}
            onClick={() => openPanel("settings")}
            title={
              update.currentVersion
                ? `${versionLabel(update.currentVersion)}, open software update settings`
                : "Open software update settings"
            }
          >
            {versionText}
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
