import { CanvasTabs } from "./components/canvas/CanvasTabs";
import { ChatCopilot } from "./components/chat/ChatCopilot";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { SettingsPanel } from "./components/SettingsPanel";
import { StudioHeader } from "./components/StudioHeader";
import { Toasts } from "./components/Toasts";
import { useStudio } from "./state/StudioContext";
import { StudioProvider } from "./state/StudioContext";

function StudioShellMinimal() {
  return (
    <div className="studio-app">
      <StudioHeader />
      <div className="studio-layout">
        <ChatCopilot />
      </div>
      <Toasts />
    </div>
  );
}

function StudioShellModerate() {
  return (
    <div className="studio-app">
      <StudioHeader />
      <div className="studio-layout">
        <CanvasTabs />
        <ChatCopilot />
      </div>
      <Toasts />
    </div>
  );
}

function StudioShellFull() {
  return (
    <div className="studio-app">
      <SettingsPanel />
      <StudioHeader />
      <div className="studio-layout">
        <CanvasTabs />
        <ChatCopilot />
      </div>
      <Toasts />
    </div>
  );
}

/** Reads engagementLevel from context (must be rendered inside StudioProvider). */
function StudioShell() {
  const { engagementLevel } = useStudio();
  switch (engagementLevel) {
    case 0:
      return <StudioShellMinimal />;
    case 1:
      return <StudioShellModerate />;
    case 2:
    default:
      return <StudioShellFull />;
  }
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
