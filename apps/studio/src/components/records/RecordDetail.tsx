import { useEffect, useRef, useState } from "react";

import { RECORD_SECTIONS, score, text, type RecordKind, type RecordRow } from "../../lib/records";
import { useStudio } from "../../state/StudioContext";

/**
 * The fields each kind actually stores, in the order the detail shows them.
 *
 * Taken from `types.ts`, not invented here, and deliberately closed: a field that is not in
 * this list is not shown, however plausible it would look. `Outcome.telemetry` is excluded on
 * purpose — it is an opaque client string with no defined shape, so rendering it would invite
 * a reading of something that cannot be read.
 */
const DETAIL_FIELDS: Record<RecordKind, string[]> = {
  job: ["id", "name", "description"],
  step: ["id", "job_id", "name", "order"],
  outcome: [
    "id",
    "job_id",
    "statement",
    "importance",
    "satisfaction",
    "opportunity_score",
    "evidence",
  ],
  evidence: [
    "id",
    "source_name",
    "source_kind",
    "item_type",
    "name",
    "content",
    "url",
    "job_id",
    "step_id",
    "outcome_id",
  ],
};

/** The ids on a record that point at another record. */
const PARENT_FIELDS = ["job_id", "step_id", "outcome_id"] as const;

const NO_AUTHOR_OR_DATE = "This record stores only the fields above — no author and no timestamp.";

const OUTCOME_NOTES = [
  "An outcome stores its statement and two estimates — not who set them, or when.",
  "The score is computed from importance and satisfaction; it is not stored input.",
];

/** The two numbers a person owns. Both are integers from 1 to 10. */
const SCORE_FIELDS = ["importance", "satisfaction"] as const;

type ScoreField = (typeof SCORE_FIELDS)[number];

/** Clamp a typed value into the range the two estimates are stored in. */
function clampScore(value: number): number {
  return Math.min(10, Math.max(1, Math.round(value)));
}

/** The stored estimate, or the floor when the record does not carry one. */
function storedScore(record: Record<string, unknown>, field: ScoreField): number {
  const value = record[field];
  return typeof value === "number" && Number.isFinite(value) ? value : 1;
}

/** The message to show beneath the inputs when a save fails. */
function saveErrorMessage(error: unknown): string {
  if (error && typeof error === "object") {
    const shaped = error as { message?: unknown; suggestion?: unknown };
    const message =
      typeof shaped.message === "string" && shaped.message.length > 0
        ? shaped.message
        : "The save did not go through.";
    const suggestion =
      typeof shaped.suggestion === "string" && shaped.suggestion.length > 0
        ? ` ${shaped.suggestion}`
        : "";
    return `${message}${suggestion}`;
  }
  return "The save did not go through.";
}

interface RecordDetailProps {
  /** The row that was pressed. A record with no id still opens. */
  row: RecordRow;
  /** Every row the lens holds, so a parent can be offered only when it exists. */
  rows: RecordRow[];
  onFilter: (id: string) => void;
  onClose: () => void;
}

function labelFor(kind: RecordKind): string {
  return RECORD_SECTIONS.find((section) => section.kind === kind)?.label ?? kind;
}

/**
 * One record, in full.
 *
 * The table is six cells; this is every field the store holds for that kind, under the name
 * the store uses. What the record does not hold is said as a gap rather than filled in: no
 * author, no timestamp, and no date, name or confidence that the person did not record.
 */
export function RecordDetail({ row, rows, onFilter, onClose }: RecordDetailProps) {
  const { updateOutcome } = useStudio();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const copyTimer = useRef<number | null>(null);
  const [copied, setCopied] = useState(false);
  const label = labelFor(row.kind);
  const fields = DETAIL_FIELDS[row.kind];
  const record = row.record as Record<string, unknown>;
  const seedImportance = storedScore(record, "importance");
  const seedSatisfaction = storedScore(record, "satisfaction");
  const [draft, setDraft] = useState<Record<ScoreField, number>>({
    importance: seedImportance,
    satisfaction: seedSatisfaction,
  });
  const [editingRow, setEditingRow] = useState(row.rowKey);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Opening a different record reseeds the editor, adjusted during render rather than in
  // an effect. A save does not reseed: the record is the source of the new score, and a
  // failed save keeps what the person typed.
  if (editingRow !== row.rowKey) {
    setEditingRow(row.rowKey);
    setDraft({ importance: seedImportance, satisfaction: seedSatisfaction });
    setSaveError(null);
  }

  useEffect(() => {
    headingRef.current?.focus();
    return () => {
      if (copyTimer.current !== null) {
        window.clearTimeout(copyTimer.current);
      }
    };
  }, []);

  const currentScores: Record<ScoreField, number> = {
    importance: seedImportance,
    satisfaction: seedSatisfaction,
  };
  const dirty = SCORE_FIELDS.some((field) => draft[field] !== currentScores[field]);

  function setScore(field: ScoreField, value: number) {
    setDraft((previous) => ({ ...previous, [field]: value }));
  }

  async function saveScores() {
    const outcomeId = row.id;
    if (!outcomeId || saving) {
      return;
    }
    const importance = clampScore(draft.importance);
    const satisfaction = clampScore(draft.satisfaction);
    setSaving(true);
    setSaveError(null);
    try {
      await updateOutcome(outcomeId, { importance, satisfaction });
    } catch (error) {
      // Keep the editor open and keep what was typed: the message is the sidecar's.
      setSaveError(saveErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function copyId() {
    if (!row.id) {
      return;
    }
    try {
      await navigator.clipboard.writeText(row.id);
      setCopied(true);
      if (copyTimer.current !== null) {
        window.clearTimeout(copyTimer.current);
      }
      copyTimer.current = window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // The id is on screen either way. A clipboard that refuses is not worth a message.
    }
  }

  const parents = PARENT_FIELDS.map((field) => record[field])
    .filter((value): value is string => typeof value === "string" && value.length > 0)
    .filter((value, index, all) => all.indexOf(value) === index);

  return (
    <aside className="records__detail" aria-label={`${label} detail`}>
      <div className="records__detail-head">
        <h3 className="records__detail-heading" tabIndex={-1} ref={headingRef}>
          {label} detail
        </h3>
        <button type="button" className="quiet-action" onClick={onClose}>
          Close
        </button>
      </div>

      <dl className="records__fields">
        {fields.map((field) => (
          <div className="records__field" key={field}>
            <dt>{field}</dt>
            <dd>
              {field === "opportunity_score"
                ? `${score(record[field] as number | null | undefined)}${saving ? " recomputing" : ""}`
                : text(record[field] as string | number | null | undefined)}
            </dd>
          </div>
        ))}
      </dl>

      {row.kind === "outcome" ? (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void saveScores();
          }}
        >
          {SCORE_FIELDS.map((field) => (
            <div className="field" key={field}>
              <label htmlFor={`record-${field}`}>
                {field === "importance" ? "Importance (1–10)" : "Satisfaction (1–10)"}
              </label>
              <input
                id={`record-${field}`}
                className="input"
                type="number"
                min={1}
                max={10}
                step={1}
                value={draft[field]}
                onChange={(event) => setScore(field, event.target.valueAsNumber)}
              />
            </div>
          ))}
          <button type="submit" className="button" disabled={!dirty || saving}>
            {saving ? "Saving…" : "Save"}
          </button>
          {saveError ? (
            <p className="field__save" role="alert">
              {saveError}
            </p>
          ) : null}
        </form>
      ) : null}

      {parents.length > 0 ? (
        <p className="records__parents">
          {parents.map((parentId) => {
            const parent = rows.find((candidate) => candidate.id === parentId);
            return parent ? (
              <button
                type="button"
                className="records__parent"
                key={parentId}
                onClick={() => onFilter(parentId)}
              >
                {labelFor(parent.kind)} {parentId}
              </button>
            ) : (
              <span className="records__parent records__parent--absent" key={parentId}>
                {parentId}
              </span>
            );
          })}
        </p>
      ) : null}

      {row.id ? (
        <p className="records__copy">
          <button type="button" className="quiet-action" onClick={() => void copyId()}>
            Copy id
          </button>
          {copied ? <span className="records__copied">Copied</span> : null}
        </p>
      ) : null}

      <ul className="records__gaps">
        <li>{NO_AUTHOR_OR_DATE}</li>
        {row.kind === "outcome"
          ? OUTCOME_NOTES.map((note) => <li key={note}>{note}</li>)
          : null}
      </ul>
    </aside>
  );
}
