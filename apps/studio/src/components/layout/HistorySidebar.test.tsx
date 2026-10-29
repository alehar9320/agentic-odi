import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import { HistorySidebar } from "./HistorySidebar";

const harness = vi.hoisted(() => ({
  state: {
    messages: [] as unknown[],
    streaming: false,
    thinkingPhase: null as string | null,
    offlineReply: false,
    canvas: null,
    conversationId: "c-2" as string | null,
    conversations: [
      { id: "c-2", title: "Cut secret setup time", created_at: "", updated_at: "" },
      { id: "c-1", title: "Find the next opportunity", created_at: "", updated_at: "" },
    ] as unknown[],
    conversationsLoading: false,
    sendMessage: vi.fn(),
    regenerateFrom: vi.fn(),
    editFrom: vi.fn(),
    switchBranch: vi.fn(),
    respondToApproval: vi.fn(),
    stopStreaming: vi.fn(),
    clearChat: vi.fn(),
    openConversation: vi.fn(),
    deleteConversation: vi.fn(),
    renameConversation: vi.fn(),
    refreshConversations: vi.fn(),
    deleteMessage: vi.fn(),
    pushToast: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

function renderHistory() {
  return render(
    <StudioRuntimeProvider>
      <HistorySidebar open onClose={() => {}} />
    </StudioRuntimeProvider>,
  );
}

describe("HistorySidebar", () => {
  // The harness is shared so the runtime sees one adapter; calls must not leak
  // from one assertion about a thread action into the next.
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists every remembered thread under the runtime's thread list", () => {
    renderHistory();

    expect(screen.getByRole("complementary", { name: "Conversation history" })).toBeInTheDocument();
    expect(screen.getByText("Cut secret setup time")).toBeInTheDocument();
    expect(screen.getByText("Find the next opportunity")).toBeInTheDocument();
  });

  it("opens a thread the reader picks", async () => {
    renderHistory();

    fireEvent.click(screen.getByText("Find the next opportunity"));

    await waitFor(() =>
      expect(harness.state.openConversation).toHaveBeenCalledWith("c-1"),
    );
  });

  it("starts a new conversation from the list", async () => {
    renderHistory();

    fireEvent.click(screen.getByRole("button", { name: /new conversation/i }));

    await waitFor(() => expect(harness.state.clearChat).toHaveBeenCalled());
  });

  it("deletes a thread the reader asks to forget", async () => {
    renderHistory();

    fireEvent.click(
      screen.getAllByRole("button", { name: "Delete Find the next opportunity" })[0],
    );

    await waitFor(() =>
      expect(harness.state.deleteConversation).toHaveBeenCalledWith("c-1"),
    );
  });

  it("renames a thread in place, as the title is the thing being changed", async () => {
    renderHistory();

    fireEvent.click(
      screen.getAllByRole("button", { name: "Rename Find the next opportunity" })[0],
    );
    const field = screen.getByRole("textbox", { name: "Conversation title" });
    fireEvent.change(field, { target: { value: "Sharpen the wedge" } });
    fireEvent.keyDown(field, { key: "Enter" });

    await waitFor(() =>
      expect(harness.state.renameConversation).toHaveBeenCalledWith(
        "c-1",
        "Sharpen the wedge",
      ),
    );
  });

  it("leaves the title alone when the rename is abandoned", async () => {
    renderHistory();

    fireEvent.click(
      screen.getAllByRole("button", { name: "Rename Find the next opportunity" })[0],
    );
    fireEvent.change(screen.getByRole("textbox", { name: "Conversation title" }), {
      target: { value: "never mind" },
    });
    fireEvent.keyDown(screen.getByRole("textbox", { name: "Conversation title" }), {
      key: "Escape",
    });

    expect(harness.state.renameConversation).not.toHaveBeenCalled();
    expect(screen.getByText("Find the next opportunity")).toBeInTheDocument();
  });

  it("renders nothing while the list is closed", () => {
    render(
      <StudioRuntimeProvider>
        <HistorySidebar open={false} onClose={() => {}} />
      </StudioRuntimeProvider>,
    );

    expect(screen.queryByRole("complementary", { name: "Conversation history" })).toBeNull();
  });
});
