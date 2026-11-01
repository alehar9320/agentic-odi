import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { INTRO_DRAFT_KEY } from "../../lib/intro";
import { IntroConversation } from "./IntroConversation";

const harness = vi.hoisted(() => ({
  state: {
    brief: null as unknown,
    canvas: null as unknown,
    saveBrief: vi.fn(),
    createJob: vi.fn(async () => "JOB-1"),
    updateJob: vi.fn(async () => undefined),
    clearChat: vi.fn(),
    closeSetup: vi.fn(),
    openPanel: vi.fn(),
    pushNotice: vi.fn(),
    pushToast: vi.fn(),
    sendMessage: vi.fn(async () => undefined),
    llmHealth: { healthy: true, message: "ok" },
    settings: { base_url: "http://llm", api_key: "k", model_name: "m", mcp_url: "http://mcp" },
    models: [] as string[],
    modelsLoading: false,
    modelsMessage: null as string | null,
    connectorSuggestions: [],
    presets: [],
    dismissConnectorSuggestion: vi.fn(),
    refreshConnectors: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

const ROLE = "I'm the PM for the deploy tool; the team is four engineers and a designer.";
const CUSTOMER = "The on-call platform engineer at 2am";
const WIN = "Ship a service without hand-copying config";
const FRICTION = "A missed key costs a deploy day";
const EVIDENCE = "Nine onboarding calls, a very angry ticket, and a Slack thread";

const COMPLETE = {
  role: ROLE,
  customer: CUSTOMER,
  win: WIN,
  friction: FRICTION,
  evidence: EVIDENCE,
};

function composer() {
  return screen.getByRole("textbox", { name: /message the studio/i });
}

function reply(text: string) {
  const input = composer();
  fireEvent.change(input, { target: { value: text } });
  fireEvent.keyDown(input, { key: "Enter" });
}

function seedDraft(answers: Record<string, string>) {
  window.localStorage.setItem(
    INTRO_DRAFT_KEY,
    JSON.stringify({ turn: 5, answers, quotes: answers }),
  );
}

beforeEach(() => {
  window.localStorage.clear();
  harness.state.brief = null;
  harness.state.saveBrief.mockClear();
  harness.state.createJob.mockClear();
  harness.state.updateJob.mockClear();
  harness.state.clearChat.mockClear();
  harness.state.closeSetup.mockClear();
  harness.state.sendMessage.mockClear();
  harness.state.pushToast.mockClear();
});

describe("IntroConversation", () => {
  it("asks five questions one at a time and keeps what the agent heard", () => {
    render(<IntroConversation />);

    expect(
      screen.getByText("What are you working on, and what's your part in it?"),
    ).toBeInTheDocument();

    reply(ROLE);
    expect(
      screen.getByText("Who feels the problem first, not the buyer, the person who hits it?"),
    ).toBeInTheDocument();
    expect(screen.getByText(ROLE)).toBeInTheDocument();

    reply(CUSTOMER);
    expect(
      screen.getByText("What are they trying to win in the next quarter?"),
    ).toBeInTheDocument();
    expect(screen.getByText("That is who feels it first.")).toBeInTheDocument();

    reply(WIN);
    expect(screen.getByText("Where does it break today? One sentence is enough.")).toBeInTheDocument();

    reply(FRICTION);
    expect(
      screen.getByText("What do you already have: interview notes, tickets, a Slack thread?"),
    ).toBeInTheDocument();

    reply(EVIDENCE);

    expect(screen.getByRole("heading", { name: "Does this look like you?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Looks like me" })).toBeInTheDocument();
    expect(screen.getByText("Team: four engineers and a designer")).toBeInTheDocument();
  });

  it("shows the example answers as illustrations, not quick replies", () => {
    render(<IntroConversation />);

    expect(
      screen.getByText(/Examples, not your answers:/),
    ).toBeInTheDocument();
    // The examples are text, never buttons that could store themselves.
    expect(
      screen.queryByRole("button", { name: /I'm the PM for the deploy tool/ }),
    ).toBeNull();
  });

  it("resumes on the same turn after a reload", () => {
    window.localStorage.setItem(
      INTRO_DRAFT_KEY,
      JSON.stringify({
        turn: 2,
        answers: { role: "PM", customer: "Engineers" },
        quotes: { role: "PM", customer: "Engineers" },
      }),
    );

    render(<IntroConversation />);

    expect(
      screen.getByText("What are they trying to win in the next quarter?"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Engineers").length).toBeGreaterThan(0);
  });

  it("skipping a turn stores nothing and moves on", () => {
    render(<IntroConversation />);

    fireEvent.click(screen.getByRole("button", { name: "Skip this question" }));

    expect(
      screen.getByText("Who feels the problem first, not the buyer, the person who hits it?"),
    ).toBeInTheDocument();
    const draft = JSON.parse(window.localStorage.getItem(INTRO_DRAFT_KEY) ?? "{}");
    expect(draft.turn).toBe(1);
    expect(draft.answers).toEqual({});
  });

  it("closes on Escape without saving the brief", () => {
    render(<IntroConversation />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(harness.state.closeSetup).toHaveBeenCalledTimes(1);
    expect(harness.state.saveBrief).not.toHaveBeenCalled();
  });

  it("sends a message that is not an answer to the conversation", () => {
    render(<IntroConversation />);

    reply("What is an outcome, exactly?");

    expect(harness.state.closeSetup).toHaveBeenCalledTimes(1);
    expect(harness.state.sendMessage).toHaveBeenCalledWith("What is an outcome, exactly?");
    expect(window.localStorage.getItem(INTRO_DRAFT_KEY)).toBeNull();
  });

  it("saves a summary row on Enter", () => {
    seedDraft(COMPLETE);
    render(<IntroConversation />);

    fireEvent.click(screen.getByRole("button", { name: "Edit customer" }));
    const input = screen.getByRole("textbox", { name: "Customer answer" });
    fireEvent.change(input, { target: { value: "The finance lead closing the books" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(screen.getByRole("button", { name: "Edit customer" })).toHaveTextContent(
      "The finance lead closing the books",
    );
    const draft = JSON.parse(window.localStorage.getItem(INTRO_DRAFT_KEY) ?? "{}");
    expect(draft.answers.customer).toBe("The finance lead closing the books");
    expect(harness.state.closeSetup).not.toHaveBeenCalled();
  });

  it("cancels a summary edit on Escape without closing the introduction", () => {
    seedDraft(COMPLETE);
    render(<IntroConversation />);

    fireEvent.click(screen.getByRole("button", { name: "Edit customer" }));
    const input = screen.getByRole("textbox", { name: "Customer answer" });
    fireEvent.change(input, { target: { value: "Something else" } });
    fireEvent.keyDown(input, { key: "Escape" });

    expect(screen.getByRole("button", { name: "Edit customer" })).toHaveTextContent(CUSTOMER);
    expect(harness.state.closeSetup).not.toHaveBeenCalled();
  });

  it("writes the brief with role, team, and evidence when accepted", async () => {
    seedDraft(COMPLETE);
    render(<IntroConversation />);

    fireEvent.click(screen.getByRole("button", { name: "Looks like me" }));

    await waitFor(() => expect(harness.state.saveBrief).toHaveBeenCalledTimes(1));
    expect(harness.state.saveBrief).toHaveBeenCalledWith(
      expect.objectContaining({
        role: ROLE,
        team: "four engineers and a designer",
        target_user: CUSTOMER,
        job_statement: WIN,
        core_problem: FRICTION,
        evidence_at_hand: [
          "Nine onboarding calls",
          "a very angry ticket",
          "a Slack thread",
        ],
      }),
    );
    expect(harness.state.createJob).toHaveBeenCalledWith(
      expect.objectContaining({ name: WIN }),
    );
    expect(harness.state.clearChat).toHaveBeenCalledTimes(1);
    expect(window.localStorage.getItem(INTRO_DRAFT_KEY)).toBeNull();
  });

  /**
   * The wizard keeps the typed context when the job write fails — losing an
   * answer was worse than a missing row. What it must not do is call that
   * outcome a clean save: the person then reads a board with no job and a
   * message that said it would be there.
   */
  it("names the job it could not create instead of reporting a clean save", async () => {
    harness.state.createJob.mockRejectedValueOnce(new Error("The studio sidecar isn't reachable."));
    seedDraft(COMPLETE);
    render(<IntroConversation />);

    fireEvent.click(screen.getByRole("button", { name: "Looks like me" }));

    await waitFor(() => expect(harness.state.saveBrief).toHaveBeenCalledTimes(1));
    expect(harness.state.pushToast).toHaveBeenCalledWith(
      "error",
      expect.stringContaining("job wasn't created"),
    );
    expect(harness.state.pushToast).not.toHaveBeenCalledWith(
      "success",
      expect.stringContaining("Context saved"),
    );
  });

  it("names a rename that did not take, rather than a clean update", async () => {
    harness.state.brief = {
      product_name: "Deploys",
      job_id: "JOB-1",
      job_statement: WIN,
    };
    harness.state.updateJob.mockRejectedValueOnce(new Error("Job name cannot be empty."));
    seedDraft(COMPLETE);
    render(<IntroConversation />);

    fireEvent.click(screen.getByRole("button", { name: "Looks like me" }));

    await waitFor(() => expect(harness.state.saveBrief).toHaveBeenCalledTimes(1));
    expect(harness.state.pushToast).toHaveBeenCalledWith(
      "error",
      expect.stringContaining("job wasn't renamed"),
    );
    expect(harness.state.pushToast).not.toHaveBeenCalledWith(
      "success",
      expect.stringContaining("Context updated"),
    );
  });
});
