import { useId } from "react";

import type { CapabilityId } from "../bff/capabilities/registry";
import { blockedReason, type BlockedActionKind } from "../lib/blockedReason";
import { useStudio } from "../state/StudioContext";

/**
 * The one place a blocked action is explained. The control keeps its disabled
 * state and points here with `aria-describedby`, so a person reads why at the
 * control they pressed instead of hunting a global banner.
 */
export function BlockedReasonNote({
  capability,
  id,
}: {
  capability: CapabilityId;
  id?: string;
}) {
  const generatedId = useId();
  const noteId = id ?? generatedId;
  const reason = blockedReason(capability);
  const { openPanel, openSetup, recheckConnections } = useStudio();

  function run(kind: BlockedActionKind) {
    switch (kind) {
      case "start-sidecar":
        openSetup();
        break;
      case "add-model":
        openPanel("settings");
        break;
      case "install-connector":
      case "connect-source":
        openPanel("capture");
        break;
      case "keep-working":
        void recheckConnections();
        break;
    }
  }

  return (
    <p className="blocked-reason" id={noteId}>
      <span className="blocked-reason__text">{reason.sentence}</span>{" "}
      <button
        type="button"
        className="quiet-action blocked-reason__action"
        onClick={() => run(reason.action.kind)}
      >
        {reason.action.label}
      </button>
    </p>
  );
}
