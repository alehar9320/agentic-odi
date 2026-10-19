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

export function StudioShell({ engagementLevel }: { engagementLevel: number }) {
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
  const { engagementLevel } = useStudio();
  return (
    <ErrorBoundary>
      <StudioProvider>
        <StudioShell engagementLevel={engagementLevel} />
      </StudioProvider>
    </ErrorBoundary>
  );
}