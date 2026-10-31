import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../../App";
import {
  dismissSignal,
  fetchSignals,
  fetchUnreadSignalCount,
  markSignalRead,
} from "../../api/studioApi";
import type { Signal } from "../../types";
import { DEMO_SIGNALS } from "./__fixtures__/signals";

const api = vi.hoisted(() => ({
  fetchConfig: vi.fn(async () => ({
    base_url: "http://localhost:8001/v1",
    api_key: "local",
    model_name: "local-tools-model",
    mcp_url: "http://localhost:8000/mcp",
  })),
  fetchCanvas: vi.fn(async () => ({
    jobs: [{ id: "JOB-1", name: "Deploy services" }],
    steps: [],
    outcomes: [],
    source: "local" as const,
  })),
  healthMcp: vi.fn(async () => ({ reachable: true })),
  healthLlm: vi.fn(async () => ({ healthy: true, message: "LLM backend reachable" })),
  addStep: vi.fn(async () => ({ ok: true })),
  addOutcome: vi.fn(async () => ({ ok: true })),
  createJob: vi.fn(async () => ({ ok: true, result: { id: "JOB-NEW" } })),
  updateJob: vi.fn(async () => ({ ok: true })),
  deleteJob: vi.fn(async () => ({ ok: true })),
  updateStep: vi.fn(async () => ({ ok: true })),
  deleteStep: vi.fn(async () => ({ ok: true })),
  updateOutcome: vi.fn(async () => ({ ok: true })),
  deleteOutcome: vi.fn(async () => ({ ok: true })),
  fetchMemory: vi.fn(async () => []),
  fetchConnectorCatalog: vi.fn(async () => []),
  fetchConnectors: vi.fn(async () => []),
  asStudioError: (error: unknown) => ({
    code: "internal",
    message: error instanceof Error ? error.message : "Something went wrong.",
    retryable: false,
  }),
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
  streamChat: vi.fn(async () => undefined),
  fetchSignals: vi.fn(async () => []),
  fetchUnreadSignalCount: vi.fn(async () => 0),
  markSignalRead: vi.fn(async () => ({ id: "sig-1" })),
  dismissSignal: vi.fn(async () => ({ id: "sig-1" })),
}));

vi.mock("../../api/studioApi", () => api);

const MCP_URL = "http://localhost:8000/mcp";

function signal(overrides: Partial<Signal> = {}): Signal {
  return {
    id: "sig-1",
    kind: "outcome_scored",
    title: "Outcome rescored: minimize deploy time",
    detail: "Opportunity moved from 7.00 to 16.00.",
    subject_kind: "outcome",
    subject_id: "O-1",
    severity: "notice",
    created_at: new Date().toISOString(),
    suppressed: false,
    fingerprint: "fp-1",
    ...overrides,
  };
}

/** Point the mocked store at a feed; `unread` defaults to what the feed shows. */
function serveFeed(feed: Signal[], unread?: number): void {
  vi.mocked(fetchSignals).mockImplementation(async () => [...feed]);
  vi.mocked(fetchUnreadSignalCount).mockImplementation(
    async () => unread ?? feed.filter((item) => !item.read_at).length,
  );
}

beforeEach(() => {
  localStorage.clear();
  serveFeed([]);
});

describe("Catch Up reads the signal inbox", () => {
  it("reads the feed from the store and ignores the old local notification store", async () => {
    localStorage.setItem(
      "studio.notifications",
      JSON.stringify([
        { id: "NOTIF-1", title: "Invented while you were away", read: false, simulated: false },
      ]),
    );
    serveFeed([signal()]);

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Signal inbox: 1 unread" }));

    expect(await screen.findByRole("heading", { name: /while you were away/i })).toBeInTheDocument();
    expect(screen.getByText("Outcome rescored: minimize deploy time")).toBeInTheDocument();
    expect(screen.queryByText(/invented while you were away/i)).toBeNull();
    expect(fetchSignals).toHaveBeenCalled();
  });

  it("exposes the feed as a named region for landmark navigation", async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Signal inbox: no unread signals" }));

    expect(await screen.findByRole("region", { name: "Signal inbox" })).toBeInTheDocument();
  });

  it("counts unread signals from the unread-count endpoint, not the page it happens to show", async () => {
    // The store holds a budgeted inbox: the badge reports all of it.
    serveFeed([signal(), signal({ id: "sig-2", read_at: new Date().toISOString() })], 3);

    render(<App />);
    const bell = await screen.findByRole("button", { name: "Signal inbox: 3 unread" });

    expect(within(bell).getByText("3")).toBeInTheDocument();
    expect(fetchUnreadSignalCount).toHaveBeenCalled();
  });

  it("filters with toggle buttons instead of a tablist", async () => {
    serveFeed([
      signal(),
      signal({
        id: "sig-2",
        kind: "evidence_ingested",
        title: "Evidence captured from Support",
        subject_kind: "evidence",
        subject_id: "EV-1",
        read_at: new Date().toISOString(),
      }),
    ]);

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Signal inbox: 1 unread" }));
    await screen.findByText("Outcome rescored: minimize deploy time");

    expect(screen.queryByRole("tablist")).toBeNull();
    expect(screen.queryByRole("tab")).toBeNull();

    const evidenceChip = screen.getByRole("button", { name: "Evidence (1)" });
    expect(evidenceChip).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(evidenceChip);

    expect(evidenceChip).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText("Outcome rescored: minimize deploy time")).toBeNull();
    expect(screen.getByText("Evidence captured from Support")).toBeInTheDocument();
  });

  it("activates a card in one step: mark read, then open what it is about", async () => {
    serveFeed([
      signal({
        kind: "job_added",
        title: 'Job added: "Deploy services"',
        subject_kind: "job",
        subject_id: "JOB-1",
        severity: "info",
      }),
    ]);

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Signal inbox: 1 unread" }));
    const card = await screen.findByRole("button", { name: /^Job added: "Deploy services"\./i });

    fireEvent.click(card);

    await waitFor(() => expect(markSignalRead).toHaveBeenCalledWith("sig-1", MCP_URL));
    expect(await screen.findByRole("heading", { name: /universal job map/i })).toBeInTheDocument();
  });

  it("makes the card itself a native button so Enter and Space activate it", async () => {
    serveFeed([signal({ kind: "job_added", subject_kind: "job", subject_id: "JOB-1" })]);

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Signal inbox: 1 unread" }));
    const card = await screen.findByRole("button", { name: /^Outcome rescored: minimize deploy time\./i });

    expect(card.tagName).toBe("BUTTON");
    expect(card).toHaveAttribute("type", "button");
  });

  it("dismisses through the store and drops the card", async () => {
    const feed = [signal()];
    serveFeed(feed);
    vi.mocked(dismissSignal).mockImplementation(async (id: string) => {
      const index = feed.findIndex((item) => item.id === id);
      if (index >= 0) {
        feed.splice(index, 1);
      }
      return signal({ id });
    });

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Signal inbox: 1 unread" }));
    await screen.findByText("Outcome rescored: minimize deploy time");

    fireEvent.click(screen.getByRole("button", { name: /^Dismiss/i }));

    await waitFor(() =>
      expect(screen.getByText(/nothing happened while you were away/i)).toBeInTheDocument(),
    );
    expect(dismissSignal).toHaveBeenCalledWith("sig-1", MCP_URL);
  });

  it("offers no simulator and explains the real triggers when the feed is empty", async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Signal inbox: no unread signals" }));
    await screen.findByText(/nothing happened while you were away/i);

    expect(screen.queryByRole("button", { name: /simulate/i })).toBeNull();
    expect(screen.queryByText(/^Simulated$/i)).toBeNull();
    expect(screen.getByText(/an outcome re-scored, evidence captured, a job map completed/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Capture evidence" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
  });

  it("opens the capture panel from the empty state's Capture evidence action", async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Signal inbox: no unread signals" }));
    await screen.findByText(/nothing happened while you were away/i);

    fireEvent.click(screen.getByRole("button", { name: "Capture evidence" }));

    expect(await screen.findByRole("heading", { name: "Capture by hand" })).toBeInTheDocument();
  });

  it("renders a feed built from the demo fixtures like any other store signal", async () => {
    serveFeed(DEMO_SIGNALS);

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Signal inbox: 3 unread" }));

    expect(
      await screen.findByText('Evidence from "telemetry": cluster config friction'),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Opportunity score crossed 10 (up): validation rules"),
    ).toBeInTheDocument();
    // The fixtures carry no special class, badge, or count exemption.
    expect(screen.queryByText(/^Simulated$/i)).toBeNull();
    expect(screen.queryByText(/^Demo$/i)).toBeNull();
    expect(screen.getByRole("button", { name: "All (3)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unread (3)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Urgent (1)" })).toBeInTheDocument();
  });

  it("renders the demo fixtures' cards exactly like cards built from store signals", async () => {
    const fromFixtures = await cardClasses(DEMO_SIGNALS);
    const fromStore = await cardClasses(
      DEMO_SIGNALS.map((item, index) => signal({ ...item, id: `sig-${index + 1}` })),
    );

    expect(fromFixtures).toEqual(fromStore);
    expect(fromFixtures).toHaveLength(3);
  });
});

/** Open the feed on `feed` and return each rendered card's class list. */
async function cardClasses(feed: Signal[]): Promise<string[]> {
  serveFeed(feed);
  const view = render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: /signal inbox: \d unread/i }));
  await screen.findByRole("region", { name: "Signal inbox" });
  const classes = Array.from(document.querySelectorAll("article.catchup-card")).map(
    (card) => card.className,
  );
  view.unmount();
  return classes;
}
