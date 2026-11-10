import { useEffect, useRef, useState, type HTMLInputTypeAttribute, type ReactNode } from "react";

import type { FieldSaveStatus } from "./saves";

/**
 * A text field that saves when it is left, and says what happened.
 *
 * Settings holds live configuration, so a value typed here takes effect the
 * moment the person leaves the field — there is no Save button to reach and no
 * way for one section's edit to discard another's. A value the studio cannot
 * use is refused before it is written: the field shows why, and the last good
 * value stays in effect because nothing was sent.
 */
interface SavedFieldProps {
  id: string;
  label: ReactNode;
  value: string;
  /** Returns a reason to refuse the value, or null to accept it. */
  validate: (value: string) => string | null;
  /** Called once, with a valid and changed value, when the field is left. */
  onCommit: (value: string) => void;
  onStatusChange?: (status: FieldSaveStatus) => void;
  type?: HTMLInputTypeAttribute;
  spellCheck?: boolean;
  autoComplete?: string;
  placeholder?: string;
  list?: string;
  /** A control shown beside the input, such as the API key's Show/Hide. */
  trailing?: ReactNode;
  /** Content shown below the input, such as the model catalog suggestions. */
  after?: ReactNode;
}

export function SavedField({
  id,
  label,
  value,
  validate,
  onCommit,
  onStatusChange,
  type,
  spellCheck,
  autoComplete,
  placeholder,
  list,
  trailing,
  after,
}: SavedFieldProps) {
  const [draft, setDraft] = useState(value);
  const [status, setStatus] = useState<FieldSaveStatus>({ kind: "idle" });
  const focused = useRef(false);

  // A value can change from outside the field (a default arrives, or the theme
  // writes the same config object). Adopt it only while the person is not
  // typing, so a refused draft they are still fixing is never clobbered.
  useEffect(() => {
    if (!focused.current) {
      setDraft(value);
    }
  }, [value]);

  function report(next: FieldSaveStatus) {
    setStatus(next);
    onStatusChange?.(next);
  }

  function handleBlur() {
    focused.current = false;
    if (draft === value) {
      // Nothing changed, so nothing is sent and no "Saved" is claimed.
      report({ kind: "idle" });
      return;
    }
    const reason = validate(draft);
    if (reason) {
      report({ kind: "error", reason });
      return;
    }
    onCommit(draft);
    report({ kind: "saved" });
  }

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className={trailing ? "field__row" : undefined}>
        <input
          id={id}
          className="input"
          type={type}
          value={draft}
          spellCheck={spellCheck}
          autoComplete={autoComplete}
          placeholder={placeholder}
          list={list}
          onChange={(event) => setDraft(event.target.value)}
          onFocus={() => {
            focused.current = true;
          }}
          onBlur={handleBlur}
        />
        {trailing}
      </div>
      {after}
      {status.kind === "error" ? (
        <p className="field__save" role="alert">
          {`Not saved — ${status.reason}`}
        </p>
      ) : null}
    </div>
  );
}

/**
 * The one line a section shows after its fields have been left: "Saved" when the
 * section's edits landed. A field that was refused states why beside itself, so
 * the section does not repeat it — and `summarizeSaves` keeps the section from
 * claiming "Saved" while any field is still refused.
 */
export function SectionSaveLine({ status }: { status: FieldSaveStatus }) {
  if (status.kind !== "saved") {
    return null;
  }
  return (
    <p className="settings__save" role="status">
      Saved
    </p>
  );
}
