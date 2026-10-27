import { useEffect, useState } from "react";

import { ChatStage } from "./components/chat/ChatStage";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { MenuIcon, SettingsIcon } from "./components/icons";
import { Sidebar } from "./components/layout/Sidebar";
import { Toasts } from "./components/Toasts";
import { WorkspacePanel } from "./components/workspace/WorkspacePanel";
import { useMediaQuery } from "./lib/useMediaQuery";
import { StudioProvider, useStudio } from "./state/StudioContext";

const COLLAPSED_KEY = "studio.sidebarCollapsed";
const MOBILE_QUERY = "(max-width: 1023px)";

function loadCollapsed(): boolean {
  try {
    const stored = localStorage.getItem(COLLAPSED_KEY);
    if (stored !== null) {
      return stored === "1";
    }
  } catch {
    /* storage unavailable */
  }
  return false;
}

function StudioShell() {
  const { activePanel, closePanel, openPanel, llmHealth, clearChat, closeSetup } = useStudio();
  const [desktopCollapsed, setDesktopCollapsed] = useState(loadCollapsed);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const isMobile = useMediaQuery(MOBILE_QUERY);

  // The drawer is a rail on desktop and a full overlay sheet on phones.
  const collapsed = isMobile ? !drawerOpen : desktopCollapsed;

  function toggleDrawer() {
    if (isMobile) {
      setDrawerOpen((prev) => !prev);
    } else {
      setDesktopCollapsed((prev) => !prev);
    }
  }

  function closeDrawer() {
    if (isMobile) {
      setDrawerOpen(false);
    }
  }

  function goHome() {
    clearChat();
    closePanel();
    closeSetup();
    setDrawerOpen(false);
  }

  useEffect(() => {
    if (isMobile) {
      return;
    }
    try {
      localStorage.setItem(COLLAPSED_KEY, desktopCollapsed ? "1" : "0");
    } catch {
      /* storage unavailable */
    }
  }, [desktopCollapsed, isMobile]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "b") {
        event.preventDefault();
        if (isMobile) {
          setDrawerOpen((prev) => !prev);
        } else {
          setDesktopCollapsed((prev) => !prev);
        }
      }
      if (event.key === "Escape") {
        closePanel();
        if (isMobile) {
          setDrawerOpen(false);
        }
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [closePanel, isMobile]);

  return (
    <div className={`studio-app${collapsed ? " studio-app--collapsed" : ""}`}>
      <Sidebar
        collapsed={collapsed}
        onToggle={toggleDrawer}
        onNavigate={closeDrawer}
        onHome={goHome}
      />

      {isMobile && drawerOpen && (
        <button
          type="button"
          className="scrim"
          aria-label="Close navigation"
          onClick={closeDrawer}
        />
      )}

      <main className="stage">
        <header className="bar">
          <div className="bar__left">
            {collapsed && (
              <button
                type="button"
                className="icon-button"
                aria-label="Open navigation"
                title="Open navigation"
                onClick={toggleDrawer}
              >
                <MenuIcon size={18} />
              </button>
            )}
            {collapsed && (
              <button type="button" className="bar__brand" onClick={goHome}>
                Living Studio
              </button>
            )}
          </div>
          <div className="bar__right">
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
              {llmHealth.healthy === null
                ? "Connecting"
                : llmHealth.healthy
                  ? "Live"
                  : "Local mode"}
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label="Open settings"
              title="Settings"
              onClick={() => openPanel("settings")}
            >
              <SettingsIcon size={18} />
            </button>
          </div>
        </header>

        <div className="stage__body">
          {activePanel ? <WorkspacePanel /> : <ChatStage />}
        </div>
      </main>

      <Toasts />
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <StudioProvider>
        <StudioShell />
      </StudioProvider>
    </ErrorBoundary>
  );
}
