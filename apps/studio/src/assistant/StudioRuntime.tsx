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

export interface StudioSuggestion {
  title: string;
  label: string;
  prompt: string;
}

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
    adapters: { attachments },
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
