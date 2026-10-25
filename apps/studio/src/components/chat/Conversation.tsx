/**
 * The transcript.
 *
 * assistant-ui owns the message list, the message parts, and the branch picker;
 * this file decides what each of those looks like in the Studio. Everything it
 * renders comes from one place — `assistant/convert.ts` — so a new part type is
 * added in exactly two files.
 */

import {
  ActionBarPrimitive,
  AuiIf,
  BranchPickerPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAuiState,
} from "@assistant-ui/react";

import { SURFACE_PART } from "../../assistant/convert";
import {
  AssistantAvatar,
  FilePart,
  ReasoningPart,
  SourcePart,
  SurfacePart,
  TextPart,
  ToolPart,
  TypingPart,
} from "../../assistant/parts";
import { useStudio } from "../../state/StudioContext";
import type { StudioError } from "../../types";
import { UiActionContext } from "../../ui/actions";
import { FailurePanel } from "../FailurePanel";
import { CopyIcon } from "../icons";
import { Markdown } from "./Markdown";

const PHASE_LABEL: Record<string, string> = {
  health_check: "Waking the model",
  mcp_tools: "Opening your studio tools",
  model: "Thinking",
};

function phaseLabel(phase: string | null): string {
  if (!phase) {
    return "Thinking";
  }
  return PHASE_LABEL[phase] ?? "Thinking";
}

function AssistantMessage() {
  const { thinkingPhase, offlineReply, sendMessage } = useStudio();
  const running = useAuiState((state) => state.message.status?.type === "running");
  const hasText = useAuiState((state) =>
    state.message.content.some((part) => part.type === "text" && part.text.trim().length > 0),
  );
  const error = useAuiState(
    (state) => state.message.metadata.custom?.error as StudioError | undefined,
  );
  const retryText = useAuiState(
    (state) => state.message.metadata.custom?.retryText as string | undefined,
  );

  return (
    <article className="message message--assistant">
      <AssistantAvatar />
      <div className="message__body">
        {offlineReply ? <span className="message__tag">Local guidance</span> : null}

        <MessagePrimitive.Parts
          components={{
            Text: TextPart,
            Reasoning: ReasoningPart,
            Source: SourcePart,
            File: FilePart,
            data: { by_name: { [SURFACE_PART]: SurfacePart } },
            tools: { Fallback: ToolPart },
          }}
        />

        {running && !hasText ? <TypingPart label={phaseLabel(thinkingPhase)} /> : null}
        {running && hasText ? <span className="caret" aria-hidden="true" /> : null}

        {error ? (
          <FailurePanel
            error={error}
            retryText={retryText}
            onRetry={(text) => void sendMessage(text)}
          />
        ) : null}

        <AuiIf condition={(state) => state.message.branchCount > 1}>
          <BranchPickerPrimitive.Root className="branch-picker">
            <BranchPickerPrimitive.Previous className="branch-picker__step" aria-label="Previous reply">
              ‹
            </BranchPickerPrimitive.Previous>
            <span className="branch-picker__label">
              <BranchPickerPrimitive.Number /> of <BranchPickerPrimitive.Count />
            </span>
            <BranchPickerPrimitive.Next className="branch-picker__step" aria-label="Next reply">
              ›
            </BranchPickerPrimitive.Next>
          </BranchPickerPrimitive.Root>
        </AuiIf>

        {!running ? (
          <ActionBarPrimitive.Root className="message__actions" hideWhenRunning>
            <ActionBarPrimitive.Copy className="quiet-action" aria-label="Copy reply">
              <CopyIcon size={14} /> Copy
            </ActionBarPrimitive.Copy>
            <ActionBarPrimitive.Reload className="quiet-action" aria-label="Regenerate reply">
              Regenerate
            </ActionBarPrimitive.Reload>
          </ActionBarPrimitive.Root>
        ) : null}
      </div>
    </article>
  );
}

function UserMessage() {
  return (
    <article className="message message--user">
      <div className="message__bubble">
        <MessagePrimitive.Parts components={{ Text: TextPart }} />
      </div>
      <MessagePrimitive.Attachments>
        {({ attachment }) => (
          <span className="attachment-chip">
            <span className="attachment-chip__name">{attachment.name}</span>
          </span>
        )}
      </MessagePrimitive.Attachments>
      <ActionBarPrimitive.Root className="message__actions message__actions--user">
        <ActionBarPrimitive.Edit className="quiet-action" aria-label="Edit message">
          Edit
        </ActionBarPrimitive.Edit>
        <ActionBarPrimitive.Copy className="quiet-action" aria-label="Copy message">
          Copy
        </ActionBarPrimitive.Copy>
      </ActionBarPrimitive.Root>
    </article>
  );
}

function SystemMessage() {
  return (
    <article className="message message--notice">
      <MessagePrimitive.Parts components={{ Text: TextPart }} />
    </article>
  );
}

/** Editing a message in place: same verb, same place, no second surface. */
function EditComposer() {
  return (
    <ComposerPrimitive.Root className="composer composer--edit">
      <ComposerPrimitive.Input
        className="composer__input"
        submitMode="enter"
        aria-label="Edit message"
      />
      <div className="composer__actions">
        <ComposerPrimitive.Cancel className="quiet-action">Cancel</ComposerPrimitive.Cancel>
        <ComposerPrimitive.Send className="composer__send composer__send--text" aria-label="Save edit">
          Save
        </ComposerPrimitive.Send>
      </div>
    </ComposerPrimitive.Root>
  );
}

export function Conversation() {
  const { sendMessage, streaming } = useStudio();

  return (
    <UiActionContext.Provider
      value={{ onIntent: (intent) => void sendMessage(intent), busy: streaming }}
    >
      <div className="conversation" role="log" aria-live="polite" aria-label="Conversation">
        <ThreadPrimitive.Messages
          components={{
            UserMessage,
            AssistantMessage,
            SystemMessage,
            EditComposer,
          }}
        />
      </div>
    </UiActionContext.Provider>
  );
}

export { Markdown };
