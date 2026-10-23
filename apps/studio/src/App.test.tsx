import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { healthLlm } from "./api/studioApi";

vi.mock("./api/studioApi", () => ({
  fetchConfig: vi.fn(async () => ({
    base_url: "http://localhost:8001/v1",
    api_key: "local",
    model_name: "local-tools-model",
    mcp_url: "http://localhost:8000/mcp",
  })),
  fetchCanvas: vi.fn(async () => ({
    jobs: [{ id: "JOB-402", name: "Propagate secrets" }],
    steps: [],
    outcomes: [
      {
        id: "O-1",
        job_id: "JOB-402",
        statement: "Minimize the time it takes to propagate secrets",
        importance: 9.2,
        satisfaction: 3.1,
        opportunity_score: 15.3,
      },
    ],
    source: "local" as const,
  })),
  healthMcp: vi.fn(async () => ({ reachable: true })),
  healthLlm: vi.fn(async () => ({ healthy: true, message: "LLM backend is reachable." })),
  addStep: vi.fn(async () => ({ ok: true, result: "created" })),
  addOutcome: vi.fn(async () => ({ ok: true, result: "created" })),
  createJob: vi.fn(async () => ({ ok: true, result: { id: "JOB-NEW" } })),
  updateJob: vi.fn(async () => ({ ok: true })),
  deleteJob: vi.fn(async () => ({ ok: true })),
  updateStep: vi.fn(async () => ({ ok: true })),
  deleteStep: vi.fn(async () => ({ ok: true })),
  updateOutcome: vi.fn(async () => ({ ok: true })),
  deleteOutcome: vi.fn(async () => ({ ok: true })),
  fetchMemory: vi.fn(async () => []),
  fetchLatestConversation: vi.fn(async () => ({ conversation: null, turns: [] })),
  createConversation: vi.fn(async () => ({
    id: "c-new",
    title: "",
    created_at: "2026-10-22T10:00:00+00:00",
    updated_at: "2026-10-22T10:00:00+00:00",
  })),
  addObservation: vi.fn(),
  updateObservation: vi.fn(),
  deleteObservation: vi.fn(async () => ({ ok: true })),
  clearMemory: vi.fn(async () => ({ ok: true })),
  streamChat: vi.fn(
    async (
      _request: unknown,
      onEvent: (event: { event: string; data: Record<string, unknown> }) => void,
    ) => {
      onEvent({ event: "status", data: { phase: "model" } });
      onEvent({ event: "delta", data: { text: "Start with the **job**." } });
      onEvent({ event: "message", data: { content: "Start with the **job**." } });
    },
  ),
}));

const BRIEF = {
  product_name: "Ambient",
  target_user: "Platform engineers",
  job_statement: "Get a service from commit to production",
  core_problem: "A missed config key costs hours",
  job_id: "JOB-402",
};

beforeEach(() => {
  for (const key of [
    "studio.brief",
    "studio.settings",
    "studio.canvas",
    "studio.displayName",
    "studio.setupDismissed",
    "studio.setupDraft",
    "studio.onboarding",
  ]) {
    window.localStorage.removeItem(key);
  }
  // Shell tests are not about onboarding: keep the tour out of their way.
  window.localStorage.setItem("studio.flags.firstRunWizard", "off");
  window.localStorage.setItem("studio.brief", JSON.stringify(BRIEF));
  vi.mocked(healthLlm).mockResolvedValue({
    healthy: true,
    message: "LLM backend is reachable.",
  });
});

describe("studio shell", () => {
  it("opens as a conversation with an invitation and suggestion pills", async () => {
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "What do you want to win?" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /message the studio/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sharpen an opportunity/i })).toBeInTheDocument();
    // The classic UI is secondary: no workspace surface until you ask for one.
    expect(screen.queryByRole("heading", { name: /opportunity landscape/i })).toBeNull();
  });

  it("opens a workspace view beside the conversation and keeps the composer", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /^landscape/i }));

    expect(
      await screen.findByRole("heading", { name: /opportunity landscape/i }),
    ).toBeInTheDocument();
    // The conversation keeps the stage: the composer never leaves.
    expect(screen.getByRole("textbox", { name: /message the studio/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /close workspace view/i }));

    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: /opportunity landscape/i })).toBeNull();
    });
    expect(screen.getByRole("textbox", { name: /message the studio/i })).toBeInTheDocument();
  });

  it("keeps the transcript on screen while a view is open", async () => {
    render(<App />);

    const composer = await screen.findByRole("textbox", { name: /message the studio/i });
    fireEvent.change(composer, { target: { value: "Where do I start?" } });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));
    await screen.findByText("Where do I start?");

    fireEvent.click(screen.getByRole("button", { name: /^landscape/i }));

    expect(
      await screen.findByRole("heading", { name: /opportunity landscape/i }),
    ).toBeInTheDocument();
    // The lens makes room; it never hides what the user was reading.
    expect(screen.getByText("Where do I start?")).toBeInTheDocument();
    expect(screen.getByText("job")).toBeInTheDocument();
  });

  it("adjusts outcome scores by hand from the landscape", async () => {
    const { updateOutcome } = await import("./api/studioApi");
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /^landscape/i }));
    fireEvent.click(await screen.findByRole("button", { name: /adjust scores/i }));
    fireEvent.click(screen.getByRole("button", { name: /save scores/i }));

    await waitFor(() => {
      expect(updateOutcome).toHaveBeenCalledWith(
        "O-1",
        expect.objectContaining({ importance: expect.any(Number), satisfaction: expect.any(Number) }),
      );
    });
  });

  it("streams an answer into the transcript after sending a message", async () => {
    render(<App />);

    const composer = await screen.findByRole("textbox", { name: /message the studio/i });
    fireEvent.change(composer, { target: { value: "Where do I start?" } });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));

    expect(await screen.findByText("Where do I start?")).toBeInTheDocument();
    expect(await screen.findByText("job")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /copy reply/i })).toBeInTheDocument();
  });

  it("returns home from the wordmark", async () => {
    render(<App />);

    const composer = await screen.findByRole("textbox", { name: /message the studio/i });
    fireEvent.change(composer, { target: { value: "Where do I start?" } });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));
    await screen.findByText("Where do I start?");

    fireEvent.click(screen.getByRole("button", { name: /go to home/i }));

    await waitFor(() => {
      expect(screen.queryByText("Where do I start?")).toBeNull();
    });
    expect(
      screen.getByRole("heading", { name: "What do you want to win?" }),
    ).toBeInTheDocument();
  });

  it("runs a slash command as a conversation when a model is live", async () => {
    render(<App />);

    const composer = await screen.findByRole("textbox", { name: /message the studio/i });
    fireEvent.change(composer, { target: { value: "/" } });

    expect(await screen.findByRole("listbox", { name: /commands/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("option", { name: /capture an outcome/i }));

    // Capture is a sentence, not a form: the request lands in the transcript.
    expect(
      await screen.findByText(/I want to capture an outcome I heard from a customer/i),
    ).toBeInTheDocument();
  });

  it("answers a slash command with a transcript notice", async () => {
    render(<App />);

    const composer = await screen.findByRole("textbox", { name: /message the studio/i });
    fireEvent.change(composer, { target: { value: "/help" } });
    fireEvent.keyDown(composer, { key: "Enter" });

    expect(await screen.findByText(/handled here/i, { selector: "p" })).toBeInTheDocument();
  });

  it("shows manual work when the model is offline", async () => {
    vi.mocked(healthLlm).mockResolvedValueOnce({ healthy: false, message: "offline" });
    render(<App />);

    expect(await screen.findByText(/working by hand/i)).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: /capture an outcome/i }).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("Local guidance")).toBeInTheDocument();
  });

  it("starts a new conversation from the drawer", async () => {
    render(<App />);

    const composer = await screen.findByRole("textbox", { name: /message the studio/i });
    fireEvent.change(composer, { target: { value: "Where do I start?" } });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));
    await screen.findByText("Where do I start?");

    fireEvent.click(screen.getByRole("button", { name: /new conversation/i }));

    await waitFor(() => {
      expect(screen.queryByText("Where do I start?")).toBeNull();
    });
  });
});

describe("first-run tour", () => {
  function prepareFreshRun() {
    window.localStorage.removeItem("studio.brief");
    window.localStorage.removeItem("studio.onboarding");
    window.localStorage.setItem("studio.flags.firstRunWizard", "on");
  }

  it("does not put a tour in front of a first-time user", async () => {
    prepareFreshRun();
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "What do you want to win?" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
    // No interview behind it either: the stage is the first thing that asks.
    expect(screen.queryByText("What are you building?", { selector: "strong" })).toBeNull();
    expect(screen.getByRole("textbox", { name: /message the studio/i })).toBeInTheDocument();
  });

  it("opens the tour when the stage offers it", async () => {
    prepareFreshRun();
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Show me around" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { level: 2 })).toHaveTextContent(
      "What do you want to win?",
    );
  });

  it("starts the boss-priority conversation from the tour", async () => {
    prepareFreshRun();
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Show me around" }));
    fireEvent.click(await screen.findByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: /My boss handed me a priority/ }));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(
      await screen.findByText("A quick look at your instruments."),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: "Make it real" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(
      await screen.findByText(/My boss handed me a priority\. Help me turn it/),
    ).toBeInTheDocument();
  });

  it("starts the find-opportunity conversation from the tour", async () => {
    prepareFreshRun();
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Show me around" }));
    fireEvent.click(await screen.findByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: /Help me find the next one/ }));
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByText("A quick look at your instruments.");
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.click(screen.getByRole("button", { name: "Find my next opportunity" }));

    expect(
      await screen.findByText(/I need to find the next opportunity worth chasing/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("first run", () => {
  it("opens the context conversation from the stage and creates the job when accepted", async () => {
    window.localStorage.removeItem("studio.brief");
    const { createJob } = await import("./api/studioApi");
    render(<App />);

    // The stage first; the interview is an answer, not a gate.
    fireEvent.click(
      await screen.findByRole("button", { name: /tell me what you're building/i }),
    );
    expect(
      await screen.findByText("What are you building?", { selector: "strong" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /explore on my own/i })).toBeInTheDocument();

    const composer = screen.getByRole("textbox", { name: /message the studio/i });
    fireEvent.change(composer, { target: { value: "Ambient" } });
    fireEvent.keyDown(composer, { key: "Enter" });

    expect(
      await screen.findByText("Who feels the problem most?", { selector: "strong" }),
    ).toBeInTheDocument();
    fireEvent.change(composer, { target: { value: "Platform engineers" } });
    fireEvent.keyDown(composer, { key: "Enter" });

    expect(
      await screen.findByText("What job are they trying to get done?", { selector: "strong" }),
    ).toBeInTheDocument();
    fireEvent.change(composer, { target: { value: "Get a service from commit to production" } });
    fireEvent.keyDown(composer, { key: "Enter" });

    expect(
      await screen.findByText("Where does it hurt most?", { selector: "strong" }),
    ).toBeInTheDocument();
    fireEvent.change(composer, { target: { value: "A missed config key costs hours" } });
    fireEvent.keyDown(composer, { key: "Enter" });

    expect(
      await screen.findByText(/Here is what I will hold/i, { selector: "p" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /looks right/i }));

    await waitFor(() => {
      expect(createJob).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Get a service from commit to production" }),
      );
    });
    expect(await screen.findByText(/Living Studio · Ambient/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /explore on my own/i })).toBeNull();
  });

  it("does not open the context interview by itself", async () => {
    window.localStorage.removeItem("studio.brief");
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "What do you want to win?" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("What are you building?", { selector: "strong" })).toBeNull();
    expect(window.localStorage.getItem("studio.setupDismissed")).toBeNull();
  });

  it("asks for context once the studio has answered something", async () => {
    window.localStorage.removeItem("studio.brief");
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "What do you want to win?" }),
    ).toBeInTheDocument();
    // Nothing to correct before the first exchange.
    expect(screen.queryByText(/I don't know your product yet/)).toBeNull();

    const composer = screen.getByRole("textbox", { name: /message the studio/i });
    fireEvent.change(composer, { target: { value: "Where do I start?" } });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));

    expect(
      await screen.findByText(/I don't know your product yet/),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /add context/i }));

    expect(
      await screen.findByText("What are you building?", { selector: "strong" }),
    ).toBeInTheDocument();
  });

  it("lets a workspace surface take over from the setup conversation", async () => {
    window.localStorage.removeItem("studio.brief");
    render(<App />);

    fireEvent.click(
      await screen.findByRole("button", { name: /tell me what you're building/i }),
    );
    expect(
      await screen.findByText("What are you building?", { selector: "strong" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^landscape/i }));
    expect(
      await screen.findByRole("heading", { name: /opportunity landscape/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /close workspace view/i }));

    // Closing the surface returns to the home stage, not back into setup.
    expect(
      await screen.findByRole("heading", { name: "What do you want to win?" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("What are you building?", { selector: "strong" })).toBeNull();
  });

  it("edits an existing context as a conversation", async () => {
    const { updateJob } = await import("./api/studioApi");
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /edit context/i }));

    expect(
      await screen.findByText(/Here is what I will hold/i, { selector: "p" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /change product/i }));
    const composer = screen.getByRole("textbox", { name: /message the studio/i });
    fireEvent.change(composer, { target: { value: "Ambient Two" } });
    fireEvent.keyDown(composer, { key: "Enter" });

    fireEvent.click(await screen.findByRole("button", { name: /save context/i }));

    await waitFor(() => {
      expect(updateJob).toHaveBeenCalledWith(
        "JOB-402",
        expect.objectContaining({ name: "Get a service from commit to production" }),
      );
    });
  });
});
