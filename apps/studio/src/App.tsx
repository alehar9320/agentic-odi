import { useEffect, useState } from "react";

import { BannerBridge, useBannerActionDispatcher } from "./banners/BannerBridge";
import { BannerProvider, useBanner } from "./banners/BannerProvider";
import { BannerStack } from "./banners/BannerStack";
import { BannerToasts } from "./banners/BannerToasts";
import { ChangelogModal } from "./components/ChangelogModal";
import { ChatStage } from "./components/chat/ChatStage";
import { ConnectorSuggestionModal } from "./components/customize/ConnectorSuggestionModal";
import { CustomizePage } from "./components/customize/CustomizePage";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { StudioBar } from "./components/layout/StudioBar";
import { WorkbenchRail } from "./components/workspace/WorkbenchRail";
import { WorkspacePanel } from "./components/workspace/WorkspacePanel";
import { FirstRunWizard, OnboardingProvider } from "./onboarding";
import { StudioRuntimeProvider } from "./assistant/StudioRuntime";
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
  const {
    closePanel,
    clearChat,
    closeSetup,
    customizeOpen,
    closeCustomize,
    streaming,
    stopStreaming,
    navigateTo,
  } = useStudio();
  const { view } = useBanner();
  const { onIntent, onAction, onDismiss } = useBannerActionDispatcher();
  const [showChangelog, setShowChangelog] = useState(false);

  function goHome() {
    clearChat();
    closePanel();
    closeSetup();
    closeCustomize();
    navigateTo({ name: "home" }, true);
  }

  function newConversation() {
    clearChat();
    closePanel();
    closeSetup();
    closeCustomize();
    navigateTo({ name: "home" }, true);
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        if (streaming) {
          stopStreaming();
          return;
        }
        closePanel();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [closePanel, streaming, stopStreaming]);

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
        onNew={newConversation}
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
