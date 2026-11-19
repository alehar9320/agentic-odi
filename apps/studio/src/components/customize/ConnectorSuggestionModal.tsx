import { useState } from "react";

import { Dialog } from "@/components/ui/dialog";
import { useStudio } from "../../state/StudioContext";
import { PlugIcon } from "../icons";

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

  if (!connectorSuggestion) {
    return null;
  }

  const { listing, reason, id } = connectorSuggestion;

  function notNow() {
    dismissConnectorSuggestion(id);
    dismissConnectorModal();
  }

  function browseAll() {
    openCustomize({ query: listing?.name ?? id });
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
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) {
          dismissConnectorModal();
        }
      }}
      title={reason === "empty" ? "Give the studio something to read" : "Connect a suggested system"}
      footer={
        <>
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
        </>
      }
    >
      <span className="suggestion-modal__mark" aria-hidden="true">
        <PlugIcon size={20} />
      </span>
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
    </Dialog>
  );
}
