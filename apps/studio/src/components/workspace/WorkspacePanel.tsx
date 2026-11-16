import { useEffect, useLayoutEffect, useMemo, useRef } from "react";

import { ResizableHandle, ResizablePanel } from "@/components/ui/resizable";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { buildRecords } from "../../lib/records";
import { useStudio } from "../../state/StudioContext";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { CloseIcon } from "../icons";
import { PanelBoundary } from "./PanelBoundary";
import type { WorkspacePanelId } from "../../types";
import { findPanel, WORKSPACE_PANELS, type PanelDefinition } from "./panels";

const MOBILE_QUERY = "(max-width: 1023px)";

/**
 * The lens body as its own component, so a lens that throws while rendering is
 * caught by the panel boundary instead of by the app.
 */
function PanelBody({ panel }: { panel: PanelDefinition }) {
  return <>{panel.render()}</>;
}

interface LensChromeProps {
  panel: PanelDefinition;
  conversationTitle: string;
  siblingCounts: Partial<Record<WorkspacePanelId, number>>;
  onOpenPanel: (id: WorkspacePanelId) => void;
  onClose: () => void;
  onTalk: () => void;
  headingRef: React.RefObject<HTMLHeadingElement | null>;
  bodyRef: React.RefObject<HTMLDivElement | null>;
  onScroll: () => void;
}

/**
 * The lens header, body, and foot. The same markup serves the docked panel and
 * the mobile sheet, so the two shells cannot drift apart.
 */
function LensChrome({
  panel,
  conversationTitle,
  siblingCounts,
  onOpenPanel,
  onClose,
  onTalk,
  headingRef,
  bodyRef,
  onScroll,
}: LensChromeProps) {
  return (
    <>
      <header className="lens__head">
        <div className="lens__heading">
          <p className="lens__where" aria-label={`In ${conversationTitle}`}>
            {conversationTitle}
          </p>
          <span className="lens__icon" aria-hidden="true">
            {panel.icon}
          </span>
          <div>
            <h2
              id={`lens-title-${panel.id}`}
              className="lens__title"
              tabIndex={-1}
              ref={headingRef}
            >
              {panel.title}
            </h2>
            <p className="lens__blurb">{panel.blurb}</p>
          </div>
        </div>
        <nav className="lens__siblings" aria-label="Other views">
          {WORKSPACE_PANELS.filter((item) => item.id !== panel.id).map((item) => {
            const count = siblingCounts[item.id];
            const label = typeof count === "number" ? `${item.label} (${count})` : item.label;
            return (
              <button
                key={item.id}
                type="button"
                className="lens__sibling"
                onClick={() => onOpenPanel(item.id)}
              >
                {label}
              </button>
            );
          })}
        </nav>
        <button
          type="button"
          className="icon-button"
          aria-label="Close workspace view"
          title="Close"
          onClick={onClose}
        >
          <CloseIcon size={16} />
        </button>
      </header>

      <div className="lens__body" ref={bodyRef} onScroll={onScroll}>
        <div className="lens__content">
          <PanelBoundary name={panel.id}>
            <PanelBody panel={panel} />
          </PanelBoundary>
        </div>
      </div>

      {panel.talk && (
        <footer className="lens__foot">
          <p className="lens__note">A lens on the conversation, not a separate place.</p>
          <button type="button" className="button button--block" onClick={onTalk}>
            {panel.talk.label}
          </button>
        </footer>
      )}
    </>
  );
}

/**
 * A lens on the conversation, not a place you go.
 *
 * On a wide screen it docks to the right as the second panel of the split, so
 * the separator resizes the lens and the thread together. On a narrow screen
 * there is no room for both, so it becomes a sheet over the thread. Both shells
 * come from the copied `resizable`/`sheet` primitives: focus trapping, Escape
 * handling, and sibling hiding are the primitive's job, not a bespoke DOM walk
 * (#407).
 */
export function WorkspacePanel() {
  const {
    activePanel,
    openPanel,
    closePanel,
    sendMessage,
    streaming,
    canvas,
    conversations,
    conversationId,
    memory,
    segments,
  } = useStudio();
  const isMobile = useMediaQuery(MOBILE_QUERY);
  const panel = activePanel ? findPanel(activePanel) : null;
  const panelId = panel?.id ?? null;
  const headingRef = useRef<HTMLHeadingElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  // Where each lens was left. The body remounts with the lens, so the position
  // has to outlive the DOM to come back with it — per panel, never global (#696).
  const scrollByPanel = useRef(new Map<WorkspacePanelId, number>());
  const returnFocusRef = useRef<HTMLElement | null>(null);
  // Which element had focus when the panel opened, so closing the lens can
  // return focus there instead of stealing it for the composer (#696).
  // Never capture a textbox (a textarea or a text-type input) as the return
  // target — focus returning to a text field moves the caret, which is exactly
  // what this guard prevents.
  // A lens opens from the rail, a canvas card, a banner, or a slash command,
  // and the composer is autofocused: "whatever held focus" is the composer, not
  // the control the person used. Remember that control instead (#692).
  const isTextbox = (el: HTMLElement) =>
    el.tagName === "TEXTAREA" ||
    (el.tagName === "INPUT" &&
      ["text", "search", "url", "tel", "email", "password", ""].includes(
        (el as HTMLInputElement).type,
      ));
  const openerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    function rememberOpener(event: MouseEvent) {
      const target = event.target;
      const control =
        target instanceof Element ? target.closest("button, a[href], [role=button]") : null;
      openerRef.current = control instanceof HTMLElement ? control : null;
    }
    document.addEventListener("click", rememberOpener, true);
    return () => document.removeEventListener("click", rememberOpener, true);
  }, []);

  // The header says where you are: the conversation this lens belongs to, and
  // the sibling lenses with the count each one holds (#324).
  const conversationTitle = useMemo(() => {
    const current = conversations.find((item) => item.id === conversationId);
    const title = current?.title?.trim();
    return title || "This conversation";
  }, [conversations, conversationId]);

  const siblingCounts = useMemo(() => {
    const outcomes = canvas?.outcomes ?? [];
    const steps = canvas?.steps ?? [];
    const evidence = outcomes.filter((outcome) => outcome.evidence?.trim()).length;
    const records = buildRecords(canvas);
    return {
      records: records.length,
      landscape: outcomes.length,
      jobmap: steps.length,
      segments: segments.length,
      evidence,
      memory: memory.length,
    } as Partial<Record<WorkspacePanelId, number>>;
  }, [canvas, memory, segments]);

  // On a wide screen the lens opens under the keyboard, so focus goes to the
  // heading and comes back to the control that opened it. The composer is
  // autofocused, so recording "whatever held focus" would pull the caret out
  // of the lens and into the thread on Escape; only a lens with no distinct
  // opener falls back to the previously focused element. The mobile sheet
  // keeps its own trap and return path; this stays out of its way (#696).
  useEffect(() => {
    if (!panelId) {
      const target = returnFocusRef.current;
      returnFocusRef.current = null;
      if (target?.isConnected) {
        target.focus();
      }
      return;
    }
    if (isMobile) {
      return;
    }
    if (!returnFocusRef.current) {
      const opener = openerRef.current;
      openerRef.current = null;
      const active = document.activeElement;
      returnFocusRef.current =
        opener?.isConnected && opener !== headingRef.current
          ? opener
          : active instanceof HTMLElement && !isTextbox(active)
          ? active
          : null;
    }
    headingRef.current?.focus();
  }, [panelId, isMobile]);

  // Escape closes the open lens and returns focus to its opener. Captured so it
  // never reaches the app-level handler. A running reply is the exception: Escape
  // stops the stream first and leaves the lens open, which is the order the app
  // shell promises (#324, #692).
  useEffect(() => {
    if (!activePanel) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape" || streaming) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      closePanel();
    }
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [activePanel, streaming, closePanel]);

  // A lens opens where it was left; a different lens starts at its top.
  useLayoutEffect(() => {
    if (!panelId) {
      return;
    }
    const body = bodyRef.current;
    if (!body) {
      return;
    }
    body.scrollTop = scrollByPanel.current.get(panelId) ?? 0;
  }, [panelId]);

  function rememberScroll() {
    const body = bodyRef.current;
    if (!body || !panelId) {
      return;
    }
    scrollByPanel.current.set(panelId, body.scrollTop);
  }

  function talk() {
    if (!panel?.talk) {
      return;
    }
    closePanel();
    void sendMessage(panel.talk.intent);
  }

  const chrome = panel ? (
    <LensChrome
      panel={panel}
      conversationTitle={conversationTitle}
      siblingCounts={siblingCounts}
      onOpenPanel={openPanel}
      onClose={closePanel}
      onTalk={talk}
      headingRef={headingRef}
      bodyRef={bodyRef}
      onScroll={rememberScroll}
    />
  ) : null;

  // The sheet stays mounted while the lens is closed so the copied primitive
  // owns its own open/close transition and returns focus to the trigger. An
  // always-`open` sheet would bypass that lifecycle and strand focus on `<body>`.
  if (isMobile) {
    return (
      <Sheet open={Boolean(panel)} onOpenChange={(open) => !open && closePanel()}>
        {panel ? (
          <SheetContent
            className="lens lens--sheet"
            side="right"
            showCloseButton={false}
            aria-label={panel.title}
          >
            <SheetTitle className="sr-only">{panel.title}</SheetTitle>
            {chrome}
          </SheetContent>
        ) : null}
      </Sheet>
    );
  }

  if (!panel) {
    return null;
  }

  return (
    <>
      <ResizableHandle withHandle />
      <ResizablePanel
        className="lens-panel"
        defaultSize={480}
        minSize={360}
        maxSize={760}
        key={panel.id}
      >
        <aside
          className="lens lens--docked"
          role="complementary"
          aria-labelledby={`lens-title-${panel.id}`}
        >
          {chrome}
        </aside>
      </ResizablePanel>
    </>
  );
}
