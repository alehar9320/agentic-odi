import { useState } from "react";

import { createShareLink } from "../api/studioApi";
import { canvasHasRecords } from "../lib/canvasProvenance";
import { useStudio } from "../state/StudioContext";
import { ShareSheet } from "./ShareSheet";

/**
 * The way to make one read-only link from the landscape.
 *
 * Creation lives on the artifact surface; the page the link opens lives at
 * `/shared/:token` and shares nothing with this one. Nothing is generated
 * locally and synced later: with no reachable sidecar there is nowhere to mint
 * a token, so the control is disabled and says so. An empty canvas has nothing
 * to share and says that too.
 */
export function ShareAction() {
  const { canvasState, sidecarReachable } = useStudio();
  const [open, setOpen] = useState(false);

  const hasRecords = canvasHasRecords(canvasState.data);
  const unreachable = sidecarReachable === false;
  const disabled = unreachable || !hasRecords;
  const reason = unreachable
    ? "Sharing needs the sidecar, and it is not reachable right now."
    : !hasRecords
      ? "Nothing to share yet."
      : null;

  return (
    <div className="share-action">
      <button
        type="button"
        className="studio-button"
        disabled={disabled}
        aria-disabled={disabled}
        title={reason ?? "Create a read-only link to this landscape"}
        onClick={() => setOpen(true)}
      >
        Share
      </button>
      {reason ? (
        <p className="share-action__reason" role="status">
          {reason}
        </p>
      ) : null}
      <ShareSheet
        isOpen={open}
        onClose={() => setOpen(false)}
        onCreate={(days) => createShareLink({ kind: "landscape", expires_in_days: days })}
      />
    </div>
  );
}
