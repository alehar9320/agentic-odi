import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import { PRODUCT_NAME } from "../../lib/brand";
import { formatRelativeTime } from "../../lib/relativeTime";
import { useFocusTrap } from "../../lib/useFocusTrap";
import { MOBILE_QUERY, useMediaQuery } from "../../lib/useMediaQuery";
import {
  IDENTITY_ROLE_PLACEHOLDER,
  useUserIdentity,
} from "../../lib/identity";
import { useStudio } from "../../state/StudioContext";
import { detectPlatform, shortcutLabels } from "../../updater/platform";
import { MenuIcon, PlusIcon, RouteIcon } from "../icons";
import { OdiMascot } from "../OdiMascot";

/**
 * The left drawer (#736): what you are working on, and who you are.
 *
 * It holds the brand the bar used to render, one way to start, the recent
 * threads, the job map, and the identity chip. It does not hold the eight
 * lenses: details are reached from the mainstage, and the drawer is not a
 * second switcher. The one destination it carries is the job map (#736 d);
 * the identity menu's Set your name is the settings path the issue sanctions,
 * because it is the person's own record, not a finding.
 *
 * Collapsing hides the region rather than unmounting this component, so the
 * scroll position and the identity menu come back where they were. `drawerOpen`
 * is the state (#735) and its value is persisted by the region hook.
 */
export function NavigationDrawer({
  onHome,
  onNew,
}: {
  onHome: () => void;
  onNew: () => void;
}) {
  const {
    conversations,
    conversationId,
    openConversation,
    refreshConversations,
    drawerOpen,
    toggleDrawer,
    openDetail,
    openPanel,
    pushToast,
  } = useStudio();
  const identity = useUserIdentity();
  const isMobile = useMediaQuery(MOBILE_QUERY);
  const keys = shortcutLabels(detectPlatform());
  const [menuOpen, setMenuOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const scrollRef = useRef(0);
  const wasOpen = useRef(drawerOpen);

  useFocusTrap(drawerRef, isMobile && drawerOpen);

  // The history list is read when it opens, not polled.
  useEffect(() => {
    if (drawerOpen) {
      void refreshConversations();
    }
  }, [drawerOpen, refreshConversations]);

  // Collapsing returns focus to the control that collapsed it.
  useEffect(() => {
    if (wasOpen.current && !drawerOpen) {
      document.getElementById("studio-drawer-toggle")?.focus();
    }
    wasOpen.current = drawerOpen;
  }, [drawerOpen]);

  // A collapsed drawer keeps its place: the list's scroll offset outlives the
  // DOM this component stops rendering.
  useLayoutEffect(() => {
    if (drawerOpen && listRef.current) {
      listRef.current.scrollTop = scrollRef.current;
    }
  }, [drawerOpen]);

  // The identity menu closes on a click outside and owns its Escape. Capture
  // stops the keystroke before the shell's Escape closes the drawer too.
  useEffect(() => {
    if (!menuOpen) {
      return;
    }
    function onPointerDown(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      setMenuOpen(false);
      menuButtonRef.current?.focus();
    }
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown, true);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown, true);
    };
  }, [menuOpen]);

  function onDrawerKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (!isMobile || event.key !== "Escape") {
      return;
    }
    // A sheet is a modal: it closes itself before the shell's Escape reaches
    // the stream behind it.
    event.preventDefault();
    event.stopPropagation();
    toggleDrawer();
  }

  function setName() {
    setMenuOpen(false);
    // The Settings path the issue names; it is a top-bar control, not a
    // mainstage finding, so opening it from the identity chip is sanctioned.
    openPanel("settings");
    if (isMobile) {
      toggleDrawer();
    }
  }

  function openJobMap() {
    openDetail("jobmap");
    if (isMobile) {
      toggleDrawer();
    }
  }

  function selectThread(id: string) {
    if (isMobile) {
      toggleDrawer();
    }
    if (id === conversationId) {
      return;
    }
    void openConversation(id).catch(() =>
      pushToast("error", "I couldn't open that conversation."),
    );
  }

  if (!drawerOpen) {
    return null;
  }

  return (
    <>
      {isMobile && (
        <button
          type="button"
          className="scrim"
          aria-label="Close navigation"
          onClick={toggleDrawer}
        />
      )}
      <div
        ref={drawerRef}
        id="studio-drawer"
        className={`drawer${isMobile ? " drawer--sheet" : ""}`}
        role={isMobile ? "dialog" : undefined}
        aria-modal={isMobile ? true : undefined}
        aria-label={isMobile ? "Navigation" : undefined}
        onKeyDown={onDrawerKeyDown}
      >
        <nav className="drawer__nav" aria-label="Your work">
          <div className="drawer__head">
            <button
              type="button"
              className="drawer__brand"
              onClick={onHome}
              aria-label={`${PRODUCT_NAME}, go to home`}
              title="Home"
            >
              <span className="drawer__mark" aria-hidden="true">
                <OdiMascot size={32} />
              </span>
              <span className="drawer__wordmark">{PRODUCT_NAME}</span>
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label="Collapse navigation"
              title="Collapse"
              onClick={toggleDrawer}
            >
              <MenuIcon size={17} />
            </button>
          </div>

          <button type="button" className="drawer__new" onClick={onNew}>
            <PlusIcon size={16} />
            <span className="drawer__new-label">New inquiry</span>
            <kbd className="drawer__kbd">{keys.focus}</kbd>
          </button>

          <section className="drawer__section" aria-labelledby="drawer-recent">
            <h2 id="drawer-recent" className="drawer__section-title">
              Recent threads
            </h2>
            {conversations.length === 0 ? (
              <p className="drawer__empty">
                No threads yet. Your first inquiry will stay here.
              </p>
            ) : (
              <ul
                ref={listRef}
                className="drawer__list"
                aria-labelledby="drawer-recent"
                onScroll={(event) => {
                  scrollRef.current = event.currentTarget.scrollTop;
                }}
              >
                {conversations.slice(0, 12).map((conversation) => {
                  const current = conversation.id === conversationId;
                  const title = conversation.title.trim() || "New conversation";
                  return (
                    <li key={conversation.id}>
                      <button
                        type="button"
                        className="drawer__thread"
                        aria-current={current ? "page" : undefined}
                        onClick={() => selectThread(conversation.id)}
                      >
                        <span className="drawer__thread-title">{title}</span>
                        <span className="drawer__thread-meta">
                          {formatRelativeTime(conversation.updated_at)}
                          {conversation.turn_count > 0
                            ? ` · ${conversation.turn_count} ${
                                conversation.turn_count === 1 ? "turn" : "turns"
                              }`
                            : ""}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <div className="drawer__destinations">
            <button type="button" className="drawer__link" onClick={openJobMap}>
              <RouteIcon size={15} />
              <span>Job map</span>
            </button>
          </div>

          <div className="drawer__foot">
            <div className="drawer__identity">
              <span className="drawer__avatar" aria-hidden="true">
                {identity.initial}
              </span>
              <span className="drawer__who">
                <span className="drawer__name">{identity.name}</span>
                <span className="drawer__role">
                  {identity.role ?? IDENTITY_ROLE_PLACEHOLDER}
                </span>
              </span>
              <div className="drawer__menu" ref={menuRef}>
                <button
                  ref={menuButtonRef}
                  type="button"
                  className="icon-button"
                  aria-label="Identity options"
                  title="Identity options"
                  aria-haspopup="menu"
                  aria-expanded={menuOpen}
                  onClick={() => setMenuOpen((open) => !open)}
                >
                  <MenuIcon size={15} />
                </button>
                {menuOpen && (
                  <div className="drawer__menu-list" role="menu" aria-label="Identity options">
                    <button
                      type="button"
                      role="menuitem"
                      className="drawer__menu-item"
                      onClick={setName}
                    >
                      Set your name
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </nav>
      </div>
    </>
  );
}
