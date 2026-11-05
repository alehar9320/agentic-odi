import { describe, expect, it } from "vitest";

import {
  emptySnapshot,
  isAlive,
  isReady,
  isAliveFlag,
  isReadyFlag,
  livenessProbe,
  livenessWord,
  mcpProbe,
  mcpWord,
  modelProbe,
  recordProbes,
  probeTone,
  withLiveness,
} from "./connection";

/**
 * A rejected key arrives from the sidecar's probe as the SDK's own text. It is
 * the string the bar used to interpolate, so it is the string these tests feed in.
 */
const REJECTED_KEY =
  "error: Error code: 401 - {'error': {'message': 'Incorrect API key provided: sk-proj-abc'}}";

describe("livenessProbe", () => {
  it("reads an answering sidecar as live", () => {
    const probe = livenessProbe({ ok: true, degraded: null, checked_at: 1_700_000_000_000 });

    expect(probe).toEqual({
      state: "live",
      checked_at: 1_700_000_000_000,
      message: "The local Studio service is answering.",
    });
  });

  it("keeps a degraded store alive, because the process answered", () => {
    const probe = livenessProbe({
      ok: true,
      degraded: { reason: "store_corrupt" },
      checked_at: 1_700_000_000_000,
    });

    expect(probe.state).toBe("degraded");
    expect(isAlive(probe)).toBe(true);
    expect(isReady(probe)).toBe(false);
  });

  it("reports a sidecar that did not answer as down", () => {
    const probe = livenessProbe({ ok: false, degraded: null, checked_at: 1_700_000_000_000 });

    expect(probe.state).toBe("down");
    expect(isAlive(probe)).toBe(false);
    expect(probe.message).toBe("The local Studio service isn't responding.");
  });
});

describe("modelProbe", () => {
  it("reads an answering model as live", () => {
    const probe = modelProbe({ healthy: true, message: "LLM backend is reachable." }, 1_700_000_000_000);

    expect(probe).toMatchObject({ state: "live", checked_at: 1_700_000_000_000 });
  });

  it("maps a rejected key to one sentence, with no provider text left in it", () => {
    const probe = modelProbe({ healthy: false, message: REJECTED_KEY }, 1_700_000_000_000);

    expect(probe.state).toBe("degraded");
    expect(probe.message).toBe("Not ready — the endpoint rejected the key.");
    expect(probe.message).not.toContain("401");
    expect(probe.message).not.toContain("sk-proj-abc");
    expect(probe.message).not.toContain(REJECTED_KEY);
  });

  it("maps a timeout to waiting, not to a dead application", () => {
    const probe = modelProbe(
      { healthy: false, message: "connection_error: Request timed out." },
      1_700_000_000_000,
    );

    expect(probe.state).toBe("degraded");
    expect(probe.message).toBe("Not ready — the endpoint did not answer in time.");
  });

  it("maps a refused connection to nothing listening", () => {
    const probe = modelProbe(
      {
        healthy: false,
        message: "connection_error: Failed to establish a new connection: refused",
      },
      1_700_000_000_000,
    );

    expect(probe.state).toBe("down");
    expect(probe.message).toBe("Not ready — nothing is listening at that address.");
  });

  it("keeps local mode as a fact about the settings, not a failure", () => {
    const probe = modelProbe(
      { healthy: false, message: "LLM server offline (Local Studio Mode enabled)" },
      1_700_000_000_000,
    );

    expect(probe.state).toBe("down");
    expect(probe.message).toBe("Answering from your device. No model connected.");
  });

  it("falls back to a sentence of its own when it cannot classify", () => {
    const probe = modelProbe({ healthy: false, message: "some SDK dump" }, 1_700_000_000_000);

    expect(probe.message).toBe("Not ready — the endpoint did not answer as expected.");
    expect(probe.message).not.toContain("some SDK dump");
  });

  it("stays unknown before the first answer", () => {
    expect(modelProbe({ healthy: null, message: "Health not checked yet." }, 0)).toMatchObject({
      state: "unknown",
      checked_at: null,
    });
  });
});

describe("mcpProbe", () => {
  it("reads a reachable server as live", () => {
    expect(mcpProbe(true, 1_700_000_000_000)).toEqual({
      state: "live",
      checked_at: 1_700_000_000_000,
      message: "The MCP server is answering.",
    });
  });

  it("reads an unreachable server as down", () => {
    const probe = mcpProbe(false, 1_700_000_000_000);

    expect(probe.state).toBe("down");
    expect(probe.message).toBe("Not ready — no MCP server answered.");
  });
});

describe("ConnectionSnapshot", () => {
  it("holds a live process and a degraded model as two separate answers", () => {
    const snapshot = recordProbes(emptySnapshot(), {
      liveness: livenessProbe({ ok: true, degraded: null, checked_at: 1_700_000_000_000 }),
      mcp: mcpProbe(true, 1_700_000_000_000),
      model: modelProbe({ healthy: false, message: REJECTED_KEY }, 1_700_000_000_000),
    });

    expect(snapshot.liveness.state).toBe("live");
    expect(snapshot.model.state).toBe("degraded");
    expect(snapshot.mcp.state).toBe("live");
  });

  it("starts with nothing measured", () => {
    const snapshot = emptySnapshot();

    expect(snapshot.liveness.state).toBe("unknown");
    expect(snapshot.model.checked_at).toBeNull();
    expect(snapshot.consecutive_failures).toBe(0);
    expect(snapshot.next_check_at).toBeNull();
  });

  it("counts the outages nobody has recovered from", () => {
    const down = withLiveness(emptySnapshot(), livenessProbe({ ok: false, degraded: null, checked_at: 1 }));
    const again = withLiveness(down, livenessProbe({ ok: false, degraded: null, checked_at: 2 }));
    const back = withLiveness(again, livenessProbe({ ok: true, degraded: null, checked_at: 3 }));

    expect(down.consecutive_failures).toBe(1);
    expect(again.consecutive_failures).toBe(2);
    expect(back.consecutive_failures).toBe(0);
    expect(back.liveness.checked_at).toBe(3);
  });

  it("leaves the snapshot it was given alone", () => {
    const before = emptySnapshot();
    withLiveness(before, livenessProbe({ ok: false, degraded: null, checked_at: 1 }));

    expect(before.liveness.state).toBe("unknown");
    expect(before.consecutive_failures).toBe(0);
  });
});

describe("probeTone", () => {
  it("paints a degraded row the same colour as a dead one", () => {
    const snapshot = recordProbes(emptySnapshot(), {
      liveness: livenessProbe({ ok: true, degraded: { reason: "store_corrupt" }, checked_at: 1 }),
      mcp: mcpProbe(false, 1),
      model: modelProbe({ healthy: null, message: "" }, 1),
    });

    expect(probeTone(snapshot.liveness)).toBe("warn");
    expect(probeTone(snapshot.mcp)).toBe("warn");
    expect(probeTone(snapshot.model)).toBe("unknown");
  });

  it("paints an answering row green", () => {
    const snapshot = recordProbes(emptySnapshot(), {
      liveness: livenessProbe({ ok: true, degraded: null, checked_at: 1 }),
      mcp: mcpProbe(true, 1),
      model: modelProbe({ healthy: true, message: "ok" }, 1),
    });

    expect(probeTone(snapshot.liveness)).toBe("ok");
    expect(probeTone(snapshot.model)).toBe("ok");
  });
});

describe("probe flags", () => {
  it("leaves a row nobody has measured pending", () => {
    const snapshot = emptySnapshot();

    expect(isAliveFlag(snapshot.liveness)).toBeNull();
    expect(isReadyFlag(snapshot.model)).toBeNull();
  });

  it("says the service is up while its store is degraded, and the model is not up", () => {
    const snapshot = recordProbes(emptySnapshot(), {
      liveness: livenessProbe({ ok: true, degraded: { reason: "store_corrupt" }, checked_at: 1 }),
      mcp: mcpProbe(false, 1),
      model: modelProbe({ healthy: false, message: "Error code: 401" }, 1),
    });

    expect(isAliveFlag(snapshot.liveness)).toBe(true);
    expect(isReadyFlag(snapshot.liveness)).toBe(false);
    expect(isReadyFlag(snapshot.model)).toBe(false);
    expect(isReadyFlag(snapshot.mcp)).toBe(false);
  });
});

describe("probe words", () => {
  it("never calls a row nobody measured down", () => {
    const snapshot = emptySnapshot();

    expect(livenessWord(snapshot.liveness)).toBe("unknown");
    expect(mcpWord(snapshot.mcp)).toBe("not checked");
  });

  it("calls an up process with a broken store degraded, not offline", () => {
    const snapshot = recordProbes(emptySnapshot(), {
      liveness: livenessProbe({ ok: true, degraded: { reason: "store_corrupt" }, checked_at: 1 }),
      mcp: mcpProbe(true, 1),
      model: modelProbe({ healthy: true, message: "ok" }, 1),
    });

    expect(livenessWord(snapshot.liveness)).toBe("degraded");
    expect(mcpWord(snapshot.mcp)).toBe("connected");
  });

  it("calls a service that refused the connection unavailable", () => {
    const snapshot = recordProbes(emptySnapshot(), {
      liveness: livenessProbe({ ok: false, degraded: null, checked_at: 1 }),
      mcp: mcpProbe(false, 1),
      model: modelProbe({ healthy: false, message: REJECTED_KEY }, 1),
    });

    expect(livenessWord(snapshot.liveness)).toBe("unavailable");
    expect(mcpWord(snapshot.mcp)).toBe("offline");
  });
});
