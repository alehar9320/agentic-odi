/**
 * The thread composer.
 *
 * Bound to the assistant-ui composer runtime: attachments, send, and cancel are
 * the library's. The Studio's own additions — the slash palette, the connector
 * chips, and the model hint — sit on top of it and use the same markup as the
 * setup wizard's composer.
 */

import { AuiIf, ComposerPrimitive, useAui, useAuiState } from "@assistant-ui/react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import {
  ATTACHMENT_ACCEPT,
  MAX_ATTACHMENT_CHARS,
  MAX_IMAGE_BYTES,
  attachmentRejection,
  formatFileSize,
  isImageLike,
} from "../../assistant/attachments";
import { dictationSupported } from "../../assistant/dictation";
import { recallAnnouncement, useComposerHistory } from "../../assistant/composerHistory";
import { isSlashCommand, matchCommands, type StudioCommand } from "../../lib/commands";
import { useStudio } from "../../state/StudioContext";
import { ArrowUpIcon, MicIcon, PaperclipIcon, StopIcon } from "../icons";
import { CommandPalette, ComposerHint, ConnectorChips, SuggestionPills, paletteOpenFor } from "./composerParts";
import { QueueLane } from "./QueueLane";
import { ModelPicker } from "./ModelPicker";

const acceptedAttachmentTypes = ATTACHMENT_ACCEPT.split(",");
const acceptedTextExtensions = acceptedAttachmentTypes.filter((type) => type.startsWith("."));
const acceptedImageTypes = acceptedAttachmentTypes
  .filter((type) => type.startsWith("image/"))
  .map((type) => type.slice("image/".length).toUpperCase());
const ATTACHMENT_HELP = `Supported text files (${acceptedTextExtensions.join(", ")} and text/*) and images (${acceptedImageTypes.join(", ")}). Images up to ${Math.floor(MAX_IMAGE_BYTES / (1024 * 1024))} MB; text files up to ${MAX_ATTACHMENT_CHARS.toLocaleString()} characters.`;

/** The local preview for an image before it is ever sent. */
function AttachmentThumb({ file }: { file?: File }) {
  const url = useMemo(() => {
    if (!file || !isImageLike(file.type) || typeof URL.createObjectURL !== "function") {
      return null;
    }
    return URL.createObjectURL(file);
  }, [file]);

  useEffect(() => {
    return () => {
      if (url) {
        URL.revokeObjectURL(url);
      }
    };
  }, [url]);

  if (!url) {
    return null;
  }
  return <img className="attachment-chip__thumb" src={url} alt="" />;
}

function AttachmentRow() {
  const aui = useAui();
  const attachments = useAuiState((state) => state.composer.attachments);

  if (attachments.length === 0) {
    return null;
  }

  return (
    <div className="composer__attachments" role="list" aria-label="Attachments">
      {attachments.map((attachment, index) => {
        const size = formatFileSize(attachment.file?.size ?? 0);
        return (
          <span className="attachment-chip" role="listitem" key={attachment.id}>
            <AttachmentThumb file={attachment.file} />
            <span className="attachment-chip__meta">
              <span className="attachment-chip__name">{attachment.name}</span>
              {size ? <span className="attachment-chip__size">{size}</span> : null}
            </span>
            <button
              type="button"
              className="attachment-chip__remove"
              aria-label={`Remove ${attachment.name}`}
              onClick={() => void aui.composer.attachment({ index }).remove()}
            >
              ✕
            </button>
          </span>
        );
      })}
    </div>
  );
}

function ComposerBody({
  onCommand,
  onSlashCommand,
  onFiles,
  placeholder,
  autoFocus = false,
}: {
  onCommand: (command: StudioCommand) => void;
  onSlashCommand?: (text: string) => boolean;
  onFiles: (files: File[]) => void;
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const aui = useAui();
  const { llmHealth } = useStudio();
  const history = useComposerHistory();
  const [recall, setRecall] = useState("");
  // A page can mount more than one composer, so every id and description needs
  // to be unique per instance rather than a fixed string in the document.
  const attachmentHelpId = useId();
  const inputId = useId();
  const paletteId = useId();
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
      return;
    }

    // Enter is a send, not a race (#410): while a turn runs the follow-up
    // joins the queue lane instead of interrupting the live answer.
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing &&
      text.trim() !== ""
    ) {
      event.preventDefault();
      aui.composer.send({ steer: false });
      return;
    }

    // The palette owns the arrows while it is open; history must not fight it.
    if (open || event.defaultPrevented) {
      return;
    }

    const empty = text.trim() === "";
    history.onKeyDown(event);
    // The hook prevents the default only when it actually recalled a message.
    // Announcing here keeps it to one status change per recall, never per key.
    if (event.key === "ArrowUp" && empty && event.defaultPrevented) {
      setRecall(recallAnnouncement(aui.composer.getState().text));
    }
  }

  return (
    <>
      <p className="sr-only" role="status">
        {recall}
      </p>
      <SuggestionPills />
      <CommandPalette
        id={paletteId}
        open={open}
        matches={matches}
        activeIndex={activeIndex}
        onHover={setHighlight}
        onChoose={choose}
      />
      <ConnectorChips />
      <QueueLane />
      <AttachmentRow />
      {/* The live transcript is recognition output, not a draft: it is marked
          as interim and the primitive replaces it with the final sentence. */}
      <AuiIf condition={(state) => state.composer.dictation != null}>
        <p className="composer__dictation">
          <span className="composer__dictation-label">Listening</span>
          <ComposerPrimitive.DictationTranscript />
        </p>
      </AuiIf>
      {/* The runtime renders this container only while a quote is set, so the
          strip cannot promise a quote that is not there. */}
      <ComposerPrimitive.Quote className="composer__quote">
        <ComposerPrimitive.QuoteText className="composer__quote-text" />
        <ComposerPrimitive.QuoteDismiss
          className="composer__quote-dismiss"
          aria-label="Remove quote"
        >
          ✕
        </ComposerPrimitive.QuoteDismiss>
      </ComposerPrimitive.Quote>
      <div className="composer__shell">
        <label className="sr-only" htmlFor={inputId}>
          Message the studio
        </label>
        <ComposerPrimitive.Input
          id={inputId}
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
          aria-haspopup="listbox"
          aria-controls={open ? paletteId : undefined}
          onKeyDown={onKeyDown}
          onPaste={(event) => {
            // A screenshot on the clipboard is a file, not text: attach it
            // rather than letting the browser paste a placeholder name.
            const files = Array.from(event.clipboardData?.files ?? []);
            if (files.length === 0) {
              return;
            }
            event.preventDefault();
            onFiles(files);
          }}
        />
        <div className="composer__actions">
          {/* No microphone where recognition is unavailable, and no second
              voice system: this is the documented dictation seam. */}
          {dictationSupported() ? (
            <>
              <AuiIf condition={(state) => state.composer.dictation == null}>
                <ComposerPrimitive.Dictate
                  className="composer__attach composer__mic"
                  aria-label="Dictate a message"
                >
                  <MicIcon size={16} />
                </ComposerPrimitive.Dictate>
              </AuiIf>
              <AuiIf condition={(state) => state.composer.dictation != null}>
                <ComposerPrimitive.StopDictation
                  className="composer__attach composer__mic is-listening"
                  aria-label="Stop dictating"
                >
                  <StopIcon size={14} />
                </ComposerPrimitive.StopDictation>
              </AuiIf>
            </>
          ) : null}
          <ComposerPrimitive.AddAttachment
            className="composer__attach"
            aria-label="Attach a file"
            aria-describedby={attachmentHelpId}
            title={ATTACHMENT_HELP}
          >
            <PaperclipIcon size={16} />
          </ComposerPrimitive.AddAttachment>
          <span id={attachmentHelpId} className="sr-only">
            {ATTACHMENT_HELP}
          </span>
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
      <ComposerHint trailing={<ModelPicker />} />
    </>
  );
}

function hasFiles(event: React.DragEvent<HTMLElement>): boolean {
  return Array.from(event.dataTransfer?.types ?? []).includes("Files");
}

export function ThreadComposer(props: {
  onCommand: (command: StudioCommand) => void;
  onSlashCommand?: (text: string) => boolean;
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const aui = useAui();
  const { pushToast } = useStudio();
  const [dragging, setDragging] = useState(false);
  // dragenter/dragleave fire for every child; count depth so moving over the
  // textarea does not flicker the drop state off and on.
  const dragDepth = useRef(0);

  function attachFiles(files: File[]) {
    for (const file of files) {
      const rejection = attachmentRejection(file);
      if (rejection) {
        pushToast("error", rejection);
        continue;
      }
      void aui.composer.addAttachment(file);
    }
  }

  return (
    <ComposerPrimitive.Root
      className={`composer${dragging ? " is-dragging" : ""}`}
      onDragEnter={(event) => {
        if (!hasFiles(event)) {
          return;
        }
        event.preventDefault();
        dragDepth.current += 1;
        setDragging(true);
      }}
      onDragOver={(event) => {
        if (!hasFiles(event)) {
          return;
        }
        // Without this the browser opens the dropped file instead.
        event.preventDefault();
      }}
      onDragLeave={() => {
        // Leave events often carry no types, so this only ever removes depth we
        // added on a file drag.
        dragDepth.current = Math.max(dragDepth.current - 1, 0);
        if (dragDepth.current === 0) {
          setDragging(false);
        }
      }}
      onDrop={(event) => {
        if (!hasFiles(event)) {
          return;
        }
        event.preventDefault();
        dragDepth.current = 0;
        setDragging(false);
        attachFiles(Array.from(event.dataTransfer.files));
      }}
    >
      {dragging ? <p className="composer__drop-hint">Drop to attach</p> : null}
      <ComposerBody {...props} onFiles={attachFiles} />
    </ComposerPrimitive.Root>
  );
}
