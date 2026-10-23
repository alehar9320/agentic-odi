import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { StudioContextValue } from "../../state/StudioContext";
import { ChatStage } from "./ChatStage";

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

// The notice is the subject; the composer, hero and transcript are not.
vi.mock("./Composer", () => ({ Composer: () => null }));
vi.mock("./Conversation", () => ({ Conversation: () => null }));
vi.mock("../setup/SetupConversation", () => ({ SetupConversation: () => null }));

import { useStudio } from "../../state/StudioContext";

const stubContext = (overrides: Record<string, unknown> = {}) =>
  ({
    messages: [],
    streaming: false,
    sendMessage: vi.fn(),
    stopStreaming: vi.fn(),
    openPanel: vi.fn(),
    closePanel: vi.fn(),
    clearChat: vi.fn(),
    pushNotice: vi.fn(),
    openSetup: vi.fn(),
    setupOpen: false,
    canvas: null,
    brief: null,
    settings: { base_url: "", api_key: "", model_name: "m", mcp_url: "", display_name: "" },
    mcpReachable: false,
    llmHealth: { healthy: null, message: "" },
    ...overrides,
  }) as unknown as StudioContextValue;

describe("ChatStage offline notice", () => {
  beforeEach(() => {
    vi.mocked(useStudio).mockReset();
  });

  it("offers a way to work when no model is reachable", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ llmHealth: { healthy: false, message: "The model did not answer." } }),
    );

    render(<ChatStage />);

    expect(screen.getByRole("status")).toHaveTextContent(/Working by hand/i);
    expect(screen.getByRole("button", { name: /capture an outcome/i })).toBeInTheDocument();
  });

  it("stays quiet when the model answers", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ llmHealth: { healthy: true, message: "LLM backend reachable" } }),
    );

    render(<ChatStage />);

    expect(screen.queryByText(/Working by hand/i)).not.toBeInTheDocument();
  });

  it("stays quiet while the model health is still unknown", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext());

    render(<ChatStage />);

    expect(screen.queryByText(/Working by hand/i)).not.toBeInTheDocument();
  });
});
