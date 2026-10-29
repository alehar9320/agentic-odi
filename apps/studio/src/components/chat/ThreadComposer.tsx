/**
 * The thread composer.
 *
 * Bound to the assistant-ui composer runtime: attachments, send, and cancel are
 * the library's. The Studio's own additions — the slash palette, the connector
 * chips, and the model hint — sit on top of it and use the same markup as the
 * setup wizard's composer.
 */

import { ComposerPrimitive, useAui, useAuiState } from "@assistant-ui/react";
import { useMemo, useState } from "react";

import { isSlashCommand, matchCommands, type StudioCommand } from "../../lib/commands";
import { useStudio } from "../../state/StudioContext";
import { ArrowUpIcon, PaperclipIcon, StopIcon } from "../icons";
import { CommandPalette, ComposerHint, ConnectorChips, paletteOpenFor } from "./composerParts";

function AttachmentRow() {
  const aui = useAui();
  const attachments = useAuiState((state) => state.composer.attachments);

  if (attachments.length === 0) {
    return null;
  }

  return (
    <div className="composer__attachments" aria-label="Attachments">
      {attachments.map((attachment, index) => (
        <span className="attachment-chip" key={attachment.id}>
          <span className="attachment-chip__name">{attachment.name}</span>
          <button
            type="button"
            className="attachment-chip__remove"
            aria-label={`Remove ${attachment.name}`}
            onClick={() => void aui.composer.attachment({ index }).remove()}
          >
            ✕
          </button>
        </span>
      ))}
    </div>
  );
}

function ComposerBody({
  onCommand,
  onSlashCommand,
  placeholder,
  autoFocus = false,
}: {
  onCommand: (command: StudioCommand) => void;
  onSlashCommand?: (text: string) => boolean;
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const aui = useAui();
  const { llmHealth } = useStudio();
  const text = useAuiState((state) => state.composer.text);
  const running = useAuiState((state) => state.thread.isRunning);
  const [highlight, setHighlight] = useState(0);
  // Remember which draft was dismissed, so typing again re-opens the palette
  // without an effect that writes state on every keystroke.
  const [dismissedFor, setDismissedFor] = useState<string | null>(null);

  const offline = llmHealth.healthy === false;
  const matches = useMemo(() => (paletteOpenFor(text) ? matchCommands(text) : []), [text]);
  const open = paletteOpenFor(text) && dismissedFor !== text;
  const activeIndex = Math.min(highlight, Math.max(matches.length - 1, 0));
  const activeCommand = matches[activeIndex];

  function choose(command: StudioCommand) {
    aui.composer.setText("");
    setHighlight(0);
    setDismissedFor("");
    onCommand(command);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (open) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        if (!matches.length) {
          return;
        }
        const delta = event.key === "ArrowDown" ? 1 : -1;
        setHighlight((index) => (index + delta + matches.length) % matches.length);
        return;
      }
      if ((event.key === "Enter" || event.key === "Tab") && activeCommand) {
        event.preventDefault();
        choose(activeCommand);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        setDismissedFor(text);
        return;
      }
    }

    // A command typed straight through — palette closed or never opened — is
    // still a command, and must never be sent to the model as prose.
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing &&
      isSlashCommand(text) &&
      onSlashCommand
    ) {
      event.preventDefault();
      aui.composer.setText("");
      setDismissedFor("");
      onSlashCommand(text);
    }
  }

  return (
    <>
      <CommandPalette
        open={open}
        matches={matches}
        activeIndex={activeIndex}
        onHover={setHighlight}
        onChoose={choose}
      />
      <ConnectorChips />
      <AttachmentRow />
      <div className="composer__shell">
        <label className="sr-only" htmlFor="studio-composer">
          Message the studio
        </label>
        <ComposerPrimitive.Input
          id="studio-composer"
          className="composer__input"
          rows={1}
          autoFocus={autoFocus}
          placeholder={
            placeholder ??
            (offline
              ? "Model offline — type / for commands, or capture what you know…"
              : "What do you want to make happen?")
          }
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={open ? "studio-command-palette" : undefined}
          onKeyDown={onKeyDown}
        />
        <div className="composer__actions">
          <ComposerPrimitive.AddAttachment
            className="composer__attach"
            aria-label="Attach a file"
            title="Attach a text file or an image"
          >
            <PaperclipIcon size={16} />
          </ComposerPrimitive.AddAttachment>
          {running ? (
            <ComposerPrimitive.Cancel
              className="composer__send composer__send--stop"
              aria-label="Stop generating"
            >
              <StopIcon size={16} />
            </ComposerPrimitive.Cancel>
          ) : (
            <ComposerPrimitive.Send className="composer__send" aria-label="Send message">
              <ArrowUpIcon size={18} />
            </ComposerPrimitive.Send>
          )}
        </div>
      </div>
      <ComposerHint />
    </>
  );
}

export function ThreadComposer(props: {
  onCommand: (command: StudioCommand) => void;
  onSlashCommand?: (text: string) => boolean;
  placeholder?: string;
  autoFocus?: boolean;
}) {
  return (
    <ComposerPrimitive.Root className="composer">
      <ComposerBody {...props} />
    </ComposerPrimitive.Root>
  );
}
