import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import { SharedArtifact } from "./SharedArtifact";

const HOUR = 60 * 60 * 1000;
const DAY = 24 * HOUR;

/** An ISO timestamp `ms` from now, so the expiry wording is stable in the test. */
function fromNow(ms: number): string {
  return new Date(Date.now() + ms).toISOString();
}

const LANDSCAPE = {
  kind: "landscape" as const,
  expires_at: fromNow(3 * DAY + HOUR),
  generated_at: fromNow(-DAY),
  source: "local" as const,
  jobs: [{ id: "JOB-1", name: "Deploy Service" }],
  outcomes: [
    {
      id: "O-101",
      statement: "Minimize time spent syncing secrets",
      importance: 9,
      satisfaction: 2,
      opportunity_score: 16,
    },
  ],
  evidence: [
    {
      id: "E-1",
      name: "Gong call",
      content: "It takes an hour every time.",
      outcome_id: "O-101",
    },
  ],
};

const VISION = {
  kind: "vision" as const,
  expires_at: fromNow(3 * DAY + HOUR),
  generated_at: fromNow(-DAY),
  source: "local" as const,
  vision: "Every platform engineer ships a secret without waiting on a ticket.",
};

function respond(body: unknown, status = 200): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify(body), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
}

function respondNotFound(): void {
  respond(
    {
      error: {
        code: "not_found",
        message: "That shared link is not available.",
        retryable: false,
      },
    },
    404,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, "", "/");
});

describe("SharedArtifact", () => {
  it("names the artifact and states the expiry in the header", async () => {
    respond(LANDSCAPE);

    render(<SharedArtifact token="odi_sh_abc" />);

    expect(
      await screen.findByRole("heading", { name: "Opportunity landscape" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Shared read-only · expires in 3 days")).toBeInTheDocument();
  });

  it("renders the landscape and its evidence read-only", async () => {
    respond(LANDSCAPE);

    render(<SharedArtifact token="odi_sh_abc" />);

    expect(await screen.findByText("Minimize time spent syncing secrets")).toBeInTheDocument();
    expect(screen.getByText("Gong call")).toBeInTheDocument();
    expect(screen.getByText("It takes an hour every time.")).toBeInTheDocument();
  });

  it("renders a vision artifact as the person's own words", async () => {
    respond(VISION);

    render(<SharedArtifact token="odi_sh_abc" />);

    expect(await screen.findByRole("heading", { name: "Vision" })).toBeInTheDocument();
    expect(
      screen.getByText("Every platform engineer ships a secret without waiting on a ticket."),
    ).toBeInTheDocument();
  });

  it("offers no control that implies editing or navigation", async () => {
    respond(LANDSCAPE);

    const { container } = render(<SharedArtifact token="odi_sh_abc" />);
    await screen.findByRole("heading", { name: "Opportunity landscape" });

    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
    for (const name of [/edit/i, /save/i, /delete/i, /remove/i, /capture/i, /share/i]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
    // The only action is print, which the browser owns; nothing is wired here.
    expect(container.querySelector(".composer")).toBeNull();
    expect(container.querySelector(".rail")).toBeNull();
  });

  it("shows one sentence and no data when the token has expired", async () => {
    respond({ ...LANDSCAPE, expires_at: fromNow(-HOUR) });

    render(<SharedArtifact token="odi_sh_abc" />);

    expect(
      await screen.findByText("This shared link has expired."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Minimize time spent syncing secrets")).toBeNull();
    expect(screen.queryByText("Gong call")).toBeNull();
  });

  it("shows one sentence and no data when the link is unknown or revoked", async () => {
    respondNotFound();

    render(<SharedArtifact token="odi_sh_abc" />);

    expect(
      await screen.findByText("This shared link is no longer available."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Minimize time spent syncing secrets")).toBeNull();
  });

  it("refuses an artifact kind this build does not know", async () => {
    respond({ ...LANDSCAPE, kind: "brief" });

    render(<SharedArtifact token="odi_sh_abc" />);

    expect(
      await screen.findByText("This shared link is no longer available."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Minimize time spent syncing secrets")).toBeNull();
  });

  it("reads only the scoped payload and never the workspace canvas", async () => {
    respond(LANDSCAPE);

    render(<SharedArtifact token="odi_sh_abc" />);
    await screen.findByRole("heading", { name: "Opportunity landscape" });

    const fetchMock = vi.mocked(fetch);
    const paths = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(paths).toEqual(["/api/share/odi_sh_abc"]);
    expect(paths.some((path) => path.includes("/api/canvas"))).toBe(false);
  });
});

describe("App routing to a shared artifact", () => {
  it("opens the shared page without the rail or the composer", async () => {
    window.history.pushState({}, "", "/shared/odi_sh_abc");
    respond(LANDSCAPE);

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Opportunity landscape" }),
    ).toBeInTheDocument();
    // The workspace boot never runs on this route: no rail, no composer, and no
    // request for the canvas.
    expect(screen.queryByRole("textbox", { name: /message the studio/i })).toBeNull();
    await waitFor(() => {
      expect(vi.mocked(fetch).mock.calls.length).toBeGreaterThan(0);
    });
    const paths = vi.mocked(fetch).mock.calls.map((call) => String(call[0]));
    expect(paths.some((path) => path.includes("/api/canvas"))).toBe(false);
    expect(paths.some((path) => path.includes("/api/config"))).toBe(false);
  });
});
