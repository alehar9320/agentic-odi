import { useEffect, useRef, useState } from "react";

import { useFocusTrap } from "../lib/useFocusTrap";
import type { ShareLink } from "../types";
import { CheckIcon, CloseIcon, CopyIcon } from "./icons";

/**
 * The one place a read-only link is made.
 *
 * Choosing a duration mints a link for one artifact and shows it once. When the
 * store offers no revoke, the sheet says the link cannot be revoked from this
 * build rather than pretending otherwise — the honest thing is the whole point
 * of the page the link opens. The share-creation flow and the read-only page are
 * separate journeys; this is only the creation half.
 */

const DURATIONS = [
  { days: 7, label: "7 days" },
  { days: 14, label: "14 days" },
  { days: 30, label: "30 days" },
];

interface ShareSheetProps {
  isOpen: boolean;
  onClose: () => void;
  /** Mint a link for one artifact, for the chosen number of days. */
  onCreate: (days: number) => Promise<ShareLink>;
  /** Revoke a link by id, when the store supports it. Omit to hide revoke. */
  onRevoke?: (id: string) => Promise<void>;
}

export function ShareSheet({ isOpen, onClose, onCreate, onRevoke }: ShareSheetProps) {
  // The body mounts only while open, so each open starts from fresh state
  // without an effect resetting it after the fact.
  return isOpen ? (
    <ShareSheetBody onClose={onClose} onCreate={onCreate} onRevoke={onRevoke} />
  ) : null;
}

function ShareSheetBody({
  onClose,
  onCreate,
  onRevoke,
}: {
  onClose: () => void;
  onCreate: (days: number) => Promise<ShareLink>;
  onRevoke?: (id: string) => Promise<void>;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [days, setDays] = useState(7);
  const [link, setLink] = useState<ShareLink | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [revoked, setRevoked] = useState(false);

  useFocusTrap(dialogRef, true);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const created = await onCreate(days);
      setLink(created);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create the link.");
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!link) {
      return;
    }
    const url = `${window.location.origin}/shared/${link.token}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      setError("Copying was blocked. Select the link and copy it by hand.");
    }
  }

  async function revoke() {
    if (!link || !onRevoke) {
      return;
    }
    setBusy(true);
    try {
      await onRevoke(link.id);
      setRevoked(true);
      setLink(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not revoke the link.");
    } finally {
      setBusy(false);
    }
  }

  const shareUrl = link ? `${window.location.origin}/shared/${link.token}` : null;

  return (
    <div
      ref={dialogRef}
      className="share-sheet"
      role="dialog"
      aria-modal="true"
      aria-label="Share a read-only link"
    >
      <div className="share-sheet__card">
        <button type="button" className="share-sheet__close" aria-label="Close" onClick={onClose}>
          <CloseIcon size={15} />
        </button>
        <h2 className="share-sheet__title">Share a read-only link</h2>
        <p className="share-sheet__body">
          One artifact, read-only, expiring. The link never carries the workspace, memory,
          conversations, or connector secrets.
        </p>

        {error ? (
          <p className="share-sheet__error" role="alert">
            {error}
          </p>
        ) : null}

        {shareUrl ? (
          <div className="share-sheet__result">
            <label className="sr-only" htmlFor="share-url">
              Shareable link
            </label>
            <input id="share-url" className="input" readOnly value={shareUrl} />
            <button type="button" className="button" onClick={() => void copy()}>
              {copied ? <CheckIcon size={14} /> : <CopyIcon size={14} />} Copy link
            </button>
            {onRevoke ? (
              <button
                type="button"
                className="quiet-action quiet-action--danger"
                disabled={busy}
                onClick={() => void revoke()}
              >
                Revoke link
              </button>
            ) : (
              <p className="share-sheet__note">
                This link cannot be revoked from this build. It stops working on its own when it
                expires.
              </p>
            )}
          </div>
        ) : revoked ? (
          <p className="share-sheet__note" role="status">
            The link no longer works.
          </p>
        ) : (
          <div className="share-sheet__create">
            <label className="share-sheet__field" htmlFor="share-duration">
              Link expires
              <select
                id="share-duration"
                className="select"
                value={days}
                disabled={busy}
                onChange={(event) => setDays(Number(event.target.value))}
              >
                {DURATIONS.map((option) => (
                  <option key={option.days} value={option.days}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="button share-sheet__primary"
              disabled={busy}
              onClick={() => void create()}
            >
              {busy ? "Creating…" : "Create link"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
