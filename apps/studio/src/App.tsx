import { useEffect, useState } from "react";

import { StudioRuntimeProvider } from "./assistant/StudioRuntime";
import { BannerBridge, useBannerActionDispatcher } from "./banners/BannerBridge";
import { BannerProvider, useBanner } from "./banners/BannerProvider";
import { BannerStack } from "./banners/BannerStack";
import { BannerToasts } from "./banners/BannerToasts";
import { ChangelogModal } from "./components/ChangelogModal";
import { ChatStage } from "./components/chat/ChatStage";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { StudioBar } from "./components/layout/StudioBar";
import { WorkbenchRail } from "./components/workspace/WorkbenchRail";
import { WorkspacePanel } from "./components/workspace/WorkspacePanel";
import { FirstRunWizard, OnboardingProvider } from "./onboarding";
import { StudioProvider, useStudio } from "./state/StudioContext";
import { UpdateBanner, UpdateProvider } from "./updater";

/**
 * One room, one intelligence.
 *
 * The conversation owns the stage at every moment. The rail above it is the
 * only navigation, and it is derived from what the thread has produced. A
 * workspace view docks beside the thread instead of replacing it, so the
 * composer never leaves the screen.
 */
function StudioShell() {
  const { closePanel, clearChat, closeSetup } = useStudio();
  const { view } = useBanner();
  const { onIntent, onAction, onDismiss } = useBannerActionDispatcher();
  const [showChangelog, setShowChangelog] = useState(false);

  function goHome() {
    clearChat();
    closePanel();
    closeSetup();
  }

  function newConversation() {
    clearChat();
    closePanel();
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closePanel();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [closePanel]);

  return (
    <div className="studio-app">
      <BannerBridge />
      <BannerToasts />
      <BannerStack
        banners={view.visible}
        overflow={view.overflow}
        onDismiss={onDismiss}
        onAction={onAction}
        onIntent={onIntent}
      />
      <main className="stage">
        <StudioBar
          onHome={goHome}
          onNew={newConversation}
          onChangelog={() => setShowChangelog(true)}
        />
        <UpdateBanner />
        <div className="stage__split">
          <div className="stage__thread">
            <WorkbenchRail />
            <ChatStage />
          </div>
          <WorkspacePanel />
        </div>
      </main>
      <ChangelogModal isOpen={showChangelog} onClose={() => setShowChangelog(false)} />
    </div>
  );
}

export default function App() {
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
