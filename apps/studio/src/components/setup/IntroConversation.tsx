import { useEffect, useRef, useState } from "react";

import { HELP_TEXT, type StudioCommand } from "../../lib/commands";
import {
  INTRO_TURNS,
  SUMMARY_INDEX,
  briefFromAnswers,
  clearIntroDraft,
  deriveTeam,
  draftFromBrief,
  hasIntroAnswers,
  introReflection,
  isExploreReply,
  isSkipReply,
  loadIntroDraft,
  migrateLegacyDraft,
  proposeDefaults,
  saveIntroDraft,
  parseIntroReply,
  type IntroAnswers,
  type IntroDraft,
  type IntroField,
} from "../../lib/intro";
import { isSavePhrase } from "../../lib/setup";
import { useStudio } from "../../state/StudioContext";
import type { StudioBrief, WorkspacePanelId } from "../../types";
import { Composer } from "../chat/Composer";
import { Markdown } from "../chat/Markdown";
import { SparkIcon } from "../icons";

const PANEL_COMMANDS = new Set<string>([
  "landscape",
  "jobmap",
  "evidence",
  "capture",
  "settings",
]);

const QUESTION_REPLY =
  /^(what|who|why|how|when|where|which|can|could|should|would|do|does|is|are|tell me)\b[\s\S]*\?$/i;

type TurnState = { kind: "question"; index: number } | { kind: "summary" };

const SUMMARY_ROWS: Array<{ field: IntroField; label: string }> = [
  { field: "role", label: "You" },
  { field: "customer", label: "Customer" },
  { field: "win", label: "Win" },
  { field: "friction", label: "Friction" },
  { field: "evidence", label: "Evidence" },
];

function phaseOf(draft: IntroDraft): TurnState {
  return draft.turn >= SUMMARY_INDEX
    ? { kind: "summary" }
    : { kind: "question", index: draft.turn };
}

export interface IntroSummaryProps {
  answers: IntroAnswers;
  team?: string;
  note?: string;
  editing: IntroField | null;
  editValue: string;
  busy?: boolean;
  onBeginEdit: (field: IntroField) => void;
  onEditChange: (value: string) => void;
  onCommit: () => void;
  onCancel: () => void;
  onAccept: () => void;
  onSkip: () => void;
}

/**
 * The five lines as a document, not a summary.
 *
 * Each row is a button that becomes an input in place: Enter saves, Escape
 * cancels. The card is presentational so a visual test can render one state
 * without a studio around it.
 */
export function IntroSummary({
  answers,
  team,
  note,
  editing,
  editValue,
  busy = false,
  onBeginEdit,
  onEditChange,
  onCommit,
  onCancel,
  onAccept,
  onSkip,
}: IntroSummaryProps) {
  return (
    <div className="intro__summary" aria-label="Your brief">
      <h2 className="intro__heading">Does this look like you?</h2>
      <ul className="intro__rows">
        {SUMMARY_ROWS.map((row) => {
          const value = answers[row.field]?.trim() ?? "";
          const isEditing = editing === row.field;
          return (
            <li className="intro__row" key={row.field}>
              <span className="intro__label">{row.label}</span>
              {isEditing ? (
                <input
                  className="intro__input"
                  aria-label={`${row.label} answer`}
                  value={editValue}
                  autoFocus
                  onChange={(event) => onEditChange(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      onCommit();
                    }
                    if (event.key === "Escape") {
                      event.preventDefault();
                      event.stopPropagation();
                      onCancel();
                    }
                  }}
                />
              ) : (
                <button
                  type="button"
                  className={`intro__value${value ? "" : " intro__value--empty"}`}
                  aria-label={`Edit ${row.label.toLowerCase()}`}
                  onClick={() => onBeginEdit(row.field)}
                >
                  {value || "Not answered — add it"}
                </button>
              )}
              {row.field === "role" && team ? (
                <span className="intro__team">Team: {team}</span>
              ) : null}
            </li>
          );
        })}
      </ul>
      {note ? <p className="intro__note">Kept from your earlier setup: {note}</p> : null}
      <div className="intro__actions">
        <button type="button" className="intro__accept" onClick={onAccept} disabled={busy}>
          Looks like me
        </button>
        <button type="button" className="intro__skip" onClick={onSkip} disabled={busy}>
          Skip the rest
        </button>
      </div>
    </div>
  );
}

function AssistantTurn({ content }: { content: string }) {
  return (
    <article className="message message--assistant">
      <span className="message__avatar" aria-hidden="true">
        <SparkIcon size={15} />
      </span>
      <div className="message__body">
        <Markdown source={content} />
      </div>
    </article>
  );
}

/**
 * The first-run introduction.
 *
 * The agent speaks first and asks one question at a time, in the order a
 * colleague would: the person, the customer, the win, the friction, and what
 * they already have. Every turn is skippable, the answers are kept as a draft,
 * and the five of them become an editable brief. Nothing here needs a model or
 * the sidecar, and nothing covers the composer.
 */
export function IntroConversation() {
  const {
    brief,
    canvas,
    saveBrief,
    createJob,
    updateJob,
    clearChat,
    closeSetup,
    openPanel,
    pushNotice,
    pushToast,
    sendMessage,
    llmHealth,
  } = useStudio();

  const editing = Boolean(brief);
  const [draft, setDraft] = useState<IntroDraft>(() => {
    if (brief) {
      return draftFromBrief(brief);
    }
    migrateLegacyDraft();
    return loadIntroDraft();
  });
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [editingRow, setEditingRow] = useState<IntroField | null>(null);
  const [rowValue, setRowValue] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const phase = phaseOf(draft);
  const current = phase.kind === "question" ? INTRO_TURNS[phase.index] : null;
  const team = deriveTeam(draft.answers.role);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) {
      element.scrollTop = element.scrollHeight;
    }
  }, [draft.turn, editingRow, notice]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") {
        return;
      }
      // Escape inside a summary row cancels the edit; anywhere else it leaves
      // the introduction without saving the brief.
      if (editingRow) {
        setEditingRow(null);
        return;
      }
      closeSetup();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [closeSetup, editingRow]);

  function applyDraft(next: IntroDraft) {
    setDraft(next);
    if (!editing) {
      saveIntroDraft(next);
    }
  }

  function advance(answer?: { field: IntroField; value: string; quote: string }) {
    const nextTurn = Math.min(draft.turn + 1, SUMMARY_INDEX);
    applyDraft(
      answer
        ? {
            ...draft,
            turn: nextTurn,
            answers: { ...draft.answers, [answer.field]: answer.value },
            quotes: { ...draft.quotes, [answer.field]: answer.quote },
          }
        : { ...draft, turn: nextTurn },
    );
    setNotice(null);
  }

  function skip() {
    if (busy || phase.kind !== "question") {
      return;
    }
    advance();
  }

  function submit(value: string) {
    const text = value.trim();
    if (!text || busy) {
      return;
    }

    if (phase.kind === "summary") {
      if (isSavePhrase(text)) {
        void finish();
        return;
      }
      // Anything else belongs in the conversation, not in the summary.
      closeSetup();
      void sendMessage(text);
      return;
    }

    if (!current) {
      return;
    }
    if (isExploreReply(text)) {
      closeSetup();
      return;
    }
    if (isSkipReply(text)) {
      skip();
      return;
    }
    // A question is a turn in the conversation, not an answer that would make
    // the brief wrong. Narrow on purpose: an answer is never rejected.
    if (QUESTION_REPLY.test(text)) {
      closeSetup();
      void sendMessage(text);
      return;
    }

    advance(parseIntroReply(current.id, text));
  }

  function questionContent(index: number): string {
    const turn = INTRO_TURNS[index];
    const previous = index > 0 ? INTRO_TURNS[index - 1] : null;
    const lead = previous
      ? draft.answers[previous.id]
        ? introReflection(previous.id)
        : "No problem — we can come back to that."
      : "";
    const defaults = proposeDefaults(draft.answers);
    const proposals: string[] = [];
    if (turn.id === "win" && defaults.customerLabel) {
      proposals.push(`I'll call them **${defaults.customerLabel}** — say if that's wrong.`);
    }
    if (turn.id === "friction" && defaults.jobStatement) {
      proposals.push(`The job, as I hear it: **${defaults.jobStatement}**.`);
    }
    if (turn.id === "evidence" && defaults.outcomeDraft) {
      proposals.push(
        `One outcome worth measuring: “${defaults.outcomeDraft}” — a guess, not your answer.`,
      );
    }
    return [lead, `**${turn.question}**`, ...proposals].filter(Boolean).join("\n\n");
  }

  function beginRow(field: IntroField) {
    setEditingRow(field);
    setRowValue(draft.answers[field] ?? "");
  }

  function commitRow() {
    if (!editingRow) {
      return;
    }
    const field = editingRow;
    const text = rowValue.trim();
    const answers = { ...draft.answers };
    const quotes = { ...draft.quotes };
    if (text) {
      const parsed = parseIntroReply(field, text);
      answers[field] = parsed.value;
      quotes[field] = parsed.quote;
    } else {
      delete answers[field];
      delete quotes[field];
    }
    applyDraft({ ...draft, answers, quotes });
    setEditingRow(null);
  }

  async function finish() {
    if (busy) {
      return;
    }
    if (!hasIntroAnswers(draft.answers)) {
      closeSetup();
      return;
    }
    setBusy(true);

    const fields = briefFromAnswers(draft.answers);
    const context: StudioBrief = {
      product_name: fields.product_name,
      product_url: brief?.product_url,
      target_user: fields.target_user,
      job_statement: fields.job_statement,
      core_problem: fields.core_problem,
      role: fields.role,
      team: fields.team,
      evidence_at_hand: fields.evidence_at_hand,
      v2mom: draft.note ? { ...brief?.v2mom, vision: draft.note } : brief?.v2mom,
    };
    const jobName = context.job_statement || context.product_name;
    const description = [context.target_user, context.core_problem]
      .filter(Boolean)
      .join(" — ");
    let jobId = brief?.job_id ?? canvas?.jobs.find((job) => job.name === jobName)?.id ?? null;
    if (jobName && jobId) {
      // A job write that fails must not cost the person their context: the
      // brief is saved either way.
      try {
        await updateJob(jobId, { name: jobName, description: description || undefined });
      } catch {
        /* keep the existing job id */
      }
    } else if (jobName) {
      try {
        jobId = await createJob({ name: jobName, description: description || undefined });
      } catch {
        jobId = null;
      }
    } else {
      jobId = null;
    }

    saveBrief({ ...context, job_id: jobId ?? undefined });
    clearIntroDraft();
    if (!editing) {
      clearChat();
    }
    pushToast(
      "success",
      editing
        ? "Context updated — I will use it from here."
        : "Context saved. Every reply now starts from what you told me.",
    );
  }

  function handleCommand(command: StudioCommand) {
    if (PANEL_COMMANDS.has(command.id)) {
      openPanel(command.id as WorkspacePanelId);
      return;
    }
    if (command.id === "impact") {
      closeSetup();
      void sendMessage(
        "Simulate the impact of a bet on my most underserved opportunity. " +
          "Ask me what the bet is, then show me what changes before and after.",
      );
      return;
    }
    if (command.id === "help") {
      setNotice(HELP_TEXT);
      return;
    }
    if (command.id === "new" || command.id === "home") {
      closeSetup();
      return;
    }
    if (command.id === "status") {
      pushNotice(
        "**Studio status** — the introduction works without a model or the sidecar; finish it and the conversation carries on.",
      );
    }
  }

  const progress = editing
    ? "Your context"
    : phase.kind === "question"
      ? `${phase.index + 1} of ${INTRO_TURNS.length} · skip anything`
      : "Your brief";

  const placeholder =
    phase.kind === "summary"
      ? "Say “looks like me”, or change a line"
      : "In your own words…";

  const history = INTRO_TURNS.slice(0, draft.turn).flatMap((turn) => {
    const answer = draft.answers[turn.id];
    return [
      <AssistantTurn content={`**${turn.question}**`} key={`${turn.id}-question`} />,
      <article className="message message--user" key={`${turn.id}-answer`}>
        <div className="message__bubble">{answer || "Skipped"}</div>
      </article>,
    ];
  });

  return (
    <section className="chat chat--setup" aria-label="Studio introduction">
      <div className="setup__meta">
        <span>
          {progress}
          {llmHealth.healthy === false ? " · model offline, the introduction still works" : ""}
        </span>
        <button type="button" className="quiet-action" onClick={closeSetup}>
          {editing ? "Back to conversation" : "Explore on my own"}
        </button>
      </div>
      <div ref={scrollRef} className="chat__scroll">
        <div className="chat__thread setup">
          <div className="setup__turns" role="log" aria-live="polite">
            {history}
            {current ? <AssistantTurn content={questionContent(draft.turn)} /> : null}
            {notice ? <AssistantTurn content={notice} /> : null}
          </div>

          {current ? (
            <div className="setup__replies" aria-label="Question options">
              <button
                type="button"
                className="suggestion suggestion--quiet"
                onClick={skip}
                disabled={busy}
              >
                Skip this question
              </button>
            </div>
          ) : (
            <IntroSummary
              answers={draft.answers}
              team={team}
              note={draft.note}
              editing={editingRow}
              editValue={rowValue}
              busy={busy}
              onBeginEdit={beginRow}
              onEditChange={setRowValue}
              onCommit={commitRow}
              onCancel={() => setEditingRow(null)}
              onAccept={() => void finish()}
              onSkip={() => void finish()}
            />
          )}
        </div>
      </div>

      <div className="chat__dock">
        <Composer
          value={input}
          onChange={setInput}
          onSubmit={() => {
            const value = input;
            setInput("");
            submit(value);
          }}
          onCommand={handleCommand}
          streaming={false}
          onStop={() => undefined}
          inputRef={inputRef}
          autoFocus
          placeholder={placeholder}
        />
        {current ? (
          <p className="intro__examples">
            Examples, not your answers: “{current.examples[0]}” · “{current.examples[1]}”
          </p>
        ) : null}
      </div>
    </section>
  );
}
