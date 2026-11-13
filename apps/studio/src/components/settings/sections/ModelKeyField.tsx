import { useEffect, useState } from "react";

import { asStudioError, fetchModelKeyStatus, saveModelKey, type ModelKeyStatus } from "../../../api/studioApi";

/**
 * The model key, written once and never read back.
 *
 * A key is a secret the page must not be able to read, so this control never
 * renders a stored value: it reports only whether a key is set and when, and
 * offers a replace action. The value is handed to the sidecar, which holds it
 * with owner-only permissions; the browser keeps nothing.
 */
function formatSetAt(value: string | null): string {
  if (!value) {
    return "Key set";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Key set";
  }
  return `Key set on ${date.toLocaleDateString(undefined, { day: "numeric", month: "short" })}`;
}

export function ModelKeyField() {
  const [status, setStatus] = useState<ModelKeyStatus | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchModelKeyStatus()
      .then((next) => {
        if (!cancelled) {
          setStatus(next);
          // Nothing stored yet: the field starts open so a key can be entered.
          setEditing(!next.configured);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setUnavailable(true);
          setEditing(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function commit() {
    const value = draft.trim();
    if (!value) {
      setError("Enter a key.");
      return;
    }
    setSaving(true);
    try {
      const next = await saveModelKey(value);
      setStatus(next);
      setUnavailable(false);
      setDraft("");
      setEditing(false);
      setError(null);
    } catch (caught) {
      setError(asStudioError(caught).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="field">
      <label htmlFor="api-key">API key</label>
      {editing ? (
        <div className="field__row">
          <input
            id="api-key"
            className="input"
            type="password"
            autoComplete="off"
            value={draft}
            spellCheck={false}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button
            type="button"
            className="quiet-action"
            disabled={saving}
            onClick={() => void commit()}
          >
            {saving ? "Saving…" : "Save key"}
          </button>
        </div>
      ) : (
        <p className="field__hint">
          {status?.configured ? formatSetAt(status.set_at) : "No key set"}
        </p>
      )}
      {!editing ? (
        <button type="button" className="quiet-action" onClick={() => setEditing(true)}>
          Replace key
        </button>
      ) : null}
      {unavailable ? (
        <p className="field__hint">The local service is not reachable, so no key can be stored.</p>
      ) : null}
      {error ? (
        <p className="field__save" role="alert">
          {`Not saved — ${error}`}
        </p>
      ) : null}
    </div>
  );
}
