/**
 * The accessibility gate for every surface that ships.
 *
 * Each test renders one surface inside a real `main` landmark and asks axe for
 * WCAG 2.1 A/AA violations. A surface is not "accessible" because it looks
 * finished; it is accessible when this sweep passes.
 */

import { createRef } from "react";

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, it, vi } from "vitest";

import { StudioRuntimeProvider } from "../assistant/StudioRuntime";
import { CatchUpFeed } from "../components/notifications/CatchUpFeed";
import { JobMap } from "../components/canvas/JobMap";
import { OpportunityLandscape } from "../components/canvas/OpportunityLandscape";
import { ChatStage } from "../components/chat/ChatStage";
import { Composer } from "../components/chat/Composer";
import { ChangelogModal } from "../components/ChangelogModal";
import { SettingsPanel } from "../components/SettingsPanel";
import { FirstRunWizard } from "../onboarding/FirstRunWizard";
import { OnboardingProvider } from "../onboarding/OnboardingProvider";
import { useOnboarding } from "../onboarding/context";
import { createUpdateService, UpdateProvider } from "../updater";
import type { UpdateTransport } from "../updater/types";
import { expectAccessible } from "./axe";

const noop = () => {};

const state = vi.hoisted(() => ({
  // Canvas surfaces
  canvasState: { kind: "ready", data: null } as unknown,
  refreshCanvas: vi.fn(),
  addStep: vi.fn(),
  updateStep: vi.fn(),
  deleteStep: vi.fn(),
  updateJob: vi.fn(),
  deleteJob: vi.fn(),
  focusedJobId: null as string | null,
  requestSimulate: vi.fn(),
  theses: [] as unknown[],
  deleteThesis: vi.fn(),
  // Signal inbox
  signals: [] as unknown[],
  signalsError: null,
  unreadSignalCount: 0,
  refreshSignals: vi.fn(),
  markSignalAsRead: vi.fn(),
  dismissSignal: vi.fn(),
  focusSignalSubject: vi.fn(),
  // Settings and connectors
  settings: {
    base_url: "http://localhost:8001/v1",
    api_key: "local",
    model_name: "local-tools-model",
    mcp_url: "http://localhost:8000/mcp",
    display_name: "Ada",
    theme: "dark",
  },
  saveSettings: vi.fn(),
  connectors: [],
  connectorsError: null,
  presets: [],
  presetError: null,
  refreshPresets: vi.fn(async () => undefined),
  refreshConnectors: vi.fn(async () => undefined),
  refreshCapabilities: vi.fn(async () => undefined),
  addConnector: vi.fn(async () => ({ ok: true })),
  deleteConnector: vi.fn(async () => ({ ok: true })),
  openCustomize: vi.fn(),
  sidecarReachable: true,
  mcpReachable: true,
  capabilities: [],
  models: [],
  modelsLoading: false,
  modelsMessage: null,
  refreshModels: vi.fn(async () => undefined),
  checkConnections: vi.fn(async () => ({ llmHealthy: true })),
  surveyConnections: vi.fn(async () => ({
    sidecarReachable: true,
    mcpReachable: true,
    llmHealthy: true,
    llmMessage: "ok",
  })),
  recheckConnections: vi.fn(async () => undefined),
  // Chat
  messages: [] as unknown[],
  sendMessage: vi.fn(async () => undefined),
  pushNotice: vi.fn(),
  pushToast: vi.fn(),
  openPanel: vi.fn(),
  closePanel: vi.fn(),
  clearChat: vi.fn(),
  openSetup: vi.fn(),
  closeSetup: vi.fn(),
  setupOpen: false,
  canvas: null as unknown,
  brief: null as unknown,
  streaming: false,
  thinkingPhase: null as string | null,
  toolActivity: [] as unknown[],
  offlineReplyFor: null as string | null,
  stopStreaming: vi.fn(),
  regenerateFrom: vi.fn(async () => undefined),
  editFrom: vi.fn(async () => undefined),
  switchBranch: vi.fn(),
  respondToApproval: vi.fn(async () => undefined),
  llmHealth: { healthy: true, message: "ok" },
  connectorSuggestions: [] as string[],
  dismissConnectorSuggestion: vi.fn(),
}));

vi.mock("../state/StudioContext", () => ({
  useStudio: () => state,
}));

const transport: UpdateTransport = {
  supported: () => false,
  currentVersion: async () => "0.14.0",
  check: async () => null,
  relaunch: async () => undefined,
};

const updateService = createUpdateService({ transport, storage: null, document: null });

const canvasData = {
  jobs: [{ id: "JOB-1", name: "Deploy services" }],
  steps: [
    { id: "STEP-1", name: "Define payload parameters", order: 1 },
    { id: "STEP-2", name: "Locate target endpoint", order: 2 },
  ],
  outcomes: [
    {
      id: "O-101",
      statement: "Minimize time spent syncing secrets",
      importance: 9,
      satisfaction: 2,
      opportunity_score: 16,
    },
    {
      id: "O-102",
      statement: "Minimize risk of configuration drift",
      importance: 8,
      satisfaction: 7,
      opportunity_score: 9,
    },
  ],
  source: "seed" as const,
};

const signal = {
  id: "sig-1",
  kind: "outcome_scored",
  title: "Outcome rescored: minimize deploy time",
  detail: "Opportunity moved from 7.00 to 16.00.",
  subject_kind: "outcome",
  subject_id: "O-101",
  severity: "notice",
  created_at: new Date().toISOString(),
  suppressed: false,
  fingerprint: "fp-1",
};

/** A surface rendered as the only page so landmark rules judge it fairly. */
function Surface({ children }: { children: React.ReactNode }) {
  return (
    <main>
      <h1 className="sr-only">Studio surface</h1>
      {children}
    </main>
  );
}

function renderWithUpdates(ui: React.ReactNode) {
  return render(
    <UpdateProvider service={updateService}>
      <OnboardingProvider enabled={false}>{ui}</OnboardingProvider>
    </UpdateProvider>,
  );
}

function TourOpener() {
  const { openTour } = useOnboarding();
  return (
    <button type="button" onClick={openTour}>
      Show me around
    </button>
  );
}

beforeEach(() => {
  localStorage.clear();
  state.canvasState = { kind: "ready", data: canvasData };
  state.signals = [signal];
  state.unreadSignalCount = 1;
});

describe("axe sweep", () => {
  it("passes the opportunity landscape in all three views", async () => {
    const { container } = renderWithUpdates(
      <Surface>
        <OpportunityLandscape />
      </Surface>,
    );

    await expectAccessible(container);

    fireEvent.click(screen.getByRole("button", { name: /visual cards/i }));
    await expectAccessible(container);

    fireEvent.click(screen.getByRole("button", { name: /table view/i }));
    await expectAccessible(container);
  });

  it("passes the job map", async () => {
    const { container } = renderWithUpdates(
      <Surface>
        <JobMap />
      </Surface>,
    );

    await expectAccessible(container);
  });

  it("passes the catch-up feed", async () => {
    const { container } = renderWithUpdates(
      <Surface>
        <CatchUpFeed />
      </Surface>,
    );

    await expectAccessible(container);
  });

  it("passes the settings panel", async () => {
    const { container } = renderWithUpdates(
      <Surface>
        {/* The workspace panel supplies this h2 in the app; keep the levels honest here. */}
        <h2 className="sr-only">Settings</h2>
        <SettingsPanel />
      </Surface>,
    );

    // The browser-model section fills itself in after a storage read, so sweep
    // the panel only once its switch, tiers and meter are on screen.
    await screen.findByText(/no model endpoint answering/i);
    await act(async () => {});
    await expectAccessible(container);
  });

  it("passes the first-run wizard", async () => {
    const { container } = render(
      <UpdateProvider service={updateService}>
        <OnboardingProvider enabled>
          <Surface>
            <FirstRunWizard />
            <TourOpener />
          </Surface>
        </OnboardingProvider>
      </UpdateProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Show me around" }));

    await expectAccessible(container);
  });

  it("passes the command palette with an option highlighted", async () => {
    const { container } = renderWithUpdates(
      <Surface>
        <Composer
          value="/"
          onChange={noop}
          onSubmit={noop}
          onCommand={noop}
          streaming={false}
          onStop={noop}
          inputRef={createRef<HTMLTextAreaElement>()}
        />
      </Surface>,
    );

    await expectAccessible(container);
  });

  it("passes the chat stage", async () => {
    const { container } = renderWithUpdates(
      <Surface>
        <StudioRuntimeProvider>
          <ChatStage />
        </StudioRuntimeProvider>
      </Surface>,
    );

    await expectAccessible(container);
  });

  it("passes the changelog dialog", async () => {
    const { container } = renderWithUpdates(
      <Surface>
        <ChangelogModal isOpen onClose={noop} />
      </Surface>,
    );

    await waitFor(() => expect(container.querySelector(".changelog-modal__loading")).toBeNull());
    await expectAccessible(container);
  });
});
