import { useEffect, useRef, useState } from "react";

import { useFocusTrap } from "../../lib/useFocusTrap";
import { useStudio } from "../../state/StudioContext";
import { CloseIcon, PlugIcon } from "../icons";

/**
 * The discovery nudge. The studio offers one connector at a time: either the
 * one the agent just suggested, or — when the studio has nothing to read at
 * all — its first Editor's pick. One offer, three ways out, never a wall of
 * choices before the user has asked for one.
 */
export function ConnectorSuggestionModal() {
  const {
    connectorSuggestion,
    dismissConnectorModal,
    dismissConnectorSuggestion,
    openCustomize,
    installFromMarketplace,
  } = useStudio();
  const [installing, setInstalling] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, connectorSuggestion !== null);

  useEffect(() => {
    if (!connectorSuggestion) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        dismissConnectorModal();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [connectorSuggestion, dismissConnectorModal]);

  if (!connectorSuggestion) {
    return null;
  }

  const { listing, reason, id } = connectorSuggestion;

  function notNow() {
    dismissConnectorSuggestion(id);
    dismissConnectorModal();
  }

  function browseAll() {
    openCustomize({ query: listing?.name ?? id, listingId: listing?.id, tab: "connectors" });
  }

  async function install() {
    if (!listing) {
      browseAll();
      return;
    }
    setInstalling(true);
    const ok = await installFromMarketplace(listing);
    setInstalling(false);
    if (ok) {
      dismissConnectorSuggestion(id);
      dismissConnectorModal();
    }
  }

  return (
    <div
      ref={dialogRef}
      className="suggestion-modal"
      role="dialog"
      aria-modal="true"
      aria-label="Connector suggestion"
    >
      <div className="suggestion-modal__card">
        <button
          type="button"
          className="suggestion-modal__close"
          aria-label="Dismiss"
          onClick={notNow}
        >
          <CloseIcon size={15} />
        </button>
        <span className="suggestion-modal__mark" aria-hidden="true">
          <PlugIcon size={20} />
        </span>
        <h2 className="suggestion-modal__title">
          {reason === "empty" ? "Give the studio something to read" : "Connect a suggested system"}
        </h2>
        <p className="suggestion-modal__body">
          {listing
            ? `${listing.title ?? listing.name} — ${listing.summary}`
            : `The agent suggested “${id}”. Browse the marketplace to add it.`}
        </p>
        {listing && listing.env_vars.length > 0 ? (
          <p className="suggestion-modal__creds">
            Set <code>{listing.env_vars.join(", ")}</code> before the studio can use it.
          </p>
        ) : null}
        <div className="suggestion-modal__actions">
          {listing?.installable ? (
            <button
              type="button"
              className="button suggestion-modal__primary"
              disabled={installing}
              onClick={() => void install()}
            >
              {installing ? "Adding…" : "Add it"}
            </button>
          ) : null}
          <button type="button" className="button button--ghost" onClick={browseAll}>
            Browse all
          </button>
          <button type="button" className="quiet-action" onClick={notNow}>
            Not now
          </button>
        </div>
      </div>
    </div>
  );
}
