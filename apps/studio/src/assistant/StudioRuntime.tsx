/* eslint-disable react-refresh/only-export-components -- runtime module intentionally exports the provider alongside suggestions and helpers */

/**
 * The conversation runtime.
 *
 * assistant-ui renders the thread; this module is the only place that knows how
 * it talks to the Studio. One `useExternalStoreRuntime` call turns our message
 * store into a thread with sending, editing, regenerating, cancelling, branch
 * switching, attachments, and write approvals — every feature is switched on by
 * the presence of one handler, so the capability surface is readable in one
 * place.
 */

import type { ReactNode } from "react";
import { useMemo } from "react";

import { AssistantRuntimeProvider, useExternalStoreRuntime } from "@assistant-ui/react";

import { useStudio } from "../state/StudioContext";
import type { ChatMessage } from "../types";
import { createAttachmentAdapter, preparedAttachments } from "./attachments";
import { textOf, toThreadMessageLike } from "./convert";
import { createDictationAdapter } from "./dictation";

export interface StudioSuggestion {
  title: string;
  label: string;
  prompt: string;
  /**
   * The shape of what a click produces, e.g. "A job map · steps · what is
   * still a guess". #317 renders it as the card's preview line; the copy lives
   * here so the card, the thread, and the test read one string.
   */
  artifact?: string;
}

/**
 * First-run starters.
 *
 * Each prompt opens with the material the person brings and only then asks for
 * help, so the first click produces work instead of another question. The count
 * in the notes card is the person's own example, never a finding of ours, and
 * every promise is answerable with the existing job, step, outcome, evidence,
 * and landscape tools. `starterCopy.test.ts` holds these rules.
 */
export const NOTES_PROMPT =
  "I have about 40 interview notes from the last month. Help me turn them into one opportunity we can defend: read what I paste, group what customers are trying to do, draft the desired outcomes in ODI form, and tell me which one is most underserved and what evidence is still missing.";
export const CHURN_PROMPT =
  "Our churn moved this month and I don't trust the first explanation. Ask me for the segment and the cancellation reasons I have, then help me state the customer's job, draft outcomes, and show which ones the evidence actually supports.";
export const ROADMAP_PROMPT =
  "I've inherited a roadmap. Help me reconstruct the job it assumes, map the steps, and mark which outcomes have evidence and which are guesses, before I commit the team to it.";

/**
 * Returning-user starters.
 *
 * Still reachable once the canvas holds something, so their words are out of
 * scope for #316 and stay as they were.
 */
export const OPPORTUNITY_PROMPT =
  "I have an opportunity in mind. Ask me what it is, then help me sharpen it into something I can defend.";
export const FIND_PROMPT =
  "I need to find the next opportunity worth chasing. Help me look across what I know about my customers and find the gap that matters most.";
export const PRESSURE_TEST_PROMPT =
  "I have a bet I'm about to make. Pressure-test it with me: ask what it is, then tell me what would have to be true and what evidence I'm missing.";
export const CAPTURE_PROMPT =
  "I heard something from a customer that I want to make sense of. Ask me what they said, then help me turn it into something we can act on.";
export const FRAME_JOB_PROMPT =
  "Help me name the job I'm trying to win. Ask me who it is for and what they are trying to get done.";

/** Starter prompts for the empty state, chosen from what the canvas holds. */
export function suggestionsFor(state: {
  jobCount: number;
  outcomeCount: number;
}): StudioSuggestion[] {
  // An empty stage offers three situations a person can recognise from their
  // own desk, in this order: the most common material first. A canvas with
  // data falls through to the returning-user swaps below.
  if (state.jobCount === 0 && state.outcomeCount === 0) {
    return [
      {
        title: "Turn 40 interview notes into one bet",
        label: "Paste the notes. Get one scored outcome and the gap that justifies it.",
        prompt: NOTES_PROMPT,
        artifact: "One outcome · its score · the evidence still missing",
      },
      {
        title: "Find what the churn spike is telling you",
        label: "Bring the numbers and the complaints. Separate the reason from the noise.",
        prompt: CHURN_PROMPT,
        artifact: "A segment note · outcomes · which ones have evidence",
      },
      {
        title: "Inherit a roadmap without inheriting its assumptions",
        label: "Map the job behind the roadmap, then mark what is still a guess.",
        prompt: ROADMAP_PROMPT,
        artifact: "A job map · steps · what is still a guess",
      },
    ];
  }

  return [
    {
      title: "Sharpen an opportunity",
      label: "Turn a hunch into something defensible",
      prompt: OPPORTUNITY_PROMPT,
    },
    state.outcomeCount > 0
      ? {
          title: "Pressure-test a bet",
          label: "Find what would have to be true",
          prompt: PRESSURE_TEST_PROMPT,
        }
      : {
          title: "Find the next opportunity",
          label: "Look across what you already know",
          prompt: FIND_PROMPT,
        },
    state.jobCount > 0
      ? {
          title: "Capture what you heard",
          label: "Turn a customer's words into an outcome",
          prompt: CAPTURE_PROMPT,
        }
      : {
          title: "Name the job",
          label: "Start from who it is for",
          prompt: FRAME_JOB_PROMPT,
        },
  ];
}

export function StudioRuntimeProvider({ children }: { children: ReactNode }) {
  const {
    messages,
    streaming,
    canvas,
    sendMessage,
    regenerateFrom,
    editFrom,
    switchBranch,
    respondToApproval,
    stopStreaming,
  } = useStudio();

  const attachments = useMemo(() => createAttachmentAdapter(), []);
  // Null where speech recognition is missing, so the composer shows no mic.
  const dictation = useMemo(() => createDictationAdapter(), []);
  const jobCount = canvas?.jobs.length ?? 0;
  const outcomeCount = canvas?.outcomes.length ?? 0;
  const suggestions = useMemo(
    () => suggestionsFor({ jobCount, outcomeCount }),
    [jobCount, outcomeCount],
  );

  const runtime = useExternalStoreRuntime<ChatMessage>({
    isRunning: streaming,
    messages,
    convertMessage: toThreadMessageLike,
    suggestions,
    adapters: { attachments, ...(dictation ? { dictation } : {}) },
    onNew: async (message) => {
      await sendMessage(textOf(message), preparedAttachments(message.attachments));
    },
    onEdit: async (message) => {
      await editFrom(message.sourceId, textOf(message), preparedAttachments(message.attachments));
    },
    onReload: async (parentId, config) => {
      await regenerateFrom(config.sourceId ?? parentId);
    },
    onCancel: async () => {
      stopStreaming();
    },
    setMessages: (next) => {
      switchBranch([...next]);
    },
    onRespondToToolApproval: async ({ approvalId, approved, reason }) => {
      await respondToApproval(approvalId, approved, reason);
    },
  });

  return <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>;
}
