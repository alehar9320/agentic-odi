import { beforeEach, describe, expect, it, vi } from "vitest";

import { LocalMemoryService } from "../bff/memory/localMemoryService";
import { MemoryLocalStore } from "../bff/store/memoryStore";
import { fetchConversationTree, fetchLatestConversation, recordBrowserTurn } from "./studioApi";

/**
 * The BFF seam is mocked, the memory behind it is not: a recorded turn has to
 * survive the same read a reload performs, and only a real store can show that.
 */
let store: MemoryLocalStore;
let memory: LocalMemoryService;

vi.mock("../bff/index", () => ({
  getStudioBff: () => Promise.resolve({ memory }),
}));

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  store = new MemoryLocalStore();
  memory = new LocalMemoryService(store);
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response({ detail: "SIDECAR_URL is not configured" }, 502)),
  );
});

describe("recordBrowserTurn", () => {
  it("puts the exchange where reopening the thread will find it", async () => {
    const conversationId = await recordBrowserTurn({
      conversationId: "c-1",
      question: { id: "q-1", text: "Where do I start?", parentId: null },
      answer: { id: "a-1", text: "Start with the job, then the outcome." },
    });

    const tree = await fetchConversationTree(conversationId);

    expect(tree.messages.map((turn) => turn.content)).toEqual([
      "Where do I start?",
      "Start with the job, then the outcome.",
    ]);
    expect(tree.messages[1]?.provenance).toBe("edge");
    expect(tree.head_id).toBe("a-1");
  });

  it("gives a turn to the thread it was asked in", async () => {
    const first = await recordBrowserTurn({
      conversationId: null,
      question: { id: "q-1", text: "First question", parentId: null },
      answer: { id: "a-1", text: "First answer" },
    });
    const second = await recordBrowserTurn({
      conversationId: first,
      question: { id: "q-2", text: "Second question", parentId: "a-1" },
      answer: { id: "a-2", text: "Second answer" },
    });

    expect(second).toBe(first);
    const tree = await fetchConversationTree(first);

    expect(tree.messages.map((turn) => turn.id)).toEqual(["q-1", "a-1", "q-2", "a-2"]);
    expect(tree.messages[2]?.parent_id).toBe("a-1");
  });
});

describe("fetchConversationTree for a thread only this browser knows", () => {
  it("opens the browser's copy when the server says it has no such conversation", async () => {
    const conversationId = await recordBrowserTurn({
      conversationId: null,
      question: { id: "q-1", text: "Where do I start?", parentId: null },
      answer: { id: "a-1", text: "Start with the job, then the outcome." },
    });
    // The live case: a hosted studio with a working sidecar that has never seen
    // this id, because the browser answered the turn itself.
    vi.mocked(fetch).mockImplementation(async () =>
      response(
        { error: { code: "not_found", message: `Conversation ${conversationId} not found` } },
        404,
      ),
    );

    const tree = await fetchConversationTree(conversationId);

    expect(tree.messages.map((turn) => turn.id)).toEqual(["q-1", "a-1"]);
    expect(tree.messages[1]?.provenance).toBe("edge");
  });

  it("still reports a conversation nobody holds", async () => {
    vi.mocked(fetch).mockImplementation(async () =>
      response({ error: { code: "not_found", message: "Conversation gone" } }, 404),
    );

    await expect(fetchConversationTree("c-lost")).rejects.toThrow();
  });
});

describe("fetchLatestConversation with the browser's own thread", () => {
  it("reopens the thread this browser was answering when the server has none", async () => {
    const conversationId = await recordBrowserTurn({
      conversationId: null,
      question: { id: "q-1", text: "Where do I start?", parentId: null },
      answer: { id: "a-1", text: "Start with the job, then the outcome." },
    });
    vi.mocked(fetch).mockResolvedValueOnce(response({ conversation: null, turns: [] }));

    const latest = await fetchLatestConversation();

    expect(latest.conversation?.id).toBe(conversationId);
  });

  it("reopens the browser's thread when it is the more recent work", async () => {
    const conversationId = await recordBrowserTurn({
      conversationId: null,
      question: { id: "q-1", text: "Where do I start?", parentId: null },
      answer: { id: "a-1", text: "Start with the job, then the outcome." },
    });
    vi.mocked(fetch).mockResolvedValueOnce(
      response({
        conversation: {
          id: "c-last-week",
          title: "Last week's thread",
          created_at: "2026-10-20T00:00:00+00:00",
          updated_at: "2026-10-20T00:00:00+00:00",
        },
        turns: [],
      }),
    );

    const latest = await fetchLatestConversation();

    expect(latest.conversation?.id).toBe(conversationId);
  });

  it("leaves the server's thread in place when this browser has not been worked in", async () => {
    await store.putConversation({
      id: "c-ancient",
      title: "A browser thread from last year",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      head_id: null,
    });
    vi.mocked(fetch).mockResolvedValueOnce(
      response({
        conversation: {
          id: "c-server",
          title: "Today's work",
          created_at: "2026-11-01T00:00:00+00:00",
          updated_at: "2026-11-01T00:00:00+00:00",
        },
        turns: [],
      }),
    );

    const latest = await fetchLatestConversation();

    expect(latest.conversation?.id).toBe("c-server");
  });

  it("does not let a local draft outrank the server's thread it was never asked about", async () => {
    // The deterministic assistant writes this while the sidecar is out. It is
    // not work the browser model did, so it cannot claim the reload.
    const drafted = await memory.createConversation();
    await memory.appendTurn(drafted.id, "user", "A question asked during the outage");
    await memory.appendTurn(drafted.id, "assistant", "The rule-based answer");
    vi.mocked(fetch).mockResolvedValueOnce(
      response({
        conversation: {
          id: "c-server",
          title: "Today's work",
          created_at: "2026-11-01T00:00:00+00:00",
          updated_at: "2026-11-01T00:00:00+00:00",
        },
        turns: [],
      }),
    );

    const latest = await fetchLatestConversation();

    expect(latest.conversation?.id).toBe("c-server");
  });
});
