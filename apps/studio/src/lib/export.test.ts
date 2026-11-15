import { describe, expect, it, vi } from "vitest";

import type { ChatMessage } from "../types";
import { catalogManifest } from "../ui/catalog";
import { parseUiSpec, type UiNode } from "../ui/protocol";
import {
  conversationToMarkdown,
  downloadJson,
  exportFilename,
  workspaceExportFilename,
} from "./export";

const exportedAt = new Date("2026-10-24T12:00:00Z");

function surfaceCard(): UiNode {
  const parsed = parseUiSpec(
    {
      type: "outcome-card",
      props: {
        id: "O-1",
        statement: "Minimize the time it takes to propagate secrets",
        importance: 9,
        satisfaction: 3,
      },
    },
    catalogManifest(),
  );
  if (!parsed.ok) {
    throw new Error(parsed.reason);
  }
  return parsed.node;
}

describe("conversationToMarkdown", () => {
  it("labels every speaker", () => {
    const messages: ChatMessage[] = [
      {
        id: "m-1",
        parentId: null,
        role: "user",
        content: "Show me the top outcomes.",
      },
      {
        id: "m-2",
        parentId: "m-1",
        role: "assistant",
        content: "Here they are.",
      },
      {
        id: "m-3",
        parentId: "m-2",
        role: "notice",
        content: "Local guidance only.",
      },
    ];

    const markdown = conversationToMarkdown(messages, exportedAt);

    expect(markdown).toContain("## User");
    expect(markdown).toContain("## Assistant");
    expect(markdown).toContain("## Notice");
    expect(markdown).toContain("Show me the top outcomes.");
    expect(markdown).toContain("Local guidance only.");
  });

  it("keeps an inline surface as a fenced JSON block", () => {
    const messages: ChatMessage[] = [
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [
          { kind: "text", text: "Here is the card." },
          { kind: "ui", id: "ui-1", node: surfaceCard() },
        ],
      },
    ];

    const markdown = conversationToMarkdown(messages, exportedAt);

    expect(markdown).toContain("```json");
    expect(markdown).toContain('"type": "outcome-card"');
    expect(markdown).toContain(
      "Minimize the time it takes to propagate secrets",
    );
  });

  it("uses the combined prose when a turn has no parts", () => {
    const messages: ChatMessage[] = [
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "Plain **answer**.",
      },
    ];

    expect(conversationToMarkdown(messages, exportedAt)).toContain(
      "Plain **answer**.",
    );
  });

  it("keeps the prose of a claims part that sits beside a surface", () => {
    const messages: ChatMessage[] = [
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content:
          "Secret rotation takes a week. [[ev:e1]] That is the bottleneck.",
        parts: [
          {
            kind: "claims",
            content:
              "Secret rotation takes a week. [[ev:e1]] That is the bottleneck.",
            claims: [
              {
                index: 0,
                text: "Secret rotation takes a week.",
                status: "cited",
                evidence: [
                  { id: "e1", name: "Call with Acme", source_name: "Gong" },
                ],
              },
            ],
          },
          { kind: "ui", id: "ui-1", node: surfaceCard() },
        ],
      },
    ];

    const markdown = conversationToMarkdown(messages, exportedAt);

    expect(markdown).toContain("Secret rotation takes a week.");
    expect(markdown).not.toContain("[[ev:e1]]");
    expect(markdown).toContain('"type": "outcome-card"');
    expect(markdown.indexOf("Secret rotation takes a week.")).toBeLessThan(
      markdown.indexOf("**Surface:"),
    );
  });

  it("labels every claim the way the transcript does", () => {
    const messages: ChatMessage[] = [
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [
          {
            kind: "claims",
            content: [
              "Rotation costs two engineer-days. [[ev:e1]]",
              "Nobody has measured the wait. [[hypothesis]]",
              "The team wants it fixed.",
            ].join(" "),
            claims: [
              {
                index: 0,
                text: "Rotation costs two engineer-days.",
                status: "cited",
                evidence: [
                  { id: "e1", name: "Call with Acme", source_name: "Gong" },
                ],
              },
              {
                index: 1,
                text: "Nobody has measured the wait.",
                status: "hypothesis",
                evidence: [],
              },
              {
                index: 2,
                text: "The team wants it fixed.",
                status: "uncited",
                evidence: [],
              },
            ],
          },
        ],
      },
    ];

    const markdown = conversationToMarkdown(messages, exportedAt);

    expect(markdown).toContain(
      "Rotation costs two engineer-days. (per Gong · Call with Acme, record e1)",
    );
    expect(markdown).toContain("Nobody has measured the wait. (Hypothesis)");
    expect(markdown).toContain("The team wants it fixed. (Uncited)");
    expect(markdown).not.toContain("[[ev:");
    expect(markdown).not.toContain("[[hypothesis]]");
  });

  it("names only the record fields the reply carries", () => {
    const messages: ChatMessage[] = [
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [
          {
            kind: "claims",
            content: [
              "One sentence is named by record only. [[ev:e2]]",
              "Another carries no name at all. [[ev:e3]]",
              "A third cites nothing. [[ev:e4]]",
            ].join(" "),
            claims: [
              {
                index: 0,
                text: "One sentence is named by record only.",
                status: "cited",
                evidence: [
                  { id: "e2", name: "Support ticket 812", source_name: "" },
                ],
              },
              {
                index: 1,
                text: "Another carries no name at all.",
                status: "cited",
                evidence: [{ id: "e3", name: "", source_name: "" }],
              },
              {
                index: 2,
                text: "A third cites nothing.",
                status: "cited",
                evidence: [],
              },
            ],
          },
        ],
      },
    ];

    const markdown = conversationToMarkdown(messages, exportedAt);

    expect(markdown).toContain(
      "One sentence is named by record only. (per Support ticket 812, record e2)",
    );
    expect(markdown).toContain(
      "Another carries no name at all. (per record e3)",
    );
    expect(markdown).toContain(
      "A third cites nothing. (cited, no record named)",
    );
  });

  it("keeps a marker inside a code fence literal", () => {
    const messages: ChatMessage[] = [
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [
          {
            kind: "claims",
            content: [
              "The marker looks like this:",
              "```",
              "[[ev:e1]]",
              "```",
              "and this sentence is cited. [[ev:e1]]",
            ].join("\n"),
            claims: [
              {
                index: 0,
                text: "and this sentence is cited.",
                status: "cited",
                evidence: [
                  { id: "e1", name: "Call with Acme", source_name: "Gong" },
                ],
              },
            ],
          },
        ],
      },
    ];

    const markdown = conversationToMarkdown(messages, exportedAt);

    expect(markdown).toContain("```\n[[ev:e1]]\n```");
    expect(markdown).toContain(
      "and this sentence is cited. (per Gong · Call with Acme, record e1)",
    );
  });

  it("prints a claim whose sentence is not in the prose", () => {
    const messages: ChatMessage[] = [
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [
          {
            kind: "claims",
            content: "The prose moved on without it.",
            claims: [
              {
                index: 0,
                text: "A sentence the validator kept separately.",
                status: "hypothesis",
                evidence: [],
              },
            ],
          },
        ],
      },
    ];

    const markdown = conversationToMarkdown(messages, exportedAt);

    expect(markdown).toContain("The prose moved on without it.");
    expect(markdown).toContain(
      "A sentence the validator kept separately. (Hypothesis)",
    );
  });

  it("says once what a citation labels when claims are exported", () => {
    const messages: ChatMessage[] = [
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [
          {
            kind: "claims",
            content: "Rotation costs two engineer-days. [[ev:e1]]",
            claims: [
              {
                index: 0,
                text: "Rotation costs two engineer-days.",
                status: "cited",
                evidence: [
                  { id: "e1", name: "Call with Acme", source_name: "Gong" },
                ],
              },
            ],
          },
        ],
      },
    ];

    const withClaims = conversationToMarkdown(messages, exportedAt);
    expect(withClaims).toContain("as it stood when the reply was written");

    const withoutClaims = conversationToMarkdown(
      [
        {
          id: "m-2",
          parentId: null,
          role: "assistant",
          content: "Plain answer.",
        },
      ],
      exportedAt,
    );
    expect(withoutClaims).not.toContain(
      "as it stood when the reply was written",
    );
  });

  it("hides claim markers in a plain text part", () => {
    const messages: ChatMessage[] = [
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [
          {
            kind: "text",
            text: "A streamed sentence [[ev:e1]] that never got validated.",
          },
        ],
      },
    ];

    const markdown = conversationToMarkdown(messages, exportedAt);

    expect(markdown).toContain(
      "A streamed sentence  that never got validated.",
    );
    expect(markdown).not.toContain("[[ev:e1]]");
  });

  it("exports a duplicated prose once when a turn carries both parts", () => {
    const prose = "Rotation costs two engineer-days. [[ev:e1]]";
    const messages: ChatMessage[] = [
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: prose,
        parts: [
          { kind: "text", text: prose },
          {
            kind: "claims",
            content: prose,
            claims: [
              {
                index: 0,
                text: "Rotation costs two engineer-days.",
                status: "cited",
                evidence: [
                  { id: "e1", name: "Call with Acme", source_name: "Gong" },
                ],
              },
            ],
          },
        ],
      },
    ];

    const markdown = conversationToMarkdown(messages, exportedAt);

    expect(markdown.match(/Rotation costs two engineer-days\./g)).toHaveLength(
      1,
    );
  });

  it("prints a near-miss sentence once, even when its label will not attach", () => {
    const messages: ChatMessage[] = [
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [
          {
            kind: "claims",
            // The list item lost its terminal punctuation, so the claim cannot be
            // matched to it. The sentence was still shown, so it was still exported.
            content: "- Ticket 812 backs it up [[ev:e2]]",
            claims: [
              {
                index: 0,
                text: "Ticket 812 backs it up.",
                status: "cited",
                evidence: [
                  { id: "e2", name: "Ticket 812", source_name: "Zendesk" },
                ],
              },
            ],
          },
        ],
      },
    ];

    const markdown = conversationToMarkdown(messages, exportedAt);

    expect(markdown.match(/Ticket 812 backs it up/g)).toHaveLength(1);
  });

  it("dates the export in the filename", () => {
    expect(exportFilename(exportedAt)).toBe(
      "agentic-odi-conversation-2026-10-24.md",
    );
  });

  it("names the workspace export by the day it was taken", () => {
    expect(workspaceExportFilename(exportedAt)).toBe(
      "agentic-odi-workspace-2026-10-24.json",
    );
  });

  it("hands the workspace JSON to the browser's save dialog", () => {
    const anchor = document.createElement("a");
    const click = vi.spyOn(anchor, "click").mockImplementation(() => {});
    const createElement = vi
      .spyOn(document, "createElement")
      .mockReturnValue(anchor);
    const createObjectURL = vi.fn(() => "blob:workspace");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });

    downloadJson('{"version":1}', "agentic-odi-workspace-2026-10-24.json");

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(anchor.download).toBe("agentic-odi-workspace-2026-10-24.json");
    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:workspace");

    click.mockRestore();
    createElement.mockRestore();
    vi.unstubAllGlobals();
  });
});
