import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("../../updater", () => ({
  useUpdateSnapshot: vi.fn(),
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: vi.fn(),
}));

import { useStudio } from "../../state/StudioContext";
import { useUpdateSnapshot } from "../../updater";
import type { UpdateSnapshot } from "../../updater/types";
import { StudioBar } from "./StudioBar";

const stubContext = (overrides: Record<string, unknown> = {}) => ({
  conversationId: null,
  conversations: [],
  llmHealth: { healthy: true, message: "ok" },
  probeRetry: { state: "closed", retryInMs: 0 },
  messages: [],
  openConversation: vi.fn(),
  refreshConversations: vi.fn(),
  unreadSignalCount: 0,
  openPanel: vi.fn(),
  pushToast: vi.fn(),
  saveSettings: vi.fn(),
  settings: { base_url: "", api_key: "", model_name: "", mcp_url: "", theme: "dark" },
  ...overrides,
});

const stubSnapshot = (overrides: Partial<UpdateSnapshot> = {}): UpdateSnapshot => ({
  phase: "up-to-date",
  currentVersion: "0.12.0",
  available: null,
  progress: null,
  lastCheckedAt: null,
  lastSuccessfulCheckAt: null,
  actions: [],
  installed: false,
  pendingInstall: false,
  error: null,
  autoCheck: true,
  skippedVersion: null,
  dismissedVersion: null,
  ...overrides,
});

describe("StudioBar", () => {
  beforeEach(() => {
    vi.mocked(useUpdateSnapshot).mockReturnValue(stubSnapshot() as never);
  });
  it("shows the Odi mark at 32 pixels so the pixel art stays crisp", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext() as never);
    const { container } = render(
      <StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />
    );
    const svg = container.querySelector(".brand__mark svg");
    expect(svg?.getAttribute("width")).toBe("32");
    expect(svg?.getAttribute("height")).toBe("32");
  });

  it("labels the model health control with its state and message", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        llmHealth: { healthy: false, message: "No model is reachable." },
        settings: {
          base_url: "https://model.example.com/v1",
          api_key: "k",
          model_name: "gpt-5",
          mcp_url: "",
          theme: "dark",
        },
        openPanel: vi.fn(),
      }) as never,
    );
    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    expect(
      screen.getByRole("button", { name: /model status: local mode\. no model is reachable\./i }),
    ).toBeInTheDocument();
  });

  it("says the device is answering before any probe has run", () => {
    // #309: an unconfigured browser is a fact about the settings, not a failure
    // to be discovered. The bar tells it plainly with healthy still unknown.
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ llmHealth: { healthy: null, message: "" } }) as never,
    );
    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    expect(
      screen.getByRole("button", {
        name: /model status: local\. answering from your device\. no model connected\./i,
      }),
    ).toBeInTheDocument();
  });

  it("reads a live model through the sidecar as live", () => {
    // The shipped desktop default points the browser at the sidecar's own proxy, which
    // is not an endpoint the bar can judge from settings alone. When the sidecar vouches
    // for the model, that answer outranks the guess.
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        llmHealth: { healthy: true, message: "qwen3 is answering." },
        sidecarReachable: true,
        settings: {
          base_url: "http://localhost:8001/v1",
          api_key: "local",
          model_name: "qwen3:8b",
          mcp_url: "",
          theme: "dark",
        },
      }) as never,
    );
    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    expect(
      screen.getByRole("button", { name: /model status: live\. qwen3 is answering\./i }),
    ).toBeInTheDocument();
  });

  it("shows a retry countdown, not a spinner, while the breaker is open (#536)", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        llmHealth: { healthy: false, message: "The model did not answer." },
        probeRetry: { state: "open", retryInMs: 240_000 },
      }) as never,
    );
    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    expect(
      screen.getByRole("button", { name: /model status: retrying in 4 min\./i }),
    ).toBeInTheDocument();
  });

  it("spins only for a connection somebody is trying to make", () => {
    // Keyless Ollama on the laptop: configured, not yet measured.
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        llmHealth: { healthy: null, message: "Health not checked yet." },
        settings: {
          base_url: "http://127.0.0.1:11434/v1",
          api_key: "",
          model_name: "qwen3:8b",
          mcp_url: "",
          theme: "dark",
        },
      }) as never,
    );
    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    expect(
      screen.getByRole("button", { name: /model status: connecting\. health not checked yet\./i }),
    ).toBeInTheDocument();
  });

  it("says a local endpoint is not reachable from a hosted page", () => {
    // #804: a hosted page cannot reach a private endpoint, so the bar says why.
    const originalLocation = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      get() {
        return new Proxy(originalLocation, {
          get(target, prop) {
            if (prop === "hostname") return "studio.example.com";
            return Reflect.get(target, prop);
          },
        });
      },
    });
    try {
      vi.mocked(useStudio).mockReturnValue(
        stubContext({
          llmHealth: { healthy: null, message: "" },
          settings: {
            base_url: "http://127.0.0.1:11434/v1",
            api_key: "",
            model_name: "qwen3:8b",
            mcp_url: "",
            theme: "dark",
          },
        }) as never,
      );
      render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

      expect(
        screen.getByRole("button", {
          name: /model status: connecting\. local endpoint, not reachable from this page/i,
        }),
      ).toBeInTheDocument();
    } finally {
      Object.defineProperty(window, "location", { value: originalLocation, configurable: true });
    }
  });

  it("keeps the brand mark decorative and labels the home control in text", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext() as never);
    const { container } = render(
      <StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />
    );
    expect(container.querySelector(".brand__mark")?.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelector(".brand--home")?.getAttribute("aria-label")).toBe("Living Studio, go to home");
  });

  it("switches to the light theme from the bar", () => {
    const saveSettings = vi.fn();
    vi.mocked(useStudio).mockReturnValue(stubContext({ saveSettings }) as never);
    const { getByRole } = render(
      <StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />
    );

    fireEvent.click(getByRole("button", { name: "Switch to light theme" }));

    expect(saveSettings).toHaveBeenCalledWith(expect.objectContaining({ theme: "light" }));
  });

  it("exports the conversation as Markdown from the overflow menu", () => {
    const createObjectURL = vi.fn(() => "blob:conversation");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      value: createObjectURL,
      configurable: true,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      value: revokeObjectURL,
      configurable: true,
    });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        messages: [
          { role: "user", content: "Show me the top outcomes." },
          { role: "assistant", content: "Here they are." },
        ],
      }) as never,
    );

    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "More actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /export.*markdown/i }));

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:conversation");
    click.mockRestore();
  });

  it("puts the unread count in the bell's accessible name and opens the inbox", () => {
    const openPanel = vi.fn();
    vi.mocked(useStudio).mockReturnValue(
      stubContext({ unreadSignalCount: 3, openPanel }) as never,
    );
    const { getByRole } = render(
      <StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />
    );

    const bell = getByRole("button", { name: "Signal inbox: 3 unread" });
    expect(bell.textContent).toContain("3");
    expect(bell.querySelector(".bell-badge")?.getAttribute("aria-hidden")).toBeNull();
    fireEvent.click(bell);

    expect(openPanel).toHaveBeenCalledWith("catchup");
  });

  it("says the inbox is empty instead of showing a zero badge", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ unreadSignalCount: 0 }) as never);
    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    const bell = screen.getByRole("button", { name: "Signal inbox: no unread signals" });
    expect(bell.querySelector(".bell-badge")).toBeNull();
  });

  it("announces the unread count politely when it changes", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext({ unreadSignalCount: 0 }) as never);
    const { rerender } = render(
      <StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />,
    );

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent("");

    vi.mocked(useStudio).mockReturnValue(stubContext({ unreadSignalCount: 4 }) as never);
    rerender(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    expect(screen.getByRole("status")).toHaveTextContent("4 new notifications");

    vi.mocked(useStudio).mockReturnValue(stubContext({ unreadSignalCount: 1 }) as never);
    rerender(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    expect(screen.getByRole("status")).toHaveTextContent("1 new notification");
  });

  it("shows the running version and opens update settings", () => {
    const openPanel = vi.fn();
    vi.mocked(useStudio).mockReturnValue(stubContext({ openPanel }) as never);
    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    const version = screen.getByRole("button", { name: "v0.12.0" });
    fireEvent.click(version);

    expect(openPanel).toHaveBeenCalledWith("settings");
  });

  it("says update ready when a restart will finish the job", () => {
    vi.mocked(useStudio).mockReturnValue(stubContext() as never);
    vi.mocked(useUpdateSnapshot).mockReturnValue(stubSnapshot({ phase: "ready" }) as never);

    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    expect(screen.getByRole("button", { name: "Update ready" })).toBeInTheDocument();
  });

  it("lists recent conversations with their title and time when the history opens", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-22T10:00:00Z"));
    const refreshConversations = vi.fn(async () => undefined);
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        refreshConversations,
        conversationId: "c-2",
        conversations: [
          {
            id: "c-2",
            title: "Where does onboarding leak?",
            created_at: "2026-10-22T09:00:00Z",
            updated_at: "2026-10-22T09:59:30Z",
            head_id: null,
            turn_count: 4,
          },
          {
            id: "c-1",
            title: "Price the churn spike",
            created_at: "2026-10-21T09:00:00Z",
            updated_at: "2026-10-21T09:00:00Z",
            head_id: null,
            turn_count: 2,
          },
        ],
      }) as never,
    );
    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    expect(screen.queryByRole("menu", { name: "Recent conversations" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Conversation history" }));

    const menu = screen.getByRole("menu", { name: "Recent conversations" });
    expect(refreshConversations).toHaveBeenCalledOnce();
    expect(within(menu).getByText("Where does onboarding leak?")).toBeInTheDocument();
    expect(within(menu).getByText("Price the churn spike")).toBeInTheDocument();
    // The relative time is its own <time>, so it is read as a date, and the
    // turn count rides alongside it rather than inside the element.
    const when = within(menu).getByText("Just now");
    expect(when.tagName).toBe("TIME");
    expect(within(menu).getByText(/· 4 turns/)).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("marks the current conversation and loads another when one is chosen", () => {
    const openConversation = vi.fn(async () => undefined);
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        openConversation,
        conversationId: "c-2",
        conversations: [
          {
            id: "c-2",
            title: "Current thread",
            created_at: "2026-10-22T09:00:00Z",
            updated_at: "2026-10-22T09:00:00Z",
            head_id: null,
            turn_count: 1,
          },
          {
            id: "c-1",
            title: "An older thread",
            created_at: "2026-10-21T09:00:00Z",
            updated_at: "2026-10-21T09:00:00Z",
            head_id: null,
            turn_count: 3,
          },
        ],
      }) as never,
    );
    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: "Conversation history" }));

    const current = screen.getByRole("menuitem", { name: /current thread/i });
    expect(current).toHaveAttribute("aria-current", "true");

    fireEvent.click(screen.getByRole("menuitem", { name: /an older thread/i }));

    expect(openConversation).toHaveBeenCalledWith("c-1");
    // Choosing closes the list, so the thread is not hidden behind it.
    expect(screen.queryByRole("menu", { name: "Recent conversations" })).toBeNull();
  });

  it("names an untitled thread rather than showing a blank row", () => {
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        conversationId: "c-1",
        conversations: [
          {
            id: "c-1",
            title: "",
            created_at: "2026-10-22T09:00:00Z",
            updated_at: "2026-10-22T09:00:00Z",
            head_id: null,
            turn_count: 0,
          },
        ],
      }) as never,
    );
    render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: "Conversation history" }));

    expect(screen.getByRole("menuitem", { name: /new conversation/i })).toBeInTheDocument();
  });
});

describe("StudioBar new thread control (#319)", () => {
  const originalMatchMedia = window.matchMedia;
  let wide = true;

  const transcript = [
    { id: "t-1", parentId: null, role: "user", content: "Where do I start?" },
    { id: "t-2", parentId: "t-1", role: "assistant", content: "Name the job." },
  ];

  beforeEach(() => {
    wide = true;
    vi.mocked(useUpdateSnapshot).mockReturnValue(stubSnapshot() as never);
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: (query: string) => ({
        matches: query === "(min-width: 720px)" && wide,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }),
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: originalMatchMedia,
    });
  });

  function renderBar(overrides: Record<string, unknown> = {}) {
    const onNew = vi.fn();
    vi.mocked(useStudio).mockReturnValue(
      stubContext({
        streaming: false,
        activePanel: null,
        customizeOpen: false,
        setupOpen: false,
        ...overrides,
      }) as never,
    );
    render(<StudioBar onHome={() => {}} onNew={onNew} onChangelog={() => {}} />);
    return { onNew };
  }

  it("says the words New thread where there is room for them", () => {
    const { onNew } = renderBar({ messages: transcript });

    const control = screen.getByRole("button", { name: "Start a new thread" });
    expect(control).toHaveTextContent("New thread");
    expect(onNew).not.toHaveBeenCalled();
  });

  it("keeps the name when the bar drops the words", () => {
    wide = false;
    renderBar({ messages: transcript });

    const control = screen.getByRole("button", { name: "Start a new thread" });
    expect(control).not.toHaveTextContent("New thread");
  });

  it("names in the tooltip what a new thread leaves alone", () => {
    renderBar({ messages: transcript });

    expect(screen.getByRole("button", { name: "Start a new thread" })).toHaveAttribute(
      "title",
      expect.stringContaining("Your jobs, outcomes, and evidence stay."),
    );
  });

  it("disables the control and says the thread is already new", () => {
    const { onNew } = renderBar({ messages: [] });

    const control = screen.getByRole("button", { name: "Start a new thread" });
    expect(control).toBeDisabled();
    const describedBy = control.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy as string)).toHaveTextContent(
      "This thread is already new.",
    );

    fireEvent.click(control);
    expect(onNew).not.toHaveBeenCalled();
  });

  it("stays live on an empty thread when a view is still open to leave", () => {
    // The bar's plus is the documented way out of the first-run setup, so an
    // empty transcript must not switch it off while setup is on screen.
    renderBar({ messages: [], setupOpen: true });

    expect(screen.getByRole("button", { name: "Start a new thread" })).toBeEnabled();
  });

  it("asks before discarding a reply that is still coming", () => {
    const { onNew } = renderBar({ messages: transcript, streaming: true });

    fireEvent.click(screen.getByRole("button", { name: "Start a new thread" }));

    const ask = screen.getByRole("dialog", { name: /stop the reply and start a new thread/i });
    expect(ask).toHaveTextContent("A reply is still coming. Stop it and start a new thread?");
    expect(onNew).not.toHaveBeenCalled();
    expect(ask).toHaveTextContent("Keep writing");
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Keep writing" }));
  });

  it("keeps the reply running when the person chooses Keep writing", () => {
    const { onNew } = renderBar({ messages: transcript, streaming: true });

    fireEvent.click(screen.getByRole("button", { name: "Start a new thread" }));
    fireEvent.click(screen.getByRole("button", { name: "Keep writing" }));

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(onNew).not.toHaveBeenCalled();
  });

  it("closes the ask on Escape without starting anything", () => {
    const { onNew } = renderBar({ messages: transcript, streaming: true });

    fireEvent.click(screen.getByRole("button", { name: "Start a new thread" }));
    // Escape from wherever the focus sits inside the ask — which is the only
    // place it is not trapping anyone.
    fireEvent.keyDown(screen.getByRole("button", { name: "Keep writing" }), { key: "Escape" });

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(onNew).not.toHaveBeenCalled();
  });

  it("stops the stream and starts the thread on the second choice", () => {
    const { onNew } = renderBar({ messages: transcript, streaming: true });

    fireEvent.click(screen.getByRole("button", { name: "Start a new thread" }));
    fireEvent.click(screen.getByRole("button", { name: "Stop and start" }));

    expect(onNew).toHaveBeenCalledWith({ stop: true });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("starts the thread with one click when nothing is streaming", () => {
    const { onNew } = renderBar({ messages: transcript });

    fireEvent.click(screen.getByRole("button", { name: "Start a new thread" }));

    expect(onNew).toHaveBeenCalledTimes(1);
    expect(onNew).not.toHaveBeenCalledWith({ stop: true });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

// Shared by the history tests: one thread, and a bar with its list open.
const conversation = (id: string, title: string, updatedAt: string, turnCount: number) => ({
  id,
  title,
  created_at: updatedAt,
  updated_at: updatedAt,
  head_id: null,
  turn_count: turnCount,
});

function openHistory(overrides: Record<string, unknown>) {
  vi.mocked(useStudio).mockReturnValue(stubContext(overrides) as never);
  const view = render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);
  fireEvent.click(screen.getByRole("button", { name: "Conversation history" }));
  return {
    menu: screen.getByRole("menu", { name: "Recent conversations" }),
    unmount: view.unmount,
  };
}

describe("history opens on the thread in view (#694 D11)", () => {
  it("opens on the thread in view, gliding unless motion is reduced", () => {
    const scrollIntoView = vi.fn();
    const received: Element[] = [];
    const original = (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView;
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      configurable: true,
      value: function (this: Element, options: ScrollIntoViewOptions) {
        received.push(this);
        scrollIntoView(options);
      },
    });

    const media = (matches: boolean) =>
      vi.fn((query: string) => ({
        matches: query.includes("prefers-reduced-motion") ? matches : false,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }));
    const originalMatchMedia = window.matchMedia;
    Object.defineProperty(window, "matchMedia", { configurable: true, value: media(true) });

    try {
      const conversations = [
        conversation("c-2", "The thread on screen", new Date(2026, 9, 22, 9, 0).toISOString(), 2),
        conversation("c-1", "An older thread", new Date(2026, 9, 20, 9, 0).toISOString(), 1),
      ];

      const reduced = openHistory({ conversationId: "c-2", conversations });
      expect(scrollIntoView).toHaveBeenCalledWith({ block: "nearest", behavior: "auto" });
      expect(received[0]).toBe(
        within(reduced.menu).getByRole("menuitem", { name: /the thread on screen/i }),
      );

      reduced.unmount();
      scrollIntoView.mockClear();
      received.length = 0;
      Object.defineProperty(window, "matchMedia", { configurable: true, value: media(false) });

      openHistory({ conversationId: "c-2", conversations });
      expect(scrollIntoView).toHaveBeenCalledWith({ block: "nearest", behavior: "smooth" });
    } finally {
      if (original === undefined) {
        delete (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView;
      } else {
        Object.defineProperty(Element.prototype, "scrollIntoView", {
          configurable: true,
          value: original,
        });
      }
      Object.defineProperty(window, "matchMedia", { configurable: true, value: originalMatchMedia });
    }
  });
});

describe("history says when and how much (#694 D12)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("reads when it happened and how many turns it holds", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 9, 22, 10, 0));

    const { menu } = openHistory({
      conversations: [
        conversation("c-1", "Pricing the churn spike", new Date(2026, 9, 22, 8, 0).toISOString(), 6),
      ],
    });

    const when = within(menu).getByText("2h ago");
    expect(when.tagName).toBe("TIME");
    expect(when).toHaveAttribute("dateTime", new Date(2026, 9, 22, 8, 0).toISOString());
    expect(within(menu).getByText(/· 6 turns/)).toBeInTheDocument();
  });

  it("gives a thread with no turns no meta line at all", () => {
    const { menu } = openHistory({
      conversations: [
        conversation("c-1", "A fresh thread", new Date(2026, 9, 22, 9, 0).toISOString(), 0),
      ],
    });

    expect(within(menu).getByText("A fresh thread")).toBeInTheDocument();
    expect(menu.querySelector(".bar__history-meta")).toBeNull();
    expect(within(menu).queryByText(/turns?/)).toBeNull();
  });
});

describe("history is grouped by day (#694 D13)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  function groupingOf(row: Element): number {
    let groups = 0;
    for (let node = row.parentElement; node; node = node.parentElement) {
      if (node.getAttribute("role") === "group") {
        groups += 1;
      }
    }
    return groups;
  }

  it("heads the list by day, in order, only where there are rows", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 9, 22, 10, 0));

    openHistory({
      conversations: [
        conversation("c-3", "This morning", new Date(2026, 9, 22, 9, 0).toISOString(), 2),
        conversation("c-2", "Last night", new Date(2026, 9, 21, 23, 0).toISOString(), 1),
        conversation("c-1", "Last week", new Date(2026, 9, 15, 9, 0).toISOString(), 3),
      ],
    });

    const headings = Array.from(document.querySelectorAll(".bar__history-day")).map(
      (node) => node.textContent,
    );
    expect(headings).toEqual(["Today", "Yesterday", "Earlier"]);

    expect(
      within(screen.getByRole("group", { name: "Today" })).getAllByRole("menuitem"),
    ).toHaveLength(1);
    expect(
      within(screen.getByRole("group", { name: "Yesterday" })).getAllByRole("menuitem"),
    ).toHaveLength(1);

    // A row sits under exactly one heading, never repeated under two.
    for (const row of screen.getAllByRole("menuitem")) {
      const group = row.closest('[role="group"]') as HTMLElement;
      expect(group.querySelectorAll(".bar__history-day")).toHaveLength(1);
      expect(groupingOf(row)).toBe(1);
    }
  });

  it("leaves out a day with nothing in it", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 9, 22, 10, 0));

    openHistory({
      conversations: [
        conversation("c-1", "This morning", new Date(2026, 9, 22, 9, 0).toISOString(), 1),
      ],
    });

    expect(screen.getByRole("group", { name: "Today" })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Yesterday" })).toBeNull();
    expect(screen.queryByRole("group", { name: "Earlier" })).toBeNull();
  });
});
