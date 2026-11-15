import { useEffect, useState } from "react";

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
import { SharedArtifact } from "./components/SharedArtifact";
import { StudioBar } from "./components/layout/StudioBar";
import { WorkbenchRail } from "./components/workspace/WorkbenchRail";
import { WorkspacePanel } from "./components/workspace/WorkspacePanel";
import { dialogOpen, focusComposer, startComposerCommand } from "./lib/composerFocus";
import { isEditableTarget } from "./lib/commands";
import { sharedTokenFromPath } from "./lib/share";
import { FirstRunWizard, OnboardingProvider } from "./onboarding";
import { ActivityProvider } from "./notices/ActivityProvider";
import { StudioRuntimeProvider } from "./assistant/StudioRuntime";
import { StudioProvider, useStudio } from "./state/StudioContext";
import { UpdateBanner, UpdateProvider } from "./updater";
import { initInstall } from "./install";

/**
 * One room, one intelligence.
 *
 * The conversation owns the stage at every moment. The rail above it is the
 * only navigation, and it is derived from what the thread has produced. A
 * workspace view docks beside the thread instead of replacing it, so the
 * composer never leaves the screen.
 */
function StudioShell() {
  const {
    activePanel,
    closePanel,
    closeSetup,
    customizeOpen,
    closeCustomize,
    startNewThread,
    streaming,
    stopStreaming,
    bootError,
    recheckBoot,
  } = useStudio();
  const { view } = useBanner();
  const { onIntent, onAction, onDismiss } = useBannerActionDispatcher();
  const [showChangelog, setShowChangelog] = useState(false);

  function goHome() {
    // Home closes what is open and leaves the thread alone. Discarding it is
    // the other control's job, and only after asking what is being lost.
    closePanel();
    closeSetup();
    closeCustomize();
  }

  function newThread(options?: { stop?: boolean }) {
    startNewThread(options);
    closePanel();
    closeSetup();
    closeCustomize();
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
        if (streaming) {
          stopStreaming();
          return;
        }
        if (activePanel) {
          closePanel();
          return;
        }
        // Nothing is open, so Escape does the one thing it can: it takes you
        // back to the place where you can type.
        focusComposer();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activePanel, closePanel, streaming, stopStreaming]);

  // Capture the install prompt as early as possible so the browser's
  // beforeinstallprompt event is not missed before Settings is opened.
  useEffect(() => {
    initInstall();
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
      />
      <UpdateBanner />
      <main id="studio-stage" className="stage" tabIndex={-1}>
        {customizeOpen ? (
          <CustomizePage />
        ) : (
          <div className="stage__split">
            <div className="stage__thread">
              <WorkbenchRail />
              <ChatStage />
            </div>
            <WorkspacePanel />
          </div>
        )}
      </main>
      <ChangelogModal isOpen={showChangelog} onClose={() => setShowChangelog(false)} />
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
                <ActivityProvider>
                  <StudioShell />
                  <FirstRunWizard />
                </ActivityProvider>
              </OnboardingProvider>
            </StudioRuntimeProvider>
          </BannerProvider>
        </StudioProvider>
      </UpdateProvider>
    </ErrorBoundary>
  );
}
