/**
 * The questionnaire surface: one labelled, accessible field per question.
 *
 * Presentational only. It receives a question and its answer and renders a
 * control; it never fetches, never reads the Studio store, and never decides
 * what an answer means. The interview card that owns the questions and the
 * submit path composes these fields.
 *
 * Authored locally for the interview card (#396) rather than copied from an
 * upstream registry: this environment fetched no artefact, so the file is
 * tracked as first-party in vendor.lock.json with the reasoning there, exactly
 * as the hover-card surface was.
 */

/** The three control shapes a question can take. */
export type QuestionnaireKind = "statement" | "text" | "scale";

export interface QuestionnaireFieldProps {
  id: string;
  kind: QuestionnaireKind;
  prompt: string;
  help?: string;
  min?: number;
  max?: number;
  required?: boolean;
  /** The current answer. `null` means "not answered yet". */
  value: string | number | null;
  /** The message to show under the field, or null when the field is valid. */
  error?: string | null;
  onChange: (value: string | number) => void;
}

function FieldBody({
  id,
  kind,
  min,
  max,
  value,
  labelledBy,
  describedBy,
  invalid,
  required,
  onChange,
}: {
  id: string;
  kind: QuestionnaireKind;
  min?: number;
  max?: number;
  value: string | number | null;
  labelledBy: string;
  describedBy: string | undefined;
  invalid: boolean;
  required: boolean;
  onChange: (value: string | number) => void;
}) {
  const label = {
    "aria-labelledby": labelledBy,
    "aria-describedby": describedBy,
    "aria-required": required || undefined,
  };

  if (kind === "text") {
    return (
      <textarea
        id={id}
        className="questionnaire__textarea"
        value={typeof value === "string" ? value : ""}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={invalid || undefined}
        {...label}
      />
    );
  }

  if (kind === "scale") {
    const floor = min ?? 0;
    const ceiling = max ?? 10;
    const current = typeof value === "number" ? value : floor;
    return (
      <div className="questionnaire__scale">
        <input
          id={id}
          className="questionnaire__range"
          type="range"
          min={floor}
          max={ceiling}
          step={1}
          value={current}
          onChange={(event) => onChange(Number(event.target.value))}
          aria-invalid={invalid || undefined}
          {...label}
        />
        <output className="questionnaire__scale-value" htmlFor={id}>
          {current}
        </output>
      </div>
    );
  }

  return (
    <input
      id={id}
      className="questionnaire__input"
      type="text"
      value={typeof value === "string" ? value : ""}
      onChange={(event) => onChange(event.target.value)}
      aria-invalid={invalid || undefined}
      {...label}
    />
  );
}

/**
 * One question, as a labelled group.
 *
 * The prompt is the group's label so screen readers announce it with the
 * control; `help` and the error are wired through `aria-describedby` so the
 * person hears the guidance and the reason together with the field.
 */
export function QuestionnaireField({
  id,
  kind,
  prompt,
  help,
  min,
  max,
  required = false,
  value,
  error,
  onChange,
}: QuestionnaireFieldProps) {
  const promptId = `${id}-prompt`;
  const helpId = help ? `${id}-help` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [helpId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <fieldset className="questionnaire__field">
      <legend className="questionnaire__legend" id={promptId}>
        {prompt}
      </legend>
      {help ? (
        <p className="questionnaire__help" id={helpId}>
          {help}
        </p>
      ) : null}
      <FieldBody
        id={id}
        kind={kind}
        min={min}
        max={max}
        value={value}
        labelledBy={promptId}
        describedBy={describedBy}
        invalid={Boolean(error)}
        required={required}
        onChange={onChange}
      />
      {error ? (
        <p className="questionnaire__error" id={errorId} role="alert">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}
