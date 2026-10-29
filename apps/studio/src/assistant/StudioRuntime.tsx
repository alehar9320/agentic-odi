/* eslint-disable react-refresh/only-export-components -- runtime module intentionally exports the provider alongside suggestions and helpers */

/**
 * The conversation runtime.
 *
 * assistant-ui renders the thread; this module is the only place that knows how
 * it talks to the Studio. One `useExternalStoreRuntime` call turns our message
 * store into a thread with sending, editing, regenerating, cancelling, branch
 * switching, attachments, queued follow-ups, feedback, deletion, dictation,
 * thread history, and write approvals — every feature is switched on by the
 * presence of one handler, so the capability surface is readable in one place.
 */

import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  AssistantRuntimeProvider,
  WebSpeechDictationAdapter,
  createMessageQueue,
  useExternalStoreRuntime,
  type AppendMessage,
} from "@assistant-ui/react";

import { useStudio } from "../state/StudioContext";
import type { ChatAttachment, ChatMessage } from "../types";
import { createAttachmentAdapter, preparedAttachments } from "./attachments";
import { textOf, toThreadMessageLike } from "./convert";
import { recordFeedback } from "./feedback";

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

/** The extraction a turn carries; the runtime hands back its own attachment list. */
function filesOf(message: AppendMessage): ChatAttachment[] {
  return preparedAttachments(message.attachments);
}

type SendFn = (text: string, attachments: ChatAttachment[]) => Promise<void>;

/**
 * A stable call-through to the newest send.
 *
 * The queue controller is built once, but the send belongs to a render: it
 * closes over the visible messages. The handle keeps the controller stable
 * while every queued dispatch runs against the current send.
 */
function createSendHandle(initial: SendFn) {
  let current = initial;
  return {
    set(next: SendFn) {
      current = next;
    },
    send(text: string, attachments: ChatAttachment[]) {
      return current(text, attachments);
    },
  };
}

export function StudioRuntimeProvider({ children }: { children: ReactNode }) {
  const {
    messages,
    streaming,
    conversationId,
    conversations,
    conversationsLoading,
    canvas,
    sendMessage,
    regenerateFrom,
    editFrom,
    switchBranch,
    respondToApproval,
    stopStreaming,
    clearChat,
    openConversation,
    deleteConversation,
    renameConversation,
    refreshConversations,
    deleteMessage,
    pushToast,
  } = useStudio();

  const attachments = useMemo(() => createAttachmentAdapter(), []);
  const jobCount = canvas?.jobs.length ?? 0;
  const outcomeCount = canvas?.outcomes.length ?? 0;
  const suggestions = useMemo(
    () => suggestionsFor({ jobCount, outcomeCount }),
    [jobCount, outcomeCount],
  );

  // Keep the handle pointed at the current send. This effect is declared before
  // the queue's idle effect, so the dispatch that follows a settling reply uses
  // the send from this render.
  const [sendHandle] = useState(() => createSendHandle(sendMessage));
  useEffect(() => {
    sendHandle.set(sendMessage);
  }, [sendHandle, sendMessage]);

  const dispatchQueued = useCallback(
    (message: AppendMessage) => {
      void sendHandle.send(textOf(message), filesOf(message));
    },
    [sendHandle],
  );

  const queue = useMemo(
    () =>
      createMessageQueue({
        // No `cancel`: a follow-up sent mid-turn must wait for the answer being
        // written, not cancel it. Stop is the reader's own control, not a
        // side effect of typing the next question.
        run: dispatchQueued,
      }),
    [dispatchQueued],
  );

  // A send that arrives while a turn runs is buffered by the runtime; once the
  // run settles the next queued item is dispatched on its own.
  useEffect(() => {
    if (streaming) {
      queue.notifyBusy();
      return;
    }
    queue.notifyIdle();
  }, [queue, streaming]);

  // The composer reads its queue from the adapter when it renders, and a queue
  // change is not a message change, so nothing else would repaint the pending
  // row. Subscribe and bump a revision: a buffered follow-up appears the moment
  // it is accepted, not on the next streamed token.
  const [, setQueueRevision] = useState(0);
  useEffect(
    () => queue.subscribe(() => setQueueRevision((revision) => revision + 1)),
    [queue],
  );

  const liveId = useMemo(() => {
    if (!streaming) {
      return null;
    }
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      if (messages[index].role === "assistant") {
        return messages[index].id;
      }
    }
    return null;
  }, [messages, streaming]);

  const convertMessage = useCallback(
    (message: ChatMessage) => toThreadMessageLike(message, { live: message.id === liveId }),
    [liveId],
  );

  const dictation = useMemo(() => {
    // The Web Speech API is not in every webview (Tauri's WebKit notably
    // varies). Offering a microphone that cannot listen is worse than none, so
    // the adapter is only attached when the browser actually ships it.
    if (typeof window === "undefined" || !WebSpeechDictationAdapter.isSupported()) {
      return null;
    }
    return new WebSpeechDictationAdapter({ language: "en-US", interimResults: true });
  }, []);

  // The history list is the sidecar's conversations, newest first. The runtime
  // compares this adapter by identity, so the list is memoised with its data.
  const threads = useMemo(
    () =>
      conversations.map((conversation) => ({
        id: conversation.id,
        status: "regular" as const,
        title: conversation.title || "Untitled thread",
      })),
    [conversations],
  );

  const threadList = useMemo(
    () => ({
      threadId: conversationId ?? undefined,
      isLoading: conversationsLoading,
      threads,
      onSwitchToThread: (threadId: string) => openConversation(threadId),
      onSwitchToNewThread: () => clearChat(),
      onRename: (threadId: string, newTitle: string) =>
        renameConversation(threadId, newTitle),
      onDelete: (threadId: string) => deleteConversation(threadId),
    }),
    [
      conversationId,
      conversationsLoading,
      threads,
      clearChat,
      openConversation,
      renameConversation,
      deleteConversation,
    ],
  );

  const feedback = useMemo(
    () => ({
      submit: ({
        message,
        type,
      }: {
        message: { id: string };
        type: "positive" | "negative";
      }) => {
        recordFeedback(message.id, type);
        pushToast("success", type === "positive" ? "Noted — thank you." : "Noted — I'll do better.");
      },
    }),
    [pushToast],
  );

  const runtime = useExternalStoreRuntime<ChatMessage>({
    isRunning: streaming,
    messages,
    convertMessage,
    suggestions,
    adapters: {
      attachments,
      threadList,
      feedback,
      ...(dictation ? { dictation } : {}),
    },
    queue: queue.adapter,
    onNew: async (message) => {
      await sendMessage(textOf(message), filesOf(message));
    },
    onEdit: async (message) => {
      await editFrom(message.sourceId, textOf(message), filesOf(message));
    },
    onReload: async (parentId, config) => {
      await regenerateFrom(config.sourceId ?? parentId);
    },
    onCancel: async () => {
      stopStreaming();
    },
    onDelete: async (messageId) => {
      deleteMessage(messageId);
    },
    setMessages: (next) => {
      switchBranch([...next]);
    },
    onRespondToToolApproval: async ({ approvalId, approved, reason }) => {
      await respondToApproval(approvalId, approved, reason);
    },
    // The thread list is rebuilt from the sidecar whenever one of its actions
    // settles, so a rename or a delete shows up without a reload.
    onRefetchThread: async () => {
      await refreshConversations();
    },
  });

  return <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>;
}
