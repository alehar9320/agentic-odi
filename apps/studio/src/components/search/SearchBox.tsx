import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";

import { dialogOpen } from "../../lib/composerFocus";
import { buildSearchIndex, flattenHits, searchAll, type OrderedHit } from "../../lib/search";
import { useFocusTrap } from "../../lib/useFocusTrap";
import { useStudio } from "../../state/StudioContext";
import type { SearchKind, WorkspacePanelId } from "../../types";
import { SearchIcon } from "../icons";

/**
 * One box over every stored artifact (#539, epic #325).
 *
 * Search used to be a filter inside one panel, invisible from the rest of the
 * room and blind to anything but statements. This is the room's own search: a
 * global overlay opened with ⌘/Ctrl+Shift+F or the bar control, running the
 * query against the records the client already holds, grouping the hits by
 * artifact, and opening the one you pick in the surface that owns it.
 *
 * ⌘/Ctrl+F is left alone: it belongs to the browser's own find.
 */

/** How long to wait after the last keystroke before running the query. */
const DEBOUNCE_MS = 250;

/**
 * Only say "Searching…" when the wait is long enough to notice. With the local
 * index the 250 ms debounce always settles first, so the note stays hidden; it
 * exists for the moment the query moves off the main thread.
 */
const SLOW_MS = 300;

/**
 * Where a record opens: the panel that owns it. Evidence and observations have
 * their own one-shot focus callbacks, so they are handled separately.
 */
const PANEL_FOR_KIND: Partial<Record<SearchKind, WorkspacePanelId>> = {
  outcome: "landscape",
  job: "jobmap",
  step: "jobmap",
};

export function SearchBox() {
  const {
    canvas,
    memory,
    searchOpen,
    openSearch,
    closeSearch,
    focusSubject,
    focusEvidence,
    focusObservation,
    openPanel,
  } = useStudio();
  const [query, setQuery] = useState("");
  const [settled, setSettled] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [slow, setSlow] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const optionRefs = useRef(new Map<number, HTMLButtonElement>());
  const listId = useId();
  const headingId = useId();

  useFocusTrap(dialogRef, searchOpen);

  // Nothing is indexed until the box is open: the shortcut that opens it is a
  // listener, not a render, so a closed box costs the app no work.
  const index = useMemo(
    () => (searchOpen ? buildSearchIndex(canvas, memory) : []),
    [searchOpen, canvas, memory],
  );
  const results = useMemo(() => searchAll(index, settled), [index, settled]);
  const hits = useMemo(() => flattenHits(results), [results]);

  // Open from anywhere. A dialog owns the keyboard while it is up, so the
  // shortcut never reaches behind the one already on screen.
  useEffect(() => {
    function onKeyDown(event: globalThis.KeyboardEvent) {
      const modifier = event.metaKey || event.ctrlKey;
      if (modifier && event.shiftKey && event.key.toLowerCase() === "f") {
        if (dialogOpen() && !searchOpen) {
          return;
        }
        event.preventDefault();
        openSearch();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [openSearch, searchOpen]);

  // Focus the input when the box appears. No state changes here: the reset
  // below happens during render, which is where React asks for it.
  useEffect(() => {
    if (searchOpen) {
      inputRef.current?.focus();
    }
  }, [searchOpen]);

  // Forget the last query the moment the box closes, so the next open starts
  // clean. Adjusting state during render is the pattern React documents for a
  // value that must reset when a prop changes.
  const [wasOpen, setWasOpen] = useState(searchOpen);
  if (wasOpen !== searchOpen) {
    setWasOpen(searchOpen);
    if (!searchOpen) {
      setQuery("");
      setSettled("");
      setSlow(false);
      setActiveIndex(0);
    }
  }

  // Debounce the keystroke, then run the query. The "Searching…" note waits
  // past SLOW_MS so a fast local search never flashes it. Every state change
  // happens inside a timer callback, never in the effect body.
  useEffect(() => {
    const slowTimer = window.setTimeout(() => setSlow(true), SLOW_MS);
    const debounceTimer = window.setTimeout(() => {
      window.clearTimeout(slowTimer);
      setSettled(query.trim());
      setSlow(false);
      setActiveIndex(0);
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(slowTimer);
      window.clearTimeout(debounceTimer);
    };
  }, [query]);

  // Keep the highlighted hit in view as the arrows move through the list.
  useEffect(() => {
    const element = optionRefs.current.get(activeIndex);
    if (!element || typeof element.scrollIntoView !== "function") {
      return;
    }
    element.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  function openHit(entry: OrderedHit) {
    const { hit } = entry;
    if (hit.kind === "evidence") {
      focusEvidence(hit.id);
    } else if (hit.kind === "observation") {
      focusObservation(hit.id);
    } else {
      focusSubject(hit.kind, hit.id);
      const panel = PANEL_FOR_KIND[hit.kind];
      if (panel) {
        openPanel(panel);
      }
    }
    closeSearch();
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeSearch();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => (hits.length ? (current + 1) % hits.length : 0));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => (hits.length ? (current - 1 + hits.length) % hits.length : 0));
      return;
    }
    // Enter opens the highlighted hit, but only from the query field: on a hit
    // button the browser already fires that row's own click.
    if (event.key === "Enter" && event.target === inputRef.current && hits[activeIndex]) {
      event.preventDefault();
      openHit(hits[activeIndex]);
    }
  }

  if (!searchOpen) {
    return null;
  }

  const hasQuery = query.trim().length > 0;
  const activeOptionId = hits[activeIndex] ? `${listId}-option-${activeIndex}` : undefined;

  return (
    <div className="search-overlay">
      <button
        type="button"
        className="search-scrim"
        aria-label="Close search"
        onClick={closeSearch}
      />
      <div
        ref={dialogRef}
        className="search-box"
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        onKeyDown={onKeyDown}
      >
        <h2 className="sr-only" id={headingId}>
          Search everything
        </h2>
        <div className="search-box__field">
          <SearchIcon size={16} />
          <input
            ref={inputRef}
            type="search"
            className="search-box__input"
            placeholder="Search outcomes, evidence, notes, jobs…"
            aria-label="Search everything"
            aria-haspopup="listbox"
            aria-controls={listId}
            aria-activedescendant={activeOptionId}
            aria-autocomplete="list"
            autoComplete="off"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <kbd className="search-box__hint">Esc</kbd>
        </div>

        {slow ? (
          <p className="search-box__status" role="status">
            Searching…
          </p>
        ) : null}

        <div className="search-box__results" role="listbox" id={listId} aria-label="Search results">
          {!hasQuery ? (
            <p className="search-box__empty">
              Type to search every stored outcome, evidence quote, note, job, and step.
            </p>
          ) : hits.length === 0 && !slow ? (
            <p className="search-box__empty">{`Nothing matches “${settled}”.`}</p>
          ) : (
            results.groups.map((group) => (
              <div
                key={group.kind}
                className="search-box__group"
                role="group"
                aria-label={group.label}
              >
                <p className="search-box__group-title" role="presentation" aria-hidden="true">
                  {group.label}
                  <span className="search-box__group-count">{group.hits.length}</span>
                </p>
                {group.hits.map((hit) => {
                  const flatIndex = hits.findIndex(
                    (entry) => entry.hit.kind === hit.kind && entry.hit.id === hit.id,
                  );
                  const active = flatIndex === activeIndex;
                  return (
                    <button
                      key={`${hit.kind}:${hit.id}`}
                      ref={(element) => {
                        if (element) {
                          optionRefs.current.set(flatIndex, element);
                        } else {
                          optionRefs.current.delete(flatIndex);
                        }
                      }}
                      type="button"
                      role="option"
                      id={`${listId}-option-${flatIndex}`}
                      aria-selected={active}
                      className={`search-box__hit${active ? " is-active" : ""}`}
                      onMouseEnter={() => setActiveIndex(flatIndex)}
                      onClick={() => openHit({ hit, groupLabel: group.label })}
                    >
                      <span className="sr-only">{`${group.label}: `}</span>
                      <span className="search-box__hit-label">{hit.label}</span>
                      <span className="search-box__hit-snippet">{hit.snippet}</span>
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        <p className="sr-only" role="status">
          {hasQuery
            ? hits.length === 0
              ? "No matches"
              : `${results.total} ${results.total === 1 ? "match" : "matches"}`
            : ""}
        </p>

        {results.truncated ? (
          <p className="search-box__status">{`Showing the best ${hits.length} of ${results.total} matches. Keep typing to narrow.`}</p>
        ) : null}
      </div>
    </div>
  );
}
