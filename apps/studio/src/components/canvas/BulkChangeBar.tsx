import { useState } from "react";

import { JOB_STAGES } from "../../domain/jobStages";
import type { Theme } from "../../types";

/** The change being drafted: what a run would write, before anybody has counted it. */
export interface BulkDraft {
  stage?: string;
  addThemeIds: string[];
  removeThemeIds: string[];
  addTags: string[];
}

function without(values: string[], value: string): string[] {
  return values.filter((entry) => entry !== value);
}

interface BulkChangeBarProps {
  selectedCount: number;
  /** What the current narrowing counted, so the wider action can name its number. */
  matchingTotal: number;
  themes: Theme[];
  draft: BulkDraft;
  busy: boolean;
  onClear: () => void;
  onDraftChange: (next: BulkDraft) => void;
  onPreviewSelected: () => void;
  onPreviewAll: () => void;
}

/**
 * The drafted change and the two ways to run it. The checked rows are the run;
 * widening is its own named action carrying the store's own count, so pressing a
 * button never quietly writes more rows than the line above it described.
 *
 * Nothing here decides whether a run is legal. An empty drafted change still gets
 * previewed, because the sentence explaining the refusal is the service's to write.
 */
export function BulkChangeBar({
  selectedCount,
  matchingTotal,
  themes,
  draft,
  busy,
  onClear,
  onDraftChange,
  onPreviewSelected,
  onPreviewAll,
}: BulkChangeBarProps) {
  const [tag, setTag] = useState("");

  function pickTheme(themeId: string, adding: boolean) {
    if (!themeId) {
      return;
    }
    // One theme cannot be both added and removed, so the later pick wins and the
    // earlier one leaves the draft rather than reaching the service as a refusal.
    const next: BulkDraft = adding
      ? {
          ...draft,
          addThemeIds: [...without(draft.addThemeIds, themeId), themeId],
          removeThemeIds: without(draft.removeThemeIds, themeId),
        }
      : {
          ...draft,
          removeThemeIds: [...without(draft.removeThemeIds, themeId), themeId],
          addThemeIds: without(draft.addThemeIds, themeId),
        };
    onDraftChange(next);
  }

  function addTag() {
    const value = tag.trim();
    if (!value) {
      return;
    }
    onDraftChange({ ...draft, addTags: [...without(draft.addTags, value), value] });
    setTag("");
  }

  const themeName = (themeId: string) => themes.find((theme) => theme.id === themeId)?.name ?? themeId;

  return (
    <section className="studio-bulk-bar" role="region" aria-label="Bulk change">
      <p className="studio-bulk-bar__count" role="status">
        {selectedCount} selected
      </p>

      <label className="studio-bulk-bar__field" htmlFor="bulk-stage">
        Move to stage
        <select
          id="bulk-stage"
          className="studio-input"
          value={draft.stage ?? ""}
          onChange={(event) =>
            onDraftChange({ ...draft, stage: event.target.value || undefined })
          }
        >
          <option value="">Leave it alone</option>
          {JOB_STAGES.map((stage) => (
            <option key={stage.id} value={stage.id}>
              {stage.name.replace(/^\d+\.\s*/, "")}
            </option>
          ))}
        </select>
      </label>

      <label className="studio-bulk-bar__field" htmlFor="bulk-add-theme">
        Theme to add
        <select
          id="bulk-add-theme"
          className="studio-input"
          value={draft.addThemeIds[draft.addThemeIds.length - 1] ?? ""}
          onChange={(event) => pickTheme(event.target.value, true)}
        >
          <option value="">Choose a theme…</option>
          {themes.map((theme) => (
            <option key={theme.id} value={theme.id}>
              {theme.name}
            </option>
          ))}
        </select>
      </label>

      <label className="studio-bulk-bar__field" htmlFor="bulk-remove-theme">
        Theme to remove
        <select
          id="bulk-remove-theme"
          className="studio-input"
          value={draft.removeThemeIds[draft.removeThemeIds.length - 1] ?? ""}
          onChange={(event) => pickTheme(event.target.value, false)}
        >
          <option value="">Choose a theme…</option>
          {themes.map((theme) => (
            <option key={theme.id} value={theme.id}>
              {theme.name}
            </option>
          ))}
        </select>
      </label>

      <div className="studio-bulk-bar__field">
        <label htmlFor="bulk-tag">Tag to add</label>
        <div style={{ display: "flex", gap: 6 }}>
          <input
            id="bulk-tag"
            className="studio-input"
            value={tag}
            onChange={(event) => setTag(event.target.value)}
            placeholder="e.g. q3-review"
          />
          <button type="button" className="quiet-action" disabled={!tag.trim()} onClick={addTag}>
            Add tag
          </button>
        </div>
      </div>

      {draft.addThemeIds.length || draft.removeThemeIds.length || draft.addTags.length ? (
        <ul className="studio-bulk-bar__pills" aria-label="Drafted change">
          {draft.addThemeIds.map((themeId) => (
            <li key={`add:${themeId}`}>
              <span className="studio-pill">+ {themeName(themeId)}</span>
              <button
                type="button"
                className="quiet-action"
                aria-label={`Stop adding ${themeName(themeId)}`}
                onClick={() => onDraftChange({ ...draft, addThemeIds: without(draft.addThemeIds, themeId) })}
              >
                ✕
              </button>
            </li>
          ))}
          {draft.removeThemeIds.map((themeId) => (
            <li key={`remove:${themeId}`}>
              <span className="studio-pill">− {themeName(themeId)}</span>
              <button
                type="button"
                className="quiet-action"
                aria-label={`Stop removing ${themeName(themeId)}`}
                onClick={() =>
                  onDraftChange({ ...draft, removeThemeIds: without(draft.removeThemeIds, themeId) })
                }
              >
                ✕
              </button>
            </li>
          ))}
          {draft.addTags.map((value) => (
            <li key={`tag:${value}`}>
              <span className="studio-pill">#{value}</span>
              <button
                type="button"
                className="quiet-action"
                aria-label={`Stop adding the tag ${value}`}
                onClick={() => onDraftChange({ ...draft, addTags: without(draft.addTags, value) })}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="studio-bulk-bar__actions">
        <button
          type="button"
          className="studio-button studio-button--primary"
          disabled={busy}
          onClick={onPreviewSelected}
        >
          Preview {selectedCount} selected
        </button>
        {matchingTotal > selectedCount ? (
          <button
            type="button"
            className="studio-button"
            disabled={busy}
            onClick={onPreviewAll}
          >
            Preview all {matchingTotal} matching
          </button>
        ) : null}
        <button type="button" className="quiet-action" onClick={onClear}>
          Clear selection
        </button>
      </div>
    </section>
  );
}
