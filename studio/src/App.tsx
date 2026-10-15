import { CanvasTabs } from "./components/canvas/CanvasTabs";
import { ChatCopilot } from "./components/chat/ChatCopilot";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { SettingsPanel } from "./components/SettingsPanel";
import { StudioHeader } from "./components/StudioHeader";
import { Toasts } from "./components/Toasts";
import { StudioProvider } from "./state/StudioContext";

export function StudioShell() {
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

export default function App() {
  return (
    <ErrorBoundary>
      <StudioProvider>
        <StudioShell />
      </StudioProvider>
    </ErrorBoundary>
  );
}
