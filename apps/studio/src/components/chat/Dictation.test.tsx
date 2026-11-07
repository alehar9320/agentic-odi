import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const dictation = vi.hoisted(() => ({
  supported: true,
  listen: vi.fn(),
}));

vi.mock("../../assistant/dictation", () => ({
  dictationSupported: () => dictation.supported,
  createDictationAdapter: () => (dictation.supported ? { listen: dictation.listen } : null),
}));

import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import type { StudioContextValue } from "../../state/StudioContext";
import { ThreadComposer } from "./ThreadComposer";

vi.mock("../../state/StudioContext", () => ({ useStudio: vi.fn() }));

import { useStudio } from "../../state/StudioContext";

const session = {
  status: { type: "running" as const },
  stop: vi.fn(async () => {}),
  cancel: vi.fn(),
  onSpeechStart: () => () => {},
  onSpeechEnd: () => () => {},
  onSpeech: () => () => {},
};

function context() {
  return {
    settings: { base_url: "", api_key: "", model_name: "test-model", mcp_url: "", display_name: "" },
    llmHealth: { healthy: true, message: "" },
    brief: null,
    canvas: null,
    connectorSuggestions: [],
    presets: [],
    dismissConnectorSuggestion: vi.fn(),
    refreshConnectors: vi.fn(async () => {}),
    messages: [],
    streaming: false,
    sendMessage: vi.fn(async () => {}),
    regenerateFrom: vi.fn(async () => {}),
    editFrom: vi.fn(async () => {}),
    switchBranch: vi.fn(),
    respondToApproval: vi.fn(async () => {}),
    stopStreaming: vi.fn(),
    pushToast: vi.fn(),
    saveSettings: vi.fn(async () => {}),
    openPanel: vi.fn(),
  } as unknown as StudioContextValue;
}

function renderComposer() {
  vi.mocked(useStudio).mockReturnValue(context());
  return render(
    <StudioRuntimeProvider>
      <ThreadComposer onCommand={() => {}} />
    </StudioRuntimeProvider>,
  );
}

afterEach(() => {
  dictation.supported = true;
});

describe("Composer dictation", () => {
  it("starts a recognition session from the microphone", () => {
    dictation.listen.mockReturnValue(session);
    renderComposer();

    fireEvent.click(screen.getByRole("button", { name: "Dictate a message" }));

    expect(dictation.listen).toHaveBeenCalledTimes(1);
  });

  it("shows no microphone in a shell without recognition", () => {
    dictation.supported = false;
    renderComposer();

    expect(screen.queryByRole("button", { name: "Dictate a message" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Stop dictating" })).toBeNull();
  });

  it("keeps the composer usable when recognition is refused", () => {
    dictation.supported = true;
    dictation.listen.mockReturnValue({
      ...session,
      status: { type: "ended" as const, reason: "error" as const },
    });
    const { container } = renderComposer();

    fireEvent.click(screen.getByRole("button", { name: "Dictate a message" }));

    // The refusal must not take the composer with it.
    expect(container.querySelector(".composer__input")).not.toBeNull();
  });
});
