import { useEffect, useRef, useState } from "react";

import { ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { BannerBridge, useBannerActionDispatcher } from "./banners/BannerBridge";
import { BannerProvider, useBanner } from "./banners/BannerProvider";
import { BannerStack } from "./banners/BannerStack";
import { BannerToasts } from "./banners/BannerToasts";
import { BootFailurePage } from "./components/BootFailurePage";
import { ChangelogModal } from "./components/ChangelogModal";
import { ChatStage } from "./components/chat/ChatStage";
import { ConnectorSuggestionModal } from "./components/customize/ConnectorSuggestionModal";
import { CustomizePage } from "./components/customize/CustomizePage";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { NavigationDrawer } from "./components/layout/NavigationDrawer";
import { QuickJump } from "./components/layout/QuickJump";
import { SharedArtifact } from "./components/SharedArtifact";
import { StudioBar } from "./components/layout/StudioBar";
import { WorkbenchRail } from "./components/workspace/WorkbenchRail";
import { WorkspacePanel } from "./components/workspace/WorkspacePanel";
import { dialogOpen, focusComposer, startComposerCommand } from "./lib/composerFocus";
import { isEditableTarget } from "./lib/commands";
import { MOBILE_QUERY, useMediaQuery } from "./lib/useMediaQuery";
import { useStudioCommands } from "./lib/useStudioCommands";
import { isFeatureEnabled } from "./features/flags";
import { sharedTokenFromPath } from "./lib/share";
import { isTauri } from "./bridge/desktopBridge";
import { FirstRunWizard, OnboardingProvider } from "./onboarding";
import { StudioRuntimeProvider } from "./assistant/StudioRuntime";
import { StudioProvider, useStudio } from "./state/StudioContext";
import { UpdateBanner, UpdateProvider } from "./updater";
import { initInstall } from "./install";

/**
 * One room, one intelligence.
 *
 * The drawer holds what you are working on, the conversation owns the
 * mainstage at every moment, and a detail docks on the right instead of
 * replacing the thread. The artifacts strip above the thread still names what
 * the inquiry has produced. Nothing is a prerequisite for anything else.
 */
function StudioShell() {
  const {
    activePanel,
    closePanel,
    closeSetup,
    customizeOpen,
    closeCustomize,
    drawerOpen,
    startNewThread,
    streaming,
    stopStreaming,
    toggleDrawer,
    bootError,
    recheckBoot,
  } = useStudio();
  const { view } = useBanner();
  const { onIntent, onAction, onDismiss } = useBannerActionDispatcher();
  const [showChangelog, setShowChangelog] = useState(false);
  const [quickJumpOpen, setQuickJumpOpen] = useState(false);
  const drawerEnabled = isFeatureEnabled("studioDrawer");
  const isMobile = useMediaQuery(MOBILE_QUERY);
  const runCommand = useStudioCommands();
  // New inquiry closes the sheet; the caret moves on the commit after that,
  // so the focus trap's own restore cannot take it back.
  const focusAfterJump = useRef(false);
  const focusAfterDrawerClose = useRef(false);

  function goHome() {
    // Home closes what is open and leaves the thread alone. Discarding it is
    // the other control's job, and only after asking what is being lost.
    closePanel();
    closeSetup();
    closeCustomize();
  }

  // The drawer and Quick jump share the name New inquiry, so they share one
  // meaning: put the caret in the composer without discarding the thread.
  // Discarding stays behind the bar's New thread, which asks before it does.
  // On a sheet the drawer closes first, and its focus trap restores the toggle
  // on that commit; the effect below takes the caret back afterwards.
  function newInquiry() {
    if (drawerEnabled && drawerOpen && isMobile) {
      focusAfterDrawerClose.current = true;
      toggleDrawer();
    } else {
      focusComposer();
    }
  }

  function newThread(options?: { stop?: boolean }) {
    startNewThread(options);
    closePanel();
    closeSetup();
    closeCustomize();
    newInquiry();
  }

  // One listener for the keys the whole room shares. The composer registers
  // how to take the caret (lib/composerFocus), so this is installed once for
  // the shell instead of once per composer.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const modifier = event.metaKey || event.ctrlKey;

      if (modifier && !event.altKey && event.key.toLowerCase() === "k") {
        if (dialogOpen()) {
          return;
        }
        // One key, one meaning: the sheet, whose first row is New inquiry
        // (#736). With the drawer flag off the old composer binding returns.
        if (drawerEnabled) {
          event.preventDefault();
          setQuickJumpOpen(true);
          return;
        }
        if (focusComposer()) {
          event.preventDefault();
        }
        return;
      }

      // `/` is a command only where it cannot be a character: inside a field
      // the slash belongs to what the person is typing.
      if (event.key === "/" && !modifier && !event.altKey) {
        if (dialogOpen() || isEditableTarget(event.target)) {
          return;
        }
        if (startComposerCommand()) {
          event.preventDefault();
        }
        return;
      }

      if (event.key === "Escape") {
        // A dialog owns its Escape. Closing it must not also stop the reply
        // behind it or move the caret out from under the person.
        if (dialogOpen()) {
          return;
        }
        // Backing out goes right to left: the detail first, then the drawer,
        // and only then the reply still streaming on the mainstage (#735/#736).
        if (activePanel) {
          closePanel();
          return;
        }
        if (drawerEnabled && drawerOpen) {
          toggleDrawer();
          return;
        }
        if (streaming) {
          stopStreaming();
          return;
        }
        // Nothing is open, so Escape does the one thing it can: it takes you
        // back to the place where you can type.
        focusComposer();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    activePanel,
    closePanel,
    drawerEnabled,
    drawerOpen,
    streaming,
    stopStreaming,
    toggleDrawer,
  ]);

  // The sheet's first row hands the caret back only after the dialog has
  // unmounted, so its focus trap cannot restore the opener over the composer.
  useEffect(() => {
    if (!quickJumpOpen && focusAfterJump.current) {
      focusAfterJump.current = false;
      focusComposer();
    }
  }, [quickJumpOpen]);

  // Closing the drawer on a phone happens in its own commit; take the caret
  // back once the sheet's focus trap has finished restoring the toggle.
  useEffect(() => {
    if (!drawerOpen && focusAfterDrawerClose.current) {
      focusAfterDrawerClose.current = false;
      focusComposer();
    }
  }, [drawerOpen]);

  // Capture the install prompt as early as possible so the browser's
  // beforeinstallprompt event is not missed before Settings is opened.
  useEffect(() => {
    initInstall();
  }, []);

  // Remember the window size across desktop sessions so the app reopens at the
  // size the person last chose, like Linear / Copilot. No-op in the browser
  // and in tests (isTauri is false there).
  useEffect(() => {
    if (!isTauri()) return;
    const win = getCurrentWebviewWindow();
    let unlisten: (() => void) | undefined;

    const save = () => {
      win.innerSize().then(({ width, height }) => {
        try {
          localStorage.setItem("studio:window-size", JSON.stringify({ width, height }));
        } catch { /* ignored: storage may be unavailable or quota-full */ }
      }).catch(() => {});
    };

    (async () => {
      try {
        const raw = localStorage.getItem("studio:window-size");
        if (raw) {
          const { width, height } = JSON.parse(raw);
          await win.setSize(new LogicalSize(width, height));
        }
      } catch { /* ignored: malformed stored size or tauri unavailable */ }
      const un = await win.listen("tauri://resize", () => save());
      unlisten = un;
    })();

    window.addEventListener("beforeunload", save);

    return () => {
      unlisten?.();
      window.removeEventListener("beforeunload", save);
    };
  }, []);

  // A damaged database is not a broken screen: the file is intact on disk and
  // the only honest thing to show is that failure, not a zeroed-out studio.
  // This return sits after every hook so the hook order never changes.
  if (bootError) {
    return <BootFailurePage error={bootError} onRecheck={() => void recheckBoot()} />;
  }

  return (
    <div className="studio-app">
      <a className="skip-link" href="#studio-stage">
        Skip to conversation
      </a>
      <BannerBridge />
      <BannerToasts />
      <BannerStack
        banners={view.visible}
        overflow={view.overflow}
        onDismiss={onDismiss}
        onAction={onAction}
        onIntent={onIntent}
      />
      <StudioBar
        onHome={goHome}
        onNew={newThread}
        onChangelog={() => setShowChangelog(true)}
        drawerEnabled={drawerEnabled}
        drawerOpen={drawerOpen}
        onToggleDrawer={toggleDrawer}
      />
      <UpdateBanner />
      <main id="studio-stage" className="stage" tabIndex={-1}>
        {customizeOpen ? (
          <CustomizePage />
        ) : (
          <div className="stage__split">
            {drawerEnabled && <NavigationDrawer onHome={goHome} onNew={newInquiry} />}
            <ResizablePanelGroup orientation="horizontal" className="stage__split-group">
              <ResizablePanel className="stage__thread" minSize="40%">
                <WorkbenchRail
                  label={drawerEnabled ? "What this thread made" : undefined}
                  jobMapInDrawer={drawerEnabled}
                />
                <ChatStage />
              </ResizablePanel>
              <WorkspacePanel />
            </ResizablePanelGroup>
          </div>
        )}
      </main>
      <ChangelogModal isOpen={showChangelog} onClose={() => setShowChangelog(false)} />
      {quickJumpOpen && (
        <QuickJump
          open
          onClose={() => setQuickJumpOpen(false)}
          onNewInquiry={() => {
            focusAfterJump.current = true;
            setQuickJumpOpen(false);
          }}
          onCommand={runCommand}
        />
      )}
      <ConnectorSuggestionModal />
    </div>
  );
}

export { StudioShell };

export default function App() {
  // A shared link opens one artifact and nothing else. It must render without
  // the workspace boot — no canvas fetch, no rail, no composer, no sidecar
  // config — so it is decided before any provider mounts.
  const sharedToken =
    typeof window === "undefined" ? null : sharedTokenFromPath(window.location.pathname);

  if (sharedToken) {
    return (
      <ErrorBoundary>
        <SharedArtifact token={sharedToken} />
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <UpdateProvider>
        <StudioProvider>
          <BannerProvider>
            <StudioRuntimeProvider>
              <OnboardingProvider>
                <StudioShell />
                <FirstRunWizard />
              </OnboardingProvider>
            </StudioRuntimeProvider>
          </BannerProvider>
        </StudioProvider>
      </UpdateProvider>
    </ErrorBoundary>
  );
}
