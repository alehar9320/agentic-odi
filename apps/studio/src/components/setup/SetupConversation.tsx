import { useEffect, useRef, useState } from "react";

import { HELP_TEXT, type StudioCommand } from "../../lib/commands";
import {
  QUESTION_COUNT,
  REVIEW_INDEX,
  SETUP_QUESTIONS,
  draftFromBrief,
  draftHasContent,
  emptyDraft,
  fieldFromText,
  firstUnanswered,
  isSavePhrase,
  parseSetupIntent,
  questionContent,
  reflectionFor,
  reviewContent,
  type BriefField,
  type SetupDraft,
} from "../../lib/setup";
import { useStudio } from "../../state/StudioContext";
import type { WorkspacePanelId } from "../../types";
import { Composer } from "../chat/Composer";
import { Markdown } from "../chat/Markdown";
import { SparkIcon } from "../icons";

const DRAFT_KEY = "studio.setupDraft";
const STEP_KEY = "studio.setupStep";

type Phase =
  | { kind: "question"; index: number }
  | { kind: "field"; field: BriefField }
  | { kind: "review" };

interface Turn {
  role: "assistant" | "user";
  content: string;
}

const PANEL_COMMANDS = new Set<string>([
  "landscape",
  "jobmap",
  "impact",
  "evidence",
  "capture",
  "settings",
]);

function loadDraft(): SetupDraft {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<SetupDraft>;
      return {
        product_name: String(parsed.product_name ?? ""),
        target_user: String(parsed.target_user ?? ""),
        job_statement: String(parsed.job_statement ?? ""),
        core_problem: String(parsed.core_problem ?? ""),
      };
    }
  } catch {
    /* malformed draft */
  }
  return emptyDraft();
}

function clearDraft(): void {
  try {
    localStorage.removeItem(DRAFT_KEY);
    localStorage.removeItem(STEP_KEY);
  } catch {
    /* storage unavailable */
  }
}

function loadStep(): number | null {
  try {
    const raw = localStorage.getItem(STEP_KEY);
    if (raw === null) {
      return null;
    }
    const step = Number(raw);
    return Number.isInteger(step) ? step : null;
  } catch {
    return null;
  }
}

function saveStep(step: number): void {
  try {
    localStorage.setItem(STEP_KEY, String(step));
  } catch {
    /* storage unavailable */
  }
}

function saveDraft(draft: SetupDraft): void {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch {
    /* storage unavailable */
  }
}

function questionIndex(field: BriefField): number {
  return SETUP_QUESTIONS.findIndex((question) => question.field === field);
}

/**
 * The getting-started experience as a conversation, not a gate.
 *
 * It borrows what works from good onboarding: one question at a time, a
 * reflection before the next ask, quick replies for people who do not want to
 * type, visible progress, and an exit that is always available. Nothing is
 * required, and answers are kept as a draft so leaving and coming back is safe.
 */
export function SetupConversation() {
  const {
    brief,
    canvas,
    saveBrief,
    createJob,
    updateJob,
    clearChat,
    closeSetup,
    openPanel,
    pushToast,
    llmHealth,
  } = useStudio();

  const editing = Boolean(brief);
  const [draft, setDraft] = useState<SetupDraft>(() =>
    editing ? draftFromBrief(brief) : loadDraft(),
  );
  const [phase, setPhase] = useState<Phase>(() => {
    if (editing) {
      return { kind: "review" };
    }
    const saved = loadStep();
    const index =
      saved !== null && saved >= 0 && saved <= REVIEW_INDEX ? saved : firstUnanswered(draft);
    return index === REVIEW_INDEX ? { kind: "review" } : { kind: "question", index };
  });
  const [turns, setTurns] = useState<Turn[]>(() => {
    const resumed = draftHasContent(draft);
    // A field edit can only start after mount, so this covers review and the
    // impossible-on-first-render field phase alike.
    if (phase.kind !== "question") {
      const intro = editing
        ? "Here is what I hold."
        : resumed
          ? "Welcome back — here is where we left off."
          : "Nothing yet — that is completely fine.";
      return [
        {
          role: "assistant",
          content: `${intro}\n\n${reviewContent(draft)}${
            editing
              ? "\n\nWhat changed? Pick a line, or leave it as it is."
              : "\n\nSay “looks right”, or pick a line to change."
          }`,
        },
      ];
    }
    const intro = resumed
      ? "Welcome back — let's pick up where we left off."
      : "Let's make this yours. Four quick questions — answer in your own words, or skip anything. You can explore on your own at any point.";
    return [{ role: "assistant", content: `${intro}\n\n${questionContent(phase.index, draft)}` }];
  });
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const currentQuestion =
    phase.kind === "question" ? SETUP_QUESTIONS[phase.index] : null;

  useEffect(() => {
    const element = scrollRef.current;
    if (element) {
      element.scrollTop = element.scrollHeight;
    }
  }, [turns, phase]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeSetup();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [closeSetup]);

  function applyDraft(next: SetupDraft) {
    setDraft(next);
    if (!editing) {
      saveDraft(next);
    }
  }

  function append(role: Turn["role"], content: string) {
    setTurns((prev) => [...prev, { role, content }]);
  }

  function ask(index: number, current: SetupDraft, lead?: string) {
    setPhase({ kind: "question", index });
    saveStep(index);
    append("assistant", questionContent(index, current, lead));
  }

  function showReview(current: SetupDraft, lead?: string) {
    setPhase({ kind: "review" });
    saveStep(REVIEW_INDEX);
    append("assistant", [lead, reviewContent(current)].filter(Boolean).join("\n\n"));
  }

  function answer(value: string) {
    const text = value.trim();
    if (!text || busy) {
      return;
    }

    // People answer questions in many ways. Read skip/explore/navigation
    // intent before treating free text as an answer, so nothing gets swallowed.
    const intent = parseSetupIntent(text);
    if (intent) {
      if (intent.kind === "skip") {
        if (phase.kind === "review") {
          closeSetup();
        } else {
          skip();
        }
        return;
      }
      if (intent.kind === "explore") {
        closeSetup();
        return;
      }
      openPanel(intent.panel);
      return;
    }

    if (phase.kind === "question") {
      const question = SETUP_QUESTIONS[phase.index];
      const next = { ...draft, [question.field]: text };
      applyDraft(next);
      append("user", text);
      const lead = reflectionFor(question.field, text);
      if (phase.index + 1 < QUESTION_COUNT) {
        ask(phase.index + 1, next, lead);
      } else {
        showReview(next, lead);
      }
      return;
    }

    if (phase.kind === "field") {
      const next = { ...draft, [phase.field]: text };
      applyDraft(next);
      append("user", text);
      showReview(next, "Updated — here is what I hold now.");
      return;
    }

    if (isSavePhrase(text)) {
      void finish();
      return;
    }
    const field = fieldFromText(text);
    if (field) {
      beginField(field);
      return;
    }
    append("user", text);
    append(
      "assistant",
      "I can change any line above — pick one of the buttons, or say “looks right” and I will save it.",
    );
  }

  function skip() {
    if (busy) {
      return;
    }
    if (phase.kind === "question") {
      append("user", "Skip");
      if (phase.index + 1 < QUESTION_COUNT) {
        ask(phase.index + 1, draft, "No problem — we can come back to that.");
      } else {
        showReview(draft, "No problem — we can come back to that.");
      }
      return;
    }
    if (phase.kind === "field") {
      append("user", "Skip");
      showReview(draft, "Left as it was.");
    }
  }

  function beginField(field: BriefField) {
    saveStep(REVIEW_INDEX);
    setPhase({ kind: "field", field });
    const current = draft[field].trim();
    append(
      "assistant",
      `${questionContent(questionIndex(field), draft)}${
        current ? "\n\nSay “keep it” to leave it unchanged." : ""
      }`,
    );
  }

  function keepCurrent() {
    if (phase.kind !== "field") {
      return;
    }
    append("user", "Keep it");
    showReview(draft, "Left as it was.");
  }

  async function finish() {
    if (busy) {
      return;
    }
    if (!draftHasContent(draft)) {
      closeSetup();
      return;
    }
    setBusy(true);
    const context = {
      product_name: draft.product_name.trim(),
      product_url: brief?.product_url,
      target_user: draft.target_user.trim(),
      job_statement: draft.job_statement.trim(),
      core_problem: draft.core_problem.trim(),
    };
    const jobName = context.job_statement || context.product_name;
    const description = [context.target_user, context.core_problem].filter(Boolean).join(" — ");
    let jobId = brief?.job_id ?? canvas?.jobs.find((job) => job.name === jobName)?.id ?? null;
    if (jobName) {
      if (jobId) {
        await updateJob(jobId, { name: jobName, description: description || undefined });
      } else {
        jobId = await createJob({ name: jobName, description: description || undefined });
      }
    } else {
      jobId = null;
    }
    saveBrief({ ...context, job_id: jobId ?? undefined });
    clearDraft();
    if (!editing) {
      clearChat();
    }
    pushToast(
      "success",
      editing
        ? "Context updated — I will use it from here."
        : "Context saved. Every reply now starts from your job.",
    );
  }

  function handleCommand(command: StudioCommand) {
    if (PANEL_COMMANDS.has(command.id)) {
      openPanel(command.id as WorkspacePanelId);
      return;
    }
    if (command.id === "help") {
      append("assistant", HELP_TEXT);
      return;
    }
    if (command.id === "new" || command.id === "home") {
      closeSetup();
    }
  }

  const replies: Array<{ label: string; run: () => void; primary?: boolean; quiet?: boolean }> = [];
  if (currentQuestion) {
    for (const reply of currentQuestion.quickReplies ?? []) {
      replies.push({ label: reply, run: () => answer(reply) });
    }
    replies.push({ label: "Skip", run: skip, quiet: true });
  }
  if (phase.kind === "field") {
    if (draft[phase.field].trim()) {
      replies.push({ label: "Keep it", run: keepCurrent });
    }
    replies.push({ label: "Skip", run: skip, quiet: true });
  }
  if (phase.kind === "review") {
    const hasContext = draftHasContent(draft);
    replies.push({
      label: hasContext
        ? editing
          ? "Save context"
          : "Looks right — let's go"
        : "Start exploring",
      run: () => {
        if (hasContext) {
          void finish();
        } else {
          closeSetup();
        }
      },
      primary: hasContext,
    });
    for (const question of SETUP_QUESTIONS) {
      replies.push({
        label: `Change ${question.label.toLowerCase()}`,
        run: () => beginField(question.field),
      });
    }
  }

  const progress = editing
    ? "Your context"
    : phase.kind === "question"
      ? `${phase.index + 1} of ${QUESTION_COUNT} · skip anything`
      : "Ready when you are";

  const placeholder = currentQuestion?.placeholder
    ? currentQuestion.placeholder
    : phase.kind === "field"
      ? "Say it differently…"
      : "Pick a change, or say “looks right”";

  return (
    <section className="chat chat--setup" aria-label="Studio setup conversation">
      <div className="setup__meta">
        <span>
          {progress}
          {llmHealth.healthy === false ? " · model offline, setup still works" : ""}
        </span>
        <button type="button" className="quiet-action" onClick={closeSetup}>
          {editing ? "Back to conversation" : "Explore on my own"}
        </button>
      </div>
      <div ref={scrollRef} className="chat__scroll">
        <div className="chat__thread setup">
          <div className="setup__turns" role="log" aria-live="polite">
            {turns.map((turn, index) =>
              turn.role === "user" ? (
                <article className="message message--user" key={index}>
                  <div className="message__bubble">{turn.content}</div>
                </article>
              ) : (
                <article className="message message--assistant" key={index}>
                  <span className="message__avatar" aria-hidden="true">
                    <SparkIcon size={15} />
                  </span>
                  <div className="message__body">
                    <Markdown source={turn.content} />
                  </div>
                </article>
              ),
            )}
          </div>

          {replies.length > 0 && (
            <div className="setup__replies" aria-label="Suggested answers">
              {replies.map((reply) => (
                <button
                  key={reply.label}
                  type="button"
                  className={`suggestion${reply.primary ? " suggestion--primary" : ""}${
                    reply.quiet ? " suggestion--quiet" : ""
                  }`}
                  onClick={reply.run}
                >
                  {reply.label}
                </button>
              ))}
            </div>
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
            answer(value);
          }}
          onCommand={handleCommand}
          streaming={false}
          onStop={() => undefined}
          inputRef={inputRef}
          autoFocus
          placeholder={placeholder}
        />
      </div>
    </section>
  );
}
