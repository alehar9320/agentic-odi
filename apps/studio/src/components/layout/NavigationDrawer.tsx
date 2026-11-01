import { useEffect, useRef } from "react";

import { useFocusTrap } from "../../lib/useFocusTrap";
import { useStudio } from "../../state/StudioContext";
import { CloseIcon, PlugIcon, PlusIcon, SettingsIcon } from "../icons";
import { WORKSPACE_PANELS } from "../workspace/panels";

/**
 * The way around the studio.
 *
 * The thread keeps the stage, but it is not the only place to go: the drawer is
 * where every lens, the connectors, the settings, and the conversations you
 * have already had are reachable. History is rendered as plain buttons that call
 * `switchConversation` / `clearChat` on the studio context, so switching threads
 * and starting a new one stay the studio's job.
 */
export function NavigationDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const {
    activePanel,
    conversations,
    conversationsLoading,
    conversationId,
    openPanel,
    openCustomize,
    customizeOpen,
    closeCustomize,
    switchConversation,
    clearChat,
    refreshConversations,
  } = useStudio();
  const drawerRef = useRef<HTMLElement>(null);

  useFocusTrap(drawerRef, open);

  // Refresh the conversation list whenever the drawer opens, so the history
  // reflects the latest stored threads.
  useEffect(() => {
    if (!open) {
      return;
    }
    void refreshConversations();
  }, [open, refreshConversations]);

  // Focus returns to whatever opened the drawer, so the keyboard never lands
  // somewhere unrelated after a close.
  useEffect(() => {
    if (!open) {
      return;
    }
    const previous = document.activeElement;
    return () => {
      if (previous instanceof HTMLElement) {
        previous.focus();
      }
    };
  }, [open]);

  // Capture, so an Escape closes the drawer instead of also stopping a reply.
  useEffect(() => {
    if (!open) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  function go(panel: (typeof WORKSPACE_PANELS)[number]["id"]) {
    openPanel(panel);
    onClose();
  }

  function customize() {
    openCustomize();
    onClose();
  }

  return (
    <>
      <button
        type="button"
        className="scrim drawer__scrim"
        aria-label="Close navigation"
        onClick={onClose}
      />
      <aside
        ref={drawerRef}
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        tabIndex={-1}
      >
        <header className="drawer__head">
          <span className="drawer__wordmark">Living Studio</span>
          <button
            type="button"
            className="icon-button"
            aria-label="Close navigation"
            title="Close navigation"
            onClick={onClose}
          >
            <CloseIcon size={17} />
          </button>
        </header>

        <div className="drawer__history">
          <button
            type="button"
            className="drawer__new"
            onClick={() => {
              clearChat();
              onClose();
            }}
          >
            <PlusIcon size={16} />
            New conversation
          </button>

          <p className="drawer__label" id="drawer-history-label">
            History
          </p>
          {conversationsLoading && conversations.length === 0 ? (
            <p className="drawer__empty">Loading your conversations…</p>
          ) : null}
          {!conversationsLoading && conversations.length === 0 ? (
            <p className="drawer__empty">
              Nothing saved yet. Every conversation you have appears here.
            </p>
          ) : null}
          {conversations.map((conversation) => (
            <button
              type="button"
              key={conversation.id}
              className="drawer__thread"
              data-active={conversation.id === conversationId ? "true" : undefined}
              onClick={() => {
                void switchConversation(conversation.id);
                onClose();
              }}
            >
              {conversation.title || "New conversation"}
            </button>
          ))}
        </div>

        <nav className="drawer__nav" aria-label="Workspace">
          <p className="drawer__label">Workspace</p>
          <ul className="drawer__list">
            {WORKSPACE_PANELS.map((panel) => {
              const active = !customizeOpen && activePanel === panel.id;
              return (
                <li key={panel.id}>
                  <button
                    type="button"
                    className={`drawer__item${active ? " is-active" : ""}`}
                    aria-current={active ? "page" : undefined}
                    onClick={() => go(panel.id)}
                    title={panel.blurb}
                  >
                    <span className="drawer__icon" aria-hidden="true">
                      {panel.icon}
                    </span>
                    <span className="drawer__item-label">{panel.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="drawer__foot">
          <button
            type="button"
            className={`drawer__item${customizeOpen ? " is-active" : ""}`}
            aria-current={customizeOpen ? "page" : undefined}
            onClick={customize}
          >
            <span className="drawer__icon" aria-hidden="true">
              <PlugIcon size={18} />
            </span>
            <span className="drawer__item-label">Customize connectors</span>
          </button>
          <button
            type="button"
            className={`drawer__item${!customizeOpen && activePanel === "settings" ? " is-active" : ""}`}
            aria-current={!customizeOpen && activePanel === "settings" ? "page" : undefined}
            onClick={() => {
              if (customizeOpen) {
                closeCustomize();
              }
              go("settings");
            }}
          >
            <span className="drawer__icon" aria-hidden="true">
              <SettingsIcon size={18} />
            </span>
            <span className="drawer__item-label">Settings</span>
          </button>
        </div>
      </aside>
    </>
  );
}
