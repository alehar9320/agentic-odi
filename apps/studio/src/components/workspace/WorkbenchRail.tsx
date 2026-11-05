import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import { canvasStatus } from "../../lib/canvasProvenance";
import { useFocusTrap } from "../../lib/useFocusTrap";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { useNavigationCounts } from "../../state/useNavigationCounts";
import { useStudio } from "../../state/StudioContext";
import type { WorkspacePanelId } from "../../types";
import { PanelLeftIcon } from "../icons";
import { SETTINGS_PANEL, WORKSPACE_PANELS, type PanelDefinition } from "./panels";

const SIDEBAR_KEY = "studio.sidebar";
const NARROW_QUERY = "(max-width: 1279px)";
const DRAWER_QUERY = "(max-width: 1023px)";

/** What the rows in a destination are called, out loud. */
const NOUNS: Partial<Record<WorkspacePanelId, [singular: string, plural: string]>> = {
  records: ["record", "records"],
  catchup: ["unread signal", "unread signals"],
  landscape: ["opportunity", "opportunities"],
  jobmap: ["step", "steps"],
  segments: ["segment", "segments"],
  evidence: ["quote", "quotes"],
  memory: ["note", "notes"],
  schedule: ["scheduled run", "scheduled runs"],
};

const MAX_COUNT = 99;

function readPreference(): "expanded" | "collapsed" | null {
  try {
    const stored = window.localStorage.getItem(SIDEBAR_KEY);
    return stored === "expanded" || stored === "collapsed" ? stored : null;
  } catch {
    return null;
  }
}

/**
 * Cmd/Ctrl+B belongs to the map, except while a person is selecting text: then
 * the keypress is theirs and the field's, not ours.
 */
function isTextSelection(target: EventTarget | null): boolean {
  const element = target as HTMLInputElement | HTMLTextAreaElement | null;
  if (!element || typeof element.selectionStart !== "number") {
    return false;
  }
  return element.selectionStart !== element.selectionEnd;
}

function displayCount(count: number): string {
  return count > MAX_COUNT ? `${MAX_COUNT}+` : String(count);
}

function countLabel(count: number, noun: [string, string] | undefined): string {
  if (!noun) {
    return displayCount(count);
  }
  return `${displayCount(count)} ${count === 1 ? noun[0] : noun[1]}`;
}

/**
 * The map of the Studio, down the left of the stage.
 *
 * It is a map and not a list of results, so it does not disappear when there is
 * nothing to show: an empty repository is exactly when a person needs to know
 * where the other destinations are. Its rows come from the panel registry, so a
 * destination cannot exist without being findable, and its counts come from one
 * hook, so a number cannot disagree with the list it promises.
 */
export function WorkbenchRail() {
  const { canvas, memory, activePanel, openPanel, closePanel } = useStudio();
  const counts = useNavigationCounts();
  const isNarrow = useMediaQuery(NARROW_QUERY);
  const isDrawer = useMediaQuery(DRAWER_QUERY);
  const [preference, setPreference] = useState<"expanded" | "collapsed" | null>(readPreference);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const listRef = useRef<HTMLUListElement>(null);
  const drawerRef = useRef<HTMLElement>(null);

  const panels = useMemo<PanelDefinition[]>(() => [...WORKSPACE_PANELS, SETTINGS_PANEL], []);
  const collapsed = !isDrawer && (preference ? preference === "collapsed" : isNarrow);
  const status = canvasStatus(canvas);
  const suggestsMemory = memory.some((note) => note.status === "suggested");

  const focusRow = useCallback((index: number) => {
    const rows = Array.from(listRef.current?.querySelectorAll<HTMLButtonElement>(".rail__row") ?? []);
    if (rows.length === 0) {
      return;
    }
    const target = ((index % rows.length) + rows.length) % rows.length;
    rows[target]?.focus();
  }, []);

  function onListKeyDown(event: ReactKeyboardEvent<HTMLUListElement>) {
    const rows = Array.from(
      listRef.current?.querySelectorAll<HTMLButtonElement>(".rail__row") ?? [],
    );
    const current = rows.indexOf(document.activeElement as HTMLButtonElement);
    if (current === -1) {
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusRow(current + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      focusRow(current - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusRow(0);
    } else if (event.key === "End") {
      event.preventDefault();
      focusRow(rows.length - 1);
    }
  }

  const toggleMap = useCallback(() => {
    const next = collapsed ? "expanded" : "collapsed";
    setPreference(next);
    try {
      window.localStorage.setItem(SIDEBAR_KEY, next);
    } catch {
      // A private mode that refuses the write is not a reason to stop the map
      // from collapsing for the rest of this session.
    }
  }, [collapsed]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "b") {
        return;
      }
      if (isDrawer || isTextSelection(event.target)) {
        return;
      }
      event.preventDefault();
      toggleMap();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isDrawer, toggleMap]);

  useFocusTrap(drawerRef, isDrawer && drawerOpen);

  // Escape closes the drawer without also stopping a reply behind it.
  useEffect(() => {
    if (!isDrawer || !drawerOpen) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        setDrawerOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [isDrawer, drawerOpen]);

  function choose(id: WorkspacePanelId) {
    if (activePanel === id) {
      closePanel();
    } else {
      openPanel(id);
    }
    if (isDrawer) {
      setDrawerOpen(false);
    }
  }

  const rows = panels.map((panel) => {
    const count = counts[panel.id];
    const open = activePanel === panel.id;
    return {
      panel,
      count,
      open,
      dot: panel.id === "memory" && suggestsMemory,
      name:
        count === undefined
          ? panel.label
          : `${panel.label}, ${countLabel(count, NOUNS[panel.id])}`,
    };
  });
  const firstOpen = rows.findIndex((row) => row.open);
  const tabIndexAnchor = firstOpen === -1 ? 0 : firstOpen;

  const navigation = (
    <nav
      ref={isDrawer ? drawerRef : undefined}
      id="studio-map"
      className={[
        "rail",
        collapsed ? "rail--collapsed" : "",
        isDrawer ? "rail--drawer" : "",
        isDrawer && !drawerOpen ? "is-closed" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      aria-label="Studio"
      role={isDrawer ? "dialog" : undefined}
      aria-modal={isDrawer ? drawerOpen : undefined}
      hidden={isDrawer && !drawerOpen}
    >
      <header className="rail__head">
        <span className="rail__title">Studio</span>
        {status ? (
          <span className="rail__status" title={status.detail}>
            {status.label}
          </span>
        ) : null}
        {!isDrawer && (
          <button
            type="button"
            className="rail__toggle icon-button"
            aria-label={collapsed ? "Expand the map" : "Collapse the map"}
            title="Cmd/Ctrl+B"
            onClick={toggleMap}
          >
            <PanelLeftIcon size={16} />
          </button>
        )}
      </header>

      <ul ref={listRef} className="rail__list" onKeyDown={onListKeyDown}>
        {rows.map((row, index) => (
          <li key={row.panel.id}>
            <button
              type="button"
              className={`rail__row${row.open ? " is-open" : ""}`}
              data-panel={row.panel.id}
              aria-current={row.open ? "page" : undefined}
              aria-label={row.name}
              title={collapsed ? row.name : undefined}
              tabIndex={index === tabIndexAnchor ? 0 : -1}
              onClick={() => choose(row.panel.id)}
            >
              <span className="rail__icon" aria-hidden="true">
                {row.panel.icon}
              </span>
              <span className="rail__label">{row.panel.label}</span>
              {row.dot ? <span className="rail__dot" aria-hidden="true" /> : null}
              {row.count !== undefined ? (
                <span className="rail__count">{displayCount(row.count)}</span>
              ) : null}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );

  if (!isDrawer) {
    return navigation;
  }

  return (
    <>
      <button
        type="button"
        className="rail__opener icon-button"
        aria-expanded={drawerOpen}
        aria-controls="studio-map"
        aria-label="Studio map"
        onClick={() => setDrawerOpen(true)}
      >
        <PanelLeftIcon size={16} />
      </button>
      {drawerOpen ? (
        <button
          type="button"
          className="scrim"
          aria-label="Close the map"
          onClick={() => setDrawerOpen(false)}
        />
      ) : null}
      {navigation}
    </>
  );
}
